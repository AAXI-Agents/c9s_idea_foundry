"""Tests for orchestrator._jira — Jira ticketing stage."""

import pytest
from unittest.mock import patch, MagicMock

from crewai_productfeature_planner.flows.prd_flow import PRDFlow
from crewai_productfeature_planner.orchestrator.orchestrator import StageResult
from crewai_productfeature_planner.orchestrator._jira import (
    _extract_issue_keys,
    build_jira_ticketing_stage,
    build_jira_epics_stories_stage,
    build_jira_subtasks_stage,
)


# ── _extract_issue_keys helper ──────────────────────────────────────


class TestExtractIssueKeys:

    def test_basic(self):
        assert _extract_issue_keys("Created PRD-42 and PRD-43") == ["PRD-42", "PRD-43"]

    def test_empty(self):
        assert _extract_issue_keys("no keys here") == []

    def test_mixed_text(self):
        keys = _extract_issue_keys(
            "Epic: PRD-100\nStory: TEST-5, also CJT-999"
        )
        assert keys == ["PRD-100", "TEST-5", "CJT-999"]


# ── Jira Ticketing Stage ────────────────────────────────────────────


class TestJiraTicketingStage:

    @pytest.fixture()
    def _jira_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

    def test_stage_name(self):
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert stage.name == "jira_ticketing"

    def test_stage_description(self):
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert "jira" in stage.description.lower()

    def test_skips_without_jira_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_skips_without_gemini_credentials(self, monkeypatch, _jira_env):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_no_final_prd(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = ""
        flow.state.confluence_url = "https://example.atlassian.net/wiki/page/1"
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_confluence_url_missing(self, _jira_env):
        """Jira must wait until Confluence publish succeeds."""
        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow.state.confluence_url = ""
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_does_not_skip_with_credentials_prd_and_confluence(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow.state.confluence_url = "https://example.atlassian.net/wiki/page/1"
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is False

    def test_apply_updates_state(self, _jira_env):
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)

        result = StageResult(
            output="Epic: key=PRD-100\nStories: PRD-101, PRD-102"
        )
        stage.apply(result)

        assert flow.state.jira_output == "Epic: key=PRD-100\nStories: PRD-101, PRD-102"


class TestEpicsStoriesStageApplyPersistence:
    """Verify build_jira_epics_stories_stage._apply persists output to MongoDB."""

    @pytest.fixture()
    def _jira_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

    def test_apply_persists_epics_stories_output(self, _jira_env):
        """_apply must call save_jira_epics_stories_output with the crew output."""
        flow = PRDFlow()
        flow.state.run_id = "run-persist-test"
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "skeleton_approved"
        flow.state.jira_skeleton = "## Epic 1"

        stage = build_jira_epics_stories_stage(flow, require_confluence=False)
        result = StageResult(output="Epic: PRD-100\nStories: PRD-101, PRD-102")

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas.repository.save_jira_epics_stories_output"
        ) as mock_save, patch(
            "crewai_productfeature_planner.orchestrator._jira._persist_jira_phase"
        ):
            stage.apply(result)

        mock_save.assert_called_once_with(
            "run-persist-test", "Epic: PRD-100\nStories: PRD-101, PRD-102",
        )
        assert flow.state.jira_epics_stories_output == "Epic: PRD-100\nStories: PRD-101, PRD-102"
        assert flow.state.jira_phase == "epics_stories_done"

    def test_apply_survives_save_failure(self, _jira_env):
        """_apply must not crash when save_jira_epics_stories_output raises."""
        flow = PRDFlow()
        flow.state.run_id = "run-fail-test"
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "skeleton_approved"
        flow.state.jira_skeleton = "## Epic 1"

        stage = build_jira_epics_stories_stage(flow, require_confluence=False)
        result = StageResult(output="Epic: PRD-200")

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas.repository.save_jira_epics_stories_output",
            side_effect=RuntimeError("DB down"),
        ), patch(
            "crewai_productfeature_planner.orchestrator._jira._persist_jira_phase"
        ):
            stage.apply(result)  # must not raise

        assert flow.state.jira_epics_stories_output == "Epic: PRD-200"


class TestSubtasksStageResume:
    """Verify the subtasks stage can resume using persisted epics_stories_output."""

    @pytest.fixture()
    def _jira_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

    def test_subtasks_skips_without_epics_output(self, _jira_env):
        """Should skip when jira_epics_stories_output is empty."""
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "subtasks_ready"
        flow.state.jira_epics_stories_output = ""

        stage = build_jira_subtasks_stage(flow, require_confluence=False)
        assert stage.should_skip() is True

    def test_subtasks_does_not_skip_with_restored_output(self, _jira_env):
        """Should NOT skip when jira_epics_stories_output has been restored."""
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "subtasks_ready"
        flow.state.jira_epics_stories_output = "Epic: PRD-100\nStories: PRD-101"

        stage = build_jira_subtasks_stage(flow, require_confluence=False)
        assert stage.should_skip() is False
