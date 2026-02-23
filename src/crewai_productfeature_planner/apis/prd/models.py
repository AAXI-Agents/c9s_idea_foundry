"""Pydantic models for PRD flow API requests and domain objects."""

from pydantic import BaseModel, Field


# ── PRD Section definitions ──────────────────────────────────

SECTION_ORDER: list[tuple[str, str]] = [
    ("executive_summary", "Executive Summary"),
    ("problem_statement", "Problem Statement"),
    ("user_personas", "User Personas"),
    ("functional_requirements", "Functional Requirements"),
    ("no_functional_requirements", "Non-Functional Requirements"),
    ("edge_cases", "Edge Cases"),
    ("error_handling", "Error Handling"),
    ("success_metrics", "Success Metrics"),
    ("dependencies", "Dependencies"),
    ("assumptions", "Assumptions"),
]

SECTION_KEYS: list[str] = [key for key, _ in SECTION_ORDER]


# Well-known agent identifiers used across the codebase.
AGENT_OPENAI = "openai_pm"
AGENT_GEMINI = "gemini_pm"

# All recognised agent identifiers (order = display preference).
VALID_AGENTS: list[str] = [AGENT_GEMINI, AGENT_OPENAI]

# Fallback when DEFAULT_AGENT env var is not set.
DEFAULT_AGENT_FALLBACK = AGENT_GEMINI


def get_default_agent() -> str:
    """Return the configured default agent identifier.

    Reads ``DEFAULT_AGENT`` from the environment.  Falls back to
    ``gemini_pm`` when unset or invalid.
    """
    import os
    agent = os.environ.get("DEFAULT_AGENT", DEFAULT_AGENT_FALLBACK)
    if agent not in VALID_AGENTS:
        return DEFAULT_AGENT_FALLBACK
    return agent


# ── Executive Summary iteration model ────────────────────────


class ExecutiveSummaryIteration(BaseModel):
    """A single iteration record for the executive summary phase."""

    content: str = Field(default="", description="Markdown content of this iteration.")
    iteration: int = Field(
        default=1, description="1-based iteration number."
    )
    critique: str | None = Field(
        default=None,
        description="Critique feedback from critique_prd_task, initially null.",
    )
    updated_date: str = Field(
        default="",
        description="ISO-8601 timestamp of this iteration.",
    )


class ExecutiveSummaryDraft(BaseModel):
    """Tracks the iterative executive summary produced in the draft phase."""

    iterations: list[ExecutiveSummaryIteration] = Field(default_factory=list)
    is_approved: bool = Field(
        default=False,
        description="Whether the executive summary has been approved.",
    )

    @property
    def latest(self) -> ExecutiveSummaryIteration | None:
        """Return the most recent iteration, or None if empty."""
        return self.iterations[-1] if self.iterations else None

    @property
    def latest_content(self) -> str:
        """Return the content of the most recent iteration."""
        latest = self.latest
        return latest.content if latest else ""

    @property
    def current_iteration(self) -> int:
        """Return the current iteration number (0 if none)."""
        latest = self.latest
        return latest.iteration if latest else 0


class PRDSection(BaseModel):
    """A single section of a PRD with its own iteration tracking."""

    key: str = Field(..., description="Section identifier slug.")
    title: str = Field(..., description="Human-readable section title.")
    step: int = Field(
        default=0,
        description="1-based step number indicating order in the PRD workflow.",
    )
    content: str = Field(default="", description="Markdown content of this section.")
    critique: str = Field(default="", description="Latest critique for this section.")
    iteration: int = Field(
        default=0, description="How many times this section has been iterated."
    )
    updated_date: str = Field(
        default="",
        description="ISO-8601 timestamp of the last update to this section.",
    )
    is_approved: bool = Field(
        default=False, description="Whether the user has approved this section."
    )
    agent_results: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Per-agent draft results for this section. Keys are agent "
            "identifiers (e.g. 'openai_pm'), values are "
            "the markdown content each agent produced."
        ),
    )
    selected_agent: str = Field(
        default="",
        description=(
            "Which agent's result was selected by the user. Empty string "
            "means no selection has been made yet."
        ),
    )


