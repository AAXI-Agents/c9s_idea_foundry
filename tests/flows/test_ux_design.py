"""Tests for the UX Design flow step (Phase 1.5c).

Covers:
- ``run_ux_design()`` — full flow with Figma URL return
- Prompt-only fallback (no Figma credentials)
- Skip on missing executive product summary
- Skip on missing Gemini credentials
- Error/skipped agent output parsing
- Raw output fallback when no pattern matches
- MongoDB persistence calls
- Progress notifications
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
)
from crewai_productfeature_planner.flows.prd_flow import PRDFlow


# ── Helpers ───────────────────────────────────────────────────

def _make_flow(**overrides) -> PRDFlow:
    """Build a PRDFlow with minimal valid state for UX Design tests."""
    flow = PRDFlow()
    flow.state.run_id = "test-ux-001"
    flow.state.idea = "Build an AI chat dashboard"
    flow.state.original_idea = "Build an AI chat dashboard"
    flow.state.executive_summary = ExecutiveSummaryDraft(iterations=[
        ExecutiveSummaryIteration(content="Exec summary v1", iteration=1),
    ])
    flow.state.requirements_breakdown = "Req A\nReq B"
    flow.state.executive_product_summary = "The 10-star product vision"
    flow._progress_callback = None
    for k, v in overrides.items():
        setattr(flow.state, k, v)
    return flow


def _mock_notify(flow: PRDFlow):
    """Attach a mock _notify_progress to a flow."""
    flow._notify_progress = MagicMock()
    return flow._notify_progress


_UX_MOD = "crewai_productfeature_planner.flows._ux_design"


# ── run_ux_design ─────────────────────────────────────────────


class TestRunUxDesign:

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_returns_figma_url_on_success(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Agent returning FIGMA_URL: should populate state and return URL."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        notifier = _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_URL:https://www.figma.com/design/abc123"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ) as mock_persist:
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        assert result == "https://www.figma.com/design/abc123"
        assert flow.state.figma_design_url == result
        assert flow.state.figma_design_status == "completed"

        # Verify MongoDB persistence
        mock_persist.assert_any_call(flow.state.run_id, status="generating")
        mock_persist.assert_any_call(flow.state.run_id, status="prompting")
        mock_persist.assert_any_call(
            flow.state.run_id, url=result, status="completed",
        )

        # Progress notifications
        notifier.assert_any_call("ux_design_start", {
            "eps_length": len("The 10-star product vision"),
        })
        notifier.assert_any_call("ux_design_complete", {
            "figma_url": result,
            "has_prompt": True,
            "status": "completed",
            "prompt_preview": "FIGMA_URL:https://www.figma.com/design/abc123"[:500],
        })

        # save_iteration called
        mock_save.assert_called_once()
        assert mock_save.call_args.kwargs["section_key"] == "ux_design"
        assert mock_save.call_args.kwargs["step"] == "ux_design"

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_returns_prompt_when_no_figma_creds(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Agent returning FIGMA_PROMPT: should store prompt and set prompt_ready."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = (
            "FIGMA_PROMPT: Design a dark mode dashboard with sidebar "
            "navigation and 12-column grid layout."
        )
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ) as mock_persist:
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        assert result == ""  # No URL returned
        assert "dashboard" in flow.state.figma_design_prompt
        assert flow.state.figma_design_status == "prompt_ready"
        mock_persist.assert_any_call(flow.state.run_id, status="prompt_ready")

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_handles_error_output(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Agent returning FIGMA_ERROR with short content should skip."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_ERROR: HTTP 500 from Figma API"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        assert result == ""
        assert flow.state.figma_design_status == "skipped"

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_error_with_long_content_recovers_prompt(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Agent returning FIGMA_ERROR alongside >100 chars of design content
        should recover the content as prompt_ready."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        design_content = "Design a dark-themed dashboard with sidebar nav. " * 5
        mock_result = MagicMock()
        mock_result.raw = (
            f"FIGMA_ERROR: HTTP 404 not found\n\n{design_content}"
        )
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        assert result == ""
        assert flow.state.figma_design_status == "prompt_ready"
        assert "dashboard" in flow.state.figma_design_prompt

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_handles_skipped_output(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Agent returning FIGMA_SKIPPED: should set status to skipped."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_SKIPPED: No credentials configured"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        assert result == ""
        assert flow.state.figma_design_status == "skipped"

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_raw_output_fallback(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Unrecognised output should be stored as prompt for manual use."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Here is my design spec with pages and components..."
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        assert result == ""
        assert flow.state.figma_design_prompt == mock_result.raw.strip()
        assert flow.state.figma_design_status == "prompt_ready"

    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_skips_when_no_exec_summary(
        self, mock_proj, mock_kickoff, mock_save,
    ):
        """Should return empty string when no executive product summary."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow(executive_product_summary="")
        _mock_notify(flow)

        result = run_ux_design(flow)

        assert result == ""
        mock_kickoff.assert_not_called()

    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_skips_when_no_gemini_credentials(
        self, mock_proj, mock_kickoff, mock_save,
    ):
        """Should skip gracefully when agent creation raises EnvironmentError."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        notifier = _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
            side_effect=EnvironmentError("Missing GOOGLE_API_KEY"),
        ), patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            result = run_ux_design(flow)

        assert result == ""
        assert flow.state.figma_design_status == ""
        mock_kickoff.assert_not_called()
        notifier.assert_any_call("ux_design_skipped", {
            "reason": "no_credentials",
        })

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_url_takes_priority_over_prompt(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """When output has both URL and PROMPT, URL should win."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = (
            "FIGMA_URL:https://figma.com/design/f1\n"
            "FIGMA_PROMPT: detailed prompt here"
        )
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            mock_create.return_value = MagicMock()
            result = run_ux_design(flow)

        # URL branch should take effect
        assert result == "https://figma.com/design/f1"
        assert flow.state.figma_design_url == result
        assert flow.state.figma_design_status == "completed"


