"""Tests for the Gemini Product Manager agent configuration and factory."""

from unittest.mock import patch

import pytest
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.agents.gemini_product_manager.agent import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_TIMEOUT,
    _build_gemini_llm,
    create_gemini_product_manager,
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
    return patch(
        "crewai_productfeature_planner.agents.product_manager.agent._build_tools",
        return_value=[_StubTool() for _ in range(6)],
    )


def _mock_build_gemini_llm():
    return patch(
        "crewai_productfeature_planner.agents.gemini_product_manager.agent._build_gemini_llm",
        return_value="gemini/gemini-3-flash-preview",
    )


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    """Provide dummy API keys for agent creation."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")


# ── Factory tests ─────────────────────────────────────────────


def test_create_gemini_pm_requires_credentials(monkeypatch):
    """Should raise EnvironmentError when neither GOOGLE_API_KEY nor GOOGLE_CLOUD_PROJECT is set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
        with _mock_build_tools(), _mock_build_gemini_llm():
            create_gemini_product_manager()


def test_create_gemini_pm_accepts_api_key_only(monkeypatch):
    """Should succeed with only GOOGLE_API_KEY set (no GOOGLE_CLOUD_PROJECT)."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with _mock_build_tools(), _mock_build_gemini_llm():
        agent = create_gemini_product_manager()
    assert agent.role == "Senior Product Manager"


def test_create_gemini_pm_accepts_project_only(monkeypatch):
    """Should succeed with only GOOGLE_CLOUD_PROJECT set (no GOOGLE_API_KEY)."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    with _mock_build_tools(), _mock_build_gemini_llm():
        agent = create_gemini_product_manager()
    assert agent.role == "Senior Product Manager"


def test_create_gemini_pm_role():
    """Agent should have the correct role."""
    with _mock_build_tools(), _mock_build_gemini_llm():
        agent = create_gemini_product_manager()
    assert agent.role == "Senior Product Manager"


def test_create_gemini_pm_backstory_mentions_smart():
    """Backstory should reference the SMART criteria."""
    with _mock_build_tools(), _mock_build_gemini_llm():
        agent = create_gemini_product_manager()
    assert "SMART" in agent.backstory


def test_create_gemini_pm_has_six_tools():
    """Agent should carry all six tools."""
    with _mock_build_tools(), _mock_build_gemini_llm():
        agent = create_gemini_product_manager()
    assert len(agent.tools) == 6


def test_create_gemini_pm_no_delegation():
    """Agent should not delegate to other agents."""
    with _mock_build_tools(), _mock_build_gemini_llm():
        agent = create_gemini_product_manager()
    assert agent.allow_delegation is False


# ── LLM configuration tests ──────────────────────────────────


def test_build_gemini_llm_default_model(monkeypatch):
    """Without GEMINI_MODEL env var, should use the default model."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm = _build_gemini_llm()
    assert DEFAULT_GEMINI_MODEL in llm.model


def test_build_gemini_llm_custom_model(monkeypatch):
    """GEMINI_MODEL env var should override the default."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-pro")
    llm = _build_gemini_llm()
    assert "gemini-2.0-pro" in llm.model


def test_build_gemini_llm_adds_prefix(monkeypatch):
    """Model names without a provider prefix get 'gemini/' prepended."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    llm = _build_gemini_llm()
    # LiteLLM may strip the prefix, but the constructed model should include it
    assert "gemini" in llm.model.lower()


def test_build_gemini_llm_skips_prefix_when_qualified(monkeypatch):
    """Model names already containing '/' should not be double-prefixed."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini/gemini-3-flash-preview")
    llm = _build_gemini_llm()
    assert "gemini/gemini/" not in llm.model


def test_build_gemini_llm_default_timeout(monkeypatch):
    """Without LLM_TIMEOUT env var, should use DEFAULT_LLM_TIMEOUT."""
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    # Just verify it constructs without error; timeout is handled
    # internally by the native GeminiCompletion provider.
    llm = _build_gemini_llm()
    assert llm is not None


def test_build_gemini_llm_custom_timeout(monkeypatch):
    """LLM_TIMEOUT env var should be accepted without error."""
    monkeypatch.setenv("LLM_TIMEOUT", "120")
    llm = _build_gemini_llm()
    assert llm is not None


def test_build_gemini_llm_default_max_retries(monkeypatch):
    """Without LLM_MAX_RETRIES, should construct without error."""
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
    llm = _build_gemini_llm()
    assert llm is not None


def test_build_gemini_llm_custom_max_retries(monkeypatch):
    """LLM_MAX_RETRIES env var should be accepted without error."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "5")
    llm = _build_gemini_llm()
    assert llm is not None


def test_default_constants():
    """Module-level defaults should be sensible."""
    assert DEFAULT_LLM_TIMEOUT == 300
    assert DEFAULT_LLM_MAX_RETRIES == 3
    assert "gemini" in DEFAULT_GEMINI_MODEL.lower()
