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
    _discover_pending_deliveries,
    _has_confluence_credentials,
    _has_gemini_credentials,
    _has_jira_credentials,
    _print_delivery_status,
    build_confluence_publish_stage,
    build_default_pipeline,
    build_idea_refinement_stage,
    build_jira_ticketing_stage,
    build_post_completion_crew,
    build_post_completion_pipeline,
    build_requirements_breakdown_stage,
    build_startup_delivery_crew,
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


# ── build_post_completion_crew ───────────────────────────────────────


class TestBuildPostCompletionCrew:
    """Tests for the CrewAI-based post-completion crew."""

    _DM = "crewai_productfeature_planner.agents.orchestrator.agent.create_delivery_manager_agent"
    _OA = "crewai_productfeature_planner.agents.orchestrator.agent.create_orchestrator_agent"
    _TC = "crewai_productfeature_planner.agents.orchestrator.agent.get_task_configs"
    _VERBOSE = "crewai_productfeature_planner.scripts.logging_config.is_verbose"
    _CREW_CLS = "crewai.Crew"
    _TASK_CLS = "crewai.Task"
    _HAS_CONF = "crewai_productfeature_planner.orchestrator.stages._has_confluence_credentials"
    _HAS_JIRA = "crewai_productfeature_planner.orchestrator.stages._has_jira_credentials"
    _HAS_GEMINI = "crewai_productfeature_planner.orchestrator.stages._has_gemini_credentials"

    _TASK_CONFIGS = {
        "publish_to_confluence_task": {
            "description": "Publish {prd_content} as '{page_title}' ({run_id})",
            "expected_output": "Confluence page URL",
        },
        "create_jira_epic_task": {
            "description": "Create epic '{page_title}' summary={executive_summary} ({run_id})",
            "expected_output": "Epic key",
        },
        "create_jira_tickets_task": {
            "description": "Create stories from {functional_requirements} under {epic_key} ({run_id})",
            "expected_output": "Story keys",
        },
    }

    def test_returns_none_without_credentials(self, monkeypatch):
        """Without Atlassian credentials, should return None."""
        monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
        monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        result = build_post_completion_crew(flow)
        assert result is None

    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_returns_none_without_final_prd(self, _mg, _mc):
        """Without a finalized PRD, should return None."""
        flow = PRDFlow()
        flow.state.final_prd = ""  # no PRD
        result = build_post_completion_crew(flow)
        assert result is None

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_returns_crew_with_confluence_credentials(
        self, _mg, _mc, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """With Confluence credentials and a final PRD, should return a Crew."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        result = build_post_completion_crew(flow)
        mock_crew.assert_called_once()
        assert result is not None

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_crew_has_two_agents(
        self, _mg, _mc, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Crew should contain Delivery Manager and Orchestrator agents."""
        dm_agent = MagicMock(name="delivery_manager")
        orch_agent = MagicMock(name="orchestrator")
        mock_dm.return_value = dm_agent
        mock_oa.return_value = orch_agent
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        build_post_completion_crew(flow)
        crew_kwargs = mock_crew.call_args[1]
        assert dm_agent in crew_kwargs["agents"]
        assert orch_agent in crew_kwargs["agents"]

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_crew_has_assess_task_plus_delivery_tasks(
        self, _mg, _mc, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Crew should have at least 2 tasks (assess + confluence)."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        build_post_completion_crew(flow)
        # At minimum: assess + confluence = 2 tasks
        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["tasks"]) >= 2

    @patch(_HAS_JIRA, return_value=True)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_returns_none_when_already_published(self, _mg, _mc, _mj):
        """If confluence_url and jira_output already set, nothing to do."""
        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.confluence_url = "https://test.atlassian.net/wiki/page/123"
        flow.state.jira_output = "PROJ-42"
        result = build_post_completion_crew(flow)
        assert result is None


# ── _print_delivery_status ───────────────────────────────────────────


class TestPrintDeliveryStatus:
    """Tests for _print_delivery_status."""

    def test_prints_with_orchestrator_prefix(self, capsys):
        _print_delivery_status("Hello world")
        captured = capsys.readouterr().out
        assert "[Orchestrator]" in captured
        assert "Hello world" in captured

    def test_prints_newline(self, capsys):
        _print_delivery_status("msg")
        assert capsys.readouterr().out.endswith("\n")


# ── _discover_pending_deliveries ─────────────────────────────────────


_STAGES = "crewai_productfeature_planner.orchestrator.stages"
_GET_DB = "crewai_productfeature_planner.main.get_db"
_ASSEMBLE = "crewai_productfeature_planner.main._assemble_prd_from_doc"
_GET_REC = "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record"
_UPSERT_REC = "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record"


def _mock_db_with_docs(docs):
    """Helper: return a MagicMock get_db whose workingIdeas.find → *docs*."""
    cursor = MagicMock()
    cursor.sort.return_value = docs
    col = MagicMock()
    col.find.return_value = cursor
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    return db


class TestDiscoverPendingDeliveries:
    """Tests for _discover_pending_deliveries."""

    @patch(_ASSEMBLE, return_value="")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_returns_empty_when_no_completed(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([])
        assert _discover_pending_deliveries() == []

    @patch(_ASSEMBLE, return_value="# PRD content")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_returns_item_for_pending_delivery(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Dark mode",
                "executive_summary": [
                    {"content": "ES content", "iteration": 1},
                ],
            },
        ])

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert items[0]["run_id"] == "r1"
        assert items[0]["idea"] == "Dark mode"
        assert items[0]["content"] == "# PRD content"
        assert items[0]["confluence_done"] is False
        assert items[0]["jira_done"] is False
        assert items[0]["finalized_idea"] == "ES content"

    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_skips_already_completed_record(self, mock_db, mock_rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {"run_id": "r1", "status": "completed", "idea": "Done"},
        ])
        mock_rec.return_value = {"status": "completed"}

        assert _discover_pending_deliveries() == []

    @patch(_UPSERT_REC, return_value=True)
    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC)
    @patch(_GET_DB)
    def test_marks_both_done_and_skips(self, mock_db, mock_rec, _asm, mock_upsert):
        """When confluence_url in doc and jira_completed in record → mark complete."""
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "Both done",
                "confluence_url": "https://wiki.test.com/p/1",
            },
        ])
        mock_rec.return_value = {
            "status": "partial",
            "confluence_published": False,
            "jira_completed": True,
        }

        items = _discover_pending_deliveries()
        assert items == []
        mock_upsert.assert_called_once_with(
            "r1",
            confluence_published=True,
            confluence_url="https://wiki.test.com/p/1",
            jira_completed=True,
        )

    @patch(_ASSEMBLE, return_value="")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_skips_empty_content(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {"run_id": "r1", "status": "completed", "idea": "Empty"},
        ])
        assert _discover_pending_deliveries() == []

    @patch(_GET_DB, side_effect=Exception("mongo down"))
    def test_returns_empty_on_db_failure(self, _db):
        assert _discover_pending_deliveries() == []

    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_extracts_functional_requirements(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {
                "run_id": "r1",
                "status": "completed",
                "idea": "With FR",
                "section": {
                    "functional_requirements": [
                        {"content": "FR1: Login", "iteration": 1},
                        {"content": "FR1: Login\nFR2: Settings", "iteration": 2},
                    ],
                },
            },
        ])

        items = _discover_pending_deliveries()
        assert len(items) == 1
        assert "FR2: Settings" in items[0]["func_reqs"]

    @patch(_ASSEMBLE, return_value="# PRD")
    @patch(_GET_REC, return_value=None)
    @patch(_GET_DB)
    def test_skips_docs_without_run_id(self, mock_db, _rec, _asm):
        mock_db.return_value = _mock_db_with_docs([
            {"status": "completed", "idea": "No run id"},
        ])
        assert _discover_pending_deliveries() == []


