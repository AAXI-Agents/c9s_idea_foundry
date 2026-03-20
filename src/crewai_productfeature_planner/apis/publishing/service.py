"""Publishing service — business logic for listing, publishing, and ticketing.

Wraps existing discovery and publishing infrastructure into a clean,
API-callable interface.  Every public function returns plain dicts
(JSON-serialisable) so routers can forward them directly.
"""

from __future__ import annotations

from typing import Any

from crewai_productfeature_planner.orchestrator._helpers import make_page_title
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models (plain dicts — no Pydantic needed here)
# ---------------------------------------------------------------------------

def _prd_summary(item: dict, *, delivery: dict | None = None) -> dict[str, Any]:
    """Normalise a discovery item into a concise API-friendly summary."""
    run_id = item.get("run_id", "")
    rec = delivery or {}
    return {
        "run_id": run_id,
        "title": item.get("title") or item.get("idea", "PRD"),
        "source": item.get("source", "mongodb"),
        "output_file": item.get("output_file", ""),
        "confluence_published": rec.get("confluence_published", False),
        "confluence_url": rec.get("confluence_url") or item.get("confluence_url", ""),
        "jira_completed": rec.get("jira_completed", False),
        "jira_tickets": rec.get("jira_tickets") or [],
        "status": rec.get("status", "new"),
    }


# ---------------------------------------------------------------------------
# List / discover
# ---------------------------------------------------------------------------


def list_pending_prds() -> list[dict[str, Any]]:
    """Return all PRDs that still need Confluence publishing or Jira tickets.

    Merges two discovery sources:

    * ``_discover_publishable_prds()`` — PRDs needing Confluence publish
    * ``_discover_pending_deliveries()`` — items needing Jira ticketing

    Returns a de-duplicated list keyed on ``run_id``.
    """
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
    )
    from crewai_productfeature_planner.orchestrator._startup_delivery import (
        _discover_pending_deliveries,
    )
    from crewai_productfeature_planner.orchestrator._startup_review import (
        _discover_publishable_prds,
    )

    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    # Source 1 — unpublished PRDs (Confluence)
    try:
        for item in _discover_publishable_prds():
            rid = item.get("run_id", "")
            key = rid or item.get("output_file", "")
            if key in seen:
                continue
            seen.add(key)
            rec = get_delivery_record(rid) if rid else None
            results.append(_prd_summary(item, delivery=rec))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Publishing] Publishable discovery failed: %s", exc)

    # Source 2 — pending deliveries (Jira)
    try:
        for item in _discover_pending_deliveries():
            rid = item.get("run_id", "")
            if rid in seen:
                continue
            seen.add(rid)
            rec = get_delivery_record(rid) if rid else None
            results.append(_prd_summary(item, delivery=rec))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Publishing] Delivery discovery failed: %s", exc)

    logger.info("[Publishing] list_pending_prds found %d items", len(results))
    return results


# ---------------------------------------------------------------------------
# Confluence publishing
# ---------------------------------------------------------------------------


def publish_confluence_single(run_id: str) -> dict[str, Any]:
    """Publish a single PRD to Confluence by ``run_id``.

    Returns a dict with ``run_id``, ``url``, ``page_id``, ``action``.
    Raises ``ValueError`` when the run cannot be found.
    """
    from crewai_productfeature_planner.components.document import assemble_prd_from_doc
    from crewai_productfeature_planner.mongodb import (
        find_completed_without_confluence,
    )
    from crewai_productfeature_planner.mongodb.product_requirements import (
        upsert_delivery_record,
    )
    from crewai_productfeature_planner.mongodb.project_config import (
        get_project_for_run,
    )
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials,
        confluence_project_context,
        publish_to_confluence,
    )

    if not _has_confluence_credentials():
        raise RuntimeError("Confluence credentials are not configured")

    # Find the matching document
    docs = find_completed_without_confluence()
    target_doc = None
    for doc in docs:
        if doc.get("run_id") == run_id:
            target_doc = doc
            break

    if target_doc is None:
        raise ValueError(
            f"No unpublished PRD found for run_id={run_id}. "
            "It may have been published already or the run_id is invalid."
        )

    content = assemble_prd_from_doc(target_doc)
    if not content:
        raise ValueError(f"Could not assemble PRD content for run_id={run_id}")

    idea = target_doc.get("idea")
    title = make_page_title(idea)

    # Resolve project-level keys (falls back to env vars if unset)
    pc = get_project_for_run(run_id) or {}
    ctx_space = pc.get("confluence_space_key", "")
    ctx_parent = pc.get("confluence_parent_id", "")

    with confluence_project_context(space_key=ctx_space, parent_id=ctx_parent):
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

    logger.info(
        "[PublishingService] Published run_id=%s → %s",
        run_id, result["url"],
    )

    return {
        "run_id": run_id,
        "title": title,
        "url": result["url"],
        "page_id": result["page_id"],
        "action": result.get("action", "created"),
    }


