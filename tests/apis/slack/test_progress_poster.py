"""Tests for make_progress_poster — pipeline stage event handling."""

from unittest.mock import MagicMock, patch

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

    def test_exec_summary_iteration_suppressed(self):
        """exec_summary_iteration is suppressed — no message posted."""
        poster, send = self._make()
        poster("exec_summary_iteration", {
            "iteration": 2,
            "max_iterations": 5,
        })
        send.run.assert_not_called()

    def test_prd_complete(self):
        poster, send = self._make()
        poster("prd_complete", {})
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "PRD generation complete" in msg


class TestIterationSuppression:
    """Verify per-iteration events are suppressed (no Slack message)."""

    def _make(self, user="U1"):
        send = MagicMock()
        poster = make_progress_poster(
            channel="C1", thread_ts="T1", user=user,
            send_tool=send, run_id="run-1",
        )
        return poster, send

    def test_section_iteration_suppressed(self):
        poster, send = self._make()
        poster("section_iteration", {
            "section_title": "Problem Statement",
            "section_key": "problem_statement",
            "section_step": 2,
            "total_sections": 12,
            "iteration": 1,
            "max_iterations": 5,
            "critique_summary": "Needs more detail",
        })
        send.run.assert_not_called()

    def test_exec_summary_iteration_suppressed_with_critique(self):
        poster, send = self._make()
        poster("exec_summary_iteration", {
            "iteration": 3,
            "max_iterations": 5,
            "critique_summary": "Improve market analysis section",
        })
        send.run.assert_not_called()

    def test_section_start_still_shown(self):
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


class TestCompletionSummaries:
    """Verify completion events include user tag + content summary."""

    def _make(self, user="U1"):
        send = MagicMock()
        poster = make_progress_poster(
            channel="C1", thread_ts="T1", user=user,
            send_tool=send, run_id="run-1",
        )
        return poster, send

    def test_section_complete_tags_user(self):
        poster, send = self._make(user="U123")
        poster("section_complete", {
            "section_title": "Problem Statement",
            "section_key": "problem_statement",
            "section_step": 2,
            "total_sections": 12,
            "iterations": 3,
            "content": "Short content here.",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "<@U123>" in msg
        assert "Problem Statement" in msg
        assert "3 iteration(s)" in msg
        assert "Short content here." in msg

    def test_section_complete_no_tag_when_user_empty(self):
        poster, send = self._make(user="")
        poster("section_complete", {
            "section_title": "Edge Cases",
            "section_key": "edge_cases",
            "section_step": 5,
            "total_sections": 12,
            "iterations": 1,
            "content": "Some edge case content.",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "<@" not in msg
        assert "Edge Cases" in msg

    def test_section_complete_no_content(self):
        poster, send = self._make()
        poster("section_complete", {
            "section_title": "Dependencies",
            "section_key": "dependencies",
            "section_step": 9,
            "total_sections": 12,
            "iterations": 2,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "Dependencies" in msg
        assert "2 iteration(s)" in msg

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.upload_content_file",
    )
    def test_section_complete_file_fallback_for_long_content(self, mock_upload):
        poster, send = self._make(user="U1")
        long_content = "x" * 5000
        poster("section_complete", {
            "section_title": "Functional Requirements",
            "section_key": "functional_requirements",
            "section_step": 4,
            "total_sections": 12,
            "iterations": 3,
            "content": long_content,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "see attached file" in msg
        mock_upload.assert_called_once()
        call_kw = mock_upload.call_args
        assert call_kw[1]["filename"] == "functional_requirements.md"
        assert call_kw[1]["content"] == long_content

    def test_exec_summary_complete_tags_user(self):
        poster, send = self._make(user="U456")
        poster("executive_summary_complete", {
            "iterations": 4,
            "chars": 200,
            "content": "Executive summary text here.",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "<@U456>" in msg
        assert "Executive Summary" in msg
        assert "4 iteration(s)" in msg
        assert "Executive summary text here." in msg

    def test_exec_summary_complete_no_tag_when_user_empty(self):
        poster, send = self._make(user="")
        poster("executive_summary_complete", {
            "iterations": 2,
            "chars": 100,
            "content": "Summary.",
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "<@" not in msg

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.upload_content_file",
    )
    def test_exec_summary_file_fallback_for_long_content(self, mock_upload):
        poster, send = self._make()
        long_content = "y" * 5000
        poster("executive_summary_complete", {
            "iterations": 3,
            "chars": 5000,
            "content": long_content,
        })
        send.run.assert_called_once()
        msg = send.run.call_args[1]["text"]
        assert "see attached file" in msg
        mock_upload.assert_called_once()
        assert mock_upload.call_args[1]["filename"] == "executive_summary.md"

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.upload_content_file",
    )
    def test_short_content_no_file_upload(self, mock_upload):
        poster, send = self._make()
        poster("section_complete", {
            "section_title": "Assumptions",
            "section_key": "assumptions",
            "section_step": 10,
            "total_sections": 12,
            "iterations": 1,
            "content": "Short assumption content.",
        })
        send.run.assert_called_once()
        mock_upload.assert_not_called()
