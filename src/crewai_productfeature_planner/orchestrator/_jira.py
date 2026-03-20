"""Jira Ticketing stage factories — phased ticket creation.

Phase 1 — **Skeleton**: Generate a skeleton outline of Epics and User
          Stories (titles only) for user approval.
Phase 2 — **Epics & Stories**: Create the approved Epics with inter-Epic
          dependencies and User Stories categorised as Data Persistence,
          Data Layer, Data Presentation, and App & Data Security.
          Pauses for user review after creation.
Phase 3 — **Sub-tasks**: Create detailed sub-tasks under each Story
          with dependencies, documentation, test cases, and unit tests.
Phase 4 — **Review Sub-tasks**: Staff Engineer and QA Lead create review
          sub-tasks for each User Story to audit production readiness
          and test methodology coverage.
Phase 5 — **QA Test Sub-tasks**: QA Engineer creates counter-tickets to
          each implementation sub-task for edge case, security, and
          rendering/behaviour testing.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_gemini_credentials,
    _has_jira_credentials,
    build_additional_prd_context_from_draft,
    logger,
    make_page_title,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentStage,
    StageResult,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow


def _build_jira_context(flow: "PRDFlow") -> str:
    """Build the ``{additional_prd_context}`` string for Jira tasks.

    Combines the standard additional PRD sections with the Engineering
    Plan and UX Design (if available) so Jira ticket generation benefits
    from the Eng Manager's architectural analysis and the UX Designer's
    Figma prototypes.
    """
    base = build_additional_prd_context_from_draft(flow.state.draft)
    blocks: list[str] = []

    eng_plan = getattr(flow.state, "engineering_plan", "")
    if eng_plan and eng_plan.strip():
        blocks.append(
            "## Engineering Plan\n\n"
            "Use this engineering plan as the primary technical "
            "reference for structuring Epics, Stories, and Sub-tasks:\n\n"
            f"{eng_plan.strip()}"
        )

    # Include UX design context (Figma URL and/or prompt) so Jira tickets
    # reference the visual design and align implementation with the UI spec.
    figma_url = getattr(flow.state, "figma_design_url", "")
    figma_prompt = getattr(flow.state, "figma_design_prompt", "")
    if figma_url or figma_prompt:
        ux_parts = ["## UX Design\n"]
        if figma_url:
            ux_parts.append(
                f"Figma prototype: {figma_url}\n"
                "Reference this Figma design for all UI implementation. "
                "Each Story and Sub-task MUST link to the relevant Figma "
                "frame or component when describing the UI.\n"
            )
        if figma_prompt:
            # Truncate long prompts to avoid bloating the Jira context.
            prompt_preview = figma_prompt[:3000]
            ux_parts.append(
                "UX Design specification (use for UI implementation details):\n\n"
                f"{prompt_preview}"
            )
        blocks.append("\n".join(ux_parts))

    if blocks:
        combined = "\n\n".join(blocks)
        return f"{combined}\n\n{base}" if base else combined
    return base


def _persist_jira_phase(run_id: str, phase: str) -> None:
    """Persist Jira phase to MongoDB so the scheduler can gate on it."""
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_jira_phase,
        )
        save_jira_phase(run_id, phase)
    except Exception:  # noqa: BLE001
        logger.debug(
            "Failed to persist jira_phase=%s for run_id=%s",
            phase, run_id, exc_info=True,
        )


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


def build_jira_skeleton_stage(
    flow: "PRDFlow", *, require_confluence: bool = True,
) -> AgentStage:
    """Create an :class:`AgentStage` that generates a skeleton outline
    of Epics and User Stories (titles only) without creating any Jira
    tickets.  The skeleton is stored in ``flow.state.jira_skeleton``
    for user approval.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(
            flow, require_confluence=require_confluence,
        )
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
            pm_agent = create_jira_product_manager_agent(project_id=project_id, run_id=flow.state.run_id)

            page_title = make_page_title(flow.state.idea)
            exec_summary = (
                flow.state.executive_product_summary
                or flow.state.finalized_idea
                or flow.state.idea
            )

            func_req_section = flow.state.draft.get_section("functional_requirements")
            func_reqs = func_req_section.content if func_req_section else ""
            additional_ctx = _build_jira_context(flow)

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
        _persist_jira_phase(flow.state.run_id, "skeleton_pending")
        # Persist skeleton to MongoDB so it survives process restarts
        # and can be shown again when the user resumes approval.
        try:
            from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                save_jira_skeleton,
            )
            save_jira_skeleton(flow.state.run_id, result.output)
        except Exception:  # noqa: BLE001
            logger.debug(
                "Failed to persist jira_skeleton for run_id=%s",
                flow.state.run_id, exc_info=True,
            )
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


