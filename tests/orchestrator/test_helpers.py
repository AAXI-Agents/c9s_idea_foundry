"""Tests for orchestrator._helpers — credential checks and CLI output."""

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    _print_delivery_status,
)


# ── _has_gemini_credentials helper ───────────────────────────────────


class TestHasGeminiCredentials:

    def test_no_credentials(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        assert _has_gemini_credentials() is False

    def test_api_key_only(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        assert _has_gemini_credentials() is True

    def test_project_only(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
        assert _has_gemini_credentials() is True

    def test_both(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
        assert _has_gemini_credentials() is True


# ── _has_confluence_credentials helper ──────────────────────────────


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


# ── _has_jira_credentials helper ────────────────────────────────────


class TestHasJiraCredentials:

    def test_all_set(self, monkeypatch):
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        assert _has_jira_credentials() is True

    def test_missing(self, monkeypatch):
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        assert _has_jira_credentials() is False


# ── _print_delivery_status ───────────────────────────────────────────


class TestPrintDeliveryStatus:
    """Tests for _print_delivery_status."""

    def test_prints_with_orchestrator_prefix(self, capsys):
        _print_delivery_status("Hello world")
        captured = capsys.readouterr().out
        assert "[Orchestrator]" in captured
        assert "Hello world" in captured

    def test_prints_newline(self, capsys):
        _print_delivery_status("msg")
        assert capsys.readouterr().out.endswith("\n")
