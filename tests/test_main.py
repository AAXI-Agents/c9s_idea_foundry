"""Tests for CLI helper functions in main.py."""

import pytest
from unittest.mock import MagicMock, patch, call

from crewai_productfeature_planner.main import (
    _approve_refined_idea,
    _approve_requirements,
    _assemble_prd_from_doc,
    _choose_refinement_mode,
    _confluence_completed_in_output,
    _extract_confluence_url,
    _generate_missing_outputs,
    _jira_completed_in_output,
    _kill_stale_crew_processes,
    _manual_idea_refinement,
    _max_iteration_from_doc,
    _publish_unpublished_prds,
    _restore_prd_state,
    _run_startup_delivery,
    _run_startup_delivery_background,
)


# ── _choose_refinement_mode ──────────────────────────────────


class TestChooseRefinementMode:
    """Tests for the refinement-mode prompt."""

    def test_agent_shortcut(self):
        with patch("builtins.input", return_value="a"):
            assert _choose_refinement_mode() == "agent"

    def test_agent_full_word(self):
        with patch("builtins.input", return_value="agent"):
            assert _choose_refinement_mode() == "agent"

    def test_manual_shortcut(self):
        with patch("builtins.input", return_value="m"):
            assert _choose_refinement_mode() == "manual"

    def test_manual_full_word(self):
        with patch("builtins.input", return_value="manual"):
            assert _choose_refinement_mode() == "manual"

    def test_case_insensitive(self):
        with patch("builtins.input", return_value="A"):
            assert _choose_refinement_mode() == "agent"

    def test_invalid_then_valid(self, capsys):
        with patch("builtins.input", side_effect=["x", "z", "m"]):
            result = _choose_refinement_mode()
        assert result == "manual"
        out = capsys.readouterr().out
        assert "Please enter" in out


# ── _manual_idea_refinement ──────────────────────────────────


class TestManualIdeaRefinement:
    """Tests for the interactive manual refinement loop."""

    def test_approve_immediately(self):
        """User approves the idea on the first prompt."""
        with patch("builtins.input", return_value="y"):
            result, history = _manual_idea_refinement("Original idea")
        assert result == "Original idea"
        assert history == []

    def test_approve_yes_word(self):
        with patch("builtins.input", return_value="yes"):
            result, history = _manual_idea_refinement("My idea")
        assert result == "My idea"
        assert history == []

    def test_edit_then_approve(self):
        """User edits once, then approves."""
        inputs = [
            "e",                     # choose to edit
            "Revised idea text",     # type the revision
            "",                      # first blank line
            "",                      # second blank line → finish
            "y",                     # approve
        ]
        with patch("builtins.input", side_effect=inputs):
            result, history = _manual_idea_refinement("Original")
        assert result == "Revised idea text"
        assert len(history) == 1
        assert history[0]["iteration"] == 1
        assert history[0]["idea"] == "Revised idea text"

    def test_multiple_edits(self):
        """User edits twice before approving."""
        inputs = [
            "e",                     # edit round 1
            "Draft v2",
            "",
            "",
            "e",                     # edit round 2
            "Draft v3 final",
            "",
            "",
            "y",                     # approve
        ]
        with patch("builtins.input", side_effect=inputs):
            result, history = _manual_idea_refinement("Draft v1")
        assert result == "Draft v3 final"
        assert len(history) == 2

    def test_empty_edit_keeps_previous(self, capsys):
        """Empty revision keeps the previous version."""
        inputs = [
            "e",           # choose to edit
            "",            # blank line 1 → empty
            "",            # blank line 2 → finish (but lines=[""] so last=="")
            "y",           # approve — still original
        ]
        with patch("builtins.input", side_effect=inputs):
            result, history = _manual_idea_refinement("Keep me")
        assert result == "Keep me"
        assert len(history) == 1  # still recorded even though edit was empty
        out = capsys.readouterr().out
        assert "Empty input" in out

    def test_multiline_edit(self):
        """Multi-line revisions are joined correctly."""
        inputs = [
            "e",
            "Line one",
            "Line two",
            "Line three",
            "",
            "",
            "y",
        ]
        with patch("builtins.input", side_effect=inputs):
            result, history = _manual_idea_refinement("Old")
        assert "Line one\nLine two\nLine three" == result
        assert len(history) == 1

    def test_invalid_choice_reprompts(self, capsys):
        """Invalid action reprompts until valid input."""
        inputs = ["x", "z", "y"]
        with patch("builtins.input", side_effect=inputs):
            result, history = _manual_idea_refinement("Idea")
        assert result == "Idea"
        assert history == []
        out = capsys.readouterr().out
        assert out.count("Please enter") == 2

    @patch("crewai_productfeature_planner.main.save_executive_summary")
    def test_saves_iterations_with_run_id(self, mock_save):
        """When run_id is provided, iterations should be saved to workingIdeas."""
        inputs = [
            "e",
            "Revised v1",
            "",
            "",
            "e",
            "Revised v2",
            "",
            "",
            "y",
        ]
        with patch("builtins.input", side_effect=inputs):
            result, history = _manual_idea_refinement("Original", run_id="run_abc")
        assert result == "Revised v2"
        assert len(history) == 2
        assert mock_save.call_count == 2
        first_call = mock_save.call_args_list[0][1]
        assert first_call["run_id"] == "run_abc"
        assert first_call["idea"] == "Original"
        assert first_call["content"] == "Revised v1"

    @patch("crewai_productfeature_planner.main.save_executive_summary")
    def test_no_run_id_skips_save(self, mock_save):
        """Without run_id, no save_executive_summary calls should be made."""
        inputs = ["e", "Revised", "", "", "y"]
        with patch("builtins.input", side_effect=inputs):
            _manual_idea_refinement("Original")  # no run_id
        mock_save.assert_not_called()


# ── _approve_refined_idea ────────────────────────────────────


