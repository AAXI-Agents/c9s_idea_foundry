"""Tests for POST /webhooks/agentic-team — inbound webhook receiver."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a test client with agentic team enabled."""
    with patch.dict(
        "os.environ",
        {"AGENTIC_TEAM_ENABLED": "true", "AGENTIC_TEAM_WEBHOOK_SECRET": "test-secret"},
    ):
        # Reload config module to pick up new env vars
        import importlib
        import crewai_productfeature_planner.apis.agentic_team._config as cfg
        importlib.reload(cfg)
        import crewai_productfeature_planner.apis.agentic_team._webhook as wh
        importlib.reload(wh)

        from crewai_productfeature_planner.apis import app
        yield TestClient(app)


@pytest.fixture()
def disabled_client():
    """Create a test client with agentic team disabled."""
    with patch.dict(
        "os.environ",
        {"AGENTIC_TEAM_ENABLED": "false", "AGENTIC_TEAM_WEBHOOK_SECRET": ""},
    ):
        import importlib
        import crewai_productfeature_planner.apis.agentic_team._config as cfg
        importlib.reload(cfg)
        import crewai_productfeature_planner.apis.agentic_team._webhook as wh
        importlib.reload(wh)

        from crewai_productfeature_planner.apis import app
        yield TestClient(app)


def _sign(payload: dict, secret: str = "test-secret") -> str:
    """Generate HMAC-SHA256 signature for a payload."""
    body = json.dumps(payload, separators=(",", ":")).encode()
    return hmac.HMAC(secret.encode(), body, hashlib.sha256).hexdigest()


def _post_webhook(client, payload: dict, secret: str = "test-secret"):
    """Post a webhook with proper signature."""
    body = json.dumps(payload, separators=(",", ":"))
    sig = hmac.HMAC(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/agentic-team",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-c9s-signature": sig,
        },
    )


# ── Signature verification ────────────────────────────────────


class TestSignatureVerification:
    """Test HMAC-SHA256 webhook signature validation."""

    def test_valid_signature_accepted(self, client):
        payload = {"event": "task.completed", "issue_key": "X-1", "labels": []}
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self, client):
        payload = {"event": "task.completed", "issue_key": "X-1"}
        body = json.dumps(payload)
        resp = client.post(
            "/webhooks/agentic-team",
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-c9s-signature": "invalid-sig",
            },
        )
        assert resp.status_code == 401

    def test_missing_signature_rejected(self, client):
        payload = {"event": "task.completed", "issue_key": "X-1"}
        resp = client.post(
            "/webhooks/agentic-team",
            json=payload,
        )
        assert resp.status_code == 401


# ── Feature flag (disabled) ───────────────────────────────────


