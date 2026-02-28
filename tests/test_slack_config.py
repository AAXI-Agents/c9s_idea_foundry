"""Tests for the Slack app URL auto-configuration helper."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.slack_config import (
    _EVENTS_PATH,
    _INTERACTIONS_PATH,
    _MANIFEST_PATH,
    _OAUTH_CALLBACK_PATH,
    _print_manual_instructions,
    _update_via_api,
    build_manifest,
    update_slack_app_urls,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    """Provide dummy keys so tests don't hit real services."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── build_manifest ───────────────────────────────────────────


class TestBuildManifest:
    """Tests for the manifest template builder."""

    def test_sets_interactivity_url(self):
        m = build_manifest(
            "https://example.ngrok.io/slack/interactions",
            "https://example.ngrok.io/slack/events",
            "https://example.ngrok.io/slack/oauth/callback",
        )
        assert m["settings"]["interactivity"]["request_url"] == (
            "https://example.ngrok.io/slack/interactions"
        )

    def test_sets_events_url(self):
        m = build_manifest(
            "https://example.ngrok.io/slack/interactions",
            "https://example.ngrok.io/slack/events",
            "https://example.ngrok.io/slack/oauth/callback",
        )
        assert m["settings"]["event_subscriptions"]["request_url"] == (
            "https://example.ngrok.io/slack/events"
        )

    def test_sets_oauth_redirect_url(self):
        m = build_manifest(
            "https://example.ngrok.io/slack/interactions",
            "https://example.ngrok.io/slack/events",
            "https://example.ngrok.io/slack/oauth/callback",
        )
        assert m["oauth_config"]["redirect_urls"] == [
            "https://example.ngrok.io/slack/oauth/callback"
        ]

    def test_interactivity_is_enabled(self):
        m = build_manifest("a", "b", "c")
        assert m["settings"]["interactivity"]["is_enabled"] is True

    def test_preserves_bot_events(self):
        m = build_manifest("a", "b", "c")
        bot_events = m["settings"]["event_subscriptions"]["bot_events"]
        assert "app_mention" in bot_events
        assert "message.im" in bot_events

    def test_preserves_scopes(self):
        m = build_manifest("a", "b", "c")
        scopes = m["oauth_config"]["scopes"]["bot"]
        assert "chat:write" in scopes
        assert "app_mentions:read" in scopes

    def test_preserves_display_info(self):
        m = build_manifest("a", "b", "c")
        assert m["display_information"]["name"] == "CrewAI PRD Planner"


# ── update_slack_app_urls ────────────────────────────────────


class TestUpdateSlackAppUrls:
    """Tests for the top-level URL updater."""

    def test_calls_api_when_credentials_set(self, monkeypatch):
        monkeypatch.setenv("SLACK_APP_ID", "A12345")
        monkeypatch.setenv("SLACK_APP_CONFIGURATION_TOKEN", "xoxe.xoxp-test")

        with patch(
            "crewai_productfeature_planner.scripts.slack_config._update_via_api",
            return_value=True,
        ) as mock_api:
            result = update_slack_app_urls("https://test.ngrok.io")

        assert result is True
        mock_api.assert_called_once_with(
            "A12345",
            "xoxe.xoxp-test",
            "https://test.ngrok.io/slack/interactions",
            "https://test.ngrok.io/slack/events",
            "https://test.ngrok.io/slack/oauth/callback",
        )

    def test_falls_back_to_manual_when_no_app_id(self, monkeypatch):
        monkeypatch.delenv("SLACK_APP_ID", raising=False)
        monkeypatch.delenv("SLACK_APP_CONFIGURATION_TOKEN", raising=False)

        with patch(
            "crewai_productfeature_planner.scripts.slack_config._print_manual_instructions",
        ) as mock_manual:
            result = update_slack_app_urls("https://test.ngrok.io")

        assert result is False
        mock_manual.assert_called_once()

    def test_falls_back_when_only_app_id_set(self, monkeypatch):
        monkeypatch.setenv("SLACK_APP_ID", "A12345")
        monkeypatch.delenv("SLACK_APP_CONFIGURATION_TOKEN", raising=False)

        with patch(
            "crewai_productfeature_planner.scripts.slack_config._print_manual_instructions",
        ) as mock_manual:
            result = update_slack_app_urls("https://test.ngrok.io")

        assert result is False
        mock_manual.assert_called_once()

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("SLACK_APP_ID", "A12345")
        monkeypatch.setenv("SLACK_APP_CONFIGURATION_TOKEN", "xoxe.xoxp-test")

        with patch(
            "crewai_productfeature_planner.scripts.slack_config._update_via_api",
            return_value=True,
        ) as mock_api:
            update_slack_app_urls("https://test.ngrok.io/")

        # The trailing slash should be stripped.
        args = mock_api.call_args[0]
        assert args[2] == "https://test.ngrok.io/slack/interactions"


