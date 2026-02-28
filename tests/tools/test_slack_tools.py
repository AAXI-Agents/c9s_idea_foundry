"""Tests for Slack tools (send, read, post PRD result, interpret)."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_slack_env(monkeypatch):
    for key in (
        "SLACK_ACCESS_TOKEN", "SLACK_BYPASS",
        "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REFRESH_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# SlackSendMessageTool
# ---------------------------------------------------------------------------

class TestSlackSendMessageTool:
    def test_bypass_mode(self, monkeypatch):
        monkeypatch.setenv("SLACK_BYPASS", "true")
        from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool

        tool = SlackSendMessageTool()
        result = json.loads(tool.run(channel="C1", text="hello"))
        assert result["status"] == "bypass"
        assert result["channel"] == "C1"

    def test_dry_run_no_token(self):
        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=None,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool

            tool = SlackSendMessageTool()
            result = json.loads(tool.run(channel="C1", text="hello"))
            assert result["status"] == "dry_run"

    def test_sends_message_with_client(self, monkeypatch):
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"channel": "C1", "ts": "1.0"}

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool

            tool = SlackSendMessageTool()
            result = json.loads(tool.run(channel="C1", text="hi", thread_ts="t1"))

        assert result["status"] == "ok"
        mock_client.chat_postMessage.assert_called_once_with(
            channel="C1", text="hi", thread_ts="t1",
        )

    def test_retries_on_token_error(self):
        mock_client = MagicMock()
        mock_client.chat_postMessage.side_effect = Exception("token_expired")

        retry_client = MagicMock()
        retry_client.chat_postMessage.return_value = {"channel": "C1", "ts": "2.0"}

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ), patch(
            "crewai_productfeature_planner.tools.slack_tools._retry_on_token_error",
            return_value=retry_client,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackSendMessageTool

            tool = SlackSendMessageTool()
            result = json.loads(tool.run(channel="C1", text="retry"))

        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# SlackReadMessagesTool
# ---------------------------------------------------------------------------

class TestSlackReadMessagesTool:
    def test_bypass_mode(self, monkeypatch):
        monkeypatch.setenv("SLACK_BYPASS", "true")
        from crewai_productfeature_planner.tools.slack_tools import SlackReadMessagesTool

        tool = SlackReadMessagesTool()
        result = json.loads(tool.run(channel="C1", limit=5))
        assert result["status"] == "bypass"
        assert result["messages"] == []

    def test_reads_channel_history(self):
        mock_client = MagicMock()
        mock_client.conversations_history.return_value = {
            "messages": [
                {"user": "U1", "text": "first", "ts": "1.0"},
                {"user": "U2", "text": "second", "ts": "2.0"},
            ],
        }

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackReadMessagesTool

            tool = SlackReadMessagesTool()
            result = json.loads(tool.run(channel="C1", limit=5))

        assert result["status"] == "ok"
        assert len(result["messages"]) == 2

    def test_reads_thread_replies(self):
        mock_client = MagicMock()
        mock_client.conversations_replies.return_value = {
            "messages": [{"user": "U1", "text": "reply", "ts": "3.0"}],
        }

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackReadMessagesTool

            tool = SlackReadMessagesTool()
            result = json.loads(tool.run(channel="C1", limit=5, thread_ts="2.0"))

        assert result["status"] == "ok"
        mock_client.conversations_replies.assert_called_once()


# ---------------------------------------------------------------------------
# SlackPostPRDResultTool
# ---------------------------------------------------------------------------

class TestSlackPostPRDResultTool:
    def test_bypass_mode(self, monkeypatch):
        monkeypatch.setenv("SLACK_BYPASS", "true")
        from crewai_productfeature_planner.tools.slack_tools import SlackPostPRDResultTool

        tool = SlackPostPRDResultTool()
        result = json.loads(tool.run(channel="C1", idea="test idea"))
        assert result["status"] == "bypass"
        assert len(result["blocks"]) >= 2

    def test_builds_blocks_with_all_fields(self):
        from crewai_productfeature_planner.tools.slack_tools import SlackPostPRDResultTool

        tool = SlackPostPRDResultTool()
        blocks = tool._build_blocks(
            idea="fitness app",
            output_file="/output/prd.md",
            confluence_url="https://confluence.test/page",
            jira_output="PROJ-1, PROJ-2",
        )
        text = json.dumps(blocks)
        assert "fitness app" in text
        assert "/output/prd.md" in text
        assert "confluence.test" in text
        assert "PROJ-1" in text

    def test_builds_blocks_minimal(self):
        from crewai_productfeature_planner.tools.slack_tools import SlackPostPRDResultTool

        tool = SlackPostPRDResultTool()
        blocks = tool._build_blocks(
            idea="minimal",
            output_file=None,
            confluence_url=None,
            jira_output=None,
        )
        # Header + idea section + success section = 3
        assert len(blocks) == 3

    def test_sends_blocks_to_slack(self):
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"channel": "C1", "ts": "5.0"}

        with patch(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            return_value=mock_client,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackPostPRDResultTool

            tool = SlackPostPRDResultTool()
            result = json.loads(tool.run(channel="C1", idea="app"))

        assert result["status"] == "ok"
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert "blocks" in call_kwargs


# ---------------------------------------------------------------------------
# SlackInterpretMessageTool
# ---------------------------------------------------------------------------

class TestSlackInterpretMessageTool:
    def test_interprets_message(self):
        mock_result = {"intent": "create_prd", "idea": "fitness app", "reply": "ok"}

        with patch(
            "crewai_productfeature_planner.tools.gemini_chat.interpret_message",
            return_value=mock_result,
        ):
            from crewai_productfeature_planner.tools.slack_tools import SlackInterpretMessageTool

            tool = SlackInterpretMessageTool()
            result = json.loads(tool.run(text="build a fitness app"))

        assert result["intent"] == "create_prd"
        assert result["idea"] == "fitness app"

    def test_passes_conversation_history(self):
        mock_result = {"intent": "greeting", "idea": None, "reply": "hi"}
        history = [{"role": "user", "content": "hi"}]

        with patch(
            "crewai_productfeature_planner.tools.gemini_chat.interpret_message",
            return_value=mock_result,
        ) as mock_interpret:
            from crewai_productfeature_planner.tools.slack_tools import SlackInterpretMessageTool

            tool = SlackInterpretMessageTool()
            tool.run(text="hey", conversation_history=json.dumps(history))

        mock_interpret.assert_called_once_with("hey", history)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_is_bypass_true(self, monkeypatch):
        from crewai_productfeature_planner.tools.slack_tools import _is_bypass

        monkeypatch.setenv("SLACK_BYPASS", "true")
        assert _is_bypass() is True

    def test_is_bypass_false(self, monkeypatch):
        from crewai_productfeature_planner.tools.slack_tools import _is_bypass

        monkeypatch.delenv("SLACK_BYPASS", raising=False)
        assert _is_bypass() is False

    def test_is_token_error(self):
        from crewai_productfeature_planner.tools.slack_tools import _is_token_error

        assert _is_token_error(Exception("token_expired")) is True
        assert _is_token_error(Exception("invalid_auth")) is True
        assert _is_token_error(Exception("not_authed")) is True
        assert _is_token_error(Exception("random error")) is False
