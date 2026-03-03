"""Shared fixtures for API tests.

Prevents the FastAPI lifespan from running expensive startup tasks
(real agent/LLM creation, background delivery thread) during tests.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True, scope="session")
def _mock_lifespan_heavy_ops():
    """Neutralise background delivery and startup pipeline in the app lifespan.

    **Session-scoped** — these patches are pure safety nets that never
    need to change between tests.  Entering the eight context-managers
    once instead of per-test saves measurable setup time across the
    hundreds of API tests.
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
        patch(
            "crewai_productfeature_planner.apis.publishing.watcher.start_watcher",
            return_value=False,
        ),
        patch(
            "crewai_productfeature_planner.apis.publishing.scheduler.start_scheduler",
            return_value=False,
        ),
        patch(
            "crewai_productfeature_planner.apis.publishing.watcher.stop_watcher",
        ),
        patch(
            "crewai_productfeature_planner.apis.publishing.scheduler.stop_scheduler",
        ),
    ):
        yield
