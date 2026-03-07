"""Tests for the unified Product Manager agent (OpenAI + Gemini backends)."""

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.product_manager.agent import (
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    create_product_manager,
    create_product_manager_critic,
    get_task_configs,
    _build_tools,
    _build_llm,
    _build_critic_llm,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_CRITIC_TIMEOUT,
    DEFAULT_CRITIC_MAX_RETRIES,
)


class _StubToolInput(BaseModel):
    query: str = Field(default="", description="stub")


class _StubTool(BaseTool):
    """Minimal BaseTool subclass that satisfies Pydantic validation."""

    name: str = "stub_tool"
    description: str = "A stub tool for testing."
    args_schema: type[BaseModel] = _StubToolInput

    def _run(self, query: str = "") -> str:
        return "stub"


def _mock_build_tools():
    """Patch _build_tools to return five stub BaseTool instances."""
    return patch(
        "crewai_productfeature_planner.agents.product_manager.agent._build_tools",
        return_value=[_StubTool() for _ in range(5)],
    )


def _mock_build_llm():
    """Patch _build_llm to return the model name string (avoids LLM init)."""
    return patch(
        "crewai_productfeature_planner.agents.product_manager.agent._build_llm",
        return_value="openai/o3",
    )


@pytest.fixture(autouse=True)
def _set_api_keys(monkeypatch):
    """Provide dummy API keys so Agent() doesn't fail on LLM init."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy-test-dummy-key")


# ── Agent factory tests (OpenAI — default) ───────────────────


def test_create_product_manager_role():
    """Agent should have the correct role."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert agent.role == "Senior Product Manager"


def test_create_product_manager_backstory_mentions_smart():
    """Backstory should reference the SMART criteria."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert "SMART" in agent.backstory


def test_create_product_manager_has_five_tools():
    """Agent should carry all five tools (no PRDFileWriteTool)."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert len(agent.tools) == 5


def test_create_product_manager_no_delegation():
    """Agent should not delegate to other agents."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert agent.allow_delegation is False


def test_create_product_manager_reasoning_enabled():
    """Agent should have reasoning enabled for plan-before-execute."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert agent.reasoning is True
    assert agent.max_reasoning_attempts == 3


# ── Agent factory tests (Gemini provider) ─────────────────────


def test_create_product_manager_gemini_role():
    """Gemini-backed agent should have the same role."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager(provider=PROVIDER_GEMINI)

    assert agent.role == "Senior Product Manager"


def test_create_product_manager_gemini_backstory_mentions_smart():
    """Gemini-backed backstory should reference SMART criteria."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager(provider=PROVIDER_GEMINI)

    assert "SMART" in agent.backstory


def test_create_product_manager_gemini_has_five_tools():
    """Gemini-backed agent should carry all five tools (no PRDFileWriteTool)."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager(provider=PROVIDER_GEMINI)

    assert len(agent.tools) == 5


def test_create_product_manager_gemini_no_delegation():
    """Gemini-backed agent should not delegate."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager(provider=PROVIDER_GEMINI)

    assert agent.allow_delegation is False


def test_create_product_manager_gemini_reasoning_enabled():
    """Gemini-backed agent should have reasoning enabled."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager(provider=PROVIDER_GEMINI)

    assert agent.reasoning is True
    assert agent.max_reasoning_attempts == 3


def test_create_product_manager_gemini_requires_key(monkeypatch):
    """Should raise EnvironmentError when no Google credentials are set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    with _mock_build_tools(), _mock_build_llm():
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            create_product_manager(provider=PROVIDER_GEMINI)


# ── Tool assembly tests ──────────────────────────────────────


def test_build_tools_returns_two_items():
    """_build_tools should assemble exactly two tools (FileRead + DirectoryRead)."""
    patches = [
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_file_read_tool",
            return_value=_StubTool(name="file_read"),
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_directory_read_tool",
            return_value=_StubTool(name="dir_read"),
        ),
    ]

    stack = contextlib.ExitStack()
    for p in patches:
        stack.enter_context(p)

    with stack:
        tools = _build_tools()

    assert len(tools) == 2