class TestApproveRefinedIdea:
    """Tests for the idea approval prompt."""

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_approve_yes(self, mock_mark):
        """[y] should return False (continue to sections)."""
        history = [{"iteration": 1, "idea": "v1"}, {"iteration": 2, "idea": "Refined"}]
        with patch("builtins.input", return_value="y"):
            result = _approve_refined_idea("Refined", "Original", "run123", refinement_history=history)
        assert result is False
        mock_mark.assert_not_called()

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_approve_yes_full(self, mock_mark):
        with patch("builtins.input", return_value="yes"):
            result = _approve_refined_idea("Refined", "Orig", "r1", refinement_history=[])
        assert result is False
        mock_mark.assert_not_called()

    def test_cancel_exits_program(self):
        """[c] should exit the CLI program via sys.exit(0)."""
        with patch("builtins.input", return_value="c"):
            with pytest.raises(SystemExit) as exc_info:
                _approve_refined_idea("Refined", "Original", "run456")
        assert exc_info.value.code == 0

    def test_cancel_full_word_exits_program(self):
        with patch("builtins.input", return_value="cancel"):
            with pytest.raises(SystemExit) as exc_info:
                _approve_refined_idea("Refined", "Orig", "r2")
        assert exc_info.value.code == 0

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_invalid_then_valid(self, mock_mark, capsys):
        with patch("builtins.input", side_effect=["x", "z", "y"]):
            result = _approve_refined_idea("Refined", "Orig", "r3")
        assert result is False
        out = capsys.readouterr().out
        assert out.count("Please enter") == 2

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_case_insensitive(self, mock_mark):
        with patch("builtins.input", return_value="Y"):
            result = _approve_refined_idea("R", "O", "r4")
        assert result is False


# ── _run_single_flow refinement wiring ──────────────────────


class TestRunSingleFlowRefinement:
    """Verify that _run_single_flow wires refinement mode into the flow."""

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.create_job")
    @patch("crewai_productfeature_planner.main._approve_refined_idea")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    @patch("crewai_productfeature_planner.main._manual_idea_refinement")
    def test_manual_mode_continue_to_prd(
        self, mock_refine, mock_mode, mock_approve, mock_create, mock_started, mock_completed
    ):
        """Manual mode + continue should set state and proceed to PRD flow."""
        mock_mode.return_value = "manual"
        mock_refine.return_value = ("Enriched idea", [{"iteration": 1, "idea": "Enriched idea"}])
        mock_approve.return_value = False  # continue to PRD

        flow_mock = None

        def capture_kickoff(self_flow):
            nonlocal flow_mock
            flow_mock = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "Final PRD"
            return "done"

        with (
            patch.object(
                __import__("crewai_productfeature_planner.flows.prd_flow", fromlist=["PRDFlow"]).PRDFlow,
                "kickoff",
                capture_kickoff,
            ),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea="Raw idea")

        assert flow_mock is not None
        assert flow_mock.state.idea == "Enriched idea"
        assert flow_mock.state.original_idea == "Raw idea"
        assert flow_mock.state.idea_refined is True

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.create_job")
    @patch("crewai_productfeature_planner.main._approve_refined_idea")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    @patch("crewai_productfeature_planner.main._manual_idea_refinement")
    def test_manual_mode_finalize_idea(
        self, mock_refine, mock_mode, mock_approve, mock_create, mock_started, mock_completed
    ):
        """Manual mode + approve should finalize idea and NOT proceed to PRD."""
        mock_mode.return_value = "manual"
        mock_refine.return_value = ("Enriched idea", [{"iteration": 1, "idea": "Enriched idea"}])
        mock_approve.return_value = True  # finalize

        from crewai_productfeature_planner.flows.prd_flow import PRDFlow
        with patch.object(PRDFlow, "kickoff") as mock_kickoff:
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea="Raw idea")

        # kickoff should NOT be called — idea was finalized before PRD
        mock_kickoff.assert_not_called()
        mock_completed.assert_called_once()

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.create_job")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    def test_agent_mode_leaves_state_for_flow(
        self, mock_mode, mock_create, mock_started, mock_completed
    ):
        """Agent mode should not set idea_refined — let the flow handle it."""
        mock_mode.return_value = "agent"

        flow_mock = None

        def capture_kickoff(self_flow):
            nonlocal flow_mock
            flow_mock = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "Final PRD"
            return "done"

        with (
            patch.object(
                __import__("crewai_productfeature_planner.flows.prd_flow", fromlist=["PRDFlow"]).PRDFlow,
                "kickoff",
                capture_kickoff,
            ),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea="Raw idea")

        assert flow_mock is not None
        assert flow_mock.state.idea == "Raw idea"
        assert flow_mock.state.idea_refined is False
        # idea_approval_callback should be set for agent mode
        assert flow_mock.idea_approval_callback is not None


