"""Tests for the Figma Make integration tool (Playwright-based).

Covers:
- ``_config.py`` — session dir, timeout, headless, project credentials
- ``_api.py`` — Figma REST API client
- ``_client.py`` — Playwright browser automation helpers
- ``figma_make_tool.py`` — CrewAI BaseTool wrapper
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.tools.figma._config import (
    DEFAULT_MAKE_TIMEOUT,
    DEFAULT_SESSION_DIR,
    FIGMA_MAKE_URL,
    FIGMA_OAUTH_URL,
    OAUTH_REDIRECT_URI,
    get_figma_client_id,
    get_figma_client_secret,
    get_figma_credentials,
    get_figma_headless,
    get_figma_make_timeout,
    get_figma_session_dir,
    get_figma_session_path,
    has_figma_credentials,
    _oauth_expired,
)
from crewai_productfeature_planner.tools.figma._client import (
    FigmaMakeError,
    _build_context,
    _find_chat_input,
    _send_prompt,
    _wait_for_generation,
    run_figma_make,
)
from crewai_productfeature_planner.tools.figma._api import (
    FigmaAPIError,
    _build_headers,
    _request,
    get_team_projects,
    get_project_files,
    get_file_info,
    refresh_oauth_token,
    exchange_oauth_code,
)
from crewai_productfeature_planner.tools.figma.figma_make_tool import (
    FigmaMakeInput,
    FigmaMakeTool,
)


# ── module path constants ────────────────────────────────────

_CONFIG_MOD = "crewai_productfeature_planner.tools.figma._config"
_CLIENT_MOD = "crewai_productfeature_planner.tools.figma._client"
_TOOL_MOD = "crewai_productfeature_planner.tools.figma.figma_make_tool"
_API_MOD = "crewai_productfeature_planner.tools.figma._api"


# ── _config ──────────────────────────────────────────────────


class TestFigmaConfig:

    def test_figma_make_url(self):
        assert FIGMA_MAKE_URL == "https://www.figma.com/make/new"

    def test_figma_oauth_url(self):
        assert FIGMA_OAUTH_URL == "https://www.figma.com/oauth"

    def test_oauth_redirect_uri(self):
        assert OAUTH_REDIRECT_URI == "http://localhost:3000/figma/callback"

    def test_default_make_timeout(self):
        assert DEFAULT_MAKE_TIMEOUT == 300

    def test_default_session_dir(self):
        assert DEFAULT_SESSION_DIR == os.path.expanduser("~/.figma_session")

    def test_get_figma_session_dir_default(self, monkeypatch):
        monkeypatch.delenv("FIGMA_SESSION_DIR", raising=False)
        assert get_figma_session_dir() == DEFAULT_SESSION_DIR

    def test_get_figma_session_dir_custom(self, monkeypatch):
        monkeypatch.setenv("FIGMA_SESSION_DIR", "/tmp/my_session")
        assert get_figma_session_dir() == "/tmp/my_session"

    def test_get_figma_session_dir_strips(self, monkeypatch):
        monkeypatch.setenv("FIGMA_SESSION_DIR", "  /tmp/s  ")
        assert get_figma_session_dir() == "/tmp/s"

    def test_get_figma_session_path(self, monkeypatch):
        monkeypatch.setenv("FIGMA_SESSION_DIR", "/tmp/sess")
        assert get_figma_session_path() == "/tmp/sess/state.json"

    def test_get_figma_make_timeout_default(self, monkeypatch):
        monkeypatch.delenv("FIGMA_MAKE_TIMEOUT", raising=False)
        assert get_figma_make_timeout() == 300

    def test_get_figma_make_timeout_custom(self, monkeypatch):
        monkeypatch.setenv("FIGMA_MAKE_TIMEOUT", "600")
        assert get_figma_make_timeout() == 600

    def test_get_figma_make_timeout_invalid(self, monkeypatch):
        monkeypatch.setenv("FIGMA_MAKE_TIMEOUT", "abc")
        assert get_figma_make_timeout() == 300

    def test_get_figma_headless_default(self, monkeypatch):
        monkeypatch.delenv("FIGMA_HEADLESS", raising=False)
        assert get_figma_headless() is True

    def test_get_figma_headless_false(self, monkeypatch):
        monkeypatch.setenv("FIGMA_HEADLESS", "false")
        assert get_figma_headless() is False

    def test_get_figma_headless_true(self, monkeypatch):
        monkeypatch.setenv("FIGMA_HEADLESS", "TRUE")
        assert get_figma_headless() is True

    def test_get_figma_client_id(self, monkeypatch):
        monkeypatch.setenv("FIGMA_CLIENT_ID", "my-client-id")
        assert get_figma_client_id() == "my-client-id"

    def test_get_figma_client_secret(self, monkeypatch):
        monkeypatch.setenv("FIGMA_CLIENT_SECRET", "my-secret")
        assert get_figma_client_secret() == "my-secret"


class TestFigmaCredentials:

    def test_get_figma_credentials_empty(self):
        creds = get_figma_credentials(None)
        assert creds["api_key"] == ""
        assert creds["oauth_token"] == ""
        assert creds["team_id"] == ""

    def test_get_figma_credentials_from_project(self):
        cfg = {
            "figma_api_key": "figd_test123",
            "figma_team_id": "12345",
            "figma_oauth_token": "tok_abc",
            "figma_oauth_refresh_token": "ref_xyz",
            "figma_oauth_expires_at": "2026-06-01T00:00:00+00:00",
        }
        creds = get_figma_credentials(cfg)
        assert creds["api_key"] == "figd_test123"
        assert creds["team_id"] == "12345"
        assert creds["oauth_token"] == "tok_abc"
        assert creds["oauth_refresh_token"] == "ref_xyz"

    @patch(f"{_CONFIG_MOD}.os.path.isfile", return_value=False)
    def test_has_credentials_with_api_key(self, _):
        cfg = {"figma_api_key": "figd_test"}
        assert has_figma_credentials(cfg) is True

    @patch(f"{_CONFIG_MOD}.os.path.isfile", return_value=False)
    def test_has_credentials_with_valid_oauth(self, _):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        cfg = {"figma_oauth_token": "tok", "figma_oauth_expires_at": future}
        assert has_figma_credentials(cfg) is True

    @patch(f"{_CONFIG_MOD}.os.path.isfile", return_value=False)
    def test_has_credentials_with_expired_oauth(self, _):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        cfg = {"figma_oauth_token": "tok", "figma_oauth_expires_at": past}
        assert has_figma_credentials(cfg) is False

    @patch(f"{_CONFIG_MOD}.os.path.isfile", return_value=True)
    def test_has_credentials_session_file(self, _, monkeypatch):
        monkeypatch.setenv("FIGMA_SESSION_DIR", "/tmp/sess")
        assert has_figma_credentials() is True

    @patch(f"{_CONFIG_MOD}.os.path.isfile", return_value=False)
    def test_has_credentials_none(self, _, monkeypatch):
        monkeypatch.setenv("FIGMA_SESSION_DIR", "/tmp/nosess")
        assert has_figma_credentials() is False

    def test_oauth_expired_empty(self):
        assert _oauth_expired("") is True

    def test_oauth_expired_future(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        assert _oauth_expired(future) is False

    def test_oauth_expired_past(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert _oauth_expired(past) is True

    def test_oauth_expired_invalid(self):
        assert _oauth_expired("not-a-date") is True


# ── _api ─────────────────────────────────────────────────────


class TestBuildHeaders:

    def test_api_key_header(self):
        h = _build_headers(api_key="figd_test")
        assert h["X-Figma-Token"] == "figd_test"
        assert "Authorization" not in h

    def test_oauth_token_header(self):
        h = _build_headers(oauth_token="bearer_tok")
        assert h["Authorization"] == "Bearer bearer_tok"
        assert "X-Figma-Token" not in h

    def test_oauth_takes_priority(self):
        h = _build_headers(api_key="key", oauth_token="tok")
        assert "Authorization" in h
        assert "X-Figma-Token" not in h

    def test_no_auth(self):
        h = _build_headers()
        assert "X-Figma-Token" not in h
        assert "Authorization" not in h
        assert h["Accept"] == "application/json"


class TestFigmaAPIRequest:

    @patch(f"{_API_MOD}.urllib.request.urlopen")
    def test_get_request(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"projects": []}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _request("GET", "/v1/teams/123/projects", api_key="k")
        assert result == {"projects": []}

    @patch(f"{_API_MOD}.urllib.request.urlopen")
    def test_http_error_raises(self, mock_urlopen):
        import urllib.error

        error = urllib.error.HTTPError(
            "url", 403, "Forbidden", {}, MagicMock(read=lambda: b"bad token"),
        )
        mock_urlopen.side_effect = error

        with pytest.raises(FigmaAPIError) as exc_info:
            _request("GET", "/v1/teams/1/projects", api_key="k")
        assert exc_info.value.status == 403


class TestGetTeamProjects:

    @patch(f"{_API_MOD}._request")
    def test_returns_projects(self, mock_req):
        mock_req.return_value = {
            "projects": [
                {"id": 1, "name": "Design System"},
                {"id": 2, "name": "Mobile App"},
            ]
        }
        result = get_team_projects("T1", api_key="k")
        assert len(result) == 2
        assert result[0]["name"] == "Design System"
        mock_req.assert_called_once_with(
            "GET", "/v1/teams/T1/projects", api_key="k", oauth_token="",
        )


class TestGetProjectFiles:

    @patch(f"{_API_MOD}._request")
    def test_returns_files(self, mock_req):
        mock_req.return_value = {
            "files": [{"key": "abc", "name": "Homepage"}]
        }
        result = get_project_files("P1", api_key="k")
        assert len(result) == 1
        assert result[0]["key"] == "abc"


class TestGetFileInfo:

    @patch(f"{_API_MOD}._request")
    def test_returns_file_metadata(self, mock_req):
        mock_req.return_value = {"name": "My File", "version": "123"}
        result = get_file_info("abc123", api_key="k")
        assert result["name"] == "My File"


class TestRefreshOAuthToken:

    @patch(f"{_API_MOD}.urllib.request.urlopen")
    def test_refreshes_token(self, mock_urlopen, monkeypatch):
        monkeypatch.setenv("FIGMA_CLIENT_ID", "cid")
        monkeypatch.setenv("FIGMA_CLIENT_SECRET", "csec")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "access_token": "new_tok",
            "expires_in": 7776000,
            "token_type": "bearer",
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = refresh_oauth_token("old_refresh")
        assert result["access_token"] == "new_tok"

    def test_raises_without_client_credentials(self, monkeypatch):
        monkeypatch.delenv("FIGMA_CLIENT_ID", raising=False)
        monkeypatch.delenv("FIGMA_CLIENT_SECRET", raising=False)
        with pytest.raises(FigmaAPIError, match="CLIENT_ID"):
            refresh_oauth_token("ref")


class TestExchangeOAuthCode:

    @patch(f"{_API_MOD}.urllib.request.urlopen")
    def test_exchanges_code(self, mock_urlopen, monkeypatch):
        monkeypatch.setenv("FIGMA_CLIENT_ID", "cid")
        monkeypatch.setenv("FIGMA_CLIENT_SECRET", "csec")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 7776000,
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = exchange_oauth_code("code123", "http://localhost:3000/cb")
        assert result["access_token"] == "tok"
        assert result["refresh_token"] == "ref"

    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("FIGMA_CLIENT_ID", raising=False)
        monkeypatch.delenv("FIGMA_CLIENT_SECRET", raising=False)
        with pytest.raises(FigmaAPIError, match="CLIENT_ID"):
            exchange_oauth_code("code", "http://localhost/cb")


# ── _client.build_context ────────────────────────────────────


class TestBuildContext:

    def test_prefers_oauth_token(self):
        mock_browser = MagicMock()
        mock_ctx = MagicMock()
        mock_browser.new_context.return_value = mock_ctx

        creds = {"oauth_token": "tok123", "api_key": ""}
        ctx = _build_context(mock_browser, creds=creds, state_path="/none")

        mock_browser.new_context.assert_called_once_with()
        mock_ctx.add_cookies.assert_called_once()
        cookie = mock_ctx.add_cookies.call_args[0][0][0]
        assert cookie["name"] == "figma.authn"
        assert cookie["value"] == "tok123"

    @patch(f"{_CLIENT_MOD}.os.path.isfile", return_value=True)
    def test_falls_back_to_session_file(self, _):
        mock_browser = MagicMock()
        creds = {"oauth_token": "", "api_key": ""}
        _build_context(mock_browser, creds=creds, state_path="/tmp/state.json")
        mock_browser.new_context.assert_called_once_with(
            storage_state="/tmp/state.json",
        )

    @patch(f"{_CLIENT_MOD}.os.path.isfile", return_value=False)
    def test_empty_context_when_no_auth(self, _):
        mock_browser = MagicMock()
        creds = {"oauth_token": "", "api_key": ""}
        _build_context(mock_browser, creds=creds, state_path="/tmp/nope")
        mock_browser.new_context.assert_called_once_with()


# ── _client helpers ──────────────────────────────────────────


class TestFindChatInput:

    def test_finds_visible_textarea(self):
        mock_page = MagicMock()
        mock_el = MagicMock()
        mock_el.is_visible.return_value = True
        mock_page.locator.return_value.first = mock_el

        result = _find_chat_input(mock_page, timeout_ms=1000)
        assert result is mock_el

    def test_raises_when_no_input_found(self):
        mock_page = MagicMock()
        mock_page.wait_for_selector.return_value = None
        mock_el = MagicMock()
        mock_el.is_visible.return_value = False
        mock_page.locator.return_value.first = mock_el
        mock_page.get_by_role.return_value.first = mock_el

        with pytest.raises(FigmaMakeError, match="chat input"):
            _find_chat_input(mock_page, timeout_ms=1000)


class TestSendPrompt:

    def test_presses_enter(self):
        mock_page = MagicMock()
        mock_input = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_visible.return_value = False
        mock_page.get_by_role.return_value = mock_btn
        mock_page.locator.return_value.first = mock_btn

        _send_prompt(mock_page, mock_input, timeout_ms=1000)
        mock_input.press.assert_called_once_with("Enter")

    def test_clicks_send_button_if_visible(self):
        mock_page = MagicMock()
        mock_input = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_visible.return_value = True
        mock_page.get_by_role.return_value = mock_btn

        _send_prompt(mock_page, mock_input, timeout_ms=1000)
        mock_input.press.assert_called_once_with("Enter")
        mock_btn.click.assert_called_once()


class TestWaitForGeneration:

    def test_waits_for_networkidle(self):
        mock_page = MagicMock()
        _wait_for_generation(mock_page, timeout_ms=60_000)
        mock_page.wait_for_load_state.assert_called_once_with(
            "networkidle", timeout=60_000,
        )

    def test_handles_timeout_gracefully(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page = MagicMock()
        mock_page.wait_for_load_state.side_effect = PlaywrightTimeout("timeout")
        _wait_for_generation(mock_page, timeout_ms=1000)


# ── _client.run_figma_make ───────────────────────────────────


class TestRunFigmaMake:

    def _make_mocks(self):
        """Build a mock Playwright stack."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_page.url = "https://www.figma.com/make/abc123XYZ"
        mock_page.goto.return_value = None

        mock_el = MagicMock()
        mock_el.is_visible.return_value = True
        mock_page.locator.return_value.first = mock_el
        mock_page.wait_for_selector.return_value = None

        mock_btn = MagicMock()
        mock_btn.is_visible.return_value = False
        mock_page.get_by_role.return_value = mock_btn

        return mock_pw, mock_browser, mock_context, mock_page

    @patch(f"{_CLIENT_MOD}.get_figma_session_path")
    @patch(f"{_CLIENT_MOD}.get_figma_headless", return_value=True)
    @patch(f"{_CLIENT_MOD}.get_figma_make_timeout", return_value=30)
    @patch(f"{_CLIENT_MOD}.sync_playwright")
    def test_returns_file_url_on_success(
        self, mock_sp, mock_timeout, mock_headless, mock_path,
    ):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mocks()
        mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sp.return_value.__exit__ = MagicMock(return_value=False)
        mock_path.return_value = "/tmp/state.json"

        with patch(f"{_CLIENT_MOD}.os.path.isfile", return_value=True):
            result = run_figma_make("Design a dashboard")

        assert result["file_url"] == "https://www.figma.com/make/abc123XYZ"
        assert result["file_key"] == "abc123XYZ"
        assert result["status"] == "completed"

    @patch(f"{_CLIENT_MOD}.get_figma_session_path")
    @patch(f"{_CLIENT_MOD}.get_figma_headless", return_value=True)
    @patch(f"{_CLIENT_MOD}.get_figma_make_timeout", return_value=30)
    @patch(f"{_CLIENT_MOD}.sync_playwright")
    def test_raises_on_login_redirect(
        self, mock_sp, mock_timeout, mock_headless, mock_path,
    ):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mocks()
        mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sp.return_value.__exit__ = MagicMock(return_value=False)
        mock_path.return_value = "/tmp/state.json"
        mock_page.url = "https://www.figma.com/login?redirect_uri=..."

        with pytest.raises(FigmaMakeError, match="session expired"):
            run_figma_make("test prompt")

    @patch(f"{_CLIENT_MOD}.get_figma_session_path")
    @patch(f"{_CLIENT_MOD}.get_figma_headless", return_value=True)
    @patch(f"{_CLIENT_MOD}.get_figma_make_timeout", return_value=5)
    @patch(f"{_CLIENT_MOD}.sync_playwright")
    def test_raises_on_timeout(
        self, mock_sp, mock_timeout, mock_headless, mock_path,
    ):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_pw, mock_browser, mock_context, mock_page = self._make_mocks()
        mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sp.return_value.__exit__ = MagicMock(return_value=False)
        mock_path.return_value = "/tmp/state.json"
        mock_page.url = "https://www.figma.com/make/new"
        mock_page.wait_for_url.side_effect = PlaywrightTimeout("timed out")

        with pytest.raises(FigmaMakeError, match="timed out"):
            run_figma_make("test")

    @patch(f"{_CLIENT_MOD}.get_figma_session_path")
    @patch(f"{_CLIENT_MOD}.get_figma_headless", return_value=True)
    @patch(f"{_CLIENT_MOD}.get_figma_make_timeout", return_value=30)
    @patch(f"{_CLIENT_MOD}.sync_playwright")
    def test_passes_project_config_to_build_context(
        self, mock_sp, mock_timeout, mock_headless, mock_path,
    ):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mocks()
        mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sp.return_value.__exit__ = MagicMock(return_value=False)
        mock_path.return_value = "/tmp/state.json"

        cfg = {"figma_oauth_token": "my_tok"}
        with patch(f"{_CLIENT_MOD}._build_context", return_value=mock_context) as mock_bc:
            result = run_figma_make("prompt", project_config=cfg)

        # Verify _build_context was called with correct creds
        call_kwargs = mock_bc.call_args[1]
        assert call_kwargs["creds"]["oauth_token"] == "my_tok"


