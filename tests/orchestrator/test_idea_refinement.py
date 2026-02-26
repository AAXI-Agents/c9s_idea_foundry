"""Tests for orchestrator._idea_refinement — idea refinement stage."""

from unittest.mock import patch

from crewai_productfeature_planner.flows.prd_flow import (
    IdeaFinalized,
    PRDFlow,
)
from crewai_productfeature_planner.orchestrator.orchestrator import StageResult
from crewai_productfeature_planner.orchestrator._idea_refinement import (
    build_idea_refinement_stage,
)


class TestIdeaRefinementStage:

    def test_stage_name(self):
        flow = PRDFlow()
        stage = build_idea_refinement_stage(flow)
        assert stage.name == "idea_refinement"

    def test_stage_description(self):
        flow = PRDFlow()
        stage = build_idea_refinement_stage(flow)
        assert "refine" in stage.description.lower()

    def test_finalized_exc_is_idea_finalized(self):
        flow = PRDFlow()
        stage = build_idea_refinement_stage(flow)
        assert stage.finalized_exc is IdeaFinalized

    def test_skips_when_already_refined(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.idea_refined = True
        stage = build_idea_refinement_stage(flow)
        assert stage.should_skip() is True

    def test_skips_without_credentials(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        stage = build_idea_refinement_stage(flow)
        assert stage.should_skip() is True

    def test_does_not_skip_with_credentials(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.idea_refined = False
        stage = build_idea_refinement_stage(flow)
        assert stage.should_skip() is False

    def test_run_calls_refine_idea(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.idea = "raw idea"
        flow.state.run_id = "abc123"
        stage = build_idea_refinement_stage(flow)

        with patch(
            "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
            return_value=("refined idea", [{"iteration": 1}]),
        ):
            result = stage.run()

        assert result.output == "refined idea"
        assert result.history == [{"iteration": 1}]
        # original_idea should be set before run returns
        assert flow.state.original_idea == "raw idea"

    def test_apply_updates_state(self):
        flow = PRDFlow()
        flow.state.idea = "old idea"
        stage = build_idea_refinement_stage(flow)

        result = StageResult(
            output="refined idea",
            history=[{"iteration": 1}],
        )
        stage.apply(result)

        assert flow.state.idea == "refined idea"
        assert flow.state.idea_refined is True
        assert flow.state.refinement_history == [{"iteration": 1}]

    def test_requires_approval_false_breakdown_already_done(self, monkeypatch):
        """Auto-bypass idea approval even when requirements already done."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.idea_refined = True
        flow.state.requirements_broken_down = True
        flow.idea_approval_callback = lambda *a: True
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is False

    def test_requires_approval_true_no_gemini(self, monkeypatch):
        """Approval gate fires when Gemini is unavailable (no breakdown)."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        flow.state.idea_refined = True
        flow.idea_approval_callback = lambda *a: True
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is True

    def test_requires_approval_false_bypass_for_breakdown(self, monkeypatch):
        """Auto-bypass idea approval when requirements breakdown will follow."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.idea_refined = True
        flow.state.requirements_broken_down = False
        flow.idea_approval_callback = lambda *a: True
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is False

    def test_requires_approval_false_not_refined(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        flow.state.idea_refined = False
        flow.idea_approval_callback = lambda *a: True
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is False

    def test_requires_approval_false_no_callback(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        flow.state.idea_refined = True
        flow.idea_approval_callback = None
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is False

    def test_get_approval_calls_callback(self):
        approvals = []
        flow = PRDFlow()
        flow.state.idea = "refined"
        flow.state.original_idea = "raw"
        flow.state.run_id = "r1"
        flow.state.refinement_history = [{"i": 1}]

        def cb(refined, original, run_id, history):
            approvals.append((refined, original, run_id))
            return True

        flow.idea_approval_callback = cb
        stage = build_idea_refinement_stage(flow)
        result = stage.get_approval()

        assert result is True
        assert approvals == [("refined", "raw", "r1")]
