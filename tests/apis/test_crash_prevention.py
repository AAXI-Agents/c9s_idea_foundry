"""Tests for server crash-prevention hardening (v0.37.0).

Validates:
- _safe_handler catches exceptions, logs them, and posts Slack error
- Global exception handler returns structured JSON with exc_info
- PRD router MongoDB failures → 500 with clean response
- Jira / Confluence JSON decode protection
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ── _safe_handler unit tests ──────────────────────────────────────────


class TestSafeHandler:
    """Verify the _safe_handler crash-protection wrapper."""

    MODULE = (
        "crewai_productfeature_planner.apis.slack"
        ".interactions_router._dispatch"
    )

    def _import_safe_handler(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _safe_handler,
        )
        return _safe_handler

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.current_team_id",
        new_callable=MagicMock,
    )
    def test_calls_fn_and_returns_result(self, mock_team_ctx):
        """Happy path: wraps fn, sets team_id, returns result."""
        _safe_handler = self._import_safe_handler()

        def _dummy(x, y):
            return x + y

        result = _safe_handler("T123", _dummy, 3, 4)
        assert result == 7
        mock_team_ctx.set.assert_called_once_with("T123")

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.current_team_id",
        new_callable=MagicMock,
    )
    def test_catches_exception_and_does_not_raise(self, mock_team_ctx):
        """Exception in handler is swallowed — thread pool stays healthy."""
        _safe_handler = self._import_safe_handler()

        def _explode():
            raise ValueError("boom")

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=None,
        ):
            # Must not raise
            result = _safe_handler("T123", _explode, channel="C1", thread_ts="t1")
        assert result is None

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.current_team_id",
        new_callable=MagicMock,
    )
    def test_logs_error_with_exc_info(self, mock_team_ctx):
        """Exception triggers logger.error with exc_info=True."""
        _safe_handler = self._import_safe_handler()

        def _explode():
            raise RuntimeError("test crash")

        with patch(f"{self.MODULE}.logger") as mock_logger, \
             patch(
                 "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
                 return_value=None,
             ):
            _safe_handler("T123", _explode, channel="C1", thread_ts="t1")

        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args
        assert call_kwargs[1].get("exc_info") is True

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.current_team_id",
        new_callable=MagicMock,
    )
    def test_posts_slack_error_message(self, mock_team_ctx):
        """Exception → posts user-visible error to Slack channel/thread."""
        _safe_handler = self._import_safe_handler()
        mock_client = MagicMock()

        def _explode():
            raise RuntimeError("kaboom")

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ), patch(f"{self.MODULE}.logger"):
            _safe_handler(
                "T123", _explode,
                channel="C_CHAN", thread_ts="1234.5678",
            )

        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C_CHAN"
        assert call_kwargs["thread_ts"] == "1234.5678"
        assert ":x:" in call_kwargs["text"]
        assert "Something went wrong" in call_kwargs["text"]

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.current_team_id",
        new_callable=MagicMock,
    )
    def test_slack_post_failure_is_silent(self, mock_team_ctx):
        """If posting the error to Slack also fails, it's swallowed."""
        _safe_handler = self._import_safe_handler()
        mock_client = MagicMock()
        mock_client.chat_postMessage.side_effect = RuntimeError("Slack down")

        def _explode():
            raise RuntimeError("handler crash")

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ), patch(f"{self.MODULE}.logger"):
            # Must not raise even when Slack notification fails
            _safe_handler(
                "T123", _explode,
                channel="C1", thread_ts="t1",
            )

    @patch(
        "crewai_productfeature_planner.tools.slack_tools.current_team_id",
        new_callable=MagicMock,
    )
    def test_no_channel_skips_slack_post(self, mock_team_ctx):
        """If channel is empty, don't attempt Slack notification."""
        _safe_handler = self._import_safe_handler()

        def _explode():
            raise RuntimeError("oops")

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
        ) as mock_get_client, patch(f"{self.MODULE}.logger"):
            _safe_handler("T123", _explode, channel="", thread_ts="")

        # _get_slack_client is called but chat_postMessage should not be
        # called because channel is empty (guard: `if client and channel`)
        if mock_get_client.return_value:
            mock_get_client.return_value.chat_postMessage.assert_not_called()


# ── Global exception handler tests ───────────────────────────────────


