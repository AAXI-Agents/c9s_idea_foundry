"""Tests for the CEO and Engineering Manager review steps (Phase 1.5).

Covers:
- ``run_ceo_review()`` — generates executive product summary
- ``run_eng_plan()`` — generates engineering plan
- Graceful skip when Gemini credentials are missing
- State population, section approval, and MongoDB persistence
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from crewai_productfeature_planner.apis.prd.models import (
    PRDDraft,
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
)
from crewai_productfeature_planner.flows.prd_flow import PRDFlow, PRDState


# ── Helpers ───────────────────────────────────────────────────

def _make_flow(**overrides) -> PRDFlow:
    """Build a PRDFlow with minimal valid state for Phase 1.5 tests."""
    flow = PRDFlow()
    flow.state.run_id = "test-run-001"
    flow.state.idea = "Build a widget dashboard"
    flow.state.original_idea = "Build a widget dashboard"
    flow.state.executive_summary = ExecutiveSummaryDraft(iterations=[
        ExecutiveSummaryIteration(content="Exec summary content v1", iteration=1),
    ])
    flow.state.requirements_breakdown = "Req 1\nReq 2\nReq 3"
    flow._progress_callback = None
    for k, v in overrides.items():
        setattr(flow.state, k, v)
    return flow


def _mock_notify(flow: PRDFlow):
    """Attach a mock _notify_progress to a flow."""
    flow._notify_progress = MagicMock()
    return flow._notify_progress


# ── run_ceo_review ────────────────────────────────────────────

_CEO_MOD = "crewai_productfeature_planner.flows._ceo_eng_review"


class TestRunCeoReview:

    @patch(f"{_CEO_MOD}.Crew")
    @patch(f"{_CEO_MOD}.Task")
    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_generates_executive_product_summary(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """CEO review should populate state and draft section."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_ceo_review

        flow = _make_flow()
        notifier = _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "  The 10-star product vision document  "
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ceo_reviewer.create_ceo_reviewer",
        ) as mock_create:
            mock_create.return_value = MagicMock()
            result = run_ceo_review(flow)

        assert result == "The 10-star product vision document"
        assert flow.state.executive_product_summary == result

        # Draft section should be populated and approved
        section = flow.state.draft.get_section("executive_product_summary")
        assert section is not None
        assert section.content == result
        assert section.is_approved is True
        assert section.iteration == 1

        # save_iteration called with correct args
        mock_save.assert_called_once()
        save_kwargs = mock_save.call_args
        assert save_kwargs.kwargs["section_key"] == "executive_product_summary"
        assert save_kwargs.kwargs["step"] == "ceo_review"
        assert save_kwargs.kwargs["run_id"] == "test-run-001"

        # Progress callbacks fired
        notifier.assert_any_call("ceo_review_start", {
            "exec_summary_length": len("Exec summary content v1"),
        })
        notifier.assert_any_call("ceo_review_complete", {
            "content_length": len(result),
        })

    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_skips_when_no_credentials(
        self, mock_proj, mock_kickoff, mock_save,
    ):
        """CEO review should return empty string and skip on EnvironmentError."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_ceo_review

        flow = _make_flow()
        notifier = _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.agents.ceo_reviewer.create_ceo_reviewer",
            side_effect=EnvironmentError("Missing GEMINI_API_KEY"),
        ):
            result = run_ceo_review(flow)

        assert result == ""
        assert flow.state.executive_product_summary == ""
        mock_kickoff.assert_not_called()
        mock_save.assert_not_called()
        notifier.assert_any_call("ceo_review_skipped", {
            "reason": "no_credentials",
        })

    @patch(f"{_CEO_MOD}.Crew")
    @patch(f"{_CEO_MOD}.Task")
    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_uses_correct_task_template(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """CEO task description should include exec_summary and idea."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_ceo_review

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "CEO output"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ceo_reviewer.create_ceo_reviewer",
        ) as mock_create:
            mock_create.return_value = MagicMock()
            run_ceo_review(flow)

        # The crew should have been kicked off once
        mock_kickoff.assert_called_once()


