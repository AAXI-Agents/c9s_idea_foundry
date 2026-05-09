"""Tests for ideation agent structured output and answer formatting."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.ideation.models import (
    ClarifyingQuestion,
    QuestionAnswer,
    Recommendation,
    StructuredIdeationResponse,
)


# ── Fixtures ──────────────────────────────────────────────────


def _make_structured_response(**overrides) -> StructuredIdeationResponse:
    """Build a valid StructuredIdeationResponse for testing."""
    defaults = {
        "acknowledgment": "Great idea! Let me explore this further.",
        "questions": [
            ClarifyingQuestion(
                id=i,
                question=f"Question {i}?",
                context=f"Context for question {i}.",
                recommendations=[
                    Recommendation(
                        label=f"Option {j}",
                        pro=f"Pro for option {j}",
                        con=f"Con for option {j}",
                        complexity=["Low", "Medium", "High"][j],
                    )
                    for j in range(3)
                ],
            )
            for i in range(1, 4)
        ],
        "agent_insight": "This idea has strong product-market fit potential.",
        "summary_draft": None,
    }
    defaults.update(overrides)
    return StructuredIdeationResponse(**defaults)


def _make_crew_result(*, pydantic=None, raw=""):
    """Build a mock CrewAI result object."""
    result = MagicMock()
    result.pydantic = pydantic
    result.raw = raw
    return result


# ── Model validation tests ────────────────────────────────────


class TestStructuredIdeationResponse:
    def test_valid_response(self):
        resp = _make_structured_response()
        assert len(resp.questions) == 3
        assert resp.acknowledgment.startswith("Great")

    def test_min_3_questions_required(self):
        with pytest.raises(Exception):
            StructuredIdeationResponse(
                acknowledgment="Hi",
                questions=[
                    ClarifyingQuestion(
                        id=1,
                        question="Q?",
                        context="C",
                        recommendations=[
                            Recommendation(label="A", pro="p", con="c", complexity="Low"),
                            Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                            Recommendation(label="C", pro="p", con="c", complexity="High"),
                        ],
                    ),
                ],
            )

    def test_max_5_questions(self):
        with pytest.raises(Exception):
            StructuredIdeationResponse(
                acknowledgment="Hi",
                questions=[
                    ClarifyingQuestion(
                        id=i,
                        question=f"Q{i}?",
                        context="C",
                        recommendations=[
                            Recommendation(label="A", pro="p", con="c", complexity="Low"),
                            Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                            Recommendation(label="C", pro="p", con="c", complexity="High"),
                        ],
                    )
                    for i in range(1, 7)  # 6 questions → too many
                ],
            )

    def test_exactly_3_recommendations_required(self):
        with pytest.raises(Exception):
            ClarifyingQuestion(
                id=1,
                question="Q?",
                context="C",
                recommendations=[
                    Recommendation(label="A", pro="p", con="c", complexity="Low"),
                    Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                ],
            )

    def test_complexity_literal_validation(self):
        with pytest.raises(Exception):
            Recommendation(label="A", pro="p", con="c", complexity="Very High")

    def test_summary_draft_optional(self):
        resp = _make_structured_response(summary_draft="Draft exec summary.")
        assert resp.summary_draft == "Draft exec summary."

    def test_serialization_roundtrip(self):
        resp = _make_structured_response()
        data = resp.model_dump()
        roundtripped = StructuredIdeationResponse.model_validate(data)
        assert roundtripped.acknowledgment == resp.acknowledgment
        assert len(roundtripped.questions) == len(resp.questions)


class TestQuestionAnswer:
    def test_selected_option(self):
        ans = QuestionAnswer(question_id=1, selected_option=2)
        assert ans.selected_option == 2
        assert ans.custom_feedback is None

    def test_custom_feedback(self):
        ans = QuestionAnswer(question_id=1, custom_feedback="My own idea")
        assert ans.selected_option is None
        assert ans.custom_feedback == "My own idea"


# ── Agent _extract_structured_response tests ──────────────────


class TestExtractStructuredResponse:
    @pytest.fixture(autouse=True)
    def _import(self):
        from crewai_productfeature_planner.agents.ideation.agent import (
            _extract_structured_response,
        )
        self.extract = _extract_structured_response

    def test_from_pydantic_attribute(self):
        model = _make_structured_response()
        result = _make_crew_result(pydantic=model)
        parsed = self.extract(result)
        assert parsed is not None
        assert parsed.acknowledgment == model.acknowledgment

    def test_from_raw_json(self):
        model = _make_structured_response()
        raw_json = model.model_dump_json()
        result = _make_crew_result(raw=raw_json)
        parsed = self.extract(result)
        assert parsed is not None
        assert len(parsed.questions) == 3

    def test_from_json_in_code_fence(self):
        model = _make_structured_response()
        raw = f"```json\n{model.model_dump_json()}\n```"
        result = _make_crew_result(raw=raw)
        parsed = self.extract(result)
        assert parsed is not None

    def test_fallback_on_invalid_json(self):
        result = _make_crew_result(raw="This is just text, not JSON.")
        parsed = self.extract(result)
        assert parsed is None

    def test_fallback_on_partial_json(self):
        result = _make_crew_result(raw='{"acknowledgment": "Hi"}')
        parsed = self.extract(result)
        assert parsed is None  # missing required fields


# ── Agent config loading tests ────────────────────────────────


class TestAgentConfig:
    def test_all_step_agent_keys_exist(self):
        from crewai_productfeature_planner.agents.ideation import STEP_AGENT_KEYS
        assert set(STEP_AGENT_KEYS.keys()) == {"a", "b", "c", "d", "e"}

    def test_all_step_task_keys_exist(self):
        from crewai_productfeature_planner.agents.ideation import STEP_TASK_KEYS
        assert set(STEP_TASK_KEYS.keys()) == {"a", "b", "c", "d", "e"}

    def test_agent_yaml_loads(self):
        from crewai_productfeature_planner.agents.ideation.agent import _load_yaml
        agents = _load_yaml("agents.yaml")
        assert "product_ideation_specialist" in agents
        assert "user_research_specialist" in agents

    def test_tasks_yaml_loads(self):
        from crewai_productfeature_planner.agents.ideation.agent import _load_yaml
        tasks = _load_yaml("tasks.yaml")
        assert "ideation_task" in tasks
        assert "persona_task" in tasks
        # Verify structured output instruction is present
        for key in ["ideation_task", "persona_task", "solution_task", "goal_task", "tech_stack_task"]:
            assert "StructuredIdeationResponse" in tasks[key]["expected_output"]


# ── Service-level answer formatting tests ─────────────────────


class TestFormatAnswersAsContext:
    @pytest.fixture(autouse=True)
    def _import(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            _format_answers_as_context,
        )
        self.format_answers = _format_answers_as_context

    def test_selected_option_with_label(self):
        answers = [
            QuestionAnswer(question_id=1, selected_option=0),
        ]
        metadata = {
            "original_questions": [
                {
                    "id": 1,
                    "question": "Who is the audience?",
                    "recommendations": [
                        {"label": "SMBs"},
                        {"label": "Enterprise"},
                        {"label": "Prosumers"},
                    ],
                }
            ]
        }
        result = self.format_answers(answers, metadata)
        assert "SMBs" in result
        assert "Who is the audience?" in result

    def test_custom_feedback(self):
        answers = [
            QuestionAnswer(question_id=1, custom_feedback="Both B2B and B2C"),
        ]
        metadata = {
            "original_questions": [
                {"id": 1, "question": "Target segment?", "recommendations": []}
            ]
        }
        result = self.format_answers(answers, metadata)
        assert "Custom: Both B2B and B2C" in result

    def test_no_original_questions(self):
        answers = [
            QuestionAnswer(question_id=1, selected_option=1),
        ]
        metadata = {}
        result = self.format_answers(answers, metadata)
        assert "Question 1" in result
        assert "Option 2" in result

    def test_multiple_answers(self):
        answers = [
            QuestionAnswer(question_id=1, selected_option=0),
            QuestionAnswer(question_id=2, custom_feedback="Custom answer"),
            QuestionAnswer(question_id=3, selected_option=2),
        ]
        metadata = {"original_questions": []}
        result = self.format_answers(answers, metadata)
        assert "Q1:" in result
        assert "Q2:" in result
        assert "Q3:" in result


# ── MessageMetadata structured field tests ────────────────────


class TestMessageMetadataStructured:
    """Regression: MessageMetadata must preserve the 'structured' field."""

    def test_structured_field_preserved(self):
        """The 'structured' key must survive Pydantic validation."""
        from crewai_productfeature_planner.apis.ideation.models import MessageMetadata

        resp = _make_structured_response()
        meta = MessageMetadata(
            render_type="structured_questions",
            can_iterate=True,
            can_advance=False,
            structured=resp.model_dump(),
        )
        assert meta.structured is not None
        assert meta.structured["acknowledgment"] == resp.acknowledgment
        assert len(meta.structured["questions"]) == 3

    def test_structured_survives_model_dump(self):
        """Round-trip through model_dump must keep 'structured'."""
        from crewai_productfeature_planner.apis.ideation.models import MessageMetadata

        resp = _make_structured_response()
        meta = MessageMetadata(
            render_type="structured_questions",
            can_iterate=True,
            can_advance=False,
            structured=resp.model_dump(),
        )
        dumped = meta.model_dump()
        assert "structured" in dumped
        assert dumped["structured"]["acknowledgment"] == resp.acknowledgment

    def test_structured_none_when_plain_text(self):
        """Plain-text messages have metadata=None or structured=None."""
        from crewai_productfeature_planner.apis.ideation.models import MessageMetadata

        meta = MessageMetadata(render_type=None)
        assert meta.structured is None

    def test_error_field_preserved(self):
        """The 'error' flag must survive validation."""
        from crewai_productfeature_planner.apis.ideation.models import MessageMetadata

        meta = MessageMetadata(error=True)
        assert meta.error is True


# ── Serialize message round-trip test ─────────────────────────


class TestSerializeMessageStructured:
    """Regression: _serialize_message must pass structured metadata through."""

    def test_serialize_includes_structured(self):
        from crewai_productfeature_planner.apis.ideation.router import (
            _serialize_message,
        )

        resp = _make_structured_response()
        raw_msg = {
            "id": "test-msg-id",
            "role": "agent",
            "content": resp.acknowledgment,
            "content_type": "cards",
            "agent_name": "product_ideation_specialist",
            "step": "a",
            "timestamp": "2026-05-04T10:00:00Z",
            "metadata": {
                "render_type": "structured_questions",
                "can_iterate": True,
                "can_advance": False,
                "structured": resp.model_dump(),
            },
        }

        item = _serialize_message(raw_msg)
        assert item.metadata is not None
        assert item.metadata.render_type == "structured_questions"
        assert item.metadata.structured is not None
        assert len(item.metadata.structured["questions"]) == 3
        assert item.metadata.can_iterate is True
        assert item.metadata.can_advance is False
        assert item.content_type == "cards"
        assert item.agent_name == "product_ideation_specialist"
        assert item.flow_step == "ideation"

    def test_serialize_plain_text_message(self):
        from crewai_productfeature_planner.apis.ideation.router import (
            _serialize_message,
        )

        raw_msg = {
            "id": "msg-2",
            "role": "agent",
            "content": "Just a text response.",
            "step": "b",
            "timestamp": "2026-05-04T10:00:00Z",
        }

        item = _serialize_message(raw_msg)
        assert item.metadata is None
        assert item.content_type == "text"
        assert item.agent_name is None
        assert item.flow_step == "persona"


# ── Broadcast envelope shape tests ───────────────────────────


class TestBroadcastMessageEnvelope:
    """Regression: _broadcast_message must use {event, data} envelope."""

    @patch(
        "crewai_productfeature_planner.apis.ideation.service.broadcast_sync",
        create=True,
    )
    def test_broadcast_message_envelope(self, mock_broadcast):
        # Patch the lazy import inside _broadcast_message
        with patch(
            "crewai_productfeature_planner.apis.ideation._route_websocket.broadcast_sync",
            mock_broadcast,
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                _broadcast_message,
            )

            resp = _make_structured_response()
            metadata = {
                "render_type": "structured_questions",
                "can_iterate": True,
                "can_advance": False,
                "structured": resp.model_dump(),
            }
            _broadcast_message(
                "sess-1", "msg-1", "Ack text", "a", metadata,
                agent_name="product_ideation_specialist",
                content_type="cards",
            )

            assert mock_broadcast.called
            call_args = mock_broadcast.call_args
            payload = call_args[0][1]

            # Must use {event, data} envelope
            assert payload["event"] == "new_message"
            assert "data" in payload
            data = payload["data"]
            assert data["id"] == "msg-1"
            assert data["role"] == "agent"
            assert data["agent_name"] == "product_ideation_specialist"
            assert data["content_type"] == "cards"
            assert data["flow_step"] == "ideation"
            assert data["metadata"]["render_type"] == "structured_questions"
            assert data["metadata"]["structured"] is not None

    @patch(
        "crewai_productfeature_planner.apis.ideation.service.broadcast_sync",
        create=True,
    )
    def test_broadcast_typing_envelope(self, mock_broadcast):
        with patch(
            "crewai_productfeature_planner.apis.ideation._route_websocket.broadcast_sync",
            mock_broadcast,
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                _broadcast_typing,
            )

            _broadcast_typing("sess-1", "a")

            assert mock_broadcast.called
            call_args = mock_broadcast.call_args
            payload = call_args[0][1]

            assert payload["event"] == "agent_typing"
            assert "data" in payload
            assert payload["data"]["agent_name"] == "ideation_agent"
            assert payload["data"]["step"] == "ideation"


# ── Repository append_message agent_name/content_type tests ───


class TestAppendMessageFields:
    """Repository append_message must persist agent_name and content_type."""

    @patch("crewai_productfeature_planner.mongodb.ideation_sessions.repository._col")
    def test_stores_agent_name_and_content_type(self, mock_col):
        from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
            append_message,
        )

        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_col.return_value = mock_collection

        msg_id = append_message(
            session_id="s1",
            role="agent",
            content="Hello",
            step="a",
            agent_name="product_ideation_specialist",
            content_type="cards",
        )

        assert msg_id is not None
        call_args = mock_collection.update_one.call_args
        pushed_msg = call_args[0][1]["$push"]["messages"]
        assert pushed_msg["agent_name"] == "product_ideation_specialist"
        assert pushed_msg["content_type"] == "cards"

    @patch("crewai_productfeature_planner.mongodb.ideation_sessions.repository._col")
    def test_omits_agent_name_when_none(self, mock_col):
        from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
            append_message,
        )

        mock_collection = MagicMock()
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_col.return_value = mock_collection

        append_message(
            session_id="s1",
            role="user",
            content="My idea",
            step="a",
        )

        call_args = mock_collection.update_one.call_args
        pushed_msg = call_args[0][1]["$push"]["messages"]
        assert "agent_name" not in pushed_msg
        assert "content_type" not in pushed_msg


# ── handle_advance auto-trigger regression test ───────────────


class TestHandleAdvanceAutoTrigger:
    """Regression: handle_advance must auto-trigger the agent for the new step."""

    @pytest.mark.asyncio
    async def test_advance_triggers_agent_for_new_step(self):
        """After advancing from step a→b, the persona agent must run."""
        import asyncio

        session_doc = {
            "session_id": "sess-adv",
            "status": "active",
            "current_step": "a",
            "steps_data": {
                "a": {"approved": False, "output": "Step A summary"},
            },
        }

        updated_session_doc = {
            **session_doc,
            "current_step": "b",
            "steps_data": {
                "a": {"approved": True, "output": "Step A summary"},
            },
        }

        agent_run_calls: list[dict] = []

        async def _fake_run_agent(*, session_id, step, user_input,
                                  session_context=None, tenant=None):
            agent_run_calls.append({
                "session_id": session_id,
                "step": step,
                "user_input": user_input,
            })
            return {
                "id": "msg-auto",
                "role": "agent",
                "content": "Persona questions",
                "step": step,
                "metadata": None,
            }

        get_session_calls = [0]

        def _fake_get_session(*, session_id, tenant=None):
            get_session_calls[0] += 1
            # First call returns original, second returns updated
            if get_session_calls[0] <= 1:
                return session_doc
            return updated_session_doc

        with patch(
            "crewai_productfeature_planner.apis.ideation.service.get_session",
            side_effect=_fake_get_session,
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service.advance_step",
            return_value="b",
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service.append_message",
            return_value="msg-prompt",
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service._run_agent_for_step",
            side_effect=_fake_run_agent,
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                handle_advance,
            )

            result = await handle_advance(session_id="sess-adv")

            assert result["previous_step"] == "a"
            assert result["new_step"] == "b"
            assert result["completed"] is False

            # Let the fire-and-forget task run
            await asyncio.sleep(0.05)

            # The agent MUST have been invoked for step "b"
            assert len(agent_run_calls) == 1, (
                "handle_advance must auto-trigger the agent for the new step"
            )
            assert agent_run_calls[0]["step"] == "b"
            assert agent_run_calls[0]["session_id"] == "sess-adv"

    @pytest.mark.asyncio
    async def test_advance_does_not_trigger_on_completion(self):
        """When all steps are done, no agent auto-trigger should fire."""
        session_doc = {
            "session_id": "sess-done",
            "status": "active",
            "current_step": "e",
            "steps_data": {
                "a": {"approved": True, "output": "A"},
                "b": {"approved": True, "output": "B"},
                "c": {"approved": True, "output": "C"},
                "d": {"approved": True, "output": "D"},
                "e": {"approved": False, "output": "E"},
            },
        }

        with patch(
            "crewai_productfeature_planner.apis.ideation.service.get_session",
            return_value=session_doc,
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service.advance_step",
            return_value=None,
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service._auto_create_idea_from_session",
            return_value={"idea_id": "idea-1"},
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service.trigger_prd_from_ideation",
            return_value="run-1",
        ), patch(
            "crewai_productfeature_planner.apis.ideation.service._run_agent_for_step",
        ) as mock_agent:
            from crewai_productfeature_planner.apis.ideation.service import (
                handle_advance,
            )

            result = await handle_advance(session_id="sess-done")

            assert result["completed"] is True
            mock_agent.assert_not_called()
