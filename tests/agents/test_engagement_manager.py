"""Tests for the Engagement Manager agent configuration and runner."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.agents.engagement_manager.agent import (
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_MAX_RETRIES,
    _build_engagement_llm,
    _build_project_tools,
    _load_yaml,
    _parse_steering_result,
    _HEARTBEAT_EMOJI,
    _PROGRESS_EVENT_MAP,
    create_engagement_manager,
    detect_user_steering,
    generate_heartbeat,
    handle_unknown_intent,
    make_heartbeat_progress_callback,
    orchestrate_idea_to_prd,
)


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    """Provide dummy API keys."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


@pytest.fixture(autouse=True)
def _mock_engagement_llm():
    """Prevent real LLM construction."""
    with patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent._build_engagement_llm",
        return_value="gemini/gemini-3-flash-preview",
    ):
        yield


# ── Factory tests ─────────────────────────────────────────────


def test_create_engagement_manager_requires_credentials(monkeypatch):
    """Should raise EnvironmentError when neither key nor project is set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
        create_engagement_manager()


def test_create_engagement_manager_accepts_api_key(monkeypatch):
    """Should succeed with only GOOGLE_API_KEY set."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    agent = create_engagement_manager()
    assert agent is not None


def test_create_engagement_manager_accepts_project(monkeypatch):
    """Should succeed with only GOOGLE_CLOUD_PROJECT set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    agent = create_engagement_manager()
    assert agent is not None


def test_create_engagement_manager_role():
    """Agent should have a role mentioning engagement or navigation."""
    agent = create_engagement_manager()
    role_lower = agent.role.lower()
    assert "engagement" in role_lower or "navigation" in role_lower


def test_create_engagement_manager_no_tools():
    """Agent should have no tools without a project_id."""
    agent = create_engagement_manager()
    assert len(agent.tools) == 0


def test_create_engagement_manager_no_delegation():
    """Agent should not delegate."""
    agent = create_engagement_manager()
    assert agent.allow_delegation is False


def test_create_engagement_manager_respects_context_window():
    """Agent should respect context window limits."""
    agent = create_engagement_manager()
    assert agent.respect_context_window is True


# ── LLM configuration tests ──────────────────────────────────
# These tests call the real _build_engagement_llm function directly,
# bypassing the autouse mock by re-importing and calling the original.


def test_build_engagement_llm_default_model(monkeypatch):
    """Without overrides, uses the default basic Gemini model."""
    monkeypatch.delenv("ENGAGEMENT_MANAGER_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with patch(
        "crewai_productfeature_planner.agents.gemini_utils.ensure_gemini_env",
    ):
        # Import the real function from the module source
        from crewai_productfeature_planner.agents.engagement_manager.agent import (
            _build_engagement_llm as real_build,
        )
        # Call __wrapped__ if it exists (mock patches), else direct call
        # Since autouse patches at module level, call via importlib
        import importlib
        import crewai_productfeature_planner.agents.engagement_manager.agent as em_mod
        importlib.reload(em_mod)
        llm = em_mod._build_engagement_llm()
        assert "gemini" in llm.model.lower()


def test_build_engagement_llm_respects_engagement_manager_model(monkeypatch):
    """ENGAGEMENT_MANAGER_MODEL should take precedence."""
    monkeypatch.setenv("ENGAGEMENT_MANAGER_MODEL", "gemini-custom-model")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    with patch(
        "crewai_productfeature_planner.agents.gemini_utils.ensure_gemini_env",
    ):
        import importlib
        import crewai_productfeature_planner.agents.engagement_manager.agent as em_mod
        importlib.reload(em_mod)
        llm = em_mod._build_engagement_llm()
        assert "gemini-custom-model" in llm.model


def test_build_engagement_llm_falls_back_to_gemini_model(monkeypatch):
    """Without ENGAGEMENT_MANAGER_MODEL, should use GEMINI_MODEL."""
    monkeypatch.delenv("ENGAGEMENT_MANAGER_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    with patch(
        "crewai_productfeature_planner.agents.gemini_utils.ensure_gemini_env",
    ):
        import importlib
        import crewai_productfeature_planner.agents.engagement_manager.agent as em_mod
        importlib.reload(em_mod)
        llm = em_mod._build_engagement_llm()
        assert "gemini-2.5-flash" in llm.model


# ── YAML config tests ────────────────────────────────────────


def test_load_agent_yaml():
    """Agent YAML should load and contain expected keys."""
    config = _load_yaml("agent.yaml")
    assert "engagement_manager" in config
    em = config["engagement_manager"]
    assert "role" in em
    assert "goal" in em
    assert "backstory" in em


def test_load_tasks_yaml():
    """Tasks YAML should load and contain the response task."""
    config = _load_yaml("tasks.yaml")
    assert "engagement_response_task" in config
    task = config["engagement_response_task"]
    assert "description" in task
    assert "expected_output" in task
    # Description should have template placeholders
    assert "{user_message}" in task["description"]
    assert "{conversation_history}" in task["description"]
    assert "{active_context}" in task["description"]


# ── Runner tests ──────────────────────────────────────────────


@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
@patch(
    "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
)
@patch(
    "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
)
def test_handle_unknown_intent_returns_response(
    mock_kickoff, mock_create, mock_crew, mock_task,
):
    """handle_unknown_intent should return the crew's response."""
    mock_create.return_value = MagicMock()
    mock_kickoff.return_value = "Try clicking *New Idea* to start a PRD."
    result = handle_unknown_intent("what can you do?")
    assert "New Idea" in result
    mock_kickoff.assert_called_once()


