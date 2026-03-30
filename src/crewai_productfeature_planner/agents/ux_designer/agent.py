"""UX Designer agent factories.

Creates agents for the UX design flow:
- **UX Designer**: Converts executive product summaries into structured
  markdown design specifications.  Uses the research model tier.
- **Design Partner**: Collaborates with UX Designer on the initial draft
  (gstack design-consultation methodology).
- **Senior Designer**: Reviews and finalizes the design via 7-pass review
  (gstack plan-design-review methodology).
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
    """Create a UX Designer agent that produces markdown design specs.

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
        tools=[],
        verbose=is_verbose(),
        allow_delegation=False,
    )


def get_task_configs() -> dict:
    """Load and return the UX Designer task configurations."""
    return _load_yaml("tasks.yaml")


# ------------------------------------------------------------------
# Design Partner agent (gstack design-consultation methodology)
# ------------------------------------------------------------------

def create_design_partner(
    project_id: str | None = None,
) -> Agent:
    """Create a Design Partner agent for the initial design draft.

    Works alongside the UX Designer to produce a comprehensive design
    specification covering product context, aesthetics, typography,
    color, spacing, layout, motion, and component patterns.

    Parameters
    ----------
    project_id:
        Optional project identifier for memory enrichment.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Design Partner requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )
    ensure_gemini_env()
    agent_config = _load_yaml("design_partner.yaml")["design_partner"]
    logger.info(
        "Creating Design Partner agent (role='%s')",
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
        tools=[],
        verbose=is_verbose(),
        allow_delegation=False,
    )


# ------------------------------------------------------------------
# Senior Designer agent (gstack plan-design-review methodology)
# ------------------------------------------------------------------

def create_senior_designer(
    project_id: str | None = None,
) -> Agent:
    """Create a Senior Designer agent for design review & finalization.

    Applies a rigorous 7-pass review (information architecture,
    interaction states, user journey, AI slop, design system alignment,
    responsive/accessibility, unresolved decisions) and produces the
    final production-ready design specification.

    Parameters
    ----------
    project_id:
        Optional project identifier for memory enrichment.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Senior Designer requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )
    ensure_gemini_env()
    agent_config = _load_yaml("senior_designer.yaml")["senior_designer"]
    logger.info(
        "Creating Senior Designer agent (role='%s')",
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
        tools=[],
        verbose=is_verbose(),
        allow_delegation=False,
    )


def get_ux_design_flow_task_configs() -> dict:
    """Load task configs for the standalone UX Design Flow."""
    return _load_yaml("ux_design_flow_tasks.yaml")
