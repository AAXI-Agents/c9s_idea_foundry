"""Shared LLM configuration utilities and model defaults.

Provides default model names for both basic (fast) and research
(deep-thinking) tasks across Gemini and OpenAI providers:

* **Basic models** (``GEMINI_MODEL`` / ``OPENAI_MODEL``) — used for
  orchestration, intent classification, next-step prediction, and
  other lightweight interactions.
* **Research models** (``GEMINI_RESEARCH_MODEL`` / ``OPENAI_RESEARCH_MODEL``)
  — used for complex tasks: idea refinement iterations, requirements
  breakdown, PRD section drafting, Confluence generation, and Jira
  ticket creation.

Also handles Gemini-specific environment setup (Vertex AI).
"""

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Default Gemini model.  Override via GEMINI_MODEL env var.
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# Default Gemini research model for complex/deep-thinking tasks.
# Override via GEMINI_RESEARCH_MODEL env var.
DEFAULT_GEMINI_RESEARCH_MODEL = "gemini-3.1-pro-preview"

# Default OpenAI research model for complex/deep-thinking tasks.
# Override via OPENAI_RESEARCH_MODEL env var.
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
