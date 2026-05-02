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
