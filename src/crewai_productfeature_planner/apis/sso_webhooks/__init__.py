"""SSO Webhooks API — receives user lifecycle events from the SSO service.

Route modules:
    post_events.py  — POST /sso/webhooks/events
"""

from crewai_productfeature_planner.apis.sso_webhooks.router import router

__all__ = ["router"]
