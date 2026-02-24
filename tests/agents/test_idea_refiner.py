"""Tests for the Idea Refinement agent configuration and runner."""

from unittest.mock import MagicMock, patch, call

import pytest

from crewai_productfeature_planner.agents.idea_refiner.agent import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MIN_ITERATIONS,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_MAX_RETRIES,
    _build_refiner_llm,
    _get_iteration_limits,
    _load_yaml,
    create_idea_refiner,
    refine_idea,
)


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    """Provide dummy API keys."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


def _mock_build_refiner_llm():
    return patch(
        "crewai_productfeature_planner.agents.idea_refiner.agent._build_refiner_llm",
        return_value="gemini/gemini-3-flash-preview",
    )


# ── Factory tests ─────────────────────────────────────────────


def test_create_idea_refiner_requires_credentials(monkeypatch):
    """Should raise EnvironmentError when neither GOOGLE_API_KEY nor GOOGLE_CLOUD_PROJECT is set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
        with _mock_build_refiner_llm():
            create_idea_refiner()


def test_create_idea_refiner_accepts_api_key(monkeypatch):
    """Should succeed with only GOOGLE_API_KEY set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with _mock_build_refiner_llm():
        agent = create_idea_refiner()
    assert "Expert" in agent.role or "expert" in agent.role.lower()


def test_create_idea_refiner_accepts_project(monkeypatch):
    """Should succeed with only GOOGLE_CLOUD_PROJECT set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    with _mock_build_refiner_llm():
        agent = create_idea_refiner()
    assert agent is not None


def test_create_idea_refiner_role():
    """Agent should have a role mentioning expert or user."""
    with _mock_build_refiner_llm():
        agent = create_idea_refiner()
    role_lower = agent.role.lower()
    assert "expert" in role_lower or "user" in role_lower


def test_create_idea_refiner_no_tools():
    """Agent should have no tools — pure reasoning only."""
    with _mock_build_refiner_llm():
        agent = create_idea_refiner()
    assert len(agent.tools) == 0


def test_create_idea_refiner_no_delegation():
    """Agent should not delegate."""
    with _mock_build_refiner_llm():
        agent = create_idea_refiner()
    assert agent.allow_delegation is False

def test_create_idea_refiner_reasoning_enabled():
    """Agent should have reasoning enabled for plan-before-execute."""
    with _mock_build_refiner_llm():
        agent = create_idea_refiner()
    assert agent.reasoning is True
    assert agent.max_reasoning_attempts == 3

# ── LLM configuration tests ──────────────────────────────────


