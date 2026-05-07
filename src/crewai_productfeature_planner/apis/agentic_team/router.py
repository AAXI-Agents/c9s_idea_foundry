"""Router composition for Agentic Team integration endpoints."""

from fastapi import APIRouter

from crewai_productfeature_planner.apis.agentic_team._deliveries import (
    router as deliveries_router,
)
from crewai_productfeature_planner.apis.agentic_team._status import (
    router as status_router,
)
from crewai_productfeature_planner.apis.agentic_team._webhook import (
    router as webhook_router,
)

router = APIRouter()
router.include_router(webhook_router)
router.include_router(status_router)
router.include_router(deliveries_router)
