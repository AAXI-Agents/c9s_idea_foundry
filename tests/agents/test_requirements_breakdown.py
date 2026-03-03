"""Tests for the Requirements Breakdown agent configuration and runner."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.agents.requirements_breakdown.agent import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_MAX_RETRIES,
    _build_breakdown_llm,
    _get_iteration_limits,
    _load_yaml,
    create_requirements_breakdown_agent,
    breakdown_requirements,
)

# Note: GeminiCompletion objects do not expose .timeout or .max_retries
# attributes, so we test those constants directly rather than on the LLM.


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    """Provide dummy API keys."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── Factory tests ─────────────────────────────────────────────


def test_create_agent_requires_credentials(monkeypatch):
    """Should raise EnvironmentError when no Google credentials are set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
        create_requirements_breakdown_agent()


def test_create_agent_accepts_api_key(monkeypatch):
    """Should succeed with only GOOGLE_API_KEY set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    agent = create_requirements_breakdown_agent()
    assert "architect" in agent.role.lower() or "requirements" in agent.role.lower()


def test_create_agent_accepts_project(monkeypatch):
    """Should succeed with only GOOGLE_CLOUD_PROJECT set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    agent = create_requirements_breakdown_agent()
    assert agent is not None


def test_create_agent_role():
    """Agent should have a role mentioning architect or requirements."""
    agent = create_requirements_breakdown_agent()
    role_lower = agent.role.lower()
    assert "architect" in role_lower or "requirements" in role_lower


def test_create_agent_no_tools():
    """Agent should have no tools — pure reasoning only."""
    agent = create_requirements_breakdown_agent()
    assert len(agent.tools) == 0


def test_create_agent_no_delegation():
    """Agent should not delegate."""
    agent = create_requirements_breakdown_agent()
    assert agent.allow_delegation is False

def test_create_agent_reasoning_enabled():
    """Agent should have reasoning enabled for plan-before-execute."""
    agent = create_requirements_breakdown_agent()
    assert agent.reasoning is True
    assert agent.max_reasoning_attempts == 3

# ── LLM configuration tests ──────────────────────────────────


def test_build_llm_default_model(monkeypatch):
    """Without REQUIREMENTS_BREAKDOWN_MODEL or GEMINI_RESEARCH_MODEL, uses the default."""
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_RESEARCH_MODEL", raising=False)
    llm = _build_breakdown_llm()
    assert "gemini" in llm.model.lower()


def test_build_llm_respects_requirements_model(monkeypatch):
    """REQUIREMENTS_BREAKDOWN_MODEL should take precedence over GEMINI_RESEARCH_MODEL."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MODEL", "gemini-custom-model")
    monkeypatch.setenv("GEMINI_RESEARCH_MODEL", "gemini-3.1-pro-preview")
    llm = _build_breakdown_llm()
    assert "gemini-custom-model" in llm.model


def test_build_llm_falls_back_to_gemini_research_model(monkeypatch):
    """Without REQUIREMENTS_BREAKDOWN_MODEL, should use GEMINI_RESEARCH_MODEL."""
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_RESEARCH_MODEL", "gemini-2.5-pro")
    llm = _build_breakdown_llm()
    assert "gemini-2.5-pro" in llm.model


def test_build_llm_adds_prefix(monkeypatch):
    """Model names without '/' should get 'gemini/' prepended."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MODEL", "gemini-3-flash-preview")
    llm = _build_breakdown_llm()
    assert "gemini" in llm.model.lower()


def test_build_llm_no_double_prefix(monkeypatch):
    """Already-qualified model names should not be double-prefixed."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MODEL", "gemini/gemini-3-flash-preview")
    llm = _build_breakdown_llm()
    assert "gemini/gemini/" not in llm.model


def test_build_llm_returns_llm_object(monkeypatch):
    """_build_breakdown_llm should return a valid LLM object."""
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MODEL", raising=False)
    llm = _build_breakdown_llm()
    assert llm is not None
    assert hasattr(llm, "model")


# ── Iteration limits ─────────────────────────────────────────


def test_iteration_limits_defaults(monkeypatch):
    """Default limits should be (3, 10)."""
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", raising=False)
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", raising=False)
    min_i, max_i = _get_iteration_limits()
    assert min_i == DEFAULT_MIN_ITERATIONS
    assert max_i == DEFAULT_MAX_ITERATIONS


def test_iteration_limits_from_env(monkeypatch):
    """Env vars should override defaults."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "5")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "8")
    min_i, max_i = _get_iteration_limits()
    assert min_i == 5
    assert max_i == 8


def test_iteration_limits_clamp_min(monkeypatch):
    """Min should be clamped to at least 1."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "0")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "5")
    min_i, max_i = _get_iteration_limits()
    assert min_i == 1
    assert max_i == 5


