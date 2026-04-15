"""Pluggable output storage backend.

Writes output files (PRDs, UX designs) to local disk by default, and
optionally to a Google Cloud Storage bucket when ``GCS_OUTPUT_BUCKET``
is set.  This allows the application to run statelessly on Cloud Run
while still producing the same file paths for consumers.

Environment variables:

* ``GCS_OUTPUT_BUCKET`` — GCS bucket name (e.g. ``my-project-prds``).
  When set, all writes go to GCS **and** local disk (local acts as
  a cache).  When unset, writes go to local disk only (default).
* ``GCS_OUTPUT_PREFIX`` — optional prefix/folder inside the bucket
  (default: ``"output"``).

Usage::

    from crewai_productfeature_planner.tools.output_storage import write_output

    local_path = write_output(
        relative_path="prds/2026/04/prd_v1.md",
        content="# My PRD ...",
    )
"""

from __future__ import annotations

import os
from pathlib import Path

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Base directory for local output files (project root / output).
_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"


def _gcs_bucket_name() -> str:
    """Return the GCS bucket name from env, or empty string if unset."""
    return os.environ.get("GCS_OUTPUT_BUCKET", "").strip()


def _gcs_prefix() -> str:
    """Return the GCS object key prefix."""
    return os.environ.get("GCS_OUTPUT_PREFIX", "output").strip().strip("/")


def write_output(relative_path: str, content: str) -> str:
    """Write content to the output storage backend.

    Args:
        relative_path: Path relative to ``output/``, e.g.
            ``prds/2026/04/prd_v1.md``.
        content: UTF-8 text content to write.

    Returns:
        The absolute local file path (even when GCS is used, a local
        copy is kept as a cache).
    """
    # Always write locally (acts as cache when GCS is enabled)
    local_path = _OUTPUT_ROOT / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(content, encoding="utf-8")

    bucket = _gcs_bucket_name()
    if bucket:
        _write_to_gcs(bucket, relative_path, content)

    return str(local_path)


def read_output(relative_path: str) -> str | None:
    """Read content from the output storage backend.

    Tries local disk first, then GCS if configured.  Returns ``None``
    if the file doesn't exist in either location.
    """
    local_path = _OUTPUT_ROOT / relative_path
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    bucket = _gcs_bucket_name()
    if bucket:
        return _read_from_gcs(bucket, relative_path)

    return None


def exists_output(relative_path: str) -> bool:
    """Check if an output file exists (local or GCS)."""
    local_path = _OUTPUT_ROOT / relative_path
    if local_path.exists():
        return True

    bucket = _gcs_bucket_name()
    if bucket:
        return _exists_in_gcs(bucket, relative_path)

    return False


# ── GCS helpers ───────────────────────────────────────────────────────


def _write_to_gcs(bucket_name: str, relative_path: str, content: str) -> None:
    """Upload content to GCS."""
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        prefix = _gcs_prefix()
        blob_name = f"{prefix}/{relative_path}" if prefix else relative_path
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type="text/markdown")
        logger.info(
            "[OutputStorage] Uploaded to gs://%s/%s (%d bytes)",
            bucket_name, blob_name, len(content),
        )
    except ImportError:
        logger.warning(
            "[OutputStorage] google-cloud-storage not installed — "
            "GCS_OUTPUT_BUCKET is set but GCS writes are disabled. "
            "Install with: pip install google-cloud-storage"
        )
    except Exception as exc:
        logger.error(
            "[OutputStorage] Failed to upload to GCS: %s",
            exc, exc_info=True,
        )


def _read_from_gcs(bucket_name: str, relative_path: str) -> str | None:
    """Download content from GCS."""
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        prefix = _gcs_prefix()
        blob_name = f"{prefix}/{relative_path}" if prefix else relative_path
        blob = bucket.blob(blob_name)
        if not blob.exists():
            return None
        content = blob.download_as_text(encoding="utf-8")
        logger.debug(
            "[OutputStorage] Downloaded from gs://%s/%s",
            bucket_name, blob_name,
        )
        return content
    except ImportError:
        return None
    except Exception as exc:
        logger.warning(
            "[OutputStorage] Failed to read from GCS: %s", exc,
        )
        return None


def _exists_in_gcs(bucket_name: str, relative_path: str) -> bool:
    """Check if a blob exists in GCS."""
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        prefix = _gcs_prefix()
        blob_name = f"{prefix}/{relative_path}" if prefix else relative_path
        return bucket.blob(blob_name).exists()
    except ImportError:
        return False
    except Exception:
        return False
