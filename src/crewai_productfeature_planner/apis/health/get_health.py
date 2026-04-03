"""GET /health — Liveness probe.

Request:  No parameters.
Response: { "status": "ok", "version": "X.Y.Z" }
Database: None.
"""

from fastapi import APIRouter

from crewai_productfeature_planner.version import get_version

router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description=(
        "Returns ``{\"status\": \"ok\", \"version\": \"X.Y.Z\"}`` to confirm the "
        "service is running and which build is deployed.\n\n"
        "Use this as a **liveness probe** for container orchestration "
        "(Docker, Kubernetes) or uptime monitoring.  The endpoint performs "
        "no database or external service checks — use "
        "``GET /health/slack-token`` to verify Slack token health."
    ),
    responses={
        200: {
            "description": "Service is alive.",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "version": "0.1.3"}
                }
            },
        },
    },
)
async def health():
    """Basic liveness probe."""
    return {"status": "ok", "version": get_version()}
