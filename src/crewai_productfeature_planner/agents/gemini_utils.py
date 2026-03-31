"""Shared LLM configuration utilities and model defaults.

The ``DEFAULT_*`` constants provide fallback model names used when
the corresponding environment variable is absent.  Every call site
resolves the model via ``os.environ.get("<ENV_VAR>", DEFAULT_*)``,
so the env var always takes precedence at runtime.

Environment variables (checked at runtime, not import time):

* ``GEMINI_MODEL`` — basic/fast Gemini model (fallback: ``gemini-3-flash-preview``)
* ``GEMINI_RESEARCH_MODEL`` — deep-reasoning Gemini model (fallback: ``gemini-3.1-pro-preview``)
* ``OPENAI_MODEL`` — basic/fast OpenAI model (fallback: ``gpt-4.1-mini``)
* ``OPENAI_RESEARCH_MODEL`` — deep-reasoning OpenAI model (fallback: ``o3``)

Also handles Gemini-specific environment setup (Vertex AI).
"""

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Model defaults — pure fallback values (no env lookup at import time).
#
# Every consumer resolves the active model at runtime via
# os.environ.get("<ENV_VAR>", DEFAULT_*).
# ---------------------------------------------------------------------------

#: Basic Gemini model fallback.  Override via ``GEMINI_MODEL`` env var.
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

#: Research Gemini model fallback.  Override via ``GEMINI_RESEARCH_MODEL`` env var.
DEFAULT_GEMINI_RESEARCH_MODEL = "gemini-3.1-pro-preview"

#: Basic OpenAI model fallback.  Override via ``OPENAI_MODEL`` env var.
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

#: Research OpenAI model fallback.  Override via ``OPENAI_RESEARCH_MODEL`` env var.
DEFAULT_OPENAI_RESEARCH_MODEL = "o3"

# Default Vertex AI region when GOOGLE_CLOUD_LOCATION is not set.
DEFAULT_VERTEX_LOCATION = "asia-southeast1"


def ensure_gemini_env() -> None:
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
