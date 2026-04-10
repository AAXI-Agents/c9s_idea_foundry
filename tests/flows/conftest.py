"""Shared fixtures for flow tests.

Mocks LLM builders that would otherwise construct expensive
``GeminiCompletion`` / ``LLM`` objects during agent creation
inside flow tests.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _mock_flow_llm_builders():
    """Stub every agent LLM builder used in flow tests."""
    with (
        patch(
            "crewai_productfeature_planner.agents.ux_designer.agent._build_llm",
            return_value="gemini/gemini-3-flash-preview",
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent._build_llm",
            return_value="gemini/gemini-3-flash-preview",
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent._build_critic_llm",
            return_value="gemini/gemini-3-flash-preview",
        ),
    ):
        yield
