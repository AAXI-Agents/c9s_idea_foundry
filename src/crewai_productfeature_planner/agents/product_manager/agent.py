"""Product Manager agent factory and configuration loader.

Supports both OpenAI and Gemini LLM backends through a single unified
factory.  The ``provider`` parameter (``"openai"`` or ``"gemini"``)
controls which LLM is used:

* **openai** — uses ``OPENAI_RESEARCH_MODEL`` env var (default from
  ``DEFAULT_OPENAI_RESEARCH_MODEL``).
* **gemini** — uses ``GEMINI_PM_MODEL`` / ``GEMINI_RESEARCH_MODEL``
  env var (default from ``DEFAULT_GEMINI_RESEARCH_MODEL``).  Requires
  ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT``.

The Product Manager performs deep-thinking tasks (PRD section drafting,
critique, refinement) and therefore uses the **research** model tier.
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
from crewai_productfeature_planner.scripts.knowledge_sources import (
    build_prd_knowledge_sources,
    get_google_embedder_config,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory
from crewai_productfeature_planner.tools.search_tool import create_search_tool
from crewai_productfeature_planner.tools.scrape_tool import create_scrape_tool
from crewai_productfeature_planner.tools.file_read_tool import create_file_read_tool
from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool
from crewai_productfeature_planner.tools.directory_read_tool import create_directory_read_tool
from crewai_productfeature_planner.tools.website_search_tool import create_website_search_tool

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

# Recognised LLM provider identifiers.
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"

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


def _build_llm(provider: str = PROVIDER_OPENAI) -> LLM:
    """Build the LLM for the Product Manager agent.

    Uses the **research** model tier because PRD section drafting,
    critique, and refinement require deep reasoning.

    Parameters
    ----------
    provider:
        ``"openai"`` or ``"gemini"``.

    **OpenAI** resolution order for model name:
        1. ``OPENAI_RESEARCH_MODEL`` env var
        2. ``DEFAULT_OPENAI_RESEARCH_MODEL`` (hard-coded fallback — ``o3``)

    **Gemini** resolution order for model name:
        1. ``GEMINI_PM_MODEL`` env var
        2. ``GEMINI_RESEARCH_MODEL`` env var
        3. ``DEFAULT_GEMINI_RESEARCH_MODEL`` (hard-coded fallback — ``gemini-3.1-pro-preview``)

    Timeout and retry behaviour are controlled via:
        - ``LLM_TIMEOUT``      — request timeout in seconds (default 300)
        - ``LLM_MAX_RETRIES``  — number of retries on transient errors (default 3)
    """
    if provider == PROVIDER_GEMINI:
        ensure_gemini_env()
        model_name = os.environ.get(
            "GEMINI_PM_MODEL",
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

    logger.info("Product Manager LLM (%s): %s (timeout=%ds, max_retries=%d)",
                provider, model_name, timeout, max_retries)
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_product_manager(
    provider: str = PROVIDER_OPENAI,
    project_id: str | None = None,
) -> Agent:
    """Create a fully configured Product Manager agent.

    Parameters
    ----------
    provider:
        LLM backend — ``"openai"`` (default) or ``"gemini"``.
    project_id:
        Optional project identifier.  When provided, the agent's
        backstory is enriched with project-level memory entries
        (guardrails, knowledge, tech stack) from MongoDB.

    Raises
    ------
    EnvironmentError
        When *provider* is ``"gemini"`` and neither ``GOOGLE_API_KEY``
        nor ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    if provider == PROVIDER_GEMINI:
        has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
        has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if not has_api_key and not has_project:
            raise EnvironmentError(
                "Gemini Product Manager requires GOOGLE_API_KEY or "
                "GOOGLE_CLOUD_PROJECT to be set."
            )

    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info("Creating Product Manager agent (provider='%s', role='%s')",
                provider, agent_config["role"].strip())

    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_llm(provider=provider),
        tools=_build_tools(),
        verbose=is_verbose(),
        allow_delegation=False,
        reasoning=True,
        max_reasoning_attempts=3,
        knowledge_sources=build_prd_knowledge_sources(),
        embedder=get_google_embedder_config(),
    )


def get_task_configs() -> dict:
    """Load task configurations for the Product Manager."""
    logger.debug("Loading Product Manager task configs")
    return _load_yaml("tasks.yaml")
