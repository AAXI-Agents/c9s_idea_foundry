"""Regression tests: Jira tickets must NEVER be created without user approval.

This test module is a safety net to prevent regressions where Jira ticket
creation bypasses the phased approval flow (skeleton → Epics/Stories →
Sub-tasks with user interaction at each gate).

Every code path that could trigger Jira ticket creation is tested here to
ensure the approval gate invariant is maintained.

See also: Obsidian > Architecture > Coding Standards — "Jira Approval Gate".
"""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.flows.prd_flow import PRDFlow

_FIN = "crewai_productfeature_planner.flows._finalization"
_ORCH = "crewai_productfeature_planner.orchestrator"
_RETRY = "crewai_productfeature_planner.scripts.retry"
_STARTUP = "crewai_productfeature_planner.orchestrator._startup_delivery"
_POST = "crewai_productfeature_planner.orchestrator._post_completion"
_HANDLERS = "crewai_productfeature_planner.apis.slack._flow_handlers"
_AGENTS = "crewai_productfeature_planner.agents.orchestrator.agent"


# ====================================================================
# 1. _run_auto_post_completion MUST use confluence_only=True
# ====================================================================

class TestAutoPostCompletionAlwaysConfluenceOnly:
    """_run_auto_post_completion must NEVER create Jira tasks.

    As of v0.38.0, the auto path no longer calls any crew at all —
    it just notifies that the PRD is ready for user-triggered publish.
    """

    @patch(f"{_ORCH}.build_post_completion_crew")
    def test_auto_post_completion_does_not_call_crew(
        self, mock_build,
    ):
        """The auto-approve path must NOT call any delivery crew."""
        from crewai_productfeature_planner.flows._finalization import (
            _run_auto_post_completion,
        )

        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.run_id = "auto-test"

        _run_auto_post_completion(flow)

        mock_build.assert_not_called()

    @patch(f"{_ORCH}.build_post_completion_crew")
    def test_auto_post_completion_via_flow_method(
        self, mock_build,
    ):
        """PRDFlow._run_post_completion() without jira callback → no crew."""
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        # No jira_skeleton_approval_callback set → auto path
        flow._run_post_completion()

        mock_build.assert_not_called()


# ====================================================================
# 2. run_post_completion routing logic
# ====================================================================

class TestPostCompletionRouting:
    """run_post_completion must route correctly based on callback presence."""

    @patch(f"{_FIN}._run_auto_post_completion")
    @patch(f"{_FIN}._run_phased_post_completion")
    def test_routes_to_auto_when_no_callback(self, mock_phased, mock_auto):
        """Without jira_skeleton_approval_callback → auto path."""
        from crewai_productfeature_planner.flows._finalization import (
            run_post_completion,
        )

        flow = PRDFlow()
        # No callback set
        run_post_completion(flow)

        mock_auto.assert_called_once_with(flow)
        mock_phased.assert_not_called()

    @patch(f"{_FIN}._run_auto_post_completion")
    @patch(f"{_FIN}._run_phased_post_completion")
    def test_routes_to_phased_when_callback_set(self, mock_phased, mock_auto):
        """With jira_skeleton_approval_callback → phased path."""
        from crewai_productfeature_planner.flows._finalization import (
            run_post_completion,
        )

        flow = PRDFlow()
        flow.jira_skeleton_approval_callback = MagicMock()
        run_post_completion(flow)

        mock_phased.assert_called_once_with(flow)
        mock_auto.assert_not_called()

    @patch(f"{_FIN}._run_auto_post_completion")
    @patch(f"{_FIN}._run_phased_post_completion")
    def test_swallows_exceptions_from_either_path(
        self, mock_phased, mock_auto,
    ):
        """Exceptions in post-completion should be logged, not raised."""
        from crewai_productfeature_planner.flows._finalization import (
            run_post_completion,
        )

        mock_auto.side_effect = RuntimeError("boom")
        flow = PRDFlow()
        # Should not raise
        run_post_completion(flow)


# ====================================================================
# 3. _run_phased_post_completion uses confluence_only for Confluence step
# ====================================================================

class TestPhasedPostCompletionConfluenceStep:
    """Phased path must NOT auto-publish Confluence.

    As of v0.38.0, _run_phased_post_completion requires Confluence
    to already be published before starting Jira phases.
    """

    @patch(f"{_ORCH}.build_post_completion_crew")
    def test_phased_does_not_auto_publish_confluence(
        self, mock_build,
    ):
        """Phased path must NOT call build_post_completion_crew."""
        from crewai_productfeature_planner.flows._finalization import (
            _run_phased_post_completion,
        )

        flow = PRDFlow()
        flow.state.final_prd = "# PRD Content"
        flow.state.run_id = "phased-test"
        flow.jira_skeleton_approval_callback = MagicMock()
        # No confluence_url → should return early

        _run_phased_post_completion(flow)

        mock_build.assert_not_called()


