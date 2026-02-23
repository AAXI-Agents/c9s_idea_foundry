"""Knowledge-source factories for CrewAI agents.

Builds :class:`TextFileKnowledgeSource` instances from the files in the
``knowledge/`` directory at the project root.  These sources are attached
to agents (via ``knowledge_sources``) or crews so that the LLM can
retrieve relevant context during task execution.

Usage::

    from crewai_productfeature_planner.scripts.knowledge_sources import (
        build_prd_knowledge_sources,
        build_user_knowledge_source,
        get_google_embedder_config,
    )

    agent = Agent(
        ...,
        knowledge_sources=build_prd_knowledge_sources(),
        embedder=get_google_embedder_config(),
    )
"""

from __future__ import annotations

import os

from crewai.knowledge.source.text_file_knowledge_source import (
    TextFileKnowledgeSource,
)

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── File paths (relative to the knowledge/ directory) ────────────────

_USER_PREFERENCE_FILE = "user_preference.txt"
_PROJECT_ARCHITECTURE_FILE = "project_architecture.txt"
_PRD_GUIDELINES_FILE = "prd_guidelines.txt"

# All knowledge files for PRD-related agents.
_PRD_KNOWLEDGE_FILES = [
    _USER_PREFERENCE_FILE,
    _PROJECT_ARCHITECTURE_FILE,
    _PRD_GUIDELINES_FILE,
]


# ── Embedder configuration ───────────────────────────────────────────


def get_google_embedder_config() -> dict:
    """Return the Google Generative AI embedder configuration.

    Uses Gemini's ``gemini-embedding-001`` model by default.  The API key
    is read from ``GOOGLE_API_KEY`` (same key used for the Gemini LLM).

    The model can be overridden via the ``KNOWLEDGE_EMBEDDING_MODEL`` env
    var.  Valid values: ``gemini-embedding-001``, ``text-embedding-005``,
    ``text-multilingual-embedding-002``.

    Returns:
        A dict suitable for the ``embedder`` parameter on
        :class:`~crewai.Agent` or :class:`~crewai.Crew`.
    """
    model_name = os.environ.get(
        "KNOWLEDGE_EMBEDDING_MODEL", "gemini-embedding-001",
    )
    config: dict = {"model_name": model_name}

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if api_key:
        config["api_key"] = api_key

    return {
        "provider": "google-generativeai",
        "config": config,
    }


def _has_embedder_credentials() -> bool:
    """Return ``True`` when at least one embedder auth mechanism is set.

    Checks for Google Generative AI key (preferred) or OpenAI key
    (fallback — CrewAI defaults to OpenAI embeddings).
    """
    return bool(
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )


# ── Knowledge-source factories ───────────────────────────────────────


def build_user_knowledge_source() -> TextFileKnowledgeSource:
    """Build a knowledge source from user preferences.

    Returns:
        A :class:`TextFileKnowledgeSource` loaded from
        ``knowledge/user_preference.txt``.
    """
    logger.debug("Building user-preference knowledge source")
    return TextFileKnowledgeSource(file_paths=[_USER_PREFERENCE_FILE])


def build_project_knowledge_source() -> TextFileKnowledgeSource:
    """Build a knowledge source from the project architecture document.

    Returns:
        A :class:`TextFileKnowledgeSource` loaded from
        ``knowledge/project_architecture.txt``.
    """
    logger.debug("Building project-architecture knowledge source")
    return TextFileKnowledgeSource(file_paths=[_PROJECT_ARCHITECTURE_FILE])


def build_prd_guidelines_knowledge_source() -> TextFileKnowledgeSource:
    """Build a knowledge source from the PRD writing guidelines.

    Returns:
        A :class:`TextFileKnowledgeSource` loaded from
        ``knowledge/prd_guidelines.txt``.
    """
    logger.debug("Building PRD-guidelines knowledge source")
    return TextFileKnowledgeSource(file_paths=[_PRD_GUIDELINES_FILE])


def build_prd_knowledge_sources() -> list[TextFileKnowledgeSource]:
    """Build all PRD-related knowledge sources.

    Returns a list of :class:`TextFileKnowledgeSource` instances
    covering user preferences, project architecture, and PRD guidelines.
    Suitable for agents involved in PRD drafting and critique.

    Returns:
        A list of three knowledge sources.
    """
    logger.info(
        "Building PRD knowledge sources (%d files)",
        len(_PRD_KNOWLEDGE_FILES),
    )
    return [
        build_user_knowledge_source(),
        build_project_knowledge_source(),
        build_prd_guidelines_knowledge_source(),
    ]
