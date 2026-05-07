"""Configuration for Agentic Team integration."""

from __future__ import annotations

import os

# ── Feature flag ──────────────────────────────────────────────
AGENTIC_TEAM_ENABLED: bool = (
    os.environ.get("AGENTIC_TEAM_ENABLED", "false").lower() == "true"
)

# ── Inbound webhook (Agentic Team → Idea Foundry) ────────────
AGENTIC_TEAM_WEBHOOK_SECRET: str = os.environ.get(
    "AGENTIC_TEAM_WEBHOOK_SECRET", ""
)

# Persist received deliveries for audit/deduplication
WEBHOOK_DELIVERY_LOG_ENABLED: bool = (
    os.environ.get("WEBHOOK_DELIVERY_LOG_ENABLED", "true").lower() == "true"
)

# ── Outbound API calls (Idea Foundry → Agentic Team) ─────────
AGENTIC_TEAM_BASE_URL: str = os.environ.get(
    "AGENTIC_TEAM_BASE_URL", ""
)

# ── Self-referencing URL (for callback_url in kickoff) ────────
IDEA_FOUNDRY_BASE_URL: str = os.environ.get(
    "IDEA_FOUNDRY_BASE_URL", ""
)

# ── Supported schema versions ─────────────────────────────────
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})