# ── Task configuration tests ─────────────────────────────────


def test_get_task_configs_has_all_tasks():
    """Task config YAML should define draft and critique tasks (no refine_prd_task)."""
    configs = get_task_configs()
    assert "draft_prd_task" in configs
    assert "critique_prd_task" in configs
    assert "refine_prd_task" not in configs


def test_draft_task_has_required_fields():
    """Each task config must have description, expected_output, and agent."""
    configs = get_task_configs()
    draft = configs["draft_prd_task"]
    assert "description" in draft
    assert "expected_output" in draft
    assert "agent" in draft


def test_critique_task_references_dod():
    """Critique task should mention Definition of Done and READY_FOR_DEV."""
    configs = get_task_configs()
    critique = configs["critique_prd_task"]
    assert "Definition of Done" in critique["description"]
    assert "READY_FOR_DEV" in critique["description"]


def test_critique_task_references_executive_summary():
    """Critique task should reference {executive_summary} and {critique} fields."""
    configs = get_task_configs()
    critique = configs["critique_prd_task"]
    assert "{executive_summary}" in critique["description"]
    assert "{critique}" in critique["description"]


def test_draft_task_references_executive_summary():
    """Draft task should reference {idea} and {executive_summary} fields."""
    configs = get_task_configs()
    draft = configs["draft_prd_task"]
    assert "{idea}" in draft["description"]
    assert "{executive_summary}" in draft["description"]


# ── OpenAI LLM configuration tests ───────────────────────────

def test_build_llm_uses_openai_model_env(monkeypatch):
    """OPENAI_RESEARCH_MODEL env var should set the model."""
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "gpt-4.1")
    llm = _build_llm(provider=PROVIDER_OPENAI)
    assert "gpt-4.1" in llm.model


def test_build_llm_defaults_to_o3(monkeypatch):
    """Without OPENAI_RESEARCH_MODEL env var, should default to o3."""
    monkeypatch.delenv("OPENAI_RESEARCH_MODEL", raising=False)
    llm = _build_llm(provider=PROVIDER_OPENAI)
    assert "o3" in llm.model


def test_build_llm_adds_openai_prefix(monkeypatch):
    """Model names without a provider prefix get 'openai/' prepended."""
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "o3")
    llm = _build_llm(provider=PROVIDER_OPENAI)
    # CrewAI normalises the model name; verify it resolved to an OpenAI provider.
    assert llm.model == "o3"


def test_build_llm_skips_prefix_when_qualified(monkeypatch):
    """Model names already containing '/' should not be double-prefixed."""
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "openai/gpt-4.1")
    llm = _build_llm(provider=PROVIDER_OPENAI)
    # CrewAI strips the provider prefix internally.
    assert llm.model == "gpt-4.1"


# ── Gemini LLM configuration tests ───────────────────────────


def test_build_llm_gemini_uses_gemini_pm_model_env(monkeypatch):
    """GEMINI_PM_MODEL env var should set the model for Gemini provider."""
    monkeypatch.setenv("GEMINI_PM_MODEL", "gemini-2.0-flash")
    llm = _build_llm(provider=PROVIDER_GEMINI)
    assert "gemini-2.0-flash" in llm.model


def test_build_llm_gemini_falls_back_to_gemini_research_model_env(monkeypatch):
    """Without GEMINI_PM_MODEL, should fall back to GEMINI_RESEARCH_MODEL."""
    monkeypatch.delenv("GEMINI_PM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_RESEARCH_MODEL", "gemini-2.5-flash-preview-04-17")
    llm = _build_llm(provider=PROVIDER_GEMINI)
    assert "gemini-2.5-flash-preview-04-17" in llm.model


def test_build_llm_gemini_defaults_to_research_model(monkeypatch):
    """Without any model env vars, should default to DEFAULT_GEMINI_RESEARCH_MODEL."""
    monkeypatch.delenv("GEMINI_PM_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_RESEARCH_MODEL", raising=False)
    llm = _build_llm(provider=PROVIDER_GEMINI)
    assert "gemini-3.1-pro-preview" in llm.model