class TestResumedFlowRefinement:
    """Verify refinement prompt behaviour when resuming an existing run."""

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.reactivate_job")
    @patch("crewai_productfeature_planner.main._approve_refined_idea")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    @patch("crewai_productfeature_planner.main._manual_idea_refinement")
    @patch("crewai_productfeature_planner.main._check_resumable_runs")
    @patch("crewai_productfeature_planner.main._restore_prd_state")
    def test_resumed_unrefined_shows_prompt(
        self, mock_restore, mock_check, mock_refine, mock_mode, mock_approve,
        mock_reactivate, mock_started, mock_completed,
    ):
        """Resuming a run whose idea was NOT refined should show the choice prompt."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow, PRDState
        from crewai_productfeature_planner.apis.prd.models import PRDDraft

        # Build a resumed flow with idea_refined=False
        flow = PRDFlow()
        flow.state.idea = "Existing idea"
        flow.state.run_id = "abc123"
        flow.state.idea_refined = False
        mock_check.return_value = {"run_id": "abc123", "idea": "Existing idea"}
        mock_restore.return_value = flow
        mock_mode.return_value = "manual"
        mock_refine.return_value = ("Improved existing idea", [{"iteration": 1, "idea": "Improved existing idea"}])
        mock_approve.return_value = False  # continue to PRD

        captured = None

        def capture_kickoff(self_flow):
            nonlocal captured
            captured = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "PRD"
            return "done"

        with (
            patch.object(PRDFlow, "kickoff", capture_kickoff),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea=None)

        mock_mode.assert_called_once()
        mock_refine.assert_called_once()
        # Verify run_id was passed as kwarg
        _, refine_kwargs = mock_refine.call_args
        assert refine_kwargs.get("run_id") is not None or len(mock_refine.call_args[0]) >= 1
        mock_approve.assert_called_once()
        assert captured.state.idea == "Improved existing idea"
        assert captured.state.original_idea == "Existing idea"
        assert captured.state.idea_refined is True

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.reactivate_job")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    @patch("crewai_productfeature_planner.main._check_resumable_runs")
    @patch("crewai_productfeature_planner.main._restore_prd_state")
    def test_resumed_already_refined_skips_prompt(
        self, mock_restore, mock_check, mock_mode,
        mock_reactivate, mock_started, mock_completed,
    ):
        """Resuming a run whose idea was already refined should skip the prompt."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        flow.state.idea = "Already enriched idea"
        flow.state.run_id = "xyz789"
        flow.state.idea_refined = True
        flow.state.original_idea = "Raw original"
        mock_check.return_value = {"run_id": "xyz789", "idea": "Already enriched idea"}
        mock_restore.return_value = flow

        captured = None

        def capture_kickoff(self_flow):
            nonlocal captured
            captured = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "PRD"
            return "done"

        with (
            patch.object(PRDFlow, "kickoff", capture_kickoff),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea=None)

        mock_mode.assert_not_called()
        assert captured.state.idea == "Already enriched idea"
        assert captured.state.idea_refined is True

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.reactivate_job")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    @patch("crewai_productfeature_planner.main._check_resumable_runs")
    @patch("crewai_productfeature_planner.main._restore_prd_state")
    def test_resumed_agent_mode(
        self, mock_restore, mock_check, mock_mode,
        mock_reactivate, mock_started, mock_completed,
    ):
        """Resuming with agent mode should leave idea_refined False for the flow."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        flow.state.idea = "Existing idea"
        flow.state.run_id = "res456"
        flow.state.idea_refined = False
        mock_check.return_value = {"run_id": "res456", "idea": "Existing idea"}
        mock_restore.return_value = flow
        mock_mode.return_value = "agent"

        captured = None

        def capture_kickoff(self_flow):
            nonlocal captured
            captured = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "PRD"
            return "done"

        with (
            patch.object(PRDFlow, "kickoff", capture_kickoff),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea=None)

        mock_mode.assert_called_once()
        assert captured.state.idea == "Existing idea"
        assert captured.state.idea_refined is False
        assert captured.state.original_idea == ""


# ── Resume continuation prompt ───────────────────────────────


class TestResumeContinuationPrompt:
    """Verify the continue/cancel prompt shown when resuming a run
    that already has sections or executive summary in progress."""

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.reactivate_job")
    @patch("crewai_productfeature_planner.main._check_resumable_runs")
    @patch("crewai_productfeature_planner.main._restore_prd_state")
    def test_continue_resumes_flow(
        self, mock_restore, mock_check,
        mock_reactivate, mock_started, mock_completed,
    ):
        """[y] at the resume prompt should continue to kickoff."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow
        from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryIteration

        flow = PRDFlow()
        flow.state.idea = "Existing idea"
        flow.state.run_id = "resume-1"
        flow.state.idea_refined = True
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(content="v1", iteration=1)
        )
        mock_check.return_value = {"run_id": "resume-1", "idea": "Existing idea"}
        mock_restore.return_value = flow

        captured = None

        def capture_kickoff(self_flow):
            nonlocal captured
            captured = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "PRD"
            return "done"

        with (
            patch.object(PRDFlow, "kickoff", capture_kickoff),
            patch("crewai_productfeature_planner.main.mark_completed"),
            patch("builtins.input", return_value="y"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea=None)

        assert captured is not None
        assert captured.state.run_id == "resume-1"

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.reactivate_job")
    @patch("crewai_productfeature_planner.main._check_resumable_runs")
    @patch("crewai_productfeature_planner.main._restore_prd_state")
    def test_cancel_exits_program(
        self, mock_restore, mock_check,
        mock_reactivate, mock_started, mock_completed,
    ):
        """[c] at the resume prompt should exit via sys.exit(0)."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow
        from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryIteration

        flow = PRDFlow()
        flow.state.idea = "Existing idea"
        flow.state.run_id = "resume-2"
        flow.state.idea_refined = True
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(content="v1", iteration=1)
        )
        mock_check.return_value = {"run_id": "resume-2", "idea": "Existing idea"}
        mock_restore.return_value = flow

        with patch("builtins.input", return_value="c"):
            with pytest.raises(SystemExit) as exc_info:
                from crewai_productfeature_planner.main import _run_single_flow
                _run_single_flow(idea=None)
        assert exc_info.value.code == 0

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.reactivate_job")
    @patch("crewai_productfeature_planner.main._check_resumable_runs")
    @patch("crewai_productfeature_planner.main._restore_prd_state")
    def test_no_prompt_when_no_progress(
        self, mock_restore, mock_check,
        mock_reactivate, mock_started, mock_completed,
    ):
        """Resume without exec summary or sections should NOT show the prompt."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        flow.state.idea = "Existing idea"
        flow.state.run_id = "resume-3"
        flow.state.idea_refined = True
        # No exec summary iterations, no section content
        mock_check.return_value = {"run_id": "resume-3", "idea": "Existing idea"}
        mock_restore.return_value = flow

        captured = None

        def capture_kickoff(self_flow):
            nonlocal captured
            captured = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "PRD"
            return "done"

        with (
            patch.object(PRDFlow, "kickoff", capture_kickoff),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea=None)

        # No input() call needed — prompt was not shown
        assert captured is not None


# ── _approve_requirements ────────────────────────────────────


class TestApproveRequirements:
    """Tests for the requirements approval prompt."""

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_approve_yes(self, mock_mark):
        """[y] should approve requirements and return False (continue to sections)."""
        history = [{"iteration": 1, "requirements": "v1"}]
        with patch("builtins.input", return_value="y"):
            result = _approve_requirements(
                "## Feature 1\nReqs", "Test idea", "run789",
                breakdown_history=history,
            )
        assert result is False
        mock_mark.assert_not_called()

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_approve_yes_full(self, mock_mark):
        with patch("builtins.input", return_value="yes"):
            result = _approve_requirements("Reqs", "Idea", "r1", breakdown_history=[])
        assert result is False
        mock_mark.assert_not_called()

    def test_cancel_exits_program(self):
        """[c] should exit the CLI program via sys.exit(0)."""
        with patch("builtins.input", return_value="c"):
            with pytest.raises(SystemExit) as exc_info:
                _approve_requirements("Reqs", "Idea", "r2")
        assert exc_info.value.code == 0

    def test_cancel_full_word_exits_program(self):
        with patch("builtins.input", return_value="cancel"):
            with pytest.raises(SystemExit) as exc_info:
                _approve_requirements("Reqs", "Idea", "r3")
        assert exc_info.value.code == 0

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_invalid_then_valid(self, mock_mark, capsys):
        with patch("builtins.input", side_effect=["x", "z", "y"]):
            result = _approve_requirements("Reqs", "Idea", "r4")
        assert result is False
        out = capsys.readouterr().out
        assert out.count("Please enter") == 2

    @patch("crewai_productfeature_planner.main.mark_completed")
    def test_case_insensitive(self, mock_mark):
        with patch("builtins.input", return_value="Y"):
            result = _approve_requirements("Reqs", "Idea", "r5")
        assert result is False

    def test_truncates_long_requirements(self, capsys):
        """Requirements longer than 3000 chars should be truncated in display."""
        long_reqs = "A" * 4000
        with patch("builtins.input", return_value="y"):
            _approve_requirements(long_reqs, "Idea", "r6")
        out = capsys.readouterr().out
        assert "more chars" in out


# ── RequirementsFinalized handling in _run_single_flow ────────


class TestRunSingleFlowRequirements:
    """Verify that _run_single_flow properly handles RequirementsFinalized."""

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.create_job")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    def test_requirements_finalized_handled(
        self, mock_mode, mock_create, mock_started, mock_completed, capsys,
    ):
        """RequirementsFinalized from flow should be caught and printed."""
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow, RequirementsFinalized

        mock_mode.return_value = "agent"

        def raise_req_finalized(self_flow):
            raise RequirementsFinalized()

        with patch.object(PRDFlow, "kickoff", raise_req_finalized):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea="Test idea")

        mock_completed.assert_called_once()
        out = capsys.readouterr().out
        assert "Requirements finalized" in out

    @patch("crewai_productfeature_planner.main.update_job_completed")
    @patch("crewai_productfeature_planner.main.update_job_started")
    @patch("crewai_productfeature_planner.main.create_job")
    @patch("crewai_productfeature_planner.main._choose_refinement_mode")
    def test_requirements_callback_wired(
        self, mock_mode, mock_create, mock_started, mock_completed,
    ):
        """requirements_approval_callback should be set on the flow."""
        mock_mode.return_value = "agent"

        captured_flow = None

        def capture_kickoff(self_flow):
            nonlocal captured_flow
            captured_flow = self_flow
            self_flow.state.is_ready = True
            self_flow.state.final_prd = "PRD"
            return "done"

        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        with (
            patch.object(PRDFlow, "kickoff", capture_kickoff),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea="Test idea")

        assert captured_flow is not None
        assert captured_flow.requirements_approval_callback is not None


