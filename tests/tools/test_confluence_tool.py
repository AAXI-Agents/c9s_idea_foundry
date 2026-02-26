"""Tests for the Atlassian Confluence publishing tool."""

import json
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.tools.confluence_tool import (
    ConfluencePublishTool,
    _build_auth_header,
    _get_confluence_env,
    _has_confluence_credentials,
    find_page_by_title,
    publish_to_confluence,
)


# ── _get_confluence_env ──────────────────────────────────────────────


class TestGetConfluenceEnv:

    def test_all_vars_set(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        monkeypatch.setenv("CONFLUENCE_PARENT_ID", "12345")

        env = _get_confluence_env()
        assert env["base_url"] == "https://example.atlassian.net/wiki"
        assert env["space_key"] == "PRD"
        assert env["username"] == "user@example.com"
        assert env["api_token"] == "secret"
        assert env["parent_id"] == "12345"

    def test_missing_base_url(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        with pytest.raises(EnvironmentError, match="ATLASSIAN_BASE_URL"):
            _get_confluence_env()

    def test_missing_multiple_vars(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_SPACE_KEY", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)

        with pytest.raises(EnvironmentError) as exc_info:
            _get_confluence_env()
        assert "ATLASSIAN_BASE_URL" in str(exc_info.value)

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki/")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_confluence_env()
        assert env["base_url"] == "https://example.atlassian.net/wiki"

    def test_appends_wiki_when_missing(self, monkeypatch):
        """ATLASSIAN_BASE_URL without /wiki should auto-append it."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_confluence_env()
        assert env["base_url"] == "https://example.atlassian.net/wiki"

    def test_appends_wiki_after_trailing_slash_strip(self, monkeypatch):
        """Trailing slash stripped first, then /wiki appended."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_confluence_env()
        assert env["base_url"] == "https://example.atlassian.net/wiki"

    def test_does_not_double_wiki(self, monkeypatch):
        """ATLASSIAN_BASE_URL already ending with /wiki should stay unchanged."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

        env = _get_confluence_env()
        assert env["base_url"] == "https://example.atlassian.net/wiki"

    def test_parent_id_default_empty(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        monkeypatch.delenv("CONFLUENCE_PARENT_ID", raising=False)

        env = _get_confluence_env()
        assert env["parent_id"] == ""


# ── _has_confluence_credentials ──────────────────────────────────────


class TestHasConfluenceCredentials:

    def test_all_set(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        assert _has_confluence_credentials() is True

    def test_missing(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_SPACE_KEY", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        assert _has_confluence_credentials() is False


# ── _build_auth_header ───────────────────────────────────────────────


def test_build_auth_header():
    header = _build_auth_header("user@example.com", "token123")
    assert header.startswith("Basic ")
    import base64
    decoded = base64.b64decode(header.split(" ")[1]).decode()
    assert decoded == "user@example.com:token123"


# ── publish_to_confluence ────────────────────────────────────────────


class TestPublishToConfluence:

    @pytest.fixture(autouse=True)
    def _set_env(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")

    @patch("crewai_productfeature_planner.tools.confluence_tool._confluence_request")
    @patch("crewai_productfeature_planner.tools.confluence_tool.find_page_by_title")
    def test_creates_new_page(self, mock_find, mock_request):
        mock_find.return_value = None
        mock_request.return_value = {
            "id": "123456",
            "_links": {"webui": "/pages/123456/PRD+Test"},
        }

        result = publish_to_confluence(
            title="PRD Test",
            markdown_content="# Hello\n\nWorld",
            run_id="test-run",
        )

        assert result["page_id"] == "123456"
        assert result["action"] == "created"
        assert "123456" in result["url"]
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"

    @patch("crewai_productfeature_planner.tools.confluence_tool._confluence_request")
    @patch("crewai_productfeature_planner.tools.confluence_tool.find_page_by_title")
    def test_updates_existing_page(self, mock_find, mock_request):
        mock_find.return_value = {
            "id": "789",
            "version": {"number": 3},
        }
        mock_request.return_value = {
            "id": "789",
            "_links": {"webui": "/pages/789/PRD+Update"},
        }

        result = publish_to_confluence(
            title="PRD Update",
            markdown_content="# Updated\n\nContent",
        )

        assert result["page_id"] == "789"
        assert result["action"] == "updated"
        call_args = mock_request.call_args
        assert call_args[0][0] == "PUT"
        payload = call_args[1]["data"]
        assert payload["version"]["number"] == 4  # incremented

    @patch("crewai_productfeature_planner.tools.confluence_tool._confluence_request")
    @patch("crewai_productfeature_planner.tools.confluence_tool.find_page_by_title")
    def test_creates_with_parent(self, mock_find, mock_request, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_PARENT_ID", "99999")
        mock_find.return_value = None
        mock_request.return_value = {"id": "55555", "_links": {}}

        publish_to_confluence(title="Child Page", markdown_content="# Child")

        payload = mock_request.call_args[1]["data"]
        assert payload["ancestors"] == [{"id": "99999"}]

    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_API_TOKEN")
        with pytest.raises(EnvironmentError, match="ATLASSIAN_API_TOKEN"):
            publish_to_confluence(title="Test", markdown_content="# Fail")


# ── ConfluencePublishTool (CrewAI tool wrapper) ──────────────────────


class TestConfluencePublishTool:

    def test_tool_metadata(self):
        tool = ConfluencePublishTool()
        assert tool.name == "confluence_publisher"
        assert "Confluence" in tool.description

    @patch("crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence")
    def test_run_success(self, mock_publish):
        mock_publish.return_value = {
            "page_id": "111",
            "url": "https://example.atlassian.net/wiki/pages/111",
            "action": "created",
        }

        tool = ConfluencePublishTool()
        result = tool._run(title="Test PRD", markdown_content="# PRD")

        assert "created" in result
        assert "111" in result

    def test_run_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)

        tool = ConfluencePublishTool()
        result = tool._run(title="Test", markdown_content="# Fail")

        assert "skipped" in result

    @patch("crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence")
    def test_run_api_error(self, mock_publish):
        mock_publish.side_effect = RuntimeError("API error 500")

        tool = ConfluencePublishTool()
        result = tool._run(title="Test", markdown_content="# Fail")

        assert "failed" in result
