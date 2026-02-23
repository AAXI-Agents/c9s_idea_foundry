"""Shared Gemini LLM configuration utilities.

Used by agents that need Gemini-specific environment setup and
model defaults (e.g. Idea Refiner, Requirements Breakdown).
"""

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Default Gemini model.  Override via GEMINI_MODEL env var.
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

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