def publish_confluence_all() -> dict[str, Any]:
    """Publish all pending PRDs to Confluence.

    Returns a summary dict with ``published``, ``failed``, ``results``.
    """
    from crewai_productfeature_planner.orchestrator._startup_review import (
        _discover_publishable_prds,
    )
    from crewai_productfeature_planner.mongodb.project_config import (
        get_project_for_run,
    )
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials,
        confluence_project_context,
        publish_to_confluence,
    )

    if not _has_confluence_credentials():
        raise RuntimeError("Confluence credentials are not configured")

    items = _discover_publishable_prds()
    if not items:
        return {"published": 0, "failed": 0, "results": [], "message": "No pending PRDs to publish"}

    published: list[dict] = []
    failed: list[dict] = []

    for item in items:
        try:
            # Resolve project-level Confluence keys per item
            rid = item.get("run_id", "")
            pc = get_project_for_run(rid) if rid else None
            pc = pc or {}
            ctx_space = pc.get("confluence_space_key", "")
            ctx_parent = pc.get("confluence_parent_id", "")

            with confluence_project_context(
                space_key=ctx_space, parent_id=ctx_parent,
            ):
                result = publish_to_confluence(
                    title=item["title"],
                    markdown_content=item["content"],
                    run_id=item.get("run_id", ""),
                )

            # Persist delivery record in productRequirements
            if item.get("run_id"):
                from crewai_productfeature_planner.mongodb.product_requirements import (
                    upsert_delivery_record as _upsert_dr,
                )
                _upsert_dr(
                    run_id=item["run_id"],
                    confluence_published=True,
                    confluence_url=result["url"],
                    confluence_page_id=result["page_id"],
                )

            published.append({
                "run_id": item.get("run_id", ""),
                "title": item["title"],
                "url": result["url"],
                "page_id": result["page_id"],
                "action": result.get("action", "created"),
            })
        except Exception as exc:  # noqa: BLE001
            failed.append({
                "run_id": item.get("run_id", ""),
                "title": item["title"],
                "error": str(exc),
            })
            logger.warning(
                "[PublishingService] Failed to publish '%s': %s",
                item["title"], exc,
            )

    return {
        "published": len(published),
        "failed": len(failed),
        "results": published,
        "errors": failed,
    }


# ---------------------------------------------------------------------------
# Jira ticketing
# ---------------------------------------------------------------------------


def create_jira_single(run_id: str) -> dict[str, Any]:
    """Create Jira tickets for a single run_id.

    Delegates to the CrewAI delivery crew which handles Epic, Stories,
    and Tasks creation.  Returns a summary dict.

    Raises ``ValueError`` if no deliverable content is found.
    """
    from crewai_productfeature_planner.orchestrator._helpers import (
        _has_jira_credentials,
    )
    from crewai_productfeature_planner.orchestrator._startup_delivery import (
        _discover_pending_deliveries,
    )

    if not _has_jira_credentials():
        raise RuntimeError("Jira credentials are not configured")

    items = _discover_pending_deliveries()
    target = None
    for item in items:
        if item.get("run_id") == run_id:
            target = item
            break

    if target is None:
        raise ValueError(
            f"No pending delivery found for run_id={run_id}. "
            "Confluence must be published first, and Jira may already be complete."
        )

    # Use the existing startup delivery logic for a single item
    from crewai_productfeature_planner.mongodb.product_requirements import (
        upsert_delivery_record,
    )
    from crewai_productfeature_planner.mongodb.project_config import (
        get_project_for_run,
    )
    from crewai_productfeature_planner.orchestrator._startup_delivery import (
        build_startup_delivery_crew,
    )
    from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry
    from crewai_productfeature_planner.tools.jira_tool import jira_project_context

    progress_lines: list[str] = []

    def _progress_cb(msg: str) -> None:
        progress_lines.append(msg)

    # Resolve project-level Jira key
    pc = get_project_for_run(run_id) or {}
    ctx_key = pc.get("jira_project_key", "")

    crew = build_startup_delivery_crew(target, progress_callback=_progress_cb)
    with jira_project_context(project_key=ctx_key):
        result = crew_kickoff_with_retry(
            crew, step_label=f"publish_jira_{run_id}",
        )
    raw = result.raw if hasattr(result, "raw") else str(result)

    # Persist result
    upsert_delivery_record(run_id, jira_completed=True, jira_output=raw)

    logger.info("[PublishingService] Jira tickets created for run_id=%s", run_id)

    # Extract ticket keys
    import re
    ticket_keys = re.findall(r"[A-Z]{2,10}-\d+", raw)

    return {
        "run_id": run_id,
        "jira_completed": True,
        "ticket_keys": ticket_keys,
        "progress": progress_lines,
    }


