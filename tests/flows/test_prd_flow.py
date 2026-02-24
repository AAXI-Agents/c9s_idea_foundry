"""Tests for the iterative PRD flow."""

import pytest
from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.apis.prd.models import (
    AGENT_GEMINI,
    AGENT_OPENAI,
    DEFAULT_AGENT_FALLBACK,
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
    PRDDraft,
    PRDSection,
    SECTION_KEYS,
    VALID_AGENTS,
    get_default_agent,
)

# Stand-in identifier used in multi-agent infrastructure tests.
_SECOND_AGENT = "second_pm"
from crewai_productfeature_planner.flows.prd_flow import (
    DEFAULT_MAX_SECTION_ITERATIONS,
    DEFAULT_MIN_SECTION_ITERATIONS,
    ExecutiveSummaryCompleted,
    PAUSE_SENTINEL,
    PauseRequested,
    PRDFlow,
    PRDState,
    _get_section_iteration_limits,
    _is_degenerate_content,
)


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
    assert state.status == "new"
    assert state.created_at == ""
    assert state.update_date == ""
    assert state.completed_at == ""
    assert len(state.run_id) == 12  # auto-generated hex id


def test_prd_draft_sections_initialised():
    """PRDDraft should have all sections in the correct order."""
    draft = PRDDraft.create_empty()
    assert len(draft.sections) == len(SECTION_KEYS)
    assert draft.sections[0].key == "executive_summary"
    assert draft.sections[0].title == "Executive Summary"
    assert draft.sections[1].key == "problem_statement"
    assert draft.sections[1].title == "Problem Statement"
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
    """Flow should accept an approval callback with agent_results signature."""
    flow = PRDFlow()
    cb = lambda iteration, section_key, agent_results, draft: (AGENT_OPENAI, True)
    flow.approval_callback = cb
    assert flow.approval_callback is cb


def test_prd_flow_approval_callback_accepts_tuple_feedback():
    """Callback returning a (agent, feedback) tuple should be accepted."""
    flow = PRDFlow()
    cb = lambda iteration, section_key, agent_results, draft: (AGENT_OPENAI, "Add more security details")
    flow.approval_callback = cb
    result = flow.approval_callback(
        1, "executive_summary", {AGENT_OPENAI: "# Draft"}, PRDDraft.create_empty(),
    )
    assert isinstance(result, tuple)
    assert result == (AGENT_OPENAI, "Add more security details")


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
    cb = lambda iteration, section_key, agent_results, draft: PAUSE_SENTINEL
    flow.approval_callback = cb
    result = flow.approval_callback(
        1, "executive_summary", {AGENT_OPENAI: "# Draft"}, PRDDraft.create_empty(),
    )
    assert result == PAUSE_SENTINEL


def test_section_approval_loop_raises_pause(monkeypatch):
    """_section_approval_loop should raise PauseRequested when callback returns PAUSE_SENTINEL."""
    import pytest

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-run"
    flow.approval_callback = lambda iteration, key, agent_results, draft, **kwargs: PAUSE_SENTINEL

    section = flow.state.draft.sections[0]
    section.content = "Some draft content"
    section.agent_results = {AGENT_OPENAI: "Some draft content"}
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    with pytest.raises(PauseRequested):
        flow._section_approval_loop(section, agents, {})


@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_finalize_saves_prd(mock_writer_cls, mock_mark_completed, mock_save_output, _mock_get_output):
    """finalize() should persist the assembled PRD via file and mark completed."""
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
    assert "saved" in result.lower()

    # Working ideas should be marked completed
    mock_mark_completed.assert_called_once_with("test-run-123")

    # Output file path should be stored in MongoDB
    mock_save_output.assert_called_once_with(
        "test-run-123", "output/prds/prd_v1.md",
    )

    # State should be flagged as ready
    assert flow.state.is_ready is True


# ── save_progress ────────────────────────────────────────────


@patch("crewai_productfeature_planner.flows.prd_flow.mark_paused")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_save_progress_with_idea_and_requirements(mock_writer_cls, mock_save_output, _mock_get_output, mock_mark_paused):
    """save_progress() should write a progress markdown with refined idea & requirements."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved to output/prds/2026/02/prd_v1.md"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    flow.state.idea = "Refined idea content here"
    flow.state.requirements_breakdown = "Detailed requirements"
    flow.state.requirements_broken_down = True
    flow.state.iteration = 0

    result = flow.save_progress()

    mock_writer._run.assert_called_once()
    call_args = mock_writer._run.call_args
    content = call_args.kwargs.get("content") or call_args[1].get("content")
    assert "In Progress" in content
    assert "# Product Requirements Document" not in content.split("(In Progress)")[0] or "In Progress" in content
    assert "Refined Idea" in content
    assert "Refined idea content here" in content
    assert "Requirements Breakdown" in content
    assert "Detailed requirements" in content
    assert "saved" in result.lower()

    # Output file path stored in MongoDB
    mock_save_output.assert_called_once_with(
        flow.state.run_id, "output/prds/2026/02/prd_v1.md",
    )

    # Working idea status updated to paused
    mock_mark_paused.assert_called_once_with(flow.state.run_id)


@patch("crewai_productfeature_planner.flows.prd_flow.mark_paused")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_save_progress_uses_final_header_when_all_approved(mock_writer_cls, mock_save_output, _mock_get_output, _mock_mark_paused):
    """save_progress() should NOT include '(In Progress)' when all sections are approved."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved to output/prds/2026/02/prd_v10.md"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    flow.state.idea = "Complete idea"
    flow.state.finalized_idea = "Complete finalized idea"
    flow.state.requirements_breakdown = "Requirements"
    flow.state.requirements_broken_down = True
    flow.state.executive_summary = ExecutiveSummaryDraft(
        iterations=[ExecutiveSummaryIteration(content="Exec summary final", iteration=1)],
    )
    flow.state.iteration = 10

    # Approve ALL sections and give them content
    for section in flow.state.draft.sections:
        section.is_approved = True
        section.content = f"Content for {section.title}"

    result = flow.save_progress()

    call_args = mock_writer._run.call_args
    content = call_args.kwargs.get("content") or call_args[1].get("content")
    assert content.startswith("# Product Requirements Document\n\n")
    assert "(In Progress)" not in content


@patch("crewai_productfeature_planner.flows.prd_flow.mark_paused")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_save_progress_includes_executive_summary(mock_writer_cls, mock_save_output, _mock_get_output, _mock_mark_paused):
    """save_progress() should include executive summary if available."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved to output/prds/2026/02/prd_v3.md"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    flow.state.idea = "Some idea"
    flow.state.executive_summary = ExecutiveSummaryDraft(
        iterations=[
            ExecutiveSummaryIteration(content="Exec summary v1", iteration=1),
            ExecutiveSummaryIteration(content="Exec summary v2", iteration=2),
        ],
    )
    flow.state.iteration = 3

    result = flow.save_progress()

    call_args = mock_writer._run.call_args
    content = call_args.kwargs.get("content") or call_args[1].get("content")
    assert "Executive Summary" in content
    assert "Exec summary v2" in content
    assert call_args.kwargs.get("version") == 3 or call_args[1].get("version") == 3


@patch("crewai_productfeature_planner.flows.prd_flow.mark_paused")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_save_progress_includes_drafted_sections(mock_writer_cls, mock_save_output, _mock_get_output, _mock_mark_paused):
    """save_progress() should include any sections that have content."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    flow.state.idea = "Some idea"

    # Fill in a couple of sections
    for section in flow.state.draft.sections:
        if section.key == "problem_statement":
            section.content = "Problem statement content here"
        elif section.key == "user_personas":
            section.content = "User personas content here"

    result = flow.save_progress()

    call_args = mock_writer._run.call_args
    content = call_args.kwargs.get("content") or call_args[1].get("content")
    assert "Problem Statement" in content
    assert "Problem statement content here" in content
    assert "User Personas" in content
    assert "User personas content here" in content


def test_save_progress_returns_empty_when_no_content():
    """save_progress() should return empty string when there is nothing to save."""
    flow = PRDFlow()
    flow.state.idea = ""

    result = flow.save_progress()

    assert result == ""


@patch("crewai_productfeature_planner.flows.prd_flow.mark_paused")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_save_progress_uses_finalized_idea_over_raw(mock_writer_cls, mock_save_output, _mock_get_output, _mock_mark_paused):
    """save_progress() should prefer finalized_idea over raw idea."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.finalized_idea = "Polished finalized idea"

    result = flow.save_progress()

    call_args = mock_writer._run.call_args
    content = call_args.kwargs.get("content") or call_args[1].get("content")
    assert "Polished finalized idea" in content
    assert "Raw idea" not in content


@patch("crewai_productfeature_planner.flows.prd_flow.mark_paused")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_save_progress_version_defaults_to_one(mock_writer_cls, mock_save_output, _mock_get_output, _mock_mark_paused):
    """save_progress() should use version=1 when iteration is 0."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer

    flow = PRDFlow()
    flow.state.idea = "Some idea"
    flow.state.iteration = 0

    flow.save_progress()

    call_args = mock_writer._run.call_args
    version = call_args.kwargs.get("version") or call_args[1].get("version")
    assert version == 1


