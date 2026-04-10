"""Shared fixtures for agent tests.

Prevents real LLM object construction by mocking the ``_build_*_llm``
functions that would otherwise create ``GeminiCompletion`` instances
(~0.1–0.2 s each).  Individual tests that need the real builder can
override the fixture or patch more specifically.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _mock_agent_llm_builders():
    """Return lightweight stubs from every agent LLM builder.

    Avoids constructing real ``GeminiCompletion`` objects for every
    test that calls ``create_idea_refiner()`` or
    ``create_requirements_breakdown_agent()`` without manually
    wrapping them in ``with _mock_build_*_llm():``.
    """
    with (
        patch(
            "crewai_productfeature_planner.agents.idea_refiner.agent._build_refiner_llm",
            return_value="gemini/gemini-3-flash-preview",
        ),
        patch(
            "crewai_productfeature_planner.agents.requirements_breakdown.agent._build_breakdown_llm",
            return_value="gemini/gemini-3-flash-preview",
        ),
        patch(
            "crewai_productfeature_planner.agents.engagement_manager.agent._build_engagement_llm",
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
        patch(
            "crewai_productfeature_planner.agents.ux_designer.agent._build_llm",
            return_value="gemini/gemini-3-flash-preview",
        ),
    ):
        yield
