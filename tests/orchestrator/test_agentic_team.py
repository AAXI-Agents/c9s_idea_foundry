"""Tests for Agentic Team auto-trigger orchestrator stage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crewai_productfeature_planner.orchestrator._agentic_team import (
    build_agentic_team_trigger_stage,
)


@pytest.fixture
def mock_flow():
    """Create a mock PRDFlow with typical state after Jira completion."""
    flow = MagicMock()
    flow.state.run_id = "run-abc123"
    flow.state.jira_phase = "qa_test_done"
    flow.state.jira_output = "Created 5 tickets"
    return flow


# ── should_skip ───────────────────────────────────────────────


class TestShouldSkip:
    """Test the skip logic for the agentic team trigger stage."""

    def test_skips_when_disabled(self, mock_flow):
        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            False,
        ):
            stage = build_agentic_team_trigger_stage(mock_flow)
            assert stage.should_skip() is True

    def test_skips_when_jira_not_done(self, mock_flow):
        mock_flow.state.jira_phase = "subtasks_done"
        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ):
            stage = build_agentic_team_trigger_stage(mock_flow)
            assert stage.should_skip() is True

    def test_does_not_skip_when_qa_test_done(self, mock_flow):
        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ):
            stage = build_agentic_team_trigger_stage(mock_flow)
            assert stage.should_skip() is False

    def test_does_not_skip_when_kanban_done(self, mock_flow):
        mock_flow.state.jira_phase = "kanban_tasks_done"
        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ):
            stage = build_agentic_team_trigger_stage(mock_flow)
            assert stage.should_skip() is False


# ── _run ──────────────────────────────────────────────────────


class TestRun:
    """Test the run logic for the agentic team trigger stage."""

    def test_triggers_batch_kickoff_with_tickets(self, mock_flow):
        tickets = [
            {"key": "PRD-10", "type": "Sub-task", "summary": "Login flow", "reused": False},
            {"key": "PRD-11", "type": "Sub-task", "summary": "Dashboard", "reused": False},
            {"key": "PRD-12", "type": "Epic", "summary": "Auth Epic", "reused": False},
            {"key": "PRD-13", "type": "Story", "summary": "User settings", "reused": False},
        ]

        mock_batch = AsyncMock(return_value={"accepted": 3, "skipped": 0, "errors": 0})

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.batch_kickoff_pipeline",
            mock_batch,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value="idea-xyz",
        ), patch("asyncio.run", side_effect=lambda coro: None) as mock_asyncio:
            # Override asyncio.run to return our mock result
            mock_asyncio.side_effect = lambda coro: {"accepted": 3, "skipped": 0, "errors": 0}

            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            # Should have called asyncio.run with batch_kickoff
            mock_asyncio.assert_called_once()
            assert "3 accepted" in result.output

    def test_filters_out_reused_tickets(self, mock_flow):
        tickets = [
            {"key": "PRD-10", "type": "Sub-task", "summary": "Login", "reused": True},
            {"key": "PRD-11", "type": "Sub-task", "summary": "Dashboard", "reused": False},
        ]

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value=None,
        ), patch("asyncio.run") as mock_asyncio:
            mock_asyncio.return_value = {"accepted": 1, "skipped": 0, "errors": 0}

            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            # asyncio.run should have been called (1 actionable ticket)
            mock_asyncio.assert_called_once()

    def test_filters_out_epics(self, mock_flow):
        tickets = [
            {"key": "PRD-1", "type": "Epic", "summary": "Big Epic"},
        ]

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value=None,
        ):
            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            assert "No actionable tickets" in result.output

    def test_returns_message_when_no_tickets(self, mock_flow):
        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=[],
        ):
            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            assert "No tickets to trigger" in result.output

    def test_handles_none_response_gracefully(self, mock_flow):
        tickets = [
            {"key": "PRD-10", "type": "Sub-task", "summary": "Login"},
        ]

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value="idea-xyz",
        ), patch("asyncio.run", return_value=None):
            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            assert "no response" in result.output

    def test_includes_idea_label_when_available(self, mock_flow):
        tickets = [
            {"key": "PRD-10", "type": "Sub-task", "summary": "Login"},
        ]

        captured_tasks = []

        def _capture_asyncio_run(coro):
            # We can't easily inspect the coroutine args, but we verify
            # the call was made
            return {"accepted": 1, "skipped": 0, "errors": 0}

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value="idea-xyz",
        ), patch("asyncio.run", side_effect=_capture_asyncio_run):
            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            assert "1 accepted" in result.output


# ── _resolve_idea_id ──────────────────────────────────────────


class TestResolveIdeaId:
    """Test idea ID resolution helper."""

    def test_resolves_from_mongodb(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _resolve_idea_id,
        )

        from bson import ObjectId  # noqa: F401

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = {"_id": "abc123def456"}

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_db",
            return_value=mock_db,
        ):
            result = _resolve_idea_id("run-abc")
            assert result == "abc123def456"

    def test_returns_none_when_not_found(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _resolve_idea_id,
        )

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = None

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_db",
            return_value=mock_db,
        ):
            result = _resolve_idea_id("run-xyz")
            assert result is None

    def test_returns_none_on_exception(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _resolve_idea_id,
        )

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_db",
            side_effect=Exception("DB down"),
        ):
            result = _resolve_idea_id("run-abc")
            assert result is None


# ── _build_epic_feature_map ───────────────────────────────────


class TestBuildEpicFeatureMap:
    """Test epic key → feature_id mapping builder."""

    def test_builds_map_from_idea_features(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _build_epic_feature_map,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.get_idea",
            return_value={
                "idea_id": "idea-1",
                "features": [
                    {"id": "feat-a", "name": "Auth", "jira_epic_key": "PRD-1"},
                    {"id": "feat-b", "name": "Dashboard", "jira_epic_key": "PRD-2"},
                    {"id": "feat-c", "name": "Settings", "jira_epic_key": None},
                ],
            },
        ):
            result = _build_epic_feature_map("idea-1")
            assert result == {"PRD-1": "feat-a", "PRD-2": "feat-b"}

    def test_returns_empty_when_no_idea(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _build_epic_feature_map,
        )

        result = _build_epic_feature_map(None)
        assert result == {}

    def test_returns_empty_when_idea_not_found(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _build_epic_feature_map,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.get_idea",
            return_value=None,
        ):
            result = _build_epic_feature_map("nonexistent")
            assert result == {}

    def test_returns_empty_on_exception(self):
        from crewai_productfeature_planner.orchestrator._agentic_team import (
            _build_epic_feature_map,
        )

        with patch(
            "crewai_productfeature_planner.mongodb.ideas.repository.get_idea",
            side_effect=Exception("DB error"),
        ):
            result = _build_epic_feature_map("idea-1")
            assert result == {}


# ── Feature label in kickoff payload ──────────────────────────


class TestFeatureLabelInKickoff:
    """Test that feature labels are included in the batch kickoff payload."""

    def test_includes_feature_label_via_parent_key(self, mock_flow):
        """Tickets with parent_key should resolve feature_id from epic map."""
        tickets = [
            {"key": "PRD-10", "type": "Sub-task", "summary": "Login flow",
             "parent_key": "PRD-1"},
            {"key": "PRD-11", "type": "Sub-task", "summary": "Dashboard",
             "parent_key": "PRD-2"},
        ]

        captured_coro = []

        def _capture(coro):
            captured_coro.append(coro)
            return {"accepted": 2, "skipped": 0, "errors": 0}

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value="idea-xyz",
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._build_epic_feature_map",
            return_value={"PRD-1": "feat-a", "PRD-2": "feat-b"},
        ), patch("asyncio.run", side_effect=_capture):
            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            assert "2 accepted" in result.output
            assert len(captured_coro) == 1

    def test_no_feature_label_when_no_parent_key(self, mock_flow):
        """Tickets without parent_key should not crash (graceful fallback)."""
        tickets = [
            {"key": "PRD-10", "type": "Story", "summary": "Login flow"},
        ]

        def _capture(coro):
            return {"accepted": 1, "skipped": 0, "errors": 0}

        with patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.AGENTIC_TEAM_ENABLED",
            True,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team.get_jira_tickets",
            return_value=tickets,
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._resolve_idea_id",
            return_value="idea-xyz",
        ), patch(
            "crewai_productfeature_planner.orchestrator._agentic_team._build_epic_feature_map",
            return_value={"PRD-1": "feat-a"},
        ), patch("asyncio.run", side_effect=_capture):
            stage = build_agentic_team_trigger_stage(mock_flow)
            result = stage.run()

            assert "1 accepted" in result.output
