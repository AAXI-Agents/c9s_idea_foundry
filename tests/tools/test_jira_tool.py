"""Tests for the Atlassian Jira ticket creation tool."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.tools.jira_tool import (
    JiraCreateIssueTool,
    _build_auth_header,
    _get_jira_env,
    _has_jira_credentials,
    create_jira_issue,
)


# ── _get_jira_env ────────────────────────────────────────────────────


class TestGetJiraEnv:

    def test_all_vars_set(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")

        env = _get_jira_env()
        assert env["base_url"] == "https://example.atlassian.net"
        assert env["project_key"] == "PRD"
        assert env["username"] == "user@example.com"
        assert env["api_token"] == "secret"

    def test_missing_base_url(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")

        with pytest.raises(EnvironmentError, match="JIRA_BASE_URL"):
            _get_jira_env()

    def test_missing_all_vars(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("JIRA_USERNAME", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        with pytest.raises(EnvironmentError):
            _get_jira_env()

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net/")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")

        env = _get_jira_env()
        assert env["base_url"] == "https://example.atlassian.net"


# ── _has_jira_credentials ────────────────────────────────────────────


class TestHasJiraCredentials:

    def test_all_set(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")
        assert _has_jira_credentials() is True

    def test_missing(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("JIRA_USERNAME", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        assert _has_jira_credentials() is False


# ── _build_auth_header ───────────────────────────────────────────────


def test_build_auth_header():
    header = _build_auth_header("admin@company.io", "tok123")
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header.split(" ")[1]).decode()
    assert decoded == "admin@company.io:tok123"


# ── create_jira_issue ────────────────────────────────────────────────


class TestCreateJiraIssue:

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")

    @patch("crewai_productfeature_planner.tools.jira_tool._jira_request")
    def test_creates_story(self, mock_request):
        mock_request.return_value = {"key": "PRD-101", "id": "10101"}

        result = create_jira_issue(
            summary="Add dark mode",
            description="Implement dark mode toggle",
            run_id="run-1",
        )

        assert result["issue_key"] == "PRD-101"
        assert result["issue_id"] == "10101"
        assert "PRD-101" in result["url"]
        mock_request.assert_called_once()
        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["issuetype"]["name"] == "Story"
        assert payload["fields"]["summary"] == "Add dark mode"
        assert payload["fields"]["description"] == "Implement dark mode toggle"

    @patch("crewai_productfeature_planner.tools.jira_tool._jira_request")
    def test_creates_epic(self, mock_request):
        mock_request.return_value = {"key": "PRD-200", "id": "20200"}

        result = create_jira_issue(
            summary="PRD — Dark Mode Feature",
            issue_type="Epic",
        )

        assert result["issue_key"] == "PRD-200"
        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["issuetype"]["name"] == "Epic"

    @patch("crewai_productfeature_planner.tools.jira_tool._jira_request")
    def test_epic_key_sets_parent(self, mock_request):
        mock_request.return_value = {"key": "PRD-301", "id": "30301"}

        create_jira_issue(
            summary="Story under epic",
            epic_key="PRD-200",
        )

        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["parent"] == {"key": "PRD-200"}

    @patch("crewai_productfeature_planner.tools.jira_tool._jira_request")
    def test_labels_and_priority(self, mock_request):
        mock_request.return_value = {"key": "PRD-401", "id": "40401"}

        create_jira_issue(
            summary="With labels",
            labels=["prd", "auto-generated"],
            priority="High",
        )

        payload = mock_request.call_args[1]["data"]
        assert payload["fields"]["labels"] == ["prd", "auto-generated"]
        assert payload["fields"]["priority"] == {"name": "High"}

    @patch("crewai_productfeature_planner.tools.jira_tool._jira_request")
    def test_no_description_omitted(self, mock_request):
        mock_request.return_value = {"key": "PRD-501", "id": "50501"}

        create_jira_issue(summary="No desc")

        payload = mock_request.call_args[1]["data"]
        assert "description" not in payload["fields"]

    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("JIRA_API_TOKEN")
        with pytest.raises(EnvironmentError, match="JIRA_API_TOKEN"):
            create_jira_issue(summary="Fail")


# ── JiraCreateIssueTool (CrewAI tool wrapper) ─────────────────────────


class TestJiraCreateIssueTool:

    def test_tool_metadata(self):
        tool = JiraCreateIssueTool()
        assert tool.name == "jira_create_issue"
        assert "Jira" in tool.description

    @patch("crewai_productfeature_planner.tools.jira_tool.create_jira_issue")
    def test_run_success(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-42",
            "issue_id": "4242",
            "url": "https://example.atlassian.net/browse/PRD-42",
        }

        tool = JiraCreateIssueTool()
        result = tool._run(summary="Test Story")

        assert "PRD-42" in result
        assert "created" in result

    def test_run_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        tool = JiraCreateIssueTool()
        result = tool._run(summary="Fail")

        assert "skipped" in result

    @patch("crewai_productfeature_planner.tools.jira_tool.create_jira_issue")
    def test_run_api_error(self, mock_create):
        mock_create.side_effect = RuntimeError("Jira API error 403")

        tool = JiraCreateIssueTool()
        result = tool._run(summary="ForbiddenStory")

        assert "failed" in result

    @patch("crewai_productfeature_planner.tools.jira_tool.create_jira_issue")
    def test_run_labels_parsed(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-99",
            "issue_id": "9999",
            "url": "https://example.atlassian.net/browse/PRD-99",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="Labeled", labels="prd, auto-gen, review")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["labels"] == ["prd", "auto-gen", "review"]

    @patch("crewai_productfeature_planner.tools.jira_tool.create_jira_issue")
    def test_run_empty_labels(self, mock_create):
        mock_create.return_value = {
            "issue_key": "PRD-98",
            "issue_id": "9898",
            "url": "https://example.atlassian.net/browse/PRD-98",
        }

        tool = JiraCreateIssueTool()
        tool._run(summary="No Labels", labels="")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["labels"] == []
