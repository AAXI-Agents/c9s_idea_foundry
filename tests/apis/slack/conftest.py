"""Shared fixtures for Slack API tests."""

import pytest


@pytest.fixture(autouse=True)
def _clear_interactive_runs():
    """Reset interactive run state between tests to prevent leakage."""
    from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
        _interactive_runs,
        _manual_refinement_text,
        _queued_feedback,
    )
    _interactive_runs.clear()
    _manual_refinement_text.clear()
    _queued_feedback.clear()
    yield
    _interactive_runs.clear()
    _manual_refinement_text.clear()
    _queued_feedback.clear()
