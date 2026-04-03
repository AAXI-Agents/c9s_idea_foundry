"""Health check router — assembles all health route modules.

Route modules:
    get_health.py                 — GET /health
    get_version.py                — GET /version
    get_slack_token.py            — GET /health/slack-token
    post_slack_token_exchange.py  — POST /health/slack-token/exchange
    post_slack_token_refresh.py   — POST /health/slack-token/refresh
"""

from fastapi import APIRouter

from crewai_productfeature_planner.apis.health.get_health import router as get_health_router
from crewai_productfeature_planner.apis.health.get_version import router as get_version_router
from crewai_productfeature_planner.apis.health.get_slack_token import router as get_slack_token_router
from crewai_productfeature_planner.apis.health.post_slack_token_exchange import router as post_exchange_router
from crewai_productfeature_planner.apis.health.post_slack_token_refresh import router as post_refresh_router

router = APIRouter()
router.include_router(get_health_router)
router.include_router(get_version_router)
router.include_router(get_slack_token_router)
router.include_router(post_exchange_router)
router.include_router(post_refresh_router)