# ── _persist_output_path cleanup ─────────────────────────────


@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file")
def test_persist_output_path_deletes_previous_file(mock_get_output, mock_save_output, tmp_path):
    """_persist_output_path should delete the old file when a new one is saved."""
    old_file = tmp_path / "old_prd.md"
    old_file.write_text("old content")
    mock_get_output.return_value = str(old_file)

    flow = PRDFlow()
    flow.state.run_id = "run-cleanup"

    new_path = str(tmp_path / "new_prd.md")
    flow._persist_output_path(f"PRD saved to {new_path}")

    assert not old_file.exists(), "Old file should have been deleted"
    mock_save_output.assert_called_once_with("run-cleanup", new_path)


@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file", return_value=None)
def test_persist_output_path_skips_cleanup_when_no_previous(_mock_get_output, mock_save_output):
    """_persist_output_path should not attempt deletion when no previous file exists."""
    flow = PRDFlow()
    flow.state.run_id = "run-new"
    flow._persist_output_path("PRD saved to output/prds/2026/02/prd_v1.md")

    mock_save_output.assert_called_once_with("run-new", "output/prds/2026/02/prd_v1.md")


@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file")
def test_persist_output_path_skips_cleanup_when_same_path(mock_get_output, mock_save_output):
    """_persist_output_path should not delete the file if old and new paths match."""
    mock_get_output.return_value = "output/prds/2026/02/prd_v1.md"

    flow = PRDFlow()
    flow.state.run_id = "run-same"
    flow._persist_output_path("PRD saved to output/prds/2026/02/prd_v1.md")

    # Should still save but not try to delete the same file
    mock_save_output.assert_called_once_with("run-same", "output/prds/2026/02/prd_v1.md")


@patch("crewai_productfeature_planner.flows.prd_flow.save_output_file")
@patch("crewai_productfeature_planner.flows.prd_flow.get_output_file")
def test_persist_output_path_handles_missing_old_file(mock_get_output, mock_save_output, tmp_path):
    """_persist_output_path should not error if the old file doesn't exist on disk."""
    mock_get_output.return_value = str(tmp_path / "already_gone.md")

    flow = PRDFlow()
    flow.state.run_id = "run-gone"

    new_path = str(tmp_path / "new_prd.md")
    flow._persist_output_path(f"PRD saved to {new_path}")

    # Should still succeed
    mock_save_output.assert_called_once_with("run-gone", new_path)


# ── Multi-agent helpers ──────────────────────────────────────


def test_parse_decision_tuple():
    """Tuple decisions should be unpacked as (agent_name, action)."""
    agent, action = PRDFlow._parse_decision(
        (_SECOND_AGENT, True), [AGENT_OPENAI, _SECOND_AGENT],
    )
    assert agent == _SECOND_AGENT
    assert action is True


def test_parse_decision_tuple_feedback():
    """Tuple with feedback string should be returned as-is."""
    agent, action = PRDFlow._parse_decision(
        (AGENT_OPENAI, "Add more details"), [AGENT_OPENAI],
    )
    assert agent == AGENT_OPENAI
    assert action == "Add more details"


def test_parse_decision_legacy_true():
    """Legacy True return should select the DEFAULT_AGENT."""
    with patch("crewai_productfeature_planner.flows.prd_flow.get_default_agent", return_value=AGENT_OPENAI):
        agent, action = PRDFlow._parse_decision(True, [AGENT_OPENAI, _SECOND_AGENT])
    assert agent == AGENT_OPENAI
    assert action is True


def test_parse_decision_legacy_false():
    """Legacy False return should select the DEFAULT_AGENT when available."""
    with patch("crewai_productfeature_planner.flows.prd_flow.get_default_agent", return_value=_SECOND_AGENT):
        agent, action = PRDFlow._parse_decision(False, [_SECOND_AGENT, AGENT_OPENAI])
    assert agent == _SECOND_AGENT
    assert action is False


def test_parse_decision_legacy_prefers_default_agent():
    """Legacy decision should prefer DEFAULT_AGENT over first in available list."""
    with patch("crewai_productfeature_planner.flows.prd_flow.get_default_agent", return_value=_SECOND_AGENT):
        agent, action = PRDFlow._parse_decision(True, [AGENT_OPENAI, _SECOND_AGENT])
    assert agent == _SECOND_AGENT
    assert action is True


def test_parse_decision_legacy_falls_back_when_default_unavailable():
    """Legacy decision should fall back to first available when default not in list."""
    with patch("crewai_productfeature_planner.flows.prd_flow.get_default_agent", return_value=_SECOND_AGENT):
        agent, action = PRDFlow._parse_decision(True, [AGENT_OPENAI])
    assert agent == AGENT_OPENAI
    assert action is True


def test_parse_decision_legacy_string():
    """Legacy string return (feedback) should select the DEFAULT_AGENT."""
    with patch("crewai_productfeature_planner.flows.prd_flow.get_default_agent", return_value=AGENT_OPENAI):
        agent, action = PRDFlow._parse_decision(
            "Needs more detail", [AGENT_OPENAI],
        )
    assert agent == AGENT_OPENAI
    assert action == "Needs more detail"


@patch("crewai_productfeature_planner.flows.prd_flow.create_product_manager")
def test_get_available_agents_gemini_only(mock_create_pm, monkeypatch):
    """Default agent should be Gemini PM."""
    monkeypatch.delenv("DEFAULT_AGENT", raising=False)
    monkeypatch.setenv("DEFAULT_MULTI_AGENTS", "1")
    mock_create_pm.return_value = MagicMock()
    agents = PRDFlow._get_available_agents()
    assert list(agents.keys()) == [AGENT_GEMINI]
    mock_create_pm.assert_called_once()


@patch("crewai_productfeature_planner.flows.prd_flow.create_product_manager")
def test_get_available_agents_openai_explicit(mock_create_pm, monkeypatch):
    """DEFAULT_AGENT=openai should use the OpenAI agent."""
    monkeypatch.setenv("DEFAULT_AGENT", AGENT_OPENAI)
    monkeypatch.setenv("DEFAULT_MULTI_AGENTS", "1")
    mock_create_pm.return_value = MagicMock()
    agents = PRDFlow._get_available_agents()
    assert list(agents.keys()) == [AGENT_OPENAI]
    mock_create_pm.assert_called_once()


@patch("crewai_productfeature_planner.flows.prd_flow.create_product_manager")
def test_get_available_agents_multi_agents_1_limits_to_default(mock_create_pm, monkeypatch):
    """DEFAULT_MULTI_AGENTS=1 should use only the default agent."""
    monkeypatch.delenv("DEFAULT_AGENT", raising=False)
    monkeypatch.setenv("DEFAULT_MULTI_AGENTS", "1")
    mock_create_pm.return_value = MagicMock()
    agents = PRDFlow._get_available_agents()
    assert list(agents.keys()) == [AGENT_GEMINI]


def test_run_agents_parallel_single():
    """Single-agent fast path should return one result."""
    mock_agent = MagicMock()
    mock_result = MagicMock()
    mock_result.raw = "Agent draft content"

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        return_value=mock_result,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        results, failed = PRDFlow._run_agents_parallel(
            agents={AGENT_OPENAI: mock_agent},
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Executive Summary",
            idea="Test idea",
            section_content="",
            executive_summary="",
        )
    assert list(results.keys()) == [AGENT_OPENAI]
    assert results[AGENT_OPENAI] == "Agent draft content"
    assert failed == {}


def test_run_agents_parallel_multi():
    """Multiple agents should run in parallel and return all results."""
    mock_result_openai = MagicMock()
    mock_result_openai.raw = "OpenAI result"
    mock_result_second = MagicMock()
    mock_result_second.raw = "Second agent result"

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        return mock_result_openai if "openai" in step_label else mock_result_second

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        results, failed = PRDFlow._run_agents_parallel(
            agents={AGENT_OPENAI: MagicMock(), _SECOND_AGENT: MagicMock()},
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            section_content="",
            executive_summary="",
        )
    assert AGENT_OPENAI in results
    assert _SECOND_AGENT in results
    assert call_count == 2
    assert failed == {}


