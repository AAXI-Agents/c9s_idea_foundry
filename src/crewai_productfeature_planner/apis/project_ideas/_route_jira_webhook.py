"""Jira webhook handler for feature completion tracking.

POST /webhooks/jira — Receives Jira issue status change events,
maps them to idea features, recalculates completion percentages.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Request, status

from crewai_productfeature_planner.mongodb.ideas.repository import (
    get_idea,
    update_features,
    update_overall_completion,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Jira webhook secret for HMAC validation
_JIRA_WEBHOOK_SECRET = os.environ.get("JIRA_WEBHOOK_SECRET", "")

# Status categories for completion calculation
_DONE_STATUSES = frozenset({"done", "closed", "resolved", "complete"})
_IN_PROGRESS_STATUSES = frozenset({"in progress", "in review", "testing"})


def _verify_jira_signature(payload: bytes, signature: str | None) -> bool:
    """Verify Jira webhook HMAC-SHA256 signature."""
    if not _JIRA_WEBHOOK_SECRET:
        # No secret configured — skip verification (dev mode)
        return True
    if not signature:
        return False
    expected = hmac.HMAC(
        _JIRA_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post(
    "/jira",
    status_code=status.HTTP_200_OK,
    summary="Jira webhook receiver",
    description=(
        "Receives Jira issue status change webhooks. Maps Jira labels "
        "to idea features and recalculates completion percentages."
    ),
)
async def handle_jira_webhook(
    request: Request,
    x_hub_signature: str | None = Header(default=None, alias="x-hub-signature"),
):
    """Process Jira webhook event."""
    body = await request.body()

    # Verify webhook signature
    if not _verify_jira_signature(body, x_hub_signature):
        logger.warning("[JiraWebhook] Invalid signature — rejecting")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload: dict[str, Any] = await request.json()
    event_type = payload.get("webhookEvent", "")

    # Only process issue status changes
    if event_type not in ("jira:issue_updated", "jira:issue_created"):
        return {"status": "ignored", "reason": f"Unhandled event: {event_type}"}

    issue = payload.get("issue", {})
    fields = issue.get("fields", {})
    issue_key = issue.get("key", "")
    issue_status = (fields.get("status", {}).get("name", "")).lower()

    # Find linked idea via labels (format: "idea:<idea_id>")
    labels = [
        lbl if isinstance(lbl, str) else lbl.get("name", "")
        for lbl in fields.get("labels", [])
    ]
    idea_id = _extract_idea_id_from_labels(labels)
    if not idea_id:
        # Check epic link
        idea_id = _extract_idea_id_from_epic(fields)

    if not idea_id:
        return {"status": "ignored", "reason": "No idea label found"}

    # Find the feature linked to this issue (via epic key or label)
    feature_id = _extract_feature_id_from_labels(labels)
    if not feature_id:
        return {"status": "ignored", "reason": "No feature label found"}

    logger.info(
        "[JiraWebhook] Processing %s: issue=%s status=%s idea=%s feature=%s",
        event_type, issue_key, issue_status, idea_id, feature_id,
    )

    # Get the idea and update feature completion
    idea = get_idea(idea_id=idea_id)
    if not idea:
        logger.warning("[JiraWebhook] Idea not found: %s", idea_id)
        return {"status": "ignored", "reason": "Idea not found"}

    # Recalculate feature completion from all linked issues
    features = idea.get("features", [])
    updated = False
    for feature in features:
        if feature.get("id") == feature_id:
            # Get all issues for this feature from Jira
            completion = _calculate_issue_completion(
                issue_key, issue_status, feature,
            )
            feature["completion_pct"] = completion
            updated = True
            break

    if updated:
        update_features(idea_id=idea_id, features=features)
        # Recalculate overall completion
        overall = _calculate_overall_completion(features)
        update_overall_completion(idea_id=idea_id, overall_completion=overall)

        logger.info(
            "[JiraWebhook] Updated idea=%s feature=%s completion=%.1f%% overall=%.1f%%",
            idea_id, feature_id, features[0]["completion_pct"] if features else 0, overall,
        )

    return {
        "status": "processed",
        "idea_id": idea_id,
        "feature_id": feature_id,
        "issue_key": issue_key,
    }


# ── Helpers ───────────────────────────────────────────────────


def _extract_idea_id_from_labels(labels: list[str]) -> str | None:
    """Extract idea_id from labels like 'idea:abc123'."""
    for label in labels:
        if label.startswith("idea:"):
            return label[5:]
    return None


def _extract_feature_id_from_labels(labels: list[str]) -> str | None:
    """Extract feature_id from labels like 'feature:f1'."""
    for label in labels:
        if label.startswith("feature:"):
            return label[8:]
    return None


def _extract_idea_id_from_epic(fields: dict) -> str | None:
    """Extract idea_id from epic custom field or parent."""
    # Check parent (for sub-tasks under an epic)
    parent = fields.get("parent", {})
    parent_labels = parent.get("fields", {}).get("labels", [])
    if parent_labels:
        return _extract_idea_id_from_labels(
            [lbl if isinstance(lbl, str) else lbl.get("name", "")
             for lbl in parent_labels]
        )
    return None


def _calculate_issue_completion(
    issue_key: str, issue_status: str, feature: dict,
) -> float:
    """Calculate feature completion based on issue status.

    For now, uses a simple heuristic: track issues in the feature's
    `jira_issues` list and calculate percentage of done issues.
    """
    issues = feature.get("jira_issues", [])

    # Update or add this issue's status
    found = False
    for issue_entry in issues:
        if issue_entry.get("key") == issue_key:
            issue_entry["status"] = issue_status
            found = True
            break
    if not found:
        issues.append({"key": issue_key, "status": issue_status})
        feature["jira_issues"] = issues

    if not issues:
        return 0.0

    done_count = sum(
        1 for i in issues if i.get("status", "").lower() in _DONE_STATUSES
    )
    return round((done_count / len(issues)) * 100.0, 1)


def _calculate_overall_completion(features: list[dict]) -> float:
    """Calculate overall idea completion from feature completions."""
    if not features:
        return 0.0
    total = sum(f.get("completion_pct", 0.0) for f in features)
    return round(total / len(features), 1)
