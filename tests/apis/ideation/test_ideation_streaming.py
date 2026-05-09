"""Tests for ideation token streaming — _streaming.py and service integration."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.ideation._streaming import (
    _broadcast_agent_token,
    _ctx,
    _on_stream_chunk,
    streaming_session,
)


# ── streaming_session context manager ────────────────────────


class TestStreamingSession:
    def test_sets_thread_local_context(self):
        """Context manager sets session_id and step on thread-local."""
        with streaming_session("sess-123", "a"):
            assert _ctx.session_id == "sess-123"
            assert _ctx.step == "a"
            assert _ctx.message_token is not None

    def test_clears_context_on_exit(self):
        """Context is cleaned up after exiting the context manager."""
        with streaming_session("sess-456", "b"):
            pass
        assert getattr(_ctx, "session_id", None) is None
        assert getattr(_ctx, "step", None) is None

    def test_clears_context_on_exception(self):
        """Context is cleaned up even if an exception occurs."""
        with pytest.raises(RuntimeError):
            with streaming_session("sess-789", "c"):
                raise RuntimeError("boom")
        assert getattr(_ctx, "session_id", None) is None

    def test_thread_isolation(self):
        """Each thread has its own context — no cross-contamination."""
        results = {}

        def worker(session_id: str, step: str, key: str):
            with streaming_session(session_id, step):
                results[key] = (_ctx.session_id, _ctx.step)

        t1 = threading.Thread(target=worker, args=("s1", "a", "t1"))
        t2 = threading.Thread(target=worker, args=("s2", "b", "t2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["t1"] == ("s1", "a")
        assert results["t2"] == ("s2", "b")


# ── _on_stream_chunk event handler ───────────────────────────


class TestOnStreamChunk:
    @patch(
        "crewai_productfeature_planner.apis.ideation._streaming._broadcast_agent_token"
    )
    def test_broadcasts_when_context_set(self, mock_broadcast):
        """Handler broadcasts token when thread has active session."""
        _ctx.session_id = "sess-abc"
        _ctx.step = "a"
        try:
            event = MagicMock()
            event.chunk = "Hello"
            _on_stream_chunk(None, event)
            mock_broadcast.assert_called_once_with("sess-abc", "a", "Hello")
        finally:
            _ctx.session_id = None
            _ctx.step = None

    @patch(
        "crewai_productfeature_planner.apis.ideation._streaming._broadcast_agent_token"
    )
    def test_noop_without_context(self, mock_broadcast):
        """Handler does nothing when no session context is set."""
        _ctx.session_id = None
        event = MagicMock()
        event.chunk = "Hello"
        _on_stream_chunk(None, event)
        mock_broadcast.assert_not_called()

    @patch(
        "crewai_productfeature_planner.apis.ideation._streaming._broadcast_agent_token"
    )
    def test_noop_for_empty_chunk(self, mock_broadcast):
        """Handler ignores empty/None chunks."""
        _ctx.session_id = "sess-abc"
        _ctx.step = "a"
        try:
            event = MagicMock()
            event.chunk = ""
            _on_stream_chunk(None, event)
            mock_broadcast.assert_not_called()

            event.chunk = None
            _on_stream_chunk(None, event)
            mock_broadcast.assert_not_called()
        finally:
            _ctx.session_id = None
            _ctx.step = None


# ── _broadcast_agent_token ───────────────────────────────────


class TestBroadcastAgentToken:
    @patch(
        "crewai_productfeature_planner.apis.ideation._route_websocket.broadcast_sync"
    )
    def test_emits_agent_token_event(self, mock_broadcast):
        """Broadcasts correctly shaped agent_token WS event."""
        _broadcast_agent_token("sess-xyz", "b", "chunk-text")
        mock_broadcast.assert_called_once()
        args = mock_broadcast.call_args
        assert args[0][0] == "sess-xyz"
        event = args[0][1]
        assert event["event"] == "agent_token"
        assert event["data"]["token"] == "chunk-text"
        assert event["data"]["is_final"] is False
        assert "message_id" in event["data"]

    @patch(
        "crewai_productfeature_planner.apis.ideation._route_websocket.broadcast_sync",
        side_effect=Exception("WS down"),
    )
    def test_swallows_broadcast_errors(self, mock_broadcast):
        """Does not raise if broadcast fails."""
        _broadcast_agent_token("sess-xyz", "a", "chunk")  # should not raise


# ── Service integration: _broadcast_agent_token_final ─────────


class TestBroadcastAgentTokenFinal:
    @patch(
        "crewai_productfeature_planner.apis.ideation._route_websocket.broadcast_sync"
    )
    def test_emits_final_token_event(self, mock_broadcast):
        """The final token event has is_final=True and empty token."""
        from crewai_productfeature_planner.apis.ideation.service import (
            _broadcast_agent_token_final,
        )

        _broadcast_agent_token_final("sess-fin", "c")
        mock_broadcast.assert_called_once()
        event = mock_broadcast.call_args[0][1]
        assert event["event"] == "agent_token"
        assert event["data"]["is_final"] is True
        assert event["data"]["token"] == ""


# ── Service integration: _run_agent_for_step uses streaming ──


class TestRunAgentStreaming:
    """Verify _run_agent_for_step wraps the agent call in streaming_session."""

    @pytest.mark.asyncio
    async def test_streaming_context_wraps_agent_call(self):
        """The agent call runs inside streaming_session context."""
        # Track whether streaming_session was active during the agent call
        captured_ctx = {}

        def fake_run_step(**kwargs):
            captured_ctx["session_id"] = getattr(_ctx, "session_id", None)
            captured_ctx["step"] = getattr(_ctx, "step", None)
            return "Agent response text"

        with (
            patch(
                "crewai_productfeature_planner.agents.ideation.run_ideation_step",
                side_effect=fake_run_step,
            ),
            patch(
                "crewai_productfeature_planner.apis.ideation._route_websocket.broadcast_sync",
            ),
            patch(
                "crewai_productfeature_planner.apis.ideation.service.get_messages",
                return_value=[],
            ),
            patch(
                "crewai_productfeature_planner.apis.ideation.service.append_message",
                return_value="msg-1",
            ),
            patch(
                "crewai_productfeature_planner.apis.ideation.service.save_step_data",
            ),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                _run_agent_for_step,
            )

            result = await _run_agent_for_step(
                session_id="test-sess-001",
                step="a",
                user_input="My great idea",
            )

        assert result is not None
        # Verify the streaming context was active during the agent call
        assert captured_ctx["session_id"] == "test-sess-001"
        assert captured_ctx["step"] == "a"


# ── LLM stream=True verification ────────────────────────────


class TestIdeationLlmStreaming:
    @patch("crewai_productfeature_planner.agents.gemini_utils.ensure_gemini_env")
    @patch("crewai_productfeature_planner.agents.ideation.agent.LLM")
    def test_llm_created_with_stream_true(self, mock_llm_cls, _mock_env):
        """The ideation LLM is created with stream=True."""
        from crewai_productfeature_planner.agents.ideation.agent import (
            _build_ideation_llm,
        )

        _build_ideation_llm()
        mock_llm_cls.assert_called_once()
        call_kwargs = mock_llm_cls.call_args
        assert call_kwargs.kwargs.get("stream") is True
