"""Tests for next-step hints after publishing (handle_publish_intent).

As of v0.71.0, Jira buttons are no longer offered after Confluence
publishing — jira_only_blocks returns [].
"""

from unittest.mock import MagicMock, patch

import pytest

_SVC = "crewai_productfeature_planner.apis.publishing.service"
_SLACK_TOOLS = "crewai_productfeature_planner.tools.slack_tools"


class TestPublishNextStepHint:
    """Verify handle_publish_intent no longer offers Jira button (v0.71.0)."""

    def _call(self, conf_result: dict):
        """Run handle_publish_intent and return (summary_text, mock_client)."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_publish_intent,
        )

        send = MagicMock()
        mock_client = MagicMock()

        with (
            patch(f"{_SVC}.publish_confluence_all", return_value=conf_result),
            patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=mock_client),
        ):
            handle_publish_intent("C1", "T1", "U1", send)

        # First call is the ack, second call is the summary
        assert send.run.call_count == 2
        summary = send.run.call_args_list[1][1]["text"]
        return summary, mock_client

    def test_no_jira_button_when_confluence_published(self):
        """When conf published > 0, NO Jira button is posted (removed in v0.71.0)."""
        summary, mock_client = self._call(
            conf_result={
                "published": 2,
                "failed": 0,
                "results": [{"run_id": "run123", "title": "T", "url": "http://x"}],
            },
        )
        assert "Say" not in summary
        # jira_only_blocks returns [] now, so no chat_postMessage call for Jira
        mock_client.chat_postMessage.assert_not_called()

    def test_no_jira_button_when_no_conf_results(self):
        """No Jira button when conf results list is empty (no run_id to bind)."""
        summary, mock_client = self._call(
            conf_result={"published": 2, "failed": 0, "results": []},
        )
        mock_client.chat_postMessage.assert_not_called()

    def test_no_jira_button_when_confluence_not_published(self):
        summary, mock_client = self._call(
            conf_result={"published": 0, "failed": 0, "message": "No pending PRDs"},
        )
        mock_client.chat_postMessage.assert_not_called()
