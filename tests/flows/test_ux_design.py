"""Tests for the UX Design flow (2-phase: draft + review).

Covers:
- ``run_ux_design_draft()`` — Phase 1: UX Designer + Design Partner
- ``run_ux_design_review()`` — Phase 2: Senior Designer review
- ``run_ux_design_flow()`` — Full 2-phase orchestrator
- ``run_ux_design()`` — Legacy entry point (backward compat)
- ``_write_design_file()`` — Fixed-name file writing (draft/final)
- ``_trigger_ux_design_flow()`` — Post-PRD trigger from finalization
- Agent factory tests (Design Partner, Senior Designer)
"""

from __future__ import annotations

from pathlib import Path
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


# ── Phase 1: run_ux_design_draft ──────────────────────────────


class TestRunUxDesignDraft:

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_returns_draft_content(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Phase 1 should return the raw agent output as draft content."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "# Design System\n\nComplete design spec here."
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_ux, patch(
            "crewai_productfeature_planner.agents.ux_designer.create_design_partner",
        ) as mock_dp, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._write_design_file",
        ) as mock_write:
            mock_ux.return_value = MagicMock()
            mock_dp.return_value = MagicMock()
            result = run_ux_design_draft(flow)

        assert "Design System" in result
        assert flow.state.figma_design_status == "prompt_ready"

        # Draft file should be written with fixed name.
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][1] == "ux_design_draft.md"

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_captures_figma_url(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """When agent returns FIGMA_URL, it should be captured."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "FIGMA_URL:https://figma.com/design/abc123\nDesign spec."
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_ux, patch(
            "crewai_productfeature_planner.agents.ux_designer.create_design_partner",
        ) as mock_dp, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._write_design_file",
        ):
            mock_ux.return_value = MagicMock()
            mock_dp.return_value = MagicMock()
            result = run_ux_design_draft(flow)

        assert "FIGMA_URL" in result
        assert flow.state.figma_design_url == "https://figma.com/design/abc123"
        assert flow.state.figma_design_status == "completed"

    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_skips_when_no_eps(self, mock_proj, mock_save):
        """Should return empty string when no executive product summary."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow(executive_product_summary="")
        _mock_notify(flow)

        result = run_ux_design_draft(flow)
        assert result == ""

    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_skips_when_no_credentials(self, mock_proj, mock_save):
        """Should skip when UX Designer creation raises EnvironmentError."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow()
        notifier = _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
            side_effect=EnvironmentError("Missing GOOGLE_API_KEY"),
        ), patch(
            f"{_UX_MOD}._persist_figma_design",
        ):
            result = run_ux_design_draft(flow)

        assert result == ""
        notifier.assert_any_call("ux_design_skipped", {"reason": "no_credentials"})

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_continues_without_design_partner(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """If Design Partner creation fails, should proceed with UX Designer only."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Design without partner"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_ux, patch(
            "crewai_productfeature_planner.agents.ux_designer.create_design_partner",
            side_effect=Exception("Partner init failed"),
        ), patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._write_design_file",
        ):
            mock_ux.return_value = MagicMock()
            result = run_ux_design_draft(flow)

        assert result == "Design without partner"

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_sends_progress_notifications(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Progress events should fire for start and draft_complete."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow()
        notifier = _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Design output"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_ux, patch(
            "crewai_productfeature_planner.agents.ux_designer.create_design_partner",
        ) as mock_dp, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._write_design_file",
        ):
            mock_ux.return_value = MagicMock()
            mock_dp.return_value = MagicMock()
            run_ux_design_draft(flow)

        notifier.assert_any_call("ux_design_start", {
            "eps_length": len("The 10-star product vision"),
        })
        notifier.assert_any_call("ux_design_draft_complete", {
            "figma_url": "",
            "has_prompt": True,
            "status": "prompt_ready",
            "prompt_preview": "Design output"[:500],
        })

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_persists_to_mongodb(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Draft should be persisted to MongoDB iterations."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_draft

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Full design specification"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_ux_designer",
        ) as mock_ux, patch(
            "crewai_productfeature_planner.agents.ux_designer.create_design_partner",
        ) as mock_dp, patch(
            f"{_UX_MOD}._persist_figma_design",
        ), patch(
            f"{_UX_MOD}._write_design_file",
        ):
            mock_ux.return_value = MagicMock()
            mock_dp.return_value = MagicMock()
            run_ux_design_draft(flow)

        mock_save.assert_called_once()
        assert mock_save.call_args.kwargs["step"] == "ux_design_draft"
        assert mock_save.call_args.kwargs["section_key"] == "ux_design"


