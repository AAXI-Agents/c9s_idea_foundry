"""Tests for save_refinement_options in working_ideas._sections."""

from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.mongodb.working_ideas._sections import (
    save_refinement_options,
)


@patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db")
def test_save_refinement_options_writes_to_mongo(mock_get_db):
    """Should set refinement_options_history on the document."""
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    mock_get_db.return_value = {"workingIdeas": mock_collection}

    history = [
        {"iteration": 3, "trigger": "auto_cycles_complete",
         "options": ["a", "b", "c"], "selected": 0},
    ]
    result = save_refinement_options("run_123", history)
    assert result is True
    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"run_id": "run_123"}
    update = call_args[0][1]
    assert update["$set"]["refinement_options_history"] == history


@patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db")
def test_save_refinement_options_returns_false_on_no_modify(mock_get_db):
    mock_collection = MagicMock()
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    mock_get_db.return_value = {"workingIdeas": mock_collection}
    result = save_refinement_options("run_x", [{"iteration": 1}])
    assert result is False


def test_save_refinement_options_skips_empty_run_id():
    assert save_refinement_options("", [{"iteration": 1}]) is False


def test_save_refinement_options_skips_empty_history():
    assert save_refinement_options("run_1", []) is False
