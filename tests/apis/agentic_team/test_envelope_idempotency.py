"""Tests for Agentic Team envelope format, idempotency, and delivery tracking."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a test client with agentic team enabled + delivery logging."""
    with patch.dict(
        "os.environ",
        {
            "AGENTIC_TEAM_ENABLED": "true",
            "AGENTIC_TEAM_WEBHOOK_SECRET": "test-secret",
            "WEBHOOK_DELIVERY_LOG_ENABLED": "true",
        },
    ):
        import importlib
        import crewai_productfeature_planner.apis.agentic_team._config as cfg

        importlib.reload(cfg)
        import crewai_productfeature_planner.apis.agentic_team._webhook as wh

        importlib.reload(wh)

        from crewai_productfeature_planner.apis import app

        yield TestClient(app)


def _sign(body_bytes: bytes, secret: str = "test-secret") -> str:
    """Generate HMAC-SHA256 signature."""
    return hmac.HMAC(secret.encode(), body_bytes, hashlib.sha256).hexdigest()


def _post_signed(client, payload: dict, extra_headers: dict | None = None):
    """Post a webhook with proper HMAC signature and optional extra headers."""
    body = json.dumps(payload, separators=(",", ":"))
    sig = _sign(body.encode())
    headers = {
        "Content-Type": "application/json",
        "x-c9s-signature": sig,
    }
    if extra_headers:
        headers.update(extra_headers)
    return client.post("/webhooks/agentic-team", content=body, headers=headers)


def _build_envelope(
    event: str,
    data: dict,
    delivery_id: str = "01HXYZ_test_delivery",
    labels: list | None = None,
) -> dict:
    """Build a spec v1.0 envelope payload."""
    return {
        "delivery_id": delivery_id,
        "event_id": f"evt_{delivery_id}",
        "event": event,
        "schema_version": "1.0",
        "timestamp": "2026-05-06T10:00:00Z",
        "source": {
            "service": "c9s_agentic_team",
            "flow_id": "flow_abc",
            "flow_run_id": "run_xyz",
        },
        "labels": labels or [],
        "data": data,
    }


# ── Envelope format detection ─────────────────────────────────


