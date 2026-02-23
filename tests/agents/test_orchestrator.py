"""Tests for the Orchestrator agent factory and configuration."""

from unittest.mock import patch

import pytest

from crewai_productfeature_planner.agents.orchestrator.agent import (
    CONFIG_DIR,
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_TIMEOUT,
    _build_llm,
    _build_tools,
    _load_yaml,
    create_orchestrator_agent,
    get_task_configs,
)


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    """Provide dummy API keys."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


def _mock_build_llm():
    return patch(
        "crewai_productfeature_planner.agents.orchestrator.agent._build_llm",
        return_value="gemini/gemini-3-flash-preview",
    )


# ── YAML config loading ──────────────────────────────────────────────


class TestLoadYaml:

    def test_loads_agent_yaml(self):
        data = _load_yaml("agent.yaml")
        assert "orchestrator" in data
        assert "role" in data["orchestrator"]
        assert "goal" in data["orchestrator"]
        assert "backstory" in data["orchestrator"]

    def test_loads_tasks_yaml(self):
        data = _load_yaml("tasks.yaml")
        assert "publish_to_confluence_task" in data
        assert "create_jira_epic_task" in data
        assert "create_jira_tickets_task" in data

    def test_config_dir_exists(self):
        assert CONFIG_DIR.is_dir()


# ── Tool assembly ────────────────────────────────────────────────────


def test_build_tools_returns_two():
    tools = _build_tools()
    assert len(tools) == 2


def test_build_tools_has_confluence():
    from crewai_productfeature_planner.tools.confluence_tool import ConfluencePublishTool
    tools = _build_tools()
    assert any(isinstance(t, ConfluencePublishTool) for t in tools)


def test_build_tools_has_jira():
    from crewai_productfeature_planner.tools.jira_tool import JiraCreateIssueTool
    tools = _build_tools()
    assert any(isinstance(t, JiraCreateIssueTool) for t in tools)


# ── LLM configuration ───────────────────────────────────────────────


def test_build_llm_default_model(monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm = _build_llm()
    assert "gemini" in llm.model.lower()


def test_build_llm_respects_orchestrator_model(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_MODEL", "gemini-custom-orch")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    llm = _build_llm()
    assert "gemini-custom-orch" in llm.model


def test_build_llm_falls_back_to_gemini_model(monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    llm = _build_llm()
    assert "gemini-2.5-pro" in llm.model


def test_build_llm_adds_prefix(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_MODEL", "gemini-3-flash-preview")
    llm = _build_llm()
    assert "gemini" in llm.model.lower()


# ── Agent factory ────────────────────────────────────────────────────


class TestCreateOrchestratorAgent:

    def test_requires_credentials(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            with _mock_build_llm():
                create_orchestrator_agent()

    def test_accepts_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        with _mock_build_llm():
            agent = create_orchestrator_agent()
        assert agent is not None

    def test_accepts_project(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
        with _mock_build_llm():
            agent = create_orchestrator_agent()
        assert agent is not None

    def test_role_mentions_orchestrator(self):
        with _mock_build_llm():
            agent = create_orchestrator_agent()
        assert "orchestrator" in agent.role.lower() or "coordinator" in agent.role.lower()

    def test_has_two_tools(self):
        with _mock_build_llm():
            agent = create_orchestrator_agent()
        assert len(agent.tools) == 2

    def test_no_delegation(self):
        with _mock_build_llm():
            agent = create_orchestrator_agent()
        assert agent.allow_delegation is False


# ── Task configs ─────────────────────────────────────────────────────


class TestGetTaskConfigs:

    def test_returns_dict(self):
        configs = get_task_configs()
        assert isinstance(configs, dict)

    def test_has_publish_to_confluence_task(self):
        configs = get_task_configs()
        assert "publish_to_confluence_task" in configs
        assert "description" in configs["publish_to_confluence_task"]
        assert "expected_output" in configs["publish_to_confluence_task"]

    def test_has_create_jira_epic_task(self):
        configs = get_task_configs()
        assert "create_jira_epic_task" in configs
        assert "description" in configs["create_jira_epic_task"]

    def test_has_create_jira_tickets_task(self):
        configs = get_task_configs()
        assert "create_jira_tickets_task" in configs
        assert "description" in configs["create_jira_tickets_task"]
