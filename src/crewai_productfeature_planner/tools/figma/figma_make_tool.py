"""CrewAI tool for generating designs via Figma Make.

Wraps the Playwright-based Figma Make browser automation in a CrewAI
``BaseTool`` so agents can submit design prompts and receive the
completed Figma file URL.
"""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.figma._client import (
    FigmaMakeError,
    run_figma_make,
)
from crewai_productfeature_planner.tools.figma._config import (
    has_figma_credentials,
)

logger = get_logger(__name__)


class FigmaMakeInput(BaseModel):
    """Input schema for the Figma Make tool."""

    prompt: str = Field(
        ...,
        description=(
            "A comprehensive, structured design prompt for Figma Make. "
            "Should describe the UI layout, components, colour palette, "
            "typography, and user interactions in enough detail for the "
            "AI to generate a complete, clickable design."
        ),
    )


class FigmaMakeTool(BaseTool):
    """Submit a design prompt to Figma Make and return the file URL.

    The tool drives a headless browser to enter the prompt in Figma
    Make, waits for the design file to be created, and returns the
    Figma file URL.  If a Figma session is not configured, it returns
    an informative message instead of failing.
    """

    name: str = "figma_make_design"
    description: str = (
        "Generate a UI design in Figma using Figma Make AI. "
        "Provide a detailed design prompt and receive the Figma file URL."
    )
    args_schema: Type[BaseModel] = FigmaMakeInput
    # Injected by the caller (e.g. _ux_design.py) before the crew runs.
    _project_config: dict | None = None

    def _run(self, prompt: str) -> str:
        """Execute the Figma Make design generation."""
        project_config = self._project_config
        if not has_figma_credentials(project_config):
            return (
                "FIGMA_SKIPPED: Figma credentials not configured. "
                "Add a Figma API key or OAuth token to the project "
                "config, or run the login script."
            )

        try:
            result = run_figma_make(prompt, project_config=project_config)
            file_url = result.get("file_url", "")
            file_key = result.get("file_key", "")

            if file_url:
                return f"FIGMA_URL:{file_url}"
            if file_key:
                url = f"https://www.figma.com/make/{file_key}"
                return f"FIGMA_URL:{url}"

            return f"FIGMA_ERROR: Design completed but no URL returned: {result}"

        except FigmaMakeError as exc:
            logger.error("[FigmaMakeTool] %s", exc)
            return f"FIGMA_ERROR: {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.error("[FigmaMakeTool] Unexpected error: %s", exc)
            return f"FIGMA_ERROR: Unexpected error: {exc}"