def test_build_llm_gemini_adds_gemini_prefix(monkeypatch):
    """Model names without provider prefix get 'gemini/' prepended."""
    monkeypatch.setenv("GEMINI_PM_MODEL", "gemini-3-flash-preview")
    llm = _build_llm(provider=PROVIDER_GEMINI)
    assert "gemini" in llm.model.lower()


def test_build_llm_gemini_skips_prefix_when_qualified(monkeypatch):
    """Model names already containing '/' should not be double-prefixed."""
    monkeypatch.setenv("GEMINI_PM_MODEL", "gemini/gemini-2.0-flash")
    llm = _build_llm(provider=PROVIDER_GEMINI)
    assert "gemini-2.0-flash" in llm.model


# ── LLM timeout & retry configuration ────────────────────────


def test_build_llm_default_timeout(monkeypatch):
    """Without LLM_TIMEOUT env var, should use DEFAULT_LLM_TIMEOUT."""
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "o3")
    llm = _build_llm()
    assert llm.timeout == DEFAULT_LLM_TIMEOUT


def test_build_llm_custom_timeout(monkeypatch):
    """LLM_TIMEOUT env var should override the default."""
    monkeypatch.setenv("LLM_TIMEOUT", "120")
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "o3")
    llm = _build_llm()
    assert llm.timeout == 120


def test_build_llm_default_max_retries(monkeypatch):
    """Without LLM_MAX_RETRIES, should use DEFAULT_LLM_MAX_RETRIES."""
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "o3")
    llm = _build_llm()
    assert llm.max_retries == DEFAULT_LLM_MAX_RETRIES


