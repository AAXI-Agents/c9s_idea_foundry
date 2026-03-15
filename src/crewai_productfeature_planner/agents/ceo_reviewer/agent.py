"""CEO Reviewer agent factory.

Creates a CEO/Founder agent that reviews executive summaries and
produces executive product summaries with 10-star product vision.
Uses the research model tier for deep thinking.
"""

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.agents.gemini_utils import (
    DEFAULT_GEMINI_RESEARCH_MODEL,
    DEFAULT_OPENAI_RESEARCH_MODEL,
    ensure_gemini_env,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

# LLM defaults — same as product_manager (research tier).
DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3

PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the agent's config directory."""
    logger.debug("Loading YAML config: %s", filename)
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_llm(provider: str = PROVIDER_GEMINI) -> LLM:
    """Build the LLM for the CEO Reviewer agent.

    Uses the research model tier — the CEO review requires deep
    reasoning about product direction and user empathy.
    """
    if provider == PROVIDER_GEMINI:
        ensure_gemini_env()
        model_name = os.environ.get(
            "GEMINI_CEO_MODEL",
            os.environ.get("GEMINI_RESEARCH_MODEL", DEFAULT_GEMINI_RESEARCH_MODEL),
        ).strip()
        if "/" not in model_name:
            model_name = f"gemini/{model_name}"
    else:
        model_name = os.environ.get(
            "OPENAI_RESEARCH_MODEL", DEFAULT_OPENAI_RESEARCH_MODEL,
        ).strip()
        if "/" not in model_name:
            model_name = f"openai/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info(
        "CEO Reviewer LLM (%s): %s (timeout=%ds, max_retries=%d)",
        provider, model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_ceo_reviewer(
    provider: str = PROVIDER_GEMINI,
    project_id: str | None = None,
) -> Agent:
    """Create a CEO Reviewer agent.

    Parameters
    ----------
    provider:
        LLM backend — ``"gemini"`` (default) or ``"openai"``.
    project_id:
        Optional project identifier for memory enrichment.
    """
    if provider == PROVIDER_GEMINI:
        has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
        has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if not has_api_key and not has_project:
            raise EnvironmentError(
                "CEO Reviewer requires GOOGLE_API_KEY or "
                "GOOGLE_CLOUD_PROJECT to be set."
            )

    agent_config = _load_yaml("agent.yaml")["ceo_reviewer"]
    logger.info(
        "Creating CEO Reviewer agent (provider='%s', role='%s')",
        provider, agent_config["role"].strip(),
    )

    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_llm(provider=provider),
        tools=[],  # CEO review is pure text reasoning — no tools needed
        verbose=is_verbose(),
        allow_delegation=False,
        reasoning=True,
        max_reasoning_attempts=3,
    )


def get_task_configs() -> dict:
    """Load and return the CEO reviewer task configurations."""
    return _load_yaml("tasks.yaml")