# ── _restore_prd_state ───────────────────────────────────────


class TestRestorePrdState:
    """Tests for _restore_prd_state executive summary restoration."""

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_restores_executive_summary_iterations(self, mock_docs):
        """Should reconstruct executive summary iterations from MongoDB doc."""
        mock_docs.return_value = [{
            "run_id": "run-1",
            "idea": "Test idea",
            "section": {},
            "executive_summary": [
                {"content": "v1", "iteration": 1, "critique": None, "updated_date": "2026-01-01"},
                {"content": "v2", "iteration": 2, "critique": "needs work", "updated_date": "2026-01-02"},
                {"content": "v3", "iteration": 3, "critique": "READY_FOR_DEV", "updated_date": "2026-01-03"},
            ],
        }]

        flow = _restore_prd_state({"run_id": "run-1", "idea": "Test idea"})

        assert len(flow.state.executive_summary.iterations) == 3
        assert flow.state.executive_summary.latest_content == "v3"
        assert flow.state.executive_summary.is_approved is True
        assert flow.state.finalized_idea == "v3"
        assert flow.state.idea_refined is True

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_empty_executive_summary(self, mock_docs):
        """No executive_summary in doc should produce empty iterations."""
        mock_docs.return_value = [{
            "run_id": "run-2",
            "idea": "Test idea",
            "section": {},
        }]

        flow = _restore_prd_state({"run_id": "run-2", "idea": "Test idea"})

        assert len(flow.state.executive_summary.iterations) == 0
        assert flow.state.executive_summary.is_approved is False
        assert flow.state.finalized_idea == ""
        assert flow.state.idea_refined is False

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_no_docs_returns_empty_exec_summary(self, mock_docs):
        """No documents at all should produce empty executive summary."""
        mock_docs.return_value = []

        flow = _restore_prd_state({"run_id": "run-3", "idea": "Test"})

        assert len(flow.state.executive_summary.iterations) == 0
        assert flow.state.finalized_idea == ""

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_partial_executive_summary_fields(self, mock_docs):
        """Iteration records with missing optional fields should still restore."""
        mock_docs.return_value = [{
            "run_id": "run-4",
            "idea": "Test",
            "section": {},
            "executive_summary": [
                {"content": "v1", "iteration": 1},
            ],
        }]

        flow = _restore_prd_state({"run_id": "run-4", "idea": "Test"})

        assert len(flow.state.executive_summary.iterations) == 1
        assert flow.state.executive_summary.iterations[0].content == "v1"
        assert flow.state.executive_summary.iterations[0].critique is None
        assert flow.state.executive_summary.iterations[0].updated_date == ""

    # ── requirements_breakdown restoration ──────────────────────

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_restores_requirements_breakdown(self, mock_docs):
        """Should set requirements_broken_down and rebuild breakdown_history."""
        mock_docs.return_value = [{
            "run_id": "run-rb-1",
            "idea": "Test idea",
            "section": {},
            "executive_summary": [
                {"content": "exec v1", "iteration": 1},
            ],
            "requirements_breakdown": [
                {"content": "reqs v1", "iteration": 1, "critique": "needs work"},
                {"content": "reqs v2", "iteration": 2, "critique": "better"},
                {"content": "reqs v3", "iteration": 3, "critique": "READY_FOR_DEV"},
            ],
        }]

        flow = _restore_prd_state({"run_id": "run-rb-1", "idea": "Test idea"})

        assert flow.state.requirements_broken_down is True
        assert flow.state.requirements_breakdown == "reqs v3"
        assert len(flow.state.breakdown_history) == 3
        assert flow.state.breakdown_history[0]["iteration"] == 1
        assert flow.state.breakdown_history[0]["requirements"] == "reqs v1"
        assert flow.state.breakdown_history[0]["evaluation"] == "needs work"
        assert flow.state.breakdown_history[2]["requirements"] == "reqs v3"

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_empty_requirements_breakdown(self, mock_docs):
        """No requirements_breakdown should leave flag False."""
        mock_docs.return_value = [{
            "run_id": "run-rb-2",
            "idea": "Test idea",
            "section": {},
        }]

        flow = _restore_prd_state({"run_id": "run-rb-2", "idea": "Test idea"})

        assert flow.state.requirements_broken_down is False
        assert flow.state.requirements_breakdown == ""
        assert flow.state.breakdown_history == []

    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_requirements_breakdown_with_empty_content(self, mock_docs):
        """Iteration records with no content should not set flag."""
        mock_docs.return_value = [{
            "run_id": "run-rb-3",
            "idea": "Test idea",
            "section": {},
            "requirements_breakdown": [
                {"iteration": 1},  # no content key
            ],
        }]

        flow = _restore_prd_state({"run_id": "run-rb-3", "idea": "Test idea"})

        assert flow.state.requirements_broken_down is False

    # ── section field missing edge case ─────────────────────────

    @patch("crewai_productfeature_planner.main.ensure_section_field")
    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_restore_reinitialises_missing_section_field(
        self, mock_docs, mock_ensure,
    ):
        """When section field is missing, should call ensure_section_field and proceed."""
        # Document intentionally lacks 'section' key
        mock_docs.return_value = [{
            "run_id": "run-no-sec",
            "idea": "Test idea",
            "executive_summary": [
                {"content": "exec v1", "iteration": 1, "critique": None},
            ],
        }]

        flow = _restore_prd_state({"run_id": "run-no-sec", "idea": "Test idea"})

        mock_ensure.assert_called_once_with("run-no-sec")
        # All sections should be empty — nothing to restore
        assert all(s.content == "" for s in flow.state.draft.sections)
        assert all(s.iteration == 0 for s in flow.state.draft.sections)
        # Executive summary should still be restored
        assert len(flow.state.executive_summary.iterations) == 1

    @patch("crewai_productfeature_planner.main.ensure_section_field")
    @patch("crewai_productfeature_planner.main.get_run_documents")
    def test_restore_does_not_call_ensure_when_section_present(
        self, mock_docs, mock_ensure,
    ):
        """When section field exists, ensure_section_field should NOT be called."""
        mock_docs.return_value = [{
            "run_id": "run-with-sec",
            "idea": "Test idea",
            "section": {
                "problem_statement": [
                    {"content": "ps v1", "iteration": 1, "critique": "", "updated_date": ""},
                ],
            },
        }]

        flow = _restore_prd_state({"run_id": "run-with-sec", "idea": "Test idea"})

        mock_ensure.assert_not_called()
        ps = flow.state.draft.get_section("problem_statement")
        assert ps.content == "ps v1"