# ── Phase 2: run_ux_design_review ─────────────────────────────


class TestRunUxDesignReview:

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_returns_final_content(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Phase 2 should return the Senior Designer's final output."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_review

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "# Final Design\n\nReviewed and finalized."
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_senior_designer",
        ) as mock_sd, patch(
            f"{_UX_MOD}._write_design_file",
        ) as mock_write:
            mock_sd.return_value = MagicMock()
            result = run_ux_design_review(flow, "Initial draft content")

        assert "Final Design" in result

        # Final file should be written.
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][1] == "ux_design_final.md"

    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_skips_when_no_draft(self, mock_proj):
        """Should return empty string when no initial draft provided."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_review

        flow = _make_flow()
        _mock_notify(flow)

        result = run_ux_design_review(flow, "")
        assert result == ""

    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_returns_draft_on_credential_failure(self, mock_proj):
        """Should return the original draft if Senior Designer cannot be created."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_review

        flow = _make_flow()
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_senior_designer",
            side_effect=EnvironmentError("No creds"),
        ):
            result = run_ux_design_review(flow, "Original draft")

        assert result == "Original draft"

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_persists_final_to_mongodb(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Final design should be persisted as iteration 2."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_review

        flow = _make_flow()
        _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Final reviewed design"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_senior_designer",
        ) as mock_sd, patch(
            f"{_UX_MOD}._write_design_file",
        ):
            mock_sd.return_value = MagicMock()
            run_ux_design_review(flow, "Draft content")

        mock_save.assert_called_once()
        assert mock_save.call_args.kwargs["step"] == "ux_design_review"
        assert mock_save.call_args.kwargs["iteration"] == 2

    @patch(f"{_UX_MOD}.Crew")
    @patch(f"{_UX_MOD}.Task")
    @patch(f"{_UX_MOD}.save_iteration")
    @patch(f"{_UX_MOD}.crew_kickoff_with_retry")
    @patch(f"{_UX_MOD}.resolve_project_id", return_value="proj-ux")
    def test_sends_review_progress(
        self, mock_proj, mock_kickoff, mock_save, mock_task, mock_crew,
    ):
        """Should fire review_start and ux_design_complete progress events."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_review

        flow = _make_flow()
        notifier = _mock_notify(flow)

        mock_result = MagicMock()
        mock_result.raw = "Reviewed output"
        mock_kickoff.return_value = mock_result

        with patch(
            "crewai_productfeature_planner.agents.ux_designer.create_senior_designer",
        ) as mock_sd, patch(
            f"{_UX_MOD}._write_design_file",
        ):
            mock_sd.return_value = MagicMock()
            run_ux_design_review(flow, "Draft content")

        notifier.assert_any_call("ux_design_review_start", {
            "draft_length": len("Draft content"),
        })
        notifier.assert_any_call("ux_design_complete", {
            "figma_url": "",
            "has_prompt": True,
            "status": flow.state.figma_design_status,
            "prompt_preview": "Reviewed output"[:500],
        })


# ── Full flow: run_ux_design_flow ─────────────────────────────


class TestRunUxDesignFlow:

    @patch(f"{_UX_MOD}.run_ux_design_review")
    @patch(f"{_UX_MOD}.run_ux_design_draft")
    def test_runs_both_phases(self, mock_draft, mock_review):
        """Full flow should run Phase 1 then Phase 2."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_flow

        flow = _make_flow()
        mock_draft.return_value = "Draft content"
        mock_review.return_value = "Final content"

        run_ux_design_flow(flow)

        mock_draft.assert_called_once_with(flow)
        mock_review.assert_called_once_with(flow, "Draft content")

    @patch(f"{_UX_MOD}.run_ux_design_review")
    @patch(f"{_UX_MOD}.run_ux_design_draft")
    def test_stops_when_draft_empty(self, mock_draft, mock_review):
        """Should not run Phase 2 if Phase 1 returned empty."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design_flow

        flow = _make_flow()
        mock_draft.return_value = ""

        result = run_ux_design_flow(flow)

        assert result == ""
        mock_review.assert_not_called()


# ── Legacy entry point: run_ux_design ─────────────────────────


class TestRunUxDesignLegacy:

    @patch(f"{_UX_MOD}.run_ux_design_flow")
    def test_delegates_to_full_flow(self, mock_flow):
        """Legacy run_ux_design should delegate to run_ux_design_flow."""
        from crewai_productfeature_planner.flows._ux_design import run_ux_design

        flow = _make_flow()
        mock_flow.return_value = "https://figma.com/design/xyz"

        result = run_ux_design(flow)

        assert result == "https://figma.com/design/xyz"
        mock_flow.assert_called_once_with(flow)


# ── File writing: _write_design_file ──────────────────────────


class TestWriteDesignFile:

    def test_writes_file_with_fixed_name(self, tmp_path):
        """Should write to the exact filename, overwriting existing."""
        from crewai_productfeature_planner.flows._ux_design import _write_design_file

        output_dir = str(tmp_path / "ux_output")
        path1 = _write_design_file(output_dir, "ux_design_draft.md", "First draft")
        assert Path(path1).is_file()
        assert "First draft" in Path(path1).read_text()

        # Overwrite with new content.
        path2 = _write_design_file(output_dir, "ux_design_draft.md", "Second draft")
        assert path1 == path2
        content = Path(path2).read_text()
        assert "Second draft" in content
        assert "First draft" not in content

    def test_includes_figma_url(self, tmp_path):
        """Should include Figma URL link when provided."""
        from crewai_productfeature_planner.flows._ux_design import _write_design_file

        output_dir = str(tmp_path / "ux_output")
        path = _write_design_file(
            output_dir, "ux_design_final.md", "Content",
            figma_url="https://figma.com/design/abc",
        )
        content = Path(path).read_text()
        assert "https://figma.com/design/abc" in content
        assert "Figma Prototype" in content

    def test_creates_directory(self, tmp_path):
        """Should create output directory if it doesn't exist."""
        from crewai_productfeature_planner.flows._ux_design import _write_design_file

        deep_dir = str(tmp_path / "a" / "b" / "c")
        path = _write_design_file(deep_dir, "test.md", "Content")
        assert Path(path).is_file()


