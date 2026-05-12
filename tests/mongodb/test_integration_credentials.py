"""Tests for the ``integrationCredentials`` MongoDB repository."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.mongodb._tenant import TenantContext


# ── Helpers ──────────────────────────────────────────────────────────

_TENANT = TenantContext(
    enterprise_id="ent-1",
    organization_id="org-1",
)

_SAMPLE_CREDS = {
    "base_url": "https://myco.atlassian.net",
    "username": "admin@myco.com",
    "api_token": "secret-token",
}


# ── get_credentials ──────────────────────────────────────────────────


class TestGetCredentials:
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.decrypt_value", side_effect=lambda x: f"DEC:{x}")
    def test_returns_decrypted(self, _dec, mock_db):
        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            get_credentials,
        )

        mock_col = MagicMock()
        mock_col.find_one.return_value = {
            "organization_id": "org-1",
            "provider": "atlassian",
            "credentials": {
                "base_url": "ENC:url",
                "username": "ENC:user",
                "api_token": "ENC:tok",
            },
            "confluence_base_url": "ENC:cfl",
        }
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = get_credentials("org-1", "atlassian", tenant=_TENANT)

        assert result is not None
        assert result["credentials"]["base_url"] == "DEC:ENC:url"
        assert result["credentials"]["username"] == "DEC:ENC:user"
        assert result["credentials"]["api_token"] == "DEC:ENC:tok"
        assert result["confluence_base_url"] == "DEC:ENC:cfl"

    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_returns_none_when_not_found(self, mock_db):
        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            get_credentials,
        )

        mock_col = MagicMock()
        mock_col.find_one.return_value = None
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = get_credentials("org-999", "atlassian", tenant=_TENANT)
        assert result is None

    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_handles_pymongo_error(self, mock_db):
        from pymongo.errors import PyMongoError

        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            get_credentials,
        )

        mock_col = MagicMock()
        mock_col.find_one.side_effect = PyMongoError("connection lost")
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = get_credentials("org-1", "atlassian", tenant=_TENANT)
        assert result is None


# ── upsert_credentials ──────────────────────────────────────────────


class TestUpsertCredentials:
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.encrypt_value", side_effect=lambda x: f"ENC:{x}")
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.decrypt_value", side_effect=lambda x: f"DEC:{x}")
    def test_encrypts_and_stores(self, _dec, _enc, mock_db):
        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            upsert_credentials,
        )

        mock_col = MagicMock()
        mock_col.find_one_and_update.return_value = {
            "organization_id": "org-1",
            "provider": "atlassian",
            "credentials": {"base_url": "ENC:url", "username": "ENC:user", "api_token": "ENC:tok"},
        }
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = upsert_credentials(
            "org-1", "atlassian", _SAMPLE_CREDS,
            user_id="user-1", tenant=_TENANT,
        )

        assert result is not None
        # Verify encryption was called.
        call_args = mock_col.find_one_and_update.call_args
        set_data = call_args[0][1]["$set"]
        assert set_data["credentials"]["base_url"] == "ENC:https://myco.atlassian.net"
        assert set_data["credentials"]["username"] == "ENC:admin@myco.com"

    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_handles_pymongo_error(self, mock_db):
        from pymongo.errors import PyMongoError

        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            upsert_credentials,
        )

        mock_col = MagicMock()
        mock_col.find_one_and_update.side_effect = PyMongoError("write error")
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        result = upsert_credentials(
            "org-1", "atlassian", _SAMPLE_CREDS,
            user_id="user-1", tenant=_TENANT,
        )
        assert result is None


# ── delete_credentials ───────────────────────────────────────────────


class TestDeleteCredentials:
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_returns_true_on_delete(self, mock_db):
        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            delete_credentials,
        )

        mock_col = MagicMock()
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        assert delete_credentials("org-1", "atlassian", tenant=_TENANT) is True

    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_returns_false_when_not_found(self, mock_db):
        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            delete_credentials,
        )

        mock_col = MagicMock()
        mock_col.delete_one.return_value = MagicMock(deleted_count=0)
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        assert delete_credentials("org-999", "atlassian", tenant=_TENANT) is False


# ── mark_synced ──────────────────────────────────────────────────────


class TestMarkSynced:
    @patch("crewai_productfeature_planner.mongodb.integration_credentials.repository.get_db")
    def test_marks_synced(self, mock_db):
        from crewai_productfeature_planner.mongodb.integration_credentials.repository import (
            mark_synced,
        )

        mock_col = MagicMock()
        mock_col.update_one.return_value = MagicMock(modified_count=1)
        mock_db.return_value.__getitem__ = MagicMock(return_value=mock_col)

        assert mark_synced("org-1", "atlassian", tenant=_TENANT) is True

        call_args = mock_col.update_one.call_args
        set_data = call_args[0][1]["$set"]
        assert set_data["synced_to_agent_worker"] is True
        assert "synced_at" in set_data
