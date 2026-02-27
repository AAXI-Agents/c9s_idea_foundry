"""Jira Ticketing stage factory.

Creates Jira Epic, role-specific Stories, and granular Tasks from
the finalized PRD requirements.
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


def build_jira_ticketing_stage(flow: "PRDFlow") -> AgentStage:
    """Create an :class:`AgentStage` that creates Jira tickets for the
    completed PRD — an Epic, role-specific Stories (UX, Engineering, QE),
    and granular Tasks for each Story.

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
        if not getattr(flow.state, "confluence_url", ""):
            logger.info(
                "[JiraTicketing] Skipping — Confluence URL not set "
                "(publish must succeed first)"
            )
            return True
        return False

    def _run() -> StageResult:
        from crewai import Crew, Process, Task

        from crewai_productfeature_planner.agents.orchestrator.agent import (
            create_jira_architect_tech_lead_agent,
            create_jira_product_manager_agent,
            get_task_configs,
        )
        from crewai_productfeature_planner.mongodb.project_config import (
            get_project_for_run,
        )
        from crewai_productfeature_planner.scripts.logging_config import is_verbose
        from crewai_productfeature_planner.scripts.retry import (
            crew_kickoff_with_retry,
        )
        from crewai_productfeature_planner.tools.jira_tool import (
            set_jira_project_key,
        )

        # Resolve project-level Jira key (falls back to env var if unset)
        pc = get_project_for_run(flow.state.run_id) or {}
        ctx_key = pc.get("jira_project_key", "")
        jira_token: object = None
        if ctx_key:
            jira_token = set_jira_project_key(ctx_key)
            logger.info(
                "[JiraTicketing] Using project-level JIRA_PROJECT_KEY=%s",
                ctx_key,
            )

        pm_agent = create_jira_product_manager_agent()
        atl_agent = create_jira_architect_tech_lead_agent()
        task_configs = get_task_configs()

        idea_preview = (flow.state.idea or "PRD")[:80].strip()
        page_title = f"PRD — {idea_preview}"
        confluence_url = getattr(flow.state, "confluence_url", "")

        # ── Create Epic ───────────────────────────────────────
        exec_summary = flow.state.finalized_idea or flow.state.idea
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

        # ── Extract epic key from result (best effort) ────────
        epic_key = ""
        for word in epic_result.raw.split():
            if "-" in word and word.replace("-", "").replace("_", "").isalnum():
                epic_key = word.strip(".,;:()")
                break

        # ── Persist Epic ticket incrementally ─────────────────
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
                pass  # best-effort — don't fail the stage

        # ── Create role-specific Stories ──────────────────────
        func_req_section = flow.state.draft.get_section("functional_requirements")
        func_reqs = func_req_section.content if func_req_section else ""

        # Enrich Jira tickets with extra PRD sections (non-functional
        # requirements, edge cases, error handling, user personas, etc.)
        additional_ctx = build_additional_prd_context_from_draft(flow.state.draft)

        stories_output = ""
        if func_reqs and epic_key:
            stories_task = Task(
                description=task_configs["create_jira_stories_task"]["description"].format(
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

            # ── Persist Story tickets incrementally ───────────
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

            # ── Create Tasks under Stories ────────────────────
            tasks_task = Task(
                description=task_configs["create_jira_tasks_task"]["description"].format(
                    stories_output=stories_output,
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

            # ── Persist Task tickets incrementally ────────────
            try:
                from crewai_productfeature_planner.mongodb.product_requirements import (
                    append_jira_ticket,
                )
                known = {epic_key} | set(_extract_issue_keys(stories_output))
                for tkey in _extract_issue_keys(tasks_result.raw):
                    if tkey not in known:
                        append_jira_ticket(flow.state.run_id, {
                            "key": tkey,
                            "type": "Task",
                        })
            except Exception:  # noqa: BLE001
                pass

            output = (
                f"Epic: {epic_result.raw}\n"
                f"Stories: {stories_output}\n"
                f"Tasks: {tasks_result.raw}"
            )
        elif func_reqs:
            output = f"Epic: {epic_result.raw}\n(Epic key extraction failed — stories skipped)"
        else:
            output = f"Epic: {epic_result.raw}\n(No functional requirements for stories)"

        # Reset project-level Jira key override
        if jira_token is not None:
            from crewai_productfeature_planner.tools.jira_tool import (
                _project_key_ctx,
            )
            _project_key_ctx.reset(jira_token)

        return StageResult(output=output)

    def _apply(result: StageResult) -> None:
        flow.state.jira_output = result.output
        logger.info(
            "[JiraTicketing] Jira tickets created (%d chars output)",
            len(result.output),
        )

    return AgentStage(
        name="jira_ticketing",
        description="Create Jira Epic, role-specific Stories (UX/Architecture/Engineering/QE), and Tasks from PRD requirements",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )
