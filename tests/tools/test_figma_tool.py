"""Tests for the Figma Make integration tool.

Covers:
- ``_config.py`` — env helpers and credential check
- ``_client.py`` — request building, submit, poll
- ``figma_make_tool.py`` — CrewAI BaseTool wrapper
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.tools.figma._config import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_POLL_TIMEOUT,
    FIGMA_API_BASE,
    get_figma_access_token,
    get_figma_team_id,
    has_figma_credentials,
)
from crewai_productfeature_planner.tools.figma._client import (
    FigmaMakeError,
    _request,
    poll_figma_make,
    submit_figma_make,
)
from crewai_productfeature_planner.tools.figma.figma_make_tool import (
    FigmaMakeInput,
    FigmaMakeTool,
)


# ── _config ──────────────────────────────────────────────────


class TestFigmaConfig:

    def test_get_figma_access_token_set(self, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok-abc-123")
        assert get_figma_access_token() == "tok-abc-123"

    def test_get_figma_access_token_missing(self, monkeypatch):
        monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
        assert get_figma_access_token() == ""

    def test_get_figma_access_token_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "  tok-123  ")
        assert get_figma_access_token() == "tok-123"

    def test_get_figma_team_id_set(self, monkeypatch):
        monkeypatch.setenv("FIGMA_TEAM_ID", "team-456")
        assert get_figma_team_id() == "team-456"

    def test_get_figma_team_id_missing(self, monkeypatch):
        monkeypatch.delenv("FIGMA_TEAM_ID", raising=False)
        assert get_figma_team_id() == ""

    def test_has_figma_credentials_true(self, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        assert has_figma_credentials() is True

    def test_has_figma_credentials_false(self, monkeypatch):
        monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
        assert has_figma_credentials() is False

    def test_has_figma_credentials_empty_string(self, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "  ")
        assert has_figma_credentials() is False

    def test_api_base_url(self):
        assert FIGMA_API_BASE == "https://api.figma.com"

    def test_default_poll_constants(self):
        assert DEFAULT_POLL_INTERVAL == 10
        assert DEFAULT_POLL_TIMEOUT == 300


# ── _client._request ────────────────────────────────────────


_CLIENT_MOD = "crewai_productfeature_planner.tools.figma._client"
_TOOL_MOD = "crewai_productfeature_planner.tools.figma.figma_make_tool"


class TestFigmaRequest:

    def test_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
        with pytest.raises(FigmaMakeError, match="FIGMA_ACCESS_TOKEN"):
            _request("GET", "/v1/files/abc")

    @patch(f"{_CLIENT_MOD}.urllib.request.urlopen")
    def test_get_request_sends_auth_header(self, mock_urlopen, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok-test")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _request("GET", "/v1/files/abc")

        assert result == {"ok": True}
        req_obj = mock_urlopen.call_args[0][0]
        assert req_obj.get_header("X-figma-token") == "tok-test"
        assert req_obj.get_method() == "GET"

    @patch(f"{_CLIENT_MOD}.urllib.request.urlopen")
    def test_post_request_sends_body(self, mock_urlopen, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok-test")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"request_id": "req-1"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _request("POST", "/v1/ai/make", body={"prompt": "test"})

        assert result == {"request_id": "req-1"}
        req_obj = mock_urlopen.call_args[0][0]
        assert req_obj.get_method() == "POST"
        assert req_obj.data == json.dumps({"prompt": "test"}).encode("utf-8")

    @patch(f"{_CLIENT_MOD}.urllib.request.urlopen")
    def test_http_error_raises_figma_make_error(self, mock_urlopen, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok-test")
        import urllib.error
        exc = urllib.error.HTTPError(
            "https://api.figma.com/v1/ai/make",
            403, "Forbidden", {}, None,
        )
        mock_urlopen.side_effect = exc

        with pytest.raises(FigmaMakeError, match="HTTP 403"):
            _request("POST", "/v1/ai/make")

    @patch(f"{_CLIENT_MOD}.urllib.request.urlopen")
    def test_url_error_raises_figma_make_error(self, mock_urlopen, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok-test")
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        with pytest.raises(FigmaMakeError, match="connection error"):
            _request("GET", "/v1/files/abc")


# ── _client.submit_figma_make ────────────────────────────────


class TestSubmitFigmaMake:

    @patch(f"{_CLIENT_MOD}._request")
    def test_submit_sends_prompt_and_team(self, mock_req, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("FIGMA_TEAM_ID", "team-42")
        mock_req.return_value = {"request_id": "req-abc", "status": "pending"}

        result = submit_figma_make("Design a dashboard")

        mock_req.assert_called_once_with(
            "POST", "/v1/ai/make",
            body={"prompt": "Design a dashboard", "team_id": "team-42"},
        )
        assert result["request_id"] == "req-abc"

    @patch(f"{_CLIENT_MOD}._request")
    def test_submit_without_team_id(self, mock_req, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        monkeypatch.delenv("FIGMA_TEAM_ID", raising=False)
        mock_req.return_value = {"request_id": "req-xyz"}

        submit_figma_make("A prompt")

        mock_req.assert_called_once_with(
            "POST", "/v1/ai/make",
            body={"prompt": "A prompt"},
        )


# ── _client.poll_figma_make ─────────────────────────────────


class TestPollFigmaMake:

    @patch(f"{_CLIENT_MOD}.time.sleep")
    @patch(f"{_CLIENT_MOD}._request")
    def test_poll_returns_on_completed(self, mock_req, mock_sleep, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_req.return_value = {
            "status": "completed",
            "file_key": "fk-1",
            "file_url": "https://figma.com/design/fk-1",
        }

        result = poll_figma_make("req-1", poll_interval=1, poll_timeout=60)

        assert result["status"] == "completed"
        assert result["file_url"] == "https://figma.com/design/fk-1"
        mock_sleep.assert_not_called()

    @patch(f"{_CLIENT_MOD}.time.sleep")
    @patch(f"{_CLIENT_MOD}._request")
    def test_poll_retries_until_complete(self, mock_req, mock_sleep, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_req.side_effect = [
            {"status": "pending"},
            {"status": "processing"},
            {"status": "completed", "file_key": "fk-2", "file_url": "url-2"},
        ]

        result = poll_figma_make("req-2", poll_interval=1, poll_timeout=60)

        assert result["status"] == "completed"
        assert mock_sleep.call_count == 2

    @patch(f"{_CLIENT_MOD}.time.sleep")
    @patch(f"{_CLIENT_MOD}._request")
    def test_poll_raises_on_failed_status(self, mock_req, mock_sleep, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_req.return_value = {"status": "failed", "error": "bad prompt"}

        with pytest.raises(FigmaMakeError, match="failed.*bad prompt"):
            poll_figma_make("req-3", poll_interval=1, poll_timeout=60)

    @patch(f"{_CLIENT_MOD}.time.monotonic")
    @patch(f"{_CLIENT_MOD}.time.sleep")
    @patch(f"{_CLIENT_MOD}._request")
    def test_poll_raises_on_timeout(self, mock_req, mock_sleep, mock_time, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        # First call to monotonic sets deadline, subsequent calls exceed it.
        mock_time.side_effect = [0, 0, 100, 200]
        mock_req.return_value = {"status": "pending"}

        with pytest.raises(FigmaMakeError, match="timed out"):
            poll_figma_make("req-4", poll_interval=1, poll_timeout=10)


# ── FigmaMakeTool ────────────────────────────────────────────


class TestFigmaMakeTool:

    def test_tool_metadata(self):
        tool = FigmaMakeTool()
        assert tool.name == "figma_make_design"
        assert "Figma" in tool.description

    def test_input_schema(self):
        inp = FigmaMakeInput(prompt="design a login page")
        assert inp.prompt == "design a login page"

    def test_run_skips_without_credentials(self, monkeypatch):
        monkeypatch.delenv("FIGMA_ACCESS_TOKEN", raising=False)
        tool = FigmaMakeTool()
        result = tool._run(prompt="test prompt")
        assert result.startswith("FIGMA_SKIPPED:")
        assert "FIGMA_ACCESS_TOKEN" in result

    @patch(f"{_TOOL_MOD}.poll_figma_make")
    @patch(f"{_TOOL_MOD}.submit_figma_make")
    def test_run_returns_url_on_success(self, mock_submit, mock_poll, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_submit.return_value = {"request_id": "req-ok"}
        mock_poll.return_value = {
            "status": "completed",
            "file_url": "https://figma.com/design/myfile",
        }

        tool = FigmaMakeTool()
        result = tool._run(prompt="build me a dashboard")

        assert result == "FIGMA_URL:https://figma.com/design/myfile"

    @patch(f"{_TOOL_MOD}.poll_figma_make")
    @patch(f"{_TOOL_MOD}.submit_figma_make")
    def test_run_builds_url_from_file_key(self, mock_submit, mock_poll, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_submit.return_value = {"request_id": "req-fk"}
        mock_poll.return_value = {
            "status": "completed",
            "file_key": "abc123",
        }

        tool = FigmaMakeTool()
        result = tool._run(prompt="a design")

        assert result == "FIGMA_URL:https://www.figma.com/design/abc123"

    @patch(f"{_TOOL_MOD}.submit_figma_make")
    def test_run_handles_missing_request_id(self, mock_submit, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_submit.return_value = {"status": "ok"}

        tool = FigmaMakeTool()
        result = tool._run(prompt="test")

        assert result.startswith("FIGMA_ERROR:")
        assert "request_id" in result

    @patch(f"{_TOOL_MOD}.submit_figma_make")
    def test_run_handles_api_error(self, mock_submit, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_submit.side_effect = FigmaMakeError("HTTP 500")

        tool = FigmaMakeTool()
        result = tool._run(prompt="test")

        assert result.startswith("FIGMA_ERROR:")
        assert "500" in result

    @patch(f"{_TOOL_MOD}.submit_figma_make")
    def test_run_handles_unexpected_error(self, mock_submit, monkeypatch):
        monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "tok")
        mock_submit.side_effect = RuntimeError("surprise!")

        tool = FigmaMakeTool()
        result = tool._run(prompt="test")

        assert result.startswith("FIGMA_ERROR:")
        assert "surprise" in result
