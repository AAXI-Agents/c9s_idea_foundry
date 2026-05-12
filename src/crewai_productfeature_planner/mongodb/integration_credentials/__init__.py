"""Repository for the ``integrationCredentials`` collection.

Stores per-tenant integration credentials (Atlassian, Figma, etc.)
encrypted at rest.  Each org has at most one document per provider,
enforced by a unique compound index on ``(organization_id, provider)``.
"""

from .repository import (
    INTEGRATION_CREDENTIALS_COLLECTION,
    delete_credentials,
    get_credentials,
    mark_synced,
    upsert_credentials,
)

__all__ = [
    "INTEGRATION_CREDENTIALS_COLLECTION",
    "delete_credentials",
    "get_credentials",
    "mark_synced",
    "upsert_credentials",
]
