"""Tests for the interactive executive summary completion gate.

Covers:
- ``make_slack_exec_summary_completion_callback`` factory (callback behaviour)
- Interactive flow runner wires ``executive_summary_callback``
- ``ExecutiveSummaryCompleted`` is handled by the interactive flow runner
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

_CALLBACKS = (
    "crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks"
)
_FLOW_RUNNER = (
    "crewai_productfeature_planner.apis.slack.interactive_handlers._flow_runner"
)


@pytest.fixture()
def _register_run():
    """Register an interactive run and clean up after the test."""
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        cleanup_interactive_run,
        register_interactive_run,
    )

    created = []

    def _factory(run_id="comp_run"):
        register_interactive_run(run_id, "C1", "1234.0", "U1", "test idea")
        created.append(run_id)
        return run_id

    yield _factory

    for rid in created:
        cleanup_interactive_run(rid)


# ====================================================================
# make_slack_exec_summary_completion_callback — factory tests
# ====================================================================


class TestMakeSlackExecSummaryCompletionCallback:
    """Tests for the interactive exec summary completion callback."""

    @patch(f"{_CALLBACKS}._post_blocks")
    def test_no_interactive_run_returns_true(self, mock_post):
        """If no interactive run exists, auto-continue."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        cb = make_slack_exec_summary_completion_callback("nonexistent")
        result = cb("# Summary", "idea", "nonexistent", [{"iteration": 1}])
        assert result is True

    @patch(f"{_CALLBACKS}._post_blocks")
    def test_cancelled_run_returns_false(self, mock_post, _register_run):
        """If the run is cancelled, return False (stop)."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            get_interactive_run,
        )
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        rid = _register_run("comp_cancel")
        info = get_interactive_run(rid)
        info["cancelled"] = True

        cb = make_slack_exec_summary_completion_callback(rid)
        result = cb("# Summary", "idea", rid, [])
        assert result is False

    @patch(f"{_CALLBACKS}._post_blocks")
    @patch(f"{_CALLBACKS}._wait_for_decision", return_value="exec_summary_continue")
    def test_continue_returns_true(self, mock_wait, mock_post, _register_run):
        """User clicks Continue → callback returns True."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        rid = _register_run("comp_continue")
        cb = make_slack_exec_summary_completion_callback(rid)
        result = cb("# Summary", "idea", rid, [{"iteration": 1}])
        assert result is True
        mock_post.assert_called_once()

    @patch(f"{_CALLBACKS}._post_blocks")
    @patch(f"{_CALLBACKS}._wait_for_decision", return_value="exec_summary_stop")
    def test_stop_returns_false(self, mock_wait, mock_post, _register_run):
        """User clicks Stop → callback returns False."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        rid = _register_run("comp_stop")
        cb = make_slack_exec_summary_completion_callback(rid)
        result = cb("# Summary", "idea", rid, [{"iteration": 1}])
        assert result is False

    @patch(f"{_CALLBACKS}._post_blocks")
    @patch(f"{_CALLBACKS}._wait_for_decision", return_value=None)
    def test_timeout_returns_true(self, mock_wait, mock_post, _register_run):
        """Timeout → auto-continue (returns True)."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        rid = _register_run("comp_timeout")
        cb = make_slack_exec_summary_completion_callback(rid)
        result = cb("# Summary", "idea", rid, [])
        assert result is True

    @patch(f"{_CALLBACKS}._post_blocks")
    @patch(f"{_CALLBACKS}._wait_for_decision", return_value="exec_summary_continue")
    def test_posts_completion_blocks(self, mock_wait, mock_post, _register_run):
        """Completion blocks are posted to Slack."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        rid = _register_run("comp_blocks")
        cb = make_slack_exec_summary_completion_callback(rid)
        cb("# Summary content", "idea", rid, [{"iteration": 1}, {"iteration": 2}])

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "C1"  # channel
        assert call_args[0][1] == "1234.0"  # thread_ts
        # Blocks should be the third positional arg
        blocks = call_args[0][2]
        assert isinstance(blocks, list)

    @patch(f"{_CALLBACKS}._post_blocks")
    @patch(f"{_CALLBACKS}._wait_for_decision", return_value="exec_summary_continue")
    def test_wait_called_with_correct_action_type(
        self, mock_wait, mock_post, _register_run,
    ):
        """_wait_for_decision is called with action_type 'exec_summary_completion'."""
        from crewai_productfeature_planner.apis.slack.interactive_handlers._callbacks import (
            make_slack_exec_summary_completion_callback,
        )

        rid = _register_run("comp_action_type")
        cb = make_slack_exec_summary_completion_callback(rid)
        cb("# Summary", "idea", rid, [])

        mock_wait.assert_called_once_with(rid, "exec_summary_completion")


# ====================================================================
# Interactive flow runner wires executive_summary_callback
# ====================================================================


class TestInteractiveFlowRunnerCompletionGate:
    """Verify run_interactive_slack_flow sets executive_summary_callback."""

    @patch(f"{_FLOW_RUNNER}.make_slack_jira_review_callback", return_value=MagicMock())
    @patch(f"{_FLOW_RUNNER}.make_slack_jira_skeleton_callback", return_value=MagicMock())
    @patch(
        f"{_FLOW_RUNNER}.make_slack_exec_summary_completion_callback",
        return_value=MagicMock(),
    )
    @patch(
        f"{_FLOW_RUNNER}.make_slack_exec_summary_feedback_callback",
        return_value=MagicMock(),
    )
    @patch(f"{_FLOW_RUNNER}.make_slack_requirements_callback", return_value=MagicMock())
    @patch(f"{_FLOW_RUNNER}.make_slack_idea_callback", return_value=MagicMock())
    @patch(f"{_FLOW_RUNNER}.wait_for_refinement_mode", return_value="agent")
    @patch(f"{_FLOW_RUNNER}.register_interactive_run")
    @patch(f"{_FLOW_RUNNER}.get_interactive_run", return_value={"cancelled": False})
    @patch(f"{_FLOW_RUNNER}.cleanup_interactive_run")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.create_job")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.update_job_started")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.update_job_completed")
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool")
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackPostPRDResultTool")
    def test_executive_summary_callback_set_on_flow(
        self,
        _mock_post_tool,
        _mock_send_tool,
        _mock_completed,
        _mock_started,
        _mock_create_job,
        _mock_cleanup,
        _mock_get_run,
        _mock_register,
        _mock_wait_mode,
        _mock_idea_cb,
        _mock_req_cb,
        _mock_feedback_cb,
        mock_completion_cb,
        _mock_skeleton_cb,
        _mock_jira_review_cb,
    ):
        """The flow.executive_summary_callback should be set."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        # Track what gets set on the flow
        captured_flow = {}

        original_init = PRDFlow.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            captured_flow["instance"] = self

        with patch.object(PRDFlow, "__init__", patched_init):
            with patch.object(PRDFlow, "kickoff", return_value="result"):
                with patch(
                    f"{_FLOW_RUNNER}._post_blocks",
                ):
                    from crewai_productfeature_planner.apis.slack.interactive_handlers._flow_runner import (
                        run_interactive_slack_flow,
                    )

                    run_interactive_slack_flow(
                        "test_ec_wire", "test idea", "C1", "T1", "U1",
                        notify=False,
                    )

        flow = captured_flow.get("instance")
        assert flow is not None
        assert flow.executive_summary_callback is mock_completion_cb.return_value