class TestEnvelopeFormat:
    """Test spec v1.0 envelope format handling."""

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_envelope_task_completed_processes_data_field(
        self, mock_has, mock_record, client,
    ):
        """Envelope format should extract event data from nested 'data' field."""
        mock_has.return_value = False
        mock_record.return_value = True

        envelope = _build_envelope(
            "task.completed",
            data={
                "issue_key": "PROJ-42",
                "project_key": "PROJ",
                "status": "done",
                "agent_role": "backend-engineer",
                "duration_s": 60.0,
                "labels": ["idea:abc123", "feature:feat-1"],
            },
            labels=["idea:abc123", "feature:feat-1"],
        )

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._webhook.get_idea"
        ) as mock_idea:
            mock_idea.return_value = {
                "idea_id": "abc123",
                "features": [{"id": "feat-1", "name": "Auth", "completion_pct": 0}],
            }
            with patch(
                "crewai_productfeature_planner.apis.agentic_team._webhook.update_features"
            ), patch(
                "crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion"
            ):
                resp = _post_signed(client, envelope)

        assert resp.status_code == 200

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_envelope_epic_completed(self, mock_has, mock_record, client):
        """Envelope format for epic.completed should work."""
        mock_has.return_value = False
        mock_record.return_value = True

        envelope = _build_envelope(
            "epic.completed",
            data={
                "issue_key": "PROJ-10",
                "project_key": "PROJ",
                "total_tasks": 5,
                "completed_tasks": 5,
                "epic_completion_pct": 100.0,
            },
            labels=["idea:idea-x", "feature:feat-x"],
        )

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._webhook.get_idea"
        ) as mock_idea:
            mock_idea.return_value = {
                "idea_id": "idea-x",
                "features": [{"id": "feat-x", "name": "Dashboard", "completion_pct": 50}],
            }
            with patch(
                "crewai_productfeature_planner.apis.agentic_team._webhook.update_features"
            ), patch(
                "crewai_productfeature_planner.apis.agentic_team._webhook.update_overall_completion"
            ):
                resp = _post_signed(client, envelope)

        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        assert resp.json()["event"] == "epic.completed"

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_unsupported_schema_version_rejected(self, mock_has, mock_record, client):
        """Envelopes with unsupported schema_version should be ignored."""
        mock_has.return_value = False

        envelope = _build_envelope("task.completed", data={"issue_key": "X-1"})
        envelope["schema_version"] = "99.0"

        resp = _post_signed(client, envelope)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert "schema" in resp.json()["reason"].lower()

    def test_legacy_flat_format_still_works(self, client):
        """Legacy flat payload (no data/source/delivery_id) should still work."""
        payload = {
            "event": "task.failed",
            "issue_key": "X-5",
            "project_key": "X",
            "error": "Build failed",
            "labels": [],
        }
        resp = _post_signed(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"


# ── Idempotency ───────────────────────────────────────────────


class TestIdempotency:
    """Test delivery_id deduplication."""

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_duplicate_delivery_returns_200(self, mock_has, mock_record, client):
        """Already-processed delivery_id should return 200 with 'duplicate' status."""
        mock_has.return_value = True  # Already seen

        envelope = _build_envelope(
            "task.completed",
            data={"issue_key": "X-1", "project_key": "X", "labels": []},
            delivery_id="dup-001",
        )
        resp = _post_signed(client, envelope)
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"
        assert resp.json()["delivery_id"] == "dup-001"
        # Should NOT call record_delivery for duplicates
        mock_record.assert_not_called()

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_new_delivery_is_processed(self, mock_has, mock_record, client):
        """New delivery_id should be processed and recorded."""
        mock_has.return_value = False
        mock_record.return_value = True

        envelope = _build_envelope(
            "task.failed",
            data={
                "issue_key": "X-2",
                "project_key": "X",
                "error": "Test error",
                "labels": [],
            },
            delivery_id="new-001",
        )
        resp = _post_signed(client, envelope)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        mock_record.assert_called_once()

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_idempotency_key_header_legacy(self, mock_has, mock_record, client):
        """Legacy flat payload with Idempotency-Key header should deduplicate."""
        mock_has.return_value = True

        payload = {
            "event": "task.failed",
            "issue_key": "X-9",
            "project_key": "X",
            "error": "Oops",
            "labels": [],
        }
        resp = _post_signed(
            client, payload, extra_headers={"Idempotency-Key": "legacy-dup-001"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"


# ── Delivery recording ────────────────────────────────────────


class TestDeliveryRecording:
    """Test that deliveries are persisted correctly."""

    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.record_delivery")
    @patch("crewai_productfeature_planner.apis.agentic_team._webhook.has_delivery")
    def test_record_delivery_called_with_correct_fields(
        self, mock_has, mock_record, client,
    ):
        """Verify record_delivery receives the correct arguments."""
        mock_has.return_value = False
        mock_record.return_value = True

        envelope = _build_envelope(
            "task.completed",
            data={
                "issue_key": "PROJ-55",
                "project_key": "PROJ",
                "status": "done",
                "agent_role": "qa",
                "duration_s": 30,
            },
            delivery_id="rec-001",
            labels=["idea:idea-rec", "feature:feat-rec"],
        )

        # No idea linkage → will be "ignored" status, but still recorded
        resp = _post_signed(client, envelope)
        assert resp.status_code == 200

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["delivery_id"] == "rec-001"
        assert call_kwargs["event"] == "task.completed"
        assert call_kwargs["source_service"] == "c9s_agentic_team"
        assert call_kwargs["schema_version"] == "1.0"
        assert call_kwargs["event_id"] == "evt_rec-001"
        assert call_kwargs["idea_id"] == "idea-rec"
        assert call_kwargs["feature_id"] == "feat-rec"
        assert call_kwargs["issue_key"] == "PROJ-55"


# ── Envelope unwrapping ───────────────────────────────────────


class TestEnvelopeUnwrapping:
    """Test _is_envelope_format and _unwrap_envelope directly."""

    def test_is_envelope_format_true(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _is_envelope_format,
        )

        envelope = {
            "delivery_id": "x",
            "source": {"service": "test"},
            "data": {},
            "event": "task.completed",
        }
        assert _is_envelope_format(envelope) is True

    def test_is_envelope_format_false_for_flat(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _is_envelope_format,
        )

        flat = {"event": "task.completed", "issue_key": "X-1"}
        assert _is_envelope_format(flat) is False

    def test_unwrap_envelope_extracts_meta_and_data(self):
        from crewai_productfeature_planner.apis.agentic_team._webhook import (
            _unwrap_envelope,
        )

        envelope = {
            "delivery_id": "del-1",
            "event_id": "evt-1",
            "event": "task.completed",
            "schema_version": "1.0",
            "timestamp": "2026-01-01T00:00:00Z",
            "source": {"service": "c9s_agentic_team", "flow_id": "f1"},
            "labels": ["idea:test"],
            "data": {"issue_key": "PROJ-1", "status": "done"},
        }
        data, meta = _unwrap_envelope(envelope)
        assert data["issue_key"] == "PROJ-1"
        assert data["labels"] == ["idea:test"]
        assert meta["delivery_id"] == "del-1"
        assert meta["event_id"] == "evt-1"
        assert meta["source"]["service"] == "c9s_agentic_team"
