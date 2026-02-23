"""Tests for the Gemini Product Manager agent configuration and factory."""

import contextlib
from unittest.mock import patch

import pytest
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.gemini_product_manager.agent import (
    create_gemini_product_manager,
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
        "crewai_productfeature_planner.agents.gemini_product_manager.agent._build_tools",
        return_value=[_StubTool() for _ in range(6)],
    )


def _mock_build_llm():
    """Patch _build_llm to return the model name string (avoids LLM init)."""
    return patch(
        "crewai_productfeature_planner.agents.gemini_product_manager.agent._build_llm",
        return_value="gemini/gemini-3-flash-preview",
    )


@pytest.fixture(autouse=True)
def _set_gemini_key(monkeypatch):
    """Provide a dummy GOOGLE_API_KEY so Agent() doesn't fail on LLM init."""
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy-test-dummy-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")


# ── Agent factory tests ──────────────────────────────────────


def test_create_gemini_product_manager_role():
    """Agent should have the correct role."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_gemini_product_manager()

    assert agent.role == "Senior Product Manager"


def test_create_gemini_product_manager_backstory_mentions_smart():
    """Backstory should reference the SMART criteria."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_gemini_product_manager()

    assert "SMART" in agent.backstory


def test_create_gemini_product_manager_has_six_tools():
    """Agent should carry all six tools."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_gemini_product_manager()

    assert len(agent.tools) == 6


def test_create_gemini_product_manager_no_delegation():
    """Agent should not delegate to other agents."""
    with _mock_build_tools(), _mock_build_llm():
        agent = create_gemini_product_manager()

    assert agent.allow_delegation is False


def test_create_gemini_product_manager_requires_key(monkeypatch):
    """Should raise EnvironmentError when no Google credentials are set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    with _mock_build_tools(), _mock_build_llm():
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            create_gemini_product_manager()


# ── Tool assembly tests ──────────────────────────────────────


def test_build_tools_returns_six_items():
    """_build_tools should assemble exactly six tools."""
    patches = [
        patch(
            "crewai_productfeature_planner.agents.gemini_product_manager.agent.create_search_tool",
            return_value=_StubTool(name="search"),
        ),
        patch(
            "crewai_productfeature_planner.agents.gemini_product_manager.agent.create_scrape_tool",
            return_value=_StubTool(name="scrape"),
        ),
        patch(
            "crewai_productfeature_planner.agents.gemini_product_manager.agent.create_file_read_tool",
            return_value=_StubTool(name="file_read"),
        ),
        patch(
            "crewai_productfeature_planner.agents.gemini_product_manager.agent.create_directory_read_tool",
            return_value=_StubTool(name="dir_read"),
        ),
        patch(
            "crewai_productfeature_planner.agents.gemini_product_manager.agent.create_website_search_tool",
            return_value=_StubTool(name="web_search"),
        ),
    ]

    stack = contextlib.ExitStack()
    for p in patches:
        stack.enter_context(p)

    with stack:
        tools = _build_tools()

    assert len(tools) == 6


# ── Task configuration tests ─────────────────────────────────


def test_get_task_configs_has_all_tasks():
    """Task config should define draft and critique tasks."""
    configs = get_task_configs()
    assert "draft_prd_task" in configs
    assert "critique_prd_task" in configs


def test_task_configs_match_product_manager():
    """Gemini PM should share the same task configs as OpenAI PM."""
    from crewai_productfeature_planner.agents.product_manager.agent import (
        get_task_configs as openai_get_task_configs,
    )
    gemini_configs = get_task_configs()
    openai_configs = openai_get_task_configs()

    assert set(gemini_configs.keys()) == set(openai_configs.keys())


# ── LLM configuration tests ──────────────────────────────────


def test_build_llm_uses_gemini_pm_model_env(monkeypatch):
    """GEMINI_PM_MODEL env var should set the model."""
    monkeypatch.setenv("GEMINI_PM_MODEL", "gemini-2.0-flash")
    llm = _build_llm()
    assert "gemini-2.0-flash" in llm.model


def test_build_llm_falls_back_to_gemini_model_env(monkeypatch):
    """Without GEMINI_PM_MODEL, should fall back to GEMINI_MODEL."""
    monkeypatch.delenv("GEMINI_PM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-preview-04-17")
    llm = _build_llm()
    assert "gemini-2.5-flash-preview-04-17" in llm.model


def test_build_llm_defaults_to_gemini_3_flash(monkeypatch):
    """Without any model env vars, should default to gemini-3-flash-preview."""
    monkeypatch.delenv("GEMINI_PM_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm = _build_llm()
    assert "gemini-3-flash-preview" in llm.model


def test_build_llm_adds_gemini_prefix(monkeypatch):
    """Model names without provider prefix get 'gemini/' prepended."""
    monkeypatch.setenv("GEMINI_PM_MODEL", "gemini-3-flash-preview")
    llm = _build_llm()
    # CrewAI normalises the model name; verify it contains gemini
    assert "gemini" in llm.model.lower()


def test_build_llm_skips_prefix_when_qualified(monkeypatch):
    """Model names already containing '/' should not be double-prefixed."""
    monkeypatch.setenv("GEMINI_PM_MODEL", "gemini/gemini-2.0-flash")
    llm = _build_llm()
    assert "gemini-2.0-flash" in llm.model


# ── LLM timeout & retry configuration ────────────────────────


def test_default_constants():
    """Module-level defaults should be sensible."""
    assert DEFAULT_LLM_TIMEOUT == 300
    assert DEFAULT_LLM_MAX_RETRIES == 3
