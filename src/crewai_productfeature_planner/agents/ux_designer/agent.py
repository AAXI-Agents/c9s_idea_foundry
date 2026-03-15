"""UX Designer agent factory.

Creates a UX Designer agent that converts executive product summaries
into structured Figma Make prompts and submits them to generate
clickable prototypes.  Uses the research model tier for design thinking.
"""

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.agents.gemini_utils import (
    DEFAULT_GEMINI_RESEARCH_MODEL,
    ensure_gemini_env,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory
from crewai_productfeature_planner.tools.figma import FigmaMakeTool

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the agent's config directory."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_llm() -> LLM:
    """Build the LLM for the UX Designer agent (research tier)."""
    ensure_gemini_env()
    model_name = os.environ.get(
        "GEMINI_UX_DESIGNER_MODEL",
        os.environ.get("GEMINI_RESEARCH_MODEL", DEFAULT_GEMINI_RESEARCH_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info(
        "UX Designer LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_ux_designer(
    project_id: str | None = None,
) -> Agent:
    """Create a UX Designer agent with FigmaMakeTool.

    Parameters
    ----------
    project_id:
        Optional project identifier for memory enrichment.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "UX Designer requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )

    agent_config = _load_yaml("agent.yaml")["ux_designer"]
    logger.info(
        "Creating UX Designer agent (role='%s')",
        agent_config["role"].strip(),
    )
    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_llm(),
        tools=[FigmaMakeTool()],
        verbose=is_verbose(),
        allow_delegation=False,
    )


def get_task_configs() -> dict:
    """Load and return the UX Designer task configurations."""
    return _load_yaml("tasks.yaml")
