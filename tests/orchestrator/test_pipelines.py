"""Tests for orchestrator._pipelines — default and post-completion pipelines."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.flows.prd_flow import (
    IdeaFinalized,
    PRDFlow,
    RequirementsFinalized,
)
from crewai_productfeature_planner.orchestrator.orchestrator import AgentOrchestrator
from crewai_productfeature_planner.orchestrator._pipelines import (
    build_default_pipeline,
    build_post_completion_pipeline,
)


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
        """IdeaFinalized stops the pipeline when no Gemini (no breakdown)."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        flow = PRDFlow()
        flow.state.idea = "raw idea"
        flow.state.idea_refined = True  # already refined (skipped stage)
        flow.idea_approval_callback = lambda *a: True  # finalize

        orch = build_default_pipeline(flow)
        with pytest.raises(IdeaFinalized):
            orch.run_pipeline()

        # Both stages skipped (no Gemini), but idea gate fired
        assert "idea_refinement" in orch.skipped

    def test_pipeline_requirements_finalization(self, monkeypatch):
        """RequirementsFinalized stops the pipeline after requirements."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "raw idea"
        # idea approval auto-bypassed — requirements breakdown follows
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


# ── build_post_completion_pipeline ───────────────────────────────────


class TestBuildPostCompletionPipeline:

    def test_returns_orchestrator(self):
        flow = PRDFlow()
        orch = build_post_completion_pipeline(flow)
        assert isinstance(orch, AgentOrchestrator)

    def test_has_two_stages(self):
        flow = PRDFlow()
        orch = build_post_completion_pipeline(flow)
        assert len(orch.stages) == 2

    def test_stage_order(self):
        flow = PRDFlow()
        orch = build_post_completion_pipeline(flow)
        names = [s.name for s in orch.stages]
        assert names == ["confluence_publish", "jira_ticketing"]

    def test_skips_all_without_credentials(self, monkeypatch):
        """Without Atlassian credentials, all stages skip."""
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        orch = build_post_completion_pipeline(flow)
        orch.run_pipeline()

        assert "confluence_publish" in orch.skipped
        assert "jira_ticketing" in orch.skipped
        assert orch.completed == []


# ── Progress callback wiring ─────────────────────────────────────────


class TestOrchestratorProgressCallback:
    """Progress callback is fired by the orchestrator during stage lifecycle."""

    def test_fires_start_and_complete_events(self, monkeypatch):
        """Stage start and complete events are forwarded to the callback."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "raw idea"
        cb = MagicMock()
        flow.progress_callback = cb

        with patch(
            "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
            return_value=("refined", [{"iteration": 1}]),
        ), patch(
            "crewai_productfeature_planner.agents.requirements_breakdown"
            ".breakdown_requirements",
            return_value=("## Req", [{"iteration": 1}, {"iteration": 2}]),
        ):
            orch = build_default_pipeline(flow)
            orch.run_pipeline()

        event_types = [c[0][0] for c in cb.call_args_list]
        assert "pipeline_stage_start" in event_types
        assert "pipeline_stage_complete" in event_types

        # Verify details on the idea_refinement complete event
        complete_calls = [
            c for c in cb.call_args_list
            if c[0][0] == "pipeline_stage_complete"
        ]
        idea_complete = [
            c for c in complete_calls if c[0][1]["stage"] == "idea_refinement"
        ]
        assert len(idea_complete) == 1
        assert idea_complete[0][0][1]["iterations"] == 1

        req_complete = [
            c for c in complete_calls
            if c[0][1]["stage"] == "requirements_breakdown"
        ]
        assert len(req_complete) == 1
        assert req_complete[0][0][1]["iterations"] == 2

    def test_fires_skipped_event(self, monkeypatch):
        """Skipped stages fire pipeline_stage_skipped."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.idea = "done"
        flow.state.idea_refined = True
        flow.state.requirements_broken_down = True
        cb = MagicMock()
        flow.progress_callback = cb

        orch = build_default_pipeline(flow)
        orch.run_pipeline()

        event_types = [c[0][0] for c in cb.call_args_list]
        assert event_types.count("pipeline_stage_skipped") == 2

    def test_no_callback_no_error(self, monkeypatch):
        """Pipeline runs fine without a progress callback."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        flow = PRDFlow()
        flow.state.idea = "test"
        orch = build_default_pipeline(flow)
        orch.run_pipeline()  # should not raise
