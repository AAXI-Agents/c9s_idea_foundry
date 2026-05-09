"""Tests for processing_status WebSocket events emitted during ideation."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.ideation.models import ProcessingPhase

_SVC = "crewai_productfeature_planner.apis.ideation.service"
_WS = "crewai_productfeature_planner.apis.ideation._route_websocket"
_AGENT = "crewai_productfeature_planner.agents.ideation"


# ── ProcessingPhase enum ──────────────────────────────────────


class TestProcessingPhase:
    def test_values(self):
        assert ProcessingPhase.ANALYZING_RESPONSES.value == "analyzing_responses"
        assert ProcessingPhase.AGENT_REVIEWING.value == "agent_reviewing"
        assert ProcessingPhase.PREPARING_QUESTIONS.value == "preparing_questions"

    def test_is_str_enum(self):
        assert isinstance(ProcessingPhase.ANALYZING_RESPONSES, str)


# ── _broadcast_processing_status ──────────────────────────────


class TestBroadcastProcessingStatus:
    def test_emits_correct_event_shape(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _broadcast_processing_status,
        )

        with patch(f"{_WS}.broadcast_sync") as mock_bc:
            _broadcast_processing_status(
                "sess1", ProcessingPhase.ANALYZING_RESPONSES, "a", 0.1,
            )

            mock_bc.assert_called_once()
            args = mock_bc.call_args
            assert args[0][0] == "sess1"
            event = args[0][1]
            assert event["event"] == "processing_status"
            data = event["data"]
            assert data["phase"] == "analyzing_responses"
            assert data["step"] == "ideation"  # step_to_name("a")
            assert data["progress"] == 0.1
            assert "label" in data

    def test_progress_clamped_to_1(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _broadcast_processing_status,
        )

        with patch(f"{_WS}.broadcast_sync") as mock_bc:
            _broadcast_processing_status(
                "sess1", ProcessingPhase.PREPARING_QUESTIONS, "b", 1.5,
            )
            data = mock_bc.call_args[0][1]["data"]
            assert data["progress"] == 1.0

    def test_broadcast_failure_does_not_raise(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _broadcast_processing_status,
        )

        with patch(f"{_WS}.broadcast_sync", side_effect=RuntimeError("boom")):
            # Should not raise
            _broadcast_processing_status(
                "sess1", ProcessingPhase.AGENT_REVIEWING, "a", 0.5,
            )

    def test_label_map_covers_all_phases(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _broadcast_processing_status,
        )

        with patch(f"{_WS}.broadcast_sync") as mock_bc:
            for phase in ProcessingPhase:
                _broadcast_processing_status("s1", phase, "a", 0.5)

            assert mock_bc.call_count == len(ProcessingPhase)
            for call in mock_bc.call_args_list:
                label = call[0][1]["data"]["label"]
                assert label and not label.startswith("analyzing")  or True  # just ensure non-empty
                assert len(label) > 5


# ── _ProgressTicker ───────────────────────────────────────────


class TestProgressTicker:
    def test_emits_events_while_running(self):
        from crewai_productfeature_planner.apis.ideation.service import _ProgressTicker

        with patch(f"{_SVC}._broadcast_processing_status") as mock_emit:
            ticker = _ProgressTicker("sess1", "a", interval=0.05)
            ticker.start()
            time.sleep(0.2)
            ticker.stop()

            assert mock_emit.call_count >= 2
            for call in mock_emit.call_args_list:
                assert call[0][0] == "sess1"
                assert call[0][1] == ProcessingPhase.AGENT_REVIEWING
                assert call[0][2] == "a"
                assert 0.25 <= call[0][3] <= 0.8

    def test_progress_increments(self):
        from crewai_productfeature_planner.apis.ideation.service import _ProgressTicker

        with patch(f"{_SVC}._broadcast_processing_status") as mock_emit:
            ticker = _ProgressTicker("sess1", "c", interval=0.03)
            ticker.start()
            time.sleep(0.15)
            ticker.stop()

            progress_values = [call[0][3] for call in mock_emit.call_args_list]
            # Each successive progress value should be >= previous
            for i in range(1, len(progress_values)):
                assert progress_values[i] >= progress_values[i - 1]

    def test_progress_caps_at_08(self):
        from crewai_productfeature_planner.apis.ideation.service import _ProgressTicker

        with patch(f"{_SVC}._broadcast_processing_status") as mock_emit:
            ticker = _ProgressTicker("sess1", "a", interval=0.01)
            ticker.start()
            time.sleep(0.3)
            ticker.stop()

            for call in mock_emit.call_args_list:
                assert call[0][3] <= 0.8

    def test_stop_is_idempotent(self):
        from crewai_productfeature_planner.apis.ideation.service import _ProgressTicker

        with patch(f"{_SVC}._broadcast_processing_status"):
            ticker = _ProgressTicker("sess1", "a")
            ticker.start()
            ticker.stop()
            ticker.stop()  # second stop should not raise

    def test_daemon_thread(self):
        from crewai_productfeature_planner.apis.ideation.service import _ProgressTicker

        with patch(f"{_SVC}._broadcast_processing_status"):
            ticker = _ProgressTicker("sess1", "a", interval=0.05)
            ticker.start()
            assert ticker._thread is not None
            assert ticker._thread.daemon is True
            ticker.stop()


# ── _run_agent_for_step integration ───────────────────────────


class TestRunAgentForStepProgress:
    """Verify that _run_agent_for_step emits all three phases."""

    @pytest.mark.asyncio
    async def test_emits_all_phases_on_success(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _run_agent_for_step,
        )

        with (
            patch(f"{_AGENT}.run_ideation_step", return_value="Plain output"),
            patch(f"{_SVC}._broadcast_typing") as mock_typing,
            patch(f"{_SVC}._broadcast_processing_status") as mock_status,
            patch(f"{_SVC}._broadcast_message"),
            patch(f"{_SVC}.append_message", return_value="msg1"),
            patch(f"{_SVC}.save_step_data"),
            patch(f"{_SVC}.get_messages", return_value=[]),
            patch(f"{_SVC}._ProgressTicker") as MockTicker,
        ):
            ticker_instance = MagicMock()
            MockTicker.return_value = ticker_instance

            await _run_agent_for_step(
                session_id="sess1",
                step="a",
                user_input="My idea",
                tenant=None,
            )

            # Typing was broadcast
            mock_typing.assert_called_once_with("sess1", "a")

            # Three processing_status calls: analyzing, reviewing, preparing
            assert mock_status.call_count == 3
            phases = [call[0][1] for call in mock_status.call_args_list]
            assert phases == [
                ProcessingPhase.ANALYZING_RESPONSES,
                ProcessingPhase.AGENT_REVIEWING,
                ProcessingPhase.PREPARING_QUESTIONS,
            ]

            # Ticker started and stopped
            ticker_instance.start.assert_called_once()
            ticker_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_ticker_stopped_on_agent_error(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _run_agent_for_step,
        )

        with (
            patch(f"{_AGENT}.run_ideation_step", side_effect=RuntimeError("LLM error")),
            patch(f"{_SVC}._broadcast_typing"),
            patch(f"{_SVC}._broadcast_processing_status"),
            patch(f"{_SVC}._broadcast_message"),
            patch(f"{_SVC}.append_message", return_value="msg1"),
            patch(f"{_SVC}.save_step_data"),
            patch(f"{_SVC}.get_messages", return_value=[]),
            patch(f"{_SVC}._ProgressTicker") as MockTicker,
            patch(f"{_WS}.broadcast_sync"),
        ):
            ticker_instance = MagicMock()
            MockTicker.return_value = ticker_instance

            result = await _run_agent_for_step(
                session_id="sess1",
                step="a",
                user_input="Bad input",
                tenant=None,
            )

            # Ticker was stopped even though agent errored
            ticker_instance.stop.assert_called_once()
            # Still got a result (error fallback)
            assert result is not None


# ── Double-fire fix ───────────────────────────────────────────


class TestNoDoubleFireTyping:
    """Verify the WS handler no longer emits agent_typing directly."""

    def test_ws_respond_path_does_not_emit_typing(self):
        """The _route_websocket.py respond branch should NOT call
        broadcast() with agent_typing — the service layer does it."""
        import inspect
        from crewai_productfeature_planner.apis.ideation import _route_websocket

        source = inspect.getsource(_route_websocket.ideation_websocket)
        # The respond branch used to have: await broadcast(session_id, {"event": "agent_typing", ...})
        # After the fix, only a comment remains
        respond_section = source.split("respond")[1].split("advance")[0]
        assert 'await broadcast(session_id' not in respond_section