# ══════════════════════════════════════════════════════════════
# _kill_stale_crew_processes
# ══════════════════════════════════════════════════════════════


class TestKillStaleCrewProcesses:
    """Tests for _kill_stale_crew_processes."""

    @patch("crewai_productfeature_planner.main.subprocess.run")
    @patch("crewai_productfeature_planner.main.os.kill")
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_kills_stale_run_crew_process(self, _getpid, mock_kill, mock_ps):
        mock_ps.return_value.stdout = (
            "  PID  PPID COMMAND\n"
            "  100     1 /path/to/.venv/bin/python main.py\n"
            "  200     1 /path/to/.venv/bin/python /path/to/.venv/bin/run_crew\n"
        )
        killed = _kill_stale_crew_processes()
        assert killed == 1
        mock_kill.assert_called_once_with(200, __import__("signal").SIGTERM)

    @patch("crewai_productfeature_planner.main.subprocess.run")
    @patch("crewai_productfeature_planner.main.os.kill")
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_does_not_kill_self(self, _getpid, mock_kill, mock_ps):
        mock_ps.return_value.stdout = (
            "  PID  PPID COMMAND\n"
            "  100     1 /path/to/.venv/bin/python /path/to/.venv/bin/run_crew\n"
        )
        killed = _kill_stale_crew_processes()
        assert killed == 0
        mock_kill.assert_not_called()

    @patch("crewai_productfeature_planner.main.subprocess.run")
    @patch("crewai_productfeature_planner.main.os.kill")
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_does_not_kill_ancestor_processes(self, _getpid, mock_kill, mock_ps):
        """crewai run → uv run run_crew → our process.

        The 'uv run run_crew' parent must NOT be killed even though its
        command line matches 'run_crew'.
        """
        mock_ps.return_value.stdout = (
            "  PID  PPID COMMAND\n"
            "   10     1 crewai run\n"
            "   50    10 uv run run_crew\n"
            "  100    50 /path/to/.venv/bin/python main:run\n"
            "  999     1 /old/.venv/bin/run_crew\n"
        )
        killed = _kill_stale_crew_processes()
        # Only PID 999 (the stale process) should be killed.
        # PID 50 is our parent and must be protected.
        assert killed == 1
        mock_kill.assert_called_once_with(999, __import__("signal").SIGTERM)

    @patch("crewai_productfeature_planner.main.subprocess.run")
    @patch("crewai_productfeature_planner.main.os.kill")
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_ignores_unrelated_processes(self, _getpid, mock_kill, mock_ps):
        mock_ps.return_value.stdout = (
            "  PID  PPID COMMAND\n"
            "  100     1 /path/python main.py\n"
            "  300     1 /usr/bin/python some_other_script\n"
            "  400     1 vim main.py\n"
        )
        killed = _kill_stale_crew_processes()
        assert killed == 0
        mock_kill.assert_not_called()

    @patch("crewai_productfeature_planner.main.subprocess.run")
    @patch("crewai_productfeature_planner.main.os.kill")
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_handles_already_gone_process(self, _getpid, mock_kill, mock_ps):
        mock_ps.return_value.stdout = (
            "  PID  PPID COMMAND\n"
            "  100     1 /path/python main.py\n"
            "  500     1 /path/to/.venv/bin/run_crew\n"
        )
        mock_kill.side_effect = ProcessLookupError()
        killed = _kill_stale_crew_processes()
        assert killed == 0

    @patch("crewai_productfeature_planner.main.subprocess.run",
           side_effect=Exception("ps not available"))
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_handles_ps_failure_gracefully(self, _getpid, mock_ps):
        killed = _kill_stale_crew_processes()
        assert killed == 0

    @patch("crewai_productfeature_planner.main.subprocess.run")
    @patch("crewai_productfeature_planner.main.os.kill")
    @patch("crewai_productfeature_planner.main.os.getpid", return_value=100)
    def test_kills_multiple_stale_processes(self, _getpid, mock_kill, mock_ps):
        mock_ps.return_value.stdout = (
            "  PID  PPID COMMAND\n"
            "  100     1 /path/python main.py\n"
            "  200     1 /path/run_crew\n"
            "  300     1 /path/crewai_productfeature_planner\n"
            "  400     1 /path/run_prd_flow\n"
        )
        killed = _kill_stale_crew_processes()
        assert killed == 3
        assert mock_kill.call_count == 3


# ══════════════════════════════════════════════════════════════
# _assemble_prd_from_doc  /  _max_iteration_from_doc
# ══════════════════════════════════════════════════════════════


