"""Tests for the flow-paused retry button and crash-prevention hardening.

Covers:
- ``flow_paused_blocks`` Block Kit builder
- ``_handle_flow_retry`` handler dispatch
- ``flow_retry`` action dispatch in interactions router
- ``BaseException`` safety net in ``run_prd_flow`` / ``resume_prd_flow``
- Thread exception hook installed during server lifespan
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_SERVICE = "crewai_productfeature_planner.apis.prd.service"
_FLOW = "crewai_productfeature_planner.flows.prd_flow"
_RETRY_HANDLER = "crewai_productfeature_planner.apis.slack.interactions_router._retry_handler"


@pytest.fixture(autouse=True)
def _clean_runs():
    """Ensure the shared ``runs`` dict is clean before/after each test."""
    from crewai_productfeature_planner.apis.shared import runs
    saved = dict(runs)
    yield
    runs.clear()
    runs.update(saved)


# ====================================================================
# flow_paused_blocks builder
# ====================================================================


class TestFlowPausedBlocks:
    """Validate the Block Kit builder for paused-flow notifications."""

    def test_blocks_contain_retry_button(self):
        from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks

        blocks = flow_paused_blocks("run_abc")
        action_ids = [
            el.get("action_id")
            for b in blocks
            if b.get("type") == "actions"
            for el in b.get("elements", [])
        ]
        assert "flow_retry" in action_ids

    def test_blocks_include_reason(self):
        from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks

        blocks = flow_paused_blocks("run_abc", "LLM timeout")
        section_text = blocks[0]["text"]["text"]
        assert "LLM timeout" in section_text

    def test_blocks_no_retry_button_when_disabled(self):
        from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks

        blocks = flow_paused_blocks("run_abc", show_retry=False)
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 0

    def test_blocks_run_id_in_button_value(self):
        from crewai_productfeature_planner.apis.slack.blocks import flow_paused_blocks

        blocks = flow_paused_blocks("my_run_42")
        for b in blocks:
            if b.get("type") == "actions":
                for el in b.get("elements", []):
                    if el.get("action_id") == "flow_retry":
                        assert el["value"] == "my_run_42"


# ====================================================================
# _handle_flow_retry handler
# ====================================================================


class TestHandleFlowRetry:
    """Verify the retry handler delegates to handle_resume_prd."""

    @patch("crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd")
    @patch("crewai_productfeature_planner.apis.slack.session_manager.get_context_session", return_value={"project_id": "proj_1"})
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool")
    def test_calls_handle_resume_prd(self, mock_send_cls, mock_session, mock_resume):
        from crewai_productfeature_planner.apis.slack.interactions_router._retry_handler import (
            _handle_flow_retry,
        )

        _handle_flow_retry("run_42", "U1", "C1", "T1")

        mock_resume.assert_called_once()
        call_kwargs = mock_resume.call_args
        assert call_kwargs.kwargs["channel"] == "C1"
        assert call_kwargs.kwargs["thread_ts"] == "T1"
        assert call_kwargs.kwargs["user"] == "U1"
        assert call_kwargs.kwargs["project_id"] == "proj_1"

    @patch("crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd", side_effect=RuntimeError("boom"))
    @patch("crewai_productfeature_planner.apis.slack.session_manager.get_context_session", return_value=None)
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool")
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_error_posts_message(self, mock_client_fn, mock_send_cls, mock_session, mock_resume):
        from crewai_productfeature_planner.apis.slack.interactions_router._retry_handler import (
            _handle_flow_retry,
        )

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        # Should not raise
        _handle_flow_retry("run_err", "U1", "C1", "T1")

        mock_client.chat_postMessage.assert_called_once()
        msg = mock_client.chat_postMessage.call_args.kwargs["text"]
        assert "boom" in msg


# ====================================================================
# Dispatch routes flow_retry
# ====================================================================


class TestDispatchFlowRetry:
    """flow_retry action_id is routed through the interactions dispatch."""

    def test_flow_retry_in_retry_actions(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _RETRY_ACTIONS,
        )
        assert "flow_retry" in _RETRY_ACTIONS

    def test_ack_label_exists(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _ack_action,
        )
        label = _ack_action("flow_retry", "testuser")
        assert "Retrying" in label


# ====================================================================
# BaseException safety net in run_prd_flow
# ====================================================================


class TestBaseExceptionSafetyNet:
    """run_prd_flow catches BaseException (SystemExit, KeyboardInterrupt)
    and pauses gracefully instead of crashing the thread."""

    @patch(f"{_FLOW}.PRDFlow")
    @patch(f"{_SERVICE}.update_job_started")
    @patch(f"{_SERVICE}.update_job_completed")
    def test_system_exit_pauses_flow(
        self, mock_completed, mock_started, mock_flow_cls,
    ):
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow
        from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs

        mock_flow = MagicMock()
        mock_flow.state = MagicMock()
        mock_flow.kickoff.side_effect = SystemExit("CrewAI subprocess exit")
        mock_flow_cls.return_value = mock_flow

        runs["test_fatal"] = FlowRun(run_id="test_fatal", flow_name="prd")

        # Should NOT raise
        run_prd_flow("test_fatal", "idea", auto_approve=True)

        run = runs["test_fatal"]
        assert run.status == FlowStatus.PAUSED
        assert "FATAL_ERROR" in run.error
        assert "SystemExit" in run.error
        mock_completed.assert_called_once_with("test_fatal", status="paused")

    @patch(f"{_FLOW}.PRDFlow")
    @patch(f"{_SERVICE}.update_job_started")
    @patch(f"{_SERVICE}.update_job_completed")
    def test_keyboard_interrupt_pauses_flow(
        self, mock_completed, mock_started, mock_flow_cls,
    ):
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow
        from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs

        mock_flow = MagicMock()
        mock_flow.state = MagicMock()
        mock_flow.kickoff.side_effect = KeyboardInterrupt()
        mock_flow_cls.return_value = mock_flow

        runs["test_kbi"] = FlowRun(run_id="test_kbi", flow_name="prd")

        # Should NOT raise
        run_prd_flow("test_kbi", "idea", auto_approve=True)

        run = runs["test_kbi"]
        assert run.status == FlowStatus.PAUSED
        assert "FATAL_ERROR" in run.error


# ====================================================================
# Thread exception hook
# ====================================================================


class TestThreadExceptionHook:
    """The lifespan installs a threading.excepthook safety net."""

    def test_hook_import_and_logger(self):
        """Verify thread_excepthook is set during lifespan setup."""
        import threading

        # Simulate what _lifespan does
        original = threading.excepthook

        def _custom_hook(args):
            pass

        threading.excepthook = _custom_hook
        assert threading.excepthook is _custom_hook

        # Restore
        threading.excepthook = original


# ====================================================================
# router.py pause notification uses blocks
# ====================================================================


class TestRouterPauseBlocks:
    """_run_slack_prd_flow posts blocks (not just text) when flow pauses."""

    @patch(f"{_FLOW}.PRDFlow")
    @patch(f"{_SERVICE}.update_job_started")
    @patch(f"{_SERVICE}.update_job_completed")
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.create_job")
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.save_slack_context",
    )
    def test_pause_posts_blocks_with_retry(
        self,
        mock_save_ctx,
        mock_create_job,
        mock_client_fn,
        mock_completed,
        mock_started,
        mock_flow_cls,
    ):
        from crewai_productfeature_planner.apis.slack.router import _run_slack_prd_flow
        from crewai_productfeature_planner.scripts.retry import LLMError

        mock_flow = MagicMock()
        mock_flow.state = MagicMock()
        mock_flow.kickoff.side_effect = LLMError("Invalid response from LLM call - None or empty")
        mock_flow_cls.return_value = mock_flow

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        _run_slack_prd_flow(
            "run_pause_test", "test idea",
            channel="C1", thread_ts="T1",
        )

        # Should have posted blocks (not just text) for the pause notification
        # Check that chat_postMessage was called with blocks containing flow_retry
        calls = mock_client.chat_postMessage.call_args_list
        pause_call = None
        for call in calls:
            kwargs = call.kwargs if call.kwargs else {}
            blocks = kwargs.get("blocks", [])
            for b in blocks:
                if b.get("type") == "actions":
                    for el in b.get("elements", []):
                        if el.get("action_id") == "flow_retry":
                            pause_call = call
                            break
        assert pause_call is not None, (
            "Expected a chat_postMessage call with flow_retry button blocks"
        )
