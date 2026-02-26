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
    def test_calls_both_publishers(self):
        with (
            patch.object(
                scheduler, "_publish_pending_confluence", return_value=1,
            ) as mock_conf,
            patch.object(
                scheduler, "_create_pending_jira", return_value=0,
            ) as mock_jira,
        ):
            scheduler._run_scan()
        mock_conf.assert_called_once()
        mock_jira.assert_called_once()


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
            {"run_id": "r1", "title": "PRD — test", "content": "# PRD", "output_file": ""},
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
                "crewai_productfeature_planner.mongodb.save_confluence_url",
            ),
        ):
            assert scheduler._publish_pending_confluence() == 1


class TestCreatePendingJira:
    def test_no_credentials(self):
        with patch(
            "crewai_productfeature_planner.orchestrator._helpers._has_jira_credentials",
            return_value=False,
        ):
            assert scheduler._create_pending_jira() == 0

    def test_no_pending(self):
        with (
            patch(
                "crewai_productfeature_planner.orchestrator._helpers._has_jira_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_delivery._discover_pending_deliveries",
                return_value=[],
            ),
        ):
            assert scheduler._create_pending_jira() == 0

    def test_creates_jira_for_pending(self):
        items = [
            {"run_id": "r1", "confluence_done": True, "jira_done": False},
        ]
        with (
            patch(
                "crewai_productfeature_planner.orchestrator._helpers._has_jira_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_delivery._discover_pending_deliveries",
                return_value=items,
            ),
            patch(
                "crewai_productfeature_planner.apis.publishing.service.create_jira_single",
                return_value={"run_id": "r1", "jira_completed": True, "ticket_keys": ["P-1"]},
            ),
        ):
            assert scheduler._create_pending_jira() == 1

    def test_skips_confluence_not_done(self):
        items = [
            {"run_id": "r1", "confluence_done": False, "jira_done": False},
        ]
        with (
            patch(
                "crewai_productfeature_planner.orchestrator._helpers._has_jira_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_delivery._discover_pending_deliveries",
                return_value=items,
            ),
        ):
            assert scheduler._create_pending_jira() == 0