class TestUxDesignFileOnlyOnSuccess:
    """UX design markdown file should only be saved when Figma URL is available."""

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_file_saved_when_figma_url_present(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """_save_ux_design_file should be called when Figma URL is available."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_URL:https://www.figma.com/design/abc123"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._save_ux_design_file",
        ) as mock_save_file:
            mock_create.return_value = MagicMock()
            run_ux_design(flow)

        mock_save_file.assert_called_once()
        call_kwargs = mock_save_file.call_args
        assert call_kwargs[0][2] == "https://www.figma.com/design/abc123"  # figma_url arg

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_file_not_saved_when_prompt_only(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """_save_ux_design_file should NOT be called for prompt-only (no Figma URL)."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_PROMPT: Design a dashboard with sidebar"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._save_ux_design_file",
        ) as mock_save_file:
            mock_create.return_value = MagicMock()
            run_ux_design(flow)

        mock_save_file.assert_not_called()

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_file_not_saved_when_error_skipped(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """_save_ux_design_file should NOT be called when status is skipped."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_SKIPPED: No credentials"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._save_ux_design_file",
        ) as mock_save_file:
            mock_create.return_value = MagicMock()
            run_ux_design(flow)

        mock_save_file.assert_not_called()

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_file_uses_project_dir_when_available(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """_save_ux_design_file should receive the project_id for project-based paths."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_URL:https://www.figma.com/design/abc123"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_create, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._save_ux_design_file",
        ) as mock_save_file:
            mock_create.return_value = MagicMock()
            run_ux_design(flow)

        # Fourth arg is project_id
        assert mock_save_file.call_args[0][3] == "proj-ux"


# ── UX Designer agent factory (basic tests) ──────────────────


class TestUxDesignerAgent:

    def test_create_requires_google_api_key(self, monkeypatch):
        """Should raise EnvironmentError without Gemini credentials."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        from crewai_productfeature_planner.agents.ux_designer.agent import (
            create_ux_designer,
        )

        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            create_ux_designer()

    def test_get_task_configs_loads_yaml(self):
        """Task configs should include the Figma Make prompt task."""
        from crewai_productfeature_planner.agents.ux_designer.agent import (
            get_task_configs,
        )

        configs = get_task_configs()
        assert "generate_figma_make_prompt_task" in configs
        task = configs["generate_figma_make_prompt_task"]
        assert "description" in task
        assert "expected_output" in task
        assert "{executive_product_summary}" in task["description"]