def test_run_agents_parallel_one_fails():
    """If one agent fails, the other should still succeed."""
    mock_result = MagicMock()
    mock_result.raw = "Survivor result"

    def mock_kickoff(crew, step_label=""):
        if "second" in step_label:
            raise RuntimeError("Second agent exploded")
        return mock_result

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        results, failed = PRDFlow._run_agents_parallel(
            agents={AGENT_OPENAI: MagicMock(), _SECOND_AGENT: MagicMock()},
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            section_content="",
            executive_summary="",
        )
    assert AGENT_OPENAI in results
    assert _SECOND_AGENT not in results
    assert _SECOND_AGENT in failed
    assert "Second agent exploded" in failed[_SECOND_AGENT]


def test_run_agents_parallel_all_fail():
    """If ALL agents fail, RuntimeError should be raised."""
    import pytest

    def mock_kickoff(crew, step_label=""):
        raise RuntimeError("boom")

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        with pytest.raises(RuntimeError, match="All agents failed"):
            PRDFlow._run_agents_parallel(
                agents={AGENT_OPENAI: MagicMock(), _SECOND_AGENT: MagicMock()},
                task_configs={
                    "draft_section_task": {
                        "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                        "expected_output": "A {section_title} section",
                    },
                },
                section_title="Problem Statement",
                idea="Test idea",
                section_content="",
                executive_summary="",
            )


def test_run_agents_parallel_reorders_default_first(monkeypatch):
    """Results dict should have the DEFAULT_AGENT first regardless of completion order."""
    mock_result_openai = MagicMock()
    mock_result_openai.raw = "OpenAI result"
    mock_result_second = MagicMock()
    mock_result_second.raw = "Second agent result"

    def mock_kickoff(crew, step_label=""):
        return mock_result_openai if "openai" in step_label else mock_result_second

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.get_default_agent",
        return_value=_SECOND_AGENT,
    ), patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        results, failed = PRDFlow._run_agents_parallel(
            agents={AGENT_OPENAI: MagicMock(), _SECOND_AGENT: MagicMock()},
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            section_content="",
            executive_summary="",
        )
    # DEFAULT_AGENT=second_pm should be first key
    assert list(results.keys())[0] == _SECOND_AGENT
    assert failed == {}


def test_failed_optional_agent_dropped_for_remaining_sections():
    """When an optional agent fails, it should be removed for subsequent sections."""
    mock_result = MagicMock()
    mock_result.raw = "Default agent result"

    call_log = []

    def mock_kickoff(crew, step_label=""):
        call_log.append(step_label)
        if "second" in step_label:
            raise RuntimeError("Second agent unavailable")
        return mock_result

    agents = {AGENT_OPENAI: MagicMock(), _SECOND_AGENT: MagicMock()}

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        # First call — second agent fails
        results, failed = PRDFlow._run_agents_parallel(
            agents=agents,
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Executive Summary",
            idea="Test idea",
            section_content="",
            executive_summary="",
        )
        assert _SECOND_AGENT in failed
        assert "Second agent unavailable" in failed[_SECOND_AGENT]
        assert AGENT_OPENAI in results

        # Simulate generate_sections removing the failed agent
        for name in list(failed):
            if name in agents:
                del agents[name]

        assert _SECOND_AGENT not in agents
        assert len(agents) == 1

        # Second call — should only use the default agent
        call_log.clear()
        results2, failed2 = PRDFlow._run_agents_parallel(
            agents=agents,
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} content: {section_content} exec: {executive_summary}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            section_content="",
            executive_summary="",
        )
        assert failed2 == {}
        assert AGENT_OPENAI in results2
        # Second agent should not have been called
        assert not any("second" in label for label in call_log)


def test_prd_state_tracks_agent_changes():
    """PRDState should track active_agents, dropped_agents, and agent_errors."""
    flow = PRDFlow()
    # Initially empty
    assert flow.state.active_agents == []
    assert flow.state.dropped_agents == []
    assert flow.state.agent_errors == {}

    # Set active agents
    flow.state.active_agents = [AGENT_OPENAI, _SECOND_AGENT]
    assert flow.state.active_agents == [AGENT_OPENAI, _SECOND_AGENT]

    # Drop an agent with error
    flow.state.dropped_agents.append(_SECOND_AGENT)
    flow.state.agent_errors[_SECOND_AGENT] = "RuntimeError: model not found"
    flow.state.active_agents = [AGENT_OPENAI]
    assert flow.state.active_agents == [AGENT_OPENAI]
    assert flow.state.dropped_agents == [_SECOND_AGENT]
    assert flow.state.agent_errors == {_SECOND_AGENT: "RuntimeError: model not found"}


def test_callback_receives_agent_kwargs():
    """The approval callback should receive active_agents, dropped_agents, and agent_errors kwargs."""
    received_kwargs = {}

    def _cb(iteration, key, agent_results, draft, **kwargs):
        received_kwargs.update(kwargs)
        return (AGENT_OPENAI, True)

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-kwargs"
    flow.state.active_agents = [AGENT_OPENAI]
    flow.state.dropped_agents = [_SECOND_AGENT]
    flow.state.agent_errors = {_SECOND_AGENT: "RuntimeError: boom"}
    flow.approval_callback = _cb

    section = flow.state.draft.sections[0]
    section.content = "Draft content"
    section.agent_results = {AGENT_OPENAI: "Draft content"}
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    flow._section_approval_loop(section, agents, {})

    assert received_kwargs.get("active_agents") == [AGENT_OPENAI]
    assert received_kwargs.get("dropped_agents") == [_SECOND_AGENT]
    assert received_kwargs.get("agent_errors") == {_SECOND_AGENT: "RuntimeError: boom"}


def test_section_agent_results_after_approval():
    """After approval with a specific agent, section should have correct selected_agent."""
    flow = PRDFlow()
    section = flow.state.draft.sections[0]
    section.content = "OpenAI draft"
    section.agent_results = {
        AGENT_OPENAI: "OpenAI draft",
        _SECOND_AGENT: "Second agent draft",
    }
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    flow.approval_callback = lambda iteration, key, agent_results, draft, **kwargs: (_SECOND_AGENT, True)

    agents = {AGENT_OPENAI: MagicMock(), _SECOND_AGENT: MagicMock()}
    flow._section_approval_loop(section, agents, {})

    assert section.is_approved is True
    assert section.selected_agent == _SECOND_AGENT
    assert section.content == "Second agent draft"


# ── get_default_agent() ──────────────────────────────────────────


def test_get_default_agent_unset(monkeypatch):
    """Without DEFAULT_AGENT env var, should return gemini."""
    monkeypatch.delenv("DEFAULT_AGENT", raising=False)
    assert get_default_agent() == AGENT_GEMINI


def test_get_default_agent_openai(monkeypatch):
    """DEFAULT_AGENT=openai should return openai."""
    monkeypatch.setenv("DEFAULT_AGENT", AGENT_OPENAI)
    assert get_default_agent() == AGENT_OPENAI


def test_get_default_agent_gemini(monkeypatch):
    """DEFAULT_AGENT=gemini should return gemini."""
    monkeypatch.setenv("DEFAULT_AGENT", AGENT_GEMINI)
    assert get_default_agent() == AGENT_GEMINI


def test_get_default_agent_invalid(monkeypatch):
    """Invalid DEFAULT_AGENT value should fall back to gemini."""
    monkeypatch.setenv("DEFAULT_AGENT", "invalid_agent")
    assert get_default_agent() == DEFAULT_AGENT_FALLBACK


def test_valid_agents_contains_both():
    """VALID_AGENTS should list both known agents."""
    assert AGENT_OPENAI in VALID_AGENTS
    assert AGENT_GEMINI in VALID_AGENTS


# ── _maybe_refine_idea integration ───────────────────────────


def test_maybe_refine_idea_skips_without_credentials(monkeypatch):
    """Refinement should be skipped when no Gemini credentials are set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow._maybe_refine_idea()
    assert flow.state.idea == "Raw idea"
    assert flow.state.idea_refined is False
    assert flow.state.original_idea == ""


def test_maybe_refine_idea_runs_with_credentials(monkeypatch):
    """Refinement should run and update the idea when Gemini key is set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    flow = PRDFlow()
    flow.state.idea = "Raw idea"

    with patch(
        "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
        return_value=("Enriched idea with details", [{"iteration": 1, "idea": "Enriched idea with details", "evaluation": "IDEA_READY"}]),
    ):
        flow._maybe_refine_idea()

    assert flow.state.idea == "Enriched idea with details"
    assert flow.state.original_idea == "Raw idea"
    assert flow.state.idea_refined is True
    assert len(flow.state.refinement_history) == 1
    assert flow.state.refinement_history[0]["iteration"] == 1


