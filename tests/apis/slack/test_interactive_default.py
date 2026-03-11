"""Tests for interactive-by-default create_prd routing.

The interactive mode is the default when a user creates a PRD via Slack.
Only when the user explicitly says "auto", "fast", "quick", etc. does
the flow run in auto-approve mode.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack import events_router as er


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _clean():
    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    er._bot_user_id = None
    yield


_EVENTS = "crewai_productfeature_planner.apis.slack.events_router"
_TOOLS = "crewai_productfeature_planner.tools.slack_tools"
_SESSION = "crewai_productfeature_planner.apis.slack.session_manager"

_ACTIVE_SESSION = {
    "project_id": "proj-1",
    "project_name": "Test",
    "active": True,
}


def _run(text: str, idea: str = "build a dashboard"):
    """Call _interpret_and_act with the given text and capture the kickoff kwargs."""
    interpretation = json.dumps({
        "intent": "create_prd",
        "idea": idea,
        "reply": "",
    })
    mock_interpret = MagicMock()
    mock_interpret.run.return_value = interpretation
    mock_send = MagicMock()
    mock_kickoff = MagicMock()
    mock_log = MagicMock()

    with (
        patch(f"{_TOOLS}.SlackInterpretMessageTool",
              return_value=mock_interpret),
        patch(f"{_TOOLS}.SlackSendMessageTool",
              return_value=mock_send),
        patch(f"{_EVENTS}._kick_off_prd_flow", mock_kickoff),
        patch(
            "crewai_productfeature_planner.mongodb.agent_interactions"
            ".repository.log_interaction",
            mock_log,
        ),
        patch(f"{_SESSION}.get_context_session",
              return_value=_ACTIVE_SESSION),
    ):
        er._interpret_and_act("C1", "T1", "U1", text, "E1")

    return mock_kickoff, mock_send, mock_log


class TestInteractiveDefault:
    """Interactive mode is the default for create_prd."""

    def test_plain_create_is_interactive(self):
        kickoff, send, _ = _run("create prd for build a dashboard")
        kickoff.assert_called_once()
        assert kickoff.call_args[1]["interactive"] is True

    def test_ack_text_interactive(self):
        _, send, _ = _run("create prd for build a dashboard")
        ack = send.run.call_args[1]["text"]
        assert "interactive" in ack.lower()

    @pytest.mark.parametrize("text", [
        "auto create prd for build a dashboard",
        "fast create prd for build a dashboard",
        "quick create prd for build a dashboard",
        "create prd auto-approve for build a dashboard",
        "create prd with no approval for build a dashboard",
    ])
    def test_keyword_disables_interactive(self, text):
        kickoff, _, _ = _run(text)
        kickoff.assert_called_once()
        assert kickoff.call_args[1]["interactive"] is False

    def test_ack_text_auto_mode(self):
        _, send, _ = _run("auto create prd for build a dashboard")
        ack = send.run.call_args[1]["text"]
        assert "results here when done" in ack

    def test_metadata_records_interactive_true(self):
        _, _, log = _run("create prd for build a dashboard")
        log.assert_called_once()
        meta = log.call_args[1]["metadata"]
        assert meta["interactive"] is True

    def test_metadata_records_interactive_false(self):
        _, _, log = _run("auto create prd for build a dashboard")
        log.assert_called_once()
        meta = log.call_args[1]["metadata"]
        assert meta["interactive"] is False