@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
@patch(
    "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
)
@patch(
    "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
)
def test_handle_unknown_intent_with_history(
    mock_kickoff, mock_create, mock_crew, mock_task,
):
    """Should pass conversation history to the task."""
    mock_create.return_value = MagicMock()
    mock_kickoff.return_value = "Let me help you navigate."
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    result = handle_unknown_intent(
        "I want to do something", conversation_history=history,
    )
    assert result
    mock_kickoff.assert_called_once()


@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
@patch(
    "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
)
@patch(
    "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
)
def test_handle_unknown_intent_with_context(
    mock_kickoff, mock_create, mock_crew, mock_task,
):
    """Should include active context in the response."""
    mock_create.return_value = MagicMock()
    mock_kickoff.return_value = "You're on project X. Try *List Ideas*."
    result = handle_unknown_intent(
        "what's going on",
        active_context="Active project: My Project",
    )
    assert result
    mock_kickoff.assert_called_once()


@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
@patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
@patch(
    "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
)
@patch(
    "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    side_effect=Exception("LLM down"),
)
def test_handle_unknown_intent_propagates_exception(
    mock_kickoff, mock_create, mock_crew, mock_task,
):
    """Should propagate exceptions to caller (message handler catches them)."""
    mock_create.return_value = MagicMock()
    with pytest.raises(Exception, match="LLM down"):
        handle_unknown_intent("something weird")


# ── YAML config tests — new tasks ────────────────────────────


def test_tasks_yaml_has_idea_to_prd_orchestration_task():
    """tasks.yaml must contain the idea_to_prd_orchestration_task."""
    config = _load_yaml("tasks.yaml")
    assert "idea_to_prd_orchestration_task" in config
    task = config["idea_to_prd_orchestration_task"]
    assert "description" in task
    assert "expected_output" in task
    assert "{idea}" in task["description"]
    assert "{initiator_user_id}" in task["description"]
    assert "{run_id}" in task["description"]


def test_tasks_yaml_has_heartbeat_update_task():
    """tasks.yaml must contain the heartbeat_update_task."""
    config = _load_yaml("tasks.yaml")
    assert "heartbeat_update_task" in config
    task = config["heartbeat_update_task"]
    assert "description" in task
    assert "expected_output" in task
    assert "{phase}" in task["description"]
    assert "{status}" in task["description"]
    assert "{run_id}" in task["description"]


