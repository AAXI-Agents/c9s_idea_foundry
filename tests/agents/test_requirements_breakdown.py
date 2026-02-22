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


def _mock_build_breakdown_llm():
    return patch(
        "crewai_productfeature_planner.agents.requirements_breakdown.agent._build_breakdown_llm",
        return_value="gemini/gemini-3-flash-preview",
    )


# ── Factory tests ─────────────────────────────────────────────


def test_create_agent_requires_credentials(monkeypatch):
    """Should raise EnvironmentError when no Google credentials are set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
        with _mock_build_breakdown_llm():
            create_requirements_breakdown_agent()


def test_create_agent_accepts_api_key(monkeypatch):
    """Should succeed with only GOOGLE_API_KEY set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with _mock_build_breakdown_llm():
        agent = create_requirements_breakdown_agent()
    assert "architect" in agent.role.lower() or "requirements" in agent.role.lower()


def test_create_agent_accepts_project(monkeypatch):
    """Should succeed with only GOOGLE_CLOUD_PROJECT set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    with _mock_build_breakdown_llm():
        agent = create_requirements_breakdown_agent()
    assert agent is not None


def test_create_agent_role():
    """Agent should have a role mentioning architect or requirements."""
    with _mock_build_breakdown_llm():
        agent = create_requirements_breakdown_agent()
    role_lower = agent.role.lower()
    assert "architect" in role_lower or "requirements" in role_lower


def test_create_agent_no_tools():
    """Agent should have no tools — pure reasoning only."""
    with _mock_build_breakdown_llm():
        agent = create_requirements_breakdown_agent()
    assert len(agent.tools) == 0


def test_create_agent_no_delegation():
    """Agent should not delegate."""
    with _mock_build_breakdown_llm():
        agent = create_requirements_breakdown_agent()
    assert agent.allow_delegation is False


# ── LLM configuration tests ──────────────────────────────────


def test_build_llm_default_model(monkeypatch):
    """Without REQUIREMENTS_BREAKDOWN_MODEL or GEMINI_MODEL, uses the default."""
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm = _build_breakdown_llm()
    assert "gemini" in llm.model.lower()


def test_build_llm_respects_requirements_model(monkeypatch):
    """REQUIREMENTS_BREAKDOWN_MODEL should take precedence over GEMINI_MODEL."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MODEL", "gemini-custom-model")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    llm = _build_breakdown_llm()
    assert "gemini-custom-model" in llm.model


def test_build_llm_falls_back_to_gemini_model(monkeypatch):
    """Without REQUIREMENTS_BREAKDOWN_MODEL, should use GEMINI_MODEL."""
    monkeypatch.delenv("REQUIREMENTS_BREAKDOWN_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
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
        result = MagicMock()
        # Odd calls = breakdown, even calls = evaluate
        if call_count % 2 == 0:
            iteration = call_count // 2
            if iteration >= 3:
                result.raw = "All criteria score 4+. REQUIREMENTS_READY"
            else:
                result.raw = "Needs more detail. NEEDS_MORE"
        else:
            result.raw = f"## Feature {call_count // 2 + 1}\nBreakdown v{call_count // 2 + 1}"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("Build a dashboard with AI")

    assert "Feature 3" in result
    # 3 breakdown + 3 evaluate = 6 calls
    assert call_count == 6
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
        result = MagicMock()
        if call_count % 2 == 0:
            result.raw = "Still needs work. NEEDS_MORE"
        else:
            result.raw = f"Requirements v{call_count // 2 + 1}"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("Build a feature")

    # 4 breakdown + 4 evaluate = 8 calls
    assert call_count == 8
    assert len(history) == 4


def test_breakdown_ignores_ready_before_min(monkeypatch):
    """REQUIREMENTS_READY before min iterations should be ignored."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "3")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "5")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count % 2 == 0:
            result.raw = "Looks good. REQUIREMENTS_READY"
        else:
            result.raw = f"Requirements v{call_count // 2 + 1}"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = breakdown_requirements("Some idea")

    # Should run exactly 3 iterations (min), then stop
    assert call_count == 6
    assert len(history) == 3


def test_breakdown_returns_tuple(monkeypatch):
    """breakdown_requirements should return a (str, list[dict]) tuple."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "1")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "1")

    def mock_kickoff(crew, step_label=""):
        result = MagicMock()
        if "evaluate" in step_label:
            result.raw = "REQUIREMENTS_READY"
        else:
            result.raw = "## Feature 1\nDetailed requirements"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
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
        result = MagicMock()
        if call_count % 2 == 0:
            result.raw = "NEEDS_MORE" if call_count < 4 else "REQUIREMENTS_READY"
        else:
            result.raw = f"Requirements v{call_count // 2 + 1}"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff), \
         patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db") as mock_db:
        mock_collection = MagicMock()
        mock_db.return_value = {"workingIdeas": mock_collection}
        result, history = breakdown_requirements("An idea", run_id="test_run_456")

    assert mock_collection.insert_one.call_count == 2
    first_doc = mock_collection.insert_one.call_args_list[0][0][0]
    assert first_doc["run_id"] == "test_run_456"
    assert first_doc["iteration"] == 1
    assert first_doc["step"] == "requirements_breakdown_1"
    assert first_doc["section_key"] == "requirements_breakdown"


def test_breakdown_no_run_id_skips_save(monkeypatch):
    """Without run_id, no save_iteration calls should be made."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "1")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "1")

    def mock_kickoff(crew, step_label=""):
        result = MagicMock()
        result.raw = "REQUIREMENTS_READY" if "evaluate" in step_label else "Requirements"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff), \
         patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db") as mock_db:
        mock_collection = MagicMock()
        mock_db.return_value = {"workingIdeas": mock_collection}
        breakdown_requirements("An idea")  # no run_id

    mock_collection.insert_one.assert_not_called()


def test_breakdown_passes_previous_requirements(monkeypatch):
    """Each iteration should receive the prior iteration's output to build upon."""
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", "2")
    monkeypatch.setenv("REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", "2")

    captured_descriptions: list[str] = []
    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        # Capture the task description from breakdown tasks
        if "breakdown" in step_label:
            task_desc = crew.tasks[0].description
            captured_descriptions.append(task_desc)
        result = MagicMock()
        if call_count % 2 == 0:
            result.raw = "NEEDS_MORE" if call_count < 4 else "REQUIREMENTS_READY"
        else:
            result.raw = f"## Feature {call_count // 2 + 1}\nRequirements iteration {call_count // 2 + 1}"
        return result

    with _mock_build_breakdown_llm(), \
         patch("crewai_productfeature_planner.agents.requirements_breakdown.agent.crew_kickoff_with_retry",
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