class TestAssemblePrdFromDoc:
    """Tests for _assemble_prd_from_doc."""

    def test_assembles_full_prd(self):
        """Should assemble exec summary + sections into PRD markdown."""
        doc = {
            "run_id": "run-1",
            "executive_summary": [
                {"content": "exec v1", "iteration": 1},
                {"content": "exec v2", "iteration": 2},
            ],
            "section": {
                "problem_statement": [
                    {"content": "Problem v1", "iteration": 1},
                    {"content": "Problem v2", "iteration": 2},
                ],
                "user_personas": [
                    {"content": "Personas v1", "iteration": 1},
                ],
            },
        }
        result = _assemble_prd_from_doc(doc)
        assert "# Product Requirements Document" in result
        assert "Executive Summary" in result
        assert "exec v2" in result  # uses latest
        assert "exec v1" not in result
        assert "Problem Statement" in result
        assert "Problem v2" in result  # uses latest
        assert "User Personas" in result
        assert "Personas v1" in result

    def test_empty_doc_returns_empty(self):
        """Should return empty string for empty document."""
        assert _assemble_prd_from_doc({}) == ""

    def test_only_executive_summary(self):
        """Should work with only executive summary."""
        doc = {
            "executive_summary": [
                {"content": "Summary content", "iteration": 1},
            ],
        }
        result = _assemble_prd_from_doc(doc)
        assert "Executive Summary" in result
        assert "Summary content" in result

    def test_skips_executive_summary_in_sections(self):
        """Should not duplicate exec summary from both top-level and section."""
        doc = {
            "executive_summary": [
                {"content": "Top-level exec", "iteration": 1},
            ],
            "section": {
                "executive_summary": [
                    {"content": "Section exec", "iteration": 1},
                ],
            },
        }
        result = _assemble_prd_from_doc(doc)
        assert result.count("Executive Summary") == 1
        assert "Top-level exec" in result

    def test_empty_section_content_skipped(self):
        """Sections with empty content should be skipped."""
        doc = {
            "section": {
                "problem_statement": [
                    {"content": "", "iteration": 1},
                ],
            },
        }
        result = _assemble_prd_from_doc(doc)
        assert result == ""


class TestMaxIterationFromDoc:
    """Tests for _max_iteration_from_doc."""

    def test_counts_executive_summary_iterations(self):
        doc = {
            "executive_summary": [
                {"content": "v1", "iteration": 1},
                {"content": "v2", "iteration": 2},
                {"content": "v3", "iteration": 3},
            ],
        }
        assert _max_iteration_from_doc(doc) == 3

    def test_counts_section_iterations(self):
        doc = {
            "section": {
                "problem_statement": [
                    {"content": "v1", "iteration": 1},
                    {"content": "v2", "iteration": 5},
                ],
            },
        }
        assert _max_iteration_from_doc(doc) == 5

    def test_returns_zero_for_empty_doc(self):
        assert _max_iteration_from_doc({}) == 0

    def test_uses_highest_across_all_sources(self):
        doc = {
            "executive_summary": [
                {"content": "v1", "iteration": 1},
                {"content": "v2", "iteration": 2},
            ],
            "section": {
                "problem_statement": [
                    {"content": "v1", "iteration": 7},
                ],
            },
        }
        assert _max_iteration_from_doc(doc) == 7


# ══════════════════════════════════════════════════════════════
# _generate_missing_outputs
# ══════════════════════════════════════════════════════════════


class TestGenerateMissingOutputs:
    """Tests for _generate_missing_outputs."""

    @patch("crewai_productfeature_planner.main.save_output_file")
    @patch("crewai_productfeature_planner.tools.file_write_tool.PRDFileWriteTool")
    @patch("crewai_productfeature_planner.main.find_completed_without_output")
    def test_generates_output_for_completed_docs(
        self, mock_find, mock_writer_cls, mock_save_output,
    ):
        """Should write markdown for each completed doc without output."""
        mock_find.return_value = [
            {
                "run_id": "run-1",
                "executive_summary": [
                    {"content": "Summary", "iteration": 1},
                ],
                "section": {
                    "problem_statement": [
                        {"content": "Problem", "iteration": 1},
                    ],
                },
            },
        ]
        mock_writer = MagicMock()
        mock_writer._run.return_value = "PRD saved to output/prds/2026/02/prd_v1.md"
        mock_writer_cls.return_value = mock_writer

        count = _generate_missing_outputs()

        assert count == 1
        mock_writer._run.assert_called_once()
        mock_save_output.assert_called_once_with(
            "run-1", "output/prds/2026/02/prd_v1.md",
        )

    @patch("crewai_productfeature_planner.main.find_completed_without_output")
    def test_returns_zero_when_none_found(self, mock_find):
        """Should return 0 when no completed docs are missing output."""
        mock_find.return_value = []
        assert _generate_missing_outputs() == 0

    @patch("crewai_productfeature_planner.main.find_completed_without_output")
    def test_returns_zero_on_db_error(self, mock_find):
        """Should return 0 when DB query fails."""
        mock_find.side_effect = Exception("connection refused")
        assert _generate_missing_outputs() == 0

    @patch("crewai_productfeature_planner.main.save_output_file")
    @patch("crewai_productfeature_planner.tools.file_write_tool.PRDFileWriteTool")
    @patch("crewai_productfeature_planner.main.find_completed_without_output")
    def test_skips_docs_with_no_content(
        self, mock_find, mock_writer_cls, mock_save_output,
    ):
        """Should skip docs that assemble to empty content."""
        mock_find.return_value = [
            {"run_id": "run-empty", "section": {}},
        ]

        count = _generate_missing_outputs()

        assert count == 0
        mock_writer_cls.assert_not_called()
        mock_save_output.assert_not_called()

    @patch("crewai_productfeature_planner.main.save_output_file")
    @patch("crewai_productfeature_planner.tools.file_write_tool.PRDFileWriteTool")
    @patch("crewai_productfeature_planner.main.find_completed_without_output")
    def test_continues_on_individual_failure(
        self, mock_find, mock_writer_cls, mock_save_output,
    ):
        """Should continue processing remaining docs when one fails."""
        mock_find.return_value = [
            {
                "run_id": "run-bad",
                "executive_summary": [
                    {"content": "Summary", "iteration": 1},
                ],
            },
            {
                "run_id": "run-good",
                "executive_summary": [
                    {"content": "Summary 2", "iteration": 1},
                ],
            },
        ]
        mock_writer = MagicMock()
        mock_writer._run.side_effect = [
            OSError("disk full"),
            "PRD saved to output/prds/2026/02/prd_v1.md",
        ]
        mock_writer_cls.return_value = mock_writer

        count = _generate_missing_outputs()

        assert count == 1
        assert mock_writer._run.call_count == 2


# ══════════════════════════════════════════════════════════════
# _publish_unpublished_prds
# ══════════════════════════════════════════════════════════════