class TestDisabledIntegration:
    """Test behaviour when AGENTIC_TEAM_ENABLED=false."""

    def test_returns_ignored_when_disabled(self, disabled_client):
        payload = {"event": "task.completed", "issue_key": "X-1"}
        resp = disabled_client.post("/webhooks/agentic-team", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert "disabled" in resp.json()["reason"].lower()


# ── Event routing ─────────────────────────────────────────────


class TestEventRouting:
    """Test event type dispatch logic."""

    def test_unknown_event_ignored(self, client):
        payload = {"event": "unknown.event", "issue_key": "X-1"}
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_task_completed_no_linkage_ignored(self, client):
        payload = {
            "event": "task.completed",
            "issue_key": "X-1",
            "project_key": "X",
            "labels": [],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_features")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion")
    def test_task_completed_updates_feature(
        self, mock_overall, mock_features, mock_get_idea, client,
    ):
        mock_get_idea.return_value = {
            "idea_id": "idea-1",
            "features": [
                {"id": "feat-1", "name": "Login", "completion_pct": 0.0},
                {"id": "feat-2", "name": "Signup", "completion_pct": 100.0},
            ],
        }

        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "status": "done",
            "agent_role": "senior-backend-engineer",
            "duration_s": 120,
            "parent_epic_key": "X-1",
            "epic_completion_pct": 75.0,
            "labels": ["idea:idea-1", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert data["idea_id"] == "idea-1"
        assert data["feature_id"] == "feat-1"
        assert data["completion_pct"] == 75.0

        # Verify feature was updated
        mock_features.assert_called_once()
        features_arg = mock_features.call_args[1]["features"]
        assert features_arg[0]["completion_pct"] == 75.0

        # Verify overall recalculated
        mock_overall.assert_called_once()

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    def test_task_completed_idea_not_found(self, mock_get_idea, client):
        mock_get_idea.return_value = None

        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "epic_completion_pct": 50.0,
            "labels": ["idea:nonexistent", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_task_failed_no_linkage(self, client):
        payload = {
            "event": "task.failed",
            "issue_key": "X-5",
            "project_key": "X",
            "error": "Dependency missing",
            "labels": [],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        assert resp.json()["event"] == "task.failed"

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_features")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion")
    def test_epic_completed_marks_feature_100(
        self, mock_overall, mock_features, mock_get_idea, client,
    ):
        mock_get_idea.return_value = {
            "idea_id": "idea-2",
            "features": [
                {"id": "feat-a", "name": "Auth", "completion_pct": 50.0},
            ],
        }

        payload = {
            "event": "epic.completed",
            "issue_key": "X-100",
            "project_key": "X",
            "status": "done",
            "total_tasks": 8,
            "completed_tasks": 8,
            "epic_completion_pct": 100.0,
            "labels": ["idea:idea-2", "feature:feat-a"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert data["event"] == "epic.completed"

        # Feature should be set to 100%
        mock_features.assert_called_once()
        features_arg = mock_features.call_args[1]["features"]
        assert features_arg[0]["completion_pct"] == 100.0

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    def test_epic_completed_no_linkage_ignored(self, mock_get_idea, client):
        payload = {
            "event": "epic.completed",
            "issue_key": "X-100",
            "project_key": "X",
            "labels": [],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


# ── Helper functions ──────────────────────────────────────────


class TestHelpers:
    """Test label extraction helpers."""

    def test_extract_idea_id(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _extract_idea_id_from_labels,
        )
        assert _extract_idea_id_from_labels(["idea:abc123"]) == "abc123"
        assert _extract_idea_id_from_labels(["feature:f1", "idea:xyz"]) == "xyz"
        assert _extract_idea_id_from_labels(["other"]) is None
        assert _extract_idea_id_from_labels([]) is None

    def test_extract_feature_id(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _extract_feature_id_from_labels,
        )
        assert _extract_feature_id_from_labels(["feature:feat-1"]) == "feat-1"
        assert _extract_feature_id_from_labels(["idea:x", "feature:f2"]) == "f2"
        assert _extract_feature_id_from_labels(["nope"]) is None

    def test_recalculate_overall(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _recalculate_overall,
        )
        # All done
        assert _recalculate_overall([
            {"completion_pct": 100.0},
            {"completion_pct": 100.0},
        ]) == 100.0

        # None done
        assert _recalculate_overall([
            {"completion_pct": 50.0},
            {"completion_pct": 0.0},
        ]) == 0.0

        # Half done
        assert _recalculate_overall([
            {"completion_pct": 100.0},
            {"completion_pct": 50.0},
        ]) == 50.0

        # Empty
        assert _recalculate_overall([]) == 0.0

    def test_resolve_tenant_from_idea(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _resolve_tenant_from_idea,
        )
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._webhook.get_idea",
            return_value={
                "idea_id": "idea-1",
                "organization_id": "org-a",
                "enterprise_id": "ent-b",
            },
        ):
            org, ent = _resolve_tenant_from_idea("idea-1")
            assert org == "org-a"
            assert ent == "ent-b"

    def test_resolve_tenant_from_idea_none(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _resolve_tenant_from_idea,
        )
        org, ent = _resolve_tenant_from_idea(None)
        assert org is None
        assert ent is None


# ── Non-terminal status filtering ─────────────────────────────


class TestNonTerminalStatusFiltering:
    """Test that non-terminal pipeline statuses (dev_done) are ignored."""

    def test_dev_done_ignored(self, client):
        """task.completed with pipeline_status=dev_done should be ignored."""
        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "pipeline_status": "dev_done",
            "epic_completion_pct": 50.0,
            "labels": ["idea:idea-1", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert "non-terminal" in data["reason"].lower() or "dev_done" in data["reason"].lower()

    def test_in_progress_ignored(self, client):
        """task.completed with pipeline_status=in_progress should be ignored."""
        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "pipeline_status": "in_progress",
            "labels": ["idea:idea-1", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_features")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion")
    def test_done_status_processed(
        self, mock_overall, mock_features, mock_get_idea, client,
    ):
        """task.completed with pipeline_status=done should be processed."""
        mock_get_idea.return_value = {
            "idea_id": "idea-1",
            "features": [{"id": "feat-1", "name": "F1", "completion_pct": 0.0}],
        }
        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "pipeline_status": "done",
            "epic_completion_pct": 80.0,
            "labels": ["idea:idea-1", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_features")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion")
    def test_donedone_status_processed(
        self, mock_overall, mock_features, mock_get_idea, client,
    ):
        """task.completed with pipeline_status=donedone should be processed."""
        mock_get_idea.return_value = {
            "idea_id": "idea-1",
            "features": [{"id": "feat-1", "name": "F1", "completion_pct": 0.0}],
        }
        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "pipeline_status": "donedone",
            "epic_completion_pct": 100.0,
            "labels": ["idea:idea-1", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.get_idea")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_features")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion")
    def test_no_pipeline_status_defaults_to_done(
        self, mock_overall, mock_features, mock_get_idea, client,
    ):
        """task.completed without pipeline_status should default to done (processed)."""
        mock_get_idea.return_value = {
            "idea_id": "idea-1",
            "features": [{"id": "feat-1", "name": "F1", "completion_pct": 0.0}],
        }
        payload = {
            "event": "task.completed",
            "issue_key": "X-10",
            "project_key": "X",
            "epic_completion_pct": 60.0,
            "labels": ["idea:idea-1", "feature:feat-1"],
        }
        resp = _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
