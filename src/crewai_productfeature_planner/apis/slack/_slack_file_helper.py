"""Helpers for Slack content that may exceed the 3000-char block limit.

When content is too long for a single Slack section block, these helpers
truncate the preview for inline display and upload the full content as
a downloadable text file in the thread.
"""

from __future__ import annotations

import time

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

#: Maximum chars in a Slack section block text field (3000).
#: We use 2800 to leave room for surrounding markdown.
SLACK_BLOCK_TEXT_LIMIT = 2800

#: Retry parameters for transient Slack file-upload failures.
_UPLOAD_MAX_RETRIES = 2
_UPLOAD_RETRY_DELAY = 1.0


def truncate_with_file_hint(content: str, limit: int = SLACK_BLOCK_TEXT_LIMIT) -> tuple[str, bool]:
    """Truncate content and add a file-download hint if it exceeds *limit*.

    Returns ``(preview, was_truncated)``.  When *was_truncated* is True,
    the caller should also call :func:`upload_content_file` to attach the
    full text.
    """
    if len(content) <= limit:
        return content, False

    preview = (
        content[:limit]
        + f"\n\n_… ({len(content) - limit} more chars — see attached file for full content)_"
    )
    return preview, True


def upload_content_file(
    channel: str,
    thread_ts: str | None,
    content: str,
    filename: str,
    title: str,
) -> bool:
    """Upload *content* as a text file snippet in the Slack thread.

    Retries up to ``_UPLOAD_MAX_RETRIES`` times on transient failures
    (rate-limits, network hiccups) before giving up.

    Returns True on success, False on failure (logged, never raises).
    """
    try:
        from crewai_productfeature_planner.tools.slack_tools import (
            _get_slack_client,
        )

        client = _get_slack_client()
        if not client:
            logger.warning("No Slack client — skipping file upload for %s", filename)
            return False

        upload_kwargs: dict = {
            "channel": channel,
            "content": content,
            "filename": filename,
            "title": title,
            "initial_comment": (
                ":page_facing_up: Full content attached — the inline "
                "preview above was truncated due to Slack's message limit."
            ),
        }
        if thread_ts:
            upload_kwargs["thread_ts"] = thread_ts

        last_exc: Exception | None = None
        for attempt in range(_UPLOAD_MAX_RETRIES + 1):
            try:
                client.files_upload_v2(**upload_kwargs)
                logger.info(
                    "[Slack] Content file uploaded channel=%s file=%s (%d chars)",
                    channel, filename, len(content),
                )
                return True
            except Exception as exc:
                last_exc = exc
                if attempt < _UPLOAD_MAX_RETRIES:
                    logger.debug(
                        "[Slack] File upload attempt %d failed for %s — retrying: %s",
                        attempt + 1, filename, exc,
                    )
                    time.sleep(_UPLOAD_RETRY_DELAY * (attempt + 1))

        logger.error(
            "Content file upload failed after %d attempts channel=%s file=%s",
            _UPLOAD_MAX_RETRIES + 1, channel, filename, exc_info=last_exc,
        )
        return False
    except Exception:
        logger.error(
            "Content file upload failed channel=%s file=%s",
            channel, filename, exc_info=True,
        )
        return False
