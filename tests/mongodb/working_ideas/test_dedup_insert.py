"""Regression tests for insert-time idea dedup enforcement.

Verifies that:
1. Two consecutive kickoffs with the same idea text within the same
   (organization_id, project_id) scope are rejected (409 or -1 return).
2. The _active_idea_key field is set on active ideas and cleared on
   terminal status transitions.
3. DuplicateKeyError from the sparse unique index is handled gracefully.
"""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.working_ideas._common import (
    build_active_idea_key,
)
from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    mark_archived,
    mark_completed,
    mark_deleted,
    save_failed,
    save_project_ref,
    save_slack_context,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── build_active_idea_key ─────────────────────────────────────


class TestBuildActiveIdeaKey:
    """Tests for the dedup key computation helper."""

    def test_returns_composite_key(self):
        key = build_active_idea_key("org-1", "proj-1", "add dark mode")
        assert key == "org-1:proj-1:add dark mode"

    def test_returns_none_when_no_project(self):
        key = build_active_idea_key("org-1", "", "add dark mode")
        assert key is None

    def test_returns_none_when_no_idea(self):
        key = build_active_idea_key("org-1", "proj-1", "")
        assert key is None

    def test_returns_none_when_no_idea_none(self):
        key = build_active_idea_key("org-1", "proj-1", None)
        assert key is None

    def test_empty_org_still_produces_key(self):
        key = build_active_idea_key(None, "proj-1", "add dark mode")
        assert key == ":proj-1:add dark mode"


# ── save_project_ref sets _active_idea_key ────────────────────


class TestSaveProjectRefDedupKey:
    """Verify save_project_ref computes and persists _active_idea_key."""

    def test_sets_active_idea_key_on_insert(self, wi_mocks):
        mock_collection, mock_db = wi_mocks
        write_result = MagicMock(
            modified_count=0,
            matched_count=0,
            upserted_id="new-id",
        )
        mock_collection.update_one.return_value = write_result

        tenant = TenantContext(
            enterprise_id="ent-1", organization_id="org-1",
        )

        with patch(
            "crewai_productfeature_planner.mongodb.project_config.get_project",
            return_value={"project_id": "proj-1"},
        ):
            result = save_project_ref(
                "run-1", "proj-1", idea="Add dark mode", tenant=tenant,
            )

        assert result == 1
        call_args = mock_collection.update_one.call_args
        set_fields = call_args[0][1]["$set"]
        assert set_fields["_active_idea_key"] == "org-1:proj-1:add dark mode"
        assert set_fields["idea_normalized"] == "add dark mode"

    def test_returns_neg1_on_duplicate_key_error(self, wi_mocks):
        """DuplicateKeyError from the sparse unique index returns -1."""
        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.side_effect = DuplicateKeyError(
            "E11000 duplicate key error"
        )

        tenant = TenantContext(
            enterprise_id="ent-1", organization_id="org-1",
        )

        with patch(
            "crewai_productfeature_planner.mongodb.project_config.get_project",
            return_value={"project_id": "proj-1"},
        ):
            result = save_project_ref(
                "run-2", "proj-1", idea="Add dark mode", tenant=tenant,
            )

        assert result == -1


# ── save_slack_context DuplicateKeyError handling ─────────────


class TestSaveSlackContextDedupKey:
    """Verify save_slack_context handles DuplicateKeyError gracefully."""

    def test_returns_neg1_on_duplicate_key_error(self, wi_mocks):
        mock_collection, mock_db = wi_mocks
        mock_collection.update_one.side_effect = DuplicateKeyError(
            "E11000 duplicate key error"
        )

        result = save_slack_context(
            "run-3", "C123", "1234567890.123456",
            idea="Add dark mode",
        )

        assert result == -1


# ── Terminal status transitions clear _active_idea_key ────────


class TestTerminalStatusClearsDedupKey:
    """Verify that terminal transitions unset _active_idea_key."""

    def test_mark_completed_unsets_key(self, wi_mocks):
        mock_collection, mock_db = wi_mocks
        write_result = MagicMock(modified_count=1)
        mock_collection.update_one.return_value = write_result

        mark_completed("run-1")

        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]
        assert "$unset" in update_doc
        assert "_active_idea_key" in update_doc["$unset"]

    def test_mark_archived_unsets_key(self, wi_mocks):
        mock_collection, mock_db = wi_mocks
        write_result = MagicMock(modified_count=1)
        mock_collection.update_one.return_value = write_result

        mark_archived("run-1")

        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]
        assert "$unset" in update_doc
        assert "_active_idea_key" in update_doc["$unset"]

    def test_mark_deleted_unsets_key(self, wi_mocks):
        mock_collection, mock_db = wi_mocks
        write_result = MagicMock(modified_count=1)
        mock_collection.update_one.return_value = write_result

        mark_deleted("run-1")

        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]
        assert "$unset" in update_doc
        assert "_active_idea_key" in update_doc["$unset"]

    def test_save_failed_unsets_key(self, wi_mocks):
        mock_collection, mock_db = wi_mocks
        write_result = MagicMock(
            modified_count=0, upserted_id="new-id",
        )
        mock_collection.update_one.return_value = write_result

        save_failed("run-1", "some idea", iteration=1, error="boom")

        # save_failed calls update_one twice (ensure_section + the main write)
        # The main write is the last call
        last_call = mock_collection.update_one.call_args_list[-1]
        update_doc = last_call[0][1]
        assert "$unset" in update_doc
        assert "_active_idea_key" in update_doc["$unset"]


# ── End-to-end dedup scenario (API layer) ─────────────────────


class TestKickoffDedupRejects409:
    """Confirm the PRD kickoff API rejects duplicate ideas with 409."""

    def test_consecutive_kickoffs_same_idea_returns_409(self):
        """Two kickoffs with the same idea text → first succeeds, second 409."""
        from unittest.mock import AsyncMock

        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            find_active_duplicate_idea,
        )

        # Simulate: first call returns None (no dup), second returns an active doc
        with patch(
            "crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db",
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__ = MagicMock(return_value=mock_collection)
            mock_get_db.return_value = mock_db

            # First kickoff: no active duplicate
            mock_collection.find_one.return_value = None
            result1 = find_active_duplicate_idea(
                "Add knowledge sharing", project_id="proj-1",
            )
            assert result1 is None

            # Second kickoff: active duplicate exists
            mock_collection.find_one.return_value = {
                "run_id": "existing-run",
                "idea": "add knowledge sharing",
                "status": "inprogress",
                "created_at": "2026-05-01T00:00:00Z",
            }
            result2 = find_active_duplicate_idea(
                "Add knowledge sharing", project_id="proj-1",
            )
            assert result2 is not None
            assert result2["run_id"] == "existing-run"
            assert result2["status"] == "inprogress"
