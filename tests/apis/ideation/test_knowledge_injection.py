"""Tests for ideation knowledge context injection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
    STEP_ORDER,
    update_session_knowledge_context,
)

_REPO = "crewai_productfeature_planner.mongodb.ideation_sessions.repository"
_SVC = "crewai_productfeature_planner.apis.ideation.service"
_AGENT = "crewai_productfeature_planner.agents.ideation.agent"
_KNOWLEDGE_CTX = "crewai_productfeature_planner.services.knowledge_context"


def _mock_col(mock_db):
    return mock_db.__getitem__.return_value


# ── Repository: knowledge_context field ───────────────────────


class TestSessionKnowledgeContextField:
    def test_create_session_includes_knowledge_context(self):
        from crewai_productfeature_planner.mongodb.ideation_sessions.repository import (
            create_session,
        )

        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.insert_one.return_value = MagicMock(acknowledged=True)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            result = create_session(user_id="u1", title="Test", project_id="p1")

        assert result is not None
        assert "knowledge_context" in result
        assert result["knowledge_context"] == ""

    def test_update_session_knowledge_context(self):
        mock_db = MagicMock()
        col = _mock_col(mock_db)

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            update_session_knowledge_context(
                session_id="sess1",
                knowledge_context="## Project Knowledge\nSome context",
            )

        col.update_one.assert_called_once()
        call_args = col.update_one.call_args
        set_doc = call_args[0][1]["$set"]
        assert set_doc["knowledge_context"] == "## Project Knowledge\nSome context"
        assert "updated_at" in set_doc

    def test_update_knowledge_context_handles_db_error(self):
        from pymongo.errors import PyMongoError

        mock_db = MagicMock()
        col = _mock_col(mock_db)
        col.update_one.side_effect = PyMongoError("timeout")

        with patch(f"{_REPO}.get_db", return_value=mock_db):
            # Should not raise — logs warning
            update_session_knowledge_context(
                session_id="sess1",
                knowledge_context="ctx",
            )


# ── Service: knowledge context fetch on session start ─────────


class TestServiceKnowledgeFetch:
    @pytest.mark.asyncio
    async def test_start_session_fetches_and_stores_knowledge(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            start_ideation_session,
        )

        session_doc = {
            "session_id": "sess1",
            "user_id": "u1",
            "project_id": "proj1",
            "title": "Test",
            "status": "active",
            "current_step": "a",
            "steps_data": {
                s: {"input": None, "output": None, "approved": False, "completed_at": None}
                for s in STEP_ORDER
            },
            "messages": [],
            "knowledge_context": "",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
            "completed_at": None,
        }

        knowledge_ctx = "## Project Knowledge Context\n### Knowledge Summary\nTest summary"

        with (
            patch(f"{_SVC}.create_session", return_value=session_doc),
            patch(f"{_SVC}.append_message"),
            patch(f"{_KNOWLEDGE_CTX}.build_knowledge_context", return_value=knowledge_ctx) as mock_build,
            patch(f"{_SVC}.update_session_knowledge_context") as mock_update,
        ):
            result = await start_ideation_session(
                user_id="u1",
                title="Test",
                project_id="proj1",
            )

        assert result is not None
        mock_build.assert_called_once_with("proj1", tenant=None)
        mock_update.assert_called_once_with(
            session_id="sess1",
            knowledge_context=knowledge_ctx,
            tenant=None,
        )
        # In-memory session should have knowledge_context set
        assert result["knowledge_context"] == knowledge_ctx

    @pytest.mark.asyncio
    async def test_start_session_no_knowledge_skips_update(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            start_ideation_session,
        )

        session_doc = {
            "session_id": "sess2",
            "user_id": "u1",
            "project_id": "proj2",
            "title": "Test",
            "status": "active",
            "current_step": "a",
            "steps_data": {
                s: {"input": None, "output": None, "approved": False, "completed_at": None}
                for s in STEP_ORDER
            },
            "messages": [],
            "knowledge_context": "",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
            "completed_at": None,
        }

        with (
            patch(f"{_SVC}.create_session", return_value=session_doc),
            patch(f"{_SVC}.append_message"),
            patch(f"{_KNOWLEDGE_CTX}.build_knowledge_context", return_value="") as mock_build,
            patch(f"{_SVC}.update_session_knowledge_context") as mock_update,
        ):
            result = await start_ideation_session(
                user_id="u1",
                title="Test",
                project_id="proj2",
            )

        assert result is not None
        mock_build.assert_called_once()
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_session_knowledge_fetch_failure_continues(self):
        from crewai_productfeature_planner.apis.ideation.service import (
            start_ideation_session,
        )

        session_doc = {
            "session_id": "sess3",
            "user_id": "u1",
            "project_id": "proj3",
            "title": "Test",
            "status": "active",
            "current_step": "a",
            "steps_data": {
                s: {"input": None, "output": None, "approved": False, "completed_at": None}
                for s in STEP_ORDER
            },
            "messages": [],
            "knowledge_context": "",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
            "completed_at": None,
        }

        with (
            patch(f"{_SVC}.create_session", return_value=session_doc),
            patch(f"{_SVC}.append_message"),
            patch(f"{_KNOWLEDGE_CTX}.build_knowledge_context", side_effect=RuntimeError("DB down")),
            patch(f"{_SVC}.update_session_knowledge_context") as mock_update,
        ):
            result = await start_ideation_session(
                user_id="u1",
                title="Test",
                project_id="proj3",
            )

        # Session still created despite knowledge fetch failure
        assert result is not None
        mock_update.assert_not_called()


# ── Agent: knowledge_context in task description ──────────────


class TestAgentKnowledgeInjection:
    def test_knowledge_context_injected_into_task(self):
        """run_ideation_step passes knowledge_context into the task template."""
        from crewai_productfeature_planner.agents.ideation.agent import (
            run_ideation_step,
        )

        knowledge_ctx = "## Project Knowledge Context\nTest project summary"

        mock_result = MagicMock()
        mock_result.pydantic = None
        mock_result.raw = '{"acknowledgment": "test", "questions": [], "agent_insight": "insight"}'

        with (
            patch(f"{_AGENT}.build_ideation_agent") as mock_agent,
            patch(f"{_AGENT}.crew_kickoff_with_retry", return_value=mock_result),
            patch(f"{_AGENT}.Task") as mock_task_cls,
            patch(f"{_AGENT}.Crew"),
        ):
            mock_agent.return_value = MagicMock()
            mock_task_cls.return_value = MagicMock()

            run_ideation_step(
                step="a",
                user_input="A fitness app",
                knowledge_context=knowledge_ctx,
            )

        # Check that the Task was created with knowledge_context in description
        task_call = mock_task_cls.call_args
        description = task_call[1]["description"] if "description" in task_call[1] else task_call[0][0]
        assert "Test project summary" in description

    def test_no_knowledge_context_uses_default(self):
        """When no knowledge_context is provided, default placeholder is used."""
        from crewai_productfeature_planner.agents.ideation.agent import (
            run_ideation_step,
        )

        mock_result = MagicMock()
        mock_result.pydantic = None
        mock_result.raw = '{"acknowledgment": "test", "questions": [], "agent_insight": "insight"}'

        with (
            patch(f"{_AGENT}.build_ideation_agent") as mock_agent,
            patch(f"{_AGENT}.crew_kickoff_with_retry", return_value=mock_result),
            patch(f"{_AGENT}.Task") as mock_task_cls,
            patch(f"{_AGENT}.Crew"),
        ):
            mock_agent.return_value = MagicMock()
            mock_task_cls.return_value = MagicMock()

            run_ideation_step(
                step="a",
                user_input="A fitness app",
            )

        task_call = mock_task_cls.call_args
        description = task_call[1]["description"] if "description" in task_call[1] else task_call[0][0]
        assert "No project knowledge available" in description

    def test_all_steps_receive_knowledge_context(self):
        """Every ideation step (a-e) receives knowledge_context."""
        from crewai_productfeature_planner.agents.ideation.agent import (
            run_ideation_step,
        )

        knowledge_ctx = "## Project Knowledge Context\nShared context"

        for step in ["a", "b", "c", "d", "e"]:
            mock_result = MagicMock()
            mock_result.pydantic = None
            mock_result.raw = '{"acknowledgment": "test", "questions": [], "agent_insight": "insight"}'

            with (
                patch(f"{_AGENT}.build_ideation_agent") as mock_agent,
                patch(f"{_AGENT}.crew_kickoff_with_retry", return_value=mock_result),
                patch(f"{_AGENT}.Task") as mock_task_cls,
                patch(f"{_AGENT}.Crew"),
            ):
                mock_agent.return_value = MagicMock()
                mock_task_cls.return_value = MagicMock()

                run_ideation_step(
                    step=step,
                    user_input="test input",
                    knowledge_context=knowledge_ctx,
                )

            task_call = mock_task_cls.call_args
            description = task_call[1]["description"] if "description" in task_call[1] else task_call[0][0]
            assert "Shared context" in description, f"Step {step} missing knowledge_context"