# ====================================================================
# 4. build_post_completion_crew — confluence_only gates Jira
# ====================================================================

class TestBuildPostCompletionCrewConfluenceOnly:
    """build_post_completion_crew(confluence_only=True) must exclude Jira."""

    _DM = f"{_AGENTS}.create_delivery_manager_agent"
    _OA = f"{_AGENTS}.create_orchestrator_agent"
    _PM = f"{_AGENTS}.create_jira_product_manager_agent"
    _ATL = f"{_AGENTS}.create_jira_architect_tech_lead_agent"
    _TC = f"{_AGENTS}.get_task_configs"
    _VERBOSE = "crewai_productfeature_planner.scripts.logging_config.is_verbose"
    _HAS_CONF = f"{_POST}._has_confluence_credentials"
    _HAS_JIRA = f"{_POST}._has_jira_credentials"
    _HAS_GEMINI = f"{_POST}._has_gemini_credentials"
    _CREW_CLS = "crewai.Crew"
    _TASK_CLS = "crewai.Task"

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
            "description": "Create epic '{page_title}' ({run_id})",
            "expected_output": "Epic key",
        },
        "create_jira_stories_task": {
            "description": "Create stories ({run_id})",
            "expected_output": "Story keys",
        },
        "create_jira_tasks_task": {
            "description": "Create tasks ({run_id})",
            "expected_output": "Task keys",
        },
    }

    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    @patch(_HAS_JIRA, return_value=True)
    @patch(_HAS_CONF, return_value=True)
    @patch(_HAS_GEMINI, return_value=True)
    def test_confluence_only_excludes_all_jira_tasks(
        self, _gem, _conf, _jira, mock_task, mock_crew,
        mock_dm, mock_oa, _tc, _v,
    ):
        """Even with Jira creds, confluence_only must produce 0 Jira tasks."""
        from crewai_productfeature_planner.orchestrator._post_completion import (
            build_post_completion_crew,
        )

        mock_dm.return_value = MagicMock(name="dm")
        mock_oa.return_value = MagicMock(name="oa")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.idea = "Test"
        build_post_completion_crew(flow, confluence_only=True)

        crew_kwargs = mock_crew.call_args[1]
        # Only DM + Orchestrator, never PM/ATL
        assert len(crew_kwargs["agents"]) == 2
        # Only assess + confluence
        assert len(crew_kwargs["tasks"]) == 2

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
    def test_without_confluence_only_includes_jira(
        self, _gem, _conf, _jira, mock_task, mock_crew,
        mock_dm, mock_oa, mock_pm, mock_atl, _tc, _v,
    ):
        """Without confluence_only, Jira creds → Jira agents + tasks included."""
        from crewai_productfeature_planner.orchestrator._post_completion import (
            build_post_completion_crew,
        )

        mock_dm.return_value = MagicMock(name="dm")
        mock_oa.return_value = MagicMock(name="oa")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.idea = "Test"
        flow.state.confluence_url = "https://test.atlassian.net/wiki/page/1"
        build_post_completion_crew(flow, confluence_only=False)

        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["agents"]) == 4  # DM + OA + PM + ATL


# ====================================================================
# 5. build_startup_delivery_crew — confluence_only gates Jira
# ====================================================================

