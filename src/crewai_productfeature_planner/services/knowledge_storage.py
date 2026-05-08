"""GCS storage service for knowledge documents.

Handles upload and deletion of knowledge files in Google Cloud Storage.
Bucket naming: ``{SERVER_ENV}-idea-foundry`` (derived from ``SERVER_ENV``).
Object key pattern:
    ``{enterprise_id}/{organization_id}/projects/{project_id}/knowledge/{doc_id}/{filename}``
"""

from __future__ import annotations

import os
from typing import BinaryIO

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.services.gcs_paths import (
    build_knowledge_key,
    get_bucket_name,
    get_gcs_client,
)

logger = get_logger(__name__)


def build_object_key(
    enterprise_id: str,
    organization_id: str,
    project_id: str,
    doc_id: str,
    filename: str,
) -> str:
    """Build the GCS object key for a knowledge document."""
    return build_knowledge_key(
        enterprise_id, organization_id, project_id, doc_id, filename,
    )


def upload_file(
    *,
    enterprise_id: str,
    organization_id: str,
    project_id: str,
    doc_id: str,
    filename: str,
    file_obj: BinaryIO,
    content_type: str | None = None,
) -> str:
    """Upload a file to GCS.

    Args:
        enterprise_id: Enterprise ID for tenant scoping.
        organization_id: Organization ID for tenant scoping.
        project_id: Project ID for path scoping.
        doc_id: Document ID for path scoping.
        filename: Original filename.
        file_obj: File-like object to upload.
        content_type: MIME type for the blob.

    Returns:
        The GCS object key (path).

    Raises:
        Exception: On upload failure.
    """
    object_key = build_object_key(
        enterprise_id, organization_id, project_id, doc_id, filename,
    )
    bucket_name = get_bucket_name()

    logger.info(
        "[GCS] Uploading file=%s bucket=%s key=%s",
        filename,
        bucket_name,
        object_key,
    )

    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_key)
    blob.upload_from_file(file_obj, content_type=content_type)

    logger.info("[GCS] Upload complete key=%s", object_key)
    return object_key


def delete_file(*, gcs_path: str) -> bool:
    """Delete a file from GCS.

    Args:
        gcs_path: The GCS object key to delete.

    Returns:
        True if deleted, False if not found or error.
    """
    bucket_name = get_bucket_name()
    logger.info("[GCS] Deleting key=%s bucket=%s", gcs_path, bucket_name)

    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)
        blob.delete()
        logger.info("[GCS] Deleted key=%s", gcs_path)
        return True
    except Exception as exc:
        logger.error("[GCS] Failed to delete key=%s: %s", gcs_path, exc, exc_info=True)
        return False


def download_as_text(*, gcs_path: str) -> str | None:
    """Download a GCS object and return its text content.

    Returns None on failure.
    """
    bucket_name = get_bucket_name()
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)
        return blob.download_as_text()
    except Exception as exc:
        logger.error(
            "[GCS] Failed to download key=%s: %s", gcs_path, exc, exc_info=True
        )
        return None


def download_as_bytes(*, gcs_path: str) -> bytes | None:
    """Download a GCS object and return its raw bytes.

    Returns None on failure.
    """
    bucket_name = get_bucket_name()
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)
        return blob.download_as_bytes()
    except Exception as exc:
        logger.error(
            "[GCS] Failed to download bytes key=%s: %s", gcs_path, exc, exc_info=True
        )
        return None
