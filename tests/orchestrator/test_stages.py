"""Tests for the orchestrator stage factory functions."""

from unittest.mock import MagicMock, patch

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
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    build_confluence_publish_stage,
    build_default_pipeline,
    build_idea_refinement_stage,
    build_jira_ticketing_stage,
    build_post_completion_pipeline,
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

    def test_requires_approval_false_exec_summary_iterations(self):
        """Auto-skip approval when executive summary already has iterations (resume)."""
        from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryIteration

        flow = PRDFlow()
        flow.state.requirements_broken_down = True
        flow.requirements_approval_callback = lambda *a: True
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(content="v1", iteration=1)
        )
        stage = build_requirements_breakdown_stage(flow)
        assert stage.requires_approval() is False

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


# ── _has_confluence_credentials helper ──────────────────────────────


class TestHasConfluenceCredentials:

    def test_all_set(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("CONFLUENCE_USERNAME", "user@example.com")
        monkeypatch.setenv("CONFLUENCE_API_TOKEN", "secret")
        assert _has_confluence_credentials() is True

    def test_missing(self, monkeypatch):
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_SPACE_KEY", raising=False)
        monkeypatch.delenv("CONFLUENCE_USERNAME", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        assert _has_confluence_credentials() is False


# ── _has_jira_credentials helper ────────────────────────────────────


class TestHasJiraCredentials:

    def test_all_set(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")
        assert _has_jira_credentials() is True

    def test_missing(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)
        monkeypatch.delenv("JIRA_USERNAME", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        assert _has_jira_credentials() is False


# ── Confluence Publish Stage ─────────────────────────────────────────


class TestConfluencePublishStage:

    @pytest.fixture()
    def _confluence_env(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://example.atlassian.net/wiki")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "PRD")
        monkeypatch.setenv("CONFLUENCE_USERNAME", "user@example.com")
        monkeypatch.setenv("CONFLUENCE_API_TOKEN", "secret")
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

    def test_stage_name(self):
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert stage.name == "confluence_publish"

    def test_stage_description(self):
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert "confluence" in stage.description.lower()

    def test_skips_without_confluence_credentials(self, monkeypatch):
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_skips_without_gemini_credentials(self, monkeypatch, _confluence_env):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_already_published(self, _confluence_env):
        flow = PRDFlow()
        flow.state.confluence_url = "https://already.published/page"
        flow.state.final_prd = "# PRD"
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_no_final_prd(self, _confluence_env):
        flow = PRDFlow()
        flow.state.final_prd = ""
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is True

    def test_does_not_skip_with_credentials_and_content(self, _confluence_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow.state.confluence_url = ""
        stage = build_confluence_publish_stage(flow)
        assert stage.should_skip() is False

    @patch("crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence")
    def test_run_publishes(self, mock_publish, _confluence_env):
        mock_publish.return_value = {
            "action": "created",
            "page_id": "12345",
            "url": "https://example.atlassian.net/wiki/pages/12345",
        }
        flow = PRDFlow()
        flow.state.idea = "Dark mode feature"
        flow.state.final_prd = "# PRD\nDark mode"
        flow.state.run_id = "run-1"
        stage = build_confluence_publish_stage(flow)

        result = stage.run()

        assert "created" in result.output
        assert "12345" in result.output
        mock_publish.assert_called_once()

    @patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db")
    def test_apply_updates_state(self, mock_get_db, _confluence_env):
        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        flow = PRDFlow()
        flow.state.run_id = "run-1"
        stage = build_confluence_publish_stage(flow)

        result = StageResult(
            output="created|12345|https://example.atlassian.net/wiki/pages/12345"
        )
        stage.apply(result)

        assert flow.state.confluence_url == "https://example.atlassian.net/wiki/pages/12345"


# ── Jira Ticketing Stage ────────────────────────────────────────────


class TestJiraTicketingStage:

    @pytest.fixture()
    def _jira_env(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
        monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
        monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "secret")
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

    def test_stage_name(self):
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert stage.name == "jira_ticketing"

    def test_stage_description(self):
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert "jira" in stage.description.lower()

    def test_skips_without_jira_credentials(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_skips_without_gemini_credentials(self, monkeypatch, _jira_env):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_skips_when_no_final_prd(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = ""
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_does_not_skip_with_credentials_and_prd(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is False

    def test_apply_updates_state(self, _jira_env):
        flow = PRDFlow()
        stage = build_jira_ticketing_stage(flow)

        result = StageResult(
            output="Epic: key=PRD-100\nStories: PRD-101, PRD-102"
        )
        stage.apply(result)

        assert flow.state.jira_output == "Epic: key=PRD-100\nStories: PRD-101, PRD-102"


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
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "key")

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        orch = build_post_completion_pipeline(flow)
        orch.run_pipeline()

        assert "confluence_publish" in orch.skipped
        assert "jira_ticketing" in orch.skipped
        assert orch.completed == []