def test_build_refiner_llm_default_model(monkeypatch):
    """Without IDEA_REFINER_MODEL or GEMINI_MODEL, uses the default."""
    monkeypatch.delenv("IDEA_REFINER_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm = _build_refiner_llm()
    assert "gemini" in llm.model.lower()


def test_build_refiner_llm_respects_idea_refiner_model(monkeypatch):
    """IDEA_REFINER_MODEL should take precedence over GEMINI_MODEL."""
    monkeypatch.setenv("IDEA_REFINER_MODEL", "gemini-custom-model")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    llm = _build_refiner_llm()
    assert "gemini-custom-model" in llm.model


def test_build_refiner_llm_falls_back_to_gemini_model(monkeypatch):
    """Without IDEA_REFINER_MODEL, should use GEMINI_MODEL."""
    monkeypatch.delenv("IDEA_REFINER_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    llm = _build_refiner_llm()
    assert "gemini-2.5-pro" in llm.model


def test_build_refiner_llm_adds_prefix(monkeypatch):
    """Model names without '/' should get 'gemini/' prepended."""
    monkeypatch.setenv("IDEA_REFINER_MODEL", "gemini-3-flash-preview")
    llm = _build_refiner_llm()
    # LiteLLM / GeminiCompletion may strip the prefix, but the model should include gemini
    assert "gemini" in llm.model.lower()


def test_build_refiner_llm_no_double_prefix(monkeypatch):
    """Already-qualified model names should not be double-prefixed."""
    monkeypatch.setenv("IDEA_REFINER_MODEL", "gemini/gemini-3-flash-preview")
    llm = _build_refiner_llm()
    assert "gemini/gemini/" not in llm.model


# ── Iteration limits ─────────────────────────────────────────


def test_iteration_limits_defaults(monkeypatch):
    """Default limits should be (3, 10)."""
    monkeypatch.delenv("IDEA_REFINER_MIN_ITERATIONS", raising=False)
    monkeypatch.delenv("IDEA_REFINER_MAX_ITERATIONS", raising=False)
    min_i, max_i = _get_iteration_limits()
    assert min_i == DEFAULT_MIN_ITERATIONS
    assert max_i == DEFAULT_MAX_ITERATIONS


def test_iteration_limits_from_env(monkeypatch):
    """Env vars should override defaults."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "5")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "8")
    min_i, max_i = _get_iteration_limits()
    assert min_i == 5
    assert max_i == 8


def test_iteration_limits_clamp_min(monkeypatch):
    """Min should be clamped to at least 1."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "0")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "5")
    min_i, max_i = _get_iteration_limits()
    assert min_i == 1
    assert max_i == 5


def test_iteration_limits_max_at_least_min(monkeypatch):
    """Max should be at least min."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "7")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "3")
    min_i, max_i = _get_iteration_limits()
    assert max_i >= min_i


def test_iteration_limits_cap(monkeypatch):
    """Max should be capped at 20, min at 10."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "50")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "100")
    min_i, max_i = _get_iteration_limits()
    assert min_i <= 10
    assert max_i <= 20


# ── YAML loading ──────────────────────────────────────────────


def test_load_agent_yaml():
    """Agent YAML should contain idea_refiner key."""
    config = _load_yaml("agent.yaml")
    assert "idea_refiner" in config
    assert "role" in config["idea_refiner"]
    assert "goal" in config["idea_refiner"]
    assert "backstory" in config["idea_refiner"]


def test_load_tasks_yaml():
    """Tasks YAML should contain refine and evaluate tasks."""
    config = _load_yaml("tasks.yaml")
    assert "refine_idea_task" in config
    assert "evaluate_quality_task" in config


# ── Constants ─────────────────────────────────────────────────


def test_default_constants():
    """Module-level defaults should be sensible."""
    assert DEFAULT_MIN_ITERATIONS == 3
    assert DEFAULT_MAX_ITERATIONS == 10
    assert DEFAULT_LLM_TIMEOUT == 300
    assert DEFAULT_LLM_MAX_RETRIES == 3


# ── refine_idea runner ────────────────────────────────────────


def test_refine_idea_stops_at_idea_ready(monkeypatch):
    """Should stop after min iterations when evaluator returns IDEA_READY."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "3")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "10")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        # Set refine_task output on the crew's first task
        refine_output = MagicMock()
        refine_output.raw = f"Refined idea version {call_count}"
        crew.tasks[0].output = refine_output
        # Return evaluation result (last task output)
        result = MagicMock()
        if call_count >= 3:
            result.raw = "All criteria score 4+. IDEA_READY"
        else:
            result.raw = "Needs more detail. NEEDS_MORE"
        return result

    with _mock_build_refiner_llm(), \
         patch("crewai_productfeature_planner.agents.idea_refiner.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = refine_idea("Build a dashboard")

    assert "Refined idea version 3" in result
    # 1 merged crew kickoff per iteration = 3 calls
    assert call_count == 3
    assert len(history) == 3
    assert history[0]["iteration"] == 1
    assert history[2]["iteration"] == 3
    assert "idea" in history[0]
    assert "evaluation" in history[0]


def test_refine_idea_runs_max_iterations(monkeypatch):
    """Should stop at max_iterations even if not IDEA_READY."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "2")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "4")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        refine_output = MagicMock()
        refine_output.raw = f"Refined idea v{call_count}"
        crew.tasks[0].output = refine_output
        result = MagicMock()
        result.raw = "Still needs work. NEEDS_MORE"
        return result

    with _mock_build_refiner_llm(), \
         patch("crewai_productfeature_planner.agents.idea_refiner.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = refine_idea("Build a feature")

    # 1 merged crew kickoff per iteration = 4 calls (max 4 iterations)
    assert call_count == 4
    assert len(history) == 4


def test_refine_idea_ignores_ready_before_min(monkeypatch):
    """IDEA_READY before min iterations should be ignored."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "3")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "5")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        refine_output = MagicMock()
        refine_output.raw = f"Refined v{call_count}"
        crew.tasks[0].output = refine_output
        result = MagicMock()
        # Always say IDEA_READY — but should be ignored before iter 3
        result.raw = "Looks good. IDEA_READY"
        return result

    with _mock_build_refiner_llm(), \
         patch("crewai_productfeature_planner.agents.idea_refiner.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = refine_idea("Some idea")

    # Should run exactly 3 iterations (min), then stop at IDEA_READY on iter 3
    # 1 merged crew kickoff per iteration = 3 calls
    assert call_count == 3
    assert len(history) == 3


def test_refine_idea_returns_tuple(monkeypatch):
    """refine_idea should return a (str, list[dict]) tuple."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "1")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "1")

    def mock_kickoff(crew, step_label=""):
        refine_output = MagicMock()
        refine_output.raw = "Enriched idea content"
        crew.tasks[0].output = refine_output
        result = MagicMock()
        result.raw = "IDEA_READY"
        return result

    with _mock_build_refiner_llm(), \
         patch("crewai_productfeature_planner.agents.idea_refiner.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff):
        result, history = refine_idea("Raw idea")

    assert isinstance(result, str)
    assert len(result) > 0
    assert isinstance(history, list)
    assert len(history) == 1
    assert history[0]["iteration"] == 1
    assert history[0]["idea"] == "Enriched idea content"
    assert history[0]["evaluation"] == "IDEA_READY"


def test_refine_idea_saves_iterations_with_run_id(monkeypatch):
    """When run_id is provided, each iteration should be saved to workingIdeas."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "1")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "2")

    call_count = 0

    def mock_kickoff(crew, step_label=""):
        nonlocal call_count
        call_count += 1
        refine_output = MagicMock()
        refine_output.raw = f"Refined v{call_count}"
        crew.tasks[0].output = refine_output
        result = MagicMock()
        result.raw = "Still improving. NEEDS_MORE" if call_count < 2 else "IDEA_READY"
        return result

    with _mock_build_refiner_llm(), \
         patch("crewai_productfeature_planner.agents.idea_refiner.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff), \
         patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db") as mock_db:
        mock_collection = MagicMock()
        mock_db.return_value = {"workingIdeas": mock_collection}
        result, history = refine_idea("Raw idea", run_id="test_run_123")

    assert mock_collection.update_one.call_count == 2
    # Verify first saved doc uses upsert with correct run_id filter
    first_call = mock_collection.update_one.call_args_list[0]
    assert first_call[0][0] == {"run_id": "test_run_123"}
    assert first_call[1].get("upsert") is True


def test_refine_idea_no_run_id_skips_save(monkeypatch):
    """Without run_id, no save_iteration calls should be made."""
    monkeypatch.setenv("IDEA_REFINER_MIN_ITERATIONS", "1")
    monkeypatch.setenv("IDEA_REFINER_MAX_ITERATIONS", "1")

    def mock_kickoff(crew, step_label=""):
        refine_output = MagicMock()
        refine_output.raw = "Refined"
        crew.tasks[0].output = refine_output
        result = MagicMock()
        result.raw = "IDEA_READY"
        return result

    with _mock_build_refiner_llm(), \
         patch("crewai_productfeature_planner.agents.idea_refiner.agent.crew_kickoff_with_retry",
               side_effect=mock_kickoff), \
         patch("crewai_productfeature_planner.mongodb.working_ideas.repository.get_db") as mock_db:
        mock_collection = MagicMock()
        mock_db.return_value = {"workingIdeas": mock_collection}
        refine_idea("Raw idea")  # no run_id

    mock_collection.update_one.assert_not_called()
