"""CrewAI tool for generating designs via Figma Make.

Wraps the Figma Make API client in a CrewAI ``BaseTool`` so agents can
submit design prompts and receive the completed Figma file URL.
"""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.figma._client import (
    FigmaMakeError,
    poll_figma_make,
    submit_figma_make,
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

    The tool submits the prompt, polls until the design is generated,
    and returns the Figma file URL.  If Figma credentials are not
    configured, it returns an informative message instead of failing.
    """

    name: str = "figma_make_design"
    description: str = (
        "Generate a UI design in Figma using Figma Make AI. "
        "Provide a detailed design prompt and receive the Figma file URL."
    )
    args_schema: Type[BaseModel] = FigmaMakeInput

    def _run(self, prompt: str) -> str:
        """Execute the Figma Make design generation."""
        if not has_figma_credentials():
            return (
                "FIGMA_SKIPPED: Figma credentials not configured. "
                "Set FIGMA_ACCESS_TOKEN to enable design generation."
            )

        try:
            # Submit the design prompt
            submit_resp = submit_figma_make(prompt)
            request_id = submit_resp.get("request_id")
            if not request_id:
                return f"FIGMA_ERROR: No request_id in response: {submit_resp}"

            # Poll until completion
            result = poll_figma_make(request_id)
            file_url = result.get("file_url", "")
            file_key = result.get("file_key", "")

            if file_url:
                return f"FIGMA_URL:{file_url}"
            if file_key:
                url = f"https://www.figma.com/design/{file_key}"
                return f"FIGMA_URL:{url}"

            return f"FIGMA_ERROR: Design completed but no URL returned: {result}"

        except FigmaMakeError as exc:
            logger.error("[FigmaMakeTool] %s", exc)
            return f"FIGMA_ERROR: {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.error("[FigmaMakeTool] Unexpected error: %s", exc)
            return f"FIGMA_ERROR: Unexpected error: {exc}"
