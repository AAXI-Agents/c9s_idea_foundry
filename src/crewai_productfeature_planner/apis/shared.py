"""Shared types and in-memory state used across API subpackages."""

import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryDraft,
    PRDDraft,
)


# ── Shared types ──────────────────────────────────────────────


class FlowStatus(str, Enum):
    """Lifecycle status of a flow run.

    Note: errors during flow execution always result in ``PAUSED``
    (never ``FAILED``), so runs can be resumed after the issue is
    resolved.  ``FAILED`` is retained for backward compatibility but
    is not set by the current flow implementation.
    """

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"  # Retained for backward compat; flow uses PAUSED on errors


class FlowRun(BaseModel):
    """Tracks a single flow execution."""

    run_id: str
    flow_name: str
    status: FlowStatus = FlowStatus.PENDING
    iteration: int = 0
    enterprise_id: str = Field(
        default="",
        description="Enterprise ID of the user who kicked off the run (tenant scope).",
    )
    organization_id: str = Field(
        default="",
        description="Organization ID of the user who kicked off the run (tenant scope).",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    result: Any = None
    error: str | None = None
    current_draft: PRDDraft = Field(default_factory=PRDDraft.create_empty)
    current_section_key: str = ""
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
        description="The raw idea before refinement (empty when skipped).",
    )
    idea_refined: bool = Field(
        default=False,
        description="Whether the idea was refined by the Idea Refinement agent.",
    )
    finalized_idea: str = Field(
        default="",
        description="Last executive summary content once Phase 1 completes.",
    )
    requirements_breakdown: str = Field(
        default="",
        description="Structured requirements from the Requirements Breakdown agent.",
    )
    executive_summary: ExecutiveSummaryDraft = Field(
        default_factory=ExecutiveSummaryDraft,
        description="Iterative executive summary produced in Phase 1.",
    )
    confluence_url: str = Field(
        default="",
        description="URL of the Confluence page where the PRD was published.",
    )
    jira_output: str = Field(
        default="",
        description="Summary of Jira tickets created from PRD requirements.",
    )
    output_file: str = Field(
        default="",
        description="Path to the generated PRD markdown file.",
    )


# ── Flow cancellation ─────────────────────────────────────────


class FlowCancelled(Exception):
    """Raised when a running flow is cancelled (e.g. idea archived)."""


# ── In-memory stores ─────────────────────────────────────────
# Swap for a DB when persistence is needed.

runs: dict[str, FlowRun] = {}

# Per-run approval controls: Event is set when user approves.
approval_events: dict[str, threading.Event] = {}
approval_decisions: dict[str, bool] = {}
approval_feedback: dict[str, str] = {}

# Per-run pause flag: set to True to pause at the next approval point.
pause_requested: dict[str, bool] = {}

# Per-run selected agent: which agent's result the caller chose.
approval_selected: dict[str, str] = {}

# Per-run cancellation events: set when the flow should stop.
cancel_events: dict[str, threading.Event] = {}


def request_cancel(run_id: str) -> None:
    """Signal the cancel event for *run_id*.

    If no event is registered yet (e.g. the flow started before
    cancel-event registration was added), creates one and sets it
    immediately so ``check_cancelled()`` will detect it.
    """
    evt = cancel_events.get(run_id)
    if evt is None:
        evt = threading.Event()
        cancel_events[run_id] = evt
    evt.set()


def is_cancelled(run_id: str) -> bool:
    """Return ``True`` if cancellation has been requested for *run_id*."""
    evt = cancel_events.get(run_id)
    return evt is not None and evt.is_set()


def check_cancelled(run_id: str) -> None:
    """Raise :class:`FlowCancelled` if *run_id* has been cancelled."""
    if is_cancelled(run_id):
        raise FlowCancelled(f"Flow {run_id} was cancelled")


def run_visible_to_tenant(run: "FlowRun", tenant) -> bool:
    """Return True if *run* belongs to the caller's tenant scope.

    Multi-tenancy guard for the in-memory ``runs`` dict. Mirrors the
    rules in ``mongodb._tenant.tenant_filter()``:

    - ``SYS_ADMIN`` (or system context) → all runs visible.
    - ``ENT_ADMIN`` → all runs in their enterprise.
    - ``USER`` → only runs in their own organization.
    - Empty/None tenant → never visible (deny).

    Used by ``GET /flow/runs/{run_id}`` and POST approve/pause/resume to
    prevent cross-tenant reads or state mutations on the global
    in-memory ``runs`` dict.
    """
    # Lazy import to avoid circular dependency with mongodb._tenant
    from crewai_productfeature_planner.mongodb._tenant import (
        TenantContext,
        _SYSTEM_ENTERPRISE,
    )
    from crewai_productfeature_planner.rbac import Role

    if not isinstance(tenant, TenantContext):
        return False

    # System / SYS_ADMIN — global visibility.
    if tenant.enterprise_id == _SYSTEM_ENTERPRISE or tenant.role == Role.SYS_ADMIN:
        return True

    # Legacy in-memory runs created before this migration may not carry
    # tenant fields. Treat empty enterprise_id on the run as "unknown" and
    # deny non-admin reads to avoid accidental cross-tenant access.
    if not run.enterprise_id:
        return False

    # ENT_ADMIN — any org under their enterprise.
    if tenant.role == Role.ENT_ADMIN:
        return run.enterprise_id == tenant.enterprise_id

    # Regular user — must match both enterprise and org.
    return (
        run.enterprise_id == tenant.enterprise_id
        and run.organization_id == tenant.organization_id
    )
