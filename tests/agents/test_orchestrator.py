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
        assert "create_jira_stories_task" in data
        assert "create_jira_tasks_task" in data

    def test_config_dir_exists(self):
        assert CONFIG_DIR.is_dir()

    def test_pm_jira_role_mentions_agent_ready(self):
        data = _load_yaml("product_manager_jira.yaml")
        role = data["product_manager_jira"]["role"].lower()
        assert "agent-ready" in role

    def test_pm_jira_goal_mentions_sample_data(self):
        data = _load_yaml("product_manager_jira.yaml")
        goal = data["product_manager_jira"]["goal"].lower()
        assert "sample data" in goal

    def test_architect_role_mentions_agent_ready(self):
        data = _load_yaml("architect_tech_lead.yaml")
        role = data["architect_tech_lead"]["role"].lower()
        assert "sub-task" in role or "agent-ready" in role

    def test_architect_goal_has_five_sections(self):
        data = _load_yaml("architect_tech_lead.yaml")
        goal = data["architect_tech_lead"]["goal"].lower()
        assert "reasoning" in goal
        assert "instructions" in goal
        assert "sample data" in goal or "sample" in goal
        assert "guard rail" in goal
        assert "definition of done" in goal or "done" in goal

    def test_architect_backstory_mentions_vibe_coding(self):
        data = _load_yaml("architect_tech_lead.yaml")
        backstory = data["architect_tech_lead"]["backstory"].lower()
        assert "sample document" in backstory or "sample data" in backstory or "sample" in backstory
        assert "test" in backstory or "acceptance criteria" in backstory or "validation" in backstory


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
    monkeypatch.delenv("GEMINI_RESEARCH_MODEL", raising=False)
    llm = _build_llm()
    assert "gemini" in llm.model.lower()


def test_build_llm_respects_orchestrator_model(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_MODEL", "gemini-custom-orch")
    monkeypatch.setenv("GEMINI_RESEARCH_MODEL", "gemini-3.1-pro-preview")
    llm = _build_llm()
    assert "gemini-custom-orch" in llm.model


def test_build_llm_falls_back_to_gemini_research_model(monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_RESEARCH_MODEL", "gemini-2.5-pro")
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

    def test_has_create_jira_stories_task(self):
        configs = get_task_configs()
        assert "create_jira_stories_task" in configs
        assert "description" in configs["create_jira_stories_task"]

    def test_has_create_jira_tasks_task(self):
        configs = get_task_configs()
        assert "create_jira_tasks_task" in configs
        assert "description" in configs["create_jira_tasks_task"]

    # ── Agent-ready prompt content assertions ────────────────────

    def test_stories_prompt_has_agent_ready_marker(self):
        """Stories prompt must instruct agents to produce agent-ready tickets."""
        desc = get_task_configs()["create_jira_stories_task"]["description"]
        assert "agent-ready" in desc.lower() or "Agent-Ready" in desc

    def test_stories_prompt_requires_sample_data(self):
        """Stories prompt must ask for sample data in Architecture stories."""
        desc = get_task_configs()["create_jira_stories_task"]["description"]
        assert "sample" in desc.lower()

    def test_stories_prompt_has_four_categories(self):
        """Stories must use the four categories: Data Persistence, Data Layer,
        Data Presentation, App & Data Security."""
        desc = get_task_configs()["create_jira_stories_task"]["description"].lower()
        assert "data persistence" in desc
        assert "data layer" in desc
        assert "data presentation" in desc
        assert "app & data security" in desc.lower() or "data security" in desc

    def test_stories_prompt_has_dependency_chain(self):
        """Stories must define the dependency chain between categories."""
        desc = get_task_configs()["create_jira_stories_task"]["description"].lower()
        assert "is_blocked_by_key" in desc or "blocked by" in desc

    def test_tasks_prompt_has_agent_ready_marker(self):
        """Tasks prompt must instruct agents to produce agent-ready tickets."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "agent-ready" in desc.lower() or "Agent-Ready" in desc

    def test_tasks_prompt_requires_five_sections(self):
        """Every task must include Reasoning, Instructions, Sample data,
        Guard rails, and Definition of done."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        desc_lower = desc.lower()
        assert "reasoning" in desc_lower
        assert "step-by-step" in desc_lower or "instructions" in desc_lower
        assert "sample data" in desc_lower
        assert "guard rail" in desc_lower
        assert "definition of done" in desc_lower

    def test_tasks_prompt_architecture_has_schema_spec(self):
        """Architecture tasks must include full schema specification."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        desc_lower = desc.lower()
        assert "collection name" in desc_lower
        assert "document structure" in desc_lower or "field" in desc_lower
        assert "sample document" in desc_lower
        assert "index" in desc_lower

    def test_tasks_prompt_architecture_has_api_spec(self):
        """Architecture tasks must include full API specification."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        desc_lower = desc.lower()
        assert "request/response" in desc_lower or "request body" in desc_lower
        assert "error response" in desc_lower or "error codes" in desc_lower
        assert "openapi" in desc_lower

    def test_tasks_prompt_backend_has_vibe_coding_instructions(self):
        """Backend tasks must be agent-codex-ready with file paths and
        function signatures."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        desc_lower = desc.lower()
        assert "agent-codex-ready" in desc_lower or "codex" in desc_lower or "coding agent" in desc_lower
        assert "file path" in desc_lower
        assert "function signature" in desc_lower or "class/function" in desc_lower

    def test_tasks_prompt_backend_has_sample_io(self):
        """Backend tasks must include sample data for implementation."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "sample" in desc.lower()

    def test_tasks_prompt_frontend_has_component_spec(self):
        """Frontend tasks must include component specs and UI states."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        desc_lower = desc.lower()
        assert "component" in desc_lower
        assert "responsive" in desc_lower or "breakpoint" in desc_lower
        assert "accessibility" in desc_lower or "aria" in desc_lower

    def test_tasks_prompt_qe_has_happy_path(self):
        """QE tasks must include happy-path test scenarios."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "happy-path" in desc.lower() or "happy path" in desc.lower()

    def test_tasks_prompt_qe_has_edge_cases(self):
        """QE tasks must include edge-case test scenarios."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "edge-case" in desc.lower() or "edge case" in desc.lower()

    def test_tasks_prompt_qe_has_negative_tests(self):
        """QE tasks must include negative test scenarios."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "negative" in desc.lower()

    def test_tasks_prompt_qe_has_test_fixtures(self):
        """QE tasks must include sample test data fixtures."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "fixture" in desc.lower() or "test data" in desc.lower()

    def test_tasks_prompt_range_3_to_7(self):
        """Tasks should be 3-7 per story (not the old 2-5)."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"]
        assert "3-7" in desc

    def test_stories_prompt_has_approved_skeleton_var(self):
        """Stories prompt must include an {approved_skeleton} format variable."""
        desc = get_task_configs()["create_jira_stories_task"]["description"]
        assert "{approved_skeleton}" in desc

    def test_has_skeleton_task(self):
        """Skeleton outline task must be defined."""
        configs = get_task_configs()
        assert "generate_jira_skeleton_task" in configs
        assert "description" in configs["generate_jira_skeleton_task"]

    def test_tasks_prompt_has_seven_sections(self):
        """Every sub-task must include all seven sections."""
        desc = get_task_configs()["create_jira_tasks_task"]["description"].lower()
        assert "reasoning" in desc
        assert "instructions" in desc
        assert "sample data" in desc
        assert "guard rails" in desc or "guard rail" in desc
        assert "definition of done" in desc
        assert "test cases for qe" in desc
        assert "unit test cases" in desc or "unit test" in desc
