"""Tests for Block Kit builders — project memory blocks."""

import pytest

from crewai_productfeature_planner.apis.slack.blocks import (
    memory_category_prompt_blocks,
    memory_configure_blocks,
    memory_saved_blocks,
    memory_view_blocks,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── memory_configure_blocks ──────────────────────────────────


class TestMemoryConfigureBlocks:
    def test_returns_blocks(self):
        """Should return a non-empty list of blocks."""
        blocks = memory_configure_blocks("MyProject", "U1")
        assert isinstance(blocks, list)
        assert len(blocks) >= 3  # header + section + actions

    def test_header_mentions_project(self):
        """Header should mention the project name."""
        blocks = memory_configure_blocks("MyProject", "U1")
        header = blocks[0]
        assert header["type"] == "header"
        assert "MyProject" in header["text"]["text"]

    def test_has_five_action_buttons(self):
        """Should have buttons for idea, knowledge, tools, view, done."""
        blocks = memory_configure_blocks("MyProject", "U1")
        actions = [b for b in blocks if b["type"] == "actions"]
        assert len(actions) >= 1
        # Flatten all action elements
        buttons = []
        for a in actions:
            buttons.extend(a["elements"])
        action_ids = {b["action_id"] for b in buttons}
        assert "memory_idea" in action_ids
        assert "memory_knowledge" in action_ids
        assert "memory_tools" in action_ids
        assert "memory_view" in action_ids
        assert "memory_done" in action_ids


# ── memory_category_prompt_blocks ────────────────────────────


class TestMemoryCategoryPromptBlocks:
    def test_returns_blocks(self):
        blocks = memory_category_prompt_blocks(
            "idea_iteration", "Idea Iteration", "How should agents iterate?",
        )
        assert isinstance(blocks, list)
        assert len(blocks) >= 1

    def test_includes_help_text(self):
        blocks = memory_category_prompt_blocks(
            "tools", "Technology Stack", "List your tech stack",
        )
        text_content = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        )
        assert "tech stack" in text_content.lower() or "Technology Stack" in text_content


# ── memory_saved_blocks ──────────────────────────────────────


class TestMemorySavedBlocks:
    def test_returns_blocks(self):
        blocks = memory_saved_blocks("Idea Iteration", 3)
        assert isinstance(blocks, list)
        assert len(blocks) >= 1

    def test_shows_count(self):
        blocks = memory_saved_blocks("Technology Stack", 5)
        text_content = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        )
        assert "5" in text_content

    def test_shows_label(self):
        blocks = memory_saved_blocks("Knowledge", 2)
        text_content = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") == "section"
        )
        assert "Knowledge" in text_content


# ── memory_view_blocks ───────────────────────────────────────


class TestMemoryViewBlocks:
    def test_empty_entries(self):
        """Should return blocks even with empty entries."""
        blocks = memory_view_blocks("MyProject", [], [], [])
        assert isinstance(blocks, list)
        assert len(blocks) >= 1

    def test_shows_project_name(self):
        blocks = memory_view_blocks("MyProject", [], [], [])
        header = blocks[0]
        assert "MyProject" in header.get("text", {}).get("text", "")

    def test_shows_entries(self):
        """Entries should appear in the view blocks."""
        idea = [{"content": "Be concise"}]
        knowledge = [{"content": "https://docs.example.com", "kind": "link"}]
        tools = [{"content": "PostgreSQL"}]

        blocks = memory_view_blocks("TestProject", idea, knowledge, tools)

        # Flatten all text content
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") in ("section", "header")
        )
        assert "Be concise" in all_text
        assert "https://docs.example.com" in all_text
        assert "PostgreSQL" in all_text

    def test_partial_entries(self):
        """Should handle some categories empty, others populated."""
        blocks = memory_view_blocks(
            "Partial", [], [], [{"content": "Redis"}],
        )
        all_text = " ".join(
            b.get("text", {}).get("text", "")
            for b in blocks
            if b.get("type") in ("section", "header")
        )
        assert "Redis" in all_text