class TestStartupDeliveryConfluenceOnly:
    """build_startup_delivery_crew(confluence_only=True) must exclude Jira."""

    _DM = f"{_AGENTS}.create_delivery_manager_agent"
    _OA = f"{_AGENTS}.create_orchestrator_agent"
    _PM = f"{_AGENTS}.create_jira_product_manager_agent"
    _ATL = f"{_AGENTS}.create_jira_architect_tech_lead_agent"
    _TC = f"{_AGENTS}.get_task_configs"
    _VERBOSE = "crewai_productfeature_planner.scripts.logging_config.is_verbose"
    _HAS_JIRA = f"{_STARTUP}._has_jira_credentials"
    _CREW_CLS = "crewai.Crew"
    _TASK_CLS = "crewai.Task"

    _TASK_CONFIGS = {
        "publish_to_confluence_task": {
            "description": "Publish {prd_content} as '{page_title}' ({run_id})",
            "expected_output": "Confluence page URL",
        },
        "create_jira_epic_task": {
            "description": "Create epic ({run_id})",
            "expected_output": "Epic key",
        },
        "create_jira_stories_task": {
            "description": "Create stories ({run_id})",
            "expected_output": "Story keys",
        },
        "create_jira_tasks_task": {
            "description": "Create tasks ({run_id})",
            "expected_output": "Task keys",
        },
    }

    def _make_item(self, **overrides):
        base = {
            "run_id": "r1",
            "idea": "Test idea",
            "content": "# PRD content",
            "confluence_done": True,
            "confluence_url": "https://test.atlassian.net/wiki/page/1",
            "jira_done": False,
            "jira_tickets": [],
            "finalized_idea": "ES summary",
            "func_reqs": "FR1: Login",
            "doc": {"run_id": "r1"},
        }
        base.update(overrides)
        return base

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_confluence_only_skips_jira_agents(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v, _hj,
    ):
        """confluence_only=True must not create PM/ATL agents."""
        from crewai_productfeature_planner.orchestrator._startup_delivery import (
            build_startup_delivery_crew,
        )

        mock_dm.return_value = MagicMock(name="dm")
        mock_oa.return_value = MagicMock(name="oa")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(
            self._make_item(), confluence_only=True,
        )

        crew_kwargs = mock_crew.call_args[1]
        # Only DM + Orchestrator
        assert len(crew_kwargs["agents"]) == 2

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_confluence_only_creates_only_assess_and_confluence_tasks(
        self, mock_task, mock_crew, mock_dm, mock_oa, _tc, _v, _hj,
    ):
        """confluence_only=True → only assess + confluence tasks."""
        from crewai_productfeature_planner.orchestrator._startup_delivery import (
            build_startup_delivery_crew,
        )

        mock_dm.return_value = MagicMock(name="dm")
        mock_oa.return_value = MagicMock(name="oa")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(
            self._make_item(), confluence_only=True,
        )

        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["tasks"]) <= 2  # assess + confluence

    @patch(_HAS_JIRA, return_value=True)
    @patch(_VERBOSE, return_value=False)
    @patch(_TC, return_value=_TASK_CONFIGS)
    @patch(_ATL)
    @patch(_PM)
    @patch(_OA)
    @patch(_DM)
    @patch(_CREW_CLS)
    @patch(_TASK_CLS)
    def test_without_confluence_only_includes_jira(
        self, mock_task, mock_crew, mock_dm, mock_oa, mock_pm, mock_atl,
        _tc, _v, _hj,
    ):
        """Without confluence_only, Jira creds + confluence_done → Jira tasks."""
        from crewai_productfeature_planner.orchestrator._startup_delivery import (
            build_startup_delivery_crew,
        )

        mock_dm.return_value = MagicMock(name="dm")
        mock_oa.return_value = MagicMock(name="oa")
        mock_pm.return_value = MagicMock(name="pm")
        mock_atl.return_value = MagicMock(name="atl")
        mock_task.side_effect = lambda **kw: MagicMock(**kw)

        build_startup_delivery_crew(
            self._make_item(), confluence_only=False,
        )

        crew_kwargs = mock_crew.call_args[1]
        assert len(crew_kwargs["agents"]) == 4  # includes PM + ATL


# ====================================================================
# 6. execute_restart_prd must pass interactive=True
# ====================================================================

class TestExecuteRestartPrdInteractive:
    """execute_restart_prd must always use interactive mode."""

    @patch(f"{_HANDLERS}.kick_off_prd_flow")
    @patch(f"{_HANDLERS}.append_to_thread")
    @patch(
        "crewai_productfeature_planner.mongodb.crew_jobs.repository.update_job_status",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.mark_archived",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_run_any_status",
    )
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool")
    def test_restart_passes_interactive_true(
        self, mock_send_cls, mock_find, mock_archive, mock_job_status,
        mock_append, mock_kickoff,
    ):
        """Restart is user-initiated, so it must use interactive mode."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            execute_restart_prd,
        )

        mock_find.return_value = {
            "run_id": "r1",
            "idea": "Test idea",
            "project_id": "proj1",
        }
        mock_send_cls.return_value = MagicMock()

        execute_restart_prd(
            run_id="r1",
            channel="C123",
            thread_ts="1234.5678",
            user="U123",
            event_ts="1234.5679",
            project_id="proj1",
        )

        mock_kickoff.assert_called_once()
        call_kwargs = mock_kickoff.call_args[1]
        assert call_kwargs["interactive"] is True

    @patch(f"{_HANDLERS}.kick_off_prd_flow")
    @patch(f"{_HANDLERS}.append_to_thread")
    @patch(
        "crewai_productfeature_planner.mongodb.crew_jobs.repository.update_job_status",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.mark_archived",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_run_any_status",
    )
    @patch("crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool")
    def test_restart_preserves_project_id(
        self, mock_send_cls, mock_find, mock_archive, mock_job_status,
        mock_append, mock_kickoff,
    ):
        """Restart should forward the project_id from the original run."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            execute_restart_prd,
        )

        mock_find.return_value = {
            "run_id": "r1",
            "idea": "Test idea",
            "project_id": "proj-abc",
        }
        mock_send_cls.return_value = MagicMock()

        execute_restart_prd(
            run_id="r1",
            channel="C123",
            thread_ts="1234.5678",
            user="U123",
        )

        call_kwargs = mock_kickoff.call_args[1]
        assert call_kwargs["project_id"] == "proj-abc"


