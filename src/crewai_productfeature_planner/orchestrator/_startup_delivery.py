"""Startup delivery crew factory.

Scans MongoDB for completed PRDs that still need Confluence publishing
or Jira ticket creation and builds a CrewAI Crew per pending item.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_jira_credentials,
    _print_delivery_status,
    build_additional_prd_context_from_doc,
    logger,
)

if TYPE_CHECKING:
    from crewai import Crew


# ── Types ─────────────────────────────────────────────────────────────

DeliveryItem = dict  # type alias for readability


# ── Discovery ─────────────────────────────────────────────────────────


def _discover_pending_deliveries() -> list[DeliveryItem]:
    """Scan MongoDB for completed PRDs that still need delivery.

    Returns a list of dicts, each containing the ``run_id``, assembled
    ``content``, ``idea``, delivery flags, and the raw workingIdeas
    document for downstream use.
    """
    from crewai_productfeature_planner.components.document import assemble_prd_from_doc
    from crewai_productfeature_planner.mongodb import get_db
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
    )

    try:
        db = get_db()
        completed_docs = list(
            db["workingIdeas"]
            .find({"status": "completed"})
            .sort("created_at", 1)
        )
    except Exception as exc:
        logger.warning("[StartupDelivery] Failed to query completed ideas: %s", exc)
        return []

    has_jira = _has_jira_credentials()

    items: list[DeliveryItem] = []
    for doc in completed_docs:
        run_id = doc.get("run_id", "")
        if not run_id:
            continue

        record = get_delivery_record(run_id)

        # A record may have been prematurely marked "completed" by
        # older code that treated absent Jira credentials as "done".
        # Re-evaluate when Jira creds are now available but the
        # jira_completed flag is still False.
        if record and record.get("status") == "completed":
            if has_jira and not record.get("jira_completed"):
                logger.info(
                    "[StartupDelivery] Re-evaluating run_id=%s — "
                    "record marked completed but jira_completed is False",
                    run_id,
                )
            else:
                continue

        confluence_done = bool(
            record and record.get("confluence_published")
        ) or bool(doc.get("confluence_url"))
        # Only reflect *actual* Jira completion from the DB — never
        # infer "done" from missing credentials so the flag stays
        # False until tickets are genuinely created.
        jira_done = bool(record and record.get("jira_completed"))

        if confluence_done and (jira_done or not has_jira):
            # Mark as completed and skip — but preserve the real
            # jira_completed value so it can be picked up later
            # when credentials are configured.
            from crewai_productfeature_planner.mongodb.product_requirements import (
                upsert_delivery_record,
            )
            upsert_delivery_record(
                run_id,
                confluence_published=True,
                confluence_url=doc.get("confluence_url", ""),
                jira_completed=jira_done,
            )
            continue

        content = assemble_prd_from_doc(doc)
        if not content:
            continue

        # Reconstruct useful fields
        finalized_idea = ""
        raw_exec = doc.get("executive_summary", [])
        if isinstance(raw_exec, list) and raw_exec:
            latest = raw_exec[-1]
            if isinstance(latest, dict):
                finalized_idea = latest.get("content", "")

        func_reqs = ""
        section_obj = doc.get("section", {})
        if isinstance(section_obj, dict):
            fr_iters = section_obj.get("functional_requirements", [])
            if isinstance(fr_iters, list) and fr_iters:
                latest_fr = fr_iters[-1]
                if isinstance(latest_fr, dict):
                    func_reqs = latest_fr.get("content", "")

        # Existing Jira tickets from a previous partial run.
        jira_tickets = (record.get("jira_tickets") or []) if record else []

        items.append({
            "run_id": run_id,
            "idea": doc.get("idea", "PRD"),
            "content": content,
            "confluence_done": confluence_done,
            "confluence_url": doc.get("confluence_url", ""),
            "jira_done": jira_done,
            "jira_tickets": jira_tickets,
            "finalized_idea": finalized_idea,
            "func_reqs": func_reqs,
            "doc": doc,
        })

    return items


# ── Crew factory ──────────────────────────────────────────────────────


def build_startup_delivery_crew(
    item: DeliveryItem,
    *,
    progress_callback: "Callable[[str], None] | None" = None,
) -> "Crew":
    """Build a CrewAI Crew for delivering a single pending PRD.

    Uses a **sequential process** with collaboration between up to four agents:

    * **Delivery Manager** — coordinates the delivery lifecycle,
      decides which steps are needed, and delegates tool-bearing
      work to specialist agents.
    * **Orchestrator** — executes Confluence publishing using its
      tool suite.
    * **Jira Product Manager** — creates Jira Epics and role-specific
      Stories with product-management reasoning (SMART criteria,
      user-outcome focus, dependency sequencing).
    * **Jira Architect / Tech Lead** — creates granular Tasks under
      each Story with architectural reasoning (data schemas, API
      contracts, Frontend/Backend splits, dependency ordering).

    The Crew runs four chained tasks (via ``context``):

    1. **Assess delivery status** — Delivery Manager analyses what is
       pending for this run_id.
    2. **Publish to Confluence** — Orchestrator publishes the PRD
       (skipped if already published).
    3. **Create Jira Epic + Stories** — Orchestrator creates Epic, then
       role-specific Stories (UX, Engineering, QE) with dependencies.
    4. **Create Jira Tasks** — Orchestrator creates granular sub-tasks
       under each Story (skipped if no functional requirements).

    Args:
        item:  A :data:`DeliveryItem` dict from
               :func:`_discover_pending_deliveries`.
        progress_callback:  Optional callable invoked with status
               messages as each task completes.

    Returns:
        A configured :class:`Crew` instance ready for ``kickoff()``.
    """
    from crewai import Crew, Process, Task

    from crewai_productfeature_planner.agents.orchestrator.agent import (
        create_delivery_manager_agent,
        create_jira_architect_tech_lead_agent,
        create_jira_product_manager_agent,
        create_orchestrator_agent,
        get_task_configs,
    )
    from crewai_productfeature_planner.scripts.logging_config import is_verbose
    from crewai_productfeature_planner.scripts.memory_loader import (
        resolve_project_id,
    )

    run_id = item["run_id"]
    idea_preview = (item["idea"] or "PRD")[:80].strip()
    page_title = f"PRD — {idea_preview}"
    task_configs = get_task_configs()

    # ── Set project-level Jira key override (if configured) ────
    from crewai_productfeature_planner.mongodb.project_config import (
        get_project_for_run,
    )
    from crewai_productfeature_planner.tools.jira_tool import set_jira_project_key

    pc = get_project_for_run(run_id) or {}
    ctx_key = pc.get("jira_project_key", "")
    if ctx_key:
        set_jira_project_key(ctx_key)
        logger.info(
            "[StartupDelivery] Using project-level JIRA_PROJECT_KEY=%s",
            ctx_key,
        )

    # Resolve project_id for memory enrichment
    project_id = resolve_project_id(run_id)

    delivery_manager = create_delivery_manager_agent(project_id=project_id)
    orchestrator_agent = create_orchestrator_agent(project_id=project_id)

    # Determine whether Jira agents are needed.
    # Jira creation only requires Confluence to be published and creds
    # to be configured — the PRD content / idea title can substitute
    # for a missing executive summary.
    jira_needed = (
        not item["jira_done"]
        and item["confluence_done"]
        and _has_jira_credentials()
    )
    pm_agent = create_jira_product_manager_agent(project_id=project_id) if jira_needed else None
    atl_agent = create_jira_architect_tech_lead_agent(project_id=project_id) if jira_needed else None

    # ── Summarise partially-created Jira tickets ────────────────
    existing_tickets = item.get("jira_tickets") or []
    existing_epic_key = ""
    existing_story_keys: list[str] = []
    existing_task_keys: list[str] = []
    for t in existing_tickets:
        if t.get("type") == "Epic":
            existing_epic_key = t.get("key", "")
        elif t.get("type") == "Story":
            existing_story_keys.append(t.get("key", ""))
        elif t.get("type") == "Task":
            existing_task_keys.append(t.get("key", ""))

    existing_tickets_note = ""
    if existing_tickets:
        lines = [f"  - {t.get('key')} ({t.get('type')})" for t in existing_tickets]
        existing_tickets_note = (
            "\n\n## Existing Jira tickets (from previous partial run)\n"
            "The following tickets were already created. "
            "Do NOT create duplicates — reuse existing keys.\n"
            + "\n".join(lines)
        )

    # ── Task 1: Assess what needs delivery ─────────────────────
    assess_task = Task(
        description=(
            f"Assess the delivery status for PRD run_id={run_id}.\n\n"
            f"## Current state\n"
            f"- Confluence published: {'Yes' if item['confluence_done'] else 'No'}\n"
            f"- Jira tickets created: {'Yes' if item['jira_done'] else 'No'}\n"
            f"- PRD title: {page_title}\n"
            f"{existing_tickets_note}\n\n"
            f"## Instructions\n"
            f"Summarise what delivery steps remain and confirm you will "
            f"coordinate them. Do NOT ask the user — act autonomously."
        ),
        expected_output=(
            "A brief summary of which delivery steps (Confluence / Jira) "
            "are pending for this PRD, confirming autonomous execution."
        ),
        agent=delivery_manager,
    )

    tasks: list[Task] = [assess_task]

    # ── Task 2: Confluence publish (if needed) ─────────────────
    if not item["confluence_done"]:
        confluence_task = Task(
            description=task_configs["publish_to_confluence_task"]["description"].format(
                prd_content=item["content"],
                page_title=page_title,
                run_id=run_id,
            ),
            expected_output=task_configs["publish_to_confluence_task"]["expected_output"],
            agent=orchestrator_agent,
            context=[assess_task],
        )
        tasks.append(confluence_task)
    else:
        confluence_task = None

    # ── Task 3: Jira ticketing (if needed) ─────────────────────
    # Jira tasks are only added when Confluence is already published
    # AND the Jira environment (JIRA_PROJECT_KEY etc.) is available.
    # If Confluence is still pending in this crew run, Jira will be
    # deferred to the next startup cycle after the publish is verified.
    if jira_needed:
        confluence_url = item.get("confluence_url", "")

        # If an Epic already exists from a partial run, inform the agent
        # and skip Epic creation by providing the existing key directly.
        epic_extra = ""
        if existing_epic_key:
            epic_extra = (
                f"\n\n## IMPORTANT — Existing Epic\n"
                f"An Epic ({existing_epic_key}) was already created for "
                f"this run_id in a previous attempt.  The jira_create_issue "
                f"tool will automatically reuse it (dedup by run_id label). "
                f"Proceed to call the tool as normal — it will return the "
                f"existing Epic key."
            )

        # Use finalized_idea when available; fall back to the idea
        # title so Jira Epic creation is never blocked by a missing
        # executive summary.
        exec_summary = (
            item["finalized_idea"]
            or item.get("idea", "")
            or "PRD"
        )

        epic_task = Task(
            description=task_configs["create_jira_epic_task"]["description"].format(
                page_title=page_title,
                executive_summary=exec_summary,
                run_id=run_id,
                confluence_url=confluence_url,
            ) + epic_extra,
            expected_output=task_configs["create_jira_epic_task"]["expected_output"],
            agent=pm_agent,
            context=[confluence_task or assess_task],
        )
        tasks.append(epic_task)

        # Use func_reqs from the workingIdeas section data when
        # available; fall back to the full PRD content so the agent
        # can still infer requirements from the Confluence page.
        effective_func_reqs = item["func_reqs"] or item.get("content", "")

        # Enrich Jira tickets with extra PRD sections (non-functional
        # requirements, edge cases, error handling, etc.)
        additional_ctx = build_additional_prd_context_from_doc(item.get("doc") or {})

        if effective_func_reqs:
            stories_extra = ""
            if existing_story_keys:
                stories_extra = (
                    f"\n\n## IMPORTANT — Existing Stories\n"
                    f"Stories already created in a previous attempt: "
                    f"{', '.join(existing_story_keys)}.  The tool "
                    f"will automatically reuse them via dedup by "
                    f"run_id label + summary match.  Proceed normally."
                )

            stories_task = Task(
                description=task_configs["create_jira_stories_task"]["description"].format(
                    functional_requirements=effective_func_reqs,
                    additional_prd_context=additional_ctx,
                    epic_key=existing_epic_key or "{epic_key from previous task}",
                    run_id=run_id,
                    confluence_url=confluence_url,
                ) + stories_extra,
                expected_output=task_configs["create_jira_stories_task"]["expected_output"],
                agent=pm_agent,
                context=[epic_task],
            )
            tasks.append(stories_task)

            tasks_extra = ""
            if existing_task_keys:
                tasks_extra = (
                    f"\n\n## IMPORTANT — Existing Tasks\n"
                    f"Tasks already created in a previous attempt: "
                    f"{', '.join(existing_task_keys)}.  The tool "
                    f"will automatically reuse them via dedup by "
                    f"run_id label + summary match.  Proceed normally."
                )

            tasks_task = Task(
                description=task_configs["create_jira_tasks_task"]["description"].format(
                    stories_output="{stories output from previous task}",
                    functional_requirements=effective_func_reqs,
                    additional_prd_context=additional_ctx,
                    confluence_url=confluence_url,
                    run_id=run_id,
                ) + tasks_extra,
                expected_output=task_configs["create_jira_tasks_task"]["expected_output"],
                agent=atl_agent,
                context=[stories_task],
            )
            tasks.append(tasks_task)

    # ── Build step-callback for progress messages ──────────────
    cb = progress_callback or _print_delivery_status
    task_index = {"n": 0}

    def _step_callback(output):
        task_index["n"] += 1
        step = task_index["n"]
        total = len(tasks)
        raw = getattr(output, "raw", str(output))
        # Emit a concise progress line
        preview = raw[:120].replace("\n", " ").strip()
        if preview:
            cb(f"[{step}/{total}] {preview}")

    # ── Assemble Crew ──────────────────────────────────────────
    agents = [delivery_manager, orchestrator_agent]
    if pm_agent is not None:
        agents.append(pm_agent)
    if atl_agent is not None:
        agents.append(atl_agent)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=is_verbose(),
        step_callback=_step_callback,
    )

    return crew
