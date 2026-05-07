"""Tests for Jira reconciliation background service."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.services.jira_reconciliation import (
    _calculate_overall_completion,
    _get_jira_client,
    _reconcile_idea_features,
    is_enabled,
)


class TestIsEnabled:
    def test_enabled_true(self):
        with patch.dict("os.environ", {"FEATURE_JIRA_RECONCILIATION": "true"}):
            assert is_enabled() is True

    def test_enabled_1(self):
        with patch.dict("os.environ", {"FEATURE_JIRA_RECONCILIATION": "1"}):
            assert is_enabled() is True

    def test_disabled_empty(self):
        with patch.dict("os.environ", {"FEATURE_JIRA_RECONCILIATION": ""}):
            assert is_enabled() is False

    def test_disabled_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            assert is_enabled() is False

    def test_disabled_false(self):
        with patch.dict("os.environ", {"FEATURE_JIRA_RECONCILIATION": "false"}):
            assert is_enabled() is False


class TestGetJiraClient:
    def test_returns_client_when_configured(self):
        env = {
            "JIRA_BASE_URL": "https://company.atlassian.net",
            "JIRA_USER_EMAIL": "bot@company.com",
            "JIRA_API_TOKEN": "secret-token",
        }
        with patch.dict("os.environ", env):
            client = _get_jira_client()
            assert client is not None
            assert client["base_url"] == "https://company.atlassian.net"
            assert client["auth"] == ("bot@company.com", "secret-token")

    def test_returns_none_when_missing_url(self):
        env = {
            "JIRA_BASE_URL": "",
            "JIRA_USER_EMAIL": "bot@company.com",
            "JIRA_API_TOKEN": "secret-token",
        }
        with patch.dict("os.environ", env):
            assert _get_jira_client() is None

    def test_returns_none_when_missing_token(self):
        env = {
            "JIRA_BASE_URL": "https://company.atlassian.net",
            "JIRA_USER_EMAIL": "bot@company.com",
            "JIRA_API_TOKEN": "",
        }
        with patch.dict("os.environ", env):
            assert _get_jira_client() is None

    def test_strips_trailing_slash(self):
        env = {
            "JIRA_BASE_URL": "https://company.atlassian.net/",
            "JIRA_USER_EMAIL": "bot@company.com",
            "JIRA_API_TOKEN": "token",
        }
        with patch.dict("os.environ", env):
            client = _get_jira_client()
            assert client["base_url"] == "https://company.atlassian.net"


class TestCalculateOverallCompletion:
    def test_empty_features(self):
        assert _calculate_overall_completion([]) == 0.0

    def test_single_feature(self):
        assert _calculate_overall_completion([{"completion_pct": 75.0}]) == 75.0

    def test_multiple_features(self):
        features = [
            {"completion_pct": 100.0},
            {"completion_pct": 50.0},
            {"completion_pct": 0.0},
        ]
        # (100 + 50 + 0) / 3 = 50.0
        assert _calculate_overall_completion(features) == 50.0

    def test_missing_completion_defaults_to_zero(self):
        features = [{"completion_pct": 80.0}, {}]
        # (80 + 0) / 2 = 40.0
        assert _calculate_overall_completion(features) == 40.0


class TestReconcileIdeaFeatures:
    @pytest.mark.asyncio
    async def test_updates_changed_statuses(self):
        """When Jira returns new status, feature completion is updated."""
        jira_client = {"base_url": "https://x.atlassian.net", "auth": ("u", "t")}
        features = [
            {
                "id": "f1",
                "completion_pct": 0.0,
                "jira_issues": [
                    {"key": "PROJ-1", "status": "in progress"},
                    {"key": "PROJ-2", "status": "to do"},
                ],
            }
        ]

        # Mock _fetch_issue_statuses to return both as done
        with patch(
            "crewai_productfeature_planner.services.jira_reconciliation._fetch_issue_statuses",
            return_value={"PROJ-1": "done", "PROJ-2": "done"},
        ), patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.update_features",
        ) as mock_update_feat, patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.update_overall_completion",
        ) as mock_update_overall:
            result = await _reconcile_idea_features(jira_client, "idea-123", features)

        assert result is True
        assert features[0]["completion_pct"] == 100.0
        mock_update_feat.assert_called_once_with(idea_id="idea-123", features=features)
        mock_update_overall.assert_called_once_with(
            idea_id="idea-123", overall_completion=100.0
        )

    @pytest.mark.asyncio
    async def test_no_change_returns_false(self):
        """When statuses haven't changed, no update happens."""
        jira_client = {"base_url": "https://x.atlassian.net", "auth": ("u", "t")}
        features = [
            {
                "id": "f1",
                "completion_pct": 50.0,
                "jira_issues": [
                    {"key": "PROJ-1", "status": "done"},
                    {"key": "PROJ-2", "status": "in progress"},
                ],
            }
        ]

        # Return same statuses
        with patch(
            "crewai_productfeature_planner.services.jira_reconciliation._fetch_issue_statuses",
            return_value={"PROJ-1": "done", "PROJ-2": "in progress"},
        ):
            result = await _reconcile_idea_features(jira_client, "idea-123", features)

        assert result is False

    @pytest.mark.asyncio
    async def test_empty_fetch_skips(self):
        """When Jira API returns empty, no update happens."""
        jira_client = {"base_url": "https://x.atlassian.net", "auth": ("u", "t")}
        features = [
            {
                "id": "f1",
                "jira_issues": [{"key": "PROJ-1", "status": "to do"}],
            }
        ]

        with patch(
            "crewai_productfeature_planner.services.jira_reconciliation._fetch_issue_statuses",
            return_value={},
        ):
            result = await _reconcile_idea_features(jira_client, "idea-123", features)

        assert result is False

    @pytest.mark.asyncio
    async def test_partial_done_calculates_correctly(self):
        """Feature with 3 issues, 1 done → 33.3%."""
        jira_client = {"base_url": "https://x.atlassian.net", "auth": ("u", "t")}
        features = [
            {
                "id": "f1",
                "completion_pct": 0.0,
                "jira_issues": [
                    {"key": "P-1", "status": "to do"},
                    {"key": "P-2", "status": "to do"},
                    {"key": "P-3", "status": "to do"},
                ],
            }
        ]

        with patch(
            "crewai_productfeature_planner.services.jira_reconciliation._fetch_issue_statuses",
            return_value={"P-1": "done", "P-2": "in progress", "P-3": "to do"},
        ), patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.update_features",
        ), patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.update_overall_completion",
        ):
            result = await _reconcile_idea_features(jira_client, "idea-1", features)

        assert result is True
        assert features[0]["completion_pct"] == 33.3


