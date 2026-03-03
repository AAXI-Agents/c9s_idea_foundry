"""FastAPI response models for PRD endpoints."""

from pydantic import BaseModel, Field

from ._domain import ExecutiveSummaryDraft


class PRDKickoffResponse(BaseModel):
    """Response for POST /flow/prd/kickoff.

    Returned when a new PRD flow is accepted.  The flow runs in the
    background through Idea Refinement → Requirements Breakdown →
    Phase 1 (Executive Summary iteration) → Phase 2 (9-section
    auto-iterate).  Poll GET /flow/runs/{run_id} for status.
    """

    run_id: str = Field(..., description="Unique identifier for this flow run.")
    flow_name: str = Field(default="prd", description="Name of the flow.")
    status: str = Field(..., description="Current status of the run.")
    message: str = Field(..., description="Human-readable status message.")


class PRDActionResponse(BaseModel):
    """Response for approval, pause, and feedback actions."""

    run_id: str = Field(..., description="The run this action was applied to.")
    action: str = Field(
        ...,
        description=(
            "The action that was taken: 'approved', 'continuing refinement', "
            "'continuing refinement with user feedback', or 'paused'."
        ),
    )
    section: str = Field(
        default="",
        description="The section key the action was applied to.",
    )
    current_step: int | None = Field(
        default=None,
        description="1-based step number of the current section.",
    )
    sections_approved: int | None = Field(
        default=None,
        description="Number of sections approved so far (including this one if approved).",
    )
    sections_total: int | None = Field(
        default=None,
        description="Total number of sections in the PRD.",
    )
    is_final_section: bool = Field(
        default=False,
        description="True when this approval completed the last section — the flow will finalize.",
    )
    active_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Provider identifiers currently participating in the flow "
            "(e.g. ['openai'])."
        ),
    )
    dropped_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Provider identifiers that were removed from the flow after "
            "failing during parallel drafting."
        ),
    )
    agent_errors: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of dropped provider name to its error message."
        ),
    )
    message: str = Field(..., description="Human-readable result message.")


class PRDSectionDetail(BaseModel):
    """A section's state as returned in run-status responses."""

    key: str = Field(..., description="Section identifier slug.")
    title: str = Field(..., description="Human-readable section title.")
    step: int = Field(default=0, description="1-based step number in the PRD workflow.")
    content: str = Field(default="", description="Current markdown content.")
    critique: str = Field(default="", description="Latest critique text.")
    iteration: int = Field(default=0, description="Section iteration count.")
    updated_date: str = Field(
        default="",
        description="ISO-8601 timestamp of the last update to this section.",
    )
    is_approved: bool = Field(default=False, description="Whether this section is approved.")
    agent_results: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Per-agent draft results. Keys are provider identifiers "
            "(e.g. 'openai'), values are the markdown "
            "content each agent produced for this section."
        ),
    )
    selected_agent: str = Field(
        default="",
        description="Which agent's result was selected by the user.",
    )


class PRDDraftDetail(BaseModel):
    """Structured draft state for API responses."""

    sections: list[PRDSectionDetail] = Field(
        default_factory=list,
        description="Ordered list of PRD sections with their current state.",
    )
    all_approved: bool = Field(
        default=False,
        description="True when every section has been approved.",
    )


