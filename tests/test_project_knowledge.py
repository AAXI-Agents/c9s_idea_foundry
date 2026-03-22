"""Tests for scripts.project_knowledge — Obsidian project knowledge base builder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.project_knowledge import (
    _idea_title_from_doc,
    _safe_dirname,
    _safe_filename,
    _truncate,
    generate_idea_page,
    generate_project_page,
    load_completed_ideas_context,
    sync_completed_idea,
    sync_project_knowledge,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── _safe_dirname ─────────────────────────────────────────────


def test_safe_dirname_basic():
    assert _safe_dirname("My Project") == "my-project"


def test_safe_dirname_special_chars():
    assert _safe_dirname("Test!@#$%^&*()") == "test"


def test_safe_dirname_collapses_hyphens():
    assert _safe_dirname("hello---world") == "hello-world"


def test_safe_dirname_strips_leading_trailing():
    assert _safe_dirname("  --hello--  ") == "hello"


def test_safe_dirname_empty():
    assert _safe_dirname("") == "unnamed"


def test_safe_dirname_unicode():
    result = _safe_dirname("Café résumé")
    assert "cafe" in result


# ── _safe_filename ────────────────────────────────────────────


def test_safe_filename_delegates():
    """_safe_filename uses _safe_dirname under the hood."""
    assert _safe_filename("My Idea Title") == "my-idea-title"


# ── _truncate ─────────────────────────────────────────────────


def test_truncate_short():
    assert _truncate("short", 500) == "short"


def test_truncate_long():
    long_text = "word " * 200  # 1000 chars
    result = _truncate(long_text, 50)
    assert len(result) <= 51  # 50 + ellipsis char
    assert result.endswith("…")


# ── _idea_title_from_doc ─────────────────────────────────────


def test_idea_title_from_idea():
    doc = {"idea": "# Build a Dashboard\nSome details here"}
    assert _idea_title_from_doc(doc) == "Build a Dashboard"


def test_idea_title_from_finalized():
    doc = {"finalized_idea": "Create a login page"}
    assert _idea_title_from_doc(doc) == "Create a login page"


def test_idea_title_empty():
    doc = {}
    assert _idea_title_from_doc(doc) == "Untitled Idea"


def test_idea_title_very_long():
    doc = {"idea": "A" * 100}
    result = _idea_title_from_doc(doc)
    assert len(result) <= 80


# ── generate_project_page ────────────────────────────────────


def test_generate_project_page_basic(tmp_path, monkeypatch):
    """Should create a project overview page with config."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    config = {
        "project_id": "proj-123",
        "name": "Test Project",
        "confluence_space_key": "TESTSPACE",
        "jira_project_key": "TEST",
    }

    result = generate_project_page(config)

    assert result.exists()
    content = result.read_text()
    assert "# Test Project" in content
    assert "proj-123" in content
    assert "TESTSPACE" in content
    assert "TEST" in content


def test_generate_project_page_with_memory(tmp_path, monkeypatch):
    """Should include project memory sections."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    config = {"project_id": "proj-1", "name": "MemProject"}
    memory = {
        "idea_iteration": [{"content": "Keep it simple"}],
        "knowledge": [{"content": "https://wiki.example.com", "kind": "link"}],
        "tools": [{"content": "React"}, {"content": "Node.js"}],
    }

    result = generate_project_page(config, memory)

    content = result.read_text()
    assert "Idea-Iteration Guardrails" in content
    assert "Keep it simple" in content
    assert "Knowledge References" in content
    assert "wiki.example.com" in content
    assert "Technology Stack" in content
    assert "React" in content
    assert "Node.js" in content


def test_generate_project_page_with_reference_urls(tmp_path, monkeypatch):
    """Should include reference URLs section."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    config = {
        "project_id": "proj-1",
        "name": "UrlProject",
        "reference_urls": ["https://docs.example.com", "https://api.example.com"],
    }

    result = generate_project_page(config)

    content = result.read_text()
    assert "Reference URLs" in content
    assert "https://docs.example.com" in content


def test_generate_project_page_creates_ideas_subdir(tmp_path, monkeypatch):
    """Should create the ideas/ subdirectory."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    config = {"project_id": "proj-1", "name": "SubdirProject"}

    generate_project_page(config)

    dirname = _safe_dirname("SubdirProject")
    ideas_dir = tmp_path / dirname / "ideas"
    assert ideas_dir.is_dir()


def test_generate_project_page_links_existing_ideas(tmp_path, monkeypatch):
    """Should list wikilinks to existing idea pages."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    # Pre-create an idea file
    dirname = _safe_dirname("LinkProject")
    ideas_dir = tmp_path / dirname / "ideas"
    ideas_dir.mkdir(parents=True)
    (ideas_dir / "my-idea.md").write_text("# My Idea")

    config = {"project_id": "proj-1", "name": "LinkProject"}
    result = generate_project_page(config)

    content = result.read_text()
    assert "Completed Ideas" in content
    assert "[[ideas/my-idea.md|My Idea]]" in content


