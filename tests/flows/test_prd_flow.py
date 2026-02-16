"""Tests for the iterative PRD flow."""

from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.apis.prd.models import (
    AGENT_GEMINI,
    AGENT_OPENAI,
    DEFAULT_AGENT_FALLBACK,
    PRDDraft,
    PRDSection,
    SECTION_KEYS,
    VALID_AGENTS,
    get_default_agent,
)
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
    assert draft.sections[1].key == "why_now"
    assert draft.sections[1].title == "Why Now / Market Timing"
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
    assert draft.next_section().key == "why_now"


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
    flow.approval_callback = lambda iteration, key, agent_results, draft: PAUSE_SENTINEL

    section = flow.state.draft.sections[0]
    section.content = "Some draft content"
    section.agent_results = {AGENT_OPENAI: "Some draft content"}
    section.iteration = 1

    agents = {AGENT_OPENAI: MagicMock()}
    with pytest.raises(PauseRequested):
        flow._section_approval_loop(section, agents, {})


@patch("crewai_productfeature_planner.flows.prd_flow.mark_completed")
@patch("crewai_productfeature_planner.flows.prd_flow.save_finalized")
@patch("crewai_productfeature_planner.flows.prd_flow.PRDFileWriteTool")
def test_finalize_saves_prd(mock_writer_cls, mock_save_finalized, mock_mark_completed):
    """finalize() should persist the assembled PRD via file and MongoDB with XHTML."""
    mock_writer = MagicMock()
    mock_writer._run.return_value = "PRD saved to output/prds/prd_v1.md"
    mock_writer_cls.return_value = mock_writer
    mock_save_finalized.return_value = "inserted_id_123"

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

    # Working ideas should be marked completed
    mock_mark_completed.assert_called_once_with("test-run-123")

    # State should be flagged as ready
    assert flow.state.is_ready is True


# ── Multi-agent helpers ──────────────────────────────────────


def test_parse_decision_tuple():
    """Tuple decisions should be unpacked as (agent_name, action)."""
    agent, action = PRDFlow._parse_decision(
        (AGENT_GEMINI, True), [AGENT_OPENAI, AGENT_GEMINI],
    )
    assert agent == AGENT_GEMINI
    assert action is True


def test_parse_decision_tuple_feedback():
    """Tuple with feedback string should be returned as-is."""
    agent, action = PRDFlow._parse_decision(
        (AGENT_OPENAI, "Add more details"), [AGENT_OPENAI],
    )
    assert agent == AGENT_OPENAI
    assert action == "Add more details"


def test_parse_decision_legacy_true():
    """Legacy True return should select the first available agent."""
    agent, action = PRDFlow._parse_decision(True, [AGENT_OPENAI, AGENT_GEMINI])
    assert agent == AGENT_OPENAI
    assert action is True


def test_parse_decision_legacy_false():
    """Legacy False return should select the first available agent."""
    agent, action = PRDFlow._parse_decision(False, [AGENT_GEMINI, AGENT_OPENAI])
    assert agent == AGENT_GEMINI
    assert action is False


def test_parse_decision_legacy_string():
    """Legacy string return (feedback) should select the first available agent."""
    agent, action = PRDFlow._parse_decision(
        "Needs more detail", [AGENT_OPENAI],
    )
    assert agent == AGENT_OPENAI
    assert action == "Needs more detail"


