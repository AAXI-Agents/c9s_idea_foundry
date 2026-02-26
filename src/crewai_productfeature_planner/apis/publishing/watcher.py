"""File-system watcher — auto-trigger publishing when new PRD files appear.

Uses a polling-based approach (no external dependencies like ``watchdog``)
to detect new ``.md`` files in ``output/prds/``.  When a file is fully
written (size stabilises over two consecutive polls), the watcher
triggers Confluence publishing and MongoDB delivery record creation.

Start / stop via :func:`start_watcher` and :func:`stop_watcher`.

Environment variables:

* ``PUBLISH_WATCHER_ENABLED`` — set to ``"0"`` or ``"false"`` to disable
  (default: enabled when Confluence credentials are configured).
* ``PUBLISH_WATCHER_POLL_SECONDS`` — polling interval (default: ``10``).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────

_watcher_thread: threading.Thread | None = None
_stop_event = threading.Event()
_watched_dir: str = ""

# Files we've already processed (absolute paths).
_processed_files: set[str] = set()

# Tracks file sizes between polls for stabilisation detection.
_pending_sizes: dict[str, int] = {}

# Default polling interval.
_DEFAULT_POLL_SECONDS = 10


# ── Public helpers ────────────────────────────────────────────────────


def get_prds_directory() -> Path:
    """Return the absolute ``output/prds`` directory path."""
    return Path(__file__).resolve().parents[3] / "output" / "prds"


def get_watcher_status() -> dict:
    """Return a dict describing the current watcher state."""
    return {
        "running": _watcher_thread is not None and _watcher_thread.is_alive(),
        "directory": _watched_dir,
    }


# ── Start / stop ─────────────────────────────────────────────────────


def start_watcher() -> bool:
    """Start the file-watcher background thread.

    Returns ``True`` if the watcher was started, ``False`` if it was
    already running or is disabled by configuration.
    """
    global _watcher_thread, _watched_dir  # noqa: PLW0603

    if _watcher_thread is not None and _watcher_thread.is_alive():
        logger.debug("[FileWatcher] Already running")
        return False

    # Check env-var override
    enabled_env = os.environ.get("PUBLISH_WATCHER_ENABLED", "").strip().lower()
    if enabled_env in ("0", "false", "no"):
        logger.info("[FileWatcher] Disabled via PUBLISH_WATCHER_ENABLED")
        return False

    # Ensure we have Confluence credentials (no point watching otherwise)
    try:
        from crewai_productfeature_planner.tools.confluence_tool import (
            _has_confluence_credentials,
        )
        if not _has_confluence_credentials():
            logger.info("[FileWatcher] No Confluence credentials — watcher not started")
            return False
    except Exception:  # noqa: BLE001
        pass

    prds_dir = get_prds_directory()
    prds_dir.mkdir(parents=True, exist_ok=True)
    _watched_dir = str(prds_dir)

    # Seed processed set with existing files so we don't re-publish
    _seed_existing_files(prds_dir)

    _stop_event.clear()
    _watcher_thread = threading.Thread(
        target=_poll_loop,
        name="prd-file-watcher",
        daemon=True,
    )
    _watcher_thread.start()
    logger.info("[FileWatcher] Started — watching %s", prds_dir)
    return True


def stop_watcher() -> None:
    """Signal the watcher thread to stop."""
    global _watcher_thread  # noqa: PLW0603
    _stop_event.set()
    if _watcher_thread is not None:
        _watcher_thread.join(timeout=15)
        _watcher_thread = None
    logger.info("[FileWatcher] Stopped")


# ── Internal ──────────────────────────────────────────────────────────


def _seed_existing_files(prds_dir: Path) -> None:
    """Mark all current ``.md`` files as already processed."""
    for md in prds_dir.rglob("*.md"):
        _processed_files.add(str(md.resolve()))


def _poll_loop() -> None:
    """Polling loop — runs in a daemon thread."""
    poll_seconds = _get_poll_seconds()
    prds_dir = get_prds_directory()

    logger.debug("[FileWatcher] Poll loop started (interval=%ds)", poll_seconds)

    while not _stop_event.is_set():
        try:
            _scan_for_new_files(prds_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[FileWatcher] Scan error: %s", exc)

        _stop_event.wait(timeout=poll_seconds)


def _scan_for_new_files(prds_dir: Path) -> None:
    """One scan pass — detect new, stabilised ``.md`` files."""
    for md_file in prds_dir.rglob("*.md"):
        abs_path = str(md_file.resolve())

        if abs_path in _processed_files:
            continue

        # Check file size stability (file fully written)
        try:
            current_size = md_file.stat().st_size
        except OSError:
            continue

        if current_size == 0:
            continue

        prev_size = _pending_sizes.get(abs_path)
        if prev_size is None or prev_size != current_size:
            # First sighting or still changing — record and re-check next poll
            _pending_sizes[abs_path] = current_size
            logger.debug(
                "[FileWatcher] New/changing file detected: %s (%d bytes)",
                abs_path, current_size,
            )
            continue

        # Size stabilised — process the file
        del _pending_sizes[abs_path]
        _processed_files.add(abs_path)

        logger.info("[FileWatcher] File stabilised — triggering publish: %s", abs_path)
        _trigger_publish(md_file)


def _trigger_publish(md_file: Path) -> None:
    """Publish a newly detected markdown file to Confluence.

    Runs in the watcher thread.  Errors are logged but never propagated
    so the watcher keeps running.
    """
    try:
        content = md_file.read_text(encoding="utf-8")
        if not content.strip():
            logger.debug("[FileWatcher] Empty file, skipping: %s", md_file)
            return

        title = f"PRD — {md_file.stem}"

        from crewai_productfeature_planner.tools.confluence_tool import (
            publish_to_confluence,
        )

        result = publish_to_confluence(
            title=title,
            markdown_content=content,
            run_id="",
        )

        logger.info(
            "[FileWatcher] Published '%s' → %s (%s)",
            title, result.get("url", ""), result.get("action", ""),
        )

        # Also create a delivery record so the scheduler can pick up
        # Jira ticketing later if needed.
        try:
            from crewai_productfeature_planner.mongodb.product_requirements import (
                upsert_delivery_record,
            )
            # Use the filename as a pseudo run_id for disk-only files
            pseudo_id = f"disk_{md_file.stem}"
            upsert_delivery_record(
                pseudo_id,
                confluence_published=True,
                confluence_url=result.get("url", ""),
                confluence_page_id=result.get("page_id", ""),
            )
        except Exception:  # noqa: BLE001
            pass  # best-effort

    except Exception as exc:  # noqa: BLE001
        logger.warning("[FileWatcher] Publish failed for %s: %s", md_file, exc)


def _get_poll_seconds() -> int:
    """Read ``PUBLISH_WATCHER_POLL_SECONDS`` from environment."""
    try:
        return max(1, int(os.environ.get("PUBLISH_WATCHER_POLL_SECONDS", _DEFAULT_POLL_SECONDS)))
    except (ValueError, TypeError):
        return _DEFAULT_POLL_SECONDS