class TestPublishUnpublishedPrds:
    """Tests for _publish_unpublished_prds startup recovery."""

    def test_returns_zero_without_confluence_credentials(self, monkeypatch):
        """Should return 0 when Confluence credentials are missing."""
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        monkeypatch.delenv("CONFLUENCE_SPACE_KEY", raising=False)
        monkeypatch.delenv("CONFLUENCE_USERNAME", raising=False)
        assert _publish_unpublished_prds() == 0

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    @patch(
        "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
        return_value=True,
    )
    def test_returns_zero_when_none_found(self, mock_has_cred, mock_get_db):
        """Should return 0 when no unpublished PRDs exist."""
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = []
        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db
        assert _publish_unpublished_prds() == 0

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    @patch(
        "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence"
    )
    @patch(
        "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
        return_value=True,
    )
    def test_publishes_unpublished_prds(
        self, mock_has_cred, mock_publish, mock_get_db,
    ):
        """Should publish each completed doc that hasn't been published."""
        docs = [
            {
                "run_id": "run-1",
                "idea": "Dark mode feature",
                "executive_summary": [
                    {"content": "Summary", "iteration": 1},
                ],
                "section": {
                    "problem_statement": [
                        {"content": "Problem", "iteration": 1},
                    ],
                },
            },
        ]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = docs
        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        mock_publish.return_value = {
            "page_id": "12345",
            "url": "https://example.atlassian.net/wiki/pages/12345",
            "action": "created",
        }

        count = _publish_unpublished_prds()

        assert count == 1
        mock_publish.assert_called_once()

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    @patch(
        "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
        return_value=True,
    )
    def test_skips_docs_with_no_content(
        self, mock_has_cred, mock_get_db,
    ):
        """Should skip docs that assemble to empty content."""
        docs = [{"run_id": "run-empty", "section": {}}]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = docs
        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        count = _publish_unpublished_prds()
        assert count == 0

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    @patch(
        "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence"
    )
    @patch(
        "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
        return_value=True,
    )
    def test_continues_on_individual_failure(
        self, mock_has_cred, mock_publish, mock_get_db,
    ):
        """Should continue when one publish fails."""
        docs = [
            {
                "run_id": "run-bad",
                "idea": "Failing idea",
                "executive_summary": [
                    {"content": "Summary", "iteration": 1},
                ],
            },
            {
                "run_id": "run-good",
                "idea": "Good idea",
                "executive_summary": [
                    {"content": "Summary 2", "iteration": 1},
                ],
            },
        ]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = docs
        mock_collection = MagicMock()
        mock_collection.find.return_value = mock_cursor
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        mock_publish.side_effect = [
            RuntimeError("API error 500"),
            {
                "page_id": "99",
                "url": "https://example.atlassian.net/wiki/pages/99",
                "action": "created",
            },
        ]

        count = _publish_unpublished_prds()

        assert count == 1
        assert mock_publish.call_count == 2

    @patch(
        "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
        return_value=True,
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.get_db",
        side_effect=Exception("connection refused"),
    )
    def test_returns_zero_on_db_error(self, mock_get_db, mock_has_cred):
        """Should return 0 when database query fails."""
        assert _publish_unpublished_prds() == 0


# ── _run_startup_delivery ────────────────────────────────────


