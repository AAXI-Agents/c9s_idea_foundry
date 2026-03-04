"""Tests for next-step hints after publishing (handle_publish_intent)."""

from unittest.mock import MagicMock, patch

import pytest

_SVC = "crewai_productfeature_planner.apis.publishing.service"


class TestPublishNextStepHint:
    """Verify handle_publish_intent shows Jira skeleton hint when appropriate."""

    def _call(self, conf_result: dict, jira_result: dict) -> str:
        """Run handle_publish_intent and return the summary text posted."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_publish_intent,
        )

        send = MagicMock()
        combined = {"confluence": conf_result, "jira": jira_result}

        with patch(
            f"{_SVC}.publish_all_and_create_tickets",
            return_value=combined,
        ):
            handle_publish_intent("C1", "T1", "U1", send)

        # First call is the ack, second call is the summary
        assert send.run.call_count == 2
        return send.run.call_args_list[1][1]["text"]

    def test_jira_skeleton_hint_when_confluence_published_no_jira(self):
        summary = self._call(
            conf_result={"published": 2, "failed": 0, "results": []},
            jira_result={"completed": 0, "failed": 0, "results": []},
        )
        assert "create jira tickets" in summary
        assert "skeleton" in summary.lower()
        assert "Epics" in summary

    def test_no_jira_hint_when_both_succeeded(self):
        summary = self._call(
            conf_result={"published": 1, "failed": 0, "results": []},
            jira_result={"completed": 1, "failed": 0, "results": [{"run_id": "abc12345", "ticket_keys": ["PROJ-1"]}]},
        )
        assert "skeleton" not in summary.lower()

    def test_no_jira_hint_when_confluence_not_published(self):
        summary = self._call(
            conf_result={"published": 0, "failed": 0, "message": "No pending PRDs"},
            jira_result={"completed": 0, "failed": 0, "message": "No pending Jira deliveries"},
        )
        assert "skeleton" not in summary.lower()

    def test_jira_hint_only_shows_with_conf_success_jira_zero(self):
        """Hint appears only when Confluence published > 0 and Jira completed == 0."""
        summary = self._call(
            conf_result={"published": 3, "failed": 0, "results": []},
            jira_result={"completed": 0, "failed": 0, "results": [], "message": "No pending Jira deliveries"},
        )
        assert "create jira tickets" in summary
        assert "review and approval" in summary.lower()