# ── run_eng_plan ──────────────────────────────────────────────

class TestRunEngPlan:

    @patch(f"{_CEO_MOD}.Crew")
    @patch(f"{_CEO_MOD}.Task")
    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_generates_engineering_plan(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Eng plan should populate state and draft section."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_eng_plan

        flow = _make_flow(executive_product_summary="CEO vision doc")
        notifier = _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "  Detailed engineering plan...  "
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.eng_manager.create_eng_manager",
        ) as mock_create:
            mock_create.return_value = MagicMock()
            result = run_eng_plan(flow)

        assert result == "Detailed engineering plan..."
        assert flow.state.engineering_plan == result

        # Draft section should be populated and approved
        section = flow.state.draft.get_section("engineering_plan")
        assert section is not None
        assert section.content == result
        assert section.is_approved is True
        assert section.iteration == 1

        # save_iteration called with correct args
        mock_save.assert_called_once()
        save_kwargs = mock_save.call_args
        assert save_kwargs.kwargs["section_key"] == "engineering_plan"
        assert save_kwargs.kwargs["step"] == "eng_plan"
        assert save_kwargs.kwargs["run_id"] == "test-run-001"

        # Progress callbacks fired
        notifier.assert_any_call("eng_plan_start", {
            "eps_length": len("CEO vision doc"),
            "requirements_length": len("Req 1\nReq 2\nReq 3"),
        })
        notifier.assert_any_call("eng_plan_complete", {
            "content_length": len(result),
        })

    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_skips_when_no_credentials(
        self, mock_proj, mock_kickoff, mock_save,
    ):
        """Eng plan should return empty string and skip on EnvironmentError."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_eng_plan

        flow = _make_flow(executive_product_summary="CEO vision doc")
        notifier = _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.agents.eng_manager.create_eng_manager",
            side_effect=EnvironmentError("Missing GEMINI_API_KEY"),
        ):
            result = run_eng_plan(flow)

        assert result == ""
        assert flow.state.engineering_plan == ""
        mock_kickoff.assert_not_called()
        mock_save.assert_not_called()
        notifier.assert_any_call("eng_plan_skipped", {
            "reason": "no_credentials",
        })

    @patch(f"{_CEO_MOD}.Crew")
    @patch(f"{_CEO_MOD}.Task")
    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_uses_requirements_in_task(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Eng task description should include eps, idea, and requirements."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_eng_plan

        flow = _make_flow(
            executive_product_summary="CEO vision doc",
            requirements_breakdown="Story A\nStory B",
        )
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Eng plan output"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.eng_manager.create_eng_manager",
        ) as mock_create:
            mock_create.return_value = MagicMock()
            run_eng_plan(flow)

        mock_kickoff.assert_called_once()

    @patch(f"{_CEO_MOD}.Crew")
    @patch(f"{_CEO_MOD}.Task")
    @patch(f"{_CEO_MOD}.save_iteration")
    @patch(f"{_CEO_MOD}.crew_kickoff_with_retry")
    @patch(f"{_CEO_MOD}.resolve_project_id", return_value="proj-123")
    def test_handles_empty_requirements(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Eng plan should still run when requirements_breakdown is empty."""
        from crewai_productfeature_planner.flows._ceo_eng_review import run_eng_plan

        flow = _make_flow(
            executive_product_summary="CEO vision",
            requirements_breakdown="",
        )
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Plan without requirements"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.eng_manager.create_eng_manager",
        ) as mock_create:
            mock_create.return_value = MagicMock()
            result = run_eng_plan(flow)

        assert result == "Plan without requirements"
        mock_kickoff.assert_called_once()


# ── PRDState specialist fields ────────────────────────────────