def test_tasks_yaml_has_user_steering_detection_task():
    """tasks.yaml must contain the user_steering_detection_task."""
    config = _load_yaml("tasks.yaml")
    assert "user_steering_detection_task" in config
    task = config["user_steering_detection_task"]
    assert "description" in task
    assert "expected_output" in task
    assert "{user_message}" in task["description"]
    assert "{initiator_user_id}" in task["description"]
    assert "{message_author_id}" in task["description"]


# ── Heartbeat tests ──────────────────────────────────────────


class TestGenerateHeartbeat:
    """Tests for the generate_heartbeat() helper."""

    def test_returns_string(self):
        result = generate_heartbeat("idea_refinement", "STARTING")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_emoji_prefix(self):
        for status, emoji in _HEARTBEAT_EMOJI.items():
            result = generate_heartbeat("test", status)
            assert result.startswith(emoji), f"Missing emoji for {status}"

    def test_unknown_status_uses_info_emoji(self):
        result = generate_heartbeat("test", "UNKNOWN_STATUS")
        assert result.startswith("\u2139")

    def test_includes_agent_name_when_provided(self):
        result = generate_heartbeat("test", "STARTING", agent_name="Idea Refiner")
        assert "[Idea Refiner]" in result

    def test_omits_agent_name_when_empty(self):
        result = generate_heartbeat("test", "STARTING", agent_name="")
        assert "[" not in result

    def test_uses_details_when_provided(self):
        result = generate_heartbeat("test", "PROGRESS", details="Working on section 3")
        assert "Working on section 3" in result

    def test_fallback_when_no_details(self):
        result = generate_heartbeat("idea_refinement", "STARTING")
        assert "idea_refinement" in result


class TestMakeHeartbeatProgressCallback:
    """Tests for make_heartbeat_progress_callback()."""

    def test_returns_callable(self):
        cb = make_heartbeat_progress_callback("U123")
        assert callable(cb)

    def test_fires_notify_on_known_event(self):
        messages = []
        cb = make_heartbeat_progress_callback("U123", notify=messages.append)
        cb("section_start", {"section_title": "Problem Statement", "section_key": "problem", "section_step": 1, "total_sections": 5})
        assert len(messages) == 1
        assert "Problem Statement" in messages[0]

    def test_ignores_unknown_event(self):
        messages = []
        cb = make_heartbeat_progress_callback("U123", notify=messages.append)
        cb("unknown_event_type", {})
        assert len(messages) == 0

    def test_handles_missing_template_keys(self):
        """If details dict has missing keys, use raw template instead of crash."""
        messages = []
        cb = make_heartbeat_progress_callback("U123", notify=messages.append)
        cb("section_start", {})  # Missing section_title etc.
        assert len(messages) == 1  # Should not crash

    def test_swallows_notify_exception(self):
        """Notify failures must not propagate."""
        def bad_notify(msg):
            raise RuntimeError("Slack is down")

        cb = make_heartbeat_progress_callback("U123", notify=bad_notify)
        # Should not raise
        cb("section_start", {"section_title": "Test", "section_key": "test", "section_step": 1, "total_sections": 1})

    def test_logs_without_notify(self):
        """Works fine with no notify callback (log-only mode)."""
        cb = make_heartbeat_progress_callback("U123", notify=None)
        cb("section_complete", {"section_title": "Test", "section_key": "test", "section_step": 1, "total_sections": 1, "iterations": 3})


class TestProgressEventMap:
    """Validate _PROGRESS_EVENT_MAP consistency."""

    def test_all_events_have_two_element_tuple(self):
        for event, mapping in _PROGRESS_EVENT_MAP.items():
            assert isinstance(mapping, tuple) and len(mapping) == 2, (
                f"Event {event} should be (status, template)"
            )

    def test_all_statuses_are_valid(self):
        valid = set(_HEARTBEAT_EMOJI.keys())
        for event, (status, _) in _PROGRESS_EVENT_MAP.items():
            assert status in valid, f"Event {event} has invalid status {status}"