class TestReconcileAll:
    @pytest.mark.asyncio
    async def test_no_ideas_skips(self):
        """When no ideas have Jira features, logs debug and returns."""
        from crewai_productfeature_planner.services.jira_reconciliation import (
            _reconcile_all,
        )

        mock_col = MagicMock()
        mock_col.find.return_value = []

        with patch(
            "crewai_productfeature_planner.mongodb.ideas.repository._col",
            return_value=mock_col,
        ), patch(
            "crewai_productfeature_planner.services.jira_reconciliation._get_jira_client",
            return_value={"base_url": "x", "auth": ("u", "t")},
        ):
            await _reconcile_all()

    @pytest.mark.asyncio
    async def test_no_jira_client_skips(self):
        """When Jira credentials not configured, skip gracefully."""
        from crewai_productfeature_planner.services.jira_reconciliation import (
            _reconcile_all,
        )

        mock_col = MagicMock()
        mock_col.find.return_value = [
            {"idea_id": "x", "features": [{"jira_issues": [{"key": "K-1"}]}]}
        ]

        with patch(
            "crewai_productfeature_planner.mongodb.ideas.repository._col",
            return_value=mock_col,
        ), patch(
            "crewai_productfeature_planner.services.jira_reconciliation._get_jira_client",
            return_value=None,
        ):
            await _reconcile_all()
