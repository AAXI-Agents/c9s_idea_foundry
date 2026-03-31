"""Tests for the Idea Agent configuration and runner."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.agents.idea_agent.agent import (
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_MAX_RETRIES,
    _extract_iteration_context,
    _handle_idea_query_fast,
    _handle_idea_query_crewai,
    _load_yaml,
    create_idea_agent,
    extract_steering_feedback,
    handle_idea_query,
)


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    """Provide dummy API keys."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture(autouse=True)
def _mock_idea_agent_llm():
    """Prevent real LLM construction."""
    with patch(
        "crewai_productfeature_planner.agents.idea_agent.agent._build_idea_agent_llm",
        return_value="gemini/gemini-3-flash-preview",
    ):
        yield


@pytest.fixture(autouse=True)
def _skip_fast_path(request):
    """Mock fast-path function to return None immediately.

    Without this, tests that call handle_idea_query() attempt a real
    Gemini HTTP call (which fails with the test API key), adding ~1s.

    Skipped for TestHandleIdeaQueryFastPath which explicitly tests
    the fast path.
    """
    cls = request.node.cls
    if cls and cls.__name__ == "TestHandleIdeaQueryFastPath":
        yield
        return
    with patch(
        "crewai_productfeature_planner.agents.idea_agent.agent._handle_idea_query_fast",
        return_value=None,
    ):
        yield


# ── Factory tests ─────────────────────────────────────────────


def test_create_idea_agent_requires_credentials(monkeypatch):
    """Should raise EnvironmentError when neither key nor project is set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
        create_idea_agent()


def test_create_idea_agent_accepts_api_key(monkeypatch):
    """Should succeed with only GOOGLE_API_KEY set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    agent = create_idea_agent()
    assert agent is not None


def test_create_idea_agent_accepts_project(monkeypatch):
    """Should succeed with only GOOGLE_CLOUD_PROJECT set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    agent = create_idea_agent()
    assert agent is not None


def test_create_idea_agent_role():
    """Agent should have a role mentioning analysis or iteration."""
    agent = create_idea_agent()
    role_lower = agent.role.lower()
    assert "idea" in role_lower or "analyst" in role_lower or "advisor" in role_lower


def test_create_idea_agent_no_tools():
    """Agent should have no external tools."""
    agent = create_idea_agent()
    assert len(agent.tools) == 0


# ── Config loading ────────────────────────────────────────────


def test_load_yaml_agent():
    """Agent YAML should load and contain expected keys."""
    config = _load_yaml("agent.yaml")
    assert "idea_agent" in config
    agent_cfg = config["idea_agent"]
    assert "role" in agent_cfg
    assert "goal" in agent_cfg
    assert "backstory" in agent_cfg


def test_load_yaml_tasks():
    """Tasks YAML should load and contain the query task."""
    config = _load_yaml("tasks.yaml")
    assert "idea_query_task" in config
    task_cfg = config["idea_query_task"]
    assert "description" in task_cfg
    assert "expected_output" in task_cfg


# ── Context extraction ────────────────────────────────────────


def _make_flow_doc(**overrides):
    """Build a minimal working-idea document for testing."""
    doc = {
        "run_id": "abc123",
        "status": "inprogress",
        "iteration": 3,
        "idea": "Build a mobile payments platform",
        "section": {},
        "executive_summary": [],
        "pipeline": {},
    }
    doc.update(overrides)
    return doc


def test_extract_context_minimal():
    """Context extraction from a minimal doc should not crash."""
    doc = _make_flow_doc()
    ctx = _extract_iteration_context(doc)
    assert "inprogress" in ctx["status_summary"]
    assert "mobile payments" in ctx["current_idea"]
    assert ctx["refinement_history"] == "(no refinement history)"
    assert ctx["executive_summary"] == "(not started)"


def test_extract_context_with_idea():
    """Current idea should be extracted from the document."""
    doc = _make_flow_doc(idea="A smart receipt scanner")
    ctx = _extract_iteration_context(doc)
    assert "smart receipt scanner" in ctx["current_idea"]


def test_extract_context_with_exec_summary():
    """Executive summary iterations should be extracted."""
    doc = _make_flow_doc(executive_summary=[
        {"iteration": 1, "content": "Draft exec summary v1", "critique": "Too vague"},
        {"iteration": 2, "content": "Refined exec summary v2", "critique": ""},
    ])
    ctx = _extract_iteration_context(doc)
    assert "Refined exec summary v2" in ctx["executive_summary"]
    assert "2" in ctx["executive_summary"]  # iteration number


def test_extract_context_with_refinement_history():
    """Refinement pipeline steps should be extracted."""
    doc = _make_flow_doc(pipeline={
        "refine_idea": [
            {"iteration": 1, "content": "First pass idea", "critique": "Needs more detail"},
            {"iteration": 2, "content": "Second pass idea", "critique": "Better"},
        ]
    })
    ctx = _extract_iteration_context(doc)
    assert "First pass" in ctx["refinement_history"]
    assert "Second pass" in ctx["refinement_history"]


def test_extract_context_with_sections():
    """Completed sections should be listed."""
    doc = _make_flow_doc(section={
        "problem_statement": [{"content": "The core problem is...", "iteration": 1}],
        "user_personas": [{"content": "Persona A: ...", "iteration": 1}],
    })
    ctx = _extract_iteration_context(doc)
    assert "Problem Statement" in ctx["status_summary"]
    assert "core problem" in ctx["completed_sections"]


def test_extract_context_with_requirements():
    """Requirements breakdown should be extracted from pipeline."""
    doc = _make_flow_doc(pipeline={
        "requirements_breakdown": [
            {"iteration": 1, "content": "Entity: Payment, API: /charge"},
        ]
    })
    ctx = _extract_iteration_context(doc)
    assert "Payment" in ctx["requirements_breakdown"]


def test_extract_context_with_engineering_plan():
    """Engineering plan should be extracted from pipeline or sections."""
    doc = _make_flow_doc(section={
        "engineering_plan": [
            {"content": "Phase 1: Build API layer", "iteration": 1},
        ]
    })
    ctx = _extract_iteration_context(doc)
    assert "API layer" in ctx["engineering_plan"]


# ── Steering feedback extraction ──────────────────────────────


def test_extract_steering_feedback_with_heading():
    """Should extract instruction from ## Steering Recommendation."""
    response = (
        "Here's what I found.\n\n"
        "## Steering Recommendation\n"
        "**Target agent**: Idea Refiner\n"
        "**Instruction**: Add mobile-first design constraints\n"
        "**Impact**: Refiner will focus on mobile UX"
    )
    result = extract_steering_feedback(response)
    assert result is not None
    assert "mobile-first" in result


