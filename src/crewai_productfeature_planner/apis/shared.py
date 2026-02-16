"""Shared types and in-memory state used across API subpackages."""

import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.prd.models import PRDDraft


# ── Shared types ──────────────────────────────────────────────


class FlowStatus(str, Enum):
    """Lifecycle status of a flow run."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class FlowRun(BaseModel):
    """Tracks a single flow execution."""

    run_id: str
    flow_name: str
    status: FlowStatus = FlowStatus.PENDING
    iteration: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    result: Any = None
    error: str | None = None
    current_draft: PRDDraft = Field(default_factory=PRDDraft.create_empty)
    current_section_key: str = ""


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
