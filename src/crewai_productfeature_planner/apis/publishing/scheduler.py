"""Periodic cron scheduler — scans for incomplete deliveries and resumes them.

Runs a background thread that periodically calls the discovery functions
and processes any PRDs whose Confluence publishing or Jira ticketing
was interrupted (e.g. by a server restart or transient failure).

This provides resilience: even if the file watcher misses a file or a
publish operation fails mid-way, the scheduler will pick it up on the
next sweep.

Environment variables:

* ``PUBLISH_SCAN_INTERVAL_SECONDS`` — sweep interval (default: ``300``
  = 5 minutes).
* ``PUBLISH_SCHEDULER_ENABLED`` — set to ``"0"`` or ``"false"`` to
  disable (default: enabled when credentials are configured).
"""

from __future__ import annotations

import os
import threading

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Module-level state ────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()

_DEFAULT_INTERVAL_SECONDS = 300  # 5 minutes


# ── Public helpers ────────────────────────────────────────────────────


def get_scheduler_status() -> dict:
    """Return a dict describing the current scheduler state."""
    return {
        "running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "interval_seconds": _get_interval_seconds(),
    }


# ── Start / stop ─────────────────────────────────────────────────────


def start_scheduler() -> bool:
    """Start the periodic scan scheduler in a background thread.

    Returns ``True`` if the scheduler was started, ``False`` if already
    running or disabled by configuration.
    """
    global _scheduler_thread  # noqa: PLW0603

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.debug("[PublishScheduler] Already running")
        return False

    # Check env-var override
    enabled_env = os.environ.get("PUBLISH_SCHEDULER_ENABLED", "").strip().lower()
    if enabled_env in ("0", "false", "no"):
        logger.info("[PublishScheduler] Disabled via PUBLISH_SCHEDULER_ENABLED")
        return False

    # Need at least one set of credentials
    try:
        from crewai_productfeature_planner.tools.confluence_tool import (
            _has_confluence_credentials,
        )
        if not _has_confluence_credentials():
            logger.info(
                "[PublishScheduler] No Confluence credentials — scheduler not started"
            )
            return False
    except Exception:  # noqa: BLE001
        pass

    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        name="publish-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()

    interval = _get_interval_seconds()
    logger.info(
        "[PublishScheduler] Started — scanning every %d seconds", interval,
    )
    return True


def stop_scheduler() -> None:
    """Signal the scheduler thread to stop."""
    global _scheduler_thread  # noqa: PLW0603
    _stop_event.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=15)
        _scheduler_thread = None
    logger.info("[PublishScheduler] Stopped")


# ── Internal ──────────────────────────────────────────────────────────


def _scheduler_loop() -> None:
    """Main loop — runs in a daemon thread."""
    interval = _get_interval_seconds()
    logger.debug("[PublishScheduler] Loop started (interval=%ds)", interval)

    # Wait one full interval before the first scan so the startup
    # pipeline and file watcher have time to process anything obvious.
    _stop_event.wait(timeout=interval)

    while not _stop_event.is_set():
        try:
            _run_scan()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[PublishScheduler] Scan error: %s", exc)

        _stop_event.wait(timeout=interval)


def _run_scan() -> None:
    """One scan sweep — discover and process pending deliveries."""
    logger.debug("[PublishScheduler] Starting scan sweep")

    published = _publish_pending_confluence()
    ticketed = _create_pending_jira()

    if published or ticketed:
        logger.info(
            "[PublishScheduler] Sweep complete — "
            "published=%d, jira_created=%d",
            published, ticketed,
        )
    else:
        logger.debug("[PublishScheduler] Sweep complete — nothing pending")


def _publish_pending_confluence() -> int:
    """Publish any PRDs that are still missing from Confluence."""
    try:
        from crewai_productfeature_planner.tools.confluence_tool import (
            _has_confluence_credentials,
            publish_to_confluence,
        )

        if not _has_confluence_credentials():
            return 0

        from crewai_productfeature_planner.orchestrator._startup_review import (
            _discover_publishable_prds,
        )

        items = _discover_publishable_prds()
        if not items:
            return 0

        published = 0
        for item in items:
            if _stop_event.is_set():
                break
            try:
                result = publish_to_confluence(
                    title=item["title"],
                    markdown_content=item["content"],
                    run_id=item.get("run_id", ""),
                )

                # Persist delivery record in productRequirements
                if item.get("run_id"):
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        upsert_delivery_record,
                    )
                    upsert_delivery_record(
                        run_id=item["run_id"],
                        confluence_published=True,
                        confluence_url=result["url"],
                        confluence_page_id=result["page_id"],
                    )

                published += 1
                logger.info(
                    "[PublishScheduler] Published '%s' → %s",
                    item["title"], result.get("url", ""),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[PublishScheduler] Failed to publish '%s': %s",
                    item["title"], exc,
                )

        return published
    except Exception as exc:  # noqa: BLE001
        logger.warning("[PublishScheduler] Confluence scan error: %s", exc)
        return 0


def _create_pending_jira() -> int:
    """Create Jira tickets for deliveries where Confluence is done but Jira is not."""
    try:
        from crewai_productfeature_planner.orchestrator._helpers import (
            _has_jira_credentials,
        )

        if not _has_jira_credentials():
            return 0

        from crewai_productfeature_planner.orchestrator._startup_delivery import (
            _discover_pending_deliveries,
        )

        items = _discover_pending_deliveries()
        jira_pending = [
            i for i in items
            if i.get("confluence_done") and not i.get("jira_done")
        ]

        if not jira_pending:
            return 0

        from crewai_productfeature_planner.apis.publishing.service import (
            create_jira_single,
        )

        created = 0
        for item in jira_pending:
            if _stop_event.is_set():
                break
            run_id = item.get("run_id", "")
            try:
                create_jira_single(run_id)
                created += 1
                logger.info(
                    "[PublishScheduler] Jira tickets created for run_id=%s",
                    run_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[PublishScheduler] Jira creation failed for run_id=%s: %s",
                    run_id, exc,
                )

        return created
    except Exception as exc:  # noqa: BLE001
        logger.warning("[PublishScheduler] Jira scan error: %s", exc)
        return 0


def _get_interval_seconds() -> int:
    """Read ``PUBLISH_SCAN_INTERVAL_SECONDS`` from environment."""
    try:
        val = int(os.environ.get("PUBLISH_SCAN_INTERVAL_SECONDS", _DEFAULT_INTERVAL_SECONDS))
        return max(30, val)  # floor at 30 seconds
    except (ValueError, TypeError):
        return _DEFAULT_INTERVAL_SECONDS
