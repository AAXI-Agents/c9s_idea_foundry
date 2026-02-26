"""Publishing API — endpoints for Confluence publishing and Jira ticketing.

Provides:

* ``router``    — FastAPI router with publishing endpoints
* ``service``   — Business logic for listing, publishing, and ticketing
* ``watcher``   — File-system watcher for auto-publishing new PRD files
* ``scheduler`` — Periodic cron job that resumes incomplete deliveries
"""

from crewai_productfeature_planner.apis.publishing.router import router

__all__ = ["router"]
