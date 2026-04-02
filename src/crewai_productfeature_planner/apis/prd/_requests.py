"""FastAPI request body models for PRD endpoints."""

from pydantic import BaseModel, Field


class PRDKickoffRequest(BaseModel):
    """Request body for POST /flow/prd/kickoff."""

    idea: str = Field(
        ...,
        min_length=1,
        max_length=50_000,
        description="The product feature idea to build a PRD for.",
        examples=["Add dark mode to the dashboard"],
    )
    title: str = Field(
        default="",
        max_length=256,
        description=(
            "Short display title for the idea. Used in dashboards and "
            "project views. When empty, the first line of the idea text "
            "is used as a fallback."
        ),
        examples=["Smart onboarding flow with personalization"],
    )
    project_id: str = Field(
        default="",
        max_length=50,
        description=(
            "Associate this PRD run with an existing project. Links the "
            "idea to the project so it inherits Confluence/Jira config. "
            "When empty, the idea is created without a project."
        ),
        examples=["proj-abc123"],
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
        max_length=10_000,
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
            "Which agent's result to use (e.g. 'openai'). "
            "Required when multiple agents produced results for the current "
            "section. Defaults to the first available agent when omitted."
        ),
        examples=["openai"],
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
