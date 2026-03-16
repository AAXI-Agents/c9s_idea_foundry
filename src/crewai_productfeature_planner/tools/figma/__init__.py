"""Figma Make integration — AI-powered design generation.

Provides a CrewAI tool that drives the Figma Make web UI via Playwright
to generate designs from prompts and return the Figma file URL.
Also provides a REST API client for Figma project / file operations.

Authentication (in priority order):

1. **Project config** — ``figma_api_key`` and/or ``figma_oauth_token``
   stored in the ``projectConfig`` MongoDB collection.
2. **Playwright session** — stored at ``FIGMA_SESSION_DIR/state.json``.

Environment variables (fallbacks):

* ``FIGMA_SESSION_DIR``    — Playwright session state directory
* ``FIGMA_MAKE_TIMEOUT``   — Max wait time for generation (seconds)
* ``FIGMA_HEADLESS``       — Run browser headless (true|false)
* ``FIGMA_CLIENT_ID``      — OAuth2 app client ID
* ``FIGMA_CLIENT_SECRET``  — OAuth2 app client secret
"""

from crewai_productfeature_planner.tools.figma.figma_make_tool import (
    FigmaMakeTool,
)

__all__ = ["FigmaMakeTool"]
