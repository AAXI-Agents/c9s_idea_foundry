"""Tests for orchestrator._post_completion — CrewAI post-completion crew."""

from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.flows.prd_flow import PRDFlow
from crewai_productfeature_planner.orchestrator._post_completion import (
    build_post_completion_crew,
)

_MOD = "crewai_productfeature_planner.orchestrator._post_completion"
_AGENTS = "crewai_productfeature_planner.agents.orchestrator.agent"


class TestBuildPostCompletionCrew:
    """Tests for the CrewAI-based post-completion crew."""

    _DM = f"{_AGENTS}.create_delivery_manager_agent"
    _OA = f"{_AGENTS}.create_orchestrator_agent"
    _PM = f"{_AGENTS}.create_jira_product_manager_agent"
    _ATL = f"{_AGENTS}.create_jira_architect_tech_lead_agent"
    _TC = f"{_AGENTS}.get_task_configs"
    _VERBOSE = "crewai_productfeature_planner.scripts.logging_config.is_verbose"
    _CREW_CLS = "crewai.Crew"
    _TASK_CLS = "crewai.Task"
    _HAS_CONF = f"{_MOD}._has_confluence_credentials"
    _HAS_JIRA = f"{_MOD}._has_jira_credentials"
    _HAS_GEMINI = f"{_MOD}._has_gemini_credentials"

    _TASK_CONFIGS = {
        "publish_to_confluence_task": {
            "description": "Publish {prd_content} as '{page_title}' ({run_id})",
            "expected_output": "Confluence page URL",
        },
        "generate_jira_skeleton_task": {
            "description": "Skeleton for '{page_title}' summary={executive_summary} reqs={functional_requirements} {additional_prd_context}",
            "expected_output": "Skeleton outline",
        },
        "create_jira_epic_task": {
            "description": "Create epic '{page_title}' summary={executive_summary} ({run_id}) confluence={confluence_url}",
            "expected_output": "Epic key",
        },
        "create_jira_stories_task": {
            "description": "Create stories from {approved_skeleton} {functional_requirements} {additional_prd_context} under {epic_key} ({run_id}) confluence={confluence_url}",
            "expected_output": "Story keys",
        },
        "create_jira_tasks_task": {
            "description": "Create tasks from {stories_output} reqs={functional_requirements} {additional_prd_context} ({run_id}) confluence={confluence_url}",
            "expected_output": "Task keys",
        },
    }

    def test_returns_none_without_credentials(self, monkeypatch):
        """Without Atlassian credentials, should return None."""
        monkeypatch.delenv("ATLASSIAN_BASE_URL", raising=False)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        result = build_post_completion_crew(flow)
        assert result is None

    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_returns_none_without_final_prd(self, _mg, _mc):
        """Without a finalized PRD, should return None."""
        flow = PRDFlow()
        flow.state.final_prd = ""  # no PRD
        result = build_post_completion_crew(flow)
        assert result is None

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_JIRA, return_value=False)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_returns_crew_with_confluence_credentials(
        self, _mg, _mc, _mj, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """With Confluence credentials and a final PRD, should return a Crew."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        result = build_post_completion_crew(flow)
        mock_crew.assert_called_once()
        assert result is not None

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_JIRA, return_value=False)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_crew_has_two_agents(
        self, _mg, _mc, _mj, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Without Jira, Crew should contain only Delivery Manager and Orchestrator."""
        dm_agent = MagicMock(name="delivery_manager")
        orch_agent = MagicMock(name="orchestrator")
        mock_dm.return_value = dm_agent
        mock_oa.return_value = orch_agent
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        build_post_completion_crew(flow)
        crew_kwargs = mock_crew.call_args[1]
        assert dm_agent in crew_kwargs["agents"]
        assert orch_agent in crew_kwargs["agents"]
        assert len(crew_kwargs["agents"]) == 2

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_JIRA, return_value=False)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_crew_has_assess_task_plus_delivery_tasks(
        self, _mg, _mc, _mj, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v,
    ):
        """Crew should have at least 2 tasks (assess + confluence)."""
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        build_post_completion_crew(flow)
        # At minimum: assess + confluence = 2 tasks
        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["tasks"]) >= 2

    @patch(_HAS_JIRA, return_value=True)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_returns_none_when_already_published(self, _mg, _mc, _mj):
        """If confluence_url and jira_output already set, nothing to do."""
        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.confluence_url = "https://test.atlassian.net/wiki/page/123"
        flow.state.jira_output = "PROJ-42"
        result = build_post_completion_crew(flow)
        assert result is None

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_JIRA, return_value=True)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_crew_has_four_agents_with_jira(
        self, _mg, _mc, _mj, mock_task, mock_crew,
        mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v,
    ):
        """With Jira, Crew should contain DM, Orchestrator, PM and Architect/TL."""
        dm_agent = MagicMock(name="delivery_manager")
        orch_agent = MagicMock(name="orchestrator")
        pm_agent = MagicMock(name="pm")
        atl_agent = MagicMock(name="atl")
        mock_dm.return_value = dm_agent
        mock_oa.return_value = orch_agent
        mock_pm.return_value = pm_agent
        mock_atl.return_value = atl_agent
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        flow.state.confluence_url = "https://test.atlassian.net/wiki/page/123"
        build_post_completion_crew(flow)
        crew_kwargs = mock_crew.call_args[1]
        assert dm_agent in crew_kwargs["agents"]
        assert orch_agent in crew_kwargs["agents"]
        assert pm_agent in crew_kwargs["agents"]
        assert atl_agent in crew_kwargs["agents"]
        assert len(crew_kwargs["agents"]) == 4

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_JIRA, return_value=True)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_jira_epic_stories_use_pm_agent(
        self, _mg, _mc, _mj, mock_task, mock_crew,
        mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v,
    ):
        """Epic and Stories tasks should be assigned to the PM agent."""
        pm_agent = MagicMock(name="pm")
        atl_agent = MagicMock(name="atl")
        mock_dm.return_value = MagicMock(name="delivery_manager")
        mock_oa.return_value = MagicMock(name="orchestrator")
        mock_pm.return_value = pm_agent
        mock_atl.return_value = atl_agent

        created_tasks = []
        def _track_task(**kw):
            t = MagicMock(**kw)
            created_tasks.append(kw)
            return t
        mock_task.side_effect = _track_task

        flow = PRDFlow()
        flow.state.final_prd = "# Some PRD"
        flow.state.idea = "A cool feature"
        flow.state.finalized_idea = "Polished idea"
        flow.state.confluence_url = "https://test.atlassian.net/wiki/page/123"
        fr_section = flow.state.draft.get_section("functional_requirements")
        fr_section.content = "FR1: Login"
        build_post_completion_crew(flow)

        # Tasks: assess(DM), skeleton(PM), epic(PM), stories(PM), tasks(ATL) = 5
        skeleton_kw = created_tasks[1]  # second task is skeleton
        epic_kw = created_tasks[2]  # third task is epic
        stories_kw = created_tasks[3]  # fourth is stories
        tasks_kw = created_tasks[4]  # fifth is tasks
        assert skeleton_kw["agent"] is pm_agent
        assert epic_kw["agent"] is pm_agent
        assert stories_kw["agent"] is pm_agent
        assert tasks_kw["agent"] is atl_agent
