"""Tests for mongodb.slack_oauth.repository — per-team Slack OAuth storage."""

import time
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.slack_oauth.repository import (
    SLACK_OAUTH_COLLECTION,
    delete_team,
    get_all_teams,
    get_team,
    token_status,
    update_tokens,
    upsert_team,
)

_DB_PATH = "crewai_productfeature_planner.mongodb.slack_oauth.repository.get_db"

TEAM_ID = "T_TEST_123"


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


def _mock_db():
    """Return a MagicMock wired as ``get_db()[COLLECTION]``."""
    mock_coll = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_coll)
    return mock_db, mock_coll


# ---------------------------------------------------------------------------
# upsert_team
# ---------------------------------------------------------------------------


class TestUpsertTeam:
    def test_creates_new_team(self):
        mock_db, mock_coll = _mock_db()
        expected = {"team_id": TEAM_ID, "access_token": "xoxb-new"}
        mock_coll.find_one_and_update.return_value = expected

        with patch(_DB_PATH, return_value=mock_db):
            result = upsert_team(
                team_id=TEAM_ID,
                team_name="Acme",
                access_token="xoxb-new",
                refresh_token="xoxr-new",
                token_type="bot",
                scope="chat:write",
                bot_user_id="B123",
                app_id="A123",
                expires_in=43200,
                authed_user_id="U123",
            )

        assert result is not None
        assert result["team_id"] == TEAM_ID
        mock_coll.find_one_and_update.assert_called_once()

        call_args = mock_coll.find_one_and_update.call_args
        assert call_args[0][0] == {"team_id": TEAM_ID}
        set_doc = call_args[0][1]["$set"]
        assert set_doc["team_id"] == TEAM_ID
        assert set_doc["access_token"] == "xoxb-new"
        assert set_doc["refresh_token"] == "xoxr-new"

    def test_returns_none_on_db_error(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.find_one_and_update.side_effect = ServerSelectionTimeoutError(
            "timeout"
        )

        with patch(_DB_PATH, return_value=mock_db):
            result = upsert_team(
                team_id=TEAM_ID,
                access_token="xoxb-fail",
                expires_in=43200,
            )

        assert result is None

    def test_upsert_sets_expires_at(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.find_one_and_update.return_value = {}
        before = time.time()

        with patch(_DB_PATH, return_value=mock_db):
            upsert_team(
                team_id=TEAM_ID,
                access_token="xoxb-test",
                expires_in=3600,
            )

        call_args = mock_coll.find_one_and_update.call_args
        set_doc = call_args[0][1]["$set"]
        # expires_at should be approx now + 3600
        assert set_doc["expires_at"] >= before + 3600
        assert set_doc["expires_at"] < before + 3610  # small tolerance


# ---------------------------------------------------------------------------
# update_tokens
# ---------------------------------------------------------------------------


class TestUpdateTokens:
    def test_updates_existing_team(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.update_one.return_value = MagicMock(matched_count=1)

        with patch(_DB_PATH, return_value=mock_db):
            result = update_tokens(
                team_id=TEAM_ID,
                access_token="xoxb-refreshed",
                refresh_token="xoxr-refreshed",
                expires_in=43200,
            )

        assert result is True
        mock_coll.update_one.assert_called_once()

    def test_returns_false_for_unknown_team(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.update_one.return_value = MagicMock(matched_count=0)

        with patch(_DB_PATH, return_value=mock_db):
            result = update_tokens(
                team_id="T_UNKNOWN",
                access_token="xoxb-nope",
            )

        assert result is False

    def test_returns_false_on_db_error(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.update_one.side_effect = ServerSelectionTimeoutError("timeout")

        with patch(_DB_PATH, return_value=mock_db):
            result = update_tokens(
                team_id=TEAM_ID,
                access_token="xoxb-err",
            )

        assert result is False


# ---------------------------------------------------------------------------
# get_team
# ---------------------------------------------------------------------------


class TestGetTeam:
    def test_returns_doc(self):
        mock_db, mock_coll = _mock_db()
        expected = {"team_id": TEAM_ID, "access_token": "xoxb-test"}
        mock_coll.find_one.return_value = expected

        with patch(_DB_PATH, return_value=mock_db):
            doc = get_team(TEAM_ID)

        assert doc == expected
        mock_coll.find_one.assert_called_once_with({"team_id": TEAM_ID})

    def test_returns_none_when_not_found(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.find_one.return_value = None

        with patch(_DB_PATH, return_value=mock_db):
            doc = get_team("T_MISSING")

        assert doc is None

    def test_returns_none_on_db_error(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.find_one.side_effect = ServerSelectionTimeoutError("timeout")

        with patch(_DB_PATH, return_value=mock_db):
            doc = get_team(TEAM_ID)

        assert doc is None


# ---------------------------------------------------------------------------
# get_all_teams
# ---------------------------------------------------------------------------


class TestGetAllTeams:
    def test_returns_all_docs(self):
        mock_db, mock_coll = _mock_db()
        docs = [
            {"team_id": "T1", "access_token": "xoxb-1"},
            {"team_id": "T2", "access_token": "xoxb-2"},
        ]
        mock_coll.find.return_value = docs

        with patch(_DB_PATH, return_value=mock_db):
            result = get_all_teams()

        assert len(result) == 2
        assert result[0]["team_id"] == "T1"

    def test_returns_empty_list_on_error(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.find.side_effect = ServerSelectionTimeoutError("timeout")

        with patch(_DB_PATH, return_value=mock_db):
            result = get_all_teams()

        assert result == []


# ---------------------------------------------------------------------------
# delete_team
# ---------------------------------------------------------------------------


class TestDeleteTeam:
    def test_deletes_existing(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.delete_one.return_value = MagicMock(deleted_count=1)

        with patch(_DB_PATH, return_value=mock_db):
            result = delete_team(TEAM_ID)

        assert result is True

    def test_returns_false_when_not_found(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.delete_one.return_value = MagicMock(deleted_count=0)

        with patch(_DB_PATH, return_value=mock_db):
            result = delete_team("T_GHOST")

        assert result is False

    def test_returns_false_on_db_error(self):
        mock_db, mock_coll = _mock_db()
        mock_coll.delete_one.side_effect = ServerSelectionTimeoutError("timeout")

        with patch(_DB_PATH, return_value=mock_db):
            result = delete_team(TEAM_ID)

        assert result is False


# ---------------------------------------------------------------------------
# token_status
# ---------------------------------------------------------------------------


class TestTokenStatus:
    def test_not_installed(self):
        with patch(_DB_PATH) as mock_db:
            mock_coll = MagicMock()
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            mock_coll.find_one.return_value = None

            status = token_status("T_MISSING")

        assert status["installed"] is False
        assert status["team_id"] == "T_MISSING"

    def test_static_bot_token(self):
        doc = {
            "team_id": TEAM_ID,
            "team_name": "Acme",
            "access_token": "xoxb-static-token",
            "refresh_token": None,
            "expires_at": time.time() + 86400,
            "bot_user_id": "B123",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "installed_at": "2025-12-01T00:00:00+00:00",
        }
        with patch(_DB_PATH) as mock_db:
            mock_coll = MagicMock()
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            mock_coll.find_one.return_value = doc

            status = token_status(TEAM_ID)

        assert status["installed"] is True
        assert status["token_type"] == "static_bot"
        assert status["is_rotating"] is False
        assert status["has_refresh_token"] is False

    def test_rotating_bot_token(self):
        doc = {
            "team_id": TEAM_ID,
            "team_name": "Acme",
            "access_token": "xoxe.xoxb-rotating",
            "refresh_token": "xoxr-refresh",
            "expires_at": time.time() + 3600,
            "bot_user_id": "B123",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "installed_at": "2025-12-01T00:00:00+00:00",
        }
        with patch(_DB_PATH) as mock_db:
            mock_coll = MagicMock()
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            mock_coll.find_one.return_value = doc

            status = token_status(TEAM_ID)

        assert status["installed"] is True
        assert status["token_type"] == "rotating_bot"
        assert status["is_rotating"] is True
        assert status["has_refresh_token"] is True
        assert status["expires_in_seconds"] > 0
