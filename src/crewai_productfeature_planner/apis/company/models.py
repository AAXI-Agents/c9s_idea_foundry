"""Company Dashboard API — Pydantic models.

Models for org chart, agent details, budget summary, and activity feed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Org Chart ─────────────────────────────────────────────────


class OrgChartNode(BaseModel):
    agent_id: str
    display_name: str
    department: str
    role: str = ""
    title: str = ""
    reports_to: str | None = None
    avatar: str = ""
    status: str = "idle"
    last_active_at: str | None = None


class OrgChartResponse(BaseModel):
    agents: list[OrgChartNode]
    departments: list[str]


# ── Agent Detail ──────────────────────────────────────────────


class AgentBudget(BaseModel):
    monthly_token_limit: int = 0
    monthly_cost_limit_usd: float = 0.0
    warning_threshold_pct: int = 80
    hard_stop: bool = False


class AgentStats(BaseModel):
    total_runs: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    month_tokens: int = 0
    month_cost_usd: float = 0.0
    month_reset_at: str = ""


class AgentDetail(BaseModel):
    agent_id: str
    display_name: str
    department: str
    role: str = ""
    title: str = ""
    reports_to: str | None = None
    avatar: str = ""
    llm_tier: str = ""
    capabilities: list[str] = Field(default_factory=list)
    budget: AgentBudget = Field(default_factory=AgentBudget)
    status: str = "idle"
    current_task: dict[str, Any] | None = None
    last_active_at: str | None = None
    stats: AgentStats = Field(default_factory=AgentStats)
    created_at: str = ""
    updated_at: str = ""


class AgentListResponse(BaseModel):
    agents: list[AgentDetail]
    total: int


# ── Budget ────────────────────────────────────────────────────


class DepartmentBudget(BaseModel):
    department: str
    cost_usd: float = 0.0
    tokens: int = 0
    agent_count: int = 0


class TopAgentCost(BaseModel):
    agent_id: str
    display_name: str
    department: str
    cost_usd: float = 0.0
    tokens: int = 0


class BudgetSummaryResponse(BaseModel):
    by_department: list[DepartmentBudget]
    top_agents: list[TopAgentCost]


# ── Activity Feed ─────────────────────────────────────────────


class ActivityEvent(BaseModel):
    event_id: str
    event_type: str
    agent_id: str
    run_id: str | None = None
    session_id: str | None = None
    department: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float | None = None
    tokens_used: int | None = None
    created_at: str = ""


class ActivityListResponse(BaseModel):
    events: list[ActivityEvent]
    total: int


# ── Budget Update Request ─────────────────────────────────────


class BudgetUpdateRequest(BaseModel):
    monthly_token_limit: int | None = None
    monthly_cost_limit_usd: float | None = None
    warning_threshold_pct: int | None = Field(default=None, ge=1, le=100)
    hard_stop: bool | None = None
