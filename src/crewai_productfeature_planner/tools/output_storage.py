"""Pluggable output storage backend.

Writes output files (PRDs, UX designs) to local disk by default, and
mirrors them to Google Cloud Storage using the unified bucket derived
from ``SERVER_ENV`` (e.g. ``dev-idea-foundry``).

GCS object keys follow the multi-tenant layout defined in
``services.gcs_paths``.  Callers pass a pre-built ``gcs_key`` so that
enterprise / organisation / project / idea scoping is handled upstream.

Usage::

    from crewai_productfeature_planner.tools.output_storage import write_output

    local_path = write_output(
        relative_path="prds/2026/04/prd_v1.md",
        content="# My PRD ...",
        gcs_key="ent123/org456/projects/proj789/ideas/idea1/prd_v1.md",
    )
"""

from __future__ import annotations

import os
from pathlib import Path

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Base directory for local output files (project root / output).
_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"


def write_output(
    relative_path: str,
    content: str,
    *,
    gcs_key: str = "",
) -> str:
    """Write content to the output storage backend.

    Args:
        relative_path: Path relative to ``output/``, e.g.
            ``prds/2026/04/prd_v1.md``.
        content: UTF-8 text content to write.
        gcs_key: Pre-built GCS object key.  When provided, the content
            is uploaded to the environment bucket (best-effort).

    Returns:
        The absolute local file path (even when GCS is used, a local
        copy is kept as a cache).
    """
    # Always write locally (acts as cache when GCS is enabled)
    local_path = _OUTPUT_ROOT / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(content, encoding="utf-8")

    if gcs_key:
        _write_to_gcs(gcs_key, content)

    return str(local_path)


def read_output(relative_path: str, *, gcs_key: str = "") -> str | None:
    """Read content from the output storage backend.

    Tries local disk first, then GCS if *gcs_key* is provided.
    Returns ``None`` if the file doesn't exist in either location.
    """
    local_path = _OUTPUT_ROOT / relative_path
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    if gcs_key:
        return _read_from_gcs(gcs_key)

    return None


def exists_output(relative_path: str, *, gcs_key: str = "") -> bool:
    """Check if an output file exists (local or GCS)."""
    local_path = _OUTPUT_ROOT / relative_path
    if local_path.exists():
        return True

    if gcs_key:
        return _exists_in_gcs(gcs_key)

    return False


# ── GCS helpers ───────────────────────────────────────────────────────


def _write_to_gcs(gcs_key: str, content: str) -> None:
    """Upload content to the environment GCS bucket."""
    try:
        from crewai_productfeature_planner.services.gcs_paths import (
            get_bucket_name,
            get_gcs_client,
        )

        bucket_name = get_bucket_name()
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_key)
        blob.upload_from_string(content, content_type="text/markdown")
        logger.info(
            "[OutputStorage] Uploaded to gs://%s/%s (%d bytes)",
            bucket_name, gcs_key, len(content),
        )
    except ImportError:
        logger.warning(
            "[OutputStorage] google-cloud-storage not installed — "
            "GCS writes are disabled. "
            "Install with: pip install google-cloud-storage"
        )
    except Exception as exc:
        logger.error(
            "[OutputStorage] Failed to upload to GCS: %s",
            exc, exc_info=True,
        )


def _read_from_gcs(gcs_key: str) -> str | None:
    """Download content from the environment GCS bucket."""
    try:
        from crewai_productfeature_planner.services.gcs_paths import (
            get_bucket_name,
            get_gcs_client,
        )

        bucket_name = get_bucket_name()
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_key)
        if not blob.exists():
            return None
        content = blob.download_as_text(encoding="utf-8")
        logger.debug(
            "[OutputStorage] Downloaded from gs://%s/%s",
            bucket_name, gcs_key,
        )
        return content
    except ImportError:
        return None
    except Exception as exc:
        logger.warning(
            "[OutputStorage] Failed to read from GCS: %s", exc,
        )
        return None


def _exists_in_gcs(gcs_key: str) -> bool:
    """Check if a blob exists in the environment GCS bucket."""
    try:
        from crewai_productfeature_planner.services.gcs_paths import (
            get_bucket_name,
            get_gcs_client,
        )

        bucket_name = get_bucket_name()
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        return bucket.blob(gcs_key).exists()
    except ImportError:
        return False
    except Exception:
        return False
