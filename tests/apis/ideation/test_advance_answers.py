"""Tests for advance-with-answers — persisting user Q&A on step transition."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC = "crewai_productfeature_planner.apis.ideation.service"


def _session_doc(**overrides):
    doc = {
        "session_id": "sess-1",
        "user_id": "u1",
        "project_id": "proj-1",
        "title": "Test Idea",
        "status": "active",
        "current_step": "a",
        "steps_data": {
            step: {
                "input": None,
                "output": "some output" if step == "a" else None,
                "approved": False,
                "completed_at": None,
            }
            for step in ["a", "b", "c", "d", "e"]
        },
        "messages": [],
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
    }
    doc.update(overrides)
    return doc


class TestAdvanceWithAnswers:
    """Verify handle_advance persists user answers before step transition."""

    @pytest.mark.asyncio
    async def test_advance_with_answers_persists_message(self):
        """When approved_output contains answers + user_summary,
        a user message is appended before the step advances."""
        from crewai_productfeature_planner.apis.ideation.service import handle_advance

        answers = [
            {"question_id": 1, "selected_option": 0},
            {"question_id": 2, "selected_option": None, "custom_feedback": "Custom answer"},
        ]
        approved_output = {
            "summary": "Step summary...",
            "user_summary": "1. Q1\n   → Option A\n\n2. Q2\n   → Custom: Custom answer",
            "answers": answers,
        }

        with (
            patch(f"{_SVC}.get_session") as mock_get,
            patch(f"{_SVC}.append_message") as mock_append,
            patch(f"{_SVC}.advance_step", return_value="b") as mock_advance,
            patch(f"{_SVC}.STEP_PROMPTS", {"a": "Prompt A", "b": "Prompt B"}),
            patch(f"{_SVC}._run_agent_for_step", new_callable=AsyncMock),
            patch(f"{_SVC}._get_max_iterations", return_value=2),
        ):
            mock_get.return_value = _session_doc()

            result = await handle_advance(
                session_id="sess-1",
                approved_output=approved_output,
            )

        assert result["new_step"] == "b"

        # Find the user message call (not the agent prompt for step b)
        user_calls = [
            c for c in mock_append.call_args_list
            if c.kwargs.get("role") == "user"
        ]
        assert len(user_calls) == 1, f"Expected 1 user message, got {len(user_calls)}"

        call_kw = user_calls[0].kwargs
        assert call_kw["content"] == approved_output["user_summary"]
        assert call_kw["step"] == "a"
        assert call_kw["content_type"] == "selection"

        meta = call_kw["metadata"]
        assert meta["response_type"] == "selection"
        assert meta["flow_step"] == "a"
        assert meta["is_advance_submission"] is True
        assert meta["answers"] == answers

    @pytest.mark.asyncio
    async def test_advance_with_answers_only_no_summary(self):
        """When only answers are provided (no user_summary), content is empty string."""
        from crewai_productfeature_planner.apis.ideation.service import handle_advance

        answers = [{"question_id": 1, "selected_option": 2}]
        approved_output = {"summary": "...", "answers": answers}

        with (
            patch(f"{_SVC}.get_session") as mock_get,
            patch(f"{_SVC}.append_message") as mock_append,
            patch(f"{_SVC}.advance_step", return_value="b"),
            patch(f"{_SVC}.STEP_PROMPTS", {"a": "A", "b": "B"}),
            patch(f"{_SVC}._run_agent_for_step", new_callable=AsyncMock),
            patch(f"{_SVC}._get_max_iterations", return_value=2),
        ):
            mock_get.return_value = _session_doc()
            await handle_advance(session_id="sess-1", approved_output=approved_output)

        user_calls = [
            c for c in mock_append.call_args_list if c.kwargs.get("role") == "user"
        ]
        assert len(user_calls) == 1
        assert user_calls[0].kwargs["content"] == ""

    @pytest.mark.asyncio
    async def test_advance_with_user_summary_only(self):
        """When only user_summary is provided (no answers array), still persists."""
        from crewai_productfeature_planner.apis.ideation.service import handle_advance

        approved_output = {
            "summary": "...",
            "user_summary": "1. Q → Option B",
        }

        with (
            patch(f"{_SVC}.get_session") as mock_get,
            patch(f"{_SVC}.append_message") as mock_append,
            patch(f"{_SVC}.advance_step", return_value="b"),
            patch(f"{_SVC}.STEP_PROMPTS", {"a": "A", "b": "B"}),
            patch(f"{_SVC}._run_agent_for_step", new_callable=AsyncMock),
            patch(f"{_SVC}._get_max_iterations", return_value=2),
        ):
            mock_get.return_value = _session_doc()
            await handle_advance(session_id="sess-1", approved_output=approved_output)

        user_calls = [
            c for c in mock_append.call_args_list if c.kwargs.get("role") == "user"
        ]
        assert len(user_calls) == 1
        meta = user_calls[0].kwargs["metadata"]
        assert "answers" not in meta  # no answers key when not provided

    @pytest.mark.asyncio
    async def test_advance_without_answers_backward_compat(self):
        """When approved_output has only summary (no answers), no extra message."""
        from crewai_productfeature_planner.apis.ideation.service import handle_advance

        approved_output = {"summary": "Step summary only"}

        with (
            patch(f"{_SVC}.get_session") as mock_get,
            patch(f"{_SVC}.append_message") as mock_append,
            patch(f"{_SVC}.advance_step", return_value="b"),
            patch(f"{_SVC}.STEP_PROMPTS", {"a": "A", "b": "B"}),
            patch(f"{_SVC}._run_agent_for_step", new_callable=AsyncMock),
            patch(f"{_SVC}._get_max_iterations", return_value=2),
        ):
            mock_get.return_value = _session_doc()
            await handle_advance(session_id="sess-1", approved_output=approved_output)

        # No user message should be persisted — only the agent prompt for step b
        user_calls = [
            c for c in mock_append.call_args_list if c.kwargs.get("role") == "user"
        ]
        assert len(user_calls) == 0

    @pytest.mark.asyncio
    async def test_advance_no_approved_output_backward_compat(self):
        """When approved_output is None, no extra message persisted."""
        from crewai_productfeature_planner.apis.ideation.service import handle_advance

        with (
            patch(f"{_SVC}.get_session") as mock_get,
            patch(f"{_SVC}.append_message") as mock_append,
            patch(f"{_SVC}.advance_step", return_value="b"),
            patch(f"{_SVC}.STEP_PROMPTS", {"a": "A", "b": "B"}),
            patch(f"{_SVC}._run_agent_for_step", new_callable=AsyncMock),
            patch(f"{_SVC}._get_max_iterations", return_value=2),
        ):
            mock_get.return_value = _session_doc()
            await handle_advance(session_id="sess-1", approved_output=None)

        user_calls = [
            c for c in mock_append.call_args_list if c.kwargs.get("role") == "user"
        ]
        assert len(user_calls) == 0

    @pytest.mark.asyncio
    async def test_advance_answers_with_feedback_both_persisted(self):
        """When both feedback and answers are provided, both messages are saved."""
        from crewai_productfeature_planner.apis.ideation.service import handle_advance

        approved_output = {
            "summary": "...",
            "user_summary": "1. Q → A",
            "answers": [{"question_id": 1, "selected_option": 0}],
        }

        with (
            patch(f"{_SVC}.get_session") as mock_get,
            patch(f"{_SVC}.append_message") as mock_append,
            patch(f"{_SVC}.advance_step", return_value="b"),
            patch(f"{_SVC}.STEP_PROMPTS", {"a": "A", "b": "B"}),
            patch(f"{_SVC}._run_agent_for_step", new_callable=AsyncMock),
            patch(f"{_SVC}._get_max_iterations", return_value=2),
        ):
            mock_get.return_value = _session_doc()
            await handle_advance(
                session_id="sess-1",
                feedback="Minor tweak",
                approved_output=approved_output,
            )

        user_calls = [
            c for c in mock_append.call_args_list if c.kwargs.get("role") == "user"
        ]
        # 2 user messages: feedback + answers
        assert len(user_calls) == 2
        # First is the feedback
        assert "[Feedback before advancing]" in user_calls[0].kwargs["content"]
        # Second is the answers
        assert user_calls[1].kwargs["metadata"]["is_advance_submission"] is True