class TestRunStartupDelivery:
    """Tests for the autonomous startup delivery orchestrator (crew-based)."""

    # Convenience aliases for the patch targets.
    _CONF = "crewai_productfeature_planner.orchestrator.stages._has_confluence_credentials"
    _JIRA = "crewai_productfeature_planner.orchestrator.stages._has_jira_credentials"
    _DISCOVER = "crewai_productfeature_planner.orchestrator.stages._discover_pending_deliveries"
    _BUILD_CREW = "crewai_productfeature_planner.orchestrator.stages.build_startup_delivery_crew"
    _KICKOFF = "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry"
    _GET_REC = "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record"
    _UPSERT = "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record"
    _STATUS = "crewai_productfeature_planner.orchestrator.stages._print_delivery_status"

    # ── credential gating ─────────────────────────────────────

    @patch(_CONF, return_value=False)
    @patch(_JIRA, return_value=False)
    def test_skips_when_no_credentials(self, _j, _c):
        """Should return 0 when neither Confluence nor Jira is configured."""
        assert _run_startup_delivery() == 0

    # ── no pending items ──────────────────────────────────────

    @patch(_STATUS)
    @patch(_DISCOVER, return_value=[])
    @patch(_CONF, return_value=True)
    @patch(_JIRA, return_value=True)
    def test_returns_zero_when_no_pending_items(self, _j, _c, _disc, _status):
        """Should return 0 when _discover_pending_deliveries returns empty."""
        assert _run_startup_delivery() == 0

    # ── crew execution for pending delivery ───────────────────

    @patch(_STATUS)
    @patch(_UPSERT, return_value=True)
    @patch(_GET_REC, return_value=None)
    @patch(_KICKOFF)
    @patch(_BUILD_CREW)
    @patch(_DISCOVER)
    @patch(_CONF, return_value=True)
    @patch(_JIRA, return_value=True)
    def test_runs_crew_for_pending_delivery(
        self, _j, _c, mock_disc, mock_build, mock_kickoff,
        _rec, _ups, _status,
    ):
        """Should build a CrewAI crew and kickoff for each pending item."""
        mock_disc.return_value = [
            {
                "run_id": "r1",
                "idea": "Dark mode",
                "content": "# PRD\n\n## ES\n\nContent",
                "confluence_done": False,
                "confluence_url": "",
                "jira_done": False,
                "finalized_idea": "Exec summary",
                "func_reqs": "FR1: Login",
                "doc": {"run_id": "r1"},
            },
        ]

        mock_crew = MagicMock()
        mock_build.return_value = mock_crew
        mock_result = MagicMock()
        mock_result.raw = "Published page_id=123 to Confluence. Created Epic PROJ-1."
        mock_kickoff.return_value = mock_result

        result = _run_startup_delivery()

        mock_build.assert_called_once()
        mock_kickoff.assert_called_once_with(
            mock_crew, step_label="startup_delivery_r1",
        )
        # Should have upserted delivery record
        assert _ups.call_count >= 1

    # ── crew error handling ───────────────────────────────────

    @patch(_STATUS)
    @patch(_UPSERT, return_value=True)
    @patch(_GET_REC, return_value=None)
    @patch(_KICKOFF)
    @patch(_BUILD_CREW)
    @patch(_DISCOVER)
    @patch(_CONF, return_value=True)
    @patch(_JIRA, return_value=True)
    def test_records_error_on_crew_failure(
        self, _j, _c, mock_disc, mock_build, mock_kickoff,
        _rec, mock_upsert, _status,
    ):
        """Should record error in productRequirements when crew fails."""
        mock_disc.return_value = [
            {
                "run_id": "r1",
                "idea": "Broken",
                "content": "# PRD",
                "confluence_done": False,
                "confluence_url": "",
                "jira_done": False,
                "finalized_idea": "ES",
                "func_reqs": "",
                "doc": {"run_id": "r1"},
            },
        ]

        mock_crew = MagicMock()
        mock_build.return_value = mock_crew
        mock_kickoff.side_effect = RuntimeError("LLM timeout")

        result = _run_startup_delivery()

        assert result == 0
        # Should have called upsert with error
        last_call = mock_upsert.call_args_list[-1]
        assert "LLM timeout" in str(last_call)

    # ── prints status messages ────────────────────────────────

    @patch(_UPSERT, return_value=True)
    @patch(_GET_REC, return_value=None)
    @patch(_KICKOFF)
    @patch(_BUILD_CREW)
    @patch(_DISCOVER)
    @patch(_CONF, return_value=True)
    @patch(_JIRA, return_value=True)
    def test_prints_progress_messages(
        self, _j, _c, mock_disc, mock_build, mock_kickoff,
        _rec, _ups,
    ):
        """Should print user-facing status messages during delivery."""
        mock_disc.return_value = [
            {
                "run_id": "r1",
                "idea": "Test idea",
                "content": "# PRD content",
                "confluence_done": False,
                "confluence_url": "",
                "jira_done": False,
                "finalized_idea": "ES",
                "func_reqs": "",
                "doc": {"run_id": "r1"},
            },
        ]

        mock_crew = MagicMock()
        mock_crew.tasks = [MagicMock(), MagicMock()]
        mock_crew.agents = [MagicMock(), MagicMock()]
        mock_build.return_value = mock_crew
        mock_result = MagicMock()
        mock_result.raw = "Published to Confluence"
        mock_kickoff.return_value = mock_result

        with patch("builtins.print") as mock_print:
            _run_startup_delivery()

        # Should have printed at least the status messages
        printed_lines = [str(c) for c in mock_print.call_args_list]
        printed_text = " ".join(printed_lines)
        assert "Orchestrator" in printed_text
        assert "1 completed PRD" in printed_text

    # ── database failure ──────────────────────────────────────

    @patch(_DISCOVER, side_effect=Exception("connection refused"))
    @patch(_CONF, return_value=True)
    @patch(_JIRA, return_value=True)
    def test_handles_discovery_failure(self, _j, _c, _disc):
        """Should return 0 when discovery fails."""
        assert _run_startup_delivery() == 0

    # ── persists jira_output to workingIdeas ──────────────────

    @patch(_STATUS)
    @patch("crewai_productfeature_planner.main.get_db")
    @patch(_UPSERT, return_value=True)
    @patch(_GET_REC, return_value=None)
    @patch(_KICKOFF)
    @patch(_BUILD_CREW)
    @patch(_DISCOVER)
    @patch(_CONF, return_value=True)
    @patch(_JIRA, return_value=True)
    def test_persists_jira_output_to_working_ideas(
        self, _j, _c, mock_disc, mock_build, mock_kickoff,
        _rec, _ups, mock_get_db, _status,
    ):
        """Should save jira_output back to the workingIdeas document."""
        mock_disc.return_value = [
            {
                "run_id": "r1",
                "idea": "Jira test",
                "content": "# PRD content",
                "confluence_done": True,
                "confluence_url": "https://wiki.test.com/page/1",
                "jira_done": False,
                "finalized_idea": "ES",
                "func_reqs": "FR1",
                "doc": {"run_id": "r1"},
            },
        ]

        mock_crew = MagicMock()
        mock_build.return_value = mock_crew
        mock_result = MagicMock()
        mock_result.raw = "Created Epic PROJ-1. Created Story PROJ-2."
        mock_kickoff.return_value = mock_result

        wi_col = MagicMock()
        wi_db = MagicMock()
        wi_db.__getitem__ = MagicMock(return_value=wi_col)
        mock_get_db.return_value = wi_db

        _run_startup_delivery()

        # Should have persisted jira output to workingIdeas
        wi_col.update_one.assert_called()
        update_args = wi_col.update_one.call_args
        assert update_args[0][0] == {"run_id": "r1"}
        assert "jira_output" in update_args[0][1]["$set"]

    # ── background wrapper ────────────────────────────────────

    @patch("crewai_productfeature_planner.main._run_startup_delivery")
    def test_background_wrapper_catches_exceptions(self, mock_delivery):
        """_run_startup_delivery_background should not raise on failure."""
        mock_delivery.side_effect = Exception("boom")
        # Should not raise
        _run_startup_delivery_background()

    @patch(_STATUS)
    @patch("crewai_productfeature_planner.main._run_startup_delivery", return_value=3)
    def test_background_wrapper_reports_count(self, mock_delivery, mock_status):
        """_run_startup_delivery_background should print count on success."""
        _run_startup_delivery_background()
        mock_status.assert_called_once()
        assert "3" in mock_status.call_args[0][0]


# ── Output helper functions ──────────────────────────────────


class TestConfluenceCompletedInOutput:
    """Tests for _confluence_completed_in_output."""

    def test_detects_published(self):
        assert _confluence_completed_in_output("Page published successfully")

    def test_detects_created(self):
        assert _confluence_completed_in_output("Created confluence page")

    def test_detects_updated(self):
        assert _confluence_completed_in_output("Updated page_id=123")

    def test_false_on_failure(self):
        assert not _confluence_completed_in_output("Failed to publish to Confluence")

    def test_false_on_unrelated(self):
        assert not _confluence_completed_in_output("Nothing happened")


class TestJiraCompletedInOutput:
    """Tests for _jira_completed_in_output."""

    def test_detects_epic(self):
        assert _jira_completed_in_output("Created Epic PROJ-1")

    def test_detects_story(self):
        assert _jira_completed_in_output("Created Story PROJ-2")

    def test_detects_issue_key(self):
        assert _jira_completed_in_output("issue_key: PROJ-3")

    def test_false_on_failure(self):
        assert not _jira_completed_in_output("Failed to create Jira Epic")

    def test_false_on_unrelated(self):
        assert not _jira_completed_in_output("Nothing happened")


class TestExtractConfluenceUrl:
    """Tests for _extract_confluence_url."""

    def test_extracts_atlassian_url(self):
        text = "Published to https://myco.atlassian.net/wiki/pages/123 successfully"
        assert "atlassian.net/wiki/pages/123" in _extract_confluence_url(text)

    def test_extracts_wiki_url(self):
        text = "Page at https://conf.example.com/wiki/spaces/PRD/page/456"
        assert "/wiki/" in _extract_confluence_url(text)

    def test_returns_empty_when_no_url(self):
        assert _extract_confluence_url("No URL here") == ""

    def test_strips_trailing_punctuation(self):
        text = "See https://co.atlassian.net/wiki/page/1."
        url = _extract_confluence_url(text)
        assert not url.endswith(".")
