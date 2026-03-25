"""Tests for the executive summary completion gate.

Covers:
- ``exec_summary_completion_blocks`` Block Kit builder
- ``resolve_exec_completion`` (button click signalling)
- ``make_exec_summary_completion_gate`` factory (callback behaviour)
- Integration: ``run_prd_flow`` accepts and forwards ``executive_summary_callback``
- Integration: interactions router dispatches new action IDs
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
_SLACK_TOOLS = "crewai_productfeature_planner.tools.slack_tools"
_SERVICE = "crewai_productfeature_planner.apis.prd.service"
_FLOW = "crewai_productfeature_planner.flows.prd_flow"


@pytest.fixture(autouse=True)
def _clean_gate_state():
    """Clear module-level completion gate state between tests."""
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        _exec_completion_lock,
        _pending_exec_completion,
    )
    with _exec_completion_lock:
        _pending_exec_completion.clear()
    yield
    with _exec_completion_lock:
        _pending_exec_completion.clear()


# ====================================================================
# Block Kit builders
# ====================================================================


class TestExecSummaryCompletionBlocks:
    """Tests for exec_summary_completion_blocks()."""

    def test_returns_blocks_list(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )
        blocks, _ = exec_summary_completion_blocks("run_1", "Summary content", 3)
        assert isinstance(blocks, list)
        assert len(blocks) >= 4

    def test_contains_continue_action(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )
        blocks, _ = exec_summary_completion_blocks("run_1", "content", 2)
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions) == 1
        action_ids = {e["action_id"] for e in actions[0]["elements"]}
        assert "exec_summary_continue" in action_ids

    def test_contains_stop_action(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )
        blocks, _ = exec_summary_completion_blocks("run_1", "content", 2)
        actions = [b for b in blocks if b.get("type") == "actions"]
        action_ids = {e["action_id"] for e in actions[0]["elements"]}
        assert "exec_summary_stop" in action_ids

    def test_run_id_in_button_values(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )
        blocks, _ = exec_summary_completion_blocks("test_run_99", "content", 1)
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert all(
            e["value"] == "test_run_99"
            for e in actions[0]["elements"]
        )

    def test_content_truncated_for_long_summary(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )
        long_content = "x" * 3500
        blocks, was_truncated = exec_summary_completion_blocks("r1", long_content, 3)
        assert was_truncated is True
        section = [b for b in blocks if b.get("type") == "section"][0]
        # The full content should NOT appear verbatim (truncated to 2700)
        assert long_content not in section["text"]["text"]
        assert "more chars" in section["text"]["text"]
        # Combined text (prefix + preview) must stay under 3000
        assert len(section["text"]["text"]) <= 3000

    def test_iteration_count_in_text(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_completion_blocks,
        )
        blocks, _ = exec_summary_completion_blocks("r1", "Summary", 5)
        section = [b for b in blocks if b.get("type") == "section"][0]
        assert "5" in section["text"]["text"]

    def test_known_actions_include_new_ids(self):
        """New action IDs must be in _KNOWN_ACTIONS."""
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _KNOWN_ACTIONS,
        )
        assert "exec_summary_continue" in _KNOWN_ACTIONS
        assert "exec_summary_stop" in _KNOWN_ACTIONS


# ====================================================================
# resolve_exec_completion
# ====================================================================


class TestResolveExecCompletion:
    """Tests for resolve_exec_completion()."""

    def test_returns_false_for_unknown_run(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            resolve_exec_completion,
        )
        assert resolve_exec_completion("unknown_run", "exec_summary_continue") is False

    def test_signals_continue(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
            resolve_exec_completion,
        )
        ev = threading.Event()
        with _exec_completion_lock:
            _pending_exec_completion["run_1"] = {
                "channel": "C1",
                "thread_ts": "T1",
                "event": ev,
                "decision": None,
            }

        result = resolve_exec_completion("run_1", "exec_summary_continue")
        assert result is True
        assert ev.is_set()
        assert _pending_exec_completion["run_1"]["decision"] == "exec_summary_continue"

    def test_signals_stop(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
            resolve_exec_completion,
        )
        ev = threading.Event()
        with _exec_completion_lock:
            _pending_exec_completion["run_2"] = {
                "channel": "C2",
                "thread_ts": "T2",
                "event": ev,
                "decision": None,
            }

        result = resolve_exec_completion("run_2", "exec_summary_stop")
        assert result is True
        assert ev.is_set()
        assert _pending_exec_completion["run_2"]["decision"] == "exec_summary_stop"


# ====================================================================
# make_exec_summary_completion_gate — callback behaviour
# ====================================================================


class TestMakeExecSummaryCompletionGate:
    """Tests for the callback returned by make_exec_summary_completion_gate()."""

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=None)
    def test_continue_returns_true(self, _mock_client):
        """When user clicks Continue, callback returns True."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
            make_exec_summary_completion_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_completion_gate(
            "C1", "T1", "U1", send_tool, run_id="run_A",
        )

        def _signal():
            time.sleep(0.1)
            with _exec_completion_lock:
                info = _pending_exec_completion.get("run_A")
                if info:
                    info["decision"] = "exec_summary_continue"
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        result = cb("# Executive Summary", "idea", "run_A", [{"iteration": 1}])
        assert result is True
        t.join(timeout=2)

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=None)
    def test_stop_returns_false(self, _mock_client):
        """When user clicks Stop, callback returns False."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
            make_exec_summary_completion_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_completion_gate(
            "C1", "T1", "U1", send_tool, run_id="run_B",
        )

        def _signal():
            time.sleep(0.1)
            with _exec_completion_lock:
                info = _pending_exec_completion.get("run_B")
                if info:
                    info["decision"] = "exec_summary_stop"
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        result = cb("# Summary", "idea", "run_B", [{"iteration": 1}])
        assert result is False
        t.join(timeout=2)

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=None)
    def test_timeout_returns_true(self, _mock_client):
        """On timeout, callback auto-continues (returns True)."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            make_exec_summary_completion_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_completion_gate(
            "C1", "T1", "U1", send_tool, run_id="run_C",
        )

        # Monkey-patch the timeout to be very short for testing
        import crewai_productfeature_planner.apis.slack._flow_handlers as fh
        original_fn = fh.make_exec_summary_completion_gate

        # We can't easily shorten the timeout, so we'll just set the event
        # immediately with no decision to simulate timeout behavior
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
        )

        def _signal():
            time.sleep(0.1)
            with _exec_completion_lock:
                info = _pending_exec_completion.get("run_C")
                if info:
                    # Set event without decision to simulate timeout
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        result = cb("# Summary", "idea", "run_C", [])
        # No decision → timeout path → auto-continue → True
        assert result is True
        t.join(timeout=2)

    @patch(f"{_SLACK_TOOLS}._get_slack_client", return_value=MagicMock())
    def test_posts_blocks_via_slack_client(self, mock_get_client):
        """When a Slack client is available, completion blocks should be posted."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
            make_exec_summary_completion_gate,
        )
        send_tool = MagicMock()
        cb = make_exec_summary_completion_gate(
            "C99", "T99", "U1", send_tool, run_id="run_D",
        )

        def _signal():
            time.sleep(0.1)
            with _exec_completion_lock:
                info = _pending_exec_completion.get("run_D")
                if info:
                    info["decision"] = "exec_summary_continue"
                    info["event"].set()

        t = threading.Thread(target=_signal, daemon=True)
        t.start()

        cb("# Summary", "idea", "run_D", [{"iteration": 1}, {"iteration": 2}])

        client = mock_get_client.return_value
        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C99"
        assert call_kwargs["thread_ts"] == "T99"
        assert "blocks" in call_kwargs
        t.join(timeout=2)


# ====================================================================
# run_prd_flow accepts executive_summary_callback
# ====================================================================


class TestRunPrdFlowExecCompletionParam:
    """Verify run_prd_flow forwards executive_summary_callback."""

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

        runs["test_comp_1"] = FlowRun(run_id="test_comp_1", flow_name="prd")

        dummy_cb = MagicMock()
        run_prd_flow(
            "test_comp_1", "idea",
            auto_approve=True,
            executive_summary_callback=dummy_cb,
        )

        assert mock_flow.executive_summary_callback is dummy_cb

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

        sentinel = object()
        mock_flow.executive_summary_callback = sentinel

        runs["test_comp_2"] = FlowRun(run_id="test_comp_2", flow_name="prd")
        run_prd_flow("test_comp_2", "idea", auto_approve=True)

        # The attribute should still be the sentinel
        assert mock_flow.executive_summary_callback is sentinel


# ====================================================================
# _run_slack_prd_flow wires up the completion gate
# ====================================================================


class TestSlackPrdFlowCompletionGateWiring:
    """Verify _run_slack_prd_flow passes executive_summary_callback."""

    @patch(f"{_FH}.make_exec_summary_completion_gate")
    @patch(f"{_FH}.make_exec_summary_gate")
    @patch(f"{_FH}.make_progress_poster")
    @patch(f"{_SLACK_TOOLS}.SlackSendMessageTool")
    @patch(f"{_SLACK_TOOLS}.SlackPostPRDResultTool")
    @patch(f"{_SERVICE}.run_prd_flow")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.create_job")
    def test_completion_gate_passed_to_run_prd_flow(
        self,
        _mock_create_job,
        mock_run_prd,
        _mock_post_tool,
        _mock_send_cls,
        _mock_progress,
        _mock_gate,
        mock_completion_gate,
    ):
        from crewai_productfeature_planner.apis.slack.router import (
            _run_slack_prd_flow,
        )

        mock_completion_gate.return_value = MagicMock()

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas.repository.save_slack_context",
        ):
            _run_slack_prd_flow(
                "run_X", "my idea", "C1", "T1", auto_approve=False,
            )

        # Verify run_prd_flow was called with executive_summary_callback
        mock_run_prd.assert_called_once()
        call_kwargs = mock_run_prd.call_args[1]
        assert "executive_summary_callback" in call_kwargs
        assert call_kwargs["executive_summary_callback"] is mock_completion_gate.return_value

    @patch(f"{_FH}.make_auto_exec_completion_gate")
    @patch(f"{_FH}.make_auto_exec_summary_gate")
    @patch(f"{_FH}.make_auto_requirements_gate")
    @patch(f"{_FH}.make_progress_poster")
    @patch(f"{_SLACK_TOOLS}.SlackSendMessageTool")
    @patch(f"{_SLACK_TOOLS}.SlackPostPRDResultTool")
    @patch(f"{_SERVICE}.run_prd_flow")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.create_job")
    def test_auto_completion_gate_used_when_auto_approve(
        self,
        _mock_create_job,
        mock_run_prd,
        _mock_post_tool,
        _mock_send_cls,
        _mock_progress,
        _mock_auto_req,
        _mock_auto_exec,
        mock_auto_completion,
    ):
        """When auto_approve=True (default), auto-mode gates are wired."""
        from crewai_productfeature_planner.apis.slack.router import (
            _run_slack_prd_flow,
        )

        mock_auto_completion.return_value = MagicMock()

        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas.repository.save_slack_context",
        ):
            _run_slack_prd_flow("run_Y", "my idea", "C2", "T2")

        mock_run_prd.assert_called_once()
        call_kwargs = mock_run_prd.call_args[1]
        assert "executive_summary_callback" in call_kwargs
        assert call_kwargs["executive_summary_callback"] is mock_auto_completion.return_value