# ── Finalization trigger: _trigger_ux_design_flow ─────────────


class TestTriggerUxDesignFlow:

    def test_triggers_when_prd_complete(self):
        """Should trigger UX flow when EPS available and no prior design."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )

        flow = _make_flow()
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
        ) as mock_kick:
            _trigger_ux_design_flow(flow)
            mock_kick.assert_called_once_with(flow)

    def test_skips_when_no_eps(self):
        """Should skip when no executive product summary."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )

        flow = _make_flow(executive_product_summary="")
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
        ) as mock_kick:
            _trigger_ux_design_flow(flow)
            mock_kick.assert_not_called()

    def test_skips_when_already_prompt_ready(self):
        """Should skip when UX design already has prompt_ready status."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )

        flow = _make_flow(figma_design_status="prompt_ready")
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
        ) as mock_kick:
            _trigger_ux_design_flow(flow)
            mock_kick.assert_not_called()

    def test_skips_when_already_completed(self):
        """Should skip when UX design already completed with URL."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )

        flow = _make_flow(figma_design_status="completed")
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
        ) as mock_kick:
            _trigger_ux_design_flow(flow)
            mock_kick.assert_not_called()

    def test_catches_non_fatal_errors(self):
        """UX flow failure should not propagate (PRD is still saved)."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )

        flow = _make_flow()
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
            side_effect=RuntimeError("Agent crashed"),
        ):
            # Should not raise
            _trigger_ux_design_flow(flow)

    def test_propagates_billing_error(self):
        """BillingError should propagate for proper pause handling."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )
        from crewai_productfeature_planner.scripts.retry import BillingError

        flow = _make_flow()
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
            side_effect=BillingError("Billing limit"),
        ):
            with pytest.raises(BillingError):
                _trigger_ux_design_flow(flow)

    def test_propagates_model_busy_error(self):
        """ModelBusyError should propagate for proper pause handling."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )
        from crewai_productfeature_planner.scripts.retry import ModelBusyError

        flow = _make_flow()
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
            side_effect=ModelBusyError("Model overloaded"),
        ):
            with pytest.raises(ModelBusyError):
                _trigger_ux_design_flow(flow)

    def test_propagates_shutdown_error(self):
        """ShutdownError should propagate for proper shutdown handling."""
        from crewai_productfeature_planner.flows._finalization import (
            _trigger_ux_design_flow,
        )
        from crewai_productfeature_planner.scripts.retry import ShutdownError

        flow = _make_flow()
        _mock_notify(flow)

        with patch(
            "crewai_productfeature_planner.flows.ux_design_flow.kick_off_ux_design_flow",
            side_effect=ShutdownError("Shutting down"),
        ):
            with pytest.raises(ShutdownError):
                _trigger_ux_design_flow(flow)


# ── Agent factories ───────────────────────────────────────────


class TestDesignPartnerAgent:

    def test_create_requires_gemini_creds(self, monkeypatch):
        """Should raise when no Gemini credentials available."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        from crewai_productfeature_planner.agents.ux_designer.agent import (
            create_design_partner,
        )
        with pytest.raises(EnvironmentError):
            create_design_partner()

    def test_loads_config(self, monkeypatch):
        """Should load design_partner.yaml config."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        from crewai_productfeature_planner.agents.ux_designer.agent import (
            create_design_partner,
        )
        agent = create_design_partner()
        assert "Design Partner" in agent.role


class TestSeniorDesignerAgent:

    def test_create_requires_gemini_creds(self, monkeypatch):
        """Should raise when no Gemini credentials available."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        from crewai_productfeature_planner.agents.ux_designer.agent import (
            create_senior_designer,
        )
        with pytest.raises(EnvironmentError):
            create_senior_designer()

    def test_loads_config(self, monkeypatch):
        """Should load senior_designer.yaml config."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        from crewai_productfeature_planner.agents.ux_designer.agent import (
            create_senior_designer,
        )
        agent = create_senior_designer()
        assert "Senior Designer" in agent.role


class TestUxDesignFlowTaskConfigs:

    def test_loads_flow_task_configs(self):
        """Should load the ux_design_flow_tasks.yaml file."""
        from crewai_productfeature_planner.agents.ux_designer.agent import (
            get_ux_design_flow_task_configs,
        )
        configs = get_ux_design_flow_task_configs()
        assert "create_initial_design_draft_task" in configs
        assert "review_and_finalize_design_task" in configs


# ── Original UX Designer agent factory (backward compat) ─────


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


# ── Output filenames ──────────────────────────────────────────


class TestOutputFilenames:

    def test_draft_filename_is_fixed(self):
        """Draft filename should be a constant, not timestamped."""
        from crewai_productfeature_planner.flows._ux_design import DRAFT_FILENAME
        assert DRAFT_FILENAME == "ux_design_draft.md"
        assert "{" not in DRAFT_FILENAME  # No dynamic parts

    def test_final_filename_is_fixed(self):
        """Final filename should be a constant, not timestamped."""
        from crewai_productfeature_planner.flows._ux_design import FINAL_FILENAME
        assert FINAL_FILENAME == "ux_design_final.md"
        assert "{" not in FINAL_FILENAME


class TestResolveOutputDir:

    def test_project_dir(self):
        """Should return project-specific path when project_id given."""
        from crewai_productfeature_planner.flows._ux_design import _resolve_output_dir
        assert _resolve_output_dir("proj-abc") == "output/proj-abc/ux design"

    def test_fallback_dir(self):
        """Should return default path when no project_id."""
        from crewai_productfeature_planner.flows._ux_design import _resolve_output_dir
        assert _resolve_output_dir(None) == "output/prds"
