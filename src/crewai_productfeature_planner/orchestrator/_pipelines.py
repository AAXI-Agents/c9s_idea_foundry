"""Pipeline assembly functions.

Combines individual stage factories into ordered
:class:`AgentOrchestrator` pipelines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai_productfeature_planner.orchestrator._confluence import (
    build_confluence_publish_stage,
)
from crewai_productfeature_planner.orchestrator._idea_refinement import (
    build_idea_refinement_stage,
)
from crewai_productfeature_planner.orchestrator._jira import (
    build_jira_ticketing_stage,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
)

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow


def build_default_pipeline(flow: "PRDFlow") -> AgentOrchestrator:
    """Assemble the default agent pipeline for PRD generation.

    Current chain::

        1. Idea Refinement   — auto-iterates until idea is polished

    Requirements Breakdown is **not** included here — it runs after
    Phase 1 (Executive Summary) inside ``generate_sections()`` so the
    user can review the executive summary before the (potentially
    expensive) requirements agent starts.

    When the flow has a ``progress_callback``, stage lifecycle events
    (``pipeline_stage_start``, ``pipeline_stage_complete``, etc.) are
    forwarded to it so callers (e.g. Slack) can post heartbeat messages.

    Args:
        flow: The :class:`PRDFlow` instance whose state will be read
              and updated by each stage.

    Returns:
        A fully-configured :class:`AgentOrchestrator` ready for
        :meth:`~AgentOrchestrator.run_pipeline`.
    """
    progress_cb = getattr(flow, "progress_callback", None)
    # Also check the callback registry in case CrewAI lost the attribute
    if progress_cb is None:
        progress_cb = flow._resolve_callback("progress_callback")
    orchestrator = AgentOrchestrator(progress_callback=progress_cb)
    orchestrator.register(build_idea_refinement_stage(flow))
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
