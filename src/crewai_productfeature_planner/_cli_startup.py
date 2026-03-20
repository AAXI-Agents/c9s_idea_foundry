"""Startup process management, delivery orchestration, and output recovery.

Contains functions for killing stale processes, running the autonomous
delivery pipeline (Confluence + Jira), generating missing output files,
and publishing unpublished PRDs at startup.
"""
from __future__ import annotations

import os
import signal
import subprocess

from crewai_productfeature_planner.mongodb import (
    find_completed_without_output,
    save_output_file,
)
from crewai_productfeature_planner.apis.prd.models import SECTION_ORDER
from crewai_productfeature_planner.orchestrator._helpers import make_page_title
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

__all__ = [
    "_CREW_PROCESS_NAMES",
    "_kill_stale_crew_processes",
    "_run_startup_delivery",
    "_run_startup_delivery_background",
    "_confluence_completed_in_output",
    "_jira_completed_in_output",
    "_extract_confluence_url",
    "_generate_missing_outputs",
    "_publish_unpublished_prds",
]

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


def _run_startup_delivery() -> int:
    """Autonomously deliver completed PRDs via CrewAI crew collaboration.

    Scans ``workingIdeas`` for completed runs, checks each against the
    ``productRequirements`` collection, and uses a **CrewAI Crew** with
    sequential process and agent collaboration to execute the delivery
    pipeline (Confluence publish + Jira ticketing).

    The crew comprises two agents:

    * **Delivery Manager** — coordinates the lifecycle, decides which
      steps are needed.  ``allow_delegation=True`` lets it hand off
      tool-bearing work.
    * **Orchestrator** — the specialist equipped with Confluence and
      Jira tools.

    Uses ``productRequirements`` to persist per-run delivery state so
    the agent can resume where it left off on subsequent restarts.

    Prints user-facing progress messages prefixed with ``[Orchestrator]``
    so the user can see what the agent is doing before the interactive
    CLI takes over.

    This is fully autonomous — no user involvement required.

    Returns:
        The number of runs that were fully delivered (Confluence + Jira).
    """
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
        upsert_delivery_record,
    )
    from crewai_productfeature_planner.orchestrator.stages import (
        _discover_pending_deliveries,
        _has_confluence_credentials,
        _has_jira_credentials,
        _print_delivery_status,
        build_startup_delivery_crew,
    )
    from crewai_productfeature_planner.scripts.retry import (
        crew_kickoff_with_retry,
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
        logger.info("[StartupDelivery] No pending deliveries found")
        return 0

    _print_delivery_status(
        f"Found {len(items)} completed PRD(s) pending delivery"
    )

    delivered = 0
    for item in items:
        run_id = item["run_id"]
        idea_preview = (item["idea"] or "PRD")[:60].strip()

        # --- Print what we're about to do ---
        pending_parts = []
        if not item["confluence_done"]:
            pending_parts.append("Confluence publish")
        if not item["jira_done"] and _has_jira_credentials():
            pending_parts.append("Jira ticketing")
        steps_label = " + ".join(pending_parts) or "finalising record"

        _print_delivery_status(
            f"Processing \"{idea_preview}\" — {steps_label}"
        )

        # Seed delivery record so we can resume on crash
        record = get_delivery_record(run_id)
        if not record:
            upsert_delivery_record(
                run_id,
                confluence_published=item["confluence_done"],
                jira_completed=item["jira_done"],
            )

        try:
            # Build the CrewAI crew with sequential process & collaboration
            crew = build_startup_delivery_crew(
                item,
                progress_callback=_print_delivery_status,
                confluence_only=True,
            )

            _print_delivery_status(
                f"Crew assembled — {len(crew.tasks)} task(s), "
                f"{len(crew.agents)} agent(s) collaborating"
            )

            # Kick off the crew (with retry for transient LLM failures)
            result = crew_kickoff_with_retry(
                crew, step_label=f"startup_delivery_{run_id}",
            )

            # Parse result to determine what was accomplished
            raw_output = result.raw if hasattr(result, "raw") else str(result)

            # Update delivery record from crew output —
            # only Confluence status, never Jira (approval gate).
            new_conf_done = item["confluence_done"] or _confluence_completed_in_output(raw_output)

            upsert_delivery_record(
                run_id,
                confluence_published=new_conf_done,
                confluence_url=_extract_confluence_url(raw_output) or item.get("confluence_url", ""),
                error=None,
            )

            if new_conf_done:
                delivered += 1
                _print_delivery_status(
                    f"✓ Published \"{idea_preview}\" to Confluence"
                )
            else:
                _print_delivery_status(
                    f"Delivery for \"{idea_preview}\" — awaiting next restart"
                )

            logger.info(
                "[StartupDelivery] Delivery crew completed for "
                "run_id=%s (confluence=%s)",
                run_id,
                "done" if new_conf_done else "pending",
            )
        except Exception as exc:
            logger.warning(
                "[StartupDelivery] Delivery crew failed for "
                "run_id=%s: %s",
                run_id, exc,
            )
            upsert_delivery_record(run_id, error=str(exc))
            _print_delivery_status(
                f"✗ Delivery failed for \"{idea_preview}\": {exc}"
            )

    if delivered:
        logger.info(
            "[StartupDelivery] Fully delivered %d PRD(s) on startup",
            delivered,
        )
    return delivered


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


def _generate_missing_outputs() -> int:
    """Generate markdown files for completed ideas that are missing output.

    On startup, queries MongoDB for ``workingIdeas`` documents whose
    ``status`` is ``"completed"`` but have no ``output_file`` recorded.
    For each, reconstructs the PRD content from the document and writes
    a markdown file via :class:`PRDFileWriteTool`.

    Returns:
        The number of output files generated.
    """
    from crewai_productfeature_planner._cli_state import _assemble_prd_from_doc, _max_iteration_from_doc
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
            content = _assemble_prd_from_doc(doc)
            if not content:
                logger.debug(
                    "[StartupRecovery] Skipping run_id=%s — no content to assemble",
                    run_id,
                )
                continue

            # Determine version from section iterations
            version = _max_iteration_from_doc(doc)

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
    """Publish completed PRDs to Confluence that haven't been published yet.

    Scans MongoDB for completed working ideas whose ``confluence_url``
    field is missing or empty.  For each, assembles the PRD from the
    stored sections and publishes it to Confluence.

    Called on server startup and after each completed flow.

    Returns:
        Number of PRDs successfully published.
    """
    from crewai_productfeature_planner._cli_state import _assemble_prd_from_doc
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials,
        publish_to_confluence,
    )

    if not _has_confluence_credentials():
        return 0

    try:
        from crewai_productfeature_planner.mongodb import (
            find_completed_without_confluence,
        )
        from crewai_productfeature_planner.mongodb.product_requirements import (
            upsert_delivery_record,
        )
        docs = find_completed_without_confluence()
    except Exception as exc:
        logger.debug(
            "Could not check for unpublished PRDs: %s", exc,
        )
        return 0

    if not docs:
        return 0

    published = 0
    for doc in docs:
        run_id = doc.get("run_id", "unknown")
        try:
            content = _assemble_prd_from_doc(doc)
            if not content:
                logger.debug(
                    "[StartupRecovery] Skipping Confluence publish for "
                    "run_id=%s — no content",
                    run_id,
                )
                continue

            idea = doc.get("idea")
            title = make_page_title(idea)

            result = publish_to_confluence(
                title=title,
                markdown_content=content,
                run_id=run_id,
            )
            upsert_delivery_record(
                run_id=run_id,
                confluence_published=True,
                confluence_url=result["url"],
                confluence_page_id=result["page_id"],
            )
            published += 1
            logger.info(
                "[StartupRecovery] Published PRD to Confluence for "
                "run_id=%s: %s",
                run_id, result["url"],
            )
        except Exception as exc:
            logger.warning(
                "[StartupRecovery] Failed to publish PRD for "
                "run_id=%s: %s",
                run_id, exc,
            )

    if published:
        logger.info(
            "[StartupRecovery] Published %d PRD(s) to Confluence",
            published,
        )
    return published


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