@patch("crewai_productfeature_planner.flows.prd_flow.create_product_manager")
def test_get_available_agents_openai_only(mock_create_pm, monkeypatch):
    """Without GOOGLE_API_KEY/GOOGLE_CLOUD_PROJECT only OpenAI PM should be returned."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("DEFAULT_AGENT", raising=False)
    mock_create_pm.return_value = MagicMock()
    agents = PRDFlow._get_available_agents()
    assert list(agents.keys()) == [AGENT_OPENAI]
    mock_create_pm.assert_called_once()


@patch(
    "crewai_productfeature_planner.agents.gemini_product_manager.create_gemini_product_manager",
)
@patch("crewai_productfeature_planner.flows.prd_flow.create_product_manager")
def test_get_available_agents_both(mock_create_pm, mock_create_gemini, monkeypatch):
    """With GOOGLE_API_KEY both OpenAI and Gemini PM agents should be returned."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("DEFAULT_AGENT", raising=False)
    mock_create_pm.return_value = MagicMock()
    mock_create_gemini.return_value = MagicMock()
    agents = PRDFlow._get_available_agents()
    assert AGENT_OPENAI in agents
    assert AGENT_GEMINI in agents
    # Default agent should come first
    assert list(agents.keys())[0] == AGENT_OPENAI


@patch(
    "crewai_productfeature_planner.agents.gemini_product_manager.create_gemini_product_manager",
)
def test_get_available_agents_gemini_default(mock_create_gemini, monkeypatch):
    """When DEFAULT_AGENT=gemini_pm, Gemini should be first and OpenAI optional."""
    monkeypatch.setenv("DEFAULT_AGENT", "gemini_pm")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    mock_create_gemini.return_value = MagicMock()
    with patch("crewai_productfeature_planner.flows.prd_flow.create_product_manager") as mock_pm:
        mock_pm.return_value = MagicMock()
        agents = PRDFlow._get_available_agents()
    assert list(agents.keys())[0] == AGENT_GEMINI
    assert AGENT_OPENAI in agents


@patch(
    "crewai_productfeature_planner.agents.gemini_product_manager.create_gemini_product_manager",
)
def test_get_available_agents_gemini_default_no_openai(mock_create_gemini, monkeypatch):
    """When DEFAULT_AGENT=gemini_pm and OPENAI_API_KEY is unset, only Gemini returned."""
    monkeypatch.setenv("DEFAULT_AGENT", "gemini_pm")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mock_create_gemini.return_value = MagicMock()
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
                    "description": "Draft {section_title} for {idea} with {context_sections}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Executive Summary",
            idea="Test idea",
            context="",
        )
    assert list(results.keys()) == [AGENT_OPENAI]
    assert results[AGENT_OPENAI] == "Agent draft content"
    assert failed == set()


def test_run_agents_parallel_multi():
    """Multiple agents should run in parallel and return all results."""
    mock_result_openai = MagicMock()
    mock_result_openai.raw = "OpenAI result"
    mock_result_gemini = MagicMock()
    mock_result_gemini.raw = "Gemini result"

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        return mock_result_openai if "openai" in step_label else mock_result_gemini

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        results, failed = PRDFlow._run_agents_parallel(
            agents={AGENT_OPENAI: MagicMock(), AGENT_GEMINI: MagicMock()},
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} with {context_sections}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            context="",
        )
    assert AGENT_OPENAI in results
    assert AGENT_GEMINI in results
    assert call_count == 2
    assert failed == set()


def test_run_agents_parallel_one_fails():
    """If one agent fails, the other should still succeed."""
    mock_result = MagicMock()
    mock_result.raw = "Survivor result"

    def mock_kickoff(crew, step_label=""):
        if "gemini" in step_label:
            raise RuntimeError("Gemini exploded")
        return mock_result

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        results, failed = PRDFlow._run_agents_parallel(
            agents={AGENT_OPENAI: MagicMock(), AGENT_GEMINI: MagicMock()},
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} with {context_sections}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            context="",
        )
    assert AGENT_OPENAI in results
    assert AGENT_GEMINI not in results
    assert failed == {AGENT_GEMINI}


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
                agents={AGENT_OPENAI: MagicMock(), AGENT_GEMINI: MagicMock()},
                task_configs={
                    "draft_section_task": {
                        "description": "Draft {section_title} for {idea} with {context_sections}",
                        "expected_output": "A {section_title} section",
                    },
                },
                section_title="Problem Statement",
                idea="Test idea",
                context="",
            )


