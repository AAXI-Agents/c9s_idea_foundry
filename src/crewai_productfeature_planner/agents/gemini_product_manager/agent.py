"""Gemini-powered Product Manager agent factory and configuration loader.

Mirrors the OpenAI-based Product Manager but uses Google Gemini as the
LLM backend.  Shares the same YAML configs (agent.yaml / tasks.yaml)
for role, goal, backstory, and task definitions.

Environment variables:

* ``GEMINI_PM_MODEL`` — override the model (defaults to ``GEMINI_MODEL``
  then ``gemini-3-flash-preview``).
* ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT`` — at least one must be
  set for Gemini authentication.
"""

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.agents.gemini_utils import (
    DEFAULT_GEMINI_MODEL,
    ensure_gemini_env,
)
from crewai_productfeature_planner.scripts.knowledge_sources import (
    build_prd_knowledge_sources,
    get_google_embedder_config,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.tools.search_tool import create_search_tool
from crewai_productfeature_planner.tools.scrape_tool import create_scrape_tool
from crewai_productfeature_planner.tools.file_read_tool import create_file_read_tool
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool
from crewai_productfeature_planner.tools.directory_read_tool import create_directory_read_tool
from crewai_productfeature_planner.tools.website_search_tool import create_website_search_tool

logger = get_logger(__name__)

# Re-use the same YAML configs as the OpenAI Product Manager.
CONFIG_DIR = Path(__file__).parent.parent / "product_manager" / "config"

# LLM timeout / retry defaults.
DEFAULT_LLM_TIMEOUT = 300       # seconds
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the product_manager config directory."""
    logger.debug("Loading YAML config: %s", filename)
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_tools() -> list:
    """Assemble the full toolkit for the Gemini Product Manager agent."""
    logger.debug("Assembling Gemini Product Manager toolkit (6 tools)")
    return [
        create_search_tool(),
        create_scrape_tool(),
        create_file_read_tool(),
        PRDFileWriteTool(),
        create_directory_read_tool(directory="output/prds"),
        create_website_search_tool(),
    ]


def _build_llm() -> LLM:
    """Build the Gemini LLM for the Product Manager agent.

    Resolution order for model name:
        1. ``GEMINI_PM_MODEL`` env var
        2. ``GEMINI_MODEL`` env var
        3. Hard-coded default (``gemini-3-flash-preview``)

    Timeout and retry behaviour are controlled via:
        - ``LLM_TIMEOUT``      — request timeout in seconds (default 300)
        - ``LLM_MAX_RETRIES``  — number of retries on transient errors (default 3)
    """
    ensure_gemini_env()

    model_name = os.environ.get(
        "GEMINI_PM_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()
    # Prefix with provider when not already qualified.
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info("Gemini Product Manager LLM: %s (timeout=%ds, max_retries=%d)",
                model_name, timeout, max_retries)
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_gemini_product_manager() -> Agent:
    """Create a fully configured Product Manager agent powered by Gemini.

    Raises ``EnvironmentError`` when neither ``GOOGLE_API_KEY`` nor
    ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Gemini Product Manager requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )

    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info("Creating Gemini Product Manager agent (role='%s')",
                agent_config["role"].strip())

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=agent_config["backstory"].strip(),
        llm=_build_llm(),
        tools=_build_tools(),
        verbose=is_verbose(),
        allow_delegation=False,
        knowledge_sources=build_prd_knowledge_sources(),
        embedder=get_google_embedder_config(),
    )


def get_task_configs() -> dict:
    """Load task configurations for the Product Manager."""
    logger.debug("Loading Gemini Product Manager task configs")
    return _load_yaml("tasks.yaml")