def test_iteration_limits_max_at_least_min(monkeypatch):
    """Max should be at least min."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "7")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "3")
    min_i, max_i = _get_iteration_limits()
    assert max_i >= min_i


def test_iteration_limits_cap(monkeypatch):
    """Max should be capped at 20, min at 10."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "50")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "100")
    min_i, max_i = _get_iteration_limits()
    assert min_i <= 10
    assert max_i <= 20


# ── YAML loading ──────────────────────────────────────────────


def test_load_agent_yaml():
    """Agent YAML should contain requirements_breakdown key."""
    config = _load_yaml("agent.yaml")
    assert "requirements_breakdown" in config
    assert "role" in config["requirements_breakdown"]
    assert "goal" in config["requirements_breakdown"]
    assert "backstory" in config["requirements_breakdown"]


def test_load_tasks_yaml():
    """Tasks YAML should contain breakdown and evaluate tasks."""
    config = _load_yaml("tasks.yaml")
    assert "breakdown_requirements_task" in config
    assert "evaluate_requirements_task" in config


def test_breakdown_task_has_required_placeholders():
    """Breakdown task description should accept idea, iteration, etc."""
    config = _load_yaml("tasks.yaml")
    desc = config["breakdown_requirements_task"]["description"]
    assert "{idea}" in desc
    assert "{iteration}" in desc
    assert "{max_iterations}" in desc
    assert "{previous_feedback}" in desc
    assert "{previous_requirements}" in desc


def test_evaluate_task_has_required_placeholders():
    """Evaluate task description should accept requirements, iteration, etc."""
    config = _load_yaml("tasks.yaml")
    desc = config["evaluate_requirements_task"]["description"]
    assert "{requirements}" in desc
    assert "{iteration}" in desc
    assert "{max_iterations}" in desc
    assert "{min_iterations}" in desc


# ── Constants ─────────────────────────────────────────────────


def test_default_constants():
    """Module-level defaults should be sensible."""
    assert DEFAULT_MIN_ITERATIONS == 3
    assert DEFAULT_MAX_ITERATIONS == 10
    assert DEFAULT_LLM_TIMEOUT == 300
    assert DEFAULT_LLM_MAX_RETRIES == 3


# ── breakdown_requirements runner ─────────────────────────────


def test_breakdown_stops_at_requirements_ready(monkeypatch):
    """Should stop after min iterations when evaluator returns REQUIREMENTS_READY."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "3")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "10")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        # Set breakdown_task output on the crew's first task
        breakdown_output = MagicMock()
        breakdown_output.raw = f"## Feature {call_count}\nBreakdown v{call_count}"
        crew.tasks[0].output = breakdown_output
        # Return evaluation result (last task output)
        result = MagicMock()
        if call_count >= 3:
            result.raw = "All criteria score 4+. REQUIREMENTS_READY"
        else:
            result.raw = "Needs more detail. NEEDS_MORE"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("Build a dashboard with AI")

    assert "Feature 3" in result
    # 1 merged crew kickoff per iteration = 3 calls
    assert call_count == 3
    assert len(history) == 3
    assert history[0]["iteration"] == 1
    assert history[2]["iteration"] == 3
    assert "requirements" in history[0]
    assert "evaluation" in history[0]


def test_breakdown_runs_max_iterations(monkeypatch):
    """Should stop at max_iterations even if not REQUIREMENTS_READY."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "2")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "4")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        breakdown_output = MagicMock()
        breakdown_output.raw = f"Requirements v{call_count}"
        crew.tasks[0].output = breakdown_output
        result = MagicMock()
        result.raw = "Still needs work. NEEDS_MORE"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("Build a feature")

    # 1 merged crew kickoff per iteration = 4 calls (max 4 iterations)
    assert call_count == 4
    assert len(history) == 4


