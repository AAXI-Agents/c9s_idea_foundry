"""Tests for the Product Manager agent configuration and factory."""

from unittest.mock import MagicMock, patch

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.product_manager.agent import (
    create_product_manager,
    get_task_configs,
    _build_tools,
    _build_llm,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_MAX_RETRIES,
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
    """Patch _build_tools to return six stub BaseTool instances."""
    return patch(
        "crewai_productfeature_planner.agents.product_manager.agent._build_tools",
        return_value=[_StubTool() for _ in range(6)],
    )


def _mock_build_llm():
    """Patch _build_llm to return the model name string (avoids LLM init)."""
    return patch(
        "crewai_productfeature_planner.agents.product_manager.agent._build_llm",
        return_value="openai/o3",
    )


import pytest


@pytest.fixture(autouse=True)
def _set_openai_key(monkeypatch):
    """Provide a dummy OPENAI_API_KEY so Agent() doesn't fail on LLM init."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")


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


def test_create_product_manager_has_six_tools():
    """Agent should carry all six tools."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert len(agent.tools) == 6


def test_create_product_manager_no_delegation():
    """Agent should not delegate to other agents."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_product_manager()

    assert agent.allow_delegation is False


def test_build_tools_returns_six_items():
    """_build_tools should assemble exactly six tools."""
    import contextlib

    patches = [
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_search_tool",
            return_value=_StubTool(name="search"),
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_scrape_tool",
            return_value=_StubTool(name="scrape"),
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_file_read_tool",
            return_value=_StubTool(name="file_read"),
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_directory_read_tool",
            return_value=_StubTool(name="dir_read"),
        ),
        patch(
            "crewai_productfeature_planner.agents.product_manager.agent.create_website_search_tool",
            return_value=_StubTool(name="web_search"),
        ),
    ]

    stack = contextlib.ExitStack()
    for p in patches:
        stack.enter_context(p)

    with stack:
        tools = _build_tools()

    assert len(tools) == 6


def test_get_task_configs_has_all_tasks():
    """Task config YAML should define draft, critique, and refine tasks."""
    configs = get_task_configs()
    assert "draft_prd_task" in configs
    assert "critique_prd_task" in configs
    assert "refine_prd_task" in configs


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


def test_refine_task_accepts_draft_and_critique():
    """Refine task template should accept both {draft} and {critique}."""
    configs = get_task_configs()
    refine = configs["refine_prd_task"]
    assert "{draft}" in refine["description"]
    assert "{critique}" in refine["description"]


# ── LLM configuration tests ──────────────────────────────────

def test_build_llm_uses_pm_model_env(monkeypatch):
    """PM_MODEL env var should take priority over MODEL."""
    monkeypatch.setenv("PM_MODEL", "gpt-4.1")
    monkeypatch.setenv("MODEL", "o3")
    llm = _build_llm()
    assert "gpt-4.1" in llm.model


def test_build_llm_falls_back_to_model_env(monkeypatch):
    """Without PM_MODEL, should fall back to MODEL env var."""
    monkeypatch.delenv("PM_MODEL", raising=False)
    monkeypatch.setenv("MODEL", "gpt-4.1")
    llm = _build_llm()
    assert "gpt-4.1" in llm.model


def test_build_llm_defaults_to_o3(monkeypatch):
    """Without any env var set, should default to o3."""
    monkeypatch.delenv("PM_MODEL", raising=False)
    monkeypatch.delenv("MODEL", raising=False)
    llm = _build_llm()
    assert "o3" in llm.model


def test_build_llm_adds_openai_prefix(monkeypatch):
    """Model names without a provider prefix get 'openai/' prepended."""
    monkeypatch.setenv("PM_MODEL", "o3")
    llm = _build_llm()
    # CrewAI normalises the model name; verify it resolved to an OpenAI provider.
    assert llm.model == "o3"


def test_build_llm_skips_prefix_when_qualified(monkeypatch):
    """Model names already containing '/' should not be double-prefixed."""
    monkeypatch.setenv("PM_MODEL", "openai/gpt-4.1")
    llm = _build_llm()
    # CrewAI strips the provider prefix internally.
    assert llm.model == "gpt-4.1"


# ── LLM timeout & retry configuration ────────────────────────


def test_build_llm_default_timeout(monkeypatch):
    """Without LLM_TIMEOUT env var, should use DEFAULT_LLM_TIMEOUT."""
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.setenv("PM_MODEL", "o3")
    llm = _build_llm()
    assert llm.timeout == DEFAULT_LLM_TIMEOUT


def test_build_llm_custom_timeout(monkeypatch):
    """LLM_TIMEOUT env var should override the default."""
    monkeypatch.setenv("LLM_TIMEOUT", "120")
    monkeypatch.setenv("PM_MODEL", "o3")
    llm = _build_llm()
    assert llm.timeout == 120


def test_build_llm_default_max_retries(monkeypatch):
    """Without LLM_MAX_RETRIES, should use DEFAULT_LLM_MAX_RETRIES."""
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
    monkeypatch.setenv("PM_MODEL", "o3")
    llm = _build_llm()
    assert llm.max_retries == DEFAULT_LLM_MAX_RETRIES


def test_build_llm_custom_max_retries(monkeypatch):
    """LLM_MAX_RETRIES env var should override the default."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("PM_MODEL", "o3")
    llm = _build_llm()
    assert llm.max_retries == 5


def test_default_constants():
    """Module-level defaults should be sensible."""
    assert DEFAULT_LLM_TIMEOUT == 300
    assert DEFAULT_LLM_MAX_RETRIES == 3