def build_jira_epics_stories_stage(
    flow: "PRDFlow", *, require_confluence: bool = True,
) -> AgentStage:
    """Create an :class:`AgentStage` that creates Jira Epics with
    inter-Epic dependencies, and User Stories categorised into Data
    Persistence, Data Layer, Data Presentation, and App & Data Security.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(
            flow, require_confluence=require_confluence,
        )
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
            pm_agent = create_jira_product_manager_agent(project_id=project_id, run_id=flow.state.run_id)

            page_title = make_page_title(flow.state.idea)
            exec_summary = (
                flow.state.executive_product_summary
                or flow.state.finalized_idea
                or flow.state.idea
            )
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
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[JiraEpicsStories] Failed to persist Epic %s: %s",
                        epic_key, exc,
                    )

            # ── Create Stories ────────────────────────────────
            func_req_section = flow.state.draft.get_section("functional_requirements")
            func_reqs = func_req_section.content if func_req_section else ""
            additional_ctx = _build_jira_context(flow)

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
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[JiraEpicsStories] Failed to persist Stories: %s",
                        exc,
                    )

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
        _persist_jira_phase(flow.state.run_id, "epics_stories_done")
        try:
            from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                save_jira_epics_stories_output,
            )
            save_jira_epics_stories_output(flow.state.run_id, result.output)
        except Exception:  # noqa: BLE001
            logger.warning(
                "[JiraEpicsStories] Failed to persist epics_stories_output "
                "for run_id=%s",
                flow.state.run_id,
            )
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


def build_jira_subtasks_stage(
    flow: "PRDFlow", *, require_confluence: bool = True,
) -> AgentStage:
    """Create an :class:`AgentStage` that creates detailed sub-tasks
    under each Story with documentation, test cases, unit tests, and
    dependency links.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(
            flow, require_confluence=require_confluence,
        )
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
            atl_agent = create_jira_architect_tech_lead_agent(project_id=project_id, run_id=flow.state.run_id)
            confluence_url = getattr(flow.state, "confluence_url", "")

            func_req_section = flow.state.draft.get_section("functional_requirements")
            func_reqs = func_req_section.content if func_req_section else ""
            additional_ctx = _build_jira_context(flow)

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
                            "type": "Sub-task",
                        })
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[JiraSubtasks] Failed to persist Sub-tasks: %s",
                    exc,
                )

            return StageResult(output=tasks_result.raw)
        finally:
            _reset_jira_context(jira_token)

    def _apply(result: StageResult) -> None:
        flow.state.jira_output = (
            f"{flow.state.jira_epics_stories_output}\n"
            f"Sub-Tasks: {result.output}"
        )
        flow.state.jira_phase = "subtasks_done"
        _persist_jira_phase(flow.state.run_id, "subtasks_done")
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
# Phase 4 — Review Sub-tasks (Staff Engineer + QA Lead)
# =====================================================================