# ── Steering detection tests ─────────────────────────────────


class TestDetectUserSteering:
    """Tests for detect_user_steering()."""

    def test_ignores_non_initiator(self):
        """Messages from non-initiator users are ignored without LLM call."""
        result = detect_user_steering(
            user_message="change the scope to mobile",
            current_phase="idea_refinement",
            current_agent="Idea Refiner",
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            message_author_id="U999",
        )
        assert result["classification"] == "IGNORE"

    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
    )
    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    )
    def test_classifies_initiator_message(
        self, mock_kickoff, mock_create, mock_crew, mock_task,
    ):
        """Messages from initiator are sent to LLM for classification."""
        mock_create.return_value = MagicMock()
        mock_kickoff.return_value = '{"classification": "STEERING", "action": "Add mobile scope", "extracted_intent": "mobile", "target_phase": "idea_refinement"}'
        result = detect_user_steering(
            user_message="also consider mobile",
            current_phase="idea_refinement",
            current_agent="Idea Refiner",
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            message_author_id="U123",
        )
        assert result["classification"] == "STEERING"
        mock_kickoff.assert_called_once()

    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
    )
    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
        side_effect=Exception("LLM timeout"),
    )
    def test_defaults_to_question_on_llm_failure(
        self, mock_kickoff, mock_create, mock_crew, mock_task,
    ):
        """LLM failures should default classification to QUESTION."""
        mock_create.return_value = MagicMock()
        result = detect_user_steering(
            user_message="what's happening?",
            current_phase="section_drafting",
            current_agent="Product Manager",
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            message_author_id="U123",
        )
        assert result["classification"] == "QUESTION"


class TestParseSteeringResult:
    """Tests for _parse_steering_result()."""

    def test_parses_json_response(self):
        raw = '{"classification": "FEEDBACK", "action": "route to PM", "extracted_intent": "more detail", "target_phase": "section_drafting"}'
        result = _parse_steering_result(raw)
        assert result["classification"] == "FEEDBACK"
        assert result["action"] == "route to PM"

    def test_parses_text_with_keyword(self):
        raw = "This is clearly a STEERING request to change the scope."
        result = _parse_steering_result(raw)
        assert result["classification"] == "STEERING"

    def test_falls_back_to_question_when_no_keyword(self):
        raw = "I have no idea what this message means."
        result = _parse_steering_result(raw)
        assert result["classification"] == "QUESTION"

    def test_handles_empty_string(self):
        result = _parse_steering_result("")
        assert result["classification"] == "QUESTION"


# ── Orchestration tests ──────────────────────────────────────


class TestOrchestrateIdeaToPrd:
    """Tests for orchestrate_idea_to_prd()."""

    @patch(
        "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
    )
    def test_calls_run_prd_flow(self, mock_run):
        """Should delegate to run_prd_flow with a heartbeat callback."""
        result = orchestrate_idea_to_prd(
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            run_id="test-run-001",
        )
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs[1]["run_id"] == "test-run-001" or call_kwargs[0][0] == "test-run-001"
        assert result["run_id"] == "test-run-001"
        assert result["status"] == "completed"

    @patch(
        "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
    )
    def test_collects_heartbeats(self, mock_run):
        """Should record heartbeat messages in the returned dict."""
        result = orchestrate_idea_to_prd(
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            run_id="test-run-002",
        )
        # At minimum: planning + completion heartbeats
        assert len(result["heartbeats"]) >= 2

    @patch(
        "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
    )
    def test_sends_heartbeats_via_notify(self, mock_run):
        """Notify callback should receive heartbeat messages."""
        messages = []
        orchestrate_idea_to_prd(
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            run_id="test-run-003",
            notify=messages.append,
        )
        assert len(messages) >= 2  # planning + completion

    @patch(
        "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
    )
    def test_passes_auto_approve(self, mock_run):
        """auto_approve should be forwarded to run_prd_flow."""
        orchestrate_idea_to_prd(
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            run_id="test-run-004",
            auto_approve=True,
        )
        _, kwargs = mock_run.call_args
        assert kwargs["auto_approve"] is True

    @patch(
        "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
    )
    def test_passes_approval_callbacks(self, mock_run):
        """Extra callbacks should be forwarded to run_prd_flow."""
        mock_cb = MagicMock()
        orchestrate_idea_to_prd(
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            run_id="test-run-005",
            executive_summary_callback=mock_cb,
            requirements_approval_callback=mock_cb,
        )
        _, kwargs = mock_run.call_args
        assert kwargs["executive_summary_callback"] is mock_cb
        assert kwargs["requirements_approval_callback"] is mock_cb

    @patch(
        "crewai_productfeature_planner.apis.prd.service.run_prd_flow",
    )
    def test_returns_initiator_user_id(self, mock_run):
        """Result dict should include the initiator_user_id."""
        result = orchestrate_idea_to_prd(
            idea="Build a SaaS dashboard",
            initiator_user_id="U123",
            run_id="test-run-006",
        )
        assert result["initiator_user_id"] == "U123"