# ── FigmaMakeTool ────────────────────────────────────────────


class TestFigmaMakeTool:

    def test_tool_metadata(self):
        tool = FigmaMakeTool()
        assert tool.name == "figma_make_design"
        assert "Figma" in tool.description

    def test_input_schema(self):
        inp = FigmaMakeInput(prompt="design a login page")
        assert inp.prompt == "design a login page"

    def test_project_config_injection(self):
        tool = FigmaMakeTool()
        cfg = {"figma_api_key": "test"}
        tool._project_config = cfg
        assert tool._project_config is cfg

    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=False)
    def test_run_skips_without_credentials(self, mock_creds):
        tool = FigmaMakeTool()
        result = tool._run(prompt="test prompt")
        assert result.startswith("FIGMA_SKIPPED:")

    @patch(f"{_TOOL_MOD}.run_figma_make")
    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=True)
    def test_run_returns_url_on_success(self, mock_creds, mock_run):
        mock_run.return_value = {
            "file_url": "https://www.figma.com/make/myfile",
            "file_key": "myfile",
            "status": "completed",
        }

        tool = FigmaMakeTool()
        result = tool._run(prompt="build me a dashboard")
        assert result == "FIGMA_URL:https://www.figma.com/make/myfile"

    @patch(f"{_TOOL_MOD}.run_figma_make")
    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=True)
    def test_run_passes_project_config(self, mock_creds, mock_run):
        mock_run.return_value = {
            "file_url": "https://www.figma.com/make/f1",
            "file_key": "f1",
            "status": "completed",
        }

        tool = FigmaMakeTool()
        cfg = {"figma_api_key": "test_key"}
        tool._project_config = cfg
        tool._run(prompt="prompt")

        mock_run.assert_called_once_with("prompt", project_config=cfg)

    @patch(f"{_TOOL_MOD}.run_figma_make")
    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=True)
    def test_run_builds_url_from_file_key(self, mock_creds, mock_run):
        mock_run.return_value = {
            "file_url": "",
            "file_key": "abc123",
            "status": "completed",
        }

        tool = FigmaMakeTool()
        result = tool._run(prompt="a design")
        assert result == "FIGMA_URL:https://www.figma.com/make/abc123"

    @patch(f"{_TOOL_MOD}.run_figma_make")
    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=True)
    def test_run_handles_empty_result(self, mock_creds, mock_run):
        mock_run.return_value = {
            "file_url": "",
            "file_key": "",
            "status": "completed",
        }

        tool = FigmaMakeTool()
        result = tool._run(prompt="test")
        assert result.startswith("FIGMA_ERROR:")

    @patch(f"{_TOOL_MOD}.run_figma_make")
    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=True)
    def test_run_handles_figma_error(self, mock_creds, mock_run):
        mock_run.side_effect = FigmaMakeError("timed out after 300s")

        tool = FigmaMakeTool()
        result = tool._run(prompt="test")
        assert result.startswith("FIGMA_ERROR:")
        assert "timed out" in result

    @patch(f"{_TOOL_MOD}.run_figma_make")
    @patch(f"{_TOOL_MOD}.has_figma_credentials", return_value=True)
    def test_run_handles_unexpected_error(self, mock_creds, mock_run):
        mock_run.side_effect = RuntimeError("surprise!")

        tool = FigmaMakeTool()
        result = tool._run(prompt="test")
        assert result.startswith("FIGMA_ERROR:")
        assert "surprise" in result
