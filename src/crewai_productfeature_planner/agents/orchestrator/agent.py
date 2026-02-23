"""Orchestrator agent factory — coordinates Atlassian publishing tasks.

Creates a Gemini-powered agent responsible for publishing completed
PRDs to Confluence and creating Jira tickets for actionable
requirements.

Environment variables:

* ``ORCHESTRATOR_MODEL`` — override the Gemini model
  (defaults to ``GEMINI_MODEL`` → ``DEFAULT_GEMINI_MODEL``).
* ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT`` — at least one
  must be set for Gemini authentication.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.agents.gemini_utils import (
    DEFAULT_GEMINI_MODEL,
    ensure_gemini_env,
)
from crewai_productfeature_planner.scripts.knowledge_sources import (
    build_project_knowledge_source,
    get_google_embedder_config,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.tools.confluence_tool import ConfluencePublishTool
from crewai_productfeature_planner.tools.jira_tool import JiraCreateIssueTool

logger = get_logger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"

# LLM timeout / retry defaults.
DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the orchestrator config directory."""
    logger.debug("Loading YAML config: %s", filename)
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_tools() -> list:
    """Assemble the toolkit for the orchestrator agent."""
    logger.debug("Assembling Orchestrator toolkit (2 tools)")
    return [
        ConfluencePublishTool(),
        JiraCreateIssueTool(),
    ]


def _build_llm() -> LLM:
    """Build the Gemini LLM for the orchestrator agent.

    Resolution order for model name:
        1. ``ORCHESTRATOR_MODEL`` env var
        2. ``GEMINI_MODEL`` env var
        3. Hard-coded default (``gemini-3-flash-preview``)
    """
    ensure_gemini_env()

    model_name = os.environ.get(
        "ORCHESTRATOR_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get(
        "LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES),
    ))

    logger.info(
        "Orchestrator LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_orchestrator_agent() -> Agent:
    """Create the Orchestrator agent powered by Google Gemini.

    The agent is equipped with Confluence and Jira tools for
    publishing completed PRDs and creating tracking tickets.

    Raises:
        EnvironmentError: When neither ``GOOGLE_API_KEY`` nor
            ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Orchestrator agent requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )

    agent_config = _load_yaml("agent.yaml")["orchestrator"]
    logger.info(
        "Creating Orchestrator agent (role='%s')",
        agent_config["role"].strip(),
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=agent_config["backstory"].strip(),
        llm=_build_llm(),
        tools=_build_tools(),
        verbose=is_verbose(),
        allow_delegation=False,
        knowledge_sources=[build_project_knowledge_source()],
        embedder=get_google_embedder_config(),
    )


def get_task_configs() -> dict:
    """Load task configurations for the Orchestrator agent."""
    logger.debug("Loading Orchestrator task configs")
    return _load_yaml("tasks.yaml")
