"""Stage factory functions for the agent pipeline.

Each ``build_*_stage(flow)`` function creates an :class:`AgentStage`
whose callables close over the given *flow* instance so they can
read/write ``flow.state`` and ``flow.<callback>`` attributes.

To extend the pipeline with a new agent, add a new factory here and
register it inside :func:`build_default_pipeline`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    AgentStage,
    StageResult,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


# ── helpers ───────────────────────────────────────────────────────────


def _has_gemini_credentials() -> bool:
    """Return True when at least one Gemini auth mechanism is configured."""
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )


def _has_confluence_credentials() -> bool:
    """Return True when all required Confluence env vars are set."""
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials as _check,
    )
    return _check()


def _has_jira_credentials() -> bool:
    """Return True when all required Jira env vars are set."""
    from crewai_productfeature_planner.tools.jira_tool import (
        _has_jira_credentials as _check,
    )
    return _check()


# ── Stage 1 — Idea Refinement ────────────────────────────────────────


def build_idea_refinement_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that refines the raw idea.

    The stage wraps :func:`refine_idea` from the ``idea_refiner``
    agent and maps its output onto ``flow.state``.
    """

    def _should_skip() -> bool:
        if flow.state.idea_refined:
            logger.info("[IdeaRefiner] Skipping — idea already refined")
            return True
        if not _has_gemini_credentials():
            logger.info(
                "[IdeaRefiner] Skipping — no GOOGLE_API_KEY "
                "or GOOGLE_CLOUD_PROJECT set"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.agents.idea_refiner import (
            refine_idea,
        )

        logger.info("[IdeaRefiner] Refining idea before PRD generation")
        # Snapshot original idea *before* refinement
        flow.state.original_idea = flow.state.idea
        refined, history = refine_idea(
            flow.state.idea, run_id=flow.state.run_id,
        )
        logger.info(
            "[IdeaRefiner] Idea refined (%d → %d chars, %d iterations)",
            len(flow.state.original_idea), len(refined), len(history),
        )
        return StageResult(output=refined, history=history)

    def _apply(result: StageResult) -> None:
        flow.state.idea = result.output
        flow.state.idea_refined = True
        flow.state.refinement_history = result.history

    def _requires_approval() -> bool:
        # Skip the idea approval gate when requirements breakdown is
        # configured (will run next OR has already completed).
        # The user will approve at the requirements stage instead.
        if _has_gemini_credentials():
            logger.info(
                "[IdeaRefiner] Auto-approving — requirements breakdown "
                "%s",
                "already done" if flow.state.requirements_broken_down
                else "will run next",
            )
            return False
        return (
            flow.state.idea_refined
            and flow.idea_approval_callback is not None
        )

    def _get_approval() -> bool:
        return flow.idea_approval_callback(
            flow.state.idea,
            flow.state.original_idea,
            flow.state.run_id,
            flow.state.refinement_history,
        )

    from crewai_productfeature_planner.flows.prd_flow import IdeaFinalized

    return AgentStage(
        name="idea_refinement",
        description="Iteratively refine raw idea via industry-expert feedback",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
        get_approval=_get_approval,
        finalized_exc=IdeaFinalized,
        requires_approval=_requires_approval,
    )


# ── Stage 2 — Requirements Breakdown ─────────────────────────────────


def build_requirements_breakdown_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that decomposes the idea into
    structured product requirements.

    The stage wraps :func:`breakdown_requirements` from the
    ``requirements_breakdown`` agent.
    """

    def _should_skip() -> bool:
        if flow.state.requirements_broken_down:
            logger.info(
                "[RequirementsBreakdown] Skipping — already broken down"
            )
            return True
        if not _has_gemini_credentials():
            logger.info(
                "[RequirementsBreakdown] Skipping — no GOOGLE_API_KEY "
                "or GOOGLE_CLOUD_PROJECT set"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.agents.requirements_breakdown import (
            breakdown_requirements,
        )

        logger.info(
            "[RequirementsBreakdown] Breaking down idea into requirements"
        )
        requirements, history = breakdown_requirements(
            flow.state.idea, run_id=flow.state.run_id,
        )
        logger.info(
            "[RequirementsBreakdown] Breakdown complete "
            "(%d chars, %d iterations)",
            len(requirements), len(history),
        )
        return StageResult(output=requirements, history=history)

    def _apply(result: StageResult) -> None:
        flow.state.requirements_breakdown = result.output
        flow.state.breakdown_history = result.history
        flow.state.requirements_broken_down = True

    def _requires_approval() -> bool:
        # On resume: if executive summary iterations or section content
        # already exist, the user previously approved requirements —
        # skip the gate so they aren't re-prompted.
        if flow.state.executive_summary.iterations:
            logger.info(
                "[RequirementsBreakdown] Auto-approving — executive "
                "summary already has %d iteration(s) (resumed run)",
                len(flow.state.executive_summary.iterations),
            )
            return False
        if any(s.content for s in flow.state.draft.sections):
            logger.info(
                "[RequirementsBreakdown] Auto-approving — sections "
                "already in progress (resumed run)",
            )
            return False
        return (
            flow.state.requirements_broken_down
            and flow.requirements_approval_callback is not None
        )

    def _get_approval() -> bool:
        return flow.requirements_approval_callback(
            flow.state.requirements_breakdown,
            flow.state.idea,
            flow.state.run_id,
            flow.state.breakdown_history,
        )

    from crewai_productfeature_planner.flows.prd_flow import RequirementsFinalized

    return AgentStage(
        name="requirements_breakdown",
        description="Decompose refined idea into detailed product requirements",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
        get_approval=_get_approval,
        finalized_exc=RequirementsFinalized,
        requires_approval=_requires_approval,
    )


# ── Stage 3 — Confluence Publish ─────────────────────────────────────


def build_confluence_publish_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that publishes the completed PRD
    to Atlassian Confluence.

    The stage is skipped when Confluence credentials are not configured
    or when the PRD has already been published for this run.
    """

    def _should_skip() -> bool:
        if not _has_confluence_credentials():
            logger.info(
                "[ConfluencePublish] Skipping — Confluence credentials "
                "not configured"
            )
            return True
        if not _has_gemini_credentials():
            logger.info(
                "[ConfluencePublish] Skipping — no Gemini credentials "
                "for orchestrator agent"
            )
            return True
        if getattr(flow.state, "confluence_url", ""):
            logger.info(
                "[ConfluencePublish] Skipping — already published: %s",
                flow.state.confluence_url,
            )
            return True
        if not flow.state.final_prd:
            logger.info(
                "[ConfluencePublish] Skipping — no final PRD to publish"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.tools.confluence_tool import (
            publish_to_confluence,
        )

        idea_preview = (flow.state.idea or "PRD")[:80].strip()
        title = f"PRD — {idea_preview}"

        logger.info(
            "[ConfluencePublish] Publishing PRD to Confluence: '%s'",
            title,
        )
        result = publish_to_confluence(
            title=title,
            markdown_content=flow.state.final_prd,
            run_id=flow.state.run_id,
        )
        return StageResult(
            output=f"{result['action']}|{result['page_id']}|{result['url']}",
        )

    def _apply(result: StageResult) -> None:
        from crewai_productfeature_planner.mongodb import save_confluence_url

        parts = result.output.split("|", 2)
        page_id = parts[1] if len(parts) > 1 else ""
        page_url = parts[2] if len(parts) > 2 else result.output

        flow.state.confluence_url = page_url
        save_confluence_url(
            run_id=flow.state.run_id,
            confluence_url=page_url,
            page_id=page_id,
        )

    return AgentStage(
        name="confluence_publish",
        description="Publish completed PRD to Atlassian Confluence",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# ── Stage 4 — Jira Ticket Creation ───────────────────────────────────


def build_jira_ticketing_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that creates Jira tickets for the
    completed PRD — an Epic plus Stories for functional requirements.

    Skipped when Jira credentials are not configured.
    """

    def _should_skip() -> bool:
        if not _has_jira_credentials():
            logger.info(
                "[JiraTicketing] Skipping — Jira credentials not configured"
            )
            return True
        if not _has_gemini_credentials():
            logger.info(
                "[JiraTicketing] Skipping — no Gemini credentials "
                "for orchestrator agent"
            )
            return True
        if not flow.state.final_prd:
            logger.info(
                "[JiraTicketing] Skipping — no final PRD available"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.orchestrator.agent import (
            create_orchestrator_agent,
            get_task_configs,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )

        agent = create_orchestrator_agent()
        task_configs = get_task_configs()

        idea_preview = (flow.state.idea or "PRD")[:80].strip()
        page_title = f"PRD — {idea_preview}"

        # ── Create Epic ───────────────────────────────────────
        exec_summary = flow.state.finalized_idea or flow.state.idea
        epic_task = Task(
            description=task_configs["create_jira_epic_task"]["description"].format(
                page_title=page_title,
                executive_summary=exec_summary,
                run_id=flow.state.run_id,
            ),
            expected_output=task_configs["create_jira_epic_task"]["expected_output"],
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[epic_task],
            process=Process.sequential,
            verbose=is_verbose(),
        )
        epic_result = crew_kickoff_with_retry(
            crew, step_label="jira_create_epic",
        )

        # ── Create Stories from functional requirements ───────
        func_req_section = flow.state.draft.get_section("functional_requirements")
        func_reqs = func_req_section.content if func_req_section else ""

        if func_reqs:
            # Extract epic key from result (best effort)
            epic_key = ""
            for word in epic_result.raw.split():
                if "-" in word and word.replace("-", "").replace("_", "").isalnum():
                    epic_key = word.strip(".,;:()")
                    break

            stories_task = Task(
                description=task_configs["create_jira_tickets_task"]["description"].format(
                    functional_requirements=func_reqs,
                    epic_key=epic_key,
                    run_id=flow.state.run_id,
                ),
                expected_output=task_configs["create_jira_tickets_task"]["expected_output"],
                agent=agent,
            )
            crew = Crew(
                agents=[agent],
                tasks=[stories_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            stories_result = crew_kickoff_with_retry(
                crew, step_label="jira_create_stories",
            )
            output = f"Epic: {epic_result.raw}\nStories: {stories_result.raw}"
        else:
            output = f"Epic: {epic_result.raw}\n(No functional requirements for stories)"

        return StageResult(output=output)

    def _apply(result: StageResult) -> None:
        flow.state.jira_output = result.output
        logger.info(
            "[JiraTicketing] Jira tickets created (%d chars output)",
            len(result.output),
        )

    return AgentStage(
        name="jira_ticketing",
        description="Create Jira Epic and Story tickets from PRD requirements",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# ── Pipeline assembly ────────────────────────────────────────────────


def build_default_pipeline(flow: "PRDFlow") -> AgentOrchestrator:
    """Assemble the default agent pipeline for PRD generation.

    Current chain::

        1. Idea Refinement   — auto-iterates until idea is polished
        2. Requirements Breakdown — decomposes idea into product requirements

    To extend, create a new ``build_*_stage`` factory and register it
    here at the desired position.

    Args:
        flow: The :class:`PRDFlow` instance whose state will be read
              and updated by each stage.

    Returns:
        A fully-configured :class:`AgentOrchestrator` ready for
        :meth:`~AgentOrchestrator.run_pipeline`.
    """
    orchestrator = AgentOrchestrator()
    orchestrator.register(build_idea_refinement_stage(flow))
    orchestrator.register(build_requirements_breakdown_stage(flow))
    return orchestrator


def build_post_completion_pipeline(flow: "PRDFlow") -> AgentOrchestrator:
    """Assemble the post-completion pipeline for Atlassian publishing.

    Runs **after** the PRD has been finalized.  Publishes the PRD to
    Confluence and creates Jira tickets from its requirements.

    Current chain::

        1. Confluence Publish  — push PRD to Confluence space
        2. Jira Ticketing      — create Epic + Stories from requirements

    Args:
        flow: The :class:`PRDFlow` instance with a finalized PRD.

    Returns:
        A fully-configured :class:`AgentOrchestrator` ready for
        :meth:`~AgentOrchestrator.run_pipeline`.
    """
    orchestrator = AgentOrchestrator()
    orchestrator.register(build_confluence_publish_stage(flow))
    orchestrator.register(build_jira_ticketing_stage(flow))
    return orchestrator


def build_post_completion_crew(
    flow: "PRDFlow",
    *,
    progress_callback: "Callable[[str], None] | None" = None,
) -> "Crew":
    """Build a multi-agent CrewAI Crew for post-PRD Atlassian delivery.

    Replaces the old :class:`AgentOrchestrator` pipeline with a proper
    CrewAI Crew using **Process.sequential** and agent collaboration.

    The Crew comprises two agents:

    * **Delivery Manager** — coordinator, ``allow_delegation=True``,
      assesses what needs to be delivered and delegates tool-bearing
      work.
    * **Orchestrator** — specialist with Confluence and Jira tools,
      ``allow_delegation=False``.

    Tasks are chained via ``context`` so each task receives the output
    of its predecessors:

    1. **Assess** — Delivery Manager summarises pending steps.
    2. **Confluence publish** — Orchestrator publishes PRD (if needed).
    3. **Jira Epic** — Orchestrator creates Epic (if applicable).
    4. **Jira Stories** — Orchestrator creates Stories (if func reqs).

    Args:
        flow:  The :class:`PRDFlow` instance with a finalized PRD.
        progress_callback:  Optional callable invoked with status
               messages as each task completes.

    Returns:
        A configured :class:`Crew` instance ready for ``kickoff()``,
        or ``None`` when no delivery steps are needed.
    """
    from crewai import Crew, Process, Task

    from crewai_productfeature_planner.agents.orchestrator.agent import (
        create_delivery_manager_agent,
        create_orchestrator_agent,
        get_task_configs,
    )
    from crewai_productfeature_planner.scripts.logging_config import is_verbose

    idea_preview = (flow.state.idea or "PRD")[:80].strip()
    page_title = f"PRD — {idea_preview}"
    task_configs = get_task_configs()

    # Determine what needs delivery
    confluence_done = bool(getattr(flow.state, "confluence_url", ""))
    jira_done = bool(getattr(flow.state, "jira_output", ""))
    has_confluence = _has_confluence_credentials() and _has_gemini_credentials()
    has_jira = _has_jira_credentials() and _has_gemini_credentials()

    confluence_needed = has_confluence and not confluence_done and flow.state.final_prd
    jira_needed = has_jira and not jira_done and flow.state.final_prd

    if not confluence_needed and not jira_needed:
        return None

    delivery_manager = create_delivery_manager_agent()
    orchestrator_agent = create_orchestrator_agent()

    # ── Task 1: Assess delivery status ─────────────────────────
    assess_task = Task(
        description=(
            f"Assess the delivery status for finalized PRD.\n\n"
            f"## Current state\n"
            f"- Confluence published: {'Yes' if confluence_done else 'No'}\n"
            f"- Jira tickets created: {'Yes' if jira_done else 'No'}\n"
            f"- PRD title: {page_title}\n\n"
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

    # ── Task 2: Confluence publish ─────────────────────────────
    if confluence_needed:
        confluence_task = Task(
            description=task_configs["publish_to_confluence_task"]["description"].format(
                prd_content=flow.state.final_prd,
                page_title=page_title,
                run_id=flow.state.run_id,
            ),
            expected_output=task_configs["publish_to_confluence_task"]["expected_output"],
            agent=orchestrator_agent,
            context=[assess_task],
        )
        tasks.append(confluence_task)
    else:
        confluence_task = None

    # ── Task 3: Jira Epic ──────────────────────────────────────
    if jira_needed:
        exec_summary = flow.state.finalized_idea or flow.state.idea
        epic_task = Task(
            description=task_configs["create_jira_epic_task"]["description"].format(
                page_title=page_title,
                executive_summary=exec_summary,
                run_id=flow.state.run_id,
            ),
            expected_output=task_configs["create_jira_epic_task"]["expected_output"],
            agent=orchestrator_agent,
            context=[confluence_task or assess_task],
        )
        tasks.append(epic_task)

        # ── Task 4: Jira Stories ───────────────────────────────
        func_req_section = flow.state.draft.get_section("functional_requirements")
        func_reqs = func_req_section.content if func_req_section else ""
        if func_reqs:
            stories_task = Task(
                description=task_configs["create_jira_tickets_task"]["description"].format(
                    functional_requirements=func_reqs,
                    epic_key="{epic_key from previous task}",
                    run_id=flow.state.run_id,
                ),
                expected_output=task_configs["create_jira_tickets_task"]["expected_output"],
                agent=orchestrator_agent,
                context=[epic_task],
            )
            tasks.append(stories_task)

    # ── Step callback for progress ─────────────────────────────
    cb = progress_callback or _print_delivery_status
    task_index = {"n": 0}

    def _step_callback(output):
        task_index["n"] += 1
        step = task_index["n"]
        total = len(tasks)
        raw = getattr(output, "raw", str(output))
        preview = raw[:120].replace("\n", " ").strip()
        if preview:
            cb(f"[{step}/{total}] {preview}")

    return Crew(
        agents=[delivery_manager, orchestrator_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=is_verbose(),
        step_callback=_step_callback,
    )


# ── Startup delivery crew ────────────────────────────────────────────

DeliveryItem = dict  # type alias for readability


def _discover_pending_deliveries() -> list[DeliveryItem]:
    """Scan MongoDB for completed PRDs that still need delivery.

    Returns a list of dicts, each containing the ``run_id``, assembled
    ``content``, ``idea``, delivery flags, and the raw workingIdeas
    document for downstream use.
    """
    from crewai_productfeature_planner.main import (
        _assemble_prd_from_doc,
        get_db,
    )
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

    items: list[DeliveryItem] = []
    for doc in completed_docs:
        run_id = doc.get("run_id", "")
        if not run_id:
            continue

        record = get_delivery_record(run_id)
        if record and record.get("status") == "completed":
            continue

        confluence_done = bool(
            record and record.get("confluence_published")
        ) or bool(doc.get("confluence_url"))
        jira_done = bool(record and record.get("jira_completed"))

        if confluence_done and jira_done:
            # Mark as completed and skip
            from crewai_productfeature_planner.mongodb.product_requirements import (
                upsert_delivery_record,
            )
            upsert_delivery_record(
                run_id,
                confluence_published=True,
                confluence_url=doc.get("confluence_url", ""),
                jira_completed=True,
            )
            continue

        content = _assemble_prd_from_doc(doc)
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

        items.append({
            "run_id": run_id,
            "idea": doc.get("idea", "PRD"),
            "content": content,
            "confluence_done": confluence_done,
            "confluence_url": doc.get("confluence_url", ""),
            "jira_done": jira_done,
            "finalized_idea": finalized_idea,
            "func_reqs": func_reqs,
            "doc": doc,
        })

    return items


def _print_delivery_status(message: str) -> None:
    """Print a delivery status line to the CLI with an orchestrator prefix."""
    print(f"  \033[36m[Orchestrator]\033[0m {message}")


def build_startup_delivery_crew(
    item: DeliveryItem,
    *,
    progress_callback: "Callable[[str], None] | None" = None,
) -> "Crew":
    """Build a CrewAI Crew for delivering a single pending PRD.

    Uses a **sequential process** with collaboration between two agents:

    * **Delivery Manager** — coordinates the delivery lifecycle,
      decides which steps are needed, and delegates tool-bearing
      work to the Orchestrator.
    * **Orchestrator** — executes Confluence publishing and Jira
      ticket creation using its tool suite.

    The Crew runs three chained tasks (via ``context``):

    1. **Assess delivery status** — Delivery Manager analyses what is
       pending for this run_id.
    2. **Publish to Confluence** — Orchestrator publishes the PRD
       (skipped if already published).
    3. **Create Jira tickets** — Orchestrator creates Epic + Stories
       (skipped if already done or no functional requirements).

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
        create_orchestrator_agent,
        get_task_configs,
    )
    from crewai_productfeature_planner.scripts.logging_config import is_verbose

    run_id = item["run_id"]
    idea_preview = (item["idea"] or "PRD")[:80].strip()
    page_title = f"PRD — {idea_preview}"
    task_configs = get_task_configs()

    delivery_manager = create_delivery_manager_agent()
    orchestrator_agent = create_orchestrator_agent()

    # ── Task 1: Assess what needs delivery ─────────────────────
    assess_task = Task(
        description=(
            f"Assess the delivery status for PRD run_id={run_id}.\n\n"
            f"## Current state\n"
            f"- Confluence published: {'Yes' if item['confluence_done'] else 'No'}\n"
            f"- Jira tickets created: {'Yes' if item['jira_done'] else 'No'}\n"
            f"- PRD title: {page_title}\n\n"
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
    if not item["jira_done"] and item["finalized_idea"]:
        epic_task = Task(
            description=task_configs["create_jira_epic_task"]["description"].format(
                page_title=page_title,
                executive_summary=item["finalized_idea"],
                run_id=run_id,
            ),
            expected_output=task_configs["create_jira_epic_task"]["expected_output"],
            agent=orchestrator_agent,
            context=[confluence_task or assess_task],
        )
        tasks.append(epic_task)

        if item["func_reqs"]:
            stories_task = Task(
                description=task_configs["create_jira_tickets_task"]["description"].format(
                    functional_requirements=item["func_reqs"],
                    epic_key="{epic_key from previous task}",
                    run_id=run_id,
                ),
                expected_output=task_configs["create_jira_tickets_task"]["expected_output"],
                agent=orchestrator_agent,
                context=[epic_task],
            )
            tasks.append(stories_task)

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
    crew = Crew(
        agents=[delivery_manager, orchestrator_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=is_verbose(),
        step_callback=_step_callback,
    )

    return crew