def build_jira_review_subtasks_stage(
    flow: "PRDFlow", *, require_confluence: bool = True,
) -> AgentStage:
    """Create an :class:`AgentStage` that generates review sub-tasks
    for each User Story — one from the Paranoid Staff Engineer and one
    from the QA Lead.

    These review tickets ensure development work matches the Jira ticket
    specifications and that test methodology is adequate.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(
            flow, require_confluence=require_confluence,
        )
        if reason:
            logger.info("[JiraReviewSubtasks] Skipping — %s", reason)
            return True
        if flow.state.jira_phase not in ("review_ready", "subtasks_done"):
            logger.info(
                "[JiraReviewSubtasks] Skipping — phase is '%s', "
                "need 'review_ready'",
                flow.state.jira_phase,
            )
            return True
        if not flow.state.jira_output and not flow.state.jira_epics_stories_output:
            logger.info("[JiraReviewSubtasks] Skipping — no Stories/Sub-tasks output")
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.staff_engineer import (
            create_staff_engineer,
            get_task_configs as get_staff_eng_task_configs,
        )
        from crewai_productfeature_planner.agents.qa_lead import (
            create_qa_lead,
            get_task_configs as get_qa_lead_task_configs,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.memory_loader import (
            resolve_project_id,
        )
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )

        jira_token, project_id, _ = _setup_jira_context(flow)

        try:
            confluence_url = getattr(flow.state, "confluence_url", "")
            additional_ctx = _build_jira_context(flow)
            eng_plan = getattr(flow.state, "engineering_plan", "")

            # Combined stories + subtasks output for reviewers to audit
            stories_and_subtasks = flow.state.jira_output or (
                f"{flow.state.jira_epics_stories_output}"
            )

            outputs = []

            # ── Staff Engineer review sub-tasks ──────────────────
            try:
                staff_agent = create_staff_engineer(
                    project_id=project_id, run_id=flow.state.run_id,
                )
                staff_task_configs = get_staff_eng_task_configs()
                task_cfg = staff_task_configs[
                    "create_staff_engineer_review_subtasks_task"
                ]
                staff_task = Task(
                    description=task_cfg["description"].format(
                        stories_and_subtasks=stories_and_subtasks,
                        engineering_plan=eng_plan or "(Not available)",
                        additional_prd_context=additional_ctx,
                        confluence_url=confluence_url,
                        run_id=flow.state.run_id,
                    ),
                    expected_output=task_cfg["expected_output"],
                    agent=staff_agent,
                )
                crew = Crew(
                    agents=[staff_agent],
                    tasks=[staff_task],
                    process=Process.sequential,
                    verbose=is_verbose(),
                )
                staff_result = crew_kickoff_with_retry(
                    crew, step_label="jira_staff_eng_review",
                )
                outputs.append(f"Staff Engineer Reviews:\n{staff_result.raw}")

                try:
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        append_jira_ticket,
                    )
                    known = set(_extract_issue_keys(stories_and_subtasks))
                    for rkey in _extract_issue_keys(staff_result.raw):
                        if rkey not in known:
                            append_jira_ticket(flow.state.run_id, {
                                "key": rkey,
                                "type": "Sub-task",
                                "category": "staff-review",
                            })
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[JiraReviewSubtasks] Failed to persist staff-eng review tickets: %s",
                        exc,
                    )

                logger.info(
                    "[JiraReviewSubtasks] Staff Engineer review sub-tasks created (%d chars)",
                    len(staff_result.raw),
                )
            except EnvironmentError:
                logger.warning(
                    "[JiraReviewSubtasks] Skipping Staff Engineer — no Gemini credentials",
                )
                outputs.append("Staff Engineer Reviews: skipped (no credentials)")

            # ── QA Lead review sub-tasks ─────────────────────────
            try:
                qa_lead_agent = create_qa_lead(
                    project_id=project_id, run_id=flow.state.run_id,
                )
                qa_lead_task_configs = get_qa_lead_task_configs()
                task_cfg = qa_lead_task_configs[
                    "create_qa_lead_review_subtasks_task"
                ]
                qa_lead_task = Task(
                    description=task_cfg["description"].format(
                        stories_and_subtasks=stories_and_subtasks,
                        engineering_plan=eng_plan or "(Not available)",
                        additional_prd_context=additional_ctx,
                        confluence_url=confluence_url,
                        run_id=flow.state.run_id,
                    ),
                    expected_output=task_cfg["expected_output"],
                    agent=qa_lead_agent,
                )
                crew = Crew(
                    agents=[qa_lead_agent],
                    tasks=[qa_lead_task],
                    process=Process.sequential,
                    verbose=is_verbose(),
                )
                qa_lead_result = crew_kickoff_with_retry(
                    crew, step_label="jira_qa_lead_review",
                )
                outputs.append(f"QA Lead Reviews:\n{qa_lead_result.raw}")

                try:
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        append_jira_ticket,
                    )
                    known = set(_extract_issue_keys(stories_and_subtasks))
                    for rkey in _extract_issue_keys(qa_lead_result.raw):
                        if rkey not in known:
                            append_jira_ticket(flow.state.run_id, {
                                "key": rkey,
                                "type": "Sub-task",
                                "category": "qa-lead-review",
                            })
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[JiraReviewSubtasks] Failed to persist QA Lead review tickets: %s",
                        exc,
                    )

                logger.info(
                    "[JiraReviewSubtasks] QA Lead review sub-tasks created (%d chars)",
                    len(qa_lead_result.raw),
                )
            except EnvironmentError:
                logger.warning(
                    "[JiraReviewSubtasks] Skipping QA Lead — no Gemini credentials",
                )
                outputs.append("QA Lead Reviews: skipped (no credentials)")

            return StageResult(output="\n\n".join(outputs))
        finally:
            _reset_jira_context(jira_token)

    def _apply(result: StageResult) -> None:
        flow.state.jira_review_output = result.output
        flow.state.jira_phase = "review_done"
        _persist_jira_phase(flow.state.run_id, "review_done")
        logger.info(
            "[JiraReviewSubtasks] Review sub-tasks created (%d chars) — "
            "paused for review before QA test sub-tasks",
            len(result.output),
        )

    return AgentStage(
        name="jira_review_subtasks",
        description="Create Staff Engineer and QA Lead review sub-tasks for each User Story",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# =====================================================================
# Phase 5 — QA Test Sub-tasks (QA Engineer)
# =====================================================================


def build_jira_qa_test_subtasks_stage(
    flow: "PRDFlow", *, require_confluence: bool = True,
) -> AgentStage:
    """Create an :class:`AgentStage` that generates QA test sub-tasks
    as counter-tickets to each implementation sub-task.

    The QA Engineer creates test cases focused on edge cases, security
    vulnerabilities, and rendering issues — complementing (not
    duplicating) the unit tests already defined in dev sub-tasks.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(
            flow, require_confluence=require_confluence,
        )
        if reason:
            logger.info("[JiraQATestSubtasks] Skipping — %s", reason)
            return True
        if flow.state.jira_phase != "qa_test_ready":
            logger.info(
                "[JiraQATestSubtasks] Skipping — phase is '%s', "
                "need 'qa_test_ready'",
                flow.state.jira_phase,
            )
            return True
        if not flow.state.jira_output and not flow.state.jira_epics_stories_output:
            logger.info("[JiraQATestSubtasks] Skipping — no Stories/Sub-tasks output")
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.qa_engineer import (
            create_qa_engineer,
            get_task_configs as get_qa_eng_task_configs,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )

        jira_token, project_id, _ = _setup_jira_context(flow)

        try:
            confluence_url = getattr(flow.state, "confluence_url", "")
            additional_ctx = _build_jira_context(flow)
            eng_plan = getattr(flow.state, "engineering_plan", "")

            stories_and_subtasks = flow.state.jira_output or (
                f"{flow.state.jira_epics_stories_output}"
            )

            qa_agent = create_qa_engineer(
                project_id=project_id, run_id=flow.state.run_id,
            )
            qa_task_configs = get_qa_eng_task_configs()
            task_cfg = qa_task_configs["create_qa_engineer_test_subtasks_task"]

            qa_task = Task(
                description=task_cfg["description"].format(
                    stories_and_subtasks=stories_and_subtasks,
                    engineering_plan=eng_plan or "(Not available)",
                    additional_prd_context=additional_ctx,
                    confluence_url=confluence_url,
                    run_id=flow.state.run_id,
                ),
                expected_output=task_cfg["expected_output"],
                agent=qa_agent,
            )
            crew = Crew(
                agents=[qa_agent],
                tasks=[qa_task],
                process=Process.sequential,
                verbose=is_verbose(),
            )
            qa_result = crew_kickoff_with_retry(
                crew, step_label="jira_qa_engineer_tests",
            )

            try:
                from crewai_productfeature_planner.mongodb.product_requirements import (
                    append_jira_ticket,
                )
                known = set(_extract_issue_keys(stories_and_subtasks))
                for tkey in _extract_issue_keys(qa_result.raw):
                    if tkey not in known:
                        append_jira_ticket(flow.state.run_id, {
                            "key": tkey,
                            "type": "Sub-task",
                            "category": "qa-test",
                        })
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[JiraQATestSubtasks] Failed to persist QA test tickets: %s",
                    exc,
                )

            return StageResult(output=qa_result.raw)
        finally:
            _reset_jira_context(jira_token)

    def _apply(result: StageResult) -> None:
        flow.state.jira_qa_test_output = result.output
        flow.state.jira_phase = "qa_test_done"
        _persist_jira_phase(flow.state.run_id, "qa_test_done")
        logger.info(
            "[JiraQATestSubtasks] QA test sub-tasks created (%d chars) — complete",
            len(result.output),
        )

    return AgentStage(
        name="jira_qa_test_subtasks",
        description="Create QA Engineer test sub-tasks as counter-tickets to implementation sub-tasks",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


# =====================================================================
# Legacy — run all Jira phases sequentially (auto-approve mode)
# =====================================================================


def build_jira_ticketing_stage(flow: "PRDFlow") -> AgentStage:
    """Backward-compatible stage that runs all five Jira phases
    sequentially in auto-approve mode (no user approval gates).

    This is used by :func:`build_post_completion_pipeline` and startup
    delivery flows where interactive approval is not available.
    """

    def _should_skip() -> bool:
        reason = _check_jira_prerequisites(flow)
        if reason:
            logger.info("[JiraTicketing] Skipping — %s", reason)
            return True
        if flow.state.jira_phase == "qa_test_done":
            logger.info("[JiraTicketing] Skipping — already completed")
            return True
        return False

    def _run() -> StageResult:
        from crewai_productfeature_planner.orchestrator.orchestrator import (
            AgentOrchestrator,
        )

        # Build a mini pipeline of all five phases, auto-approving
        # between each so the next phase proceeds.
        skeleton = build_jira_skeleton_stage(flow)
        epics_stories = build_jira_epics_stories_stage(flow)
        subtasks = build_jira_subtasks_stage(flow)
        reviews = build_jira_review_subtasks_stage(flow)
        qa_tests = build_jira_qa_test_subtasks_stage(flow)

        mini = AgentOrchestrator(
            stages=[skeleton, epics_stories, subtasks, reviews, qa_tests],
        )

        # After skeleton runs, auto-approve so Phase 2 proceeds.
        orig_skeleton_apply = skeleton.apply

        def _auto_approve_apply(result: StageResult) -> None:
            orig_skeleton_apply(result)
            # Move past "skeleton_pending" so Phase 2 runs
            flow.state.jira_phase = "skeleton_approved"
            _persist_jira_phase(flow.state.run_id, "skeleton_approved")

        skeleton.apply = _auto_approve_apply

        # After Phase 2 runs, auto-approve so Phase 3 proceeds.
        orig_es_apply = epics_stories.apply

        def _auto_approve_subtasks(result: StageResult) -> None:
            orig_es_apply(result)
            flow.state.jira_phase = "subtasks_ready"
            _persist_jira_phase(flow.state.run_id, "subtasks_ready")

        epics_stories.apply = _auto_approve_subtasks

        # After Phase 3 runs, auto-approve so Phase 4 proceeds.
        orig_st_apply = subtasks.apply

        def _auto_approve_reviews(result: StageResult) -> None:
            orig_st_apply(result)
            flow.state.jira_phase = "review_ready"
            _persist_jira_phase(flow.state.run_id, "review_ready")

        subtasks.apply = _auto_approve_reviews

        # After Phase 4 runs, auto-approve so Phase 5 proceeds.
        orig_rv_apply = reviews.apply

        def _auto_approve_qa_tests(result: StageResult) -> None:
            orig_rv_apply(result)
            flow.state.jira_phase = "qa_test_ready"
            _persist_jira_phase(flow.state.run_id, "qa_test_ready")

        reviews.apply = _auto_approve_qa_tests

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
