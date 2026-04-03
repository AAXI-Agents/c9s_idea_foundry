"""SSO Webhooks router — assembles all webhook route modules.

Route modules:
    post_events.py  — POST /sso/webhooks/events
"""

from fastapi import APIRouter

from crewai_productfeature_planner.apis.sso_webhooks.post_events import router as post_events_router

router = APIRouter(prefix="/sso/webhooks", tags=["SSO Webhooks"])
router.include_router(post_events_router)
