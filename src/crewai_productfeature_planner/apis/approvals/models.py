"""Pydantic models for the Approvals API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApprovalAction(BaseModel):
    """Hint for frontend about which endpoint to call."""

    label: str = Field(..., description="Button label (e.g. 'Approve').")
    endpoint: str = Field(..., description="REST endpoint to call.")
    payload_hint: dict[str, Any] = Field(
        default_factory=dict,
        description="Example payload for the action.",
    )


class ApprovalItem(BaseModel):
    """A single item awaiting user action."""

    id: str = Field(..., description="Synthetic approval ID.")
    kind: str = Field(
        ...,
        description=(
            "Approval type: prd_section_approval, publish_confluence, "
            "publish_jira, resume_paused."
        ),
    )
    run_id: str = Field(..., description="Associated flow run ID.")
    project_id: str = Field(default="", description="Associated project ID.")
    title: str = Field(..., description="Human-readable title.")
    section_key: str | None = Field(
        default=None,
        description="Section key for prd_section_approval kind.",
    )
    waiting_since: str = Field(
        default="", description="ISO-8601 timestamp when this started waiting."
    )
    owner_agent_id: str | None = Field(
        default=None, description="Agent responsible for this item."
    )
    actions: list[ApprovalAction] = Field(
        default_factory=list, description="Available actions."
    )


class ApprovalListResponse(BaseModel):
    """Response for GET /approvals/pending."""

    count: int = Field(default=0, description="Number of pending approval items.")
    items: list[ApprovalItem] = Field(
        default_factory=list, description="Pending approval items."
    )