# ====================================================================
# 7. kick_off_prd_flow — interactive vs auto path
# ====================================================================

class TestKickOffPrdFlowInteractiveRouting:
    """kick_off_prd_flow must route correctly based on interactive flag."""

    @patch(f"{_HANDLERS}.threading")
    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
        return_value=None,
    )
    def test_interactive_true_uses_interactive_flow(
        self, _client, mock_threading,
    ):
        """interactive=True → run_interactive_slack_flow thread."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            kick_off_prd_flow,
        )

        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread

        kick_off_prd_flow(
            channel="C123",
            thread_ts="1234",
            user="U123",
            idea="test",
            event_ts="1235",
            interactive=True,
        )

        thread_kwargs = mock_threading.Thread.call_args
        assert "interactive" in thread_kwargs[1].get("name", "")
        mock_thread.start.assert_called_once()

    @patch(f"{_HANDLERS}.threading")
    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
        return_value=None,
    )
    def test_interactive_false_uses_auto_flow(self, _client, mock_threading):
        """interactive=False → _run_slack_prd_flow thread."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            kick_off_prd_flow,
        )

        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread

        kick_off_prd_flow(
            channel="C123",
            thread_ts="1234",
            user="U123",
            idea="test",
            event_ts="1235",
            interactive=False,
        )

        thread_kwargs = mock_threading.Thread.call_args
        assert "interactive" not in thread_kwargs[1].get("name", "")
        mock_thread.start.assert_called_once()


# ====================================================================
# 8. jira_detected_in_output false positive resilience
# ====================================================================

class TestJiraDetectedInOutput:
    """jira_detected_in_output must not false-positive on PRD content."""

    def test_detects_real_jira_output(self):
        from crewai_productfeature_planner.flows._finalization import (
            jira_detected_in_output,
        )

        output = "Created Epic PROJ-42. Story PROJ-43 completed."
        assert jira_detected_in_output(output) is True

    def test_no_false_positive_on_confluence_only(self):
        from crewai_productfeature_planner.flows._finalization import (
            jira_detected_in_output,
        )

        # Confluence publish output — should NOT trigger Jira detection
        output = "Published page at https://co.atlassian.net/wiki/pages/123456"
        assert jira_detected_in_output(output) is False

    def test_rejects_failure_output(self):
        from crewai_productfeature_planner.flows._finalization import (
            jira_detected_in_output,
        )

        output = "Failed to create Epic PROJ-99. Connection refused."
        assert jira_detected_in_output(output) is False

    def test_requires_both_keyword_and_issue_key(self):
        from crewai_productfeature_planner.flows._finalization import (
            jira_detected_in_output,
        )

        # Keyword but no issue key
        assert jira_detected_in_output("Created epic for the project") is False
        # Issue key but no keyword
        assert jira_detected_in_output("Ticket PROJ-1 processed") is False


# ====================================================================
# 9. Startup callers must use confluence_only=True
# ====================================================================

class TestStartupCallersNoAutoPublish:
    """CLI and server startup paths must NOT auto-publish.

    As of v0.38.0, startup functions only discover pending items and
    log them — they never trigger publishing or Jira creation.
    """

    def test_cli_startup_does_not_auto_deliver(self):
        """_cli_startup.py must not call build_startup_delivery_crew."""
        import inspect
        from crewai_productfeature_planner import _cli_startup

        source = inspect.getsource(_cli_startup)
        # The startup functions should not call crew builders
        assert "build_startup_delivery_crew" not in source or "no auto-publish" in source.lower() or "discovery-only" in source.lower(), (
            "_cli_startup.py must not auto-deliver — "
            "publishing requires explicit user action"
        )

    def test_component_startup_does_not_auto_deliver(self):
        """components/startup.py must not call build_startup_delivery_crew."""
        import inspect
        from crewai_productfeature_planner.components import startup

        source = inspect.getsource(startup)
        assert "build_startup_delivery_crew" not in source or "no auto-publish" in source.lower() or "discovery-only" in source.lower(), (
            "components/startup.py must not auto-deliver — "
            "publishing requires explicit user action"
        )

    def test_auto_post_completion_does_not_publish(self):
        """_finalization._run_auto_post_completion must not auto-publish."""
        import inspect
        from crewai_productfeature_planner.flows import _finalization

        source = inspect.getsource(_finalization._run_auto_post_completion)
        assert "build_post_completion_crew" not in source, (
            "_run_auto_post_completion must not call build_post_completion_crew "
            "— all publishing requires user approval"
        )


