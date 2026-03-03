"""Jira Ticketing stage factories — phased ticket creation.

Phase 1 — **Skeleton**: Generate a skeleton outline of Epics and User
          Stories (titles only) for user approval.
Phase 2 — **Epics & Stories**: Create the approved Epics with inter-Epic
          dependencies and User Stories categorised as Data Persistence,
          Data Layer, Data Presentation, and App & Data Security.
          Pauses for user review after creation.
Phase 3 — **Sub-tasks**: Create detailed sub-tasks under each Story
          with dependencies, documentation, test cases, and unit tests.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_gemini_credentials,
    _has_jira_credentials,
    build_additional_prd_context_from_draft,
    logger,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentStage,
    StageResult,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow


def _extract_issue_keys(text: str) -> list[str]:
    """Extract Jira issue keys (e.g. ``PRD-42``) from *text*."""
    return re.findall(r"[A-Z]{2,10}-\d+", text)


# ── Common precondition checks ───────────────────────────────────────


def _check_jira_prerequisites(
    flow: "PRDFlow", *, require_confluence: bool = True,
) -> str | None:
    """Return a skip-reason string if Jira prerequisites are not met.

    Returns ``None`` when all conditions are satisfied.
    """
    if not _has_jira_credentials():
        return "Jira credentials not configured"
    if not _has_gemini_credentials():
        return "no Gemini credentials for orchestrator agent"
    if not flow.state.final_prd:
        return "no final PRD available"
    if require_confluence and not getattr(flow.state, "confluence_url", ""):
        return "Confluence URL not set (publish must succeed first)"
    return None


def _setup_jira_context(flow: "PRDFlow"):
    """Resolve project-level Jira key and return context tuple.

    Returns ``(jira_token, project_id, task_configs)``.
    """
    from crewai_productfeature_planner.agents.orchestrator.agent import (
        get_task_configs,
    )
    from crewai_productfeature_planner.mongodb.project_config import (
        get_project_for_run,
    )
    from crewai_productfeature_planner.scripts.memory_loader import (
        resolve_project_id,
    )
    from crewai_productfeature_planner.tools.jira_tool import (
        set_jira_project_key,
    )

    pc = get_project_for_run(flow.state.run_id) or {}
    ctx_key = pc.get("jira_project_key", "")
    jira_token: object = None
    if ctx_key:
        jira_token = set_jira_project_key(ctx_key)
        logger.info(
            "[JiraTicketing] Using project-level JIRA_PROJECT_KEY=%s",
            ctx_key,
        )

    project_id = resolve_project_id(flow.state.run_id)
    task_configs = get_task_configs()
    return jira_token, project_id, task_configs


def _reset_jira_context(jira_token: object) -> None:
    """Reset the project-level Jira key override if it was set."""
    if jira_token is not None:
        from crewai_productfeature_planner.tools.jira_tool import (
            _project_key_ctx,
        )
        _project_key_ctx.reset(jira_token)


# =====================================================================
# Phase 1 — Skeleton generation (no tickets created)
# =====================================================================


def build_jira_skeleton_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that generates a skeleton outline
    of Epics and User Stories (titles only) without creating any Jira
    tickets.  The skeleton is stored in ``flow.state.jira_skeleton``
    for user approval.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(flow)
        if reason:
            logger.info("[JiraSkeleton] Skipping — %s", reason)
            return True
        if flow.state.jira_skeleton:
            logger.info("[JiraSkeleton] Skipping — skeleton already generated")
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.orchestrator.agent import (
            create_jira_product_manager_agent,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )

        jira_token, project_id, task_configs = _setup_jira_context(flow)

        try:
            pm_agent = create_jira_product_manager_agent(project_id=project_id)

            idea_preview = (flow.state.idea or "PRD")[:80].strip()
            page_title = f"PRD — {idea_preview}"
            exec_summary = flow.state.finalized_idea or flow.state.idea

            func_req_section = flow.state.draft.get_section("functional_requirements")
            func_reqs = func_req_section.content if func_req_section else ""
            additional_ctx = build_additional_prd_context_from_draft(flow.state.draft)

            skeleton_task = Task(
                description=task_configs["generate_jira_skeleton_task"]["description"].format(
                    page_title=page_title,
                    executive_summary=exec_summary,
                    functional_requirements=func_reqs,
                    additional_prd_context=additional_ctx,
                ),
                expected_output=task_configs["generate_jira_skeleton_task"]["expected_output"],
                agent=pm_agent,
            )
            crew = Crew(
                agents=[pm_agent],
                tasks=[skeleton_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            result = crew_kickoff_with_retry(
                crew, step_label="jira_generate_skeleton",
            )
            return StageResult(output=result.raw)
        finally:
            _reset_jira_context(jira_token)

    def _apply(result: StageResult) -> None:
        flow.state.jira_skeleton = result.output
        flow.state.jira_phase = "skeleton_pending"
        logger.info(
            "[JiraSkeleton] Skeleton generated (%d chars) — awaiting approval",
            len(result.output),
        )

    return AgentStage(
        name="jira_skeleton",
        description="Generate a skeleton outline of Jira Epics and User Stories (titles only) for user approval",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# =====================================================================
# Phase 2 — Create Epics and Stories (with user-approved skeleton)
# =====================================================================


def build_jira_epics_stories_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that creates Jira Epics with
    inter-Epic dependencies, and User Stories categorised into Data
    Persistence, Data Layer, Data Presentation, and App & Data Security.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(flow)
        if reason:
            logger.info("[JiraEpicsStories] Skipping — %s", reason)
            return True
        if not flow.state.jira_skeleton:
            logger.info("[JiraEpicsStories] Skipping — no approved skeleton")
            return True
        if flow.state.jira_phase == "skeleton_pending":
            logger.info("[JiraEpicsStories] Skipping — skeleton not yet approved")
            return True
        if flow.state.jira_phase in ("epics_stories_done", "subtasks_done"):
            logger.info("[JiraEpicsStories] Skipping — already created")
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.orchestrator.agent import (
            create_jira_product_manager_agent,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )

        jira_token, project_id, task_configs = _setup_jira_context(flow)

        try:
            pm_agent = create_jira_product_manager_agent(project_id=project_id)

            idea_preview = (flow.state.idea or "PRD")[:80].strip()
            page_title = f"PRD — {idea_preview}"
            exec_summary = flow.state.finalized_idea or flow.state.idea
            confluence_url = getattr(flow.state, "confluence_url", "")

            # ── Create Epic ───────────────────────────────────
            epic_task = Task(
                description=task_configs["create_jira_epic_task"]["description"].format(
                    page_title=page_title,
                    executive_summary=exec_summary,
                    run_id=flow.state.run_id,
                    confluence_url=confluence_url,
                ),
                expected_output=task_configs["create_jira_epic_task"]["expected_output"],
                agent=pm_agent,
            )
            crew = Crew(
                agents=[pm_agent],
                tasks=[epic_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            epic_result = crew_kickoff_with_retry(
                crew, step_label="jira_create_epic",
            )

            epic_key = ""
            for word in epic_result.raw.split():
                if "-" in word and word.replace("-", "").replace("_", "").isalnum():
                    epic_key = word.strip(".,;:()")
                    break

            if epic_key:
                try:
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        append_jira_ticket,
                    )
                    append_jira_ticket(flow.state.run_id, {
                        "key": epic_key,
                        "type": "Epic",
                        "summary": page_title,
                    })
                except Exception:  # noqa: BLE001
                    pass

            # ── Create Stories ────────────────────────────────
            func_req_section = flow.state.draft.get_section("functional_requirements")
            func_reqs = func_req_section.content if func_req_section else ""
            additional_ctx = build_additional_prd_context_from_draft(flow.state.draft)

            stories_output = ""
            if func_reqs and epic_key:
                stories_task = Task(
                    description=task_configs["create_jira_stories_task"]["description"].format(
                        approved_skeleton=flow.state.jira_skeleton,
                        functional_requirements=func_reqs,
                        additional_prd_context=additional_ctx,
                        epic_key=epic_key,
                        run_id=flow.state.run_id,
                        confluence_url=confluence_url,
                    ),
                    expected_output=task_configs["create_jira_stories_task"]["expected_output"],
                    agent=pm_agent,
                )
                crew = Crew(
                    agents=[pm_agent],
                    tasks=[stories_task],
                    process=Process.sequential,
                    verbose=is_verbose(),
                )
                stories_result = crew_kickoff_with_retry(
                    crew, step_label="jira_create_stories",
                )
                stories_output = stories_result.raw

                try:
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        append_jira_ticket,
                    )
                    for skey in _extract_issue_keys(stories_output):
                        if skey != epic_key:
                            append_jira_ticket(flow.state.run_id, {
                                "key": skey,
                                "type": "Story",
                            })
                except Exception:  # noqa: BLE001
                    pass

                output = (
                    f"Epic: {epic_result.raw}\n"
                    f"Stories: {stories_output}"
                )
            elif func_reqs:
                output = f"Epic: {epic_result.raw}\n(Epic key extraction failed)"
            else:
                output = f"Epic: {epic_result.raw}\n(No functional requirements)"

            return StageResult(output=output)
        finally:
            _reset_jira_context(jira_token)

    def _apply(result: StageResult) -> None:
        flow.state.jira_epics_stories_output = result.output
        flow.state.jira_phase = "epics_stories_done"
        logger.info(
            "[JiraEpicsStories] Epics and Stories created (%d chars) — "
            "paused for review before sub-task creation",
            len(result.output),
        )

    return AgentStage(
        name="jira_epics_stories",
        description="Create Jira Epics with dependencies and categorised User Stories",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# =====================================================================
# Phase 3 — Create Sub-tasks
# =====================================================================


def build_jira_subtasks_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that creates detailed sub-tasks
    under each Story with documentation, test cases, unit tests, and
    dependency links.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(flow)
        if reason:
            logger.info("[JiraSubtasks] Skipping — %s", reason)
            return True
        if flow.state.jira_phase != "subtasks_ready":
            logger.info(
                "[JiraSubtasks] Skipping — phase is '%s', need 'subtasks_ready'",
                flow.state.jira_phase,
            )
            return True
        if not flow.state.jira_epics_stories_output:
            logger.info("[JiraSubtasks] Skipping — no Epics/Stories output")
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.orchestrator.agent import (
            create_jira_architect_tech_lead_agent,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )

        jira_token, project_id, task_configs = _setup_jira_context(flow)

        try:
            atl_agent = create_jira_architect_tech_lead_agent(project_id=project_id)
            confluence_url = getattr(flow.state, "confluence_url", "")

            func_req_section = flow.state.draft.get_section("functional_requirements")
            func_reqs = func_req_section.content if func_req_section else ""
            additional_ctx = build_additional_prd_context_from_draft(flow.state.draft)

            tasks_task = Task(
                description=task_configs["create_jira_tasks_task"]["description"].format(
                    stories_output=flow.state.jira_epics_stories_output,
                    functional_requirements=func_reqs,
                    additional_prd_context=additional_ctx,
                    confluence_url=confluence_url,
                    run_id=flow.state.run_id,
                ),
                expected_output=task_configs["create_jira_tasks_task"]["expected_output"],
                agent=atl_agent,
            )
            crew = Crew(
                agents=[atl_agent],
                tasks=[tasks_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            tasks_result = crew_kickoff_with_retry(
                crew, step_label="jira_create_tasks",
            )

            try:
                from crewai_productfeature_planner.mongodb.product_requirements import (
                    append_jira_ticket,
                )
                known = set(_extract_issue_keys(flow.state.jira_epics_stories_output))
                for tkey in _extract_issue_keys(tasks_result.raw):
                    if tkey not in known:
                        append_jira_ticket(flow.state.run_id, {
                            "key": tkey,
                            "type": "Task",
                        })
            except Exception:  # noqa: BLE001
                pass

            return StageResult(output=tasks_result.raw)
        finally:
            _reset_jira_context(jira_token)

    def _apply(result: StageResult) -> None:
        flow.state.jira_output = (
            f"{flow.state.jira_epics_stories_output}\n"
            f"Sub-Tasks: {result.output}"
        )
        flow.state.jira_phase = "subtasks_done"
        logger.info(
            "[JiraSubtasks] Sub-tasks created (%d chars) — complete",
            len(result.output),
        )

    return AgentStage(
        name="jira_subtasks",
        description="Create detailed Jira sub-tasks with dependencies, documentation, test cases, and unit tests",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# =====================================================================
# Legacy — run all Jira phases sequentially (auto-approve mode)
# =====================================================================


def build_jira_ticketing_stage(flow: "PRDFlow") -> AgentStage:
    """Backward-compatible stage that runs all three Jira phases
    sequentially in auto-approve mode (no user approval gates).

    This is used by :func:`build_post_completion_pipeline` and startup
    delivery flows where interactive approval is not available.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(flow)
        if reason:
            logger.info("[JiraTicketing] Skipping — %s", reason)
            return True
        if flow.state.jira_phase == "subtasks_done":
            logger.info("[JiraTicketing] Skipping — already completed")
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.orchestrator.orchestrator import (
            AgentOrchestrator,
        )

        # Build a mini pipeline of the three phases, auto-approving
        # skeleton so Phase 2 doesn't skip.
        skeleton = build_jira_skeleton_stage(flow)
        epics_stories = build_jira_epics_stories_stage(flow)
        subtasks = build_jira_subtasks_stage(flow)

        mini = AgentOrchestrator(stages=[skeleton, epics_stories, subtasks])

        # After skeleton runs, auto-approve so Phase 2 proceeds.
        orig_skeleton_apply = skeleton.apply

        def _auto_approve_apply(result: StageResult) -> None:
            orig_skeleton_apply(result)
            # Move past "skeleton_pending" so Phase 2 runs
            flow.state.jira_phase = "skeleton_approved"

        skeleton.apply = _auto_approve_apply

        # After Phase 2 runs, auto-approve so Phase 3 proceeds.
        orig_es_apply = epics_stories.apply

        def _auto_approve_subtasks(result: StageResult) -> None:
            orig_es_apply(result)
            flow.state.jira_phase = "subtasks_ready"

        epics_stories.apply = _auto_approve_subtasks

        mini.run_pipeline()

        # Collect combined output
        combined = flow.state.jira_output or ""
        return StageResult(output=combined)

    def _apply(result: StageResult) -> None:
        # Phase sub-stages already applied their state changes;
        # just ensure jira_output is set.
        if result.output and not flow.state.jira_output:
            flow.state.jira_output = result.output

    return AgentStage(
        name="jira_ticketing",
        description=(
            "Create Jira tickets (skeleton → Epics/Stories → sub-tasks) "
            "in auto-approve mode"
        ),
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )
