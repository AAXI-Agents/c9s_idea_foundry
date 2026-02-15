"""Pydantic models for PRD flow API requests and domain objects."""

from pydantic import BaseModel, Field


# ── PRD Section definitions ──────────────────────────────────

SECTION_ORDER: list[tuple[str, str]] = [
    ("executive_summary", "Executive Summary"),
    ("problem_statement", "Problem Statement"),
    ("user_personas", "User Personas"),
    ("functional_requirements", "Functional Requirements"),
    ("non_functional_requirements", "Non-Functional Requirements"),
    ("user_stories", "User Stories with Acceptance Criteria"),
    ("edge_cases", "Edge Cases and Error Handling"),
    ("analytics_metrics", "Analytics and Success Metrics"),
    ("dependencies_assumptions", "Dependencies and Assumptions"),
    ("out_of_scope", "Out of Scope"),
]

SECTION_KEYS: list[str] = [key for key, _ in SECTION_ORDER]


class PRDSection(BaseModel):
    """A single section of a PRD with its own iteration tracking."""

    key: str = Field(..., description="Section identifier slug.")
    title: str = Field(..., description="Human-readable section title.")
    content: str = Field(default="", description="Markdown content of this section.")
    critique: str = Field(default="", description="Latest critique for this section.")
    iteration: int = Field(
        default=0, description="How many times this section has been iterated."
    )
    is_approved: bool = Field(
        default=False, description="Whether the user has approved this section."
    )


class PRDDraft(BaseModel):
    """Structured PRD draft with individually iterable sections."""

    sections: list[PRDSection] = Field(default_factory=list)

    @classmethod
    def create_empty(cls) -> "PRDDraft":
        """Create a new PRDDraft with all sections initialized empty."""
        return cls(
            sections=[
                PRDSection(key=key, title=title) for key, title in SECTION_ORDER
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


# ── API response models ───────────────────────────────────────


class PRDKickoffResponse(BaseModel):
    """Response for POST /flow/prd/kickoff."""

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
    message: str = Field(..., description="Human-readable result message.")


class PRDSectionDetail(BaseModel):
    """A section's state as returned in run-status responses."""

    key: str = Field(..., description="Section identifier slug.")
    title: str = Field(..., description="Human-readable section title.")
    content: str = Field(default="", description="Current markdown content.")
    critique: str = Field(default="", description="Latest critique text.")
    iteration: int = Field(default=0, description="Section iteration count.")
    is_approved: bool = Field(default=False, description="Whether this section is approved.")


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
    iteration: int = Field(default=0, description="Total iteration count across all sections.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    result: str | None = Field(default=None, description="Final result when completed.")
    error: str | None = Field(default=None, description="Error message if failed.")
    current_section_key: str = Field(
        default="",
        description="Key of the section currently being iterated.",
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
    """Response for POST /flow/prd/resume."""

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
    message: str = Field(..., description="Human-readable status message.")
