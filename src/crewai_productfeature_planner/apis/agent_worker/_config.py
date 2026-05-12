"""Configuration for the Agent Worker proxy layer."""

from __future__ import annotations

import os

# ── Feature flag ──────────────────────────────────────────────
AGENT_WORKER_ENABLED: bool = (
    os.environ.get("AGENT_WORKER_ENABLED", "false").lower() == "true"
)

# ── Outbound API calls (Idea Foundry → Agent Worker) ─────────
AGENT_WORKER_BASE_URL: str = os.environ.get(
    "AGENT_WORKER_BASE_URL", ""
)
