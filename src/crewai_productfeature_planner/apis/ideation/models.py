"""Pydantic models for the Ideation Flow API.

Response shapes are aligned with the frontend contract
(c9s_idea_foundry_web agentService.ts TypeScript interfaces).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Structured ideation output models ─────────────────────────


class Recommendation(BaseModel):
    """One of 3 concrete options for a clarifying question."""

    label: str = Field(..., description="Concrete answer/direction (specific to the idea).")
    pro: str = Field(..., description="Key advantage (one line).")
    con: str = Field(..., description="Key risk or disadvantage (one line).")
    complexity: Literal["Low", "Medium", "High"] = Field(
        ..., description="Implementation complexity."
    )


class ClarifyingQuestion(BaseModel):
    """A structured question with exactly 3 recommendations."""

    id: int = Field(..., description="1-based question index.")
    question: str = Field(..., description="Specific, targeted question.")
    context: str = Field(..., description="Why this question matters (agent perspective).")
    recommendations: list[Recommendation] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 recommendation options.",
    )


class StructuredIdeationResponse(BaseModel):
    """Universal agent output for all ideation steps — structured questions."""

    acknowledgment: str = Field(
        ..., description="1-2 sentence acknowledgment of user input."
    )
    questions: list[ClarifyingQuestion] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-5 structured clarifying questions.",
    )
    agent_insight: str | None = Field(
        default=None, description="Agent's key strategic observation."
    )
    summary_draft: str | None = Field(
        default=None,
        description="Step output draft when enough info is gathered.",
    )


class QuestionAnswer(BaseModel):
    """User's answer to one clarifying question."""

    question_id: int = Field(..., description="1-based question ID being answered.")
    selected_option: int | None = Field(
        default=None, description="0-2 index of selected recommendation, None if custom."
    )
    custom_feedback: str | None = Field(
        default=None, description="Free-form alternative answer."
    )


# ── Request models ────────────────────────────────────────────


class IdeationKickoffRequest(BaseModel):
    """Start a new ideation session."""

    idea: str | None = Field(
        default=None,
        alias="idea",
        description="Initial idea text to seed the session.",
    )
    title: str | None = Field(
        default=None,
        description="Optional title for the session. Auto-generated if omitted.",
    )
    project_id: str | None = Field(
        default=None,
        description="Link this session to an existing project.",
    )

    model_config = {"populate_by_name": True}


class IdeationRespondRequest(BaseModel):
    """User responds to an agent question/prompt."""

    content: str = Field(
        ...,
        min_length=1,
        description="The user's response text.",
    )
    response_type: str = Field(
        default="text",
        description="Response type: text, choice, selection.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Structured answers for choice/card interactions.",
    )


class IdeationAdvanceRequest(BaseModel):
    """Approve current step output and advance to the next."""

    approved_output: dict[str, Any] | None = Field(
        default=None,
        description="Explicit output to save (if user edited agent's output).",
    )


class IdeationIterateRequest(BaseModel):
    """Request re-iteration of the current step with optional feedback."""

    feedback: str | None = Field(
        default=None,
        description="Optional feedback to guide the re-iteration.",
    )


class IdeationUpdateRequest(BaseModel):
    """Update session metadata (title, project_id)."""

    title: str | None = Field(default=None, description="New session title.")
    project_id: str | None = Field(default=None, description="Assign to a project.")


class IdeationRollbackRequest(BaseModel):
    """Request rollback to a specific or previous step."""

    target_step: str | None = Field(
        default=None,
        description="Step name to roll back to (e.g. 'ideation'). If omitted, goes to previous.",
    )


# ── Response models ───────────────────────────────────────────


class MessageMetadata(BaseModel):
    """Metadata attached to agent messages for UI rendering."""

    render_type: str | None = None
    questions: list[dict[str, Any]] | None = None
    choices: list[dict[str, Any]] | None = None
    can_iterate: bool | None = None
    can_advance: bool | None = None
    structured: dict[str, Any] | None = None
    response_type: str | None = None
    answers: list[dict[str, Any]] | None = None
    error: bool | None = None


class IdeationMessageItem(BaseModel):
    """A single chat message (frontend-compatible shape)."""

    id: str
    role: str
    agent_name: str | None = None
    content: str
    content_type: str = "text"
    metadata: MessageMetadata | None = None
    flow_step: str
    created_at: str


class IdeationMessagesResponse(BaseModel):
    """Paginated messages response."""

    messages: list[IdeationMessageItem]
    total: int
    has_more: bool = False


class StepOutput(BaseModel):
    """Output state for a single flow step."""

    status: str = "pending"
    iteration: int = 1
    started_at: str | None = None
    completed_at: str | None = None
    executive_summary: str | None = None
    mission_statement: str | None = None
    personas: list[dict[str, Any]] | None = None
    solution_type: dict[str, Any] | None = None
    primary_goals: list[dict[str, Any]] | None = None
    tech_stack: dict[str, Any] | None = None


class IdeationSessionResponse(BaseModel):
    """Full session detail (frontend-compatible shape)."""

    id: str
    title: str
    status: str
    current_step: str
    iteration: int = 1
    created_at: str
    updated_at: str
    completed_at: str | None = None
    project_id: str | None = None
    prd_run_id: str | None = None
    outputs: dict[str, StepOutput] = {}


class IdeationSessionSummary(BaseModel):
    """Session list item."""

    id: str
    title: str
    status: str
    current_step: str
    iteration: int = 1
    created_at: str
    updated_at: str
    completed_at: str | None = None
    project_id: str | None = None
    prd_run_id: str | None = None


class IdeationSessionListResponse(BaseModel):
    """Paginated session list response."""

    items: list[IdeationSessionSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class IdeationKickoffResponse(BaseModel):
    """Response when a new session is created."""

    session_id: str
    status: str = "active"
    current_step: str = "ideation"
    message: str = "Ideation session started. The Ideation Agent is analyzing your idea."


class IdeationRespondResponse(BaseModel):
    """Response after submitting a user message."""

    message_id: str
    status: str = "completed"
    content: str = ""
    step: str = ""
    role: str = "agent"
    message: str = "Agent response ready."
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Structured data when render_type is 'structured_questions'.",
    )


class IdeationIterateResponse(BaseModel):
    """Response after requesting re-iteration."""

    status: str = "iterating"
    iteration: int
    message: str


class IdeationAdvanceResponse(BaseModel):
    """Response when advancing to the next step."""

    status: str
    previous_step: str
    current_step: str | None = None
    message: str
    prd_run_id: str | None = None
    prd_status: str | None = None


class IdeationRollbackResponse(BaseModel):
    """Response when rolling back to a previous step."""

    status: str = "rolled_back"
    current_step: str
    iteration: int = 1
    message: str


class IdeationDeleteResponse(BaseModel):
    """Response when archiving/deleting a session."""

    status: str = "archived"
    message: str = "Session archived"


class IdeationErrorResponse(BaseModel):
    """Standard error response for ideation endpoints."""

    error_code: str
    message: str
    detail: str | None = None