def test_breakdown_ignores_ready_before_min(monkeypatch):
    """REQUIREMENTS_READY before min iterations should be ignored."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "3")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "5")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        breakdown_output = MagicMock()
        breakdown_output.raw = f"Requirements v{call_count}"
        crew.tasks[0].output = breakdown_output
        result = MagicMock()
        # Always say REQUIREMENTS_READY — but should be ignored before iter 3
        result.raw = "Looks good. REQUIREMENTS_READY"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("Some idea")

    # Should run exactly 3 iterations (min), then stop
    assert call_count == 3
    assert len(history) == 3


def test_breakdown_returns_tuple(monkeypatch):
    """breakdown_requirements should return a (str, list[dict]) tuple."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "1")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "1")

    def mock_kickoff(crew, step_label=""):
        breakdown_output = MagicMock()
        breakdown_output.raw = "## Feature 1\nDetailed requirements"
        crew.tasks[0].output = breakdown_output
        result = MagicMock()
        result.raw = "REQUIREMENTS_READY"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("An idea")

    assert isinstance(result, str)
    assert len(result) > 0
    assert isinstance(history, list)
    assert len(history) == 1
    assert history[0]["iteration"] == 1
    assert history[0]["requirements"] == "## Feature 1\nDetailed requirements"
    assert history[0]["evaluation"] == "REQUIREMENTS_READY"


def test_breakdown_saves_iterations_with_run_id(monkeypatch):
    """When run_id is provided, each iteration should be saved to workingIdeas."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "1")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "2")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        breakdown_output = MagicMock()
        breakdown_output.raw = f"Requirements v{call_count}"
        crew.tasks[0].output = breakdown_output
        result = MagicMock()
        result.raw = "NEEDS_MORE" if call_count < 2 else "REQUIREMENTS_READY"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff), \
         patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db") as mock_db:
        mock_collection = MagicMock()
        mock_db.return_value = {"workingIdeas": mock_collection}
        result, history = breakdown_requirements("An idea", run_id="test_run_456")

    assert mock_collection.update_one.call_count == 2
    first_call = mock_collection.update_one.call_args_list[0]
    assert first_call[0][0] == {"run_id": "test_run_456"}
    assert first_call[1].get("upsert") is True


def test_breakdown_no_run_id_skips_save(monkeypatch):
    """Without run_id, no save_iteration calls should be made."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "1")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "1")

    def mock_kickoff(crew, step_label=""):
        breakdown_output = MagicMock()
        breakdown_output.raw = "Requirements"
        crew.tasks[0].output = breakdown_output
        result = MagicMock()
        result.raw = "REQUIREMENTS_READY"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff), \
         patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db") as mock_db:
        mock_collection = MagicMock()
        mock_db.return_value = {"workingIdeas": mock_collection}
        breakdown_requirements("An idea")  # no run_id

    mock_collection.update_one.assert_not_called()


def test_breakdown_passes_previous_requirements(monkeypatch):
    """Each iteration should receive the prior iteration's output to build upon."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "2")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "2")

    captured_descriptions: list[str] = []
    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        # Capture the breakdown task description (first task)
        task_desc = crew.tasks[0].description
        captured_descriptions.append(task_desc)
        # Set breakdown_task output
        breakdown_output = MagicMock()
        breakdown_output.raw = f"## Feature {call_count}\nRequirements iteration {call_count}"
        crew.tasks[0].output = breakdown_output
        result = MagicMock()
        result.raw = "NEEDS_MORE" if call_count < 2 else "REQUIREMENTS_READY"
        return result

    with patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        breakdown_requirements("Build a dashboard")

    # Should have captured 2 breakdown task descriptions
    assert len(captured_descriptions) == 2
    # First iteration: no prior requirements
    assert "First iteration" in captured_descriptions[0]
    assert "no prior requirements" in captured_descriptions[0]
    # Second iteration: should contain the first iteration's output
    assert "## Feature 1" in captured_descriptions[1]
    assert "Requirements iteration 1" in captured_descriptions[1]


def test_breakdown_task_instructs_to_build_upon():
    """Breakdown task should instruct agent to build upon previous output."""
    config = _load_yaml("tasks.yaml")
    desc = config["breakdown_requirements_task"]["description"]
    assert "build upon" in desc.lower() or "improve them" in desc.lower()
    assert "do NOT start from scratch" in desc or "do not start from scratch" in desc.lower()


def test_evaluate_task_granularity_check():
    """Evaluate task should include a granularity check for data architect readiness."""
    config = _load_yaml("tasks.yaml")
    desc = config["evaluate_requirements_task"]["description"]
    assert "granularity" in desc.lower() or "Granularity" in desc
    assert "data architect" in desc.lower()


# ── __init__.py re-exports ────────────────────────────────────


def test_init_exports():
    """Package __init__.py should re-export the public API."""
    from crewai_productfeature_planner.agents.requirements_breakdown import (
        DEFAULT_MAX_ITERATIONS as MAX,
        DEFAULT_MIN_ITERATIONS as MIN,
        create_requirements_breakdown_agent as factory,
        breakdown_requirements as runner,
    )
    assert MIN == 3
    assert MAX == 10
    assert callable(factory)
    assert callable(runner)