# ====================================================================
# ExecutiveSummaryCompleted handled by interactive flow runner
# ====================================================================


class TestInteractiveFlowRunnerExecSummaryCompleted:
    """ExecutiveSummaryCompleted should be caught and handled gracefully."""

    @patch(f"{_FLOW_RUNNER}.make_slack_jira_review_callback", return_value=MagicMock())
    @patch(f"{_FLOW_RUNNER}.make_slack_jira_skeleton_callback", return_value=MagicMock())
    @patch(
        f"{_FLOW_RUNNER}.make_slack_exec_summary_completion_callback",
        return_value=MagicMock(),
    )
    @patch(
        f"{_FLOW_RUNNER}.make_slack_exec_summary_feedback_callback",
        return_value=MagicMock(),
    )
    @patch(f"{_FLOW_RUNNER}.make_slack_requirements_callback", return_value=MagicMock())
    @patch(f"{_FLOW_RUNNER}.make_slack_idea_callback", return_value=MagicMock())
    @patch(f"{_FLOW_RUNNER}.wait_for_refinement_mode", return_value="agent")
    @patch(f"{_FLOW_RUNNER}.register_interactive_run")
    @patch(f"{_FLOW_RUNNER}.get_interactive_run", return_value={"cancelled": False})
    @patch(f"{_FLOW_RUNNER}.cleanup_interactive_run")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.create_job")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.update_job_started")
    @patch("crewai_productfeature_planner.mongodb.crew_jobs.update_job_completed")
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool")
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackPostPRDResultTool")
    def test_exec_summary_completed_marks_completed(
        self,
        _mock_post_tool,
        _mock_send_tool,
        mock_completed,
        _mock_started,
        _mock_create_job,
        _mock_cleanup,
        _mock_get_run,
        _mock_register,
        _mock_wait_mode,
        _mock_idea_cb,
        _mock_req_cb,
        _mock_feedback_cb,
        _mock_completion_cb,
        _mock_skeleton_cb,
        _mock_jira_review_cb,
    ):
        """ExecutiveSummaryCompleted should result in COMPLETED status."""
        from crewai_productfeature_planner.apis.shared import FlowStatus, runs
        from crewai_productfeature_planner.flows._constants import (
            ExecutiveSummaryCompleted,
        )
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        with patch.object(
            PRDFlow, "kickoff",
            side_effect=ExecutiveSummaryCompleted("User stopped"),
        ):
            with patch(f"{_FLOW_RUNNER}._post_blocks"):
                with patch(f"{_FLOW_RUNNER}._post_text") as mock_post_text:
                    from crewai_productfeature_planner.apis.slack.interactive_handlers._flow_runner import (
                        run_interactive_slack_flow,
                    )

                    run_interactive_slack_flow(
                        "test_ec_stopped", "test idea", "C1", "T1", "U1",
                        notify=True,
                    )

        run = runs.get("test_ec_stopped")
        assert run is not None
        assert run.status == FlowStatus.COMPLETED
        mock_completed.assert_called_once_with("test_ec_stopped", status="completed")

        # Should have posted a message about stopping
        mock_post_text.assert_called()
        posted_text = mock_post_text.call_args[0][2]
        assert "executive summary" in posted_text.lower()


# ====================================================================
# Export check
# ====================================================================


class TestExport:
    """The new callback factory is exported from the package."""

    def test_importable_from_package(self):
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            make_slack_exec_summary_completion_callback,
        )
        assert callable(make_slack_exec_summary_completion_callback)
