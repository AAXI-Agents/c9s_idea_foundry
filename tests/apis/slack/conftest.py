"""Shared fixtures for Slack API tests."""

from unittest.mock import patch

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


@pytest.fixture(autouse=True)
def _clear_session_manager_state():
    """Reset session manager pending-state dicts to prevent cross-test leakage.

    Without this, a test that calls ``mark_pending_create()`` or
    ``mark_pending_memory()`` without consuming the entry leaves
    residual state visible to later tests in the suite.
    """
    import crewai_productfeature_planner.apis.slack.session_manager as sm
    import crewai_productfeature_planner.apis.slack.events_router as er

    with sm._lock:
        sm._pending_project_creates.clear()
        sm._pending_memory_entries.clear()
        sm._pending_project_setup.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    yield
    with sm._lock:
        sm._pending_project_creates.clear()
        sm._pending_memory_entries.clear()
        sm._pending_project_setup.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()


@pytest.fixture(autouse=True)
def _mock_engagement_manager():
    """Prevent real Engagement Manager LLM calls in Slack tests.

    Returns a deterministic response so existing tests that check the
    fallback path (unknown / general_question) still pass.
    """
    with patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent.handle_unknown_intent",
        return_value="I can help you navigate! Try clicking *New Idea* to start a PRD.",
    ):
        yield
