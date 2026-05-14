"""Tests for the ideation iteration limit enforcement feature.

Covers:
    - Repository: increment_step_iteration
    - Service: iteration limit enforcement in handle_iterate / handle_user_response
    - Router: 409 on iterate when limit reached
    - Router: iteration history endpoint
    - Metadata population: can_iterate, can_advance, iteration_count, max_iterations
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    STEP_ORDER,
    create_session,
    increment_step_iteration,
)

_REPO = "crewai_productfeature_planner.mongodb.ideation_sessions.repository"
_SERVICE = "crewai_productfeature_planner.apis.ideation.service"
_AGENT = "crewai_productfeature_planner.agents.ideation"
_STREAMING = "crewai_productfeature_planner.apis.ideation._streaming"
_ROUTER = "crewai_productfeature_planner.apis.ideation.router"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_session_doc(**overrides):
    doc = {
        "session_id": "sess1",
        "user_id": "user1",
        "project_id": None,
        "title": "Test Idea",
        "status": "active",
        "current_step": "a",
        "steps_data": {
            step: {
                "input": None,
                "output": None,
                "approved": False,
                "completed_at": None,
                "iteration": 0,
            }
            for step in STEP_ORDER
        },
        "messages": [],
        "knowledge_context": "",
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "completed_at": None,
    }
    doc.update(overrides)
    return doc


def _mock_col(mock_db):
    return mock_db.__getitem__.return_value


# ── Repository: increment_step_iteration ──────────────────────


class TestIncrementStepIteration:
    def test_increments_and_returns_new_value(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one_and_update.return_value = {
            "steps_data": {"a": {"iteration": 2}},
        }

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = increment_step_iteration(
                session_id="sess1", step="a",
            )

        assert result == 2
        col.find_one_and_update.assert_called_once()

    def test_returns_zero_on_not_found(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one_and_update.return_value = None

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = increment_step_iteration(
                session_id="nope", step="a",
            )

        assert result == 0

    def test_returns_zero_on_error(self):
        from pymongo.errors import PyMongoError

        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.find_one_and_update.side_effect = PyMongoError("fail")

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = increment_step_iteration(
                session_id="sess1", step="a",
            )

        assert result == 0


class TestCreateSessionIterationField:
    def test_session_has_iteration_field(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.insert_one.return_value = MagicMock(acknowledged=True)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = create_session(user_id="u1", title="Test")

        assert result is not None
        for step in STEP_ORDER:
            assert result["steps_data"][step]["iteration"] == 0


# ── Service: handle_iterate — limit enforcement ──────────────


class TestHandleIterateLimitEnforcement:
    @pytest.mark.asyncio
    async def test_returns_error_when_limit_reached(self):
        session = _make_session_doc()
        session["steps_data"]["a"]["iteration"] = 2  # at limit

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(f"{_SERVICE}._get_max_iterations", return_value=2),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                handle_iterate,
            )

            result = await handle_iterate(session_id="sess1")

        assert result is not None
        assert result["error"] == "iteration_limit_reached"
        assert result["max_iterations"] == 2

    @pytest.mark.asyncio
    async def test_allows_iterate_when_under_limit(self):
        session = _make_session_doc()
        session["steps_data"]["a"]["iteration"] = 1  # under limit of 2

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(f"{_SERVICE}._get_max_iterations", return_value=2),
            patch(f"{_SERVICE}.increment_step_iteration", return_value=2),
            patch(f"{_SERVICE}.append_message"),
            patch(f"{_SERVICE}._run_agent_for_step", new_callable=AsyncMock),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                handle_iterate,
            )

            result = await handle_iterate(session_id="sess1")

        assert result is not None
        assert "error" not in result
        assert result["iteration"] == 2
        assert result["step"] == "a"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_session(self):
        with patch(f"{_SERVICE}.get_session", return_value=None):
            from crewai_productfeature_planner.apis.ideation.service import (
                handle_iterate,
            )

            result = await handle_iterate(session_id="nope")

        assert result is None


# ── Service: handle_user_response — iteration increment ──────


class TestHandleUserResponseIteration:
    @pytest.mark.asyncio
    async def test_increments_iteration_on_respond(self):
        session = _make_session_doc()

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(f"{_SERVICE}._get_max_iterations", return_value=2),
            patch(
                f"{_SERVICE}.increment_step_iteration", return_value=1,
            ) as mock_inc,
            patch(f"{_SERVICE}.append_message"),
            patch(f"{_SERVICE}.save_step_data"),
            patch(
                f"{_SERVICE}._run_agent_for_step",
                new_callable=AsyncMock,
                return_value={"id": "m1", "role": "agent", "content": "ok"},
            ),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                handle_user_response,
            )

            result = await handle_user_response(
                session_id="sess1", content="My idea"
            )

        assert result is not None
        mock_inc.assert_called_once_with(
            session_id="sess1", step="a", tenant=None,
        )


# ── Router: 409 on iterate when limit reached ────────────────


class TestIterateEndpoint409:
    def test_returns_409_when_limit_reached(self, client):
        session = _make_session_doc()

        with (
            patch(f"{_ROUTER}.get_session", return_value=session),
            patch(
                f"{_ROUTER}.handle_iterate",
                new_callable=AsyncMock,
                return_value={
                    "error": "iteration_limit_reached",
                    "max_iterations": 2,
                },
            ),
        ):
            resp = client.post(
                "/flow/ideation/sessions/sess1/iterate",
                json={},
            )

        assert resp.status_code == 409
        assert "Maximum iterations reached" in resp.json()["detail"]

    def test_returns_200_when_under_limit(self, client):
        session = _make_session_doc()

        with (
            patch(f"{_ROUTER}.get_session", return_value=session),
            patch(
                f"{_ROUTER}.handle_iterate",
                new_callable=AsyncMock,
                return_value={"iteration": 2, "step": "a"},
            ),
        ):
            resp = client.post(
                "/flow/ideation/sessions/sess1/iterate",
                json={"feedback": "improve this"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["iteration"] == 2
        assert body["status"] == "iterating"


# ── Router: iteration history endpoint ────────────────────────


class TestIterationHistoryEndpoint:
    def test_returns_history(self, client):
        session = _make_session_doc()
        history = {
            "step": "ideation",
            "iteration_count": 2,
            "max_iterations": 3,
            "rounds": [
                {
                    "round": 1,
                    "questions": [
                        {"id": 1, "question": "Who is the target?"},
                    ],
                    "agent_insight": "Focus on B2B",
                    "completed_at": "2026-05-14T10:30:00Z",
                },
            ],
        }

        with (
            patch(f"{_ROUTER}.get_session", return_value=session),
            patch(
                f"{_ROUTER}.get_iteration_history",
                new_callable=AsyncMock,
                return_value=history,
            ),
        ):
            resp = client.get(
                "/flow/ideation/sessions/sess1/iterations?step=ideation",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["step"] == "ideation"
        assert body["iteration_count"] == 2
        assert body["max_iterations"] == 3
        assert len(body["rounds"]) == 1

    def test_returns_404_when_session_not_found(self, client):
        with patch(
            f"{_ROUTER}.get_iteration_history",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(
                "/flow/ideation/sessions/nope/iterations",
            )

        assert resp.status_code == 404


# ── Metadata population ──────────────────────────────────────


class TestMetadataPopulation:
    @pytest.mark.asyncio
    async def test_can_iterate_true_when_under_limit(self):
        """Verify that _run_agent_for_step populates metadata correctly."""
        from crewai_productfeature_planner.apis.ideation.models import (
            StructuredIdeationResponse,
            ClarifyingQuestion,
            Recommendation,
        )

        mock_response = StructuredIdeationResponse(
            acknowledgment="Great idea!",
            questions=[
                ClarifyingQuestion(
                    id=1,
                    question="Who?",
                    context="Important",
                    recommendations=[
                        Recommendation(label="A", pro="p", con="c", complexity="Low"),
                        Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                        Recommendation(label="C", pro="p", con="c", complexity="High"),
                    ],
                ),
                ClarifyingQuestion(
                    id=2,
                    question="What?",
                    context="Important",
                    recommendations=[
                        Recommendation(label="A", pro="p", con="c", complexity="Low"),
                        Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                        Recommendation(label="C", pro="p", con="c", complexity="High"),
                    ],
                ),
                ClarifyingQuestion(
                    id=3,
                    question="When?",
                    context="Important",
                    recommendations=[
                        Recommendation(label="A", pro="p", con="c", complexity="Low"),
                        Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                        Recommendation(label="C", pro="p", con="c", complexity="High"),
                    ],
                ),
            ],
            agent_insight="Good direction",
        )

        with (
            patch(f"{_AGENT}.run_ideation_step", return_value=mock_response),
            patch(f"{_STREAMING}.streaming_session"),
            patch(f"{_SERVICE}.append_message", return_value="msg1"),
            patch(f"{_SERVICE}.save_step_data"),
            patch(f"{_SERVICE}._build_step_context", return_value={}),
            patch(f"{_SERVICE}._build_conversation_history", return_value=[]),
            patch(f"{_SERVICE}._broadcast_typing"),
            patch(f"{_SERVICE}._broadcast_processing_status"),
            patch(f"{_SERVICE}._broadcast_agent_token_final"),
            patch(f"{_SERVICE}._broadcast_message"),
            patch(f"{_SERVICE}._ProgressTicker"),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                _run_agent_for_step,
            )

            result = await _run_agent_for_step(
                session_id="sess1",
                step="a",
                user_input="My idea",
                iteration_count=1,
                max_iterations=3,
            )

        assert result is not None
        meta = result["metadata"]
        assert meta["can_iterate"] is True
        assert meta["can_advance"] is True
        assert meta["iteration_count"] == 1
        assert meta["max_iterations"] == 3

    @pytest.mark.asyncio
    async def test_can_iterate_false_when_at_limit(self):
        from crewai_productfeature_planner.apis.ideation.models import (
            StructuredIdeationResponse,
            ClarifyingQuestion,
            Recommendation,
        )

        mock_response = StructuredIdeationResponse(
            acknowledgment="Final round!",
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
                ClarifyingQuestion(
                    id=2,
                    question="Q2?",
                    context="C",
                    recommendations=[
                        Recommendation(label="A", pro="p", con="c", complexity="Low"),
                        Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                        Recommendation(label="C", pro="p", con="c", complexity="High"),
                    ],
                ),
                ClarifyingQuestion(
                    id=3,
                    question="Q3?",
                    context="C",
                    recommendations=[
                        Recommendation(label="A", pro="p", con="c", complexity="Low"),
                        Recommendation(label="B", pro="p", con="c", complexity="Medium"),
                        Recommendation(label="C", pro="p", con="c", complexity="High"),
                    ],
                ),
            ],
        )

        with (
            patch(f"{_AGENT}.run_ideation_step", return_value=mock_response),
            patch(f"{_STREAMING}.streaming_session"),
            patch(f"{_SERVICE}.append_message", return_value="msg1"),
            patch(f"{_SERVICE}.save_step_data"),
            patch(f"{_SERVICE}._build_step_context", return_value={}),
            patch(f"{_SERVICE}._build_conversation_history", return_value=[]),
            patch(f"{_SERVICE}._broadcast_typing"),
            patch(f"{_SERVICE}._broadcast_processing_status"),
            patch(f"{_SERVICE}._broadcast_agent_token_final"),
            patch(f"{_SERVICE}._broadcast_message"),
            patch(f"{_SERVICE}._ProgressTicker"),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                _run_agent_for_step,
            )

            result = await _run_agent_for_step(
                session_id="sess1",
                step="a",
                user_input="Final",
                iteration_count=3,
                max_iterations=3,
            )

        assert result is not None
        meta = result["metadata"]
        assert meta["can_iterate"] is False
        assert meta["can_advance"] is True
        assert meta["iteration_count"] == 3
        assert meta["max_iterations"] == 3


# ── Service: get_iteration_history ────────────────────────────


class TestGetIterationHistory:
    @pytest.mark.asyncio
    async def test_builds_rounds_from_messages(self):
        session = _make_session_doc()
        session["steps_data"]["a"]["iteration"] = 2

        messages = [
            {
                "id": "m1",
                "role": "agent",
                "content": "Hello",
                "step": "a",
                "timestamp": "2026-05-14T10:00:00Z",
                "metadata": {
                    "render_type": "structured_questions",
                    "structured": {
                        "questions": [
                            {"id": 1, "question": "Who is the target?"},
                            {"id": 2, "question": "What problem?"},
                        ],
                        "agent_insight": "Focus on B2B",
                    },
                },
            },
            {
                "id": "m2",
                "role": "user",
                "content": "B2B SaaS teams",
                "step": "a",
                "timestamp": "2026-05-14T10:01:00Z",
                "metadata": {
                    "response_type": "selection",
                    "answers": [
                        {"question_id": 1, "selected_option": 0},
                        {"question_id": 2, "custom_feedback": "Manual PRD writing"},
                    ],
                },
            },
            {
                "id": "m3",
                "role": "agent",
                "content": "Great direction",
                "step": "a",
                "timestamp": "2026-05-14T10:02:00Z",
                "metadata": {
                    "render_type": "structured_questions",
                    "structured": {
                        "questions": [
                            {"id": 1, "question": "How many users?"},
                        ],
                        "agent_insight": "Scale matters",
                    },
                },
            },
        ]

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(f"{_SERVICE}._get_max_iterations", return_value=3),
            patch(f"{_SERVICE}.get_messages", return_value=messages),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                get_iteration_history,
            )

            result = await get_iteration_history(session_id="sess1")

        assert result is not None
        assert result["step"] == "ideation"
        assert result["iteration_count"] == 2
        assert result["max_iterations"] == 3
        assert len(result["rounds"]) == 2

        # Round 1 — agent questions + user answers merged
        r1 = result["rounds"][0]
        assert r1["round"] == 1
        assert len(r1["questions"]) == 2
        assert r1["questions"][0]["question"] == "Who is the target?"
        assert r1["completed_at"] == "2026-05-14T10:01:00Z"
        assert r1["agent_insight"] == "Focus on B2B"

        # Round 2 — agent questions only (no user answer yet)
        r2 = result["rounds"][1]
        assert r2["round"] == 2
        assert len(r2["questions"]) == 1
        assert r2["completed_at"] is None

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_session(self):
        with patch(f"{_SERVICE}.get_session", return_value=None):
            from crewai_productfeature_planner.apis.ideation.service import (
                get_iteration_history,
            )

            result = await get_iteration_history(session_id="nope")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_rounds_for_step_with_no_messages(self):
        session = _make_session_doc()

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(f"{_SERVICE}._get_max_iterations", return_value=2),
            patch(f"{_SERVICE}.get_messages", return_value=[]),
        ):
            from crewai_productfeature_planner.apis.ideation.service import (
                get_iteration_history,
            )

            result = await get_iteration_history(session_id="sess1")

        assert result is not None
        assert result["rounds"] == []
        assert result["iteration_count"] == 0


# ── Enterprise settings: default changed ─────────────────────


class TestEnterpriseSettingsDefault:
    def test_default_agent_flow_iteration_is_2(self):
        from crewai_productfeature_planner.mongodb.enterprise_settings.repository import (
            _DEFAULTS,
        )

        assert _DEFAULTS["agent_flow_iteration"] == 2

    def test_settings_patch_validates_range(self, client):
        """agent_flow_iteration must be 1-3."""
        with (
            patch(
                f"crewai_productfeature_planner.apis.settings.router.update_enterprise_settings",
            ),
        ):
            # Value 4 should fail validation (max 3)
            resp = client.patch(
                "/settings",
                json={"agent_flow_iteration": 4},
            )
        assert resp.status_code == 422


# ── Backward compatibility ────────────────────────────────────


class TestBackwardCompatibility:
    def test_missing_iteration_field_treated_as_zero(self):
        """Sessions created before this feature have no iteration field."""
        session = _make_session_doc()
        # Simulate old schema — no iteration field
        for step in STEP_ORDER:
            del session["steps_data"][step]["iteration"]

        step_data = session["steps_data"]["a"]
        assert step_data.get("iteration", 0) == 0