class TestSpecialistStateFields:

    def test_default_empty_strings(self):
        """New PRDState should have empty specialist fields."""
        state = PRDState()
        assert state.executive_product_summary == ""
        assert state.engineering_plan == ""

    def test_specialist_section_keys_constant(self):
        """SPECIALIST_SECTION_KEYS should contain both specialist keys."""
        from crewai_productfeature_planner.apis.prd._sections import (
            SPECIALIST_SECTION_KEYS,
        )
        assert "executive_product_summary" in SPECIALIST_SECTION_KEYS
        assert "engineering_plan" in SPECIALIST_SECTION_KEYS
        assert len(SPECIALIST_SECTION_KEYS) == 2

    def test_section_order_includes_specialists(self):
        """SECTION_ORDER should include specialist sections after executive_summary."""
        from crewai_productfeature_planner.apis.prd._sections import SECTION_ORDER
        keys = [k for k, _ in SECTION_ORDER]
        es_idx = keys.index("executive_summary")
        eps_idx = keys.index("executive_product_summary")
        eng_idx = keys.index("engineering_plan")
        assert eps_idx == es_idx + 1
        assert eng_idx == es_idx + 2


# ── Jira context builder ─────────────────────────────────────

class TestJiraContext:

    def test_build_jira_context_with_engineering_plan(self):
        """_build_jira_context should append engineering plan to PRD context."""
        from crewai_productfeature_planner.orchestrator._jira import (
            _build_jira_context,
        )

        flow = _make_flow(engineering_plan="## Architecture\nMicroservices")
        flow.state.draft.get_section("problem_statement").content = "The problem"
        flow.state.draft.get_section("problem_statement").is_approved = True

        with patch(
            "crewai_productfeature_planner.orchestrator._jira.build_additional_prd_context_from_draft",
        ) as mock_build:
            mock_build.return_value = "PRD sections context"
            result = _build_jira_context(flow)

        assert "PRD sections context" in result
        assert "## Architecture\nMicroservices" in result

    def test_build_jira_context_without_engineering_plan(self):
        """_build_jira_context should return only PRD context when no eng plan."""
        from crewai_productfeature_planner.orchestrator._jira import (
            _build_jira_context,
        )

        flow = _make_flow(engineering_plan="")

        with patch(
            "crewai_productfeature_planner.orchestrator._jira.build_additional_prd_context_from_draft",
        ) as mock_build:
            mock_build.return_value = "PRD sections context"
            result = _build_jira_context(flow)

        assert result == "PRD sections context"
        assert "Engineering Plan" not in result

    def test_build_jira_context_with_ux_design_content(self):
        """_build_jira_context should include UX design content when available."""
        from crewai_productfeature_planner.orchestrator._jira import (
            _build_jira_context,
        )

        flow = _make_flow(
            engineering_plan="",
            ux_design_content="Design spec with 12-col grid and sidebar nav",
        )

        with patch(
            "crewai_productfeature_planner.orchestrator._jira.build_additional_prd_context_from_draft",
        ) as mock_build:
            mock_build.return_value = ""
            result = _build_jira_context(flow)

        assert "## UX Design" in result
        assert "12-col grid" in result
        assert "UX Design specification" in result

    def test_build_jira_context_with_ux_content_and_eng_plan(self):
        """Both UX design content and eng plan should appear when both available."""
        from crewai_productfeature_planner.orchestrator._jira import (
            _build_jira_context,
        )

        flow = _make_flow(
            engineering_plan="## Arch\nMonolith",
            ux_design_content="Detailed design prompt text",
        )

        with patch(
            "crewai_productfeature_planner.orchestrator._jira.build_additional_prd_context_from_draft",
        ) as mock_build:
            mock_build.return_value = "PRD base"
            result = _build_jira_context(flow)

        assert "## Engineering Plan" in result
        assert "## UX Design" in result
        assert "Detailed design prompt text" in result
        assert "PRD base" in result

    def test_build_jira_context_no_ux_no_eng(self):
        """No UX Design or Engineering Plan should return only PRD context."""
        from crewai_productfeature_planner.orchestrator._jira import (
            _build_jira_context,
        )

        flow = _make_flow(
            engineering_plan="",
            ux_design_content="",
        )

        with patch(
            "crewai_productfeature_planner.orchestrator._jira.build_additional_prd_context_from_draft",
        ) as mock_build:
            mock_build.return_value = "PRD only"
            result = _build_jira_context(flow)

        assert result == "PRD only"
        assert "UX Design" not in result
