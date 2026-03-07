"""Tests for orchestrator._requirements — requirements breakdown stage."""

from unittest.mock import patch

from crewai_productfeature_planner.flows.prd_flow import (
    PRDFlow,
    RequirementsFinalized,
)
from crewai_productfeature_planner.orchestrator.orchestrator import StageResult
from crewai_productfeature_planner.orchestrator._requirements import (
    build_requirements_breakdown_stage,
)


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

    def test_requires_approval_true_with_exec_summary_iterations(self):
        """Approval IS required even when exec summary has iterations.

        Requirements now runs *after* the executive summary, so
        iterations will always be present — they no longer indicate
        a resumed run that already passed the requirements gate.
        """
        from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryIteration

        flow = PRDFlow()
        flow.state.requirements_broken_down = True
        flow.requirements_approval_callback = lambda *a: True
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(content="v1", iteration=1)
        )
        stage = build_requirements_breakdown_stage(flow)
        assert stage.requires_approval() is True

    def test_requires_approval_false_sections_in_progress(self):
        """Auto-skip approval when sections already have content (resume)."""
        flow = PRDFlow()
        flow.state.requirements_broken_down = True
        flow.requirements_approval_callback = lambda *a: True
        flow.state.draft.sections[1].content = "Some drafted content"
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
