"""Inbound webhook receiver for Agentic Team task completion events.

POST /webhooks/agentic-team — Receives task/epic status change events
from the Agentic Team platform, maps them to idea features, and
recalculates completion percentages.

Supports both:
  - **Envelope format** (spec v1.0): nested ``data`` field with event payload
  - **Flat format** (legacy): event fields at top level

Idempotency: Uses ``delivery_id`` from envelope or ``Idempotency-Key``
header to deduplicate. Already-processed deliveries return 200 immediately.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Request, status

from crewai_productfeature_planner.apis.agentic_team._config import (
    AGENTIC_TEAM_ENABLED,
    AGENTIC_TEAM_WEBHOOK_SECRET,
    SUPPORTED_SCHEMA_VERSIONS,
    WEBHOOK_DELIVERY_LOG_ENABLED,
)
from crewai_productfeature_planner.mongodb.ideas.repository import (
    get_idea,
    update_features,
    update_overall_completion,
)
from crewai_productfeature_planner.mongodb.webhook_deliveries import (
    has_delivery,
    record_delivery,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Valid event types we process
_VALID_EVENTS = frozenset({"task.completed", "task.failed", "epic.completed"})

# Jira status categories considered "done"
_DONE_STATUSES = frozenset({"done", "donedone", "closed", "resolved", "complete"})


def _verify_signature(payload: bytes, signature: str | None) -> bool:
    """Verify HMAC-SHA256 signature from x-c9s-signature header."""
    if not AGENTIC_TEAM_WEBHOOK_SECRET:
        # No secret configured — skip verification (dev mode only)
        return True
    if not signature:
        return False
    expected = hmac.HMAC(
        AGENTIC_TEAM_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_idea_id_from_labels(labels: list[str]) -> str | None:
    """Extract idea_id from labels like 'idea:abc123'."""
    for label in labels:
        if isinstance(label, str) and label.startswith("idea:"):
            return label[5:]
    return None


def _extract_feature_id_from_labels(labels: list[str]) -> str | None:
    """Extract feature_id from labels like 'feature:feat-001'."""
    for label in labels:
        if isinstance(label, str) and label.startswith("feature:"):
            return label[8:]
    return None


def _resolve_tenant_from_idea(idea_id: str | None) -> tuple[str | None, str | None]:
    """Look up organization_id and enterprise_id from the linked idea.

    Returns (organization_id, enterprise_id) or (None, None) if not resolvable.
    """
    if not idea_id:
        return None, None
    try:
        idea = get_idea(idea_id=idea_id)
        if idea:
            return idea.get("organization_id"), idea.get("enterprise_id")
    except Exception:  # noqa: BLE001
        pass
    return None, None


def _recalculate_overall(features: list[dict[str, Any]]) -> float:
    """Calculate weighted overall completion from features."""
    if not features:
        return 0.0
    total = len(features)
    done = sum(
        1 for f in features if f.get("completion_pct", 0) >= 100.0
    )
    return round((done / total) * 100, 1)


def _is_envelope_format(payload: dict[str, Any]) -> bool:
    """Detect if the payload uses the spec envelope format (has data + source)."""
    return "data" in payload and "source" in payload and "delivery_id" in payload


def _unwrap_envelope(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract event data and metadata from an envelope-format payload.

    Returns (event_data, envelope_meta).
    """
    meta = {
        "delivery_id": payload.get("delivery_id"),
        "event_id": payload.get("event_id"),
        "schema_version": payload.get("schema_version", "1.0"),
        "timestamp": payload.get("timestamp"),
        "source": payload.get("source", {}),
        "labels": payload.get("labels", []),
    }
    data = payload.get("data", {})
    # Inject labels into data for unified processing
    if "labels" not in data:
        data["labels"] = meta["labels"]
    return data, meta