# ── Project knowledge tests ──────────────────────────────────


class TestBuildProjectTools:
    """Tests for _build_project_tools()."""

    def test_returns_empty_when_no_project_id(self):
        """No project_id → empty tools and empty context."""
        tools, ctx = _build_project_tools(None)
        assert tools == []
        assert ctx == ""

    def test_returns_empty_when_empty_project_id(self):
        """Empty string project_id → same as None."""
        tools, ctx = _build_project_tools("")
        assert tools == []
        assert ctx == ""

    @patch(
        "crewai_productfeature_planner.scripts.project_knowledge.load_completed_ideas_context",
        return_value="── Completed Ideas ──\n1. Dashboard idea",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.project_config.get_project",
        return_value={"name": "My Test Project"},
    )
    def test_returns_tools_when_project_dir_exists(
        self, mock_get_project, mock_load_ctx, tmp_path,
    ):
        """With valid project_id and existing dir, returns tools + context."""
        project_dir = tmp_path / "my-test-project"
        project_dir.mkdir()

        with patch(
            "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
            tmp_path,
        ), patch(
            "crewai_productfeature_planner.scripts.project_knowledge._safe_dirname",
            return_value="my-test-project",
        ):
            tools, ctx = _build_project_tools("proj-123")

        assert len(tools) == 2
        assert "Completed Ideas" in ctx
        mock_get_project.assert_called_once_with("proj-123")

    @patch(
        "crewai_productfeature_planner.scripts.project_knowledge.load_completed_ideas_context",
        return_value="",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.project_config.get_project",
        return_value={"name": "Missing Project"},
    )
    def test_no_tools_when_dir_missing(
        self, mock_get_project, mock_load_ctx, tmp_path,
    ):
        """Project exists in DB but no knowledge dir → no tools, just context."""
        with patch(
            "crewai_productfeature_planner.scripts.project_knowledge._PROJECTS_ROOT",
            tmp_path,
        ), patch(
            "crewai_productfeature_planner.scripts.project_knowledge._safe_dirname",
            return_value="missing-project",
        ):
            tools, ctx = _build_project_tools("proj-456")

        assert tools == []

    @patch(
        "crewai_productfeature_planner.scripts.project_knowledge.load_completed_ideas_context",
        return_value="── Completed Ideas ──\n1. Some idea",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.project_config.get_project",
        side_effect=Exception("DB connection failed"),
    )
    def test_graceful_fallback_on_db_error(self, mock_get_project, mock_load_ctx):
        """DB errors should not crash — returns ideas context only."""
        tools, ctx = _build_project_tools("proj-789")
        assert tools == []
        assert "Completed Ideas" in ctx


