"""Agent provider constants and default-agent helper."""

from crewai_productfeature_planner.agents.product_manager.agent import (
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
)

# Well-known agent provider identifiers used across the codebase.
# These match the ``provider`` parameter accepted by
# ``create_product_manager(provider=...)``.
AGENT_OPENAI = PROVIDER_OPENAI   # "openai"
AGENT_GEMINI = PROVIDER_GEMINI   # "gemini"

# All recognised provider identifiers (order = display preference).
VALID_AGENTS: list[str] = [AGENT_GEMINI, AGENT_OPENAI]

# Fallback when DEFAULT_AGENT env var is not set.
DEFAULT_AGENT_FALLBACK = AGENT_GEMINI


def get_default_agent() -> str:
    """Return the configured default agent provider identifier.

    Reads ``DEFAULT_AGENT`` from the environment.  Falls back to
    ``gemini`` when unset or invalid.
    """
    import os
    agent = os.environ.get("DEFAULT_AGENT", DEFAULT_AGENT_FALLBACK)
    if agent not in VALID_AGENTS:
        return DEFAULT_AGENT_FALLBACK
    return agent
