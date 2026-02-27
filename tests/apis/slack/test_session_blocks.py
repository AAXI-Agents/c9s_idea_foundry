"""Tests for Block Kit builders — project session blocks."""

import pytest

from crewai_productfeature_planner.apis.slack.blocks import (
    active_session_blocks,
    project_create_prompt_blocks,
    project_selection_blocks,
    session_ended_blocks,
    session_started_blocks,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── project_selection_blocks ─────────────────────────────────


class TestProjectSelectionBlocks:
    def test_empty_projects(self):
        """Should still show Create New button even with no projects."""
        blocks = project_selection_blocks([], "U1")
        # header + section + divider + actions = 4
        assert len(blocks) == 4
        actions = blocks[-1]
        assert actions["type"] == "actions"
        assert len(actions["elements"]) == 1  # only "Create New"
        assert actions["elements"][0]["action_id"] == "project_create"
        assert actions["elements"][0]["value"] == "U1"

    def test_projects_shown_as_buttons(self):
        """Each project should create a selection button."""
        projects = [
            {"project_id": "p1", "name": "Alpha"},
            {"project_id": "p2", "name": "Beta"},
        ]
        blocks = project_selection_blocks(projects, "U1")
        actions = [b for b in blocks if b["type"] == "actions"][0]
        # 2 project buttons + 1 Create New = 3
        assert len(actions["elements"]) == 3
        assert actions["elements"][0]["action_id"] == "project_select_p1"
        assert actions["elements"][1]["action_id"] == "project_select_p2"
        assert actions["elements"][2]["action_id"] == "project_create"

    def test_max_five_projects(self):
        """Only the first 5 projects should be shown as buttons."""
        projects = [
            {"project_id": f"p{i}", "name": f"Project {i}"}
            for i in range(8)
        ]
        blocks = project_selection_blocks(projects, "U1")
        actions = [b for b in blocks if b["type"] == "actions"][0]
        # 5 project buttons + 1 Create New = 6
        assert len(actions["elements"]) == 6
        # Context line should mention overflow
        context = [b for b in blocks if b["type"] == "context"]
        assert len(context) == 1
        assert "8 projects" in context[0]["elements"][0]["text"]

    def test_no_overflow_context_for_five_or_fewer(self):
        """No context line when <= 5 projects."""
        projects = [{"project_id": f"p{i}", "name": f"P{i}"} for i in range(5)]
        blocks = project_selection_blocks(projects, "U1")
        context = [b for b in blocks if b["type"] == "context"]
        assert context == []

    def test_block_id_includes_user(self):
        blocks = project_selection_blocks([], "U42")
        actions = [b for b in blocks if b["type"] == "actions"][0]
        assert actions["block_id"] == "project_select_U42"


# ── active_session_blocks ───────────────────────────────────


class TestActiveSessionBlocks:
    def test_basic_structure(self):
        blocks = active_session_blocks("MyProject", "p1", "U1")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "section"
        assert "MyProject" in blocks[0]["text"]["text"]

    def test_action_ids(self):
        blocks = active_session_blocks("P", "p1", "U1")
        actions = blocks[1]
        assert actions["type"] == "actions"
        ids = [e["action_id"] for e in actions["elements"]]
        assert ids == ["project_continue", "project_switch", "session_end"]

    def test_continue_value_is_project_id(self):
        blocks = active_session_blocks("P", "proj-42", "U1")
        continue_btn = blocks[1]["elements"][0]
        assert continue_btn["value"] == "proj-42"


# ── project_create_prompt_blocks ─────────────────────────────


class TestProjectCreatePromptBlocks:
    def test_structure(self):
        blocks = project_create_prompt_blocks("U1")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert "Create a New Project" in blocks[0]["text"]["text"]


# ── session_started_blocks ───────────────────────────────────


class TestSessionStartedBlocks:
    def test_includes_project_name(self):
        blocks = session_started_blocks("Acme Corp")
        assert len(blocks) == 1
        assert "Acme Corp" in blocks[0]["text"]["text"]
        assert "switch project" in blocks[0]["text"]["text"]


# ── session_ended_blocks ─────────────────────────────────────


class TestSessionEndedBlocks:
    def test_structure(self):
        blocks = session_ended_blocks()
        assert len(blocks) == 1
        assert "ended" in blocks[0]["text"]["text"].lower()
