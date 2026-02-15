"""Tests for the iterative PRD flow."""

from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.apis.prd.models import PRDDraft, PRDSection, SECTION_KEYS
from crewai_productfeature_planner.flows.prd_flow import PAUSE_SENTINEL, PauseRequested, PRDFlow, PRDState


def test_prd_state_defaults():
    """PRDState should initialise with sensible defaults."""
    state = PRDState()
    assert state.idea == ""
    assert isinstance(state.draft, PRDDraft)
    assert len(state.draft.sections) == len(SECTION_KEYS)
    assert state.critique == ""
    assert state.final_prd == ""
    assert state.current_section_key == ""
    assert state.iteration == 0
    assert state.is_ready is False
    assert len(state.run_id) == 12  # auto-generated hex id


def test_prd_draft_sections_initialised():
    """PRDDraft should have all sections in the correct order."""
    draft = PRDDraft.create_empty()
    assert len(draft.sections) == len(SECTION_KEYS)
    assert draft.sections[0].key == "executive_summary"
    assert draft.sections[0].title == "Executive Summary"
    assert all(s.content == "" for s in draft.sections)
    assert all(s.iteration == 0 for s in draft.sections)
    assert all(not s.is_approved for s in draft.sections)


def test_prd_draft_get_section():
    """get_section should return the correct section by key."""
    draft = PRDDraft.create_empty()
    section = draft.get_section("executive_summary")
    assert section is not None
    assert section.key == "executive_summary"
    assert draft.get_section("nonexistent") is None


def test_prd_draft_approved_context():
    """approved_context should return only approved sections with content."""
    draft = PRDDraft.create_empty()
    es = draft.get_section("executive_summary")
    es.content = "Brief summary"
    es.is_approved = True
    ps = draft.get_section("problem_statement")
    ps.content = "The problem is..."
    ps.is_approved = False

    ctx = draft.approved_context()
    assert "Brief summary" in ctx
    assert "The problem is..." not in ctx

    ctx_excluding = draft.approved_context(exclude_key="executive_summary")
    assert "Brief summary" not in ctx_excluding


def test_prd_draft_all_sections_context():
    """all_sections_context should return all sections with content and their status."""
    draft = PRDDraft.create_empty()
    es = draft.get_section("executive_summary")
    es.content = "Summary"
    es.is_approved = True
    ps = draft.get_section("problem_statement")
    ps.content = "Problem"

    ctx = draft.all_sections_context()
    assert "[APPROVED]" in ctx
    assert "[DRAFT]" in ctx


def test_prd_draft_all_approved():
    """all_approved should return True only when all sections approved."""
    draft = PRDDraft.create_empty()
    assert not draft.all_approved()
    for s in draft.sections:
        s.is_approved = True
    assert draft.all_approved()


def test_prd_draft_next_section():
    """next_section should return the first unapproved section."""
    draft = PRDDraft.create_empty()
    assert draft.next_section().key == "executive_summary"
    draft.sections[0].is_approved = True
    assert draft.next_section().key == "problem_statement"


def test_prd_draft_assemble():
    """assemble should combine all sections into a single markdown document."""
    draft = PRDDraft.create_empty()
    draft.get_section("executive_summary").content = "Summary content"
    draft.get_section("problem_statement").content = "Problem content"
    result = draft.assemble()
    assert "# Product Requirements Document" in result
    assert "## Executive Summary" in result
    assert "Summary content" in result
    assert "## Problem Statement" in result
    assert "Problem content" in result


def test_prd_flow_sets_idea():
    """Flow should propagate the idea into its state."""
    flow = PRDFlow()
    flow.state.idea = "Build a real-time chat feature"
    assert flow.state.idea == "Build a real-time chat feature"


def test_prd_state_section_ready_detection():
    """SECTION_READY in the critique should signal readiness."""
    state = PRDState(
        critique="Score: 9/10 - Status: SECTION_READY",
    )
    assert "SECTION_READY" in state.critique.upper()


def test_prd_state_needs_refinement_detection():
    """NEEDS_REFINEMENT in the critique should not pass the quality gate."""
    state = PRDState(
        critique="Score: 5/10 - Status: NEEDS_REFINEMENT",
    )
    assert "SECTION_READY" not in state.critique.upper()


def test_prd_flow_approval_callback():
    """Flow should accept an approval callback with section signature."""
    flow = PRDFlow()
    cb = lambda iteration, section_key, content, draft: True
    flow.approval_callback = cb
    assert flow.approval_callback is cb


def test_prd_flow_approval_callback_accepts_string():
    """Callback returning a string should be accepted (user feedback)."""
    flow = PRDFlow()
    cb = lambda iteration, section_key, content, draft: "Add more security details"
    flow.approval_callback = cb
    result = flow.approval_callback(1, "executive_summary", "# Draft", PRDDraft.create_empty())
    assert isinstance(result, str)
    assert result == "Add more security details"


def test_pause_sentinel_value():
    """PAUSE_SENTINEL should be the expected string constant."""
    assert PAUSE_SENTINEL == "__PAUSE__"


def test_pause_requested_is_exception():
    """PauseRequested should be an Exception so it can propagate out of the flow."""
    assert issubclass(PauseRequested, Exception)
    exc = PauseRequested()
    assert isinstance(exc, Exception)


def test_prd_flow_callback_returning_pause_sentinel():
    """Callback returning PAUSE_SENTINEL should be detected as a pause request."""
    flow = PRDFlow()
    cb = lambda iteration, section_key, content, draft: PAUSE_SENTINEL
    flow.approval_callback = cb
    result = flow.approval_callback(1, "executive_summary", "# Draft", PRDDraft.create_empty())
    assert result == PAUSE_SENTINEL


def test_section_approval_loop_raises_pause(monkeypatch):
    """_section_approval_loop should raise PauseRequested when callback returns PAUSE_SENTINEL."""
    import pytest

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-run"
    flow.approval_callback = lambda iteration, key, content, draft: PAUSE_SENTINEL

    section = flow.state.draft.sections[0]
    section.content = "Some draft content"
    section.iteration = 1

    with pytest.raises(PauseRequested):
        flow._section_approval_loop(section, MagicMock(), {})


@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_finalize_saves_prd(mock_writer_cls, mock_save_finalized):
    """finalize() should persist the assembled PRD via file and MongoDB with XHTML."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved to output/prds/prd_v1.md"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    # Fill in sections with content
    for section in flow.state.draft.sections:
        section.content = f"Content for {section.title}"
        section.is_approved = True
    flow.state.iteration = 10
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-run-123"

    result = flow.finalize()

    mock_writer._run.assert_called_once()
    mock_save_finalized.assert_called_once()
    call_kwargs = mock_save_finalized.call_args[1]
    assert call_kwargs["run_id"] == "test-run-123"
    assert call_kwargs["idea"] == "Test idea"
    assert call_kwargs["iteration"] == 10
    assert "# Product Requirements Document" in call_kwargs["final_prd"]
    assert "## Executive Summary" in call_kwargs["final_prd"]
    # XHTML should be generated and passed
    assert "confluence_xhtml" in call_kwargs
    xhtml = call_kwargs["confluence_xhtml"]
    assert "<h1" in xhtml or "<h2" in xhtml
    assert "saved" in result.lower()