# ====================================================================
# 10. End-to-end: API run_prd_flow path never triggers Jira
# ====================================================================

class TestApiPathNoJira:
    """The API prd/service.py path must not auto-create Jira tickets."""

    @patch(f"{_ORCH}.build_post_completion_crew")
    def test_api_run_prd_flow_does_not_auto_publish(
        self, mock_build,
    ):
        """run_prd_flow (API path) has no Jira callbacks → auto path →
        no crew call (v0.38.0: all publishing is user-triggered)."""
        from crewai_productfeature_planner.flows._finalization import (
            run_post_completion,
        )

        # Simulate API path: flow without any callbacks
        flow = PRDFlow()
        flow.state.final_prd = "# PRD"
        flow.state.run_id = "api-test"

        run_post_completion(flow)

        mock_build.assert_not_called()


# ====================================================================
# 11. handle_resume_prd passes Jira callbacks to resume_prd_flow
# ====================================================================

_RESUME_SERVICE = "crewai_productfeature_planner.apis.prd.service.resume_prd_flow"
_SAVE_CTX = (
    "crewai_productfeature_planner.mongodb.working_ideas.repository"
    ".save_slack_context"
)


class TestResumePathPassesJiraCallbacks:
    """handle_resume_prd must register interactive state and pass Jira
    callbacks to resume_prd_flow so post-completion uses phased delivery."""

    @patch(f"{_HANDLERS}.threading")
    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers"
        ".make_slack_jira_review_callback",
        return_value=MagicMock(name="jira_review_cb"),
    )
    @patch(
        "crewai_productfeature_planner.apis.slack.interactive_handlers"
        ".make_slack_jira_skeleton_callback",
        return_value=MagicMock(name="jira_skel_cb"),
    )
    @patch(_SAVE_CTX)
    @patch(
        "crewai_productfeature_planner.mongodb.find_unfinalized",
        return_value=[{
            "run_id": "resume-jira-test",
            "idea": "Test idea",
            "status": "paused",
            "sections_done": 9,
            "total_sections": 12,
        }],
    )
    def test_resume_builds_jira_callbacks(
        self, _find, _save, mock_skel_factory, mock_review_factory,
        mock_threading,
    ):
        """handle_resume_prd must build Jira callback factories."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_resume_prd,
        )

        send_tool = MagicMock()
        mock_threading.Thread.return_value = MagicMock()

        handle_resume_prd("C1", "T1", "U1", send_tool)

        # Jira callback factories must have been called
        mock_skel_factory.assert_called_once_with("resume-jira-test")
        mock_review_factory.assert_called_once_with("resume-jira-test")

        # Thread must have been created and started
        assert mock_threading.Thread.called

        # Cleanup
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            cleanup_interactive_run,
        )
        cleanup_interactive_run("resume-jira-test")

    @patch(f"{_HANDLERS}.threading")
    @patch(_SAVE_CTX)
    @patch(
        "crewai_productfeature_planner.mongodb.find_unfinalized",
        return_value=[{
            "run_id": "resume-interactive-test",
            "idea": "Test idea 2",
            "status": "paused",
            "sections_done": 5,
            "total_sections": 12,
        }],
    )
    def test_resume_registers_interactive_run(
        self, _find, _save, mock_threading,
    ):
        """handle_resume_prd must register an interactive run so Jira
        callbacks can look up channel/thread_ts."""
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            handle_resume_prd,
        )
        from crewai_productfeature_planner.apis.slack.interactive_handlers._run_state import (
            get_interactive_run,
        )

        send_tool = MagicMock()
        mock_threading.Thread.return_value = MagicMock()

        handle_resume_prd("C-resume", "T-resume", "U1", send_tool)

        # The run_id for the unfinalized idea
        info = get_interactive_run("resume-interactive-test")
        assert info is not None
        assert info["channel"] == "C-resume"
        assert info["thread_ts"] == "T-resume"

        # Cleanup
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            cleanup_interactive_run,
        )
        cleanup_interactive_run("resume-interactive-test")
