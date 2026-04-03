"""Ideas API sub-package.

Route modules:
    get_ideas.py          — GET /ideas (paginated list)
    get_idea.py           — GET /ideas/{run_id}
    patch_idea_status.py  — PATCH /ideas/{run_id}/status

Shared:
    models.py             — IdeaItem, IdeaListResponse, IdeaStatusUpdate, idea_fields()
"""

from crewai_productfeature_planner.apis.ideas.router import router

__all__ = ["router"]
