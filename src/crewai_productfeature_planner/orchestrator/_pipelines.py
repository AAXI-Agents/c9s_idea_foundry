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
from crewai_productfeature_planner.orchestrator._requirements import (
    build_requirements_breakdown_stage,
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
