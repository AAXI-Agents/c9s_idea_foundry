"""Agentic Team auto-trigger stage — kicks off the implementation pipeline
after all Jira tickets have been created.

Runs as the final stage of the post-completion pipeline (after Jira ticketing).
Gated by the ``AGENTIC_TEAM_ENABLED`` feature flag.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from crewai_productfeature_planner.apis.agentic_team._config import (
    AGENTIC_TEAM_ENABLED,
)
from crewai_productfeature_planner.apis.agentic_team._service import (
    batch_kickoff_pipeline,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.mongodb.product_requirements.repository import (
    get_jira_tickets,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentStage,
    StageResult,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)


def build_agentic_team_trigger_stage(flow: "PRDFlow") -> AgentStage:
    """Build a stage that triggers the Agentic Team batch pipeline.

    After Jira tickets are created, this stage:
    1. Fetches all created sub-task keys from MongoDB
    2. Builds the batch payload with issue keys, summaries, and labels
    3. Calls POST /pipeline/batch-kickoff on the Agentic Team service

    Skips silently when:
    - AGENTIC_TEAM_ENABLED is False
    - No Jira tickets have been created
    - Jira phase is not at a completion state
    """

    def _should_skip() -> bool:
        if not AGENTIC_TEAM_ENABLED:
            logger.debug("[AgenticTeamTrigger] Skipping — feature flag disabled")
            return True

        # Only trigger after Jira is fully complete
        done_phases = ("qa_test_done", "kanban_tasks_done")
        if flow.state.jira_phase not in done_phases:
            logger.debug(
                "[AgenticTeamTrigger] Skipping — jira_phase=%s (not done)",
                flow.state.jira_phase,
            )
            return True

        return False

    def _run() -> StageResult:
        run_id = flow.state.run_id

        # Fetch all created tickets
        tickets = get_jira_tickets(run_id)
        if not tickets:
            logger.info(
                "[AgenticTeamTrigger] No Jira tickets found for run_id=%s",
                run_id,
            )
            return StageResult(output="No tickets to trigger pipeline for.")

        # Filter to actionable ticket types (Sub-tasks and Stories)
        actionable_types = {"Sub-task", "Story", "Task"}
        actionable = [
            t for t in tickets
            if t.get("type") in actionable_types and not t.get("reused")
        ]

        if not actionable:
            logger.info(
                "[AgenticTeamTrigger] No actionable tickets (Sub-tasks/Stories) "
                "for run_id=%s (%d total tickets)",
                run_id, len(tickets),
            )
            return StageResult(output="No actionable tickets for pipeline.")

        # Resolve idea_id for labeling
        idea_id = _resolve_idea_id(run_id)

        # Build epic_key → feature_id mapping from idea's features
        epic_to_feature = _build_epic_feature_map(idea_id)

        # Build batch payload
        tasks = []
        for ticket in actionable:
            issue_key = ticket.get("key", "")
            summary = ticket.get("summary", "")
            labels = [f"run:{run_id}"]
            if idea_id:
                labels.append(f"idea:{idea_id}")

            # Resolve feature_id via ticket's parent epic key
            parent_key = ticket.get("parent_key", "")
            feature_id = epic_to_feature.get(parent_key) if parent_key else None
            if not feature_id and issue_key:
                # Ticket itself might be an epic mapped to a feature
                feature_id = epic_to_feature.get(issue_key)
            if feature_id:
                labels.append(f"feature:{feature_id}")

            tasks.append({
                "issue_key": issue_key,
                "task_input": summary,
                "topic": summary[:80] if summary else issue_key,
                "labels": labels,
            })

        logger.info(
            "[AgenticTeamTrigger] Triggering batch pipeline: run_id=%s, "
            "%d tasks, idea_id=%s",
            run_id, len(tasks), idea_id,
        )

        # Call the async service function from sync context
        result = asyncio.run(batch_kickoff_pipeline(tasks))

        if result:
            accepted = result.get("accepted", 0)
            skipped = result.get("skipped", 0)
            errors = result.get("errors", 0)
            msg = (
                f"Agentic Team pipeline triggered: "
                f"{accepted} accepted, {skipped} skipped, {errors} errors"
            )
            logger.info("[AgenticTeamTrigger] %s", msg)
            return StageResult(output=msg)

        logger.warning(
            "[AgenticTeamTrigger] Batch kickoff returned None for run_id=%s",
            run_id,
        )
        return StageResult(
            output="Agentic Team pipeline trigger attempted but got no response.",
        )

    def _apply(result: StageResult) -> None:
        logger.debug(
            "[AgenticTeamTrigger] Stage complete: %s",
            result.output[:100] if result.output else "(empty)",
        )

    return AgentStage(
        name="agentic_team_trigger",
        description="Trigger Agentic Team batch pipeline for implementation",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )


def _resolve_idea_id(run_id: str) -> str | None:
    """Resolve the idea_id for the given run_id from MongoDB."""
    try:
        doc = get_db()["workingIdeas"].find_one(
            {"run_id": run_id},
            {"_id": 1},
        )
        if doc and doc.get("_id"):
            return str(doc["_id"])
    except Exception:  # noqa: BLE001
        logger.debug(
            "[AgenticTeamTrigger] Failed to resolve idea_id for run_id=%s",
            run_id, exc_info=True,
        )
    return None


def _build_epic_feature_map(idea_id: str | None) -> dict[str, str]:
    """Build a mapping of Jira epic_key → feature_id from the idea's features.

    Returns an empty dict if the idea is not found or has no features
    with jira_epic_key set.
    """
    if not idea_id:
        return {}
    try:
        from crewai_productfeature_planner.mongodb.ideas.repository import get_idea

        idea = get_idea(idea_id=idea_id)
        if not idea:
            return {}
        features = idea.get("features") or []
        mapping: dict[str, str] = {}
        for feat in features:
            epic_key = feat.get("jira_epic_key")
            feat_id = feat.get("id")
            if epic_key and feat_id:
                mapping[epic_key] = feat_id
        if mapping:
            logger.debug(
                "[AgenticTeamTrigger] Epic→feature map: %d entries for idea=%s",
                len(mapping), idea_id,
            )
        return mapping
    except Exception:  # noqa: BLE001
        logger.debug(
            "[AgenticTeamTrigger] Failed to build epic→feature map for idea=%s",
            idea_id, exc_info=True,
        )
        return {}