# ── generate_idea_page ───────────────────────────────────────


def test_generate_idea_page_basic(tmp_path, monkeypatch):
    """Should create a completed idea page with YAML frontmatter."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    doc = {
        "run_id": "run-001",
        "status": "completed",
        "created_at": "2026-03-20T10:00:00Z",
        "completed_at": "2026-03-21T15:00:00Z",
        "idea": "# Dashboard Feature\nBuild a real-time dashboard",
        "finalized_idea": "Build a comprehensive real-time dashboard",
        "executive_summary": [{"content": "A dashboard for real-time monitoring"}],
        "section": {},
    }

    result = generate_idea_page(doc, "Test Project")

    assert result is not None
    assert result.exists()
    content = result.read_text()
    assert "---" in content  # YAML frontmatter
    assert "run_id: run-001" in content
    assert "status: completed" in content
    assert "tags: [idea, prd, completed]" in content
    assert "# Dashboard Feature" in content
    assert "Executive Summary" in content
    assert "real-time monitoring" in content


def test_generate_idea_page_with_sections(tmp_path, monkeypatch):
    """Should include PRD sections from the document."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    doc = {
        "run_id": "run-002",
        "status": "completed",
        "idea": "Auth System",
        "section": {
            "problem_statement": [{"content": "Users cannot log in securely"}],
            "user_personas": [{"content": "Admin, Developer, Viewer roles"}],
        },
    }

    result = generate_idea_page(doc, "Auth Project")

    content = result.read_text()
    assert "Problem Statement" in content
    assert "Users cannot log in securely" in content
    assert "User Personas" in content


def test_generate_idea_page_with_figma(tmp_path, monkeypatch):
    """Should include UX Design section when Figma URL is present."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    doc = {
        "run_id": "run-003",
        "status": "completed",
        "idea": "UX Feature",
        "figma_design_url": "https://figma.com/proto/abc",
        "section": {},
    }

    result = generate_idea_page(doc, "UX Project")

    content = result.read_text()
    assert "UX Design" in content
    assert "https://figma.com/proto/abc" in content


def test_generate_idea_page_with_delivery(tmp_path, monkeypatch):
    """Should include delivery status when present."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    doc = {
        "run_id": "run-004",
        "status": "completed",
        "idea": "Delivered Feature",
        "confluence_url": "https://wiki.example.com/page/123",
        "jira_phase": "epics_stories",
        "section": {},
    }

    result = generate_idea_page(doc, "Delivery Project")

    content = result.read_text()
    assert "Delivery Status" in content
    assert "https://wiki.example.com/page/123" in content
    assert "epics_stories" in content


def test_generate_idea_page_original_and_refined(tmp_path, monkeypatch):
    """Should show both original and refined when they differ."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    doc = {
        "run_id": "run-005",
        "status": "completed",
        "idea": "Original idea text",
        "finalized_idea": "Refined idea text",
        "section": {},
    }

    result = generate_idea_page(doc, "Refine Project")

    content = result.read_text()
    assert "Original Idea" in content
    assert "Original idea text" in content
    assert "Refined Idea" in content
    assert "Refined idea text" in content


# ── load_completed_ideas_context ─────────────────────────────


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_load_completed_ideas_context_with_docs(mock_get_db):
    """Should return formatted context with completed idea summaries."""
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = [
        {
            "run_id": "run-1",
            "idea": "# Dashboard\nA real-time dashboard",
            "executive_summary": [{"content": "Dashboard for monitoring KPIs"}],
            "completed_at": "2026-03-20",
        },
        {
            "run_id": "run-2",
            "idea": "# Auth System\nSSO integration",
            "executive_summary": [{"content": "Single sign-on for enterprise"}],
            "completed_at": "2026-03-19",
        },
    ]
    col = MagicMock()
    col.find.return_value = cursor_mock
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    result = load_completed_ideas_context("proj-abc")

    assert "2 completed idea(s)" in result
    assert "Dashboard" in result
    assert "Auth System" in result
    assert "monitoring KPIs" in result


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_load_completed_ideas_no_docs(mock_get_db):
    """Should return empty string when no completed ideas."""
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = []
    col = MagicMock()
    col.find.return_value = cursor_mock
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    result = load_completed_ideas_context("proj-empty")
    assert result == ""


def test_load_completed_ideas_empty_project_id():
    """Should return empty string for empty project_id."""
    assert load_completed_ideas_context("") == ""


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_load_completed_ideas_db_error(mock_get_db):
    """Should return empty string on DB error."""
    mock_get_db.side_effect = Exception("connection lost")

    result = load_completed_ideas_context("proj-abc")
    assert result == ""


# ── sync_project_knowledge ───────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.get_project_memory")
@patch("crewai_productfeature_planner.mongodb.project_config.get_project")
def test_sync_project_knowledge_creates_page(
    mock_get_proj, mock_get_mem, tmp_path, monkeypatch,
):
    """Should create the project overview page."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    mock_get_proj.return_value = {
        "project_id": "proj-sync",
        "name": "Sync Project",
    }
    mock_get_mem.return_value = None

    result = sync_project_knowledge("proj-sync")

    assert result is not None
    assert result.exists()
    assert "# Sync Project" in result.read_text()


