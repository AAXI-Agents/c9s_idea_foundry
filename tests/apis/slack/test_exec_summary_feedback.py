"""Tests for executive summary interactive user feedback.

Covers the three-step interactive loop:
1. Pre-draft prompt — user can provide initial guidance or skip
2. Post-iteration prompt — show summary, user can approve or give feedback
3. Feedback-driven re-iteration — user feedback injected into next refine step

Also tests Block Kit builders and the PRDFlow integration.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ====================================================================
# Block Kit builders
# ====================================================================


class TestExecSummaryPreFeedbackBlocks:
    """Tests for exec_summary_pre_feedback_blocks()."""

    def test_returns_blocks_list(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_pre_feedback_blocks,
        )
        blocks = exec_summary_pre_feedback_blocks("run_1", "Build a fitness app")
        assert isinstance(blocks, list)
        assert len(blocks) >= 3

    def test_contains_skip_action(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_pre_feedback_blocks,
        )
        blocks = exec_summary_pre_feedback_blocks("run_1", "my idea")
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions) == 1
        action_ids = {e["action_id"] for e in actions[0]["elements"]}
        assert "exec_summary_skip" in action_ids

    def test_contains_cancel_action(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_pre_feedback_blocks,
        )
        blocks = exec_summary_pre_feedback_blocks("run_1", "my idea")
        actions = [b for b in blocks if b.get("type") == "actions"]
        action_ids = {e["action_id"] for e in actions[0]["elements"]}
        assert "flow_cancel" in action_ids

    def test_run_id_in_button_values(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_pre_feedback_blocks,
        )
        blocks = exec_summary_pre_feedback_blocks("test_run_42", "idea")
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert all(
            e["value"] == "test_run_42"
            for e in actions[0]["elements"]
        )

    def test_idea_truncated_in_preview(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_pre_feedback_blocks,
        )
        long_idea = "x" * 500
        blocks = exec_summary_pre_feedback_blocks("r1", long_idea)
        section = [b for b in blocks if b.get("type") == "section"][0]
        # The full 500-char idea should NOT appear verbatim (truncated to 300)
        assert long_idea not in section["text"]["text"]


class TestExecSummaryFeedbackBlocks:
    """Tests for exec_summary_feedback_blocks()."""

    def test_returns_blocks_list(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )
        blocks, _ = exec_summary_feedback_blocks("run_1", "Summary content", 1)
        assert isinstance(blocks, list)
        assert len(blocks) >= 4

    def test_contains_approve_action(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )
        blocks, _ = exec_summary_feedback_blocks("run_1", "content", 2)
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions) == 1
        action_ids = {e["action_id"] for e in actions[0]["elements"]}
        assert "exec_summary_approve" in action_ids

    def test_contains_cancel_action(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )
        blocks, _ = exec_summary_feedback_blocks("run_1", "content", 1)
        actions = [b for b in blocks if b.get("type") == "actions"]
        action_ids = {e["action_id"] for e in actions[0]["elements"]}
        assert "flow_cancel" in action_ids

    def test_iteration_in_header(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )
        blocks, _ = exec_summary_feedback_blocks("run_1", "content", 3)
        header = [b for b in blocks if b.get("type") == "header"][0]
        assert "3" in header["text"]["text"]

    def test_long_content_truncated(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )
        long_content = "y" * 5000
        blocks, was_truncated = exec_summary_feedback_blocks("r1", long_content, 1)
        assert was_truncated is True
        section = [b for b in blocks if b.get("type") == "section"][0]
        assert len(section["text"]["text"]) <= 3000

    def test_run_id_in_button_values(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            exec_summary_feedback_blocks,
        )
        blocks, _ = exec_summary_feedback_blocks("run_42", "content", 1)
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert all(
            e["value"] == "run_42"
            for e in actions[0]["elements"]
        )


# ====================================================================
# Interactions router — new action IDs
# ====================================================================


class TestExecSummaryActionIds:
    """The new exec_summary_* action IDs are in _KNOWN_ACTIONS."""

    def test_exec_summary_approve_known(self):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _KNOWN_ACTIONS,
        )
        assert "exec_summary_approve" in _KNOWN_ACTIONS

    def test_exec_summary_skip_known(self):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _KNOWN_ACTIONS,
        )
        assert "exec_summary_skip" in _KNOWN_ACTIONS

    def test_ack_labels_present(self):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _ack_action,
        )
        ack = _ack_action("exec_summary_approve", "testuser")
        assert "approved" in ack.lower()
        ack2 = _ack_action("exec_summary_skip", "testuser")
        assert "skipped" in ack2.lower()


# ====================================================================
# PRDFlow — exec_summary_user_feedback_callback attribute
# ====================================================================


class TestPRDFlowExecSummaryCallback:
    """The new callback attribute exists on PRDFlow and defaults to None."""

    def test_callback_defaults_to_none(self):
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        assert flow.exec_summary_user_feedback_callback is None

    def test_callback_is_settable(self):
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        cb = MagicMock(return_value=("skip", None))
        flow = PRDFlow()
        flow.exec_summary_user_feedback_callback = cb
        assert flow.exec_summary_user_feedback_callback is cb


# ====================================================================
# PRDFlow._exec_summary_user_gate — unit tests
# ====================================================================


class TestExecSummaryUserGate:
    """Unit tests for _exec_summary_user_gate()."""

    def _make_flow(self, action: str, feedback: str | None = None):
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        flow.state.run_id = "gate_test"
        flow.state.idea = "test idea"
        flow.state.original_idea = "test idea"
        flow.exec_summary_user_feedback_callback = MagicMock(
            return_value=(action, feedback),
        )
        return flow

    @patch("crewai_productfeature_planner.flows._executive_summary.save_finalized_idea")
    def test_approve_returns_false(self, mock_save):
        flow = self._make_flow("approve")
        result = flow._exec_summary_user_gate("content", 1)
        assert result is False
        assert flow.state.executive_summary.is_approved is True

    @patch("crewai_productfeature_planner.flows._executive_summary.save_finalized_idea")
    def test_approve_saves_finalized_idea(self, mock_save):
        flow = self._make_flow("approve")
        # Add an iteration so latest_content is available
        from crewai_productfeature_planner.flows.prd_flow import (
            ExecutiveSummaryIteration,
        )
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(
                content="my summary",
                iteration=1,
                critique=None,
                updated_date="2026-01-01",
            ),
        )
        flow._exec_summary_user_gate("my summary", 1)
        mock_save.assert_called_once()

    def test_feedback_returns_text(self):
        flow = self._make_flow("feedback", "Please add more detail")
        result = flow._exec_summary_user_gate("content", 2)
        assert result == "Please add more detail"

    def test_skip_returns_none(self):
        flow = self._make_flow("skip")
        result = flow._exec_summary_user_gate("content", 1)
        assert result is None

    def test_unknown_action_returns_none(self):
        flow = self._make_flow("something_else")
        result = flow._exec_summary_user_gate("content", 1)
        assert result is None

    def test_callback_exception_returns_none(self):
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        flow.state.run_id = "err_test"
        flow.state.idea = "idea"
        flow.exec_summary_user_feedback_callback = MagicMock(
            side_effect=RuntimeError("boom"),
        )
        result = flow._exec_summary_user_gate("content", 1)
        assert result is None


# ====================================================================
# make_slack_exec_summary_feedback_callback — Slack callback factory
# ====================================================================


class TestMakeSlackExecSummaryFeedbackCallback:
    """Tests for the Slack callback factory."""

    def _register(self, run_id="es_run"):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            cleanup_interactive_run,
            register_interactive_run,
        )
        register_interactive_run(run_id, "C1", "1234.0", "U1", "test idea")
        return cleanup_interactive_run

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_no_interactive_run_returns_skip(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
        )

        cb = make_slack_exec_summary_feedback_callback("nonexistent")
        action, text = cb("content", "idea", "nonexistent", 1)
        assert action == "skip"
        assert text is None

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_pre_draft_skip_via_button(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            resolve_interaction,
        )

        cleanup = self._register("es_skip")
        cb = make_slack_exec_summary_feedback_callback("es_skip")

        # Simulate button click in background
        def _click():
            time.sleep(0.1)
            resolve_interaction("es_skip", "exec_summary_skip", "U1")

        t = threading.Thread(target=_click)
        t.start()

        action, text = cb("", "idea", "es_skip", 0)
        t.join(timeout=5.0)

        assert action == "skip"
        assert text is None
        cleanup("es_skip")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_text",
    )
    def test_pre_draft_feedback_via_thread_reply(self, mock_post_text, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            submit_manual_refinement,
        )

        cleanup = self._register("es_guide")
        cb = make_slack_exec_summary_feedback_callback("es_guide")

        # Simulate thread reply
        def _reply():
            time.sleep(0.1)
            submit_manual_refinement("es_guide", "Focus on mobile users")

        t = threading.Thread(target=_reply)
        t.start()

        action, text = cb("", "idea", "es_guide", 0)
        t.join(timeout=5.0)

        assert action == "feedback"
        assert text == "Focus on mobile users"
        # Verify acknowledgment was posted
        mock_post_text.assert_called_once()
        ack_text = mock_post_text.call_args[1].get("text") or mock_post_text.call_args[0][2]
        assert "feedback" in ack_text.lower() or "got it" in ack_text.lower()
        cleanup("es_guide")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_post_iteration_approve(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            resolve_interaction,
        )

        cleanup = self._register("es_approve")
        cb = make_slack_exec_summary_feedback_callback("es_approve")

        def _click():
            time.sleep(0.1)
            resolve_interaction("es_approve", "exec_summary_approve", "U1")

        t = threading.Thread(target=_click)
        t.start()

        action, text = cb("Summary content here", "idea", "es_approve", 1)
        t.join(timeout=5.0)

        assert action == "approve"
        assert text is None
        cleanup("es_approve")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_text",
    )
    def test_post_iteration_feedback_via_reply(self, mock_post_text, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            submit_manual_refinement,
        )

        cleanup = self._register("es_reply")
        cb = make_slack_exec_summary_feedback_callback("es_reply")

        def _reply():
            time.sleep(0.1)
            submit_manual_refinement(
                "es_reply", "Add more about scalability",
            )

        t = threading.Thread(target=_reply)
        t.start()

        action, text = cb("Summary", "idea", "es_reply", 2)
        t.join(timeout=5.0)

        assert action == "feedback"
        assert text == "Add more about scalability"
        # Verify acknowledgment was posted
        mock_post_text.assert_called_once()
        ack_text = mock_post_text.call_args[1].get("text") or mock_post_text.call_args[0][2]
        assert "feedback" in ack_text.lower() or "got it" in ack_text.lower()
        cleanup("es_reply")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_cancel_raises_exception(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            resolve_interaction,
        )
        from crewai_productfeature_planner.flows.prd_flow import (
            ExecutiveSummaryCompleted,
        )

        cleanup = self._register("es_cancel")
        cb = make_slack_exec_summary_feedback_callback("es_cancel")

        def _click():
            time.sleep(0.1)
            resolve_interaction("es_cancel", "flow_cancel", "U1")

        t = threading.Thread(target=_click)
        t.start()

        with pytest.raises(ExecutiveSummaryCompleted):
            cb("content", "idea", "es_cancel", 1)

        t.join(timeout=5.0)
        cleanup("es_cancel")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_timeout_returns_skip(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
        )

        cleanup = self._register("es_timeout")
        cb = make_slack_exec_summary_feedback_callback("es_timeout")

        # Patch the wait timeout to be very short
        info_module = __import__(
            "crewai_productfeature_planner.apis.slack.interactive_handlers",
            fromlist=["get_interactive_run"],
        )
        info = info_module.get_interactive_run("es_timeout")
        original_wait = info["event"].wait

        def short_wait(timeout=None):
            return original_wait(timeout=0.05)

        info["event"].wait = short_wait

        action, text = cb("content", "idea", "es_timeout", 1)
        assert action == "skip"
        assert text is None
        cleanup("es_timeout")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_pre_draft_posts_pre_feedback_blocks(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            resolve_interaction,
        )

        cleanup = self._register("es_blocks_pre")
        cb = make_slack_exec_summary_feedback_callback("es_blocks_pre")

        def _click():
            time.sleep(0.1)
            resolve_interaction("es_blocks_pre", "exec_summary_skip", "U1")

        t = threading.Thread(target=_click)
        t.start()
        cb("", "idea", "es_blocks_pre", 0)
        t.join(timeout=5.0)

        # _post_blocks should have been called with pre-feedback blocks
        mock_post.assert_called_once()
        args = mock_post.call_args
        blocks = args[0][2] if len(args[0]) > 2 else args[1].get("blocks")
        # The blocks should contain the "Initial Guidance" header
        header = [b for b in blocks if b.get("type") == "header"]
        assert any("Guidance" in h["text"]["text"] for h in header)
        cleanup("es_blocks_pre")

    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks._post_blocks",
    )
    def test_post_iteration_posts_feedback_blocks(self, mock_post):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_feedback_callback,
            resolve_interaction,
        )

        cleanup = self._register("es_blocks_post")
        cb = make_slack_exec_summary_feedback_callback("es_blocks_post")

        def _click():
            time.sleep(0.1)
            resolve_interaction("es_blocks_post", "exec_summary_approve", "U1")

        t = threading.Thread(target=_click)
        t.start()
        cb("Summary text", "idea", "es_blocks_post", 3)
        t.join(timeout=5.0)

        mock_post.assert_called_once()
        args = mock_post.call_args
        blocks = args[0][2] if len(args[0]) > 2 else args[1].get("blocks")
        header = [b for b in blocks if b.get("type") == "header"]
        assert any("Iteration 3" in h["text"]["text"] for h in header)
        cleanup("es_blocks_post")


# ====================================================================
# Events router — thread replies route to exec summary feedback
# ====================================================================


class TestEventsRouterExecSummaryReplies:
    """Thread replies during exec summary feedback should be captured."""

    def test_exec_summary_feedback_pending_action_captured(self):
        """When pending_action is exec_summary_feedback, thread replies
        are routed via submit_manual_refinement."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            _interactive_runs,
            _lock,
            _manual_refinement_text,
            cleanup_interactive_run,
            register_interactive_run,
            submit_manual_refinement,
        )

        register_interactive_run("es_evt", "C1", "1234.0", "U1", "idea")
        with _lock:
            _interactive_runs["es_evt"]["pending_action"] = "exec_summary_feedback"

        result = submit_manual_refinement("es_evt", "My feedback")
        assert result is True

        with _lock:
            assert _manual_refinement_text.get("es_evt") == "My feedback"

        cleanup_interactive_run("es_evt")

    def test_exec_summary_pre_feedback_pending_action_captured(self):
        """When pending_action is exec_summary_pre_feedback, thread
        replies are routed via submit_manual_refinement."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            _interactive_runs,
            _lock,
            _manual_refinement_text,
            cleanup_interactive_run,
            register_interactive_run,
            submit_manual_refinement,
        )

        register_interactive_run("es_pre", "C1", "1234.0", "U1", "idea")
        with _lock:
            _interactive_runs["es_pre"]["pending_action"] = "exec_summary_pre_feedback"

        result = submit_manual_refinement("es_pre", "Focus on security")
        assert result is True

        with _lock:
            assert _manual_refinement_text.get("es_pre") == "Focus on security"

        cleanup_interactive_run("es_pre")
