"""Staff Engineer agent factory.

Creates a Paranoid Staff Engineer agent that reviews Jira user story
sub-tasks to find production-killing bugs hidden in the implementation
plan.  Equipped with the Jira tool so it can create review sub-tasks.
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
from crewai_productfeature_planner.tools.jira_tool import JiraCreateIssueTool

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_llm() -> LLM:
    ensure_gemini_env()
    model_name = os.environ.get(
        "GEMINI_STAFF_ENG_MODEL",
        os.environ.get("GEMINI_RESEARCH_MODEL", DEFAULT_GEMINI_RESEARCH_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"
    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))
    logger.info(
        "Staff Engineer LLM: %s (timeout=%ds, retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_staff_engineer(
    project_id: str | None = None,
    run_id: str = "",
) -> Agent:
    """Create a Paranoid Staff Engineer agent with Jira tool."""
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Staff Engineer requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )

    agent_config = _load_yaml("agent.yaml")["staff_engineer"]
    logger.info(
        "Creating Staff Engineer agent (role='%s')",
        agent_config["role"].strip(),
    )
    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )
    from crewai_productfeature_planner.scripts.knowledge_sources import (
        build_project_knowledge_source,
        get_google_embedder_config,
    )
    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_llm(),
        tools=[JiraCreateIssueTool(authoritative_run_id=run_id)],
        verbose=is_verbose(),
        allow_delegation=False,
        knowledge_sources=[build_project_knowledge_source()],
        embedder=get_google_embedder_config(),
    )


def get_task_configs() -> dict:
    return _load_yaml("tasks.yaml")
