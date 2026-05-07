"""Tests for the knowledge context service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from crewai_productfeature_planner.services.knowledge_context import (
    build_knowledge_context,
    _fetch_knowledge_summary,
    _fetch_repo_blurbs,
)


class TestBuildKnowledgeContext:
    """Tests for build_knowledge_context()."""

    def test_empty_project_id_returns_empty(self):
        assert build_knowledge_context("") == ""
        assert build_knowledge_context(None) == ""

    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_knowledge_summary"
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_repo_blurbs"
    )
    def test_no_knowledge_returns_empty(self, mock_repos, mock_summary):
        mock_summary.return_value = ""
        mock_repos.return_value = ""
        result = build_knowledge_context("proj-123")
        assert result == ""

    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_knowledge_summary"
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_repo_blurbs"
    )
    def test_summary_only(self, mock_repos, mock_summary):
        mock_summary.return_value = "### Knowledge Summary\n\nSome summary"
        mock_repos.return_value = ""
        result = build_knowledge_context("proj-123")
        assert "## Project Knowledge Context" in result
        assert "Knowledge Summary" in result
        assert "Some summary" in result

    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_knowledge_summary"
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_repo_blurbs"
    )
    def test_repos_only(self, mock_repos, mock_summary):
        mock_summary.return_value = ""
        mock_repos.return_value = "### Code Repository Context\n\n**org/repo**\n  FastAPI app"
        result = build_knowledge_context("proj-123")
        assert "## Project Knowledge Context" in result
        assert "Code Repository Context" in result

    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_knowledge_summary"
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_repo_blurbs"
    )
    def test_both_combined(self, mock_repos, mock_summary):
        mock_summary.return_value = "### Knowledge Summary\n\nUnified view"
        mock_repos.return_value = "### Code Repository Context\n\n**org/repo**"
        result = build_knowledge_context("proj-123")
        assert "Knowledge Summary" in result
        assert "Code Repository Context" in result

    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_knowledge_summary"
    )
    @patch(
        "crewai_productfeature_planner.services.knowledge_context._fetch_repo_blurbs"
    )
    def test_truncation_on_overflow(self, mock_repos, mock_summary):
        mock_summary.return_value = "x" * 20000
        mock_repos.return_value = ""
        result = build_knowledge_context("proj-123")
        assert result.endswith("[...truncated]")
        assert len(result) <= 16000 + 50  # header + truncation marker


class TestFetchKnowledgeSummary:
    """Tests for _fetch_knowledge_summary()."""

    @patch(
        "crewai_productfeature_planner.services.knowledge_context.get_knowledge_summary",
        create=True,
    )
    def test_no_doc_returns_empty(self, mock_get):
        # Patch at module level after import
        with patch(
            "crewai_productfeature_planner.mongodb.knowledge_summaries.get_knowledge_summary",
            return_value=None,
        ):
            result = _fetch_knowledge_summary("proj-123")
            assert result == ""

    def test_no_summary_content_returns_empty(self):
        with patch(
            "crewai_productfeature_planner.mongodb.knowledge_summaries.get_knowledge_summary",
            return_value={"unified_summary": "", "unified_bullets": []},
        ):
            result = _fetch_knowledge_summary("proj-123")
            assert result == ""

    def test_summary_with_bullets(self):
        doc = {
            "unified_summary": "The product does X and Y.",
            "unified_bullets": ["Point A", "Point B", "Point C"],
            "contradictions": [
                {
                    "claim_a": "Uses REST",
                    "claim_b": "Uses GraphQL",
                    "severity": "medium",
                }
            ],
        }
        with patch(
            "crewai_productfeature_planner.mongodb.knowledge_summaries.get_knowledge_summary",
            return_value=doc,
        ):
            result = _fetch_knowledge_summary("proj-123")
            assert "The product does X and Y." in result
            assert "- Point A" in result
            assert "- Point B" in result
            assert "Contradictions Detected" in result
            assert "Uses REST" in result

    def test_exception_returns_empty(self):
        with patch(
            "crewai_productfeature_planner.mongodb.knowledge_summaries.get_knowledge_summary",
            side_effect=RuntimeError("DB down"),
        ):
            result = _fetch_knowledge_summary("proj-123")
            assert result == ""


class TestFetchRepoBlurbs:
    """Tests for _fetch_repo_blurbs()."""

    def test_no_repos_returns_empty(self):
        with patch(
            "crewai_productfeature_planner.mongodb.code_repos.list_code_repos",
            return_value=[],
        ):
            result = _fetch_repo_blurbs("proj-123")
            assert result == ""

    def test_no_ready_repos_returns_empty(self):
        repos = [
            {"status": "pending", "analysis": None, "owner": "o", "name": "r"},
            {"status": "cloning", "analysis": None, "owner": "o", "name": "r2"},
        ]
        with patch(
            "crewai_productfeature_planner.mongodb.code_repos.list_code_repos",
            return_value=repos,
        ):
            result = _fetch_repo_blurbs("proj-123")
            assert result == ""

    def test_ready_repos_with_blurbs(self):
        repos = [
            {
                "status": "ready",
                "owner": "acme",
                "name": "backend",
                "analysis": {
                    "architecture_blurb": "FastAPI monolith with layered design",
                    "primary_language": "Python",
                    "frameworks": ["FastAPI", "SQLAlchemy"],
                },
            },
            {
                "status": "ready",
                "owner": "acme",
                "name": "frontend",
                "analysis": {
                    "architecture_blurb": "Next.js app with React",
                    "primary_language": "TypeScript",
                    "frameworks": ["Next.js", "React"],
                },
            },
        ]
        with patch(
            "crewai_productfeature_planner.mongodb.code_repos.list_code_repos",
            return_value=repos,
        ):
            result = _fetch_repo_blurbs("proj-123")
            assert "**acme/backend**" in result
            assert "FastAPI monolith" in result
            assert "**acme/frontend**" in result
            assert "Next.js app" in result
            assert "Language: Python" in result

    def test_repos_without_blurb_skipped(self):
        repos = [
            {
                "status": "ready",
                "owner": "acme",
                "name": "empty",
                "analysis": {
                    "architecture_blurb": "",
                    "primary_language": "Go",
                },
            },
        ]
        with patch(
            "crewai_productfeature_planner.mongodb.code_repos.list_code_repos",
            return_value=repos,
        ):
            result = _fetch_repo_blurbs("proj-123")
            assert result == ""  # Only header, no content → empty

    def test_exception_returns_empty(self):
        with patch(
            "crewai_productfeature_planner.mongodb.code_repos.list_code_repos",
            side_effect=RuntimeError("DB error"),
        ):
            result = _fetch_repo_blurbs("proj-123")
            assert result == ""