def test_build_llm_custom_max_retries(monkeypatch):
    """LLM_MAX_RETRIES env var should override the default."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "o3")
    llm = _build_llm()
    assert llm.max_retries == 5


def test_default_constants():
    """Module-level defaults should be sensible."""
    assert DEFAULT_LLM_TIMEOUT == 300
    assert DEFAULT_LLM_MAX_RETRIES == 3


# ---------------------------------------------------------------------------
# Critic agent tests
# ---------------------------------------------------------------------------

def _mock_build_critic_llm():
    """Patch _build_critic_llm to return the model name string."""
    return patch(
        "crewai_productfeature_planner.agents.product_manager.agent._build_critic_llm",
        return_value="gemini/gemini-3-flash-preview",
    )


class TestCreateProductManagerCritic:
    """Tests for create_product_manager_critic."""

    def test_critic_requires_google_key(self, monkeypatch):
        """Should raise EnvironmentError without Google credentials."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            create_product_manager_critic()

    def test_critic_has_no_tools(self, monkeypatch):
        """Critic agent must have zero tools."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with _mock_build_critic_llm():
            agent = create_product_manager_critic()
        assert len(agent.tools) == 0

    def test_critic_no_delegation(self, monkeypatch):
        """Critic must not delegate."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with _mock_build_critic_llm():
            agent = create_product_manager_critic()
        assert agent.allow_delegation is False

    def test_critic_reasoning_enabled(self, monkeypatch):
        """Critic should use reasoning with 3 attempts."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with _mock_build_critic_llm():
            agent = create_product_manager_critic()
        assert agent.reasoning is True
        assert agent.max_reasoning_attempts == 3

    def test_critic_role_matches_pm(self, monkeypatch):
        """Critic shares the PM role from agent.yaml."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with _mock_build_critic_llm():
            agent = create_product_manager_critic()
        assert agent.role  # non-empty string

    def test_critic_accepts_project_id(self, monkeypatch):
        """Critic creation should accept project_id without error."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with _mock_build_critic_llm(), \
             patch("crewai_productfeature_planner.agents.product_manager.agent.enrich_backstory",
                   return_value="enriched backstory"):
            agent = create_product_manager_critic(project_id="test-project")
        assert agent.backstory == "enriched backstory"


class TestBuildCriticLlm:
    """Tests for _build_critic_llm."""

    def test_default_model(self, monkeypatch):
        """Without env vars, uses DEFAULT_GEMINI_MODEL."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.delenv("GEMINI_CRITIC_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        llm = _build_critic_llm()
        # Should contain the default flash model
        assert "gemini" in llm.model

    def test_critic_model_env_var(self, monkeypatch):
        """GEMINI_CRITIC_MODEL should override all other model vars."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_CRITIC_MODEL", "gemini-custom-critic")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-should-not-use")
        llm = _build_critic_llm()
        assert "gemini-custom-critic" in llm.model
        assert "should-not-use" not in llm.model

    def test_falls_back_to_gemini_model(self, monkeypatch):
        """Without GEMINI_CRITIC_MODEL, should fall back to GEMINI_MODEL."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.delenv("GEMINI_CRITIC_MODEL", raising=False)
        monkeypatch.setenv("GEMINI_MODEL", "gemini-basic-fallback")
        llm = _build_critic_llm()
        assert "gemini-basic-fallback" in llm.model

    def test_default_timeout_passed_to_constructor(self, monkeypatch):
        """Without env vars, passes DEFAULT_CRITIC_TIMEOUT to LLM()."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.delenv("CRITIC_LLM_TIMEOUT", raising=False)
        monkeypatch.delenv("LLM_TIMEOUT", raising=False)
        with patch(
            "crewai_productfeature_planner.agents.product_manager.agent.LLM",
            return_value=MagicMock(),
        ) as mock_llm:
            _build_critic_llm()
        _, kwargs = mock_llm.call_args
        assert kwargs["timeout"] == DEFAULT_CRITIC_TIMEOUT

    def test_critic_timeout_env_var(self, monkeypatch):
        """CRITIC_LLM_TIMEOUT overrides LLM_TIMEOUT for the critic."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("CRITIC_LLM_TIMEOUT", "60")
        monkeypatch.setenv("LLM_TIMEOUT", "300")
        with patch(
            "crewai_productfeature_planner.agents.product_manager.agent.LLM",
            return_value=MagicMock(),
        ) as mock_llm:
            _build_critic_llm()
        _, kwargs = mock_llm.call_args
        assert kwargs["timeout"] == 60

    def test_falls_back_to_llm_timeout(self, monkeypatch):
        """Without CRITIC_LLM_TIMEOUT, falls back to LLM_TIMEOUT."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.delenv("CRITIC_LLM_TIMEOUT", raising=False)
        monkeypatch.setenv("LLM_TIMEOUT", "200")
        with patch(
            "crewai_productfeature_planner.agents.product_manager.agent.LLM",
            return_value=MagicMock(),
        ) as mock_llm:
            _build_critic_llm()
        _, kwargs = mock_llm.call_args
        assert kwargs["timeout"] == 200

    def test_default_max_retries_passed_to_constructor(self, monkeypatch):
        """Without LLM_MAX_RETRIES, passes DEFAULT_CRITIC_MAX_RETRIES."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
        with patch(
            "crewai_productfeature_planner.agents.product_manager.agent.LLM",
            return_value=MagicMock(),
        ) as mock_llm:
            _build_critic_llm()
        _, kwargs = mock_llm.call_args
        assert kwargs["max_retries"] == DEFAULT_CRITIC_MAX_RETRIES

    def test_custom_max_retries(self, monkeypatch):
        """LLM_MAX_RETRIES env var should override the default."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MAX_RETRIES", "7")
        with patch(
            "crewai_productfeature_planner.agents.product_manager.agent.LLM",
            return_value=MagicMock(),
        ) as mock_llm:
            _build_critic_llm()
        _, kwargs = mock_llm.call_args
        assert kwargs["max_retries"] == 7


def test_critic_default_constants():
    """Critic module-level defaults should be sensible."""
    assert DEFAULT_CRITIC_TIMEOUT == 120
    assert DEFAULT_CRITIC_MAX_RETRIES == 3
