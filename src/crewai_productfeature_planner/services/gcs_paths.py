"""Unified GCS bucket and path resolution for all storage backends.

Bucket naming convention:

    {SERVER_ENV}-idea-foundry

where ``SERVER_ENV`` (``DEV``, ``UAT``, ``PROD``) is lowercased.  There
is **one bucket per environment** — no separate env vars are needed.

Multi-tenant object key layout::

    {enterprise_id}/{organization_id}/projects/{project_id}/knowledge/{doc_id}/{filename}
    {enterprise_id}/{organization_id}/projects/{project_id}/ideas/{idea_id}/{filename}
"""

from __future__ import annotations

import os

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


# ── Bucket name ──────────────────────────────────────────────────────


def get_bucket_name() -> str:
    """Derive the GCS bucket name from ``SERVER_ENV``.

    Returns e.g. ``"dev-idea-foundry"`` when ``SERVER_ENV=DEV``.
    """
    env = os.environ.get("SERVER_ENV", "DEV").strip().lower()
    return f"{env}-idea-foundry"


# ── GCS client ───────────────────────────────────────────────────────


def get_gcs_client():
    """Return a ``google.cloud.storage.Client`` using ADC.

    Falls back to ``GCP_SERVICE_ACCOUNT_JSON`` if set, then to
    ``GOOGLE_APPLICATION_CREDENTIALS`` (standard ADC).

    Raises ``ImportError`` if ``google-cloud-storage`` is not installed.
    """
    from google.cloud import storage  # type: ignore[import-untyped]

    creds_path = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if creds_path:
        return storage.Client.from_service_account_json(creds_path)
    return storage.Client()


# ── Path builders ────────────────────────────────────────────────────


def build_knowledge_key(
    enterprise_id: str,
    organization_id: str,
    project_id: str,
    doc_id: str,
    filename: str,
) -> str:
    """Build a GCS object key for a knowledge document.

    Returns:
        ``"{enterprise_id}/{organization_id}/projects/{project_id}/knowledge/{doc_id}/{filename}"``
    """
    return (
        f"{enterprise_id}/{organization_id}/projects/{project_id}"
        f"/knowledge/{doc_id}/{filename}"
    )


def build_idea_key(
    enterprise_id: str,
    organization_id: str,
    project_id: str,
    idea_id: str,
    filename: str,
) -> str:
    """Build a GCS object key for an idea artifact (PRD, UX design).

    Returns:
        ``"{enterprise_id}/{organization_id}/projects/{project_id}/ideas/{idea_id}/{filename}"``
    """
    return (
        f"{enterprise_id}/{organization_id}/projects/{project_id}"
        f"/ideas/{idea_id}/{filename}"
    )


def build_idea_prefix(
    enterprise_id: str,
    organization_id: str,
    project_id: str,
    idea_id: str,
) -> str:
    """Build the GCS key prefix for all artifacts of an idea.

    Callers append a filename to produce the full object key.

    Returns:
        ``"{enterprise_id}/{organization_id}/projects/{project_id}/ideas/{idea_id}/"``
    """
    return (
        f"{enterprise_id}/{organization_id}/projects/{project_id}"
        f"/ideas/{idea_id}/"
    )
