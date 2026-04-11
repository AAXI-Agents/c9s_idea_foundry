"""Dashboard router — ``GET /dashboard/stats`` aggregate endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb.working_ideas import _common
from crewai_productfeature_planner.mongodb.working_ideas._common import (
    WORKING_COLLECTION,
    logger,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_sso_user)],
)


# ── Response model ────────────────────────────────────────────


class DashboardStats(BaseModel):
    """Aggregate idea counts returned by ``GET /dashboard/stats``."""

    total_ideas: int = Field(
        default=0,
        description="Total number of ideas (excluding archived).",
    )
    in_development: int = Field(
        default=0,
        description="Ideas currently in development (paused + inprogress).",
    )
    prd_completed: int = Field(
        default=0,
        description="Ideas with completed PRDs.",
    )
    ideas_in_progress: int = Field(
        default=0,
        description="Ideas currently being processed (inprogress).",
    )
    uxd_completed: int = Field(
        default=0,
        description="Ideas with completed UX design.",
    )


# ── Endpoint ──────────────────────────────────────────────────


@router.get(
    "/stats",
    summary="Dashboard aggregate statistics",
    response_model=DashboardStats,
    description=(
        "Returns aggregate idea counts for the dashboard. "
        "Counts exclude archived ideas."
    ),
    responses={
        200: {"description": "Statistics returned successfully."},
    },
)
async def get_dashboard_stats(
    user: dict = Depends(require_sso_user),
) -> DashboardStats:
    """Aggregate idea counts from the workingIdeas collection."""
    user_id = user.get("user_id", "unknown")
    logger.info("[API] Dashboard stats requested by user_id=%s", user_id)

    try:
        db = _common.get_db()
        coll = db[WORKING_COLLECTION]

        # Single aggregation pipeline for all counts.
        pipeline = [
            {"$match": {"status": {"$ne": "archived"}}},
            {
                "$group": {
                    "_id": None,
                    "total_ideas": {"$sum": 1},
                    "in_development": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["inprogress", "paused"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "prd_completed": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "completed"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "ideas_in_progress": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "inprogress"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "uxd_completed": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$ux_design_status", "completed"]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]

        results = list(coll.aggregate(pipeline))

        if not results:
            return DashboardStats()

        doc = results[0]
        return DashboardStats(
            total_ideas=doc.get("total_ideas", 0),
            in_development=doc.get("in_development", 0),
            prd_completed=doc.get("prd_completed", 0),
            ideas_in_progress=doc.get("ideas_in_progress", 0),
            uxd_completed=doc.get("uxd_completed", 0),
        )

    except PyMongoError as exc:
        logger.error(
            "[API] Dashboard stats aggregation failed: %s",
            exc,
            exc_info=True,
        )
        # Return zeros rather than 500 — the frontend has a
        # fallback to client-side counting anyway.
        return DashboardStats()