def test_maybe_refine_idea_skips_when_already_refined(monkeypatch):
    """Should not refine again if idea_refined is already True."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    flow = PRDFlow()
    flow.state.idea = "Already refined idea"
    flow.state.idea_refined = True
    flow._maybe_refine_idea()
    assert flow.state.idea == "Already refined idea"


def test_maybe_refine_idea_continues_on_failure(monkeypatch):
    """If the refiner fails, the original idea should be kept."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    flow = PRDFlow()
    flow.state.idea = "Raw idea"

    with patch(
        "crewai_productfeature_planner.agents.idea_refiner.refine_idea",
        side_effect=RuntimeError("Gemini API error"),
    ):
        flow._maybe_refine_idea()

    assert flow.state.idea == "Raw idea"
    assert flow.state.idea_refined is False


def test_prd_state_refinement_fields():
    """PRDState should initialise refinement fields properly."""
    state = PRDState()
    assert state.original_idea == ""
    assert state.idea_refined is False
    assert state.refinement_history == []


# ── IdeaFinalized & idea_approval_callback ───────────────────


def test_idea_finalized_exception_importable():
    """IdeaFinalized exception should be importable from the flow module."""
    from crewai_productfeature_planner.flows.prd_flow import IdeaFinalized
    assert issubclass(IdeaFinalized, Exception)


def test_idea_approval_callback_defaults_to_none():
    """PRDFlow should have idea_approval_callback=None by default."""
    flow = PRDFlow()
    assert flow.idea_approval_callback is None


def test_idea_approval_callback_finalize_raises(monkeypatch):
    """When idea_approval_callback returns True, IdeaFinalized should be raised."""
    from crewai_productfeature_planner.flows.prd_flow import IdeaFinalized

    # Ensure no Gemini credentials — stages skip based on state flags
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.idea_refined = True
    flow.state.original_idea = "Raw idea"

    flow.idea_approval_callback = lambda refined, original, run_id, history: True

    import pytest
    with pytest.raises(IdeaFinalized):
        flow.generate_sections()


def test_idea_approval_callback_continue_does_not_raise(monkeypatch):
    """When idea_approval_callback returns False, PRD generation should proceed."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.idea_refined = True
    flow.state.original_idea = "Raw idea"

    callback_called = False

    def cb(refined, original, run_id, history):
        nonlocal callback_called
        callback_called = True
        return False  # continue to PRD

    flow.idea_approval_callback = cb

    # Mock _get_available_agents to avoid real LLM creation
    monkeypatch.setattr(
        PRDFlow, "_get_available_agents",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("stop here"))),
    )

    # generate_sections will proceed past the callback but fail on agents
    with pytest.raises(RuntimeError, match="stop here"):
        flow.generate_sections()

    assert callback_called is True


def test_idea_approval_callback_skipped_when_not_refined(monkeypatch):
    """Callback should not be called if idea was not refined."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.idea_refined = False  # not refined

    callback_called = False

    def cb(refined, original, run_id, history):
        nonlocal callback_called
        callback_called = True
        return True

    flow.idea_approval_callback = cb

    monkeypatch.setattr(
        PRDFlow, "_get_available_agents",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("stop here"))),
    )

    with pytest.raises(RuntimeError, match="stop here"):
        flow.generate_sections()

    assert callback_called is False


def test_idea_approval_callback_skipped_when_none(monkeypatch):
    """No callback set should proceed without error."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.idea_refined = True
    flow.state.original_idea = "Raw idea"
    flow.idea_approval_callback = None

    monkeypatch.setattr(
        PRDFlow, "_get_available_agents",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("stop here"))),
    )

    # Should proceed past the approval gate without IdeaFinalized
    with pytest.raises(RuntimeError, match="stop here"):
        flow.generate_sections()


# ── RequirementsFinalized & requirements_approval_callback ───


def test_requirements_finalized_exception_importable():
    """RequirementsFinalized exception should be importable."""
    from crewai_productfeature_planner.flows.prd_flow import RequirementsFinalized
    assert issubclass(RequirementsFinalized, Exception)


def test_requirements_approval_callback_defaults_to_none():
    """PRDFlow should have requirements_approval_callback=None by default."""
    flow = PRDFlow()
    assert flow.requirements_approval_callback is None


def test_prd_state_requirements_fields():
    """PRDState should initialise requirements breakdown fields properly."""
    state = PRDState()
    assert state.requirements_breakdown == ""
    assert state.breakdown_history == []
    assert state.requirements_broken_down is False


def test_maybe_breakdown_requirements_skips_without_credentials(monkeypatch):
    """Should skip breakdown when no Google credentials are set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow._maybe_breakdown_requirements()
    assert flow.state.requirements_broken_down is False


def test_maybe_breakdown_requirements_runs_with_credentials(monkeypatch):
    """Should run breakdown when credentials are present."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    flow = PRDFlow()
    flow.state.idea = "Test idea"

    with patch(
        "crewai_productfeature_planner.agents.requirements_breakdown.breakdown_requirements",
        return_value=("## Feature 1\nDetailed reqs", [{"iteration": 1}]),
    ):
        flow._maybe_breakdown_requirements()

    assert flow.state.requirements_broken_down is True
    assert "Feature 1" in flow.state.requirements_breakdown
    assert len(flow.state.breakdown_history) == 1


def test_maybe_breakdown_requirements_skips_when_already_done(monkeypatch):
    """Should not breakdown again if already done."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.requirements_broken_down = True

    flow._maybe_breakdown_requirements()
    # Should not have changed anything
    assert flow.state.requirements_breakdown == ""


def test_maybe_breakdown_requirements_continues_on_failure(monkeypatch):
    """Should continue without requirements if breakdown fails."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    flow = PRDFlow()
    flow.state.idea = "Test idea"

    with patch(
        "crewai_productfeature_planner.agents.requirements_breakdown.breakdown_requirements",
        side_effect=RuntimeError("LLM unavailable"),
    ):
        flow._maybe_breakdown_requirements()

    assert flow.state.requirements_broken_down is False
    assert flow.state.requirements_breakdown == ""


def test_requirements_approval_callback_finalize_raises(monkeypatch):
    """When requirements_approval_callback returns True, RequirementsFinalized should be raised."""
    from crewai_productfeature_planner.flows.prd_flow import RequirementsFinalized

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.idea_refined = True
    flow.state.original_idea = "Raw idea"
    flow.state.requirements_broken_down = True
    flow.state.requirements_breakdown = "## Feature 1"

    flow.idea_approval_callback = lambda refined, original, run_id, history: False
    flow.requirements_approval_callback = lambda reqs, idea, run_id, history: True

    with pytest.raises(RequirementsFinalized):
        flow.generate_sections()


def test_requirements_approval_callback_continue_proceeds(monkeypatch):
    """When requirements_approval_callback returns False, PRD generation should proceed."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.idea_refined = True
    flow.state.original_idea = "Raw idea"
    flow.state.requirements_broken_down = True
    flow.state.requirements_breakdown = "## Feature 1"

    callback_called = False

    def req_cb(reqs, idea, run_id, history):
        nonlocal callback_called
        callback_called = True
        return False

    flow.idea_approval_callback = lambda refined, original, run_id, history: False
    flow.requirements_approval_callback = req_cb

    monkeypatch.setattr(
        PRDFlow, "_get_available_agents",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("stop here"))),
    )

    with pytest.raises(RuntimeError, match="stop here"):
        flow.generate_sections()

    assert callback_called is True


def test_requirements_callback_skipped_when_not_broken_down(monkeypatch):
    """Callback should not be called if requirements were not broken down."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    flow = PRDFlow()
    flow.state.idea = "Raw idea"
    flow.state.requirements_broken_down = False

    callback_called = False

    def req_cb(reqs, idea, run_id, history):
        nonlocal callback_called
        callback_called = True
        return True

    flow.requirements_approval_callback = req_cb

    monkeypatch.setattr(
        PRDFlow, "_get_available_agents",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("stop here"))),
    )

    with pytest.raises(RuntimeError, match="stop here"):
        flow.generate_sections()

    assert callback_called is False


# ── _get_section_iteration_limits ────────────────────────────


def test_section_iteration_limits_defaults(monkeypatch):
    """Defaults should be 2/5 when env vars are unset."""
    monkeypatch.delenv("PRD_SECTION_MIN_ITERATIONS", raising=False)
    monkeypatch.delenv("PRD_SECTION_MAX_ITERATIONS", raising=False)
    min_iter, max_iter = _get_section_iteration_limits()
    assert min_iter == DEFAULT_MIN_SECTION_ITERATIONS
    assert max_iter == DEFAULT_MAX_SECTION_ITERATIONS


def test_section_iteration_limits_from_env(monkeypatch):
    """Env vars should override defaults."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "8")
    min_iter, max_iter = _get_section_iteration_limits()
    assert min_iter == 3
    assert max_iter == 8