def create_jira_all() -> dict[str, Any]:
    """Create Jira tickets for all pending deliveries.

    Returns a summary with ``completed``, ``failed``, ``results``.
    """
    from crewai_productfeature_planner.orchestrator._helpers import (
        _has_jira_credentials,
    )
    from crewai_productfeature_planner.orchestrator._startup_delivery import (
        _discover_pending_deliveries,
    )

    if not _has_jira_credentials():
        raise RuntimeError("Jira credentials are not configured")

    items = _discover_pending_deliveries()
    # Filter to items where Confluence is done but Jira is not
    jira_pending = [i for i in items if i.get("confluence_done") and not i.get("jira_done")]

    if not jira_pending:
        return {"completed": 0, "failed": 0, "results": [], "message": "No pending Jira deliveries"}

    completed: list[dict] = []
    failed: list[dict] = []

    for item in jira_pending:
        run_id = item.get("run_id", "")
        try:
            result = create_jira_single(run_id)
            completed.append(result)
        except Exception as exc:  # noqa: BLE001
            failed.append({"run_id": run_id, "error": str(exc)})
            logger.warning(
                "[PublishingService] Jira creation failed for run_id=%s: %s",
                run_id, exc,
            )

    return {
        "completed": len(completed),
        "failed": len(failed),
        "results": completed,
        "errors": failed,
    }


# ---------------------------------------------------------------------------
# Combined publish + ticket
# ---------------------------------------------------------------------------


def publish_and_create_tickets(run_id: str) -> dict[str, Any]:
    """Publish to Confluence then create Jira tickets for a single run.

    Returns a combined summary dict.
    """
    logger.info("[Publishing] publish_and_create_tickets run_id=%s", run_id)
    result: dict[str, Any] = {"run_id": run_id}

    # Step 1 — Confluence
    try:
        conf_result = publish_confluence_single(run_id)
        result["confluence"] = conf_result
    except (ValueError, RuntimeError):
        # Already published or no credentials — check if we can proceed
        from crewai_productfeature_planner.mongodb.product_requirements import (
            get_delivery_record,
        )
        rec = get_delivery_record(run_id)
        if rec and rec.get("confluence_published"):
            result["confluence"] = {"status": "already_published", "url": rec.get("confluence_url", "")}
        else:
            raise

    # Step 2 — Jira
    try:
        jira_result = create_jira_single(run_id)
        result["jira"] = jira_result
    except (ValueError, RuntimeError) as exc:
        result["jira"] = {"status": "skipped", "reason": str(exc)}

    return result


def publish_all_and_create_tickets() -> dict[str, Any]:
    """Publish all pending Confluence pages then create all Jira tickets.

    Returns a combined summary.
    """
    logger.info("[Publishing] publish_all_and_create_tickets called")
    conf = publish_confluence_all()
    jira = create_jira_all()
    return {
        "confluence": conf,
        "jira": jira,
    }


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------


def get_delivery_status(run_id: str) -> dict[str, Any]:
    """Return the full delivery status for a ``run_id``."""
    logger.info("[Publishing] get_delivery_status run_id=%s", run_id)
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
    )

    rec = get_delivery_record(run_id)
    if rec is None:
        logger.warning("[Publishing] No delivery record for run_id=%s", run_id)
        raise ValueError(f"No delivery record found for run_id={run_id}")

    # Remove MongoDB _id for JSON serialisation
    rec.pop("_id", None)
    return rec