class TestCreateEngagementManagerWithProject:
    """Tests for create_engagement_manager(project_id=...)."""

    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent._build_project_tools",
    )
    def test_gets_tools_with_project_id(self, mock_build_tools):
        """Agent should receive tools when project_id is provided."""
        # Create real-ish tool mocks via spec to satisfy pydantic validation
        from crewai.tools import BaseTool

        mock_tool_a = MagicMock(spec=BaseTool)
        mock_tool_b = MagicMock(spec=BaseTool)
        mock_build_tools.return_value = (
            [mock_tool_a, mock_tool_b],
            "── Completed Ideas ──",
        )
        with patch(
            "crewai_productfeature_planner.agents.engagement_manager.agent.Agent",
        ) as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(tools=[mock_tool_a, mock_tool_b])
            agent = create_engagement_manager(project_id="proj-123")
        assert len(agent.tools) == 2
        mock_build_tools.assert_called_once_with("proj-123")

    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent._build_project_tools",
        return_value=([], "── Completed Ideas ──\n1. Dashboard v2"),
    )
    def test_backstory_includes_ideas_context(self, mock_build_tools):
        """Agent backstory should append the ideas context."""
        agent = create_engagement_manager(project_id="proj-123")
        assert "Completed Ideas" in agent.backstory

    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent._build_project_tools",
        return_value=([], ""),
    )
    def test_backstory_unchanged_without_context(self, mock_build_tools):
        """No ideas context → backstory stays as original YAML."""
        agent_with = create_engagement_manager(project_id="proj-empty")
        agent_without = create_engagement_manager()
        # Both should have the YAML backstory, neither appended empty text
        assert agent_with.backstory == agent_without.backstory


class TestHandleUnknownIntentWithProject:
    """Tests for handle_unknown_intent(project_id=...)."""

    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
    )
    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    )
    def test_passes_project_id_to_create(
        self, mock_kickoff, mock_create, mock_crew, mock_task,
    ):
        """project_id should be forwarded to create_engagement_manager."""
        mock_create.return_value = MagicMock()
        mock_kickoff.return_value = "Here's a summary."
        handle_unknown_intent("summarize ideas", project_id="proj-123")
        mock_create.assert_called_once_with(project_id="proj-123")

    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
    )
    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    )
    @patch(
        "crewai_productfeature_planner.scripts.project_knowledge.load_completed_ideas_context",
        return_value="── Completed Ideas ──\n1. Dashboard v2",
    )
    def test_project_knowledge_in_task_description(
        self, mock_load_ctx, mock_kickoff, mock_create, mock_crew, mock_task,
    ):
        """Task description should contain project knowledge when available."""
        mock_create.return_value = MagicMock()
        mock_kickoff.return_value = "Ideas summary."
        handle_unknown_intent("what ideas exist?", project_id="proj-123")
        # Check the Task was created with project_knowledge in description
        task_call_kwargs = mock_task.call_args[1]
        assert "Completed Ideas" in task_call_kwargs["description"]

    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Task")
    @patch("crewai_productfeature_planner.agents.engagement_manager.agent.Crew")
    @patch(
        "crewai_productfeature_planner.agents.engagement_manager.agent.create_engagement_manager",
    )
    @patch(
        "crewai_productfeature_planner.scripts.retry.crew_kickoff_with_retry",
    )
    def test_no_project_uses_fallback_knowledge(
        self, mock_kickoff, mock_create, mock_crew, mock_task,
    ):
        """Without project_id, task description should contain fallback text."""
        mock_create.return_value = MagicMock()
        mock_kickoff.return_value = "No ideas available."
        handle_unknown_intent("list all ideas")
        task_call_kwargs = mock_task.call_args[1]
        assert "no project selected" in task_call_kwargs["description"]


def test_tasks_yaml_has_project_knowledge_placeholder():
    """engagement_response_task must contain {project_knowledge} placeholder."""
    config = _load_yaml("tasks.yaml")
    task = config["engagement_response_task"]
    assert "{project_knowledge}" in task["description"]
