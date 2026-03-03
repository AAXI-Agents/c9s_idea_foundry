"""Tests for orchestrator._confluence — Confluence publish stage."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.flows.prd_flow import PRDFlow
from crewai_productfeature_planner.orchestrator.orchestrator import StageResult
from crewai_productfeature_planner.orchestrator._confluence import (
    build_confluence_publish_stage,
)


class TestConfluencePublishStage:

    @pytest.fixture()
    def _confluence_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

    def test_stage_name(self):
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert stage.name == "confluence_publish"

    def test_stage_description(self):
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert "confluence" in stage.description.lower()

    def test_skips_without_confluence_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_skips_without_gemini_credentials(self, monkeypatch, _confluence_env):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_already_published(self, _confluence_env):
        flow = PRDFlow()
        flow.state.confluence_url = "https://already.published/page"
        flow.state.final_prd = "# PRD"
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_no_final_prd(self, _confluence_env):
        flow = PRDFlow()
        flow.state.final_prd = ""
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_does_not_skip_with_credentials_and_content(self, _confluence_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow.state.confluence_url = ""
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is False

    @patch("crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence")
    def test_run_publishes(self, mock_publish, _confluence_env):
        mock_publish.return_value = {
            "action": "created",
            "page_id": "12345",
            "url": "https://example.atlassian.net/wiki/pages/12345",
        }
        flow = PRDFlow()
        flow.state.idea = "Dark mode feature"
        flow.state.final_prd = "# PRD\nDark mode"
        flow.state.run_id = "run-1"
        stage = build_confluence_publish_stage(flow)

        result = stage.run()

        assert "created" in result.output
        assert "12345" in result.output
        mock_publish.assert_called_once()

    @patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db")
    def test_apply_updates_state(self, mock_get_db, _confluence_env):
        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        flow = PRDFlow()
        flow.state.run_id = "run-1"
        stage = build_confluence_publish_stage(flow)

        result = StageResult(
            output="created|12345|https://example.atlassian.net/wiki/pages/12345"
        )
        stage.apply(result)

        assert flow.state.confluence_url == "https://example.atlassian.net/wiki/pages/12345"