class PRDRunStatusResponse(BaseModel):
    """Response for GET /flow/runs/{run_id}."""

    run_id: str = Field(..., description="Unique run identifier.")
    flow_name: str = Field(..., description="Name of the flow.")
    status: str = Field(..., description="Current lifecycle status.")
    iteration: int = Field(
        default=0,
        description=(
            "Total iteration count across all sections.  In the two-phase "
            "flow, Phase 1 (Executive Summary) iterates ≥ PRD_EXEC_RESUME_THRESHOLD "
            "times, and Phase 2 sections each iterate between "
            "PRD_SECTION_MIN_ITERATIONS and PRD_SECTION_MAX_ITERATIONS."
        ),
    )
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    update_date: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of the last update.",
    )
    completed_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp when the run was completed.",
    )
    result: str | None = Field(default=None, description="Final result when completed.")
    error: str | None = Field(
        default=None,
        description=(
            "Error message if the run was paused due to an error. "
            "Prefixed with an error code: BILLING_ERROR, LLM_ERROR, or "
            "INTERNAL_ERROR. Note: errors always result in status='paused' "
            "(never 'failed'), so the run can be resumed after the issue "
            "is resolved."
        ),
    )
    current_section_key: str = Field(
        default="",
        description="Key of the section currently being iterated.",
    )
    current_step: int = Field(
        default=0,
        description="1-based step number of the current section.",
    )
    sections_approved: int = Field(
        default=0,
        description="Number of approved sections (convenience, derivable from current_draft).",
    )
    sections_total: int = Field(
        default=0,
        description="Total number of PRD sections.",
    )
    active_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Provider identifiers currently participating in the flow "
            "(e.g. ['openai'])."
        ),
    )
    dropped_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Provider identifiers that were removed after failing during "
            "parallel drafting."
        ),
    )
    agent_errors: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of dropped agent name to its error message."
        ),
    )
    original_idea: str = Field(
        default="",
        description=(
            "The raw idea before the Idea Refinement agent enriched it. "
            "Empty when refinement was skipped."
        ),
    )
    idea_refined: bool = Field(
        default=False,
        description="Whether the idea was refined by the Idea Refinement agent.",
    )
    finalized_idea: str = Field(
        default="",
        description=(
            "Copy of the last executive summary content once Phase 1 "
            "completes. Empty until the executive summary iteration "
            "loop finishes."
        ),
    )
    requirements_breakdown: str = Field(
        default="",
        description=(
            "Structured product requirements produced by the Requirements "
            "Breakdown agent. Empty until the breakdown phase completes."
        ),
    )
    executive_summary: ExecutiveSummaryDraft = Field(
        default_factory=ExecutiveSummaryDraft,
        description=(
            "Iterative executive summary produced in Phase 1. Contains "
            "the full iteration history with content, critique, and "
            "timestamps for each cycle."
        ),
    )
    confluence_url: str = Field(
        default="",
        description=(
            "URL of the Confluence page where the PRD was published. "
            "Empty until post-completion publishing succeeds."
        ),
    )
    jira_output: str = Field(
        default="",
        description=(
            "Summary of Jira tickets created from PRD requirements. "
            "Empty until post-completion ticketing completes."
        ),
    )
    output_file: str = Field(
        default="",
        description=(
            "Path to the generated PRD markdown file on disk. "
            "Empty until the flow finalizes."
        ),
    )
    current_draft: PRDDraftDetail = Field(
        default_factory=PRDDraftDetail,
        description="Full structured draft with per-section state.",
    )


class PRDResumableRun(BaseModel):
    """An unfinalized run that can be resumed."""

    run_id: str = Field(..., description="Unique run identifier.")
    idea: str = Field(default="", description="The feature idea text.")
    iteration: int = Field(default=0, description="Last iteration number.")
    created_at: str | None = Field(
        default=None, description="ISO-8601 timestamp of the last activity."
    )
    sections: list[str] = Field(
        default_factory=list,
        description="Section keys that have draft content.",
    )
    exec_summary_iterations: int = Field(
        default=0,
        description="Number of executive summary iterations completed.",
    )
    req_breakdown_iterations: int = Field(
        default=0,
        description="Number of requirements breakdown iterations completed.",
    )


class PRDResumableListResponse(BaseModel):
    """Response for GET /flow/prd/resumable."""

    count: int = Field(..., description="Number of resumable runs.")
    runs: list[PRDResumableRun] = Field(
        default_factory=list, description="List of resumable runs."
    )


class PRDResumeResponse(BaseModel):
    """Response for POST /flow/prd/resume.

    Returned when a paused or unfinalized run is successfully resumed.
    Sections with existing content will skip the draft step and resume
    directly into the critique→refine loop.  Degenerate content left by
    a previous crash is cleaned up automatically.
    """

    run_id: str = Field(..., description="The resumed run identifier.")
    flow_name: str = Field(default="prd", description="Name of the flow.")
    status: str = Field(..., description="Current status after resuming.")
    sections_approved: int = Field(
        default=0, description="Number of sections already approved."
    )
    sections_total: int = Field(
        default=0, description="Total number of PRD sections."
    )
    next_section: str | None = Field(
        default=None, description="Key of the next section to iterate."
    )
    next_step: int | None = Field(
        default=None, description="1-based step number of the next section."
    )
    message: str = Field(..., description="Human-readable status message.")
