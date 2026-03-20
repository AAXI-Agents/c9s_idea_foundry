"""Tests for orchestrator._helpers — credential checks and CLI output."""

from unittest.mock import MagicMock

from crewai_productfeature_planner.orchestrator._helpers import (
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    _print_delivery_status,
    build_additional_prd_context_from_doc,
    build_additional_prd_context_from_draft,
    make_page_title,
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
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
        assert _has_confluence_credentials() is True

    def test_true_without_space_key(self, monkeypatch):
        """space_key is not required — it can come from projectConfig."""
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.delenv("CONFLUENCE_SPACE_KEY", raising=False)
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


# ── build_additional_prd_context_from_draft ──────────────────────────


class TestBuildAdditionalPrdContextFromDraft:

    def _make_draft(self, sections: dict[str, str]):
        """Create a mock PRDDraft with the given section key→content."""
        draft = MagicMock()

        def _get_section(key):
            if key in sections:
                sec = MagicMock()
                sec.content = sections[key]
                return sec
            return None

        draft.get_section = _get_section
        return draft

    def test_empty_draft(self):
        draft = self._make_draft({})
        assert build_additional_prd_context_from_draft(draft) == ""

    def test_single_section(self):
        draft = self._make_draft({
            "edge_cases": "Handle empty input gracefully",
        })
        result = build_additional_prd_context_from_draft(draft)
        assert "Additional PRD Context" in result
        assert "Edge Cases" in result
        assert "Handle empty input gracefully" in result

    def test_multiple_sections(self):
        draft = self._make_draft({
            "no_functional_requirements": "99.9% uptime SLA",
            "edge_cases": "Empty arrays",
            "error_handling": "Return 500 on unhandled exceptions",
        })
        result = build_additional_prd_context_from_draft(draft)
        assert "Non-Functional Requirements" in result
        assert "99.9% uptime SLA" in result
        assert "Edge Cases" in result
        assert "Error Handling" in result

    def test_ignores_empty_content(self):
        draft = self._make_draft({
            "edge_cases": "",
            "error_handling": "  ",
        })
        assert build_additional_prd_context_from_draft(draft) == ""

    def test_includes_user_personas(self):
        draft = self._make_draft({
            "user_personas": "Admin user, regular user, guest",
        })
        result = build_additional_prd_context_from_draft(draft)
        assert "User Personas" in result

    def test_includes_dependencies(self):
        draft = self._make_draft({
            "dependencies": "Requires Redis for caching",
        })
        result = build_additional_prd_context_from_draft(draft)
        assert "Dependencies" in result


# ── build_additional_prd_context_from_doc ────────────────────────────


class TestBuildAdditionalPrdContextFromDoc:

    def test_empty_doc(self):
        assert build_additional_prd_context_from_doc({}) == ""

    def test_no_section_key(self):
        assert build_additional_prd_context_from_doc({"idea": "test"}) == ""

    def test_invalid_section_type(self):
        assert build_additional_prd_context_from_doc({"section": "not-dict"}) == ""

    def test_single_section_from_doc(self):
        doc = {
            "section": {
                "edge_cases": [
                    {"content": "Old version"},
                    {"content": "Handle null user_id"},
                ],
            },
        }
        result = build_additional_prd_context_from_doc(doc)
        assert "Edge Cases" in result
        assert "Handle null user_id" in result
        # Should use the latest iteration, not the old one
        assert "Old version" not in result

    def test_multiple_sections_from_doc(self):
        doc = {
            "section": {
                "no_functional_requirements": [{"content": "< 200ms p95"}],
                "error_handling": [{"content": "Log all 5xx errors"}],
                "dependencies": [{"content": "MongoDB 7.0+"}],
            },
        }
        result = build_additional_prd_context_from_doc(doc)
        assert "Non-Functional Requirements" in result
        assert "< 200ms p95" in result
        assert "Error Handling" in result
        assert "Dependencies" in result

    def test_ignores_empty_iterations(self):
        doc = {
            "section": {
                "edge_cases": [],
            },
        }
        assert build_additional_prd_context_from_doc(doc) == ""

    def test_ignores_empty_content_in_latest(self):
        doc = {
            "section": {
                "edge_cases": [{"content": ""}],
            },
        }
        assert build_additional_prd_context_from_doc(doc) == ""


# ── make_page_title ──────────────────────────────────────────────────


class TestMakePageTitle:

    def test_returns_idea_text(self):
        assert make_page_title("Build a notification system") == "Build a notification system"

    def test_strips_whitespace(self):
        assert make_page_title("  Spaced idea  ") == "Spaced idea"

    def test_truncates_long_ideas(self):
        long_idea = "A" * 100
        result = make_page_title(long_idea)
        assert len(result) <= 81  # 80 chars + ellipsis
        assert result.endswith("…")

    def test_none_returns_fallback(self):
        assert make_page_title(None) == "Product Requirements"

    def test_empty_string_returns_fallback(self):
        assert make_page_title("") == "Product Requirements"

    def test_whitespace_only_returns_fallback(self):
        assert make_page_title("   ") == "Product Requirements"

    def test_custom_fallback(self):
        assert make_page_title(None, fallback="Untitled") == "Untitled"

    def test_exactly_80_chars_no_truncation(self):
        idea = "A" * 80
        assert make_page_title(idea) == idea
