"""Tests for the orchestrator stage factory functions."""

from unittest.mock import patch

import pytest

from crewai_productfeature_planner.flows.prd_flow import (
    IdeaFinalized,
    PRDFlow,
    RequirementsFinalized,
)
from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    StageResult,
)
from crewai_productfeature_planner.orchestrator.stages import (
    _has_gemini_credentials,
    build_default_pipeline,
    build_idea_refinement_stage,
    build_requirements_breakdown_stage,
)


# ── _has_gemini_credentials helper ───────────────────────────────────


class TestHasGeminiCredentials:

    def test_no_credentials(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        assert _has_gemini_credentials() is False

    def test_api_key_only(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        assert _has_gemini_credentials() is True

    def test_project_only(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
        assert _has_gemini_credentials() is True

    def test_both(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
        assert _has_gemini_credentials() is True


# ── Idea Refinement Stage ────────────────────────────────────────────


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

    def test_requires_approval_true(self):
        flow = PRDFlow()
        flow.state.idea_refined = True
        flow.idea_approval_callback = lambda *a: True
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is True

    def test_requires_approval_false_not_refined(self):
        flow = PRDFlow()
        flow.state.idea_refined = False
        flow.idea_approval_callback = lambda *a: True
        stage = build_idea_refinement_stage(flow)
        assert stage.requires_approval() is False

    def test_requires_approval_false_no_callback(self):
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


# ── Requirements Breakdown Stage ─────────────────────────────────────


class TestRequirementsBreakdownStage:

    def test_stage_name(self):
        flow = PRDFlow()
        stage = build_requirements_breakdown_stage(flow)
        assert stage.name == "requirements_breakdown"

    def test_stage_description(self):
        flow = PRDFlow()
        stage = build_requirements_breakdown_stage(flow)
        assert "requirements" in stage.description.lower()

    def test_finalized_exc_is_requirements_finalized(self):
        flow = PRDFlow()
        stage = build_requirements_breakdown_stage(flow)
        assert stage.finalized_exc is RequirementsFinalized

    def test_skips_when_already_broken_down(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.requirements_broken_down = True
        stage = build_requirements_breakdown_stage(flow)
        assert stage.should_skip() is True

    def test_skips_without_credentials(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        stage = build_requirements_breakdown_stage(flow)
        assert stage.should_skip() is True

    def test_does_not_skip_with_credentials(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.requirements_broken_down = False
        stage = build_requirements_breakdown_stage(flow)
        assert stage.should_skip() is False

    def test_run_calls_breakdown_requirements(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        flow.state.idea = "detailed idea"
        flow.state.run_id = "xyz789"
        stage = build_requirements_breakdown_stage(flow)

        with patch(
            "crewai_productfeature_planner.agents.requirements_breakdown"
            ".breakdown_requirements",
            return_value=("## Feature 1\nreqs", [{"iteration": 1}]),
        ):
            result = stage.run()

        assert result.output == "## Feature 1\nreqs"
        assert result.history == [{"iteration": 1}]

    def test_apply_updates_state(self):
        flow = PRDFlow()
        stage = build_requirements_breakdown_stage(flow)

        result = StageResult(
            output="## Feature 1\nreqs",
            history=[{"iteration": 1}],
        )
        stage.apply(result)

        assert flow.state.requirements_breakdown == "## Feature 1\nreqs"
        assert flow.state.requirements_broken_down is True
        assert flow.state.breakdown_history == [{"iteration": 1}]

    def test_requires_approval_true(self):
        flow = PRDFlow()
        flow.state.requirements_broken_down = True
        flow.requirements_approval_callback = lambda *a: True
        stage = build_requirements_breakdown_stage(flow)
        assert stage.requires_approval() is True

    def test_requires_approval_false_not_broken_down(self):
        flow = PRDFlow()
        flow.state.requirements_broken_down = False
        flow.requirements_approval_callback = lambda *a: True
        stage = build_requirements_breakdown_stage(flow)
        assert stage.requires_approval() is False

    def test_requires_approval_false_no_callback(self):
        flow = PRDFlow()
        flow.state.requirements_broken_down = True
        flow.requirements_approval_callback = None
        stage = build_requirements_breakdown_stage(flow)
        assert stage.requires_approval() is False

    def test_get_approval_calls_callback(self):
        approvals = []
        flow = PRDFlow()
        flow.state.requirements_breakdown = "## Reqs"
        flow.state.idea = "idea"
        flow.state.run_id = "r2"
        flow.state.breakdown_history = [{"i": 1}]

        def cb(reqs, idea, run_id, history):
            approvals.append((reqs, idea, run_id))
            return False

        flow.requirements_approval_callback = cb
        stage = build_requirements_breakdown_stage(flow)
        result = stage.get_approval()

        assert result is False
        assert approvals == [("## Reqs", "idea", "r2")]


# ── build_default_pipeline ───────────────────────────────────────────


class TestBuildDefaultPipeline:

    def test_returns_orchestrator(self):
        flow = PRDFlow()
        orch = build_default_pipeline(flow)
        assert isinstance(orch, AgentOrchestrator)

    def test_has_two_stages(self):
        flow = PRDFlow()
        orch = build_default_pipeline(flow)
        assert len(orch.stages) == 2

    def test_stage_order(self):
        flow = PRDFlow()
        orch = build_default_pipeline(flow)
        names = [s.name for s in orch.stages]
        assert names == ["idea_refinement", "requirements_breakdown"]

    def test_pipeline_skips_all_without_credentials(self, monkeypatch):
        """Without Gemini credentials, all stages skip and pipeline
        completes without error."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        flow = PRDFlow()
        flow.state.idea = "test"
        orch = build_default_pipeline(flow)
        orch.run_pipeline()

        assert orch.skipped == ["idea_refinement", "requirements_breakdown"]
        assert orch.completed == []

    def test_pipeline_runs_idea_then_requirements(self, monkeypatch):
        """With credentials, both stages run in order."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "raw idea"

        with patch(
            "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
            return_value=("refined idea", [{"iteration": 1}]),
        ), patch(
            "crewai_productfeature_planner.agents.requirements_breakdown"
            ".breakdown_requirements",
            return_value=("## Feature 1", [{"iteration": 1}]),
        ):
            orch = build_default_pipeline(flow)
            orch.run_pipeline()

        assert orch.completed == ["idea_refinement", "requirements_breakdown"]
        assert flow.state.idea == "refined idea"
        assert flow.state.idea_refined is True
        assert flow.state.requirements_broken_down is True

    def test_pipeline_idea_finalization_stops_early(self, monkeypatch):
        """IdeaFinalized stops the pipeline before requirements."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "raw idea"
        flow.idea_approval_callback = lambda *a: True  # finalize

        with patch(
            "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
            return_value=("refined idea", [{"iteration": 1}]),
        ):
            orch = build_default_pipeline(flow)
            with pytest.raises(IdeaFinalized):
                orch.run_pipeline()

        assert orch.completed == ["idea_refinement"]
        assert flow.state.requirements_broken_down is False

    def test_pipeline_requirements_finalization(self, monkeypatch):
        """RequirementsFinalized stops the pipeline after requirements."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "raw idea"
        flow.idea_approval_callback = lambda *a: False  # continue
        flow.requirements_approval_callback = lambda *a: True  # finalize

        with patch(
            "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
            return_value=("refined idea", [{"iteration": 1}]),
        ), patch(
            "crewai_productfeature_planner.agents.requirements_breakdown"
            ".breakdown_requirements",
            return_value=("## Feature 1", [{"iteration": 1}]),
        ):
            orch = build_default_pipeline(flow)
            with pytest.raises(RequirementsFinalized):
                orch.run_pipeline()

        assert orch.completed == ["idea_refinement", "requirements_breakdown"]

    def test_pipeline_idea_failure_continues(self, monkeypatch):
        """If idea refinement fails, requirements still runs."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "raw idea"

        with patch(
            "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
            side_effect=RuntimeError("LLM down"),
        ), patch(
            "crewai_productfeature_planner.agents.requirements_breakdown"
            ".breakdown_requirements",
            return_value=("## Feature 1", [{"iteration": 1}]),
        ):
            orch = build_default_pipeline(flow)
            orch.run_pipeline()

        assert orch.failed == ["idea_refinement"]
        assert orch.completed == ["requirements_breakdown"]
        assert flow.state.idea_refined is False
        assert flow.state.requirements_broken_down is True

    def test_pipeline_skips_already_done_stages(self, monkeypatch):
        """Stages that are already done are skipped."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "already refined"
        flow.state.idea_refined = True
        flow.state.requirements_broken_down = True

        orch = build_default_pipeline(flow)
        orch.run_pipeline()

        assert orch.skipped == ["idea_refinement", "requirements_breakdown"]
        assert orch.completed == []
