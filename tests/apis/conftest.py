"""Shared fixtures for API tests.

Prevents the FastAPI lifespan from running expensive startup tasks
(real agent/LLM creation, background delivery thread) during tests.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _mock_lifespan_heavy_ops():
    """Neutralise background delivery and startup pipeline in the app lifespan.

    The lifespan handler imports and runs ``build_startup_pipeline`` and
    launches ``_run_startup_delivery_background`` in a daemon thread.
    Without mocking, these create real CrewAI Agent/LLM objects that take
    ~30s+ per TestClient instantiation.
    """
    with (
        patch(
            "crewai_productfeature_planner.components.startup._run_startup_delivery_background",
        ),
        patch(
            "crewai_productfeature_planner.components.startup._kill_stale_crew_processes",
            return_value=0,
        ),
        patch(
            "crewai_productfeature_planner.components.startup._generate_missing_outputs",
            return_value=0,
        ),
        patch(
            "crewai_productfeature_planner.orchestrator.stages.build_startup_pipeline",
        ),
    ):
        yield
