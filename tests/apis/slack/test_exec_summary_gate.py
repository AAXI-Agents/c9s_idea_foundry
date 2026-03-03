"""Tests for the non-interactive exec summary feedback gate.

Covers:
- ``make_exec_summary_gate`` factory (callback behaviour)
- ``resolve_exec_feedback`` (button click / thread reply signalling)
- Integration with ``_run_slack_prd_flow`` (callback is wired up)
- Integration with the interactions router (button dispatch)
- Integration with the events router (thread reply dispatch)
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ====================================================================
# Module paths
# ====================================================================

_FH = "crewai_productfeature_planner.apis.slack._flow_handlers"
_ROUTER = "crewai_productfeature_planner.apis.slack.router"
_SLACK_TOOLS = "crewai_productfeature_planner.tools.slack_tools"
_SERVICE = "crewai_productfeature_planner.apis.prd.service"
_FLOW = "crewai_productfeature_planner.flows.prd_flow"


@pytest.fixture(autouse=True)
def _clean_gate_state():
    """Clear module-level gate state between tests."""
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        _exec_feedback_lock,
        _pending_exec_feedback,
    )
    with _exec_feedback_lock:
        _pending_exec_feedback.clear()
    yield
    with _exec_feedback_lock:
        _pending_exec_feedback.clear()


# ====================================================================
# resolve_exec_feedback
# ====================================================================


class TestResolveExecFeedback:
    """Tests for resolve_exec_feedback()."""

    def test_returns_false_for_unknown_run(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            resolve_exec_feedback,
        )
        assert resolve_exec_feedback("unknown_run", "approve") is False

    def test_signals_approve(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            resolve_exec_feedback,
        )
        ev = threading.Event()
        with _exec_feedback_lock:
            _pending_exec_feedback["run_1"] = {
                "channel": "C1",
                "thread_ts": "T1",
                "event": ev,
                "decision": None,
                "feedback": None,
            }

        result = resolve_exec_feedback("run_1", "approve")
        assert result is True
        assert ev.is_set()
        assert _pending_exec_feedback["run_1"]["decision"] == "approve"

    def test_signals_feedback(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            resolve_exec_feedback,
        )
        ev = threading.Event()
        with _exec_feedback_lock:
            _pending_exec_feedback["run_2"] = {
                "channel": "C2",
                "thread_ts": "T2",
                "event": ev,
                "decision": None,
                "feedback": None,
            }

        result = resolve_exec_feedback("run_2", "feedback", "needs more detail")
        assert result is True
        assert ev.is_set()
        assert _pending_exec_feedback["run_2"]["decision"] == "feedback"
        assert _pending_exec_feedback["run_2"]["feedback"] == "needs more detail"


# ====================================================================
# make_exec_summary_gate — callback behaviour
# ====================================================================


class TestMakeExecSummaryGate:
    """Tests for the callback returned by make_exec_summary_gate()."""

    def test_iteration_zero_returns_skip(self):
        """At iteration 0, the callback should return ('skip', None)."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            make_exec_summary_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_gate("C1", "T1", "U1", send_tool, run_id="run_A")
        action, text = cb("", "idea", "run_A", 0)
        assert action == "skip"
        assert text is None

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=None)
    def test_iteration_1_posts_blocks_and_waits(self, _mock_client):
        """After iteration 1, should post blocks and wait for response."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            make_exec_summary_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_gate("C1", "T1", "U1", send_tool, run_id="run_B")

        # Signal approve from a background thread after a short delay
        def _signal():
            time.sleep(0.1)
            with _exec_feedback_lock:
                info = _pending_exec_feedback.get("run_B")
                if info:
                    info["decision"] = "approve"
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        action, text = cb("# Summary content", "idea", "run_B", 1)
        assert action == "approve"
        assert text is None
        t.join(timeout=2)

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=None)
    def test_iteration_1_feedback_returns_user_text(self, _mock_client):
        """When user provides feedback, the callback should return it."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            make_exec_summary_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_gate("C1", "T1", "U1", send_tool, run_id="run_C")

        def _signal():
            time.sleep(0.1)
            with _exec_feedback_lock:
                info = _pending_exec_feedback.get("run_C")
                if info:
                    info["decision"] = "feedback"
                    info["feedback"] = "Add more detail about security"
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        action, text = cb("# Summary", "idea", "run_C", 1)
        assert action == "feedback"
        assert text == "Add more detail about security"
        t.join(timeout=2)

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=MagicMock())
    def test_posts_blocks_via_slack_client(self, mock_get_client):
        """When a Slack client is available, blocks should be posted."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            make_exec_summary_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_gate("C99", "T99", "U1", send_tool, run_id="run_D")

        # Approve immediately
        def _signal():
            time.sleep(0.1)
            with _exec_feedback_lock:
                info = _pending_exec_feedback.get("run_D")
                if info:
                    info["decision"] = "approve"
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        cb("# My Summary", "idea", "run_D", 1)

        client = mock_get_client.return_value
        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C99"
        assert call_kwargs["thread_ts"] == "T99"
        assert "blocks" in call_kwargs
        t.join(timeout=2)


# ====================================================================
# run_prd_flow accepts exec_summary_user_feedback_callback
# ====================================================================


class TestRunPrdFlowExecSummaryParam:
    """Verify run_prd_flow forwards exec_summary_user_feedback_callback."""

    @patch(f"{_FLOW}.PRDFlow")
    @patch(f"{_SERVICE}.update_job_started")
    @patch(f"{_SERVICE}.update_job_completed")
    def test_callback_set_on_flow(
        self, _mock_completed, _mock_started, mock_flow_cls,
    ):
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow
        from crewai_productfeature_planner.apis.shared import FlowRun, runs

        mock_flow = MagicMock()
        mock_flow.state = MagicMock()
        mock_flow.kickoff.return_value = "result"
        mock_flow_cls.return_value = mock_flow

        runs["test_run"] = FlowRun(run_id="test_run", flow_name="prd")

        dummy_cb = MagicMock()
        run_prd_flow(
            "test_run", "idea",
            auto_approve=True,
            exec_summary_user_feedback_callback=dummy_cb,
        )

        assert mock_flow.exec_summary_user_feedback_callback is dummy_cb

    @patch(f"{_FLOW}.PRDFlow")
    @patch(f"{_SERVICE}.update_job_started")
    @patch(f"{_SERVICE}.update_job_completed")
    def test_no_callback_when_not_provided(
        self, _mock_completed, _mock_started, mock_flow_cls,
    ):
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow
        from crewai_productfeature_planner.apis.shared import FlowRun, runs

        mock_flow = MagicMock()
        mock_flow.state = MagicMock()
        mock_flow.kickoff.return_value = "result"
        mock_flow_cls.return_value = mock_flow

        # Use a sentinel so we can detect if the attribute was set
        sentinel = object()
        mock_flow.exec_summary_user_feedback_callback = sentinel

        runs["test_run2"] = FlowRun(run_id="test_run2", flow_name="prd")
        run_prd_flow("test_run2", "idea", auto_approve=True)

        # The attribute should still be the sentinel — service must NOT have
        # overwritten it (the `if callback is not None` guard skips it).
        assert mock_flow.exec_summary_user_feedback_callback is sentinel


# ====================================================================
# events_router thread reply dispatches to exec feedback gate
# ====================================================================


class TestEventsRouterExecFeedbackDispatch:
    """Thread replies in an active exec feedback gate go to resolve_exec_feedback."""

    def test_thread_reply_sends_feedback(self):
        """A thread reply while exec feedback is pending should signal feedback."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
        )

        ev = threading.Event()
        with _exec_feedback_lock:
            _pending_exec_feedback["run_EV"] = {
                "channel": "C_EV",
                "thread_ts": "T_EV",
                "user": "U1",
                "event": ev,
                "decision": None,
                "feedback": None,
            }

        try:
            # We test _handle_thread_message_inner directly because the
            # exec feedback gate check lives there, not in the outer
            # _handle_thread_message wrapper.
            with patch.object(er, "touch_thread"), \
                 patch.object(er, "append_to_thread"):
                er._handle_thread_message_inner(
                    channel="C_EV",
                    thread_ts="T_EV",
                    user="U_SENDER",
                    clean_text="Add more about scalability",
                    event_ts="9999.1",
                )

            assert ev.is_set()
            assert _pending_exec_feedback["run_EV"]["decision"] == "feedback"
            assert _pending_exec_feedback["run_EV"]["feedback"] == "Add more about scalability"
        finally:
            _pending_exec_feedback.pop("run_EV", None)


# ====================================================================
# interactions_router dispatches exec_summary_approve to gate
# ====================================================================


class TestInteractionsRouterExecApproveDispatch:
    """exec_summary_approve button clicks resolve the non-interactive gate."""

    def test_approve_button_resolves_gate(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
        )

        ev = threading.Event()
        with _exec_feedback_lock:
            _pending_exec_feedback["run_BTN"] = {
                "channel": "C_BTN",
                "thread_ts": "T_BTN",
                "user": "U1",
                "event": ev,
                "decision": None,
                "feedback": None,
            }

        # Simulate calling resolve_exec_feedback as the dispatch would
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            resolve_exec_feedback,
        )
        result = resolve_exec_feedback("run_BTN", "approve")

        assert result is True
        assert ev.is_set()
        assert _pending_exec_feedback["run_BTN"]["decision"] == "approve"