@router.post(
    "/agentic-team",
    status_code=status.HTTP_200_OK,
    summary="Agentic Team webhook receiver",
    description=(
        "Receives task/epic completion events from the Agentic Team "
        "platform. Maps Jira labels to idea features and recalculates "
        "completion percentages. Verified via HMAC-SHA256. "
        "Supports idempotent delivery via delivery_id deduplication."
    ),
    tags=["Webhooks"],
)
async def handle_agentic_team_webhook(
    request: Request,
    x_c9s_signature: str | None = Header(default=None, alias="x-c9s-signature"),
    idempotency_key: str | None = Header(default=None, alias="idempotency-key"),
) -> dict[str, Any]:
    """Process Agentic Team webhook event."""
    if not AGENTIC_TEAM_ENABLED:
        return {"status": "ignored", "reason": "Integration disabled"}

    body = await request.body()

    # Verify webhook signature
    if not _verify_signature(body, x_c9s_signature):
        logger.warning("[AgenticTeam] Invalid webhook signature — rejecting")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload: dict[str, Any] = await request.json()

    # ── Detect format: envelope (spec v1.0) vs flat (legacy) ──
    envelope_meta: dict[str, Any] | None = None
    if _is_envelope_format(payload):
        event_data, envelope_meta = _unwrap_envelope(payload)
        event_type = payload.get("event", "")
        delivery_id = envelope_meta["delivery_id"]

        # Validate schema version
        schema_ver = envelope_meta.get("schema_version", "1.0")
        if schema_ver not in SUPPORTED_SCHEMA_VERSIONS:
            logger.warning(
                "[AgenticTeam] Unsupported schema_version=%s delivery_id=%s",
                schema_ver, delivery_id,
            )
            return {"status": "ignored", "reason": f"Unsupported schema: {schema_ver}"}
    else:
        # Legacy flat format
        event_data = payload
        event_type = payload.get("event", "")
        delivery_id = idempotency_key  # may be None

    if event_type not in _VALID_EVENTS:
        return {"status": "ignored", "reason": f"Unhandled event: {event_type}"}

    # ── Idempotency check ─────────────────────────────────────
    if delivery_id and WEBHOOK_DELIVERY_LOG_ENABLED:
        if has_delivery(delivery_id):
            logger.info(
                "[AgenticTeam] Duplicate delivery_id=%s — returning 200",
                delivery_id,
            )
            return {"status": "duplicate", "delivery_id": delivery_id}

    # Extract event-level fields from the (unwrapped) data
    issue_key = event_data.get("issue_key", "")
    project_key = event_data.get("project_key", "")
    labels = event_data.get("labels", [])
    # Also check envelope-level labels if present
    if not labels and envelope_meta:
        labels = envelope_meta.get("labels", [])

    logger.info(
        "[AgenticTeam] Webhook received: event=%s issue=%s project=%s delivery_id=%s",
        event_type, issue_key, project_key, delivery_id,
    )

    # Inject labels into event_data for handler access
    event_data["labels"] = labels

    # Route by event type
    if event_type == "task.completed":
        result = _handle_task_completed(event_data)
    elif event_type == "task.failed":
        result = _handle_task_failed(event_data)
    elif event_type == "epic.completed":
        result = _handle_epic_completed(event_data)
    else:
        result = {"status": "ignored"}

    # ── Persist delivery for audit + idempotency ──────────────
    if delivery_id and WEBHOOK_DELIVERY_LOG_ENABLED:
        idea_id = _extract_idea_id_from_labels(labels)
        feature_id = _extract_feature_id_from_labels(labels)

        # Extract tenant context from the linked idea for audit scoping
        org_id, ent_id = _resolve_tenant_from_idea(idea_id)

        record_delivery(
            delivery_id=delivery_id,
            event=event_type,
            source_service=envelope_meta["source"].get("service", "c9s_agentic_team") if envelope_meta else "c9s_agentic_team",
            schema_version=envelope_meta.get("schema_version", "1.0") if envelope_meta else "1.0",
            event_id=envelope_meta.get("event_id") if envelope_meta else None,
            status=result.get("status", "processed"),
            idea_id=idea_id,
            feature_id=feature_id,
            issue_key=issue_key,
            payload=payload,
            result=result,
            organization_id=org_id,
            enterprise_id=ent_id,
        )

    return result


