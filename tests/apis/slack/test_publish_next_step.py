"""Tests for next-step hints after publishing (handle_publish_intent)."""

from unittest.mock import MagicMock, patch

import pytest

_SVC = "crewai_productfeature_planner.apis.publishing.service"
_SLACK_TOOLS = "crewai_productfeature_planner.tools.slack_tools"


class TestPublishNextStepHint:
    """Verify handle_publish_intent shows Jira button when appropriate."""

    def _call(self, conf_result: dict, jira_result: dict):
        """Run handle_publish_intent and return (summary_text, mock_client)."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_publish_intent,
        )

        send = MagicMock()
        mock_client = MagicMock()
        combined = {"confluence": conf_result, "jira": jira_result}

        with (
            patch(f"{_SVC}.publish_all_and_create_tickets", return_value=combined),
            patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=mock_client),
        ):
            handle_publish_intent("C1", "T1", "U1", send)

        # First call is the ack, second call is the summary
        assert send.run.call_count == 2
        summary = send.run.call_args_list[1][1]["text"]
        return summary, mock_client

    def test_jira_button_when_confluence_published_no_jira(self):
        """When conf published > 0 and jira == 0, a Jira button is posted."""
        summary, mock_client = self._call(
            conf_result={
                "published": 2,
                "failed": 0,
                "results": [{"run_id": "run123", "title": "T", "url": "http://x"}],
            },
            jira_result={"completed": 0, "failed": 0, "results": []},
        )
        # The summary should NOT contain the old text-based "create jira" hint
        assert "Say" not in summary
        # A Jira button should be posted via chat_postMessage
        mock_client.chat_postMessage.assert_called_once()
        call_kw = mock_client.chat_postMessage.call_args[1]
        assert call_kw["channel"] == "C1"
        assert call_kw["thread_ts"] == "T1"
        # Blocks should contain a button with action_id delivery_create_jira
        blocks = call_kw.get("blocks", [])
        action_ids = [
            el.get("action_id", "")
            for blk in blocks
            for el in (blk.get("elements", []))
        ]
        assert "delivery_create_jira" in action_ids

    def test_no_jira_button_when_no_conf_results(self):
        """No Jira button when conf results list is empty (no run_id to bind)."""
        summary, mock_client = self._call(
            conf_result={"published": 2, "failed": 0, "results": []},
            jira_result={"completed": 0, "failed": 0, "results": []},
        )
        mock_client.chat_postMessage.assert_not_called()

    def test_no_jira_button_when_both_succeeded(self):
        summary, mock_client = self._call(
            conf_result={"published": 1, "failed": 0, "results": []},
            jira_result={"completed": 1, "failed": 0, "results": [{"run_id": "abc12345", "ticket_keys": ["PROJ-1"]}]},
        )
        mock_client.chat_postMessage.assert_not_called()

    def test_no_jira_button_when_confluence_not_published(self):
        summary, mock_client = self._call(
            conf_result={"published": 0, "failed": 0, "message": "No pending PRDs"},
            jira_result={"completed": 0, "failed": 0, "message": "No pending Jira deliveries"},
        )
        mock_client.chat_postMessage.assert_not_called()