# ── _update_via_api ──────────────────────────────────────────


class TestUpdateViaApi:
    """Tests for the Slack API path."""

    def test_returns_true_on_success(self):
        mock_client = MagicMock()
        mock_client.api_call.return_value = {"ok": True}

        with patch("slack_sdk.WebClient", return_value=mock_client):
            result = _update_via_api(
                "A12345", "xoxe.xoxp-test",
                "https://x.io/slack/interactions",
                "https://x.io/slack/events",
                "https://x.io/slack/oauth/callback",
            )

        assert result is True
        mock_client.api_call.assert_called_once()
        call_args = mock_client.api_call.call_args
        assert call_args[0][0] == "apps.manifest.update"
        payload = call_args[1]["json"]
        assert payload["app_id"] == "A12345"

    def test_returns_false_on_api_error(self):
        mock_client = MagicMock()
        mock_client.api_call.return_value = {
            "ok": False,
            "error": "invalid_manifest",
        }

        with (
            patch("slack_sdk.WebClient", return_value=mock_client),
            patch(
                "crewai_productfeature_planner.scripts.slack_config."
                "_print_manual_instructions",
            ),
        ):
            result = _update_via_api(
                "A12345", "xoxe.xoxp-test",
                "https://x.io/a", "https://x.io/b", "https://x.io/c",
            )

        assert result is False

    def test_returns_false_on_exception(self):
        mock_client = MagicMock()
        mock_client.api_call.side_effect = RuntimeError("network error")

        with (
            patch("slack_sdk.WebClient", return_value=mock_client),
            patch(
                "crewai_productfeature_planner.scripts.slack_config."
                "_print_manual_instructions",
            ),
        ):
            result = _update_via_api(
                "A12345", "xoxe.xoxp-test",
                "https://x.io/a", "https://x.io/b", "https://x.io/c",
            )

        assert result is False


# ── _print_manual_instructions ───────────────────────────────


class TestPrintManualInstructions:
    """Tests for the fallback manual instructions logger."""

    def test_includes_urls_in_log(self, capsys):
        _print_manual_instructions(
            "https://x.io/slack/interactions",
            "https://x.io/slack/events",
            "https://x.io/slack/oauth/callback",
        )

        captured = capsys.readouterr().err
        assert "https://x.io/slack/interactions" in captured
        assert "https://x.io/slack/events" in captured
        assert "https://x.io/slack/oauth/callback" in captured

    def test_includes_dashboard_link_with_app_id(self, capsys):
        _print_manual_instructions("a", "b", "c", app_id="A9999")

        captured = capsys.readouterr().err
        assert "https://api.slack.com/apps/A9999" in captured

    def test_generic_dashboard_link_without_app_id(self, capsys):
        _print_manual_instructions("a", "b", "c", app_id="")

        captured = capsys.readouterr().err
        assert "https://api.slack.com/apps" in captured


# ── Constants ────────────────────────────────────────────────


class TestConstants:
    """Verify the module-level constants."""

    def test_interactions_path(self):
        assert _INTERACTIONS_PATH == "/slack/interactions"

    def test_events_path(self):
        assert _EVENTS_PATH == "/slack/events"

    def test_oauth_callback_path(self):
        assert _OAUTH_CALLBACK_PATH == "/slack/oauth/callback"

    def test_manifest_path_exists(self):
        assert _MANIFEST_PATH.exists(), f"Expected {_MANIFEST_PATH} to exist"

    def test_manifest_is_valid_json(self):
        raw = _MANIFEST_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "settings" in data
        assert "oauth_config" in data
