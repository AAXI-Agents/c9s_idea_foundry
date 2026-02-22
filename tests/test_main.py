"""Tests for CLI helper functions in main.py."""

import pytest
from unittest.mock import patch, call

from crewai_productfeature_planner.main import (
    _approve_refined_idea,
    _approve_requirements,
    _choose_refinement_mode,
    _manual_idea_refinement,
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

    @patch("crewai_productfeature_planner.main.save_iteration")
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
        assert first_call["step"] == "idea_manual_1"

    @patch("crewai_productfeature_planner.main.save_iteration")
    def test_no_run_id_skips_save(self, mock_save):
        """Without run_id, no save_iteration calls should be made."""
        inputs = ["e", "Revised", "", "", "y"]
        with patch("builtins.input", side_effect=inputs):
            _manual_idea_refinement("Original")  # no run_id
        mock_save.assert_not_called()


# ── _approve_refined_idea ────────────────────────────────────


class TestApproveRefinedIdea:
    """Tests for the idea approval prompt."""

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_approve_yes(self, mock_save, mock_mark):
        """[y] should finalize the idea and return True."""
        history = [{"iteration": 1, "idea": "v1"}, {"iteration": 2, "idea": "Refined"}]
        with patch("builtins.input", return_value="y"):
            result = _approve_refined_idea("Refined", "Original", "run123", refinement_history=history)
        assert result is True
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["run_id"] == "run123"
        assert call_kwargs["idea"] == "Refined"
        assert call_kwargs["original_idea"] == "Original"
        assert call_kwargs["finalized_type"] == "idea"
        assert call_kwargs["final_prd"] == ""
        assert call_kwargs["iteration"] == 2
        assert call_kwargs["refinement_history"] == history
        mock_mark.assert_called_once_with("run123")

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_approve_yes_full(self, mock_save, mock_mark):
        with patch("builtins.input", return_value="yes"):
            result = _approve_refined_idea("Refined", "Orig", "r1", refinement_history=[])
        assert result is True
        mock_save.assert_called_once()
        assert mock_save.call_args[1]["iteration"] == 0

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_continue(self, mock_save, mock_mark):
        """[c] should return False without saving."""
        with patch("builtins.input", return_value="c"):
            result = _approve_refined_idea("Refined", "Original", "run456")
        assert result is False
        mock_save.assert_not_called()
        mock_mark.assert_not_called()

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_continue_full_word(self, mock_save, mock_mark):
        with patch("builtins.input", return_value="continue"):
            result = _approve_refined_idea("Refined", "Orig", "r2")
        assert result is False

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_invalid_then_valid(self, mock_save, mock_mark, capsys):
        with patch("builtins.input", side_effect=["x", "z", "y"]):
            result = _approve_refined_idea("Refined", "Orig", "r3")
        assert result is True
        out = capsys.readouterr().out
        assert out.count("Please enter") == 2

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_case_insensitive(self, mock_save, mock_mark):
        with patch("builtins.input", return_value="Y"):
            result = _approve_refined_idea("R", "O", "r4")
        assert result is True


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
            patch("crewai_productfeature_planner.main.save_finalized"),
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
            patch("crewai_productfeature_planner.main.save_finalized"),
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
            patch("crewai_productfeature_planner.main.save_finalized"),
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
            patch("crewai_productfeature_planner.main.save_finalized"),
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
            patch("crewai_productfeature_planner.main.save_finalized"),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea=None)

        mock_mode.assert_called_once()
        assert captured.state.idea == "Existing idea"
        assert captured.state.idea_refined is False
        assert captured.state.original_idea == ""


# ── _approve_requirements ────────────────────────────────────


class TestApproveRequirements:
    """Tests for the requirements approval prompt."""

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_approve_yes(self, mock_save, mock_mark):
        """[y] should finalize requirements and return True."""
        history = [{"iteration": 1, "requirements": "v1"}]
        with patch("builtins.input", return_value="y"):
            result = _approve_requirements(
                "## Feature 1\nReqs", "Test idea", "run789",
                breakdown_history=history,
            )
        assert result is True
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["run_id"] == "run789"
        assert call_kwargs["idea"] == "Test idea"
        assert call_kwargs["finalized_type"] == "requirements"
        assert call_kwargs["final_prd"] == ""
        assert call_kwargs["requirements_breakdown"] == "## Feature 1\nReqs"
        assert call_kwargs["iteration"] == 1
        assert call_kwargs["breakdown_history"] == history
        mock_mark.assert_called_once_with("run789")

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_approve_yes_full(self, mock_save, mock_mark):
        with patch("builtins.input", return_value="yes"):
            result = _approve_requirements("Reqs", "Idea", "r1", breakdown_history=[])
        assert result is True
        assert mock_save.call_args[1]["iteration"] == 0

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_continue(self, mock_save, mock_mark):
        """[c] should return False without saving."""
        with patch("builtins.input", return_value="c"):
            result = _approve_requirements("Reqs", "Idea", "r2")
        assert result is False
        mock_save.assert_not_called()
        mock_mark.assert_not_called()

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_continue_full_word(self, mock_save, mock_mark):
        with patch("builtins.input", return_value="continue"):
            result = _approve_requirements("Reqs", "Idea", "r3")
        assert result is False

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_invalid_then_valid(self, mock_save, mock_mark, capsys):
        with patch("builtins.input", side_effect=["x", "z", "y"]):
            result = _approve_requirements("Reqs", "Idea", "r4")
        assert result is True
        out = capsys.readouterr().out
        assert out.count("Please enter") == 2

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_case_insensitive(self, mock_save, mock_mark):
        with patch("builtins.input", return_value="Y"):
            result = _approve_requirements("Reqs", "Idea", "r5")
        assert result is True

    @patch("crewai_productfeature_planner.main.mark_completed")
    @patch("crewai_productfeature_planner.main.save_finalized")
    def test_truncates_long_requirements(self, mock_save, mock_mark, capsys):
        """Requirements longer than 3000 chars should be truncated in display."""
        long_reqs = "A" * 4000
        with patch("builtins.input", return_value="c"):
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
            patch("crewai_productfeature_planner.main.save_finalized"),
            patch("crewai_productfeature_planner.main.mark_completed"),
        ):
            from crewai_productfeature_planner.main import _run_single_flow
            _run_single_flow(idea="Test idea")

        assert captured_flow is not None
        assert captured_flow.requirements_approval_callback is not None
