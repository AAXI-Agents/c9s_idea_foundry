"""Backward-compatible re-export facade.

The stage factories that used to live in this single monolithic file
have been split into focused sub-modules under the ``orchestrator``
package.  This file re-exports every public and semi-public name so
that existing ``from ...stages import X`` statements keep working.

Sub-modules
-----------
_helpers           Credential checks and CLI output utilities.
_idea_refinement   build_idea_refinement_stage
_requirements      build_requirements_breakdown_stage
_confluence        build_confluence_publish_stage
_jira              _extract_issue_keys, build_jira_ticketing_stage
_pipelines         build_default_pipeline, build_post_completion_pipeline
_post_completion   build_post_completion_crew
_startup_review    _discover_publishable_prds,
                   build_startup_markdown_review_stage,
                   build_startup_pipeline
_startup_delivery  DeliveryItem, _discover_pending_deliveries,
                   build_startup_delivery_crew
"""

from __future__ import annotations

# ---- helpers ----
from crewai_productfeature_planner.orchestrator._helpers import (  # noqa: F401
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    _print_delivery_status,
)

# ---- stage factories ----
from crewai_productfeature_planner.orchestrator._idea_refinement import (  # noqa: F401
    build_idea_refinement_stage,
)
from crewai_productfeature_planner.orchestrator._requirements import (  # noqa: F401
    build_requirements_breakdown_stage,
)
from crewai_productfeature_planner.orchestrator._confluence import (  # noqa: F401
    build_confluence_publish_stage,
)
from crewai_productfeature_planner.orchestrator._jira import (  # noqa: F401
    _extract_issue_keys,
    build_jira_epics_stories_stage,
    build_jira_skeleton_stage,
    build_jira_subtasks_stage,
    build_jira_ticketing_stage,
)

# ---- pipelines ----
from crewai_productfeature_planner.orchestrator._pipelines import (  # noqa: F401
    build_default_pipeline,
    build_post_completion_pipeline,
)

# ---- post-completion crew ----
from crewai_productfeature_planner.orchestrator._post_completion import (  # noqa: F401
    build_post_completion_crew,
)

# ---- startup review ----
from crewai_productfeature_planner.orchestrator._startup_review import (  # noqa: F401
    _discover_publishable_prds,
    build_startup_markdown_review_stage,
    build_startup_pipeline,
)

# ---- startup delivery ----
from crewai_productfeature_planner.orchestrator._startup_delivery import (  # noqa: F401
    DeliveryItem,
    _discover_pending_deliveries,
    build_startup_delivery_crew,
)
