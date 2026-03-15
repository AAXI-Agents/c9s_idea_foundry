"""Figma Make integration — AI-powered design generation.

Provides a CrewAI tool that submits design prompts to the Figma Make
API and returns the generated Figma file URL.

Environment variables:

* ``FIGMA_ACCESS_TOKEN`` — Personal access token or OAuth2 token
* ``FIGMA_TEAM_ID``      — Team to create design files in
"""

from crewai_productfeature_planner.tools.figma.figma_make_tool import (
    FigmaMakeTool,
)

__all__ = ["FigmaMakeTool"]
