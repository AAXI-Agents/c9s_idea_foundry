"""Tests for the file watcher module."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.publishing import watcher


@pytest.fixture(autouse=True)
def _reset_watcher_state():
    """Reset module-level state between tests."""
    watcher._processed_files.clear()
    watcher._pending_sizes.clear()
    watcher._stop_event.clear()
    watcher._watcher_thread = None
    yield
    watcher.stop_watcher()


class TestGetPrdsDirectory:
    def test_returns_path(self):
        d = watcher.get_prds_directory()
        assert isinstance(d, Path)
        assert str(d).endswith("output/prds")


class TestGetWatcherStatus:
    def test_not_running(self):
        status = watcher.get_watcher_status()
        assert status["running"] is False

    def test_running(self):
        # Simulate a running thread
        import threading
        t = threading.Thread(target=lambda: time.sleep(10), daemon=True)
        t.start()
        watcher._watcher_thread = t
        watcher._watched_dir = "/tmp/prds"
        status = watcher.get_watcher_status()
        assert status["running"] is True
        assert status["directory"] == "/tmp/prds"
        watcher._stop_event.set()


class TestStartWatcher:
    def test_disabled_by_env(self):
        with patch.dict("os.environ", {"PUBLISH_WATCHER_ENABLED": "false"}):
            assert watcher.start_watcher() is False

    def test_no_credentials(self):
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=False,
            ),
        ):
            assert watcher.start_watcher() is False

    def test_starts_thread(self, tmp_path):
        # Re-import real function since conftest mocks it for lifespan
        from importlib import reload
        import crewai_productfeature_planner.apis.publishing.watcher as w
        reload(w)
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch.object(w, "get_prds_directory", return_value=tmp_path),
        ):
            result = w.start_watcher()
        assert result is True
        assert w._watcher_thread is not None
        assert w._watcher_thread.is_alive()
        w.stop_watcher()

    def test_already_running(self, tmp_path):
        from importlib import reload
        import crewai_productfeature_planner.apis.publishing.watcher as w
        reload(w)
        with (
            patch.dict("os.environ", {}, clear=False),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch.object(w, "get_prds_directory", return_value=tmp_path),
        ):
            w.start_watcher()
            assert w.start_watcher() is False
        w.stop_watcher()


class TestScanForNewFiles:
    def test_detects_new_file(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# PRD\n\nContent here")
        # First scan: records size
        watcher._scan_for_new_files(tmp_path)
        assert str(md.resolve()) not in watcher._processed_files
        assert str(md.resolve()) in watcher._pending_sizes

        # Second scan: size stable → processed
        with patch.object(watcher, "_trigger_publish") as mock_pub:
            watcher._scan_for_new_files(tmp_path)
        assert str(md.resolve()) in watcher._processed_files
        mock_pub.assert_called_once()

    def test_ignores_empty_file(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("")
        watcher._scan_for_new_files(tmp_path)
        assert str(md.resolve()) not in watcher._pending_sizes

    def test_ignores_already_processed(self, tmp_path):
        md = tmp_path / "done.md"
        md.write_text("# Already done")
        watcher._processed_files.add(str(md.resolve()))
        watcher._scan_for_new_files(tmp_path)
        assert str(md.resolve()) not in watcher._pending_sizes

    def test_detects_changing_file(self, tmp_path):
        md = tmp_path / "changing.md"
        md.write_text("# V1")
        watcher._scan_for_new_files(tmp_path)
        # Change file size
        md.write_text("# V2 — now with more content")
        with patch.object(watcher, "_trigger_publish") as mock_pub:
            watcher._scan_for_new_files(tmp_path)
        # Should not trigger — size changed
        mock_pub.assert_not_called()
        # Now stable
        with patch.object(watcher, "_trigger_publish") as mock_pub:
            watcher._scan_for_new_files(tmp_path)
        mock_pub.assert_called_once()


class TestTriggerPublish:
    def test_publishes_file(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# PRD content")
        with (
            patch(
                "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence",
                return_value={"url": "https://example.com/page/1", "page_id": "1", "action": "created"},
            ) as mock_pub,
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record",
            ),
        ):
            watcher._trigger_publish(md)
        mock_pub.assert_called_once()

    def test_skips_empty_file(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("   ")
        with patch(
            "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence",
        ) as mock_pub:
            watcher._trigger_publish(md)
        mock_pub.assert_not_called()

    def test_handles_publish_error(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# PRD content")
        with patch(
            "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence",
            side_effect=RuntimeError("API error"),
        ):
            # Should not raise
            watcher._trigger_publish(md)
