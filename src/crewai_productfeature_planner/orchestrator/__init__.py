"""Agent Orchestrator — manages the ordered pipeline of agent stages.

The orchestrator runs each registered :class:`AgentStage` in sequence,
handling skip conditions, error recovery, and approval gates.

Typical usage inside ``prd_flow.py``::

    from crewai_productfeature_planner.orchestrator import build_default_pipeline

    orchestrator = build_default_pipeline(self)  # self = PRDFlow
    orchestrator.run_pipeline()
"""

from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    AgentStage,
    StageResult,
)
from crewai_productfeature_planner.orchestrator.stages import (
    build_confluence_publish_stage,
    build_default_pipeline,
    build_idea_refinement_stage,
    build_jira_epics_stories_stage,
    build_jira_skeleton_stage,
    build_jira_subtasks_stage,
    build_jira_ticketing_stage,
    build_post_completion_crew,
    build_post_completion_pipeline,
    build_requirements_breakdown_stage,
    build_startup_delivery_crew,
    _discover_pending_deliveries,
    _print_delivery_status,
)

__all__ = [
    "AgentOrchestrator",
    "AgentStage",
    "StageResult",
    "build_confluence_publish_stage",
    "build_default_pipeline",
    "build_idea_refinement_stage",
    "build_jira_epics_stories_stage",
    "build_jira_skeleton_stage",
    "build_jira_subtasks_stage",
    "build_jira_ticketing_stage",
    "build_post_completion_crew",
    "build_post_completion_pipeline",
    "build_requirements_breakdown_stage",
    "build_startup_delivery_crew",
    "_discover_pending_deliveries",
    "_print_delivery_status",
]