def _handle_task_completed(payload: dict[str, Any]) -> dict[str, Any]:
    """Process task.completed — update feature/idea completion.

    Only updates completion when the task reached a terminal status
    (done/donedone). Intermediate statuses like dev_done are ignored
    to prevent premature 100% reporting.
    """
    issue_key = payload.get("issue_key", "")
    epic_key = payload.get("parent_epic_key")
    epic_pct = payload.get("epic_completion_pct")
    agent_role = payload.get("agent_role", "unknown")
    pipeline_status = payload.get("pipeline_status", "done")

    # Only process final terminal statuses — skip intermediate states
    terminal_statuses = {"done", "donedone", "closed", "resolved", "complete"}
    if pipeline_status and pipeline_status.lower() not in terminal_statuses:
        logger.debug(
            "[AgenticTeam] Skipping task.completed with non-terminal status=%s "
            "for %s",
            pipeline_status, issue_key,
        )
        return {
            "status": "ignored",
            "reason": f"Non-terminal status: {pipeline_status}",
        }

    # Try to find linked idea via labels in the payload
    # The Agentic Team may pass labels directly, or we search by epic
    labels = payload.get("labels", [])
    idea_id = _extract_idea_id_from_labels(labels)
    feature_id = _extract_feature_id_from_labels(labels)

    if not idea_id and not epic_key:
        logger.debug(
            "[AgenticTeam] No idea/epic linkage for %s — ignoring", issue_key,
        )
        return {"status": "ignored", "reason": "No idea linkage"}

    # If we have epic_completion_pct from the payload, use it
    # to update the matching feature
    if idea_id and feature_id and epic_pct is not None:
        idea = get_idea(idea_id=idea_id)
        if not idea:
            logger.warning("[AgenticTeam] Idea not found: %s", idea_id)
            return {"status": "ignored", "reason": "Idea not found"}

        features = idea.get("features", [])
        updated = False
        for feature in features:
            if feature.get("id") == feature_id:
                feature["completion_pct"] = min(epic_pct, 100.0)
                updated = True
                break

        if updated:
            update_features(idea_id=idea_id, features=features)
            overall = _recalculate_overall(features)
            update_overall_completion(
                idea_id=idea_id, overall_completion=overall,
            )

            # Push WebSocket update to connected clients
            _broadcast_completion_update(idea_id, feature_id, epic_pct, overall)

            logger.info(
                "[AgenticTeam] Updated idea=%s feature=%s "
                "completion=%.1f%% overall=%.1f%% agent=%s",
                idea_id, feature_id, epic_pct, overall, agent_role,
            )
            return {
                "status": "processed",
                "idea_id": idea_id,
                "feature_id": feature_id,
                "completion_pct": epic_pct,
                "overall": overall,
            }

    logger.debug(
        "[AgenticTeam] task.completed for %s — no actionable linkage",
        issue_key,
    )
    return {"status": "ignored", "reason": "No actionable feature linkage"}


def _handle_task_failed(payload: dict[str, Any]) -> dict[str, Any]:
    """Process task.failed — log and optionally broadcast."""
    issue_key = payload.get("issue_key", "")
    error = payload.get("error", "")
    labels = payload.get("labels", [])
    idea_id = _extract_idea_id_from_labels(labels)

    logger.warning(
        "[AgenticTeam] Task failed: issue=%s error=%s idea=%s",
        issue_key, error, idea_id,
    )

    if idea_id:
        _broadcast_task_failed(idea_id, issue_key, error)

    return {"status": "processed", "issue_key": issue_key, "event": "task.failed"}


def _handle_epic_completed(payload: dict[str, Any]) -> dict[str, Any]:
    """Process epic.completed — mark linked feature as 100%."""
    issue_key = payload.get("issue_key", "")
    labels = payload.get("labels", [])
    idea_id = _extract_idea_id_from_labels(labels)
    feature_id = _extract_feature_id_from_labels(labels)

    if not idea_id or not feature_id:
        return {"status": "ignored", "reason": "No idea/feature linkage"}

    idea = get_idea(idea_id=idea_id)
    if not idea:
        logger.warning("[AgenticTeam] Idea not found for epic: %s", idea_id)
        return {"status": "ignored", "reason": "Idea not found"}

    features = idea.get("features", [])
    updated = False
    for feature in features:
        if feature.get("id") == feature_id:
            feature["completion_pct"] = 100.0
            updated = True
            break

    if updated:
        update_features(idea_id=idea_id, features=features)
        overall = _recalculate_overall(features)
        update_overall_completion(idea_id=idea_id, overall_completion=overall)
        _broadcast_completion_update(idea_id, feature_id, 100.0, overall)

        logger.info(
            "[AgenticTeam] Epic completed: idea=%s feature=%s overall=%.1f%%",
            idea_id, feature_id, overall,
        )

    return {
        "status": "processed",
        "idea_id": idea_id,
        "feature_id": feature_id,
        "event": "epic.completed",
    }


# ── WebSocket broadcast helpers ───────────────────────────────


def _broadcast_completion_update(
    idea_id: str,
    feature_id: str,
    feature_pct: float,
    overall: float,
) -> None:
    """Push feature completion update via WebSocket."""
    try:
        from crewai_productfeature_planner.apis.project_ideas import (
            broadcast_idea_sync,
        )
        broadcast_idea_sync(idea_id, {
            "event": "feature_update",
            "data": {
                "idea_id": idea_id,
                "feature_id": feature_id,
                "completion_pct": feature_pct,
                "overall_completion": overall,
            },
        })
    except Exception:  # noqa: BLE001
        pass


def _broadcast_task_failed(idea_id: str, issue_key: str, error: str) -> None:
    """Push task failure notification via WebSocket."""
    try:
        from crewai_productfeature_planner.apis.project_ideas import (
            broadcast_idea_sync,
        )
        broadcast_idea_sync(idea_id, {
            "event": "task_failed",
            "data": {
                "idea_id": idea_id,
                "issue_key": issue_key,
                "error": error,
            },
        })
    except Exception:  # noqa: BLE001
        pass
