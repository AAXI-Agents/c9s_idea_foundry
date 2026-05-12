"""CRUD operations for the ``integrationCredentials`` collection.

Stores per-tenant integration credentials (Atlassian, Figma, etc.)
encrypted at rest via ``field_encryption``.

Standard document schema
------------------------
::

    {
        "organization_id":         str,
        "provider":                "atlassian" | "figma" | "github" | "slack",
        "credentials": {
            "base_url":            str (encrypted),
            "username":            str (encrypted),
            "api_token":           str (encrypted),
        },
        "confluence_base_url":     str | None (encrypted),
        "jira_project_key":        str | None,
        "created_at":              str (ISO-8601),
        "updated_at":              str (ISO-8601),
        "created_by":              str (user_id),
        "synced_to_agent_worker":  bool,
        "synced_at":               str | None (ISO-8601),
        "enterprise_id":           str,
    }

Unique compound index on ``(organization_id, provider)``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
    tenant_filter,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.services.field_encryption import (
    decrypt_value,
    encrypt_value,
)

logger = get_logger(__name__)

INTEGRATION_CREDENTIALS_COLLECTION = "integrationCredentials"

# Credential sub-fields that must be encrypted at rest.
_ENCRYPTED_FIELDS = frozenset({"base_url", "username", "api_token"})

# Top-level fields that are encrypted.
_ENCRYPTED_TOP_FIELDS = frozenset({"confluence_base_url"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encrypt_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    """Encrypt sensitive credential fields before storage."""
    encrypted = {}
    for k, v in creds.items():
        if k in _ENCRYPTED_FIELDS and isinstance(v, str) and v:
            encrypted[k] = encrypt_value(v)
        else:
            encrypted[k] = v
    return encrypted


def _decrypt_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    """Decrypt credential fields after retrieval."""
    decrypted = {}
    for k, v in creds.items():
        if k in _ENCRYPTED_FIELDS and isinstance(v, str) and v:
            decrypted[k] = decrypt_value(v)
        else:
            decrypted[k] = v
    return decrypted


def get_credentials(
    organization_id: str,
    provider: str,
    *,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Return the credentials document for an org + provider, or ``None``.

    Credential fields are decrypted before returning.
    """
    try:
        doc = get_db()[INTEGRATION_CREDENTIALS_COLLECTION].find_one(
            {
                "organization_id": organization_id,
                "provider": provider,
                **tenant_filter(tenant),
            },
            {"_id": 0},
        )
        if doc and "credentials" in doc:
            doc["credentials"] = _decrypt_credentials(doc["credentials"])
            for f in _ENCRYPTED_TOP_FIELDS:
                if doc.get(f):
                    doc[f] = decrypt_value(doc[f])
        return doc
    except PyMongoError:
        logger.exception(
            "[IntegrationCreds] Failed to read creds org_id=%s provider=%s",
            organization_id, provider,
        )
        return None


def upsert_credentials(
    organization_id: str,
    provider: str,
    credentials: dict[str, Any],
    *,
    user_id: str,
    confluence_base_url: str | None = None,
    jira_project_key: str | None = None,
    synced_to_agent_worker: bool = False,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Create or update credentials for an org + provider.

    Returns the updated document (decrypted), or ``None`` on error.
    """
    now = _now_iso()
    encrypted_creds = _encrypt_credentials(credentials)

    updates: dict[str, Any] = {
        "credentials": encrypted_creds,
        "updated_at": now,
        "synced_to_agent_worker": synced_to_agent_worker,
    }
    if synced_to_agent_worker:
        updates["synced_at"] = now
    if confluence_base_url:
        updates["confluence_base_url"] = encrypt_value(confluence_base_url)
    if jira_project_key is not None:
        updates["jira_project_key"] = jira_project_key

    try:
        result = get_db()[INTEGRATION_CREDENTIALS_COLLECTION].find_one_and_update(
            {
                "organization_id": organization_id,
                "provider": provider,
                **tenant_filter(tenant),
            },
            {
                "$set": updates,
                "$setOnInsert": {
                    "organization_id": organization_id,
                    "provider": provider,
                    "created_at": now,
                    "created_by": user_id,
                    **(tenant_fields(tenant) if tenant else {}),
                },
            },
            upsert=True,
            return_document=True,
            projection={"_id": 0},
        )
        # Decrypt before returning.
        if result and "credentials" in result:
            result["credentials"] = _decrypt_credentials(result["credentials"])
            for f in _ENCRYPTED_TOP_FIELDS:
                if result.get(f):
                    result[f] = decrypt_value(result[f])
        logger.info(
            "[IntegrationCreds] Upserted creds org_id=%s provider=%s synced=%s",
            organization_id, provider, synced_to_agent_worker,
        )
        return result
    except PyMongoError:
        logger.exception(
            "[IntegrationCreds] Failed to upsert creds org_id=%s provider=%s",
            organization_id, provider,
        )
        return None


def delete_credentials(
    organization_id: str,
    provider: str,
    *,
    tenant: TenantContext | None = None,
) -> bool:
    """Delete credentials for an org + provider.

    Returns ``True`` if a document was deleted, ``False`` otherwise.
    """
    try:
        result = get_db()[INTEGRATION_CREDENTIALS_COLLECTION].delete_one(
            {
                "organization_id": organization_id,
                "provider": provider,
                **tenant_filter(tenant),
            },
        )
        deleted = result.deleted_count > 0
        logger.info(
            "[IntegrationCreds] Delete creds org_id=%s provider=%s deleted=%s",
            organization_id, provider, deleted,
        )
        return deleted
    except PyMongoError:
        logger.exception(
            "[IntegrationCreds] Failed to delete creds org_id=%s provider=%s",
            organization_id, provider,
        )
        return False


def mark_synced(
    organization_id: str,
    provider: str,
    *,
    tenant: TenantContext | None = None,
) -> bool:
    """Mark credentials as successfully synced to Agent Worker."""
    now = _now_iso()
    try:
        result = get_db()[INTEGRATION_CREDENTIALS_COLLECTION].update_one(
            {
                "organization_id": organization_id,
                "provider": provider,
                **tenant_filter(tenant),
            },
            {"$set": {"synced_to_agent_worker": True, "synced_at": now}},
        )
        return result.modified_count > 0
    except PyMongoError:
        logger.exception(
            "[IntegrationCreds] Failed to mark synced org_id=%s provider=%s",
            organization_id, provider,
        )
        return False
