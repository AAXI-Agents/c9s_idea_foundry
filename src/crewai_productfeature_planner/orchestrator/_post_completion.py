"""Post-completion CrewAI Crew factory.

Builds a multi-agent Crew for Atlassian delivery (Confluence + Jira)
after a PRD has been finalized within a :class:`PRDFlow` session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    _print_delivery_status,
    build_additional_prd_context_from_draft,
    logger,
)

if TYPE_CHECKING:
    from crewai import Crew

    from crewai_productfeature_planner.flows.prd_flow import PRDFlow


def build_post_completion_crew(
    flow: "PRDFlow",
    *,
    progress_callback: "Callable[[str], None] | None" = None,
) -> "Crew | None":
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
    3. **Jira Skeleton** — PM agent generates Epics/Stories outline.
    4. **Jira Epic** — PM agent creates Epic (if applicable).
    5. **Jira Stories** — PM agent creates categorised Stories
       (Data Persistence, Data Layer, Data Presentation,
       App & Data Security) under the Epic with dependencies.
    6. **Jira Tasks** — Architect/TL agent creates granular sub-tasks
       under each Story with docs, test cases, and dependencies.

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
        create_jira_architect_tech_lead_agent,
        create_jira_product_manager_agent,
        create_orchestrator_agent,
        get_task_configs,
    )
    from crewai_productfeature_planner.scripts.logging_config import is_verbose

    idea_preview = (flow.state.idea or "PRD")[:80].strip()
    page_title = f"PRD — {idea_preview}"
    task_configs = get_task_configs()

    # ── Set project-level Jira key override (if configured) ────
    from crewai_productfeature_planner.mongodb.project_config import (
        get_project_for_run,
    )
    from crewai_productfeature_planner.tools.jira_tool import set_jira_project_key

    pc = get_project_for_run(flow.state.run_id) or {}
    ctx_key = pc.get("jira_project_key", "")
    if ctx_key:
        set_jira_project_key(ctx_key)
        logger.info(
            "[PostCompletion] Using project-level JIRA_PROJECT_KEY=%s",
            ctx_key,
        )

    # Determine what needs delivery
    confluence_done = bool(getattr(flow.state, "confluence_url", ""))
    jira_done = bool(getattr(flow.state, "jira_output", ""))
    has_confluence = _has_confluence_credentials() and _has_gemini_credentials()
    has_jira = _has_jira_credentials() and _has_gemini_credentials()

    confluence_needed = has_confluence and not confluence_done and flow.state.final_prd

    # Jira requires Confluence to be published first.  When Confluence
    # is already done we can proceed; when it is needed in *this* crew
    # run the Jira tasks will still be added, but a post-run guard in
    # _run_post_completion / _run_startup_delivery ensures they only
    # execute after a verified publish.
    jira_needed = (
        has_jira
        and not jira_done
        and flow.state.final_prd
        and (confluence_done or confluence_needed)
    )

    if not confluence_needed and not jira_needed:
        return None

    # Resolve project_id for memory enrichment
    from crewai_productfeature_planner.scripts.memory_loader import (
        resolve_project_id,
    )
    project_id = resolve_project_id(flow.state.run_id)

    delivery_manager = create_delivery_manager_agent(project_id=project_id)
    orchestrator_agent = create_orchestrator_agent(project_id=project_id)
    pm_agent = create_jira_product_manager_agent(project_id=project_id) if jira_needed else None
    atl_agent = create_jira_architect_tech_lead_agent(project_id=project_id) if jira_needed else None

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

    # ── Task 3: Jira Skeleton (titles only) ──────────────────
    if jira_needed:
        exec_summary = flow.state.finalized_idea or flow.state.idea
        confluence_url = getattr(flow.state, "confluence_url", "")

        func_req_section = flow.state.draft.get_section("functional_requirements")
        func_reqs = func_req_section.content if func_req_section else ""
        additional_ctx = build_additional_prd_context_from_draft(flow.state.draft)

        idea_preview = (flow.state.idea or "PRD")[:80].strip()
        skeleton_page_title = f"PRD — {idea_preview}"

        skeleton_task = Task(
            description=task_configs["generate_jira_skeleton_task"]["description"].format(
                page_title=skeleton_page_title,
                executive_summary=exec_summary,
                functional_requirements=func_reqs,
                additional_prd_context=additional_ctx,
            ),
            expected_output=task_configs["generate_jira_skeleton_task"]["expected_output"],
            agent=pm_agent,
            context=[confluence_task or assess_task],
        )
        tasks.append(skeleton_task)

        # ── Task 4: Jira Epic ──────────────────────────────────
        epic_task = Task(
            description=task_configs["create_jira_epic_task"]["description"].format(
                page_title=skeleton_page_title,
                executive_summary=exec_summary,
                run_id=flow.state.run_id,
                confluence_url=confluence_url,
            ),
            expected_output=task_configs["create_jira_epic_task"]["expected_output"],
            agent=pm_agent,
            context=[skeleton_task],
        )
        tasks.append(epic_task)

        # ── Task 5: Jira Stories (categorised) ─────────────────
        if func_reqs:
            stories_task = Task(
                description=task_configs["create_jira_stories_task"]["description"].format(
                    approved_skeleton="{skeleton output from skeleton task}",
                    functional_requirements=func_reqs,
                    additional_prd_context=additional_ctx,
                    epic_key="{epic_key from previous task}",
                    run_id=flow.state.run_id,
                    confluence_url=confluence_url,
                ),
                expected_output=task_configs["create_jira_stories_task"]["expected_output"],
                agent=pm_agent,
                context=[epic_task],
            )
            tasks.append(stories_task)

            # ── Task 6: Jira Tasks (sub-tasks under Stories) ───
            tasks_task = Task(
                description=task_configs["create_jira_tasks_task"]["description"].format(
                    stories_output="{stories output from previous task}",
                    functional_requirements=func_reqs,
                    additional_prd_context=additional_ctx,
                    confluence_url=confluence_url,
                    run_id=flow.state.run_id,
                ),
                expected_output=task_configs["create_jira_tasks_task"]["expected_output"],
                agent=atl_agent,
                context=[stories_task],
            )
            tasks.append(tasks_task)

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

    agents = [delivery_manager, orchestrator_agent]
    if pm_agent is not None:
        agents.append(pm_agent)
    if atl_agent is not None:
        agents.append(atl_agent)

    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=is_verbose(),
        step_callback=_step_callback,
    )
