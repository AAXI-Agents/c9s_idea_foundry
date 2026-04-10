"""PRD flow constants, utility functions, exceptions, and state model.

Extracted from ``prd_flow.py`` for modularity.  All names are
re-exported by ``prd_flow.py`` so existing imports remain valid.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Union

from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryDraft,
    PRDDraft,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

PAUSE_SENTINEL = "__PAUSE__"

# Minimum and maximum critique→refine iterations for each PRD section.
# Override via ``PRD_SECTION_MIN_ITERATIONS`` / ``PRD_SECTION_MAX_ITERATIONS``.
DEFAULT_MIN_SECTION_ITERATIONS = 2
DEFAULT_MAX_SECTION_ITERATIONS = 10

# When resuming, skip Phase 1 (executive summary iteration) if the
# document already has at least this many executive summary iterations.
# Override via ``PRD_EXEC_RESUME_THRESHOLD``.
DEFAULT_EXEC_RESUME_THRESHOLD = 3

# How many PM agents to run in parallel for section drafting.
# 1 = default agent only; 2 = default + optional (e.g. Gemini + OpenAI).
# Override via ``DEFAULT_MULTI_AGENTS``.
DEFAULT_MULTI_AGENTS = 1

# Maximum allowed character count for a single PRD section.
# If a refine result exceeds this, it is treated as degenerate LLM
# output (e.g. repetitive "ofofofof…") and the previous version is
# kept.  Override via ``PRD_SECTION_MAX_CHARS``.
DEFAULT_SECTION_MAX_CHARS = 30_000

# If a refine result is more than this multiplier times the previous
# content length, it is considered degenerate.  Override via
# ``PRD_SECTION_GROWTH_FACTOR``.
DEFAULT_SECTION_GROWTH_FACTOR = 5.0


def _get_section_iteration_limits() -> tuple[int, int]:
    """Return ``(min_iterations, max_iterations)`` from env or defaults."""
    min_iter = int(os.environ.get(
        "PRD_SECTION_MIN_ITERATIONS", str(DEFAULT_MIN_SECTION_ITERATIONS),
    ))
    max_iter = int(os.environ.get(
        "PRD_SECTION_MAX_ITERATIONS", str(DEFAULT_MAX_SECTION_ITERATIONS),
    ))
    # Sanity clamp
    min_iter = max(1, min(min_iter, 10))
    max_iter = max(min_iter, min(max_iter, 20))
    return min_iter, max_iter


def _is_degenerate_content(
    content: str,
    prev_len: int = 0,
    *,
    max_chars: int | None = None,
    growth_factor: float | None = None,
) -> bool:
    """Return *True* if *content* looks like degenerate LLM output.

    Two independent triggers:
    1. Absolute size exceeds *max_chars* (env ``PRD_SECTION_MAX_CHARS``).
    2. Size exceeds *prev_len* × *growth_factor*
       (env ``PRD_SECTION_GROWTH_FACTOR``), when *prev_len* > 0.
    """
    if max_chars is None:
        max_chars = int(os.environ.get(
            "PRD_SECTION_MAX_CHARS",
            str(DEFAULT_SECTION_MAX_CHARS),
        ))
    if growth_factor is None:
        growth_factor = float(os.environ.get(
            "PRD_SECTION_GROWTH_FACTOR",
            str(DEFAULT_SECTION_GROWTH_FACTOR),
        ))
    new_len = len(content)
    if new_len > max_chars:
        return True
    if prev_len > 0 and new_len > prev_len * growth_factor:
        return True
    return False


# Type alias for the approval callback return.
#   - True/False       → approve / refine (selects first available agent)
#   - str              → user feedback for refinement
#   - PAUSE_SENTINEL   → pause the flow
#   - (agent, True)    → approve using *agent*'s result
#   - (agent, False)   → refine using *agent*
#   - (agent, str)     → refine with user feedback using *agent*
ApprovalDecision = Union[bool, str, tuple[str, Union[bool, str]]]


class PauseRequested(Exception):
    """Raised when the user requests to pause and save the current iteration."""


class IdeaFinalized(Exception):
    """Raised when the user approves the refined idea without generating a PRD.

    The working idea has been marked as completed by the time this
    is raised.
    """


class RequirementsFinalized(Exception):
    """Raised when the user finalizes the requirements breakdown without PRD.

    The working idea has been marked as completed by the time this
    is raised.
    """


class ExecutiveSummaryCompleted(Exception):
    """Raised when the executive summary iteration is complete.

    The user chose not to continue to section-level drafting.  The
    executive summary has been saved to ``workingIdeas``.
    """


class PRDState(BaseModel):
    """Tracks the evolving PRD through the section-by-section workflow."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    idea: str = ""
    draft: PRDDraft = Field(default_factory=PRDDraft.create_empty)
    current_section_key: str = ""
    critique: str = ""
    final_prd: str = ""
    iteration: int = 0
    is_ready: bool = False
    status: str = Field(
        default="new",
        description="Lifecycle status: 'new', 'inprogress', or 'completed'.",
    )
    created_at: str = Field(
        default="",
        description="ISO-8601 timestamp when the run was created.",
    )
    update_date: str = Field(
        default="",
        description="ISO-8601 timestamp of the last update.",
    )
    completed_at: str = Field(
        default="",
        description="ISO-8601 timestamp when the run was completed.",
    )
    active_agents: list[str] = Field(
        default_factory=list,
        description="Agent identifiers currently participating in the flow.",
    )
    dropped_agents: list[str] = Field(
        default_factory=list,
        description="Agent identifiers removed after failing during parallel drafting.",
    )
    agent_errors: dict[str, str] = Field(
        default_factory=dict,
        description="Map of agent name to error message for agents that failed.",
    )
    original_idea: str = Field(
        default="",
        description="The raw idea before refinement (empty when refinement is skipped).",
    )
    idea_refined: bool = Field(
        default=False,
        description="Whether the idea was refined by the Idea Refinement agent.",
    )
    refinement_history: list[dict] = Field(
        default_factory=list,
        description="Iteration history from idea refinement (each dict has 'iteration', 'idea', and optionally 'evaluation').",
    )
    refinement_options_history: list[dict] = Field(
        default_factory=list,
        description=(
            "Records when 3 alternative directions were presented and which "
            "was selected. Each dict has 'iteration', 'trigger', 'options', "
            "'selected'."
        ),
    )
    requirements_breakdown: str = Field(
        default="",
        description="Structured product requirements produced by the Requirements Breakdown agent.",
    )
    breakdown_history: list[dict] = Field(
        default_factory=list,
        description="Iteration history from requirements breakdown (each dict has 'iteration', 'requirements', 'evaluation').",
    )
    requirements_broken_down: bool = Field(
        default=False,
        description="Whether the idea has been broken down into requirements.",
    )
    executive_summary: ExecutiveSummaryDraft = Field(
        default_factory=ExecutiveSummaryDraft,
        description="Iterative executive summary produced in the draft phase.",
    )
    executive_product_summary: str = Field(
        default="",
        description="CEO-reviewed executive product summary generated after the executive summary.",
    )
    engineering_plan: str = Field(
        default="",
        description="Engineering plan generated by the Eng Manager after the CEO review.",
    )
    figma_design_url: str = Field(
        default="",
        description="Deprecated — always empty. Kept for backward compatibility with existing MongoDB documents.",
    )
    figma_design_prompt: str = Field(
        default="",
        description="Deprecated — use ux_design_content. Kept for backward compatibility.",
    )
    figma_design_status: str = Field(
        default="",
        description="Deprecated — use ux_design_status. Kept for backward compatibility.",
    )
    ux_design_content: str = Field(
        default="",
        description="Markdown design specification produced by the UX Designer agents.",
    )
    ux_design_status: str = Field(
        default="",
        description=(
            "UX design generation status: '' (not started), "
            "'generating' (agent working), "
            "'completed' (design spec produced), "
            "'skipped' (error or no credentials)."
        ),
    )
    finalized_idea: str = Field(
        default="",
        description="Copy of the last iterated executive summary content once Phase 1 completes.",
    )
    confluence_url: str = Field(
        default="",
        description="URL of the Confluence page where the PRD was published.",
    )
    jira_output: str = Field(
        default="",
        description="Summary of Jira tickets created from PRD requirements.",
    )
    jira_skeleton: str = Field(
        default="",
        description="Skeleton of Epics and User Stories (titles only) for user approval before creation.",
    )
    jira_epics_stories_output: str = Field(
        default="",
        description="Output from Phase 2 — Epics and User Stories created (before sub-tasks).",
    )
    jira_phase: str = Field(
        default="",
        description=(
            "Current Jira ticketing phase: '' (not started), "
            "Scrum: 'skeleton_pending' → 'skeleton_approved' → "
            "'epics_stories_done' → 'subtasks_ready' → 'subtasks_done' → "
            "'review_ready' → 'review_done' → 'qa_test_ready' → 'qa_test_done'. "
            "Kanban: 'kanban_skeleton_pending' → 'kanban_skeleton_approved' → "
            "'kanban_tasks_done'."
        ),
    )
    jira_review_output: str = Field(
        default="",
        description="Output from Phase 4 — Staff Engineer and QA Lead review sub-tasks.",
    )
    jira_qa_test_output: str = Field(
        default="",
        description="Output from Phase 5 — QA Engineer test sub-tasks.",
    )


__all__ = [
    "PAUSE_SENTINEL",
    "DEFAULT_MIN_SECTION_ITERATIONS",
    "DEFAULT_MAX_SECTION_ITERATIONS",
    "DEFAULT_EXEC_RESUME_THRESHOLD",
    "DEFAULT_MULTI_AGENTS",
    "DEFAULT_SECTION_MAX_CHARS",
    "DEFAULT_SECTION_GROWTH_FACTOR",
    "ApprovalDecision",
    "PauseRequested",
    "IdeaFinalized",
    "RequirementsFinalized",
    "ExecutiveSummaryCompleted",
    "PRDState",
    "_get_section_iteration_limits",
    "_is_degenerate_content",
]