class PRDDraft(BaseModel):
    """Structured PRD draft with individually iterable sections."""

    sections: list[PRDSection] = Field(default_factory=list)

    @classmethod
    def create_empty(cls) -> "PRDDraft":
        """Create a new PRDDraft with all sections initialized empty."""
        return cls(
            sections=[
                PRDSection(key=key, title=title, step=idx)
                for idx, (key, title) in enumerate(SECTION_ORDER, 1)
            ]
        )

    def get_section(self, key: str) -> PRDSection | None:
        """Look up a section by its key."""
        return next((s for s in self.sections if s.key == key), None)

    def approved_context(self, exclude_key: str = "") -> str:
        """Return markdown of all approved sections as context."""
        parts = []
        for s in self.sections:
            if s.is_approved and s.key != exclude_key and s.content:
                parts.append(f"## {s.title}\n\n{s.content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def all_sections_context(self, exclude_key: str = "") -> str:
        """Return markdown of all sections that have content, with status labels."""
        parts = []
        for s in self.sections:
            if s.key != exclude_key and s.content:
                status = "APPROVED" if s.is_approved else "DRAFT"
                parts.append(f"## {s.title} [{status}]\n\n{s.content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def all_approved(self) -> bool:
        """Check if all sections have been approved."""
        return all(s.is_approved for s in self.sections)

    def next_section(self) -> PRDSection | None:
        """Return the next section that hasn't been approved yet."""
        return next((s for s in self.sections if not s.is_approved), None)

    def assemble(self) -> str:
        """Assemble all sections into a single markdown PRD document."""
        parts = [f"## {s.title}\n\n{s.content}" for s in self.sections if s.content]
        return "# Product Requirements Document\n\n" + "\n\n---\n\n".join(parts)


# ── API request models ────────────────────────────────────────


class PRDKickoffRequest(BaseModel):
    """Request body for POST /flow/prd/kickoff."""

    idea: str = Field(
        ...,
        min_length=1,
        description="The product feature idea to build a PRD for.",
        examples=["Add dark mode to the dashboard"],
    )
    auto_approve: bool = Field(
        default=False,
        description=(
            "When true, the flow runs end-to-end without pausing for "
            "manual approval at each section (same behaviour as the CLI). "
            "Sections auto-iterate between PRD_SECTION_MIN_ITERATIONS and "
            "PRD_SECTION_MAX_ITERATIONS and are auto-approved when the "
            "critique contains SECTION_READY after the minimum iterations. "
            "The POST /flow/prd/approve endpoint is not needed when this "
            "is enabled — poll GET /flow/runs/{run_id} for progress instead."
        ),
    )


class PRDApproveRequest(BaseModel):
    """Request body for POST /flow/prd/approve."""

    run_id: str = Field(
        ...,
        description="The run to approve or continue.",
        examples=["a1b2c3d4e5f6"],
    )
    approve: bool = Field(
        ...,
        description="True to approve the current section, False to keep refining.",
        examples=[True],
    )
    feedback: str | None = Field(
        default=None,
        description=(
            "Optional critique feedback from the user. When provided with "
            "approve=false, this feedback is used as the critique for the "
            "current section instead of the agent's self-critique."
        ),
        examples=["Add more detail to the security section and include OAuth2 flow."],
    )
    selected_agent: str | None = Field(
        default=None,
        description=(
            "Which agent's result to use (e.g. 'openai_pm'). "
            "Required when multiple agents produced results for the current "
            "section. Defaults to the first available agent when omitted."
        ),
        examples=["openai_pm"],
    )


class PRDPauseRequest(BaseModel):
    """Request body for POST /flow/prd/pause."""

    run_id: str = Field(
        ...,
        description="The run to pause.",
        examples=["a1b2c3d4e5f6"],
    )


class PRDResumeRequest(BaseModel):
    """Request body for POST /flow/prd/resume."""

    run_id: str = Field(
        ...,
        description="The run_id of an unfinalized working idea to resume.",
        examples=["a1b2c3d4e5f6"],
    )
    auto_approve: bool = Field(
        default=False,
        description=(
            "When true, the resumed flow runs end-to-end without pausing "
            "for manual approval at each section (same behaviour as the "
            "CLI). Poll GET /flow/runs/{run_id} for progress instead of "
            "calling POST /flow/prd/approve."
        ),
    )


# ── API response models ───────────────────────────────────────


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
            "Agent identifiers currently participating in the flow "
            "(e.g. ['openai_pm'])."
        ),
    )
    dropped_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Agent identifiers that were removed from the flow after "
            "failing during parallel drafting."
        ),
    )
    agent_errors: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of dropped agent name to its error message."
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
            "Per-agent draft results. Keys are agent identifiers "
            "(e.g. 'openai_pm'), values are the markdown "
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
            "Agent identifiers currently participating in the flow "
            "(e.g. ['openai_pm'])."
        ),
    )
    dropped_agents: list[str] = Field(
        default_factory=list,
        description=(
            "Agent identifiers that were removed after failing during "
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


# ── Job tracking models ──────────────────────────────────────


class JobDetail(BaseModel):
    """A persistent job record from the ``crewJobs`` collection."""

    job_id: str = Field(..., description="Unique job identifier (same as run_id).")
    flow_name: str = Field(..., description="Name of the flow (e.g. 'prd').")
    idea: str = Field(default="", description="The feature idea / input text.")
    status: str = Field(
        ...,
        description=(
            "Job lifecycle status: queued, running, awaiting_approval, "
            "paused, or completed. Note: flow errors always result in "
            "'paused' (not 'failed'), allowing the run to be resumed."
        ),
    )
    error: str | None = Field(
        default=None,
        description=(
            "Error message when the job was paused due to an error. "
            "Present when the job encountered an LLM, billing, or "
            "internal error and was automatically paused."
        ),
    )

    queued_at: str | None = Field(default=None, description="ISO-8601 timestamp when the job was created.")
    started_at: str | None = Field(default=None, description="ISO-8601 timestamp when execution began.")
    completed_at: str | None = Field(
        default=None, description="ISO-8601 timestamp when the job reached a terminal state."
    )

    queue_time_ms: int | None = Field(
        default=None, description="Time spent in queue (started_at - queued_at) in milliseconds."
    )
    queue_time_human: str | None = Field(
        default=None, description="Queue duration in human-readable form (e.g. '0h 1m 30s')."
    )
    running_time_ms: int | None = Field(
        default=None, description="Time spent running (completed_at - started_at) in milliseconds."
    )
    running_time_human: str | None = Field(
        default=None, description="Running duration in human-readable form (e.g. '1h 23m 45s')."
    )
    updated_at: str | None = Field(default=None, description="ISO-8601 timestamp of last update.")


class JobListResponse(BaseModel):
    """Response for GET /flow/jobs."""

    count: int = Field(..., description="Number of jobs returned.")
    jobs: list[JobDetail] = Field(default_factory=list, description="List of job records.")


# ── Error response model ─────────────────────────────────────


class ErrorResponse(BaseModel):
    """Standard error envelope returned by all API endpoints.

    Returned for any unexpected server-side error (HTTP 500) or when
    the upstream LLM / OpenAI service is unavailable (HTTP 503).

    Error codes:
        ``LLM_ERROR``      — The LLM backend returned an unrecoverable
                             error after exhausting all retry attempts
                             (e.g. timeouts, model overload).
        ``BILLING_ERROR``  — OpenAI billing / quota issue detected
                             (e.g. ``insufficient_quota``,
                             ``billing_hard_limit_reached``).
        ``INTERNAL_ERROR`` — Any other unexpected server-side failure.
    """

    error_code: str = Field(
        ...,
        description=(
            "Machine-readable error code. One of: "
            "LLM_ERROR, BILLING_ERROR, INTERNAL_ERROR."
        ),
        examples=["LLM_ERROR"],
    )
    message: str = Field(
        ...,
        description="Human-readable description of the error.",
        examples=["LLM timeout after 4 attempts"],
    )
    run_id: str | None = Field(
        default=None,
        description="The run_id affected by this error, if applicable.",
        examples=["a1b2c3d4e5f6"],
    )
    detail: str | None = Field(
        default=None,
        description="Additional diagnostic detail (e.g. the original exception message).",
    )
