"""Tests for the orchestrator credential helpers with MongoDB fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestHasConfluenceCredentials:
    def test_env_vars_only(self, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_confluence_credentials,
        )

        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@x.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "tok")

        assert _has_confluence_credentials() is True

    def test_missing_env_vars(self, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_confluence_credentials,
        )

        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)

        assert _has_confluence_credentials() is False

    @patch(
        "crewai_productfeature_planner.orchestrator._helpers._load_atlassian_from_db",
        return_value={
            "base_url": "https://db.atlassian.net",
            "username": "db-user@x.com",
            "api_token": "db-tok",
            "confluence_base_url": "",
            "jira_project_key": "",
        },
    )
    def test_reads_from_db_when_org_provided(self, mock_load, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_confluence_credentials,
        )

        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        assert _has_confluence_credentials(organization_id="org-1") is True
        mock_load.assert_called_once_with("org-1")

    @patch(
        "crewai_productfeature_planner.orchestrator._helpers._load_atlassian_from_db",
        return_value=None,
    )
    def test_falls_back_to_env_when_db_returns_none(self, mock_load, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_confluence_credentials,
        )

        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://env.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "env-user@x.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "env-tok")

        assert _has_confluence_credentials(organization_id="org-1") is True
        mock_load.assert_called_once_with("org-1")


class TestHasJiraCredentials:
    def test_env_vars_only(self, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_jira_credentials,
        )

        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@x.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "tok")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRJ")

        assert _has_jira_credentials() is True

    def test_missing_project_key(self, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_jira_credentials,
        )

        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "user@x.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "tok")
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        assert _has_jira_credentials() is False

    @patch(
        "crewai_productfeature_planner.orchestrator._helpers._load_atlassian_from_db",
        return_value={
            "base_url": "https://db.atlassian.net",
            "username": "db-user@x.com",
            "api_token": "db-tok",
            "confluence_base_url": "",
            "jira_project_key": "PRJ",
        },
    )
    def test_reads_jira_from_db(self, mock_load, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_jira_credentials,
        )

        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        assert _has_jira_credentials(organization_id="org-1") is True

    @patch(
        "crewai_productfeature_planner.orchestrator._helpers._load_atlassian_from_db",
        return_value={
            "base_url": "https://db.atlassian.net",
            "username": "db-user@x.com",
            "api_token": "db-tok",
            "confluence_base_url": "",
            "jira_project_key": "",
        },
    )
    def test_jira_false_when_no_project_key_in_db(self, mock_load, monkeypatch):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_jira_credentials,
        )

        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        assert _has_jira_credentials(organization_id="org-1") is False


class TestLoadAtlassianFromDb:
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.decrypt_value", side_effect=lambda x: x)
    def test_loads_from_db(self, _dec, mock_db):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _load_atlassian_from_db,
        )

        mock_col = MagicMock()
        mock_col.find_one.return_value = {
            "organization_id": "org-1",
            "provider": "atlassian",
            "credentials": {
                "base_url": "https://db.atlassian.net",
                "username": "db-user",
                "api_token": "db-tok",
            },
            "confluence_base_url": "https://db-confluence.atlassian.net",
            "jira_project_key": "PRJ",
        }
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = _load_atlassian_from_db("org-1")
        assert result is not None
        assert result["base_url"] == "https://db.atlassian.net"
        assert result["jira_project_key"] == "PRJ"

    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_returns_none_when_not_found(self, mock_db):
        from crewai_productfeature_planner.orchestrator._helpers import (
            _load_atlassian_from_db,
        )

        mock_col = MagicMock()
        mock_col.find_one.return_value = None
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = _load_atlassian_from_db("org-999")
        assert result is None
