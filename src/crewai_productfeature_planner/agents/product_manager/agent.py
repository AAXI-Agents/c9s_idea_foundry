"""Product Manager agent factory and configuration loader."""

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

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
CONFIG_DIR = Path(__file__).parent / "config"

# Default reasoning model for the Product Manager agent.
# Override via OPENAI_MODEL env var.
DEFAULT_OPENAI_MODEL = "o3"

# LLM timeout / retry defaults.  Reasoning models (o3) can take 60-120 s;
# a generous default avoids premature timeouts while still failing eventually.
DEFAULT_LLM_TIMEOUT = 300      # seconds
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the agent's config directory."""
    logger.debug("Loading YAML config: %s", filename)
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_tools() -> list:
    """Assemble the full toolkit for the Product Manager agent.

    Tools included:
        - SerperDevTool: Google search for market & competitor research
        - ScrapeWebsiteTool: Extract content from competitor/product pages
        - FileReadTool: Read knowledge files, existing PRDs, reference docs
        - PRDFileWriteTool: Save PRD drafts with automatic versioning
        - DirectoryReadTool: List output and knowledge directories
        - WebsiteSearchTool: RAG-based semantic search within a website
    """
    logger.debug("Assembling Product Manager toolkit (6 tools)")
    return [
        create_search_tool(),
        create_scrape_tool(),
        create_file_read_tool(),
        PRDFileWriteTool(),
        create_directory_read_tool(directory="output/prds"),
        create_website_search_tool(),
    ]


def _build_llm() -> LLM:
    """Build the OpenAI LLM for the Product Manager agent.

    Resolution order for model name:
        1. ``OPENAI_MODEL`` env var  (project-level OpenAI model)
        2. ``DEFAULT_OPENAI_MODEL``  (hard-coded fallback — o3)

    Timeout and retry behaviour are controlled via:
        - ``LLM_TIMEOUT``      — request timeout in seconds (default 300)
        - ``LLM_MAX_RETRIES``  — number of retries on transient errors (default 3)
    """
    model_name = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
    # Prefix with provider when not already qualified.
    if "/" not in model_name:
        model_name = f"openai/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info("Product Manager LLM: %s (timeout=%ds, max_retries=%d)",
                model_name, timeout, max_retries)
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_product_manager() -> Agent:
    """Create a fully configured Product Manager agent with tools."""
    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info("Creating Product Manager agent (role='%s')",
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
    logger.debug("Loading Product Manager task configs")
    return _load_yaml("tasks.yaml")
