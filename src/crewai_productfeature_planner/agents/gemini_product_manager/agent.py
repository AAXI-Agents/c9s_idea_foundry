"""Gemini-powered Product Manager agent factory.

Creates a Product Manager agent that uses Google Gemini instead of
OpenAI.  Task configurations are shared with the OpenAI Product
Manager — only the LLM backend differs.

Two authentication modes are supported (at least one is required):

1. **Google API key** — set ``GOOGLE_API_KEY`` with a key from
   `Google AI Studio <https://aistudio.google.com/apikey>`_.  This is
   the simplest option and uses the Gemini API directly.

2. **Vertex AI (ADC)** — set ``GOOGLE_CLOUD_PROJECT`` to your GCP
   project ID and authenticate via
   ``gcloud auth application-default login`` (or
   ``GOOGLE_APPLICATION_CREDENTIALS``).  ``GOOGLE_CLOUD_LOCATION``
   defaults to ``asia-southeast1``.

If *both* are set, the Google API key takes precedence.

Optional ``GEMINI_MODEL`` env var overrides the default model
(default: ``gemini-3-flash-preview``).
"""

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.agents.product_manager import get_task_configs  # noqa: F401 — re-export
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

# Default Gemini model.  Override via GEMINI_MODEL env var.
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# Default Vertex AI region when GOOGLE_CLOUD_LOCATION is not set.
DEFAULT_VERTEX_LOCATION = "asia-southeast1"

# LLM timeout / retry defaults — Gemini Flash models are typically faster
# than OpenAI reasoning models, so a shorter timeout is fine.
DEFAULT_LLM_TIMEOUT = 300      # seconds
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the Gemini agent's config directory."""
    logger.debug("Loading YAML config: %s", filename)
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _ensure_gemini_env() -> None:
    """Configure environment for the chosen authentication mode.

    * If ``GOOGLE_CLOUD_PROJECT`` is set, enables Vertex AI by setting
      ``GOOGLE_GENAI_USE_VERTEXAI=true`` and defaulting
      ``GOOGLE_CLOUD_LOCATION``.
    * If only ``GOOGLE_API_KEY`` is set, the native provider uses the
      Gemini API (Google AI Studio) — no extra env vars needed.
    """
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", DEFAULT_VERTEX_LOCATION)


def _build_gemini_llm() -> LLM:
    """Build the Gemini LLM for the Product Manager agent.

    Resolution order for model name:
        1. ``GEMINI_MODEL`` env var
        2. ``DEFAULT_GEMINI_MODEL`` hard-coded fallback

    Requires either ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT``.
    """
    _ensure_gemini_env()

    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    # Prefix with provider when not already qualified.
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info("Gemini Product Manager LLM: %s (timeout=%ds, max_retries=%d)",
                model_name, timeout, max_retries)
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_gemini_product_manager() -> Agent:
    """Create a Product Manager agent powered by Google Gemini.

    Uses the same role / goal / backstory as the OpenAI PM but routes
    inference through Google Gemini.  Task configurations are shared.

    Raises if neither ``GOOGLE_API_KEY`` nor ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required to create "
            "the Gemini Product Manager agent.  Set at least one in your "
            "environment or .env file."
        )

    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info("Creating Gemini Product Manager agent (role='%s')",
                agent_config["role"].strip())

    # Gemini agent shares the same tools as the OpenAI PM (minus tools
    # that require OpenAI embeddings).  For simplicity, import the
    # OpenAI PM's tool builder.
    from crewai_productfeature_planner.agents.product_manager.agent import _build_tools

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=agent_config["backstory"].strip(),
        llm=_build_gemini_llm(),
        tools=_build_tools(),
        verbose=True,
        allow_delegation=False,
    )
