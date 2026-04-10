"""Tests for kanban board-style support in orchestrator._jira."""

import pytest
from unittest.mock import patch, MagicMock

from crewai_productfeature_planner.flows.prd_flow import PRDFlow
from crewai_productfeature_planner.orchestrator.orchestrator import StageResult
from crewai_productfeature_planner.orchestrator._jira import (
    _get_board_style,
    build_jira_skeleton_stage,
    build_jira_epics_stories_stage,
    build_jira_kanban_tasks_stage,
    build_jira_ticketing_stage,
)


@pytest.fixture()
def _jira_env(monkeypatch):
    monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_PROJECT_KEY", "PRD")
    monkeypatch.setenv("ATLASSIAN_USERNAME", "user@example.com")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "key")


# ── _get_board_style helper ─────────────────────────────────────────


class TestGetBoardStyle:

    _PATCH = "crewai_productfeature_planner.mongodb.project_config.get_project_for_run"

    def test_defaults_to_scrum(self):
        flow = PRDFlow()
        with patch(self._PATCH, return_value={}):
            assert _get_board_style(flow) == "scrum"

    def test_kanban_from_project_config(self):
        flow = PRDFlow()
        with patch(self._PATCH, return_value={"board_style": "kanban"}):
            assert _get_board_style(flow) == "kanban"

    def test_scrum_from_project_config(self):
        flow = PRDFlow()
        with patch(self._PATCH, return_value={"board_style": "scrum"}):
            assert _get_board_style(flow) == "scrum"

    def test_defaults_on_exception(self):
        flow = PRDFlow()
        with patch(self._PATCH, side_effect=RuntimeError("DB down")):
            assert _get_board_style(flow) == "scrum"

    def test_defaults_when_no_project(self):
        flow = PRDFlow()
        with patch(self._PATCH, return_value=None):
            assert _get_board_style(flow) == "scrum"


# ── Skeleton stage — kanban task selection ───────────────────────────


class TestSkeletonKanbanSelection:

    @pytest.fixture()
    def kanban_flow(self):
        flow = PRDFlow()
        flow.state.run_id = "run-kanban-skel"
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.idea = "Build a dashboard"
        return flow

    @pytest.fixture()
    def _kanban_board(self):
        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="kanban",
        ):
            yield

    def test_skeleton_apply_sets_kanban_phase(
        self, _jira_env, _kanban_board, kanban_flow
    ):
        stage = build_jira_skeleton_stage(kanban_flow, require_confluence=False)
        result = StageResult(output="## Kanban Skeleton")

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._persist_jira_phase"
        ) as mock_persist, patch(
            "crewai_productfeature_planner.mongodb.working_ideas.repository.save_jira_skeleton",
        ):
            stage.apply(result)

        assert kanban_flow.state.jira_phase == "kanban_skeleton_pending"
        mock_persist.assert_called_once_with(
            "run-kanban-skel", "kanban_skeleton_pending",
        )

    def test_skeleton_apply_sets_scrum_phase_by_default(self, _jira_env):
        flow = PRDFlow()
        flow.state.run_id = "run-scrum-skel"
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="scrum",
        ):
            stage = build_jira_skeleton_stage(flow, require_confluence=False)

        result = StageResult(output="## Scrum Skeleton")
        with patch(
            "crewai_productfeature_planner.orchestrator._jira._persist_jira_phase"
        ), patch(
            "crewai_productfeature_planner.mongodb.working_ideas.repository.save_jira_skeleton",
        ):
            stage.apply(result)

        assert flow.state.jira_phase == "skeleton_pending"


# ── Epics/Stories stage — skips for kanban ───────────────────────────


