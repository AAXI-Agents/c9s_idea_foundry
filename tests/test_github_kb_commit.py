"""Tests for GitHub service KB commit functionality."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.services.github_service import (
    _build_kb_path,
    _format_detail,
    _get_file_sha,
    commit_to_kb_repo,
)


class TestBuildKbPath:
    def test_standard_path(self):
        result = _build_kb_path("cloudninesoftware", "my-project", "my-repo")
        assert result == "enterprises/cloudninesoftware/projects/my-project/repos/my-repo/"

    def test_with_different_slugs(self):
        result = _build_kb_path("acme", "foo-bar", "backend-api")
        assert result == "enterprises/acme/projects/foo-bar/repos/backend-api/"


class TestFormatDetail:
    def test_string_value(self):
        assert _format_detail("some text") == "some text"

    def test_list_value(self):
        result = _format_detail(["item1", "item2"])
        assert result == "- item1\n- item2"

    def test_empty_value(self):
        assert _format_detail("") == "(not available)"
        assert _format_detail(None) == "(not available)"


class TestCommitToKbRepo:
    """Tests for commit_to_kb_repo()."""

    def test_no_pat_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            result = commit_to_kb_repo(
                repo_name="test-repo",
                repo_owner="org",
                repo_url="https://github.com/org/test-repo",
                project_slug="my-project",
                tenant_slug="cloudninesoftware",
                analysis={"primary_language": "Python"},
            )
            assert result is False

    @patch("crewai_productfeature_planner.services.github_service._get_file_sha")
    @patch("httpx.Client")
    def test_successful_commit(self, mock_client_cls, mock_get_sha):
        """Files are committed via GitHub API."""
        mock_get_sha.return_value = None  # New files (no existing SHA)

        # Mock httpx client
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with patch.dict("os.environ", {"GITHUB_KB_PAT": "ghp_test123"}):
            result = commit_to_kb_repo(
                repo_name="backend",
                repo_owner="acme",
                repo_url="https://github.com/acme/backend",
                project_slug="my-project",
                tenant_slug="cloudninesoftware",
                analysis={
                    "primary_language": "Python",
                    "frameworks": ["FastAPI", "SQLAlchemy"],
                    "architecture_blurb": "Layered FastAPI monolith",
                    "api_endpoints_count": 15,
                    "schema_entities_count": 8,
                    "dependencies_count": 42,
                },
                commit_sha="abc123def",
            )

        assert result is True
        # Should have committed 8 files (one per template)
        assert mock_client.put.call_count == 8

        # Verify the first call's URL and content
        first_call = mock_client.put.call_args_list[0]
        url = first_call[0][0]
        assert "enterprises/cloudninesoftware/projects/my-project/repos/backend/" in url

        # Verify commit message
        payload = first_call[1]["json"]
        assert "chore(kb): refresh my-project/backend @ abc123d" in payload["message"]
        assert "content" in payload
        assert "branch" in payload

    @patch("crewai_productfeature_planner.services.github_service._get_file_sha")
    @patch("httpx.Client")
    def test_update_existing_file_includes_sha(self, mock_client_cls, mock_get_sha):
        """Updating existing files includes the file SHA."""
        mock_get_sha.return_value = "existing_sha_abc123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with patch.dict("os.environ", {"GITHUB_KB_PAT": "ghp_test123"}):
            commit_to_kb_repo(
                repo_name="repo",
                repo_owner="org",
                repo_url="https://github.com/org/repo",
                project_slug="proj",
                tenant_slug="tenant",
                analysis={"primary_language": "Go"},
            )

        # Verify SHA is included in payload
        first_call = mock_client.put.call_args_list[0]
        payload = first_call[1]["json"]
        assert payload["sha"] == "existing_sha_abc123"

    @patch("crewai_productfeature_planner.services.github_service._get_file_sha")
    @patch("httpx.Client")
    def test_partial_failure_still_returns_true(self, mock_client_cls, mock_get_sha):
        """If some files fail, returns True if at least one succeeded."""
        mock_get_sha.return_value = None

        # First call succeeds, rest fail
        success_resp = MagicMock(status_code=201)
        fail_resp = MagicMock(status_code=422, text="conflict")
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put.side_effect = [success_resp] + [fail_resp] * 7
        mock_client_cls.return_value = mock_client

        with patch.dict("os.environ", {"GITHUB_KB_PAT": "ghp_test123"}):
            result = commit_to_kb_repo(
                repo_name="repo",
                repo_owner="org",
                repo_url="https://github.com/org/repo",
                project_slug="proj",
                tenant_slug="tenant",
                analysis={"primary_language": "Rust"},
            )

        assert result is True

    @patch("crewai_productfeature_planner.services.github_service._get_file_sha")
    @patch("httpx.Client")
    def test_all_failures_returns_false(self, mock_client_cls, mock_get_sha):
        """If all files fail, returns False."""
        mock_get_sha.return_value = None

        fail_resp = MagicMock(status_code=500, text="server error")
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put.return_value = fail_resp
        mock_client_cls.return_value = mock_client

        with patch.dict("os.environ", {"GITHUB_KB_PAT": "ghp_test123"}):
            result = commit_to_kb_repo(
                repo_name="repo",
                repo_owner="org",
                repo_url="https://github.com/org/repo",
                project_slug="proj",
                tenant_slug="tenant",
                analysis={"primary_language": "Java"},
            )

        assert result is False

    def test_obsidian_format_compliance(self):
        """Generated files have YAML frontmatter and wiki-links."""
        from crewai_productfeature_planner.services.github_service import (
            _KB_FILES_TEMPLATE,
        )

        format_vars = {
            "repo_name": "test-repo",
            "repo_owner": "org",
            "repo_url": "https://github.com/org/test-repo",
            "primary_language": "Python",
            "frameworks": "FastAPI, React",
            "analyzed_at": "2026-05-07 12:00 UTC",
            "architecture_blurb": "Monolith architecture",
            "api_endpoints_count": 10,
            "schema_entities_count": 5,
            "dependencies_count": 30,
            "api_details": "- GET /health",
            "schema_details": "- User entity",
            "dependencies_details": "- fastapi==0.100",
            "frameworks_details": "- FastAPI (web)",
            "third_party_details": "- Stripe (payments)",
            "queries_details": "- Users by email",
        }

        for filename, template in _KB_FILES_TEMPLATE.items():
            content = template.format(**format_vars)
            # All files start with YAML frontmatter
            assert content.startswith("---\n"), f"{filename} missing frontmatter"
            assert "\n---\n" in content[4:], f"{filename} missing frontmatter close"
            # All files have exactly one H1
            h1_count = content.count("\n# ")
            assert h1_count == 1, f"{filename} has {h1_count} H1 headers"

        # Index file has wiki-links
        index_content = _KB_FILES_TEMPLATE["_index.md"].format(**format_vars)
        assert "[[Architecture]]" in index_content
        assert "[[APIs]]" in index_content
