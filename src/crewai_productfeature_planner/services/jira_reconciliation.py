"""Jira reconciliation background task.

Periodically polls Jira for status changes on linked issues and
recalculates feature completion percentages. Acts as a safety net
for missed webhooks.

Triggered on server startup with a configurable interval (default 10 min).
Feature-flagged via FEATURE_JIRA_RECONCILIATION=true.
"""

from __future__ import annotations

import asyncio
import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Default reconciliation interval: 10 minutes
_DEFAULT_INTERVAL_SECONDS = 600

# Done statuses (must match _route_jira_webhook.py)
_DONE_STATUSES = frozenset({"done", "closed", "resolved", "complete"})


def is_enabled() -> bool:
    """Check if Jira reconciliation is enabled via feature flag."""
    return os.environ.get("FEATURE_JIRA_RECONCILIATION", "").lower() in (
        "true", "1", "yes",
    )


def _get_interval() -> int:
    """Get the reconciliation interval in seconds."""
    try:
        return int(os.environ.get(
            "JIRA_RECONCILIATION_INTERVAL_SECONDS",
            str(_DEFAULT_INTERVAL_SECONDS),
        ))
    except ValueError:
        return _DEFAULT_INTERVAL_SECONDS


async def reconciliation_loop() -> None:
    """Run the Jira reconciliation loop.

    Queries all ideas with active Jira features and recalculates
    completion from Jira API responses.
    """
    interval = _get_interval()
    logger.info(
        "[JiraReconciliation] Starting background loop (interval=%ds)",
        interval,
    )

    while True:
        try:
            await asyncio.sleep(interval)
            await _reconcile_all()
        except asyncio.CancelledError:
            logger.info("[JiraReconciliation] Loop cancelled — stopping")
            break
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[JiraReconciliation] Reconciliation failed: %s",
                exc,
                exc_info=True,
            )
            # Wait a bit before retrying on error
            await asyncio.sleep(min(interval, 60))


async def _reconcile_all() -> None:
    """Reconcile all ideas that have Jira-linked features."""
    from crewai_productfeature_planner.mongodb.ideas.repository import (
        _col as ideas_col,
        update_features,
        update_overall_completion,
    )

    try:
        # Find ideas with features that have jira_issues
        cursor = ideas_col().find(
            {
                "features": {"$elemMatch": {"jira_issues": {"$exists": True, "$ne": []}}},
                "status": {"$nin": ["archived", "completed"]},
            },
            {"_id": 0, "idea_id": 1, "features": 1},
        )

        ideas = list(cursor)
        if not ideas:
            logger.debug("[JiraReconciliation] No ideas with Jira-linked features")
            return

        logger.info(
            "[JiraReconciliation] Reconciling %d idea(s) with Jira features",
            len(ideas),
        )

        jira_client = _get_jira_client()
        if not jira_client:
            logger.debug("[JiraReconciliation] No Jira credentials — skipping")
            return

        reconciled_count = 0
        for idea in ideas:
            idea_id = idea.get("idea_id", "")
            features = idea.get("features", [])
            if not idea_id or not features:
                continue

            updated = await _reconcile_idea_features(
                jira_client, idea_id, features
            )
            if updated:
                reconciled_count += 1

        if reconciled_count:
            logger.info(
                "[JiraReconciliation] Reconciled %d idea(s)", reconciled_count
            )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[JiraReconciliation] Query failed: %s", exc, exc_info=True
        )


async def _reconcile_idea_features(
    jira_client: dict,
    idea_id: str,
    features: list[dict],
) -> bool:
    """Reconcile feature completion for a single idea.

    Returns True if any feature was updated.
    """
    from crewai_productfeature_planner.mongodb.ideas.repository import (
        update_features,
        update_overall_completion,
    )

    any_updated = False

    for feature in features:
        jira_issues = feature.get("jira_issues", [])
        if not jira_issues:
            continue

        # Fetch current status for each issue from Jira
        issue_keys = [i.get("key") for i in jira_issues if i.get("key")]
        if not issue_keys:
            continue

        statuses = await _fetch_issue_statuses(jira_client, issue_keys)
        if not statuses:
            continue

        # Update local issue statuses
        changed = False
        for issue_entry in jira_issues:
            key = issue_entry.get("key", "")
            if key in statuses:
                new_status = statuses[key]
                if issue_entry.get("status") != new_status:
                    issue_entry["status"] = new_status
                    changed = True

        if changed:
            # Recalculate completion
            done_count = sum(
                1 for i in jira_issues
                if i.get("status", "").lower() in _DONE_STATUSES
            )
            feature["completion_pct"] = round(
                (done_count / len(jira_issues)) * 100.0, 1
            )
            any_updated = True

    if any_updated:
        update_features(idea_id=idea_id, features=features)
        overall = _calculate_overall_completion(features)
        update_overall_completion(idea_id=idea_id, overall_completion=overall)
        logger.info(
            "[JiraReconciliation] Updated idea=%s overall=%.1f%%",
            idea_id,
            overall,
        )

    return any_updated


async def _fetch_issue_statuses(
    jira_client: dict,
    issue_keys: list[str],
) -> dict[str, str]:
    """Fetch current statuses for multiple Jira issues.

    Uses the Jira REST API with JQL search.

    Returns:
        Dict mapping issue_key → current status name.
    """
    import httpx

    base_url = jira_client["base_url"]
    auth = jira_client["auth"]

    # Batch query using JQL
    jql = f"key in ({','.join(issue_keys)})"
    url = f"{base_url}/rest/api/3/search"
    params = {
        "jql": jql,
        "fields": "status",
        "maxResults": len(issue_keys),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url, params=params, auth=auth,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[JiraReconciliation] Jira API %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return {}

            data = resp.json()
            result = {}
            for issue in data.get("issues", []):
                key = issue.get("key", "")
                status_name = (
                    issue.get("fields", {})
                    .get("status", {})
                    .get("name", "")
                    .lower()
                )
                if key and status_name:
                    result[key] = status_name
            return result

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[JiraReconciliation] Failed to fetch statuses: %s", exc
        )
        return {}


def _get_jira_client() -> dict | None:
    """Build Jira API client config from env vars.

    Returns:
        Dict with base_url and auth tuple, or None if not configured.
    """
    base_url = os.environ.get("JIRA_BASE_URL", "")
    email = os.environ.get("JIRA_USER_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")

    if not all([base_url, email, token]):
        return None

    return {
        "base_url": base_url.rstrip("/"),
        "auth": (email, token),
    }


def _calculate_overall_completion(features: list[dict]) -> float:
    """Calculate overall idea completion from feature completions."""
    if not features:
        return 0.0
    total = sum(f.get("completion_pct", 0.0) for f in features)
    return round(total / len(features), 1)
