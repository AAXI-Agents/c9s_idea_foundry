"""Health check API.

Route modules:
    get_health.py                 — GET /health (liveness probe)
    get_version.py                — GET /version (version + codex)
    get_slack_token.py            — GET /health/slack-token (token diagnostics)
    post_slack_token_exchange.py  — POST /health/slack-token/exchange
    post_slack_token_refresh.py   — POST /health/slack-token/refresh
"""

from crewai_productfeature_planner.apis.health.router import router

__all__ = ["router"]