class TestGlobalExceptionHandler:
    """Verify the FastAPI global exception handler returns structured JSON."""

    @pytest.mark.anyio
    async def test_internal_error_response(self):
        """Generic exception → 500 INTERNAL_ERROR."""
        from unittest.mock import AsyncMock

        from crewai_productfeature_planner.apis import _unhandled_exception_handler

        request = AsyncMock()
        request.method = "GET"
        request.url.path = "/test"

        resp = await _unhandled_exception_handler(request, RuntimeError("boom"))
        assert resp.status_code == 500
        body = json.loads(resp.body)
        assert body["error_code"] == "INTERNAL_ERROR"
        assert "boom" in body["message"]
        assert body["run_id"] is None

    @pytest.mark.anyio
    async def test_billing_error_response(self):
        """BillingError → 503 BILLING_ERROR."""
        from unittest.mock import AsyncMock

        from crewai_productfeature_planner.apis import _unhandled_exception_handler
        from crewai_productfeature_planner.scripts.retry import BillingError

        request = AsyncMock()
        request.method = "POST"
        request.url.path = "/flow/prd/kickoff"

        resp = await _unhandled_exception_handler(request, BillingError("quota exceeded"))
        assert resp.status_code == 503
        body = json.loads(resp.body)
        assert body["error_code"] == "BILLING_ERROR"

    @pytest.mark.anyio
    async def test_llm_error_response(self):
        """LLMError → 503 LLM_ERROR."""
        from unittest.mock import AsyncMock

        from crewai_productfeature_planner.apis import _unhandled_exception_handler
        from crewai_productfeature_planner.scripts.retry import LLMError

        request = AsyncMock()
        request.method = "POST"
        request.url.path = "/flow/prd/kickoff"

        resp = await _unhandled_exception_handler(request, LLMError("model down"))
        assert resp.status_code == 503
        body = json.loads(resp.body)
        assert body["error_code"] == "LLM_ERROR"


# ── Jira HTTP JSON decode protection ─────────────────────────────────


class TestJiraJsonDecodeProtection:
    """Verify Jira HTTP returns RuntimeError on invalid JSON."""

    JIRA_HTTP = "crewai_productfeature_planner.tools.jira._http"

    @patch(f"crewai_productfeature_planner.tools.jira._http.urllib.request.urlopen")
    def test_invalid_json_raises_runtime_error(self, mock_urlopen):
        """Jira returning garbage HTML instead of JSON → RuntimeError."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>Not JSON</html>"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from crewai_productfeature_planner.tools.jira._http import _jira_request

        with pytest.raises(RuntimeError, match="invalid JSON"):
            _jira_request("GET", "https://test.atlassian.net/rest/api/3/issue", auth_header="Basic dGVzdA==")

    @patch(f"crewai_productfeature_planner.tools.jira._http.urllib.request.urlopen")
    def test_valid_json_returns_dict(self, mock_urlopen):
        """Jira returning valid JSON works normally."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"key": "PROJ-1"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from crewai_productfeature_planner.tools.jira._http import _jira_request

        result = _jira_request("GET", "https://test.atlassian.net/rest/api/3/issue", auth_header="Basic dGVzdA==")
        assert result == {"key": "PROJ-1"}

    @patch(f"crewai_productfeature_planner.tools.jira._http.urllib.request.urlopen")
    def test_empty_response_returns_empty_dict(self, mock_urlopen):
        """Jira returning empty body → empty dict (not JSONDecodeError)."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"  "
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from crewai_productfeature_planner.tools.jira._http import _jira_request

        result = _jira_request("GET", "https://test.atlassian.net/rest/api/3/issue", auth_header="Basic dGVzdA==")
        assert result == {}


# ── Confluence JSON decode protection ─────────────────────────────────


class TestConfluenceJsonDecodeProtection:
    """Verify Confluence HTTP returns RuntimeError on invalid JSON."""

    @patch(
        "crewai_productfeature_planner.tools.confluence_tool.urllib.request.urlopen"
    )
    def test_invalid_json_raises_runtime_error(self, mock_urlopen):
        """Confluence returning garbage → RuntimeError."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>Server Error</html>"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from crewai_productfeature_planner.tools.confluence_tool import (
            _confluence_request,
        )

        with pytest.raises(RuntimeError, match="invalid JSON"):
            _confluence_request("GET", "https://test.atlassian.net/wiki/rest/api/content", auth_header="Basic dGVzdA==")


# ── PRD router MongoDB failure protection ─────────────────────────────


class TestPrdRouterMongoProtection:
    """Verify PRD router returns 500 on MongoDB failures."""

    @pytest.mark.anyio
    async def test_list_resumable_mongo_failure(self):
        """MongoDB crash during list_resumable → 500."""
        from httpx import ASGITransport, AsyncClient

        from crewai_productfeature_planner.apis import app
        from crewai_productfeature_planner.apis.sso_auth import require_sso_user

        app.dependency_overrides[require_sso_user] = lambda: {"user_id": "test"}
        try:
            with patch(
                "crewai_productfeature_planner.mongodb.find_unfinalized",
                side_effect=Exception("MongoDB down"),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    resp = await ac.get("/flow/prd/resumable")

            assert resp.status_code == 500
            assert "Failed to query resumable runs" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(require_sso_user, None)
