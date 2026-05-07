"""Tests for auto-create idea from ideation session completion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.ideation.service import (
    _auto_create_idea_from_session,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext

_SERVICE = "crewai_productfeature_planner.apis.ideation.service"


def _tenant():
    return TenantContext(enterprise_id="ent-1", organization_id="org-1")


def _make_completed_session(**overrides):
    session = {
        "session_id": "sess-001",
        "user_id": "user-1",
        "project_id": "proj-1",
        "title": "My Idea",
        "status": "completed",
        "current_step": "e",
        "steps_data": {
            "a": {"input": "raw idea", "output": "Refined summary", "approved": True},
            "b": {"input": None, "output": "Persona analysis", "approved": True},
            "c": {"input": None, "output": "Solution design", "approved": True},
            "d": {"input": None, "output": "Feature goals", "approved": True},
            "e": {"input": None, "output": "Tech stack rec", "approved": True},
        },
    }
    session.update(overrides)
    return session


class TestAutoCreateIdea:
    def test_creates_idea_from_completed_session(self):
        session = _make_completed_session()
        idea_doc = {
            "idea_id": "idea-abc",
            "project_id": "proj-1",
            "title": "My Idea",
            "status": "draft",
        }

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(
                "crewai_productfeature_planner.mongodb.ideas.repository.create_idea",
                return_value=idea_doc,
            ) as mock_create,
        ):
            result = _auto_create_idea_from_session(
                session_id="sess-001", tenant=_tenant()
            )

        assert result is not None
        assert result["idea_id"] == "idea-abc"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["project_id"] == "proj-1"
        assert call_kwargs["title"] == "My Idea"
        assert call_kwargs["created_by"] == "user-1"
        assert call_kwargs["ideation_session_id"] == "sess-001"
        assert "Executive Summary & Mission" in call_kwargs["description"]
        assert "Tech stack rec" in call_kwargs["description"]

    def test_returns_none_when_session_not_found(self):
        with patch(f"{_SERVICE}.get_session", return_value=None):
            result = _auto_create_idea_from_session(
                session_id="missing", tenant=_tenant()
            )
        assert result is None

    def test_creates_idea_with_empty_steps(self):
        session = _make_completed_session()
        session["steps_data"] = {
            k: {"input": None, "output": None, "approved": False}
            for k in "abcde"
        }
        idea_doc = {"idea_id": "idea-empty", "status": "draft"}

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(
                "crewai_productfeature_planner.mongodb.ideas.repository.create_idea",
                return_value=idea_doc,
            ) as mock_create,
        ):
            result = _auto_create_idea_from_session(
                session_id="sess-001", tenant=_tenant()
            )

        assert result is not None
        assert mock_create.call_args.kwargs["description"] == ""

    def test_handles_structured_output(self):
        session = _make_completed_session()
        session["steps_data"]["a"]["output"] = {
            "acknowledgment": "Great idea!",
            "summary": "AI chatbot for customer service",
        }
        idea_doc = {"idea_id": "idea-struct", "status": "draft"}

        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(
                "crewai_productfeature_planner.mongodb.ideas.repository.create_idea",
                return_value=idea_doc,
            ) as mock_create,
        ):
            result = _auto_create_idea_from_session(
                session_id="sess-001", tenant=_tenant()
            )

        assert result is not None
        desc = mock_create.call_args.kwargs["description"]
        assert "Great idea!" in desc

    def test_returns_none_on_create_failure(self):
        session = _make_completed_session()
        with (
            patch(f"{_SERVICE}.get_session", return_value=session),
            patch(
                "crewai_productfeature_planner.mongodb.ideas.repository.create_idea",
                return_value=None,
            ),
        ):
            result = _auto_create_idea_from_session(
                session_id="sess-001", tenant=_tenant()
            )
        assert result is None
