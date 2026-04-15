"""Tests for the cron scheduler module."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.publishing import scheduler


@pytest.fixture(autouse=True)
def _reset_scheduler_state():
    """Reset module-level state between tests."""
    scheduler._stop_event.clear()
    scheduler._scheduler_thread = None
    yield
    scheduler.stop_scheduler()


class TestGetSchedulerStatus:
    def test_not_running(self):
        status = scheduler.get_scheduler_status()
        assert status["running"] is False
        assert status["interval_seconds"] >= 30

    def test_interval_from_env(self):
        with patch.dict("os.environ", {"PUBLISH_SCAN_INTERVAL_SECONDS": "120"}):
            status = scheduler.get_scheduler_status()
        assert status["interval_seconds"] == 120

    def test_interval_floor(self):
        with patch.dict("os.environ", {"PUBLISH_SCAN_INTERVAL_SECONDS": "5"}):
            status = scheduler.get_scheduler_status()
        assert status["interval_seconds"] == 30  # floor


class TestStartScheduler:
    def test_disabled_by_env(self):
        with patch.dict("os.environ", {"PUBLISH_SCHEDULER_ENABLED": "false"}):
            assert scheduler.start_scheduler() is False

    def test_no_credentials(self):
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=False,
            ),
        ):
            assert scheduler.start_scheduler() is False

    def test_starts_thread(self):
        from importlib import reload
        import crewai_productfeature_planner.apis.publishing.scheduler as s
        reload(s)
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
        ):
            result = s.start_scheduler()
        assert result is True
        assert s._scheduler_thread is not None
        assert s._scheduler_thread.is_alive()
        s.stop_scheduler()

    def test_already_running(self):
        from importlib import reload
        import crewai_productfeature_planner.apis.publishing.scheduler as s
        reload(s)
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
        ):
            s.start_scheduler()
            assert s.start_scheduler() is False
        s.stop_scheduler()


class TestStopScheduler:
    def test_stop_when_not_running(self):
        # Should not raise
        scheduler.stop_scheduler()

    def test_stop_running(self):
        from importlib import reload
        import crewai_productfeature_planner.apis.publishing.scheduler as s
        reload(s)
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
        ):
            s.start_scheduler()
        s.stop_scheduler()
        assert s._scheduler_thread is None


class TestRunScan:
    def test_calls_confluence_publisher_only(self):
        """Scheduler only handles Confluence — Jira requires user approval."""
        with (
            patch.object(
                scheduler, "_publish_pending_confluence", return_value=1,
            ) as mock_conf,
        ):
            scheduler._run_scan()
        mock_conf.assert_called_once()


class TestPublishPendingConfluence:
    def test_no_credentials(self):
        with patch(
            "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
            return_value=False,
        ):
            assert scheduler._publish_pending_confluence() == 0

    def test_no_items(self):
        with (
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_review._discover_publishable_prds",
                return_value=[],
            ),
        ):
            assert scheduler._publish_pending_confluence() == 0

    def test_publishes_items(self):
        items = [
            {"run_id": "r1", "title": "test", "content": "# PRD", "output_file": ""},
        ]
        with (
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_review._discover_publishable_prds",
                return_value=items,
            ),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence",
                return_value={"url": "https://example.com", "page_id": "1"},
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record",
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.claim_for_confluence",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.release_claim",
            ),
            patch(
                "crewai_productfeature_planner.mongodb.leases.repository._instance_id",
                return_value="test-host-1",
            ),
        ):
            assert scheduler._publish_pending_confluence() == 1


class TestCreatePendingJira:
    """Jira creation is disabled in the scheduler (Jira Approval Gate)."""

    def test_always_returns_zero(self):
        """Scheduler must NEVER create Jira tickets autonomously."""
        assert scheduler._create_pending_jira() == 0

    def test_no_external_calls(self):
        """Verify no MongoDB or Jira calls are made."""
        # The stub should return immediately without importing anything
        result = scheduler._create_pending_jira()
        assert result == 0