# ── build_startup_delivery_crew ──────────────────────────────────────


class TestBuildStartupDeliveryCrew:
    """Tests for build_startup_delivery_crew."""

    _DM = "crewai_productfeature_planner.agents.orchestrator.agent.create_delivery_manager_agent"
    _OA = "crewai_productfeature_planner.agents.orchestrator.agent.create_orchestrator_agent"
    _TC = "crewai_productfeature_planner.agents.orchestrator.agent.get_task_configs"
    _VERBOSE = "crewai_productfeature_planner.scripts.logging_config.is_verbose"
    _CREW_CLS = "crewai.Crew"
    _TASK_CLS = "crewai.Task"

    _TASK_CONFIGS = {
        "publish_to_confluence_task": {
            "description": "Publish {prd_content} as '{page_title}' ({run_id})",
            "expected_output": "Confluence page URL",
        },
        "create_jira_epic_task": {
            "description": "Create epic '{page_title}' summary={executive_summary} ({run_id})",
            "expected_output": "Epic key",
        },
        "create_jira_tickets_task": {
            "description": "Create stories from {functional_requirements} under {epic_key} ({run_id})",
            "expected_output": "Story keys",
        },
    }

    def _make_item(self, **overrides):
        base = {
            "run_id": "r1",
            "idea": "Test idea",
            "content": "# PRD content",
            "confluence_done": False,
            "confluence_url": "",
            "jira_done": False,
            "finalized_idea": "ES summary",
            "func_reqs": "FR1: Login",
            "doc": {"run_id": "r1"},
        }
        base.update(overrides)
        return base

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_creates_crew_with_all_tasks(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should create 4 tasks when both Confluence and Jira are pending."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item())

        assert mock_task.call_count == 4  # assess + confluence + epic + stories
        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["agents"]) == 2
        assert len(crew_kwargs["tasks"]) == 4

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_confluence_when_already_done(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should create 3 tasks when Confluence is already published."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(confluence_done=True))

        assert mock_task.call_count == 3  # assess + epic + stories

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_jira_when_already_done(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should create 2 tasks when Jira is done but Confluence pending."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(jira_done=True))

        assert mock_task.call_count == 2  # assess + confluence

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_stories_when_no_func_reqs(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should create 3 tasks when no functional_requirements provided."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(func_reqs=""))

        assert mock_task.call_count == 3  # assess + confluence + epic

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_progress_callback_invoked(
        self, mock_task, mock_crew_cls, mock_dm, mock_oa, _tc, _v,
    ):
        """step_callback should invoke the progress_callback."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        cb = MagicMock()
        build_startup_delivery_crew(self._make_item(), progress_callback=cb)

        # Extract the step_callback passed to Crew
        crew_kwargs = mock_crew_cls.call_args[1]
        step_callback = crew_kwargs["step_callback"]

        # Simulate step_callback invocation
        step_output = MagicMock()
        step_output.raw = "Published page_id=123"
        step_callback(step_output)

        cb.assert_called_once()
        assert "[1/4]" in cb.call_args[0][0]

    @patch(_VERBOSE, return_value=True)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_respects_verbose_setting(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Crew verbose flag should match is_verbose()."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item())

        crew_kwargs = mock_crew.call_args[1]
        assert crew_kwargs["verbose"] is True

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_skips_jira_when_no_finalized_idea(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Should not create Jira tasks when finalized_idea is empty."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(self._make_item(finalized_idea=""))

        assert mock_task.call_count == 2  # assess + confluence only
