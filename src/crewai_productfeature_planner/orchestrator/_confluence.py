"""Confluence Publish stage factory.

Wraps the ``publish_to_confluence`` tool in an :class:`AgentStage`
that pushes the finalized PRD to Atlassian Confluence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_confluence_credentials,
    _has_gemini_credentials,
    logger,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentStage,
    StageResult,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow


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
        from crewai_productfeature_planner.mongodb.project_config import (
            get_project_for_run,
        )
        from crewai_productfeature_planner.tools.confluence_tool import (
            confluence_project_context,
            publish_to_confluence,
        )

        idea_preview = (flow.state.idea or "PRD")[:80].strip()
        title = f"PRD — {idea_preview}"

        # Resolve project-level keys (falls back to env vars if unset)
        pc = get_project_for_run(flow.state.run_id) or {}
        ctx_space = pc.get("confluence_space_key", "")
        ctx_parent = pc.get("confluence_parent_id", "")

        logger.info(
            "[ConfluencePublish] Publishing PRD to Confluence: '%s'"
            " (project space_key=%s)",
            title,
            ctx_space or "<env>",
        )
        with confluence_project_context(
            space_key=ctx_space, parent_id=ctx_parent,
        ):
            result = publish_to_confluence(
                title=title,
                markdown_content=flow.state.final_prd,
                run_id=flow.state.run_id,
            )
        return StageResult(
            output=f"{result['action']}|{result['page_id']}|{result['url']}",
        )

    def _apply(result: StageResult) -> None:
        from crewai_productfeature_planner.mongodb.product_requirements import (
            upsert_delivery_record,
        )

        parts = result.output.split("|", 2)
        page_id = parts[1] if len(parts) > 1 else ""
        page_url = parts[2] if len(parts) > 2 else result.output

        flow.state.confluence_url = page_url
        upsert_delivery_record(
            run_id=flow.state.run_id,
            confluence_published=True,
            confluence_url=page_url,
            confluence_page_id=page_id,
        )

    return AgentStage(
        name="confluence_publish",
        description="Publish completed PRD to Atlassian Confluence",
        run=_run,
        should_skip=_should_skip,
        apply=_apply,
    )