def test_section_iteration_limits_clamp_min_floor(monkeypatch):
    """min_iterations should be clamped to at least 1."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "0")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")
    min_iter, max_iter = _get_section_iteration_limits()
    assert min_iter == 1
    assert max_iter == 5


def test_section_iteration_limits_clamp_max_floor(monkeypatch):
    """max_iterations should be at least min_iterations."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "4")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "2")
    min_iter, max_iter = _get_section_iteration_limits()
    assert min_iter == 4
    assert max_iter == 4


def test_section_iteration_limits_clamp_ceiling(monkeypatch):
    """min capped at 10, max capped at 20."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "15")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "30")
    min_iter, max_iter = _get_section_iteration_limits()
    assert min_iter == 10
    assert max_iter == 20


def test_default_constants():
    """Module constants should have the expected values."""
    assert DEFAULT_MIN_SECTION_ITERATIONS == 2
    assert DEFAULT_MAX_SECTION_ITERATIONS == 10


# ── min/max iteration enforcement in _section_approval_loop ──


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_section_iterates_min_before_auto_approve(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Even when critique says SECTION_READY, loop must iterate min times."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")

    # Always return SECTION_READY critique and refined content
    call_count = {"critique": 0, "refine": 0}

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            call_count["critique"] += 1
            result.raw = "Score 9/10 — SECTION_READY"
        else:
            call_count["refine"] += 1
            result.raw = f"Refined content v{call_count['refine'] + 1}"
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-min-iter"
    # No approval_callback → auto mode

    section = flow.state.draft.sections[0]
    section.content = "Initial draft"
    section.agent_results = {AGENT_OPENAI: "Initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    # Must iterate at least min (3) — approve at iteration 3 (past_min + SECTION_READY)
    assert section.is_approved is True
    assert section.iteration >= 3
    # Critique called for each iteration (1, 2, 3), refine for iterations before approval
    assert call_count["critique"] >= 2  # at least iterations 1 and 2 critiqued + refine


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_section_force_approved_at_max(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Section should be force-approved when max iterations reached."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "2")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "3")

    # Always return NEEDS_REFINEMENT
    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            result.raw = "Score 4/10 — NEEDS_REFINEMENT"
        else:
            result.raw = "Refined content"
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-max-iter"

    section = flow.state.draft.sections[0]
    section.content = "Initial draft"
    section.agent_results = {AGENT_OPENAI: "Initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    assert section.is_approved is True
    # Section was force-approved at max=3
    assert section.iteration == 3


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_section_ready_before_min_keeps_iterating(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """SECTION_READY before min iterations should NOT auto-approve."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")

    iteration_tracker = {"current": 1}

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            # Always SECTION_READY
            result.raw = "SECTION_READY — looks great"
        else:
            iteration_tracker["current"] += 1
            result.raw = f"Refined v{iteration_tracker['current']}"
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-ready-before-min"

    section = flow.state.draft.sections[0]
    section.content = "Initial draft"
    section.agent_results = {AGENT_OPENAI: "Initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    assert section.is_approved is True
    # Even though SECTION_READY was returned at iteration 1 and 2,
    # the section should only be approved at iteration >= 3 (min)
    assert section.iteration >= 3


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_section_saves_each_iteration_to_db(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Each refine cycle should call save_iteration with correct iteration number."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "2")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "3")

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            result.raw = "NEEDS_REFINEMENT — more detail needed"
        else:
            result.raw = "Refined content"
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-save-iters"

    section = flow.state.draft.sections[0]
    section.content = "Initial draft"
    section.agent_results = {AGENT_OPENAI: "Initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    # save_iteration called for each refine (iter 2 and 3 at max=3 force-approve at iter 3)
    # iter 1 → critique → refine → save(iter=2)
    # iter 2 → critique → refine → save(iter=3)
    # iter 3 → critique → at_max → approve
    assert mock_save.call_count == 2
    # Verify iteration numbers in calls
    saved_iters = [call.kwargs.get("iteration") or call[1].get("iteration", None)
                   for call in mock_save.call_args_list]
    assert 2 in saved_iters
    assert 3 in saved_iters


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_section_critique_updates_each_iteration(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """update_section_critique should be called for every iteration."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "2")

    call_idx = {"n": 0}

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        call_idx["n"] += 1
        if "critique" in step_label:
            if call_idx["n"] <= 2:
                result.raw = "NEEDS_REFINEMENT"
            else:
                result.raw = "SECTION_READY"
        else:
            result.raw = "Refined"
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test"
    flow.state.run_id = "test-crit-update"

    section = flow.state.draft.sections[0]
    section.content = "Draft"
    section.agent_results = {AGENT_OPENAI: "Draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    # update_section_critique called at each critique step
    assert mock_update_crit.call_count >= 2


def test_user_callback_can_approve_before_min(monkeypatch):
    """User approval via callback should override min iteration gate."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "5")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "10")

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-user-override"
    flow.approval_callback = (
        lambda iteration, key, agent_results, draft, **kwargs:
        (AGENT_OPENAI, True)
    )

    section = flow.state.draft.sections[0]
    section.content = "Draft content"
    section.agent_results = {AGENT_OPENAI: "Draft content"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1  # well below min=5

    agents = {AGENT_OPENAI: MagicMock()}
    flow._section_approval_loop(section, agents, {})

    # User approved at iteration 1, even though min=5
    assert section.is_approved is True
    assert section.iteration == 1


# ── _is_degenerate_content unit tests ────────────────────────


def test_is_degenerate_content_exceeds_max(monkeypatch):
    """Text exceeding PRD_SECTION_MAX_CHARS should be flagged."""
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "100")
    assert _is_degenerate_content("x" * 101) is True
    assert _is_degenerate_content("x" * 100) is False


def test_is_degenerate_content_exceeds_growth(monkeypatch):
    """Text exceeding growth factor relative to prev_len should be flagged."""
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "999999")
    monkeypatch.setenv("PRD_SECTION_GROWTH_FACTOR", "3.0")
    # 301 > 100 * 3.0
    assert _is_degenerate_content("y" * 301, prev_len=100) is True
    # 299 <= 100 * 3.0
    assert _is_degenerate_content("y" * 299, prev_len=100) is False


def test_is_degenerate_content_no_prev_len(monkeypatch):
    """Without prev_len, growth factor should not trigger."""
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "999999")
    monkeypatch.setenv("PRD_SECTION_GROWTH_FACTOR", "2.0")
    # Large text but under max_chars, and prev_len=0 → not degenerate
    assert _is_degenerate_content("z" * 5000) is False


# ── degenerate output guard in _section_approval_loop ────────


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_degenerate_output_exceeds_max_chars(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Refine output exceeding PRD_SECTION_MAX_CHARS should be reverted."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "5000")

    call_count = {"n": 0}

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        call_count["n"] += 1
        if "critique" in step_label:
            result.raw = "Needs work — continue iterating"
        else:
            # Return degenerate output on first refine
            result.raw = "of" * 50000  # 100,000 chars
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-degen-max"

    section = flow.state.draft.sections[1]  # problem_statement
    section.content = "Good initial draft content"
    section.agent_results = {AGENT_OPENAI: "Good initial draft content"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    # Should revert to original content and force-approve
    assert section.is_approved is True
    assert section.content == "Good initial draft content"


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_degenerate_output_exceeds_growth_factor(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Refine output exceeding growth factor should be reverted."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "999999")  # high cap
    monkeypatch.setenv("PRD_SECTION_GROWTH_FACTOR", "3.0")

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            result.raw = "Needs work — continue"
        else:
            result.raw = "X" * 10000  # 10x the 1000-char original → exceeds 3.0 factor
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-degen-growth"

    section = flow.state.draft.sections[1]
    section.content = "A" * 1000
    section.agent_results = {AGENT_OPENAI: "A" * 1000}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    assert section.is_approved is True
    assert section.content == "A" * 1000  # reverted to original


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_degenerate_refine_retries_below_min_iter(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Degenerate refine at iteration < min_iter must retry, not force-approve."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "5000")

    refine_call = {"n": 0}

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            result.raw = "Needs work — continue iterating"
        else:
            refine_call["n"] += 1
            if refine_call["n"] <= 2:
                # First two refines produce degenerate output (iterations 1 & 2)
                result.raw = "X" * 50000
            else:
                # Third refine produces good output
                result.raw = "Good refined content"
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-degen-retry"

    section = flow.state.draft.sections[1]  # problem_statement
    section.content = "Good initial draft"
    section.agent_results = {AGENT_OPENAI: "Good initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    # Should NOT force-approve at iteration 1 or 2 (below min=3).
    # Degenerate outputs at iterations 1 & 2 reverted, then good output at iteration 3.
    assert section.is_approved is True
    assert section.content == "Good refined content"
    assert section.iteration >= 3  # reached min_iter before approval


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_degenerate_refine_force_approves_at_min_iter(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Degenerate refine at iteration >= min_iter should force-approve."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "2")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "5000")

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            result.raw = "Needs work — continue iterating"
        else:
            # Always produce degenerate output
            result.raw = "X" * 50000
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-degen-pastmin"

    section = flow.state.draft.sections[1]  # problem_statement
    section.content = "Good initial draft"
    section.agent_results = {AGENT_OPENAI: "Good initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 2  # already at min_iter

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    # At iteration=2, min=2 → past_min → should force-approve
    assert section.is_approved is True
    assert section.content == "Good initial draft"  # reverted


@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_normal_output_not_flagged_as_degenerate(
    _mock_task, _mock_crew, mock_kickoff, mock_save, mock_update_crit,
    monkeypatch,
):
    """Normal-length refine output should NOT be reverted."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "2")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "30000")
    monkeypatch.setenv("PRD_SECTION_GROWTH_FACTOR", "5.0")

    iteration = {"n": 0}

    def _kickoff(crew, step_label=""):
        result = MagicMock()
        if "critique" in step_label:
            iteration["n"] += 1
            if iteration["n"] >= 2:
                result.raw = "Score 10/10 — SECTION_READY"
            else:
                result.raw = "Needs a little polish"
        else:
            result.raw = "Nicely refined content here"  # reasonable length
        return result

    mock_kickoff.side_effect = _kickoff

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-normal"

    section = flow.state.draft.sections[1]
    section.content = "Initial draft"
    section.agent_results = {AGENT_OPENAI: "Initial draft"}
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "critique_section_task": {
            "description": "Critique {section_title}: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "A critique",
        },
        "refine_section_task": {
            "description": "Refine {section_title}: {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow._section_approval_loop(section, agents, task_configs)

    assert section.is_approved is True
    assert section.content == "Nicely refined content here"  # NOT reverted


# ══════════════════════════════════════════════════════════════
# Executive Summary — model tests
# ══════════════════════════════════════════════════════════════


def test_executive_summary_iteration_defaults():
    """ExecutiveSummaryIteration should initialise with sensible defaults."""
    it = ExecutiveSummaryIteration()
    assert it.content == ""
    assert it.iteration == 1
    assert it.critique is None
    assert it.updated_date == ""


def test_executive_summary_draft_empty():
    """Empty ExecutiveSummaryDraft properties should return safe defaults."""
    draft = ExecutiveSummaryDraft()
    assert draft.latest is None
    assert draft.latest_content == ""
    assert draft.current_iteration == 0
    assert draft.is_approved is False
    assert draft.iterations == []


def test_executive_summary_draft_latest():
    """latest / latest_content / current_iteration should track last entry."""
    draft = ExecutiveSummaryDraft(
        iterations=[
            ExecutiveSummaryIteration(content="v1", iteration=1),
            ExecutiveSummaryIteration(content="v2", iteration=2, critique="ok"),
        ],
    )
    assert draft.latest is not None
    assert draft.latest.iteration == 2
    assert draft.latest_content == "v2"
    assert draft.current_iteration == 2


def test_prd_state_has_executive_summary():
    """PRDState should include an executive_summary field by default."""
    state = PRDState()
    assert isinstance(state.executive_summary, ExecutiveSummaryDraft)
    assert state.executive_summary.iterations == []


# ══════════════════════════════════════════════════════════════
# ExecutiveSummaryCompleted exception
# ══════════════════════════════════════════════════════════════


def test_executive_summary_completed_is_exception():
    """ExecutiveSummaryCompleted should be a regular Exception subclass."""
    exc = ExecutiveSummaryCompleted()
    assert isinstance(exc, Exception)


def test_executive_summary_completed_can_carry_message():
    """ExecutiveSummaryCompleted should optionally carry a message."""
    exc = ExecutiveSummaryCompleted("User stopped")
    assert str(exc) == "User stopped"


# ══════════════════════════════════════════════════════════════
# executive_summary_callback attribute
# ══════════════════════════════════════════════════════════════


def test_executive_summary_callback_defaults_to_none():
    """PRDFlow.executive_summary_callback should default to None."""
    flow = PRDFlow()
    assert flow.executive_summary_callback is None


# ══════════════════════════════════════════════════════════════
# _iterate_executive_summary tests
# ══════════════════════════════════════════════════════════════


@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_iterate_exec_summary_ready_at_min(_mock_task, _mock_crew, mock_kickoff, mock_update_crit, mock_save, mock_save_fin, monkeypatch):
    """Executive summary should approve when READY_FOR_DEV at min iteration."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "2")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")

    # Iteration 1 → initial draft
    # Iteration 1 critique → needs work
    # Iteration 2 → refined draft
    # Iteration 2 critique → READY_FOR_DEV
    mock_kickoff.side_effect = [
        MagicMock(raw="Initial executive summary"),   # draft iter 1
        MagicMock(raw="NEEDS_REVISION: improve scope"),  # critique iter 1
        MagicMock(raw="Refined executive summary"),   # refine iter 2
        MagicMock(raw="READY_FOR_DEV: looks great"),  # critique iter 2
    ]

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-exec-1"
    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "draft_prd_task": {
            "description": "Draft for {idea}. Summary: {executive_summary}",
            "expected_output": "Executive summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique}. Summary: {executive_summary}",
            "expected_output": "Critique",
        },
    }

    flow._iterate_executive_summary(agents, task_configs)

    assert flow.state.executive_summary.is_approved is True
    assert len(flow.state.executive_summary.iterations) == 2
    assert flow.state.executive_summary.iterations[0].content == "Initial executive summary"
    assert flow.state.executive_summary.iterations[1].content == "Refined executive summary"
    assert mock_save.call_count == 2   # once per iteration
    assert mock_update_crit.call_count == 2  # critique for iter 1 and iter 2
    assert flow.state.finalized_idea == "Refined executive summary"
    mock_save_fin.assert_called_once()


@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_iterate_exec_summary_force_approve_at_max(_mock_task, _mock_crew, mock_kickoff, mock_update_crit, mock_save, mock_save_fin, monkeypatch):
    """Executive summary should force-approve when max iterations reached."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "2")

    # Iteration 1 → initial draft
    # Iteration 1 critique → needs work
    # Iteration 2 → refined draft
    # Iteration 2 critique → needs work (still not ready)
    # max=2 reached → force-approve
    mock_kickoff.side_effect = [
        MagicMock(raw="Draft v1"),
        MagicMock(raw="NEEDS_REVISION: still issues"),
        MagicMock(raw="Draft v2"),
        MagicMock(raw="NEEDS_REVISION: more issues"),
    ]

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-exec-max"
    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
    }

    flow._iterate_executive_summary(agents, task_configs)

    assert flow.state.executive_summary.is_approved is True
    assert len(flow.state.executive_summary.iterations) == 2
    assert flow.state.finalized_idea == "Draft v2"
    mock_save_fin.assert_called_once()


@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_iterate_exec_summary_ready_before_min_continues(_mock_task, _mock_crew, mock_kickoff, mock_update_crit, mock_save, mock_save_fin, monkeypatch):
    """READY_FOR_DEV before min iterations should keep iterating."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "5")

    mock_kickoff.side_effect = [
        MagicMock(raw="Draft v1"),                     # draft iter 1
        MagicMock(raw="READY_FOR_DEV: looks great"),   # critique iter 1 — ready but min=3
        MagicMock(raw="Draft v2"),                     # refine iter 2
        MagicMock(raw="READY_FOR_DEV: still good"),    # critique iter 2 — ready but min=3
        MagicMock(raw="Draft v3"),                     # refine iter 3
        MagicMock(raw="READY_FOR_DEV: finalized"),     # critique iter 3 — ready AND past_min
    ]

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-exec-min"
    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
    }

    flow._iterate_executive_summary(agents, task_configs)

    assert flow.state.executive_summary.is_approved is True
    # Should have 3 iterations (kept going past READY_FOR_DEV until min met)
    assert len(flow.state.executive_summary.iterations) == 3
    assert flow.state.executive_summary.current_iteration == 3


@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
def test_iterate_exec_summary_critique_text_persisted(_mock_task, _mock_crew, mock_kickoff, mock_update_crit, mock_save, mock_save_fin, monkeypatch):
    """Critique text should be stored on the iteration record."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "2")

    mock_kickoff.side_effect = [
        MagicMock(raw="Initial draft"),
        MagicMock(raw="READY_FOR_DEV: approved"),
    ]

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.state.run_id = "test-crit-store"
    agents = {AGENT_OPENAI: MagicMock()}
    task_configs = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
    }

    flow._iterate_executive_summary(agents, task_configs)

    # The critique should be on the first (and only) iteration
    assert flow.state.executive_summary.iterations[0].critique == "READY_FOR_DEV: approved"
    assert flow.state.critique == "READY_FOR_DEV: approved"
    mock_update_crit.assert_called_once()


# ══════════════════════════════════════════════════════════════
# generate_sections — executive_summary_callback gate tests
# ══════════════════════════════════════════════════════════════


@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
@patch.object(PRDFlow, "_get_available_agents")
@patch("crewai_productfeature_planner.flows.prd_flow.get_task_configs")
@patch("crewai_productfeature_planner.orchestrator.build_default_pipeline")
def test_callback_false_raises_completed(
    mock_pipeline, mock_task_configs, mock_agents, _mock_task, _mock_crew,
    mock_kickoff, mock_update_crit, mock_save, mock_save_fin, monkeypatch,
):
    """executive_summary_callback returning False should raise ExecutiveSummaryCompleted."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "1")

    mock_agents.return_value = {AGENT_OPENAI: MagicMock()}
    mock_task_configs.return_value = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
    }
    mock_kickoff.side_effect = [
        MagicMock(raw="Exec summary"),
        MagicMock(raw="READY_FOR_DEV: done"),
    ]

    flow = PRDFlow()
    flow.state.idea = "Test"
    flow.executive_summary_callback = lambda content, idea, run_id, iters: False

    with pytest.raises(ExecutiveSummaryCompleted):
        flow.generate_sections()


@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
@patch.object(PRDFlow, "_get_available_agents")
@patch("crewai_productfeature_planner.flows.prd_flow.get_task_configs")
@patch("crewai_productfeature_planner.orchestrator.build_default_pipeline")
def test_callback_true_continues_to_sections(
    mock_pipeline, mock_task_configs, mock_agents, _mock_task, _mock_crew,
    mock_kickoff, mock_update_crit, mock_save, mock_save_fin,
    mock_save_iter, mock_update_sec_crit,
    mock_mark_completed, mock_writer_cls, monkeypatch,
):
    """executive_summary_callback returning True should continue to Phase 2 sections."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "1")

    mock_agents.return_value = {AGENT_OPENAI: MagicMock()}
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved to output/prds/prd_v1.md"
    mock_writer_cls.return_value = mock_writer
    mock_task_configs.return_value = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
        "draft_section_task": {
            "description": "Section: {section_title} {idea} content: {section_content} exec: {executive_summary}",
            "expected_output": "Draft {section_title}",
        },
        "critique_section_task": {
            "description": "Critique: {section_title} {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Section critique",
        },
        "refine_section_task": {
            "description": "Refine: {section_title} {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    # exec summary kickoffs, then section kickoffs
    phase1_calls = [
        MagicMock(raw="Exec summary"),       # draft
        MagicMock(raw="READY_FOR_DEV: ok"),  # critique
    ]
    # Phase 2: 9 sections (executive_summary is carried from Phase 1)
    # With min=1, max=1: draft + critique (SECTION_READY) per section
    section_calls = []
    for _ in range(9):  # 9 sections (excludes executive_summary)
        section_calls.append(MagicMock(raw="Section content"))   # draft
        section_calls.append(MagicMock(raw="SECTION_READY: ok"))  # critique
    mock_kickoff.side_effect = phase1_calls + section_calls

    flow = PRDFlow()
    flow.state.idea = "Test"
    flow.executive_summary_callback = lambda content, idea, run_id, iters: True

    # Should not raise, should return finalized PRD
    result = flow.generate_sections()
    assert result is not None
    # Executive summary should be carried from Phase 1
    exec_sec = flow.state.draft.sections[0]
    assert exec_sec.key == "executive_summary"
    assert exec_sec.content == "Exec summary"
    assert exec_sec.is_approved is True
    # Remaining 9 sections should be filled by Phase 2
    for section in flow.state.draft.sections[1:]:
        assert section.content != "", f"Section '{section.key}' was not filled"


# ══════════════════════════════════════════════════════════════
# generate_sections — Phase 1 skip for resumed runs
# ══════════════════════════════════════════════════════════════


@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
@patch.object(PRDFlow, "_get_available_agents")
@patch("crewai_productfeature_planner.flows.prd_flow.get_task_configs")
@patch("crewai_productfeature_planner.orchestrator.build_default_pipeline")
def test_skip_phase1_when_exec_summary_has_enough_iterations(
    mock_pipeline, mock_task_configs, mock_agents, _mock_task, _mock_crew,
    mock_kickoff, mock_update_crit, mock_save_exec, mock_save_fin,
    mock_save_iter, mock_update_sec_crit,
    mock_mark_completed, mock_writer_cls, monkeypatch,
):
    """Phase 1 should be skipped when executive summary already has >= threshold iterations."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "1")
    monkeypatch.setenv("PRD_EXEC_RESUME_THRESHOLD", "3")

    mock_agents.return_value = {AGENT_OPENAI: MagicMock()}
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer
    mock_task_configs.return_value = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
        "draft_section_task": {
            "description": "Section: {section_title} {idea} content: {section_content} exec: {executive_summary}",
            "expected_output": "Draft {section_title}",
        },
        "critique_section_task": {
            "description": "Critique: {section_title} {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Section critique",
        },
        "refine_section_task": {
            "description": "Refine: {section_title} {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    # NO Phase 1 calls needed — only Phase 2 section calls
    # 9 sections: draft + critique (SECTION_READY) per section
    section_calls = []
    for _ in range(9):
        section_calls.append(MagicMock(raw="Section content"))
        section_calls.append(MagicMock(raw="SECTION_READY: ok"))
    mock_kickoff.side_effect = section_calls

    flow = PRDFlow()
    flow.state.idea = "Test idea"

    # Pre-populate executive summary with 3 iterations (simulating resume)
    from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryIteration
    for i in range(1, 4):
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(
                content=f"Exec summary v{i}",
                iteration=i,
                critique="critique" if i < 3 else "READY_FOR_DEV",
                updated_date=f"2026-01-0{i}",
            )
        )

    result = flow.generate_sections()

    assert result is not None
    # Phase 1 was skipped — save_executive_summary should NOT have been called
    mock_save_exec.assert_not_called()
    # Executive summary should use the last iteration content
    assert flow.state.finalized_idea == "Exec summary v3"
    assert flow.state.executive_summary.is_approved is True
    # Executive summary section should be populated and approved
    exec_sec = flow.state.draft.sections[0]
    assert exec_sec.key == "executive_summary"
    assert exec_sec.content == "Exec summary v3"
    assert exec_sec.is_approved is True
    # Remaining 9 sections should be filled by Phase 2
    for section in flow.state.draft.sections[1:]:
        assert section.content != "", f"Section '{section.key}' was not filled"


@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
@patch.object(PRDFlow, "_get_available_agents")
@patch("crewai_productfeature_planner.flows.prd_flow.get_task_configs")
@patch("crewai_productfeature_planner.orchestrator.build_default_pipeline")
def test_phase1_runs_when_below_threshold(
    mock_pipeline, mock_task_configs, mock_agents, _mock_task, _mock_crew,
    mock_kickoff, mock_update_crit, mock_save_exec, mock_save_fin,
    mock_save_iter, mock_update_sec_crit,
    mock_mark_completed, mock_writer_cls, monkeypatch,
):
    """Phase 1 should still run when executive summary has < threshold iterations."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "1")
    monkeypatch.setenv("PRD_EXEC_RESUME_THRESHOLD", "3")

    mock_agents.return_value = {AGENT_OPENAI: MagicMock()}
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer
    mock_task_configs.return_value = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
        "draft_section_task": {
            "description": "Section: {section_title} {idea} content: {section_content} exec: {executive_summary}",
            "expected_output": "Draft {section_title}",
        },
        "critique_section_task": {
            "description": "Critique: {section_title} {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Section critique",
        },
        "refine_section_task": {
            "description": "Refine: {section_title} {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    # Phase 1 calls (exec summary draft + critique) + Phase 2 section calls
    phase1_calls = [
        MagicMock(raw="New exec summary"),
        MagicMock(raw="READY_FOR_DEV: ok"),
    ]
    section_calls = []
    for _ in range(9):
        section_calls.append(MagicMock(raw="Section content"))
        section_calls.append(MagicMock(raw="SECTION_READY: ok"))
    mock_kickoff.side_effect = phase1_calls + section_calls

    flow = PRDFlow()
    flow.state.idea = "Test idea"
    flow.executive_summary_callback = lambda content, idea, run_id, iters: True

    # Only 2 iterations — below threshold of 3
    from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryIteration
    for i in range(1, 3):
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(
                content=f"Exec v{i}", iteration=i,
                critique="needs work", updated_date=f"2026-01-0{i}",
            )
        )

    result = flow.generate_sections()

    assert result is not None
    # Phase 1 DID run — save_executive_summary should have been called
    assert mock_save_exec.call_count >= 1


# ══════════════════════════════════════════════════════════════
# generate_sections — resume skips draft for in-progress sections
# ══════════════════════════════════════════════════════════════


@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
@patch.object(PRDFlow, "_get_available_agents")
@patch("crewai_productfeature_planner.flows.prd_flow.get_task_configs")
@patch("crewai_productfeature_planner.orchestrator.build_default_pipeline")
def test_resume_skips_draft_for_in_progress_section(
    mock_pipeline, mock_task_configs, mock_agents, _mock_task, _mock_crew,
    mock_kickoff, mock_update_crit, mock_save_exec, mock_save_fin,
    mock_save_iter, mock_update_sec_crit,
    mock_mark_completed, mock_writer_cls, monkeypatch,
):
    """Sections with restored content and iteration > 0 should skip
    the draft step and go directly into the approval loop."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "3")
    monkeypatch.setenv("PRD_EXEC_RESUME_THRESHOLD", "3")

    mock_agents.return_value = {AGENT_OPENAI: MagicMock()}
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer
    mock_task_configs.return_value = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
        "draft_section_task": {
            "description": "Section: {section_title} {idea} content: {section_content} exec: {executive_summary}",
            "expected_output": "Draft {section_title}",
        },
        "critique_section_task": {
            "description": "Critique: {section_title} {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Section critique",
        },
        "refine_section_task": {
            "description": "Refine: {section_title} {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow = PRDFlow()
    flow.state.idea = "Test idea"

    # Pre-populate executive summary (3 iterations → skip Phase 1)
    for i in range(1, 4):
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(
                content=f"Exec summary v{i}", iteration=i,
                critique="READY_FOR_DEV", updated_date=f"2026-01-0{i}",
            )
        )

    # Simulate resume: sections 1-4 approved (exec_summary + 3 sections)
    # Section 5 (index 4) has content at iteration 2 but NOT approved
    for i in range(4):
        flow.state.draft.sections[i].content = f"Approved section {i} content"
        flow.state.draft.sections[i].is_approved = True
        flow.state.draft.sections[i].iteration = 3

    # The in-progress section — has content from a prior run
    in_progress = flow.state.draft.sections[4]
    in_progress.content = "Restored iteration 2 content"
    in_progress.iteration = 2
    in_progress.selected_agent = AGENT_OPENAI

    # Calls needed:
    # - Section 5 (index 4): already has content → skip draft → critique + SECTION_READY
    # - Sections 6-10 (indices 5-9): need full draft + critique (SECTION_READY)
    calls = []
    # Section 5: critique only (SECTION_READY — will auto-approve since min=1, iter=2)
    calls.append(MagicMock(raw="SECTION_READY: looking good"))
    # Sections 6-10: draft + critique each
    for _ in range(5):
        calls.append(MagicMock(raw="New section content"))
        calls.append(MagicMock(raw="SECTION_READY: ok"))
    mock_kickoff.side_effect = calls

    result = flow.generate_sections()

    assert result is not None
    # The in-progress section should keep its restored content since
    # SECTION_READY was returned at iteration 2 (past min=1)
    assert in_progress.is_approved is True
    assert in_progress.iteration == 2
    assert in_progress.content == "Restored iteration 2 content"
    # All sections should be approved
    for section in flow.state.draft.sections:
        assert section.is_approved is True, (
            f"Section '{section.key}' was not approved"
        )


@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.update_section_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.save_iteration")
@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized_idea")
@patch("crewai_productfeature_planner.flows.prd_flow.save_executive_summary")
@patch("crewai_productfeature_planner.flows.prd_flow.update_executive_summary_critique")
@patch("crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry")
@patch("crewai_productfeature_planner.flows.prd_flow.Crew")
@patch("crewai_productfeature_planner.flows.prd_flow.Task")
@patch.object(PRDFlow, "_get_available_agents")
@patch("crewai_productfeature_planner.flows.prd_flow.get_task_configs")
@patch("crewai_productfeature_planner.orchestrator.build_default_pipeline")
def test_resume_wipes_degenerate_restored_content(
    mock_pipeline, mock_task_configs, mock_agents, _mock_task, _mock_crew,
    mock_kickoff, mock_update_crit, mock_save_exec, mock_save_fin,
    mock_save_iter, mock_update_sec_crit,
    mock_mark_completed, mock_writer_cls, monkeypatch,
):
    """A section restored from MongoDB with degenerate content (e.g. saved
    before the guard existed) should be wiped and re-drafted from scratch."""
    monkeypatch.setenv("PRD_SECTION_MIN_ITERATIONS", "1")
    monkeypatch.setenv("PRD_SECTION_MAX_ITERATIONS", "3")
    monkeypatch.setenv("PRD_EXEC_RESUME_THRESHOLD", "3")
    monkeypatch.setenv("PRD_SECTION_MAX_CHARS", "5000")

    mock_agents.return_value = {AGENT_OPENAI: MagicMock()}
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved"
    mock_writer_cls.return_value = mock_writer
    mock_task_configs.return_value = {
        "draft_prd_task": {
            "description": "Draft: {idea} {executive_summary}",
            "expected_output": "Summary",
        },
        "critique_prd_task": {
            "description": "Critique: {critique} {executive_summary}",
            "expected_output": "Critique",
        },
        "draft_section_task": {
            "description": "Section: {section_title} {idea} content: {section_content} exec: {executive_summary}",
            "expected_output": "Draft {section_title}",
        },
        "critique_section_task": {
            "description": "Critique: {section_title} {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Section critique",
        },
        "refine_section_task": {
            "description": "Refine: {section_title} {section_content} critique: {critique_section_content} exec: {executive_summary} approved: {approved_sections}",
            "expected_output": "Refined {section_title} based on {critique_section_content}",
        },
    }

    flow = PRDFlow()
    flow.state.idea = "Test idea"

    # Pre-populate executive summary (3 iterations → skip Phase 1)
    for i in range(1, 4):
        flow.state.executive_summary.iterations.append(
            ExecutiveSummaryIteration(
                content=f"Exec summary v{i}", iteration=i,
                critique="READY_FOR_DEV", updated_date=f"2026-01-0{i}",
            )
        )

    # Sections 0-3 approved
    for i in range(4):
        flow.state.draft.sections[i].content = f"Approved section {i}"
        flow.state.draft.sections[i].is_approved = True
        flow.state.draft.sections[i].iteration = 3

    # Section 4 has DEGENERATE restored content (133k chars of garbage)
    degenerate_section = flow.state.draft.sections[4]
    degenerate_section.content = "of" * 50_000  # 100,000 chars > 5000 max
    degenerate_section.iteration = 2
    degenerate_section.selected_agent = AGENT_OPENAI

    # Calls needed:
    # - Section 4: wiped → fresh draft + critique (SECTION_READY)
    # - Sections 5-9: fresh draft + critique each
    calls = []
    for _ in range(6):
        calls.append(MagicMock(raw="Fresh draft content"))
        calls.append(MagicMock(raw="SECTION_READY: ok"))
    mock_kickoff.side_effect = calls

    result = flow.generate_sections()

    assert result is not None
    # Degenerate content should have been wiped and re-drafted
    assert degenerate_section.is_approved is True
    assert degenerate_section.content == "Fresh draft content"
    assert degenerate_section.iteration == 1  # reset to 1 from draft
    for section in flow.state.draft.sections:
        assert section.is_approved is True, (
            f"Section '{section.key}' was not approved"
        )


# ══════════════════════════════════════════════════════════════
# _run_post_completion
# ══════════════════════════════════════════════════════════════


class TestRunPostCompletion:
    """Tests for PRDFlow._run_post_completion."""

    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry"
    )
    @patch(
        "crewai_productfeature_planner.orchestrator.build_post_completion_crew"
    )
    def test_calls_post_completion_crew(self, mock_build, mock_kickoff):
        mock_crew = MagicMock()
        mock_build.return_value = mock_crew

        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow._run_post_completion()

        mock_build.assert_called_once_with(flow)
        mock_kickoff.assert_called_once_with(mock_crew, step_label="post_completion")

    @patch(
        "crewai_productfeature_planner.orchestrator.build_post_completion_crew"
    )
    def test_skips_when_crew_is_none(self, mock_build):
        """When no delivery steps needed, crew returns None — should skip."""
        mock_build.return_value = None

        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow._run_post_completion()

        mock_build.assert_called_once_with(flow)

    @patch(
        "crewai_productfeature_planner.orchestrator.build_post_completion_crew"
    )
    def test_swallows_exceptions(self, mock_build):
        """Crew errors should be logged but not raised."""
        mock_build.side_effect = RuntimeError("Confluence down")

        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        # Should not raise
        flow._run_post_completion()


def test_prd_state_confluence_url_default():
    """PRDState should have empty confluence_url by default."""
    state = PRDState()
    assert state.confluence_url == ""


def test_prd_state_jira_output_default():
    """PRDState should have empty jira_output by default."""
    state = PRDState()
    assert state.jira_output == ""