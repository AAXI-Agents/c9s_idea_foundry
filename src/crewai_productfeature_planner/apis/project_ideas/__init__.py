"""Project Ideas API router — CRUD for ideas under projects.

Route modules:
    _route_crud.py         — POST, GET list, GET detail, PATCH, DELETE
    _route_features.py     — PATCH features
    _route_flow.py         — POST start, GET progress, POST resume
    _route_deliverables.py — GET deliverables
    _route_jira_webhook.py — POST /webhooks/jira
    _route_websocket.py    — WS /ws/ideas/{idea_id}

All routes are nested under ``/projects/{project_id}/ideas``.
"""

from crewai_productfeature_planner.apis.project_ideas.router import (
    router,
    ws_only_router,
)
from crewai_productfeature_planner.apis.project_ideas._route_jira_webhook import (
    router as jira_webhook_router,
)
from crewai_productfeature_planner.apis.project_ideas._route_websocket import (
    broadcast_idea_event,
    broadcast_idea_sync,
)

__all__ = ["router"]
