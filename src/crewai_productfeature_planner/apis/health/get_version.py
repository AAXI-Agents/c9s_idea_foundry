"""GET /version — Application version and codex (changelog).

Request:  No parameters.
Response: { "version": "X.Y.Z", "latest": {...}, "codex": [...] }
Database: None — reads from version.py in-memory codex list.
"""

from fastapi import APIRouter

from crewai_productfeature_planner.version import (
    get_codex,
    get_latest_codex_entry,
    get_version,
)

router = APIRouter()


@router.get(
    "/version",
    tags=["Health"],
    summary="Application version and codex",
    description=(
        "Returns the current application version, the latest changelog "
        "entry, and the full codex (changelog) of all iterations.\n\n"
        "Use this to verify which build is deployed and trace what "
        "changed in each iteration."
    ),
    responses={
        200: {
            "description": "Version info with codex.",
            "content": {
                "application/json": {
                    "example": {
                        "version": "0.1.3",
                        "latest": {
                            "version": "0.1.3",
                            "date": "2026-02-28",
                            "summary": "Version control & codex.",
                        },
                        "codex": [
                            {
                                "version": "0.1.0",
                                "date": "2026-02-14",
                                "summary": "Initial release.",
                            },
                        ],
                    }
                }
            },
        },
    },
)
async def version():
    """Return version and full codex (changelog)."""
    return {
        "version": get_version(),
        "latest": get_latest_codex_entry(),
        "codex": get_codex(),
    }