def test_extract_steering_feedback_with_bold_heading():
    """Should extract from *Steering Recommendation* too."""
    response = (
        "Analysis complete.\n\n"
        "*Steering Recommendation*\n"
        "*Instruction*: Focus on security requirements\n"
    )
    result = extract_steering_feedback(response)
    assert result is not None
    assert "security" in result


def test_extract_steering_feedback_none_when_missing():
    """Should return None when no steering section exists."""
    response = "The idea looks good. No changes needed."
    result = extract_steering_feedback(response)
    assert result is None


def test_extract_steering_feedback_returns_section_without_instruction():
    """When no explicit Instruction line, returns the full section."""
    response = (
        "## Steering Recommendation\n"
        "Consider adding payment compliance requirements."
    )
    result = extract_steering_feedback(response)
    assert result is not None
    assert "payment compliance" in result


# ── handle_idea_query (mocked) ────────────────────────────────


def test_handle_idea_query_calls_crew(monkeypatch):
    """handle_idea_query should call crew_kickoff_with_retry."""
    mock_result = MagicMock()
    mock_result.__str__ = lambda _: "The current idea focuses on mobile payments."

    with patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
        return_value=mock_result,
    ):
        doc = _make_flow_doc()
        response = handle_idea_query(
            user_message="what is the current summary?",
            flow_doc=doc,
        )
    assert "mobile payments" in response


def test_handle_idea_query_includes_history(monkeypatch):
    """Conversation history should be passed to the task."""
    mock_result = MagicMock()
    mock_result.__str__ = lambda _: "Summary response"

    with patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
        return_value=mock_result,
    ) as mock_crew:
        doc = _make_flow_doc()
        handle_idea_query(
            user_message="what changed?",
            flow_doc=doc,
            conversation_history=[
                {"role": "user", "content": "iterate on fintech idea"},
                {"role": "assistant", "content": "Starting iteration..."},
            ],
        )
        # Crew should have been called
        mock_crew.assert_called_once()


# ── __init__ exports ──────────────────────────────────────────


def test_init_exports():
    """Package __init__ should export key functions."""
    from crewai_productfeature_planner.agents.idea_agent import (
        create_idea_agent,
        extract_steering_feedback,
        handle_idea_query,
    )
    assert callable(create_idea_agent)
    assert callable(extract_steering_feedback)
    assert callable(handle_idea_query)


# ── Fast-path tests (direct Gemini REST API) ──────────────────


class TestHandleIdeaQueryFastPath:
    """Tests for the direct Gemini REST API fast path."""

    @patch(
        "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
        return_value="The idea focuses on mobile payments with 3 iterations.",
    )
    def test_fast_path_returns_response(self, mock_chat):
        """Fast path should return generate_chat_response result."""
        doc = _make_flow_doc()
        result = _handle_idea_query_fast("what is the idea?", doc, None)
        assert result == "The idea focuses on mobile payments with 3 iterations."
        mock_chat.assert_called_once()

    @patch(
        "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
        return_value=None,
    )
    def test_fast_path_returns_none_on_failure(self, mock_chat):
        """Fast path returns None when generate_chat_response fails."""
        doc = _make_flow_doc()
        result = _handle_idea_query_fast("summarize", doc, None)
        assert result is None

    @patch(
        "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
        return_value="Fast idea analysis",
    )
    def test_handle_uses_fast_path_by_default(self, mock_chat):
        """handle_idea_query should use fast path by default."""
        doc = _make_flow_doc()
        result = handle_idea_query("what changed?", doc)
        assert result == "Fast idea analysis"

    @patch(
        "crewai_productfeature_planner.tools.gemini_chat.generate_chat_response",
        return_value=None,
    )
    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    )
    def test_falls_back_to_crewai_when_fast_fails(
        self, mock_kickoff, mock_chat,
    ):
        """When fast path returns None, should fall back to CrewAI."""
        mock_result = MagicMock()
        mock_result.__str__ = lambda _: "CrewAI idea response"
        mock_kickoff.return_value = mock_result

        doc = _make_flow_doc()
        result = handle_idea_query("what changed?", doc)
        assert result == "CrewAI idea response"
        mock_chat.assert_called_once()
        mock_kickoff.assert_called_once()

    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    )
    def test_uses_crewai_when_env_var_set(
        self, mock_kickoff, monkeypatch,
    ):
        """IDEA_AGENT_USE_CREWAI=true should bypass fast path."""
        monkeypatch.setenv("IDEA_AGENT_USE_CREWAI", "true")
        mock_result = MagicMock()
        mock_result.__str__ = lambda _: "CrewAI forced"
        mock_kickoff.return_value = mock_result

        doc = _make_flow_doc()
        result = handle_idea_query("status?", doc)
        assert result == "CrewAI forced"
        mock_kickoff.assert_called_once()