@patch("crewai_productfeature_planner.mongodb.project_config.get_project")
def test_sync_project_knowledge_no_config(mock_get_proj):
    """Should return None when no project config exists."""
    mock_get_proj.return_value = None

    result = sync_project_knowledge("proj-missing")
    assert result is None


# ── sync_completed_idea ──────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_memory.get_project_memory")
@patch("crewai_productfeature_planner.mongodb.project_config.get_project")
@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_sync_completed_idea_creates_page(
    mock_get_db, mock_get_proj, mock_get_mem, tmp_path, monkeypatch,
):
    """Should generate idea page and refresh project overview."""
    monkeypatch.setattr(
        "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
        tmp_path,
    )
    col = MagicMock()
    col.find_one.return_value = {
        "run_id": "run-sync",
        "project_id": "proj-x",
        "status": "completed",
        "idea": "# Sync Feature\nA sync feature",
        "section": {},
    }
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    mock_get_proj.return_value = {
        "project_id": "proj-x",
        "name": "SyncTest",
    }
    mock_get_mem.return_value = None

    result = sync_completed_idea("run-sync")

    assert result is not None
    assert result.exists()
    assert "Sync Feature" in result.read_text()

    # Project overview page should also exist
    dirname = _safe_dirname("SyncTest")
    project_page = tmp_path / dirname / f"{dirname}.md"
    assert project_page.exists()


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_sync_completed_idea_no_doc(mock_get_db):
    """Should return None when workingIdeas doc not found."""
    col = MagicMock()
    col.find_one.return_value = None
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    result = sync_completed_idea("run-missing")
    assert result is None


@patch("crewai_productfeature_planner.mongodb.client.get_db")
def test_sync_completed_idea_no_project_id(mock_get_db):
    """Should return None when doc has no project_id."""
    col = MagicMock()
    col.find_one.return_value = {"run_id": "run-x"}  # no project_id
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    mock_get_db.return_value = db

    result = sync_completed_idea("run-x")
    assert result is None


# ── enrich_backstory integration ─────────────────────────────


@patch(
    "crewai_productfeature_planner.scripts.memory_loader.load_project_memory_context",
)
@patch(
    "crewai_productfeature_planner.scripts.project_knowledge.load_completed_ideas_context",
)
def test_enrich_backstory_includes_completed_ideas(mock_ideas, mock_mem):
    """enrich_backstory should append completed ideas context."""
    from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory

    mock_mem.return_value = "\n=== PROJECT MEMORY ===\nBe concise"
    mock_ideas.return_value = "\n── Completed Ideas ──\n1. Dashboard"

    result = enrich_backstory("I am a PM.", "proj-1")

    assert "PROJECT MEMORY" in result
    assert "Completed Ideas" in result
    assert "Dashboard" in result


@patch(
    "crewai_productfeature_planner.scripts.memory_loader.load_project_memory_context",
)
@patch(
    "crewai_productfeature_planner.scripts.project_knowledge.load_completed_ideas_context",
)
def test_enrich_backstory_no_ideas(mock_ideas, mock_mem):
    """When no completed ideas, backstory should still include project memory."""
    from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory

    mock_mem.return_value = "\n=== PROJECT MEMORY ===\nBe concise"
    mock_ideas.return_value = ""

    result = enrich_backstory("I am a PM.", "proj-1")

    assert "PROJECT MEMORY" in result
    assert "Completed Ideas" not in result