def test_failed_optional_agent_dropped_for_remaining_sections():
    """When an optional agent fails, it should be removed for subsequent sections."""
    mock_result = MagicMock()
    mock_result.raw = "Default agent result"

    call_log = []

    def mock_kickoff(crew, step_label=""):
        call_log.append(step_label)
        if "gemini" in step_label:
            raise RuntimeError("Gemini unavailable")
        return mock_result

    agents = {AGENT_OPENAI: MagicMock(), AGENT_GEMINI: MagicMock()}

    with patch(
        "crewai_productfeature_planner.flows.prd_flow.crew_kickoff_with_retry",
        side_effect=mock_kickoff,
    ), patch("crewai_productfeature_planner.flows.prd_flow.Crew"), patch(
        "crewai_productfeature_planner.flows.prd_flow.Task",
    ):
        # First call — Gemini fails
        results, failed = PRDFlow._run_agents_parallel(
            agents=agents,
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} with {context_sections}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Executive Summary",
            idea="Test idea",
            context="",
        )
        assert failed == {AGENT_GEMINI}
        assert AGENT_OPENAI in results

        # Simulate generate_sections removing the failed agent
        for name in failed:
            if name in agents:
                del agents[name]

        assert AGENT_GEMINI not in agents
        assert len(agents) == 1

        # Second call — should only use the default agent, no Gemini attempt
        call_log.clear()
        results2, failed2 = PRDFlow._run_agents_parallel(
            agents=agents,
            task_configs={
                "draft_section_task": {
                    "description": "Draft {section_title} for {idea} with {context_sections}",
                    "expected_output": "A {section_title} section",
                },
            },
            section_title="Problem Statement",
            idea="Test idea",
            context="",
        )
        assert failed2 == set()
        assert AGENT_OPENAI in results2
        # Gemini should not have been called
        assert not any("gemini" in label for label in call_log)


def test_section_agent_results_after_approval():
    """After approval with a specific agent, section should have correct selected_agent."""
    flow = PRDFlow()
    section = flow.state.draft.sections[0]
    section.content = "OpenAI draft"
    section.agent_results = {
        AGENT_OPENAI: "OpenAI draft",
        AGENT_GEMINI: "Gemini draft",
    }
    section.selected_agent = AGENT_OPENAI
    section.iteration = 1

    flow.approval_callback = lambda iteration, key, agent_results, draft: (AGENT_GEMINI, True)

    agents = {AGENT_OPENAI: MagicMock(), AGENT_GEMINI: MagicMock()}
    flow._section_approval_loop(section, agents, {})

    assert section.is_approved is True
    assert section.selected_agent == AGENT_GEMINI
    assert section.content == "Gemini draft"


# ── get_default_agent() ──────────────────────────────────────────


def test_get_default_agent_unset(monkeypatch):
    """Without DEFAULT_AGENT env var, should return openai_pm."""
    monkeypatch.delenv("DEFAULT_AGENT", raising=False)
    assert get_default_agent() == AGENT_OPENAI


def test_get_default_agent_openai(monkeypatch):
    """DEFAULT_AGENT=openai_pm should return openai_pm."""
    monkeypatch.setenv("DEFAULT_AGENT", "openai_pm")
    assert get_default_agent() == AGENT_OPENAI


def test_get_default_agent_gemini(monkeypatch):
    """DEFAULT_AGENT=gemini_pm should return gemini_pm."""
    monkeypatch.setenv("DEFAULT_AGENT", "gemini_pm")
    assert get_default_agent() == AGENT_GEMINI


def test_get_default_agent_invalid(monkeypatch):
    """Invalid DEFAULT_AGENT value should fall back to openai_pm."""
    monkeypatch.setenv("DEFAULT_AGENT", "invalid_agent")
    assert get_default_agent() == DEFAULT_AGENT_FALLBACK


def test_valid_agents_contains_both():
    """VALID_AGENTS should list both known agents."""
    assert AGENT_OPENAI in VALID_AGENTS
    assert AGENT_GEMINI in VALID_AGENTS
