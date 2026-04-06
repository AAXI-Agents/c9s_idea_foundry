"""Tests for section conversation persistence functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_COMMON = "crewai_productfeature_planner.mongodb.working_ideas._common"


@pytest.fixture()
def mock_db():
    """Patch _common.get_db so we don't need a real MongoDB."""
    col = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    with patch(f"{_COMMON}.get_db", return_value=db):
        yield col


class TestSaveSectionMessage:
    """Test save_section_message function."""

    def test_appends_message(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            save_section_message,
        )
        mock_db.update_one.return_value = MagicMock(modified_count=1)
        result = save_section_message("r1", "problem_statement", "user", "Add more detail")
        assert result is True
        mock_db.update_one.assert_called_once()
        call_args = mock_db.update_one.call_args
        update = call_args[0][1]
        assert "$push" in update
        pushed = update["$push"]["section_conversations.problem_statement"]
        assert pushed["role"] == "user"
        assert pushed["content"] == "Add more detail"

    def test_rejects_dot_in_section_key(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            save_section_message,
        )
        result = save_section_message("r1", "bad.key", "user", "x")
        assert result is False
        mock_db.update_one.assert_not_called()

    def test_rejects_dollar_in_section_key(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            save_section_message,
        )
        result = save_section_message("r1", "$bad", "user", "x")
        assert result is False

    def test_returns_false_on_db_error(self, mock_db):
        from pymongo.errors import PyMongoError
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            save_section_message,
        )
        mock_db.update_one.side_effect = PyMongoError("fail")
        result = save_section_message("r1", "problem_statement", "user", "x")
        assert result is False


class TestGetSectionConversation:
    """Test get_section_conversation function."""

    def test_returns_empty_when_no_doc(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            get_section_conversation,
        )
        mock_db.find_one.return_value = None
        assert get_section_conversation("r1", "problem_statement") == []

    def test_returns_conversation(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            get_section_conversation,
        )
        mock_db.find_one.return_value = {
            "section_conversations": {
                "problem_statement": [
                    {"role": "user", "content": "Add detail", "timestamp": "2026-04-05"},
                    {"role": "agent", "content": "Done", "timestamp": "2026-04-05"},
                ],
            },
        }
        convos = get_section_conversation("r1", "problem_statement")
        assert len(convos) == 2
        assert convos[0]["role"] == "user"

    def test_rejects_dot_in_key(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            get_section_conversation,
        )
        assert get_section_conversation("r1", "bad.key") == []


class TestSectionSummaryNotes:
    """Test summary notes functions."""

    def test_save_summary_note(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            save_section_summary_note,
        )
        mock_db.update_one.return_value = MagicMock(modified_count=1)
        result = save_section_summary_note("r1", "problem_statement", "Key decisions: ...")
        assert result is True
        call_args = mock_db.update_one.call_args
        update = call_args[0][1]
        assert "section_summary_notes.problem_statement" in update["$set"]

    def test_get_summary_notes(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            get_section_summary_notes,
        )
        mock_db.find_one.return_value = {
            "section_summary_notes": {
                "problem_statement": "Key decisions here",
                "user_personas": "3 personas defined",
            },
        }
        notes = get_section_summary_notes("r1")
        assert len(notes) == 2
        assert "problem_statement" in notes

    def test_get_summary_notes_empty(self, mock_db):
        from crewai_productfeature_planner.mongodb.working_ideas._sections import (
            get_section_summary_notes,
        )
        mock_db.find_one.return_value = None
        assert get_section_summary_notes("r1") == {}
