"""Startup tasks — process management, output recovery, delivery.

Functions that run at application startup (CLI or API server) to
clean up stale processes, recover incomplete outputs, and orchestrate
autonomous delivery of completed PRDs.
"""

import os
import signal
import subprocess

from crewai_productfeature_planner.components.document import (
    assemble_prd_from_doc,
    max_iteration_from_doc,
)
from crewai_productfeature_planner.mongodb import (
    find_completed_without_output,
    save_output_file,
)
from crewai_productfeature_planner.orchestrator._helpers import make_page_title
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Process names used by the project's console_scripts entry points.
_CREW_PROCESS_NAMES = ("run_crew", "crewai_productfeature_planner", "run_prd_flow")


def _kill_stale_crew_processes() -> int:
    """Kill any lingering CrewAI CLI processes from a previous run.

    Scans ``ps`` output for processes whose command line contains one of
    the known entry-point script names and sends ``SIGTERM``.

    The current process **and its entire ancestor chain** (parent,
    grandparent, …) are never killed.  This is important because
    ``crewai run`` spawns ``uv run run_crew`` as an intermediate parent
    whose command line matches the pattern.

    Returns the number of processes terminated.
    """
    my_pid = os.getpid()
    killed = 0

    try:
        # Use `ps` with PPID so we can build the ancestor chain.
        result = subprocess.run(
            ["ps", "axo", "pid,ppid,command"],
            capture_output=True, text=True, timeout=5,
        )

        # First pass: build pid→ppid map so we can walk ancestors.
        ppid_map: dict[int, int] = {}
        lines: list[tuple[int, str]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
            except ValueError:
                continue
            ppid_map[pid] = ppid
            lines.append((pid, parts[2]))

        # Build set of ancestor PIDs to protect.
        protected: set[int] = set()
        cur = my_pid
        while cur and cur not in protected:
            protected.add(cur)
            cur = ppid_map.get(cur, 0)

        # Second pass: kill matching processes that are NOT protected.
        for pid, cmd in lines:
            if pid in protected:
                continue
            if any(name in cmd for name in _CREW_PROCESS_NAMES):
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
                    logger.info(
                        "[Startup] Killed stale process PID %d: %s",
                        pid, cmd[:120],
                    )
                except ProcessLookupError:
                    pass  # already gone
                except PermissionError:
                    logger.debug(
                        "[Startup] No permission to kill PID %d", pid,
                    )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[Startup] Could not scan for stale processes: %s", exc)

    return killed


# ── Startup delivery orchestrator ────────────────────────────────────


def _run_startup_delivery() -> int:
    """Log completed PRDs that still need delivery (Confluence / Jira).

    .. versionchanged:: 0.38.0
       No longer auto-publishes to Confluence or creates Jira tickets.
       Only discovers and logs pending items.  Users must explicitly
       trigger publishing via Slack button or API.

    Returns:
        Always returns 0 (no autonomous delivery).
    """
    from crewai_productfeature_planner.orchestrator.stages import (
        _discover_pending_deliveries,
        _has_confluence_credentials,
        _has_jira_credentials,
        _print_delivery_status,
    )

    if not (_has_confluence_credentials() or _has_jira_credentials()):
        logger.debug(
            "[StartupDelivery] Skipped — neither Confluence nor Jira configured"
        )
        return 0

    # Discover pending deliveries from MongoDB
    try:
        items = _discover_pending_deliveries()
    except Exception as exc:
        logger.warning(
            "[StartupDelivery] Discovery failed: %s", exc,
        )
        return 0
    if not items:
        return 0

    _print_delivery_status(
        f"Found {len(items)} completed PRD(s) pending delivery — "
        "awaiting user-triggered publish"
    )

    for item in items:
        idea_preview = (item["idea"] or "PRD")[:60].strip()
        pending_parts = []
        if not item["confluence_done"]:
            pending_parts.append("Confluence publish")
        if not item["jira_done"] and _has_jira_credentials():
            pending_parts.append("Jira ticketing")
        steps_label = " + ".join(pending_parts) or "finalising record"
        logger.info(
            "[StartupDelivery] Pending: \"%s\" — %s (run_id=%s)",
            idea_preview, steps_label, item["run_id"],
        )

    return 0


# ── Output detection helpers ─────────────────────────────────────────


def _confluence_completed_in_output(output: str) -> bool:
    """Detect Confluence publish success in crew output.

    Requires **both** a success keyword AND a recognisable Confluence URL
    so that mere mentions of "Confluence" in assessment text do not
    trigger a false positive.
    """
    lower = output.lower()
    if "fail" in lower[:200]:
        return False
    has_keyword = any(kw in lower for kw in [
        "published", "created", "updated", "page_id", "page id",
    ])
    has_url = bool(_extract_confluence_url(output))
    return has_keyword and has_url


def _jira_completed_in_output(output: str) -> bool:
    """Detect Jira ticket creation in crew output.

    Requires **both** a Jira keyword AND a recognisable issue key
    pattern (e.g. ``PROJ-123``) to avoid false positives from
    assessment text that merely mentions "Jira".
    """
    import re
    lower = output.lower()
    if "fail" in lower[:200]:
        return False
    has_keyword = any(kw in lower for kw in [
        "epic", "story", "stories",
        "issue_key", "issue key",
    ])
    has_issue_key = bool(re.search(r"[A-Z]{2,10}-\d+", output))
    return has_keyword and has_issue_key


def _extract_confluence_url(output: str) -> str:
    """Extract a Confluence URL from crew output text."""
    import re
    match = re.search(r"https?://[^\s]+atlassian[^\s]*wiki[^\s]*", output)
    if match:
        return match.group(0).rstrip(".,;:()\"'")
    # Fallback: any URL with /wiki/ in it
    match = re.search(r"https?://[^\s]+/wiki/[^\s]*", output)
    if match:
        return match.group(0).rstrip(".,;:()\"'")
    return ""


# ── Output recovery ──────────────────────────────────────────────────


def _generate_missing_outputs() -> int:
    """Generate markdown files for completed ideas that are missing output.

    On startup, queries MongoDB for ``workingIdeas`` documents whose
    ``status`` is ``"completed"`` but have no ``output_file`` recorded.
    For each, reconstructs the PRD content from the document and writes
    a markdown file via :class:`PRDFileWriteTool`.

    Returns:
        The number of output files generated.
    """
    from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool

    try:
        docs = find_completed_without_output()
    except Exception as exc:
        logger.debug("Could not check for completed ideas without output: %s", exc)
        return 0

    if not docs:
        return 0

    generated = 0
    for doc in docs:
        run_id = doc.get("run_id", "unknown")
        try:
            content = assemble_prd_from_doc(doc)
            if not content:
                logger.debug(
                    "[StartupRecovery] Skipping run_id=%s — no content to assemble",
                    run_id,
                )
                continue

            # Determine version from section iterations
            version = max_iteration_from_doc(doc)

            writer = PRDFileWriteTool()
            save_result = writer._run(
                content=content,
                filename="",
                version=max(version, 1),
            )
            # Extract path from "PRD saved to <path>"
            prefix = "PRD saved to "
            output_path = save_result[len(prefix):] if save_result.startswith(prefix) else save_result
            save_output_file(run_id, output_path)
            generated += 1
            logger.info(
                "[StartupRecovery] Generated missing output for run_id=%s: %s",
                run_id, save_result,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[StartupRecovery] Failed to generate output for run_id=%s: %s",
                run_id, exc,
            )

    if generated:
        logger.info(
            "[StartupRecovery] Generated %d missing output file(s)", generated,
        )
    return generated


def _publish_unpublished_prds() -> int:
    """Log completed PRDs that haven't been published to Confluence yet.

    .. versionchanged:: 0.38.0
       No longer auto-publishes.  Only discovers and logs pending PRDs.
       Users must explicitly trigger publishing via Slack button or API.

    Returns:
        Always returns 0 (no autonomous publishing).
    """
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials,
    )

    if not _has_confluence_credentials():
        return 0

    try:
        from crewai_productfeature_planner.mongodb import (
            find_completed_without_confluence,
        )
        docs = find_completed_without_confluence()
    except Exception as exc:
        logger.debug(
            "Could not check for unpublished PRDs: %s", exc,
        )
        return 0

    if docs:
        logger.info(
            "[StartupRecovery] Found %d PRD(s) awaiting Confluence "
            "publish — user must trigger via Slack or API",
            len(docs),
        )

    return 0


def _run_startup_delivery_background() -> None:
    """Wrapper for ``_run_startup_delivery`` that runs in a daemon thread.

    Catches all exceptions so the background thread never crashes the
    main process.  Prints a summary line when delivery completes.
    """
    try:
        delivered = _run_startup_delivery()
        if delivered:
            from crewai_productfeature_planner.orchestrator.stages import (
                _print_delivery_status,
            )
            _print_delivery_status(
                f"Background delivery complete — {delivered} PRD(s) fully delivered"
            )
    except Exception as exc:
        logger.warning("[StartupDelivery] Background thread failed: %s", exc)
