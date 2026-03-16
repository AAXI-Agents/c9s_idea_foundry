"""Tests for make_progress_poster — pipeline stage event handling."""

from unittest.mock import MagicMock

from crewai_productfeature_planner.apis.slack._flow_handlers import (
    make_progress_poster,
)


class TestPipelineStageEvents:
    """Verify make_progress_poster handles orchestrator pipeline events."""

    def _make(self):
        send = MagicMock()
        poster = make_progress_poster(
            channel="C1", thread_ts="T1", user="U1",
            send_tool=send, run_id="run-1",
        )
        return poster, send

    def test_pipeline_stage_start_idea_refinement(self):
        poster, send = self._make()
        poster("pipeline_stage_start", {
            "stage": "idea_refinement",
            "description": "Iteratively refine raw idea",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Idea Refinement" in msg
        assert "polished" in msg

    def test_pipeline_stage_start_requirements_breakdown(self):
        poster, send = self._make()
        poster("pipeline_stage_start", {
            "stage": "requirements_breakdown",
            "description": "Decompose idea",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Requirements Breakdown" in msg

    def test_pipeline_stage_start_unknown(self):
        poster, send = self._make()
        poster("pipeline_stage_start", {
            "stage": "custom_stage",
            "description": "Do something",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Do something" in msg

    def test_pipeline_stage_complete_idea_refinement(self):
        poster, send = self._make()
        poster("pipeline_stage_complete", {
            "stage": "idea_refinement",
            "iterations": 3,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Idea Refinement" in msg
        assert "3 iteration(s)" in msg
        assert "requirements breakdown" in msg

    def test_pipeline_stage_complete_requirements_breakdown(self):
        poster, send = self._make()
        poster("pipeline_stage_complete", {
            "stage": "requirements_breakdown",
            "iterations": 5,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Requirements Breakdown" in msg
        assert "5 iteration(s)" in msg

    def test_pipeline_stage_skipped(self):
        poster, send = self._make()
        poster("pipeline_stage_skipped", {"stage": "idea_refinement"})
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "idea_refinement" in msg
        assert "skipped" in msg

    def test_send_failure_swallowed(self):
        poster, send = self._make()
        send.run.side_effect = RuntimeError("Slack down")
        # Should not raise
        poster("pipeline_stage_start", {
            "stage": "idea_refinement",
            "description": "Refine",
        })

    def test_unknown_event_no_message(self):
        poster, send = self._make()
        poster("totally_unknown_event", {})
        send.run.assert_not_called()


class TestExistingProgressEvents:
    """Ensure existing event types still work."""

    def _make(self):
        send = MagicMock()
        poster = make_progress_poster(
            channel="C1", thread_ts="T1", user="U1",
            send_tool=send, run_id="run-1",
        )
        return poster, send

    def test_section_start(self):
        poster, send = self._make()
        poster("section_start", {
            "section_title": "Problem Statement",
            "section_key": "problem_statement",
            "section_step": 2,
            "total_sections": 12,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Problem Statement" in msg

    def test_exec_summary_iteration(self):
        poster, send = self._make()
        poster("exec_summary_iteration", {
            "iteration": 2,
            "max_iterations": 5,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Executive Summary" in msg
        assert "2/5" in msg

    def test_prd_complete(self):
        poster, send = self._make()
        poster("prd_complete", {})
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "PRD generation complete" in msg