class TestEpicsStoriesKanbanSkip:

    def test_skips_when_kanban(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "skeleton_approved"
        flow.state.jira_skeleton = "## Skeleton"

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="kanban",
        ):
            stage = build_jira_epics_stories_stage(
                flow, require_confluence=False,
            )
            assert stage.should_skip() is True

    def test_does_not_skip_when_scrum(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "skeleton_approved"
        flow.state.jira_skeleton = "## Skeleton"

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="scrum",
        ):
            stage = build_jira_epics_stories_stage(
                flow, require_confluence=False,
            )
            assert stage.should_skip() is False


# ── Kanban tasks stage ──────────────────────────────────────────────


class TestKanbanTasksStage:

    @pytest.fixture()
    def kanban_flow(self):
        flow = PRDFlow()
        flow.state.run_id = "run-kanban-tasks"
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_skeleton = "## Kanban Skeleton"
        flow.state.jira_phase = "kanban_skeleton_approved"
        return flow

    @pytest.fixture()
    def _kanban_board(self):
        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="kanban",
        ):
            yield

    def test_stage_name(self, _kanban_board, kanban_flow):
        stage = build_jira_kanban_tasks_stage(kanban_flow)
        assert stage.name == "jira_kanban_tasks"

    def test_does_not_skip_with_approved_skeleton(
        self, _jira_env, _kanban_board, kanban_flow
    ):
        stage = build_jira_kanban_tasks_stage(
            kanban_flow, require_confluence=False,
        )
        assert stage.should_skip() is False

    def test_skips_when_not_kanban(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_skeleton = "## Skeleton"
        flow.state.jira_phase = "kanban_skeleton_approved"

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="scrum",
        ):
            stage = build_jira_kanban_tasks_stage(
                flow, require_confluence=False,
            )
            assert stage.should_skip() is True

    def test_skips_when_no_skeleton(self, _jira_env, _kanban_board):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_skeleton = ""
        flow.state.jira_phase = "kanban_skeleton_approved"

        stage = build_jira_kanban_tasks_stage(flow, require_confluence=False)
        assert stage.should_skip() is True

    def test_skips_when_pending(self, _jira_env, _kanban_board):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_skeleton = "## Skeleton"
        flow.state.jira_phase = "kanban_skeleton_pending"

        stage = build_jira_kanban_tasks_stage(flow, require_confluence=False)
        assert stage.should_skip() is True

    def test_skips_when_already_done(self, _jira_env, _kanban_board):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_skeleton = "## Skeleton"
        flow.state.jira_phase = "kanban_tasks_done"

        stage = build_jira_kanban_tasks_stage(flow, require_confluence=False)
        assert stage.should_skip() is True

    def test_apply_sets_kanban_tasks_done(self, _kanban_board, kanban_flow):
        stage = build_jira_kanban_tasks_stage(kanban_flow)
        result = StageResult(output="Task PRD-201, Task PRD-202")

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._persist_jira_phase"
        ) as mock_persist:
            stage.apply(result)

        assert kanban_flow.state.jira_output == "Task PRD-201, Task PRD-202"
        assert kanban_flow.state.jira_phase == "kanban_tasks_done"
        mock_persist.assert_called_once_with(
            "run-kanban-tasks", "kanban_tasks_done",
        )


# ── Ticketing stage — kanban routing ─────────────────────────────────


class TestTicketingKanbanRouting:

    @pytest.fixture()
    def _kanban_board(self):
        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="kanban",
        ):
            yield

    def test_ticketing_skips_when_kanban_done(self, _jira_env, _kanban_board):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "kanban_tasks_done"

        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is True

    def test_ticketing_does_not_skip_kanban_not_done(
        self, _jira_env, _kanban_board
    ):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = ""

        stage = build_jira_ticketing_stage(flow)
        assert stage.should_skip() is False

    def test_ticketing_skips_scrum_qa_test_done(self, _jira_env):
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.confluence_url = "https://wiki.example.com/p/1"
        flow.state.jira_phase = "qa_test_done"

        with patch(
            "crewai_productfeature_planner.orchestrator._jira._get_board_style",
            return_value="scrum",
        ):
            stage = build_jira_ticketing_stage(flow)
            assert stage.should_skip() is True
