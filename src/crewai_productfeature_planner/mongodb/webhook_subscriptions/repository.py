"""Repository for the ``webhookSubscriptions`` collection.

Stores webhook subscription state per-provider per-enterprise.
Supports Jira and GitHub providers with their respective configurations.

Document schema::

    {
        "enterprise_id":     str,          # tenant isolation
        "organization_id":   str,          # tenant isolation
        "provider":          str,          # "jira" | "github"
        "webhook_url":       str,          # computed inbound URL
        "event_types":       [str],        # subscribed event types
        "status":            str,          # "active" | "paused"
        "jira_projects":     [             # Jira-only: subscribed projects
            {
                "jira_project_key": str,
                "subscribed_repos": [{"repo_id": str, "repo_url": str, "project_key": str}]
            }
        ],
        "registered_repos":  [             # GitHub-only: registered repos
            {
                "project_key":         str,
                "repo_owner":          str,
                "repo_name":           str,
                "repo_url":            str,
                "github_settings_url": str,
                "github_webhook_id":   int | None,
            }
        ],
        "webhook_secret_hash": str | None, # GitHub-only: hashed secret
        "webhook_secret_masked": str | None, # GitHub-only: masked for display
        "created_at":        str,          # ISO-8601
        "updated_at":        str,          # ISO-8601
    }

Indexes:
    - unique on ``(enterprise_id, provider)``
    - ``(enterprise_id, provider, status)`` for filtered queries
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

WEBHOOK_SUBSCRIPTIONS_COLLECTION = "webhookSubscriptions"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_secret(secret: str) -> str:
    """SHA-256 hash of a webhook secret for storage."""
    return hashlib.sha256(secret.encode()).hexdigest()


def _mask_secret(secret: str) -> str:
    """Mask a secret for display: first 4 chars + asterisks."""
    if len(secret) <= 8:
        return secret[:2] + "****"
    return secret[:4] + "****" + secret[-4:]


def _generate_secret() -> str:
    """Generate a cryptographically secure webhook secret."""
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_webhook_subscription(
    enterprise_id: str,
    provider: str,
    project_key: str | None = None,
) -> dict[str, Any] | None:
    """Get a single webhook subscription.

    For Jira, optionally filters to a specific jira_project_key within the subscription.
    For GitHub, optionally filters registered_repos by project_key.
    """
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]

    try:
        doc = coll.find_one(
            {"enterprise_id": enterprise_id, "provider": provider},
            {"_id": 0},
        )
        if not doc:
            return None

        # Filter to specific project if requested
        if project_key and provider == "github":
            repos = doc.get("registered_repos", [])
            matching = [r for r in repos if r.get("project_key") == project_key]
            if not matching:
                return None
            doc["registered_repos"] = matching

        return doc
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to get subscription enterprise_id=%s provider=%s",
            enterprise_id,
            provider,
            exc_info=True,
        )
        return None


def list_webhook_subscriptions(
    enterprise_id: str,
    *,
    provider: str | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """List webhook subscriptions for an enterprise."""
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]

    query: dict[str, Any] = {"enterprise_id": enterprise_id}
    if provider and provider != "all":
        query["provider"] = provider
    if status_filter:
        query["status"] = status_filter

    try:
        return list(coll.find(query, {"_id": 0}))
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to list subscriptions enterprise_id=%s",
            enterprise_id,
            exc_info=True,
        )
        return []


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def upsert_webhook_subscription(
    enterprise_id: str,
    organization_id: str,
    provider: str,
    *,
    webhook_url: str = "",
    event_types: list[str] | None = None,
    jira_projects: list[dict[str, Any]] | None = None,
    registered_repos: list[dict[str, Any]] | None = None,
    status: str = "active",
) -> tuple[dict[str, Any], str | None]:
    """Create or update a webhook subscription.

    For GitHub, generates and returns a webhook secret on create.
    Returns (document, secret_plaintext_or_None).
    """
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]
    now = _now_iso()

    secret_plaintext: str | None = None
    set_on_insert: dict[str, Any] = {
        "enterprise_id": enterprise_id,
        "organization_id": organization_id,
        "provider": provider,
        "created_at": now,
    }

    set_fields: dict[str, Any] = {
        "updated_at": now,
        "status": status,
    }
    if webhook_url:
        set_fields["webhook_url"] = webhook_url
    if event_types is not None:
        set_fields["event_types"] = event_types
    if jira_projects is not None:
        set_fields["jira_projects"] = jira_projects
    if registered_repos is not None:
        set_fields["registered_repos"] = registered_repos

    # Generate secret for new GitHub subscriptions
    if provider == "github":
        existing = coll.find_one(
            {"enterprise_id": enterprise_id, "provider": "github"}
        )
        if not existing:
            secret_plaintext = _generate_secret()
            set_on_insert["webhook_secret_hash"] = _hash_secret(secret_plaintext)
            set_on_insert["webhook_secret_masked"] = _mask_secret(secret_plaintext)

    try:
        result = coll.find_one_and_update(
            {"enterprise_id": enterprise_id, "provider": provider},
            {"$set": set_fields, "$setOnInsert": set_on_insert},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if result:
            result.pop("_id", None)
            result.pop("webhook_secret_hash", None)
        logger.info(
            "[WebhookSubscriptions] Upserted subscription enterprise_id=%s provider=%s",
            enterprise_id,
            provider,
        )
        return result or {}, secret_plaintext
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to upsert subscription enterprise_id=%s provider=%s",
            enterprise_id,
            provider,
            exc_info=True,
        )
        raise


def add_github_repo(
    enterprise_id: str,
    organization_id: str,
    repo_entry: dict[str, Any],
    webhook_url: str = "",
) -> tuple[dict[str, Any], str | None]:
    """Add a GitHub repo to the subscription. Creates subscription if needed.

    Returns (updated_doc, secret_if_new).
    """
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]
    now = _now_iso()

    existing = coll.find_one(
        {"enterprise_id": enterprise_id, "provider": "github"},
        {"_id": 0},
    )

    secret_plaintext: str | None = None

    if not existing:
        # Create new subscription
        secret_plaintext = _generate_secret()
        doc = {
            "enterprise_id": enterprise_id,
            "organization_id": organization_id,
            "provider": "github",
            "webhook_url": webhook_url,
            "event_types": ["push", "pull_request", "issues"],
            "registered_repos": [repo_entry],
            "webhook_secret_hash": _hash_secret(secret_plaintext),
            "webhook_secret_masked": _mask_secret(secret_plaintext),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        coll.insert_one(doc)
        doc.pop("_id", None)
        doc.pop("webhook_secret_hash", None)
        return doc, secret_plaintext

    # Add repo to existing subscription
    try:
        result = coll.find_one_and_update(
            {"enterprise_id": enterprise_id, "provider": "github"},
            {
                "$push": {"registered_repos": repo_entry},
                "$set": {"updated_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )
        if result:
            result.pop("_id", None)
            result.pop("webhook_secret_hash", None)
        return result or {}, None
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to add GitHub repo enterprise_id=%s",
            enterprise_id,
            exc_info=True,
        )
        raise


def remove_github_repo(
    enterprise_id: str,
    project_key: str,
) -> dict[str, Any] | None:
    """Remove a GitHub repo from the subscription by project_key."""
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]

    try:
        result = coll.find_one_and_update(
            {"enterprise_id": enterprise_id, "provider": "github"},
            {
                "$pull": {"registered_repos": {"project_key": project_key}},
                "$set": {"updated_at": _now_iso()},
            },
            return_document=ReturnDocument.AFTER,
        )
        if result:
            result.pop("_id", None)
            result.pop("webhook_secret_hash", None)
        return result
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to remove GitHub repo enterprise_id=%s project_key=%s",
            enterprise_id,
            project_key,
            exc_info=True,
        )
        return None


def update_subscription_status(
    enterprise_id: str,
    provider: str,
    new_status: str,
    *,
    project_key: str | None = None,
) -> dict[str, Any] | None:
    """Toggle subscription status (active/paused)."""
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]

    try:
        result = coll.find_one_and_update(
            {"enterprise_id": enterprise_id, "provider": provider},
            {"$set": {"status": new_status, "updated_at": _now_iso()}},
            return_document=ReturnDocument.AFTER,
        )
        if result:
            result.pop("_id", None)
            result.pop("webhook_secret_hash", None)
        return result
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to update status enterprise_id=%s provider=%s",
            enterprise_id,
            provider,
            exc_info=True,
        )
        return None


def delete_webhook_subscription(
    enterprise_id: str,
    provider: str,
    project_key: str | None = None,
) -> bool:
    """Delete a webhook subscription (or remove a specific project_key for GitHub)."""
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]

    if provider == "github" and project_key:
        # Just remove the repo, don't delete the whole subscription
        result = remove_github_repo(enterprise_id, project_key)
        return result is not None

    try:
        result = coll.delete_one(
            {"enterprise_id": enterprise_id, "provider": provider}
        )
        return result.deleted_count > 0
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to delete subscription enterprise_id=%s provider=%s",
            enterprise_id,
            provider,
            exc_info=True,
        )
        return False


def reveal_github_secret(enterprise_id: str) -> str | None:
    """Retrieve the plaintext secret for audit. Returns None if not set.

    Note: We store a hash for verification; the actual secret is only
    returned at creation time. This reveals the masked version.
    For full reveal, we'd need to store encrypted (not just hashed).
    In practice, this returns the masked version.
    """
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]
    doc = coll.find_one(
        {"enterprise_id": enterprise_id, "provider": "github"},
        {"webhook_secret_masked": 1, "_id": 0},
    )
    if doc:
        return doc.get("webhook_secret_masked")
    return None


def regenerate_github_secret(enterprise_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Generate a new webhook secret for GitHub subscription.

    Returns (updated_doc, new_secret_plaintext).
    """
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]
    new_secret = _generate_secret()

    try:
        result = coll.find_one_and_update(
            {"enterprise_id": enterprise_id, "provider": "github"},
            {
                "$set": {
                    "webhook_secret_hash": _hash_secret(new_secret),
                    "webhook_secret_masked": _mask_secret(new_secret),
                    "updated_at": _now_iso(),
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if result:
            result.pop("_id", None)
            result.pop("webhook_secret_hash", None)
        return result, new_secret
    except PyMongoError:
        logger.error(
            "[WebhookSubscriptions] Failed to regenerate secret enterprise_id=%s",
            enterprise_id,
            exc_info=True,
        )
        return None, None


# ---------------------------------------------------------------------------
# Index setup
# ---------------------------------------------------------------------------


def ensure_indexes() -> None:
    """Create indexes for the webhookSubscriptions collection."""
    db = get_db()
    coll = db[WEBHOOK_SUBSCRIPTIONS_COLLECTION]
    coll.create_index(
        [("enterprise_id", 1), ("provider", 1)],
        unique=True,
        name="ix_enterprise_provider_unique",
    )
    coll.create_index(
        [("enterprise_id", 1), ("provider", 1), ("status", 1)],
        name="ix_enterprise_provider_status",
    )
    logger.debug("[WebhookSubscriptions] Indexes ensured")
