"""Publishing API router — list pending PRDs, publish to Confluence, create Jira tickets.

Endpoints:

    GET   /publishing/pending             — list PRDs needing delivery
    POST  /publishing/confluence/all      — batch-publish all to Confluence
    POST  /publishing/confluence/{run_id} — publish a single PRD
    POST  /publishing/jira/all            — batch-create all Jira tickets
    POST  /publishing/jira/{run_id}       — create Jira tickets for one run
    POST  /publishing/all                 — publish Confluence + Jira for everything
    POST  /publishing/all/{run_id}        — publish Confluence + Jira for one run
    GET   /publishing/status/{run_id}     — delivery status for a run
    GET   /publishing/automation/status   — watcher & scheduler status
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from crewai_productfeature_planner.apis.publishing.models import (
    CombinedPublishResult,
    ConfluenceBatchResult,
    ConfluencePublishResult,
    DeliveryStatusResponse,
    JiraBatchResult,
    JiraCreateResult,
    PendingListResponse,
    PublishingErrorResponse,
    WatcherStatusResponse,
)
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _safe_detail(exc: Exception) -> str:
    """Return a generic error message — never expose internal details."""
    if isinstance(exc, RuntimeError):
        return "Service temporarily unavailable. Check server logs."
    return "An internal error occurred. Check server logs."

router = APIRouter(
    prefix="/publishing",
    tags=["Publishing"],
    dependencies=[Depends(require_sso_user)],
)

# Standard error responses documented on every endpoint.
_ERROR_RESPONSES: dict = {
    500: {
        "description": "Internal server error.",
        "model": PublishingErrorResponse,
    },
}


# ---------------------------------------------------------------------------
# GET /publishing/pending
# ---------------------------------------------------------------------------


@router.get(
    "/pending",
    response_model=PendingListResponse,
    summary="List PRDs pending delivery",
    description=(
        "Discover all PRDs that still require Confluence publishing or "
        "Jira ticket creation.  Merges MongoDB completed runs and "
        "on-disk markdown files in ``output/prds/``."
    ),
    responses=_ERROR_RESPONSES,
)
async def list_pending(user: dict = Depends(require_sso_user)):
    """Return all PRDs that need Confluence publish or Jira tickets."""
    from crewai_productfeature_planner.apis.publishing.service import (
        list_pending_prds,
    )

    try:
        items = list_pending_prds()
        return PendingListResponse(count=len(items), items=items)
    except Exception as exc:
        logger.error("list_pending failed: %s", exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# POST /publishing/confluence/all
# ---------------------------------------------------------------------------


@router.post(
    "/confluence/all",
    response_model=ConfluenceBatchResult,
    summary="Publish all pending PRDs to Confluence",
    description=(
        "Iterates over every unpublished PRD discovered from MongoDB "
        "and disk, converts each to XHTML, and creates or updates the "
        "Confluence page. Returns a batch summary with per-item results."
    ),
    responses=_ERROR_RESPONSES,
)
async def publish_confluence_all_endpoint(background_tasks: BackgroundTasks, user: dict = Depends(require_sso_user)):
    """Batch-publish all pending PRDs to Confluence."""
    from crewai_productfeature_planner.apis.publishing.service import (
        publish_confluence_all,
    )

    try:
        result = publish_confluence_all()
        return ConfluenceBatchResult(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("publish_confluence_all failed: %s", exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# POST /publishing/confluence/{run_id}
# ---------------------------------------------------------------------------


@router.post(
    "/confluence/{run_id}",
    response_model=ConfluencePublishResult,
    summary="Publish a single PRD to Confluence",
    description=(
        "Look up the completed PRD for the given ``run_id`` and publish "
        "it to Confluence. Persists the Confluence URL back to MongoDB. "
        "Returns 404 if no unpublished PRD is found for the run."
    ),
    responses={
        404: {
            "description": "No unpublished PRD found for the given run_id.",
            "model": PublishingErrorResponse,
        },
        **_ERROR_RESPONSES,
    },
)
async def publish_confluence_single_endpoint(run_id: str, user: dict = Depends(require_sso_user)):
    """Publish a single PRD to Confluence."""
    from crewai_productfeature_planner.apis.publishing.service import (
        publish_confluence_single,
    )

    try:
        result = publish_confluence_single(run_id)
        return ConfluencePublishResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("publish_confluence_single failed for %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# POST /publishing/jira/all
# ---------------------------------------------------------------------------


@router.post(
    "/jira/all",
    response_model=JiraBatchResult,
    summary="Create Jira tickets for all pending deliveries",
    description=(
        "Iterates over every delivery where Confluence is published but "
        "Jira tickets are missing.  Launches a CrewAI delivery crew "
        "for each to create Epics, Stories, and Tasks. "
        "Returns a batch summary."
    ),
    responses=_ERROR_RESPONSES,
)
async def create_jira_all_endpoint(background_tasks: BackgroundTasks, user: dict = Depends(require_sso_user)):
    """Batch-create Jira tickets for all pending deliveries."""
    from crewai_productfeature_planner.apis.publishing.service import (
        create_jira_all,
    )

    try:
        result = create_jira_all()
        return JiraBatchResult(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("create_jira_all failed: %s", exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# POST /publishing/jira/{run_id}
# ---------------------------------------------------------------------------


@router.post(
    "/jira/{run_id}",
    response_model=JiraCreateResult,
    summary="Create Jira tickets for a single run",
    description=(
        "Create Jira Epic, Stories, and Tasks for the given ``run_id``. "
        "Requires that the PRD has already been published to Confluence. "
        "Uses the CrewAI delivery crew for intelligent ticket creation."
    ),
    responses={
        404: {
            "description": "No pending delivery found for the given run_id.",
            "model": PublishingErrorResponse,
        },
        **_ERROR_RESPONSES,
    },
)
async def create_jira_single_endpoint(run_id: str, user: dict = Depends(require_sso_user)):
    """Create Jira tickets for a single run."""
    from crewai_productfeature_planner.apis.publishing.service import (
        create_jira_single,
    )

    try:
        result = create_jira_single(run_id)
        return JiraCreateResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("create_jira_single failed for %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# POST /publishing/all
# ---------------------------------------------------------------------------


@router.post(
    "/all",
    response_model=CombinedPublishResult,
    summary="Publish all Confluence pages and create all Jira tickets",
    description=(
        "Convenience endpoint that first publishes all pending PRDs to "
        "Confluence, then creates Jira tickets for all deliveries "
        "where Confluence is published but Jira is incomplete."
    ),
    responses=_ERROR_RESPONSES,
)
async def publish_all_endpoint(background_tasks: BackgroundTasks, user: dict = Depends(require_sso_user)):
    """Full batch: Confluence publish + Jira ticketing."""
    from crewai_productfeature_planner.apis.publishing.service import (
        publish_all_and_create_tickets,
    )

    try:
        result = publish_all_and_create_tickets()
        return CombinedPublishResult(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("publish_all failed: %s", exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# POST /publishing/all/{run_id}
# ---------------------------------------------------------------------------


@router.post(
    "/all/{run_id}",
    response_model=CombinedPublishResult,
    summary="Publish Confluence + create Jira tickets for one run",
    description=(
        "End-to-end delivery for a single ``run_id``: publishes the "
        "PRD to Confluence (if needed), then creates Jira tickets."
    ),
    responses={
        404: {
            "description": "No deliverable content found for the run_id.",
            "model": PublishingErrorResponse,
        },
        **_ERROR_RESPONSES,
    },
)
async def publish_single_all_endpoint(run_id: str, user: dict = Depends(require_sso_user)):
    """Full pipeline for a single run: Confluence + Jira."""
    from crewai_productfeature_planner.apis.publishing.service import (
        publish_and_create_tickets,
    )

    try:
        result = publish_and_create_tickets(run_id)
        return CombinedPublishResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("publish_single_all failed for %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# GET /publishing/status/{run_id}
# ---------------------------------------------------------------------------


@router.get(
    "/status/{run_id}",
    response_model=DeliveryStatusResponse,
    summary="Get delivery status for a run",
    description=(
        "Returns the full delivery record for the given ``run_id`` from "
        "the ``productRequirements`` MongoDB collection, including "
        "Confluence publication state, Jira ticket list, and any errors."
    ),
    responses={
        404: {
            "description": "No delivery record found for the run_id.",
            "model": PublishingErrorResponse,
        },
        **_ERROR_RESPONSES,
    },
)
async def get_status_endpoint(run_id: str, user: dict = Depends(require_sso_user)):
    """Return delivery status for a run."""
    from crewai_productfeature_planner.apis.publishing.service import (
        get_delivery_status,
    )

    try:
        return get_delivery_status(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=_safe_detail(exc)) from exc
    except Exception as exc:
        logger.error("get_status failed for %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=_safe_detail(exc)) from exc


# ---------------------------------------------------------------------------
# GET /publishing/automation/status
# ---------------------------------------------------------------------------


@router.get(
    "/automation/status",
    response_model=WatcherStatusResponse,
    summary="Get file watcher and cron scheduler status",
    description=(
        "Returns whether the file watcher and periodic scan scheduler "
        "are currently running, along with their configuration."
    ),
    responses=_ERROR_RESPONSES,
)
async def get_automation_status(user: dict = Depends(require_sso_user)):
    """Return the status of the file watcher and cron scheduler."""
    from crewai_productfeature_planner.apis.publishing.scheduler import (
        get_scheduler_status,
    )
    from crewai_productfeature_planner.apis.publishing.watcher import (
        get_watcher_status,
    )

    watcher = get_watcher_status()
    scheduler = get_scheduler_status()

    return WatcherStatusResponse(
        watcher_running=watcher["running"],
        watcher_directory=watcher["directory"],
        scheduler_running=scheduler["running"],
        scheduler_interval_seconds=scheduler["interval_seconds"],
    )
