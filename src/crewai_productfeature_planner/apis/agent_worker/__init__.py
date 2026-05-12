"""Agent Worker proxy layer — ``/aw/`` endpoints.

Provides a gateway for the frontend to interact with the Agent Worker
service through the Idea Foundry backend.  Credentials are stored locally
(encrypted) and forwarded to Agent Worker (store-and-forward pattern).
The generic proxy forwards all other requests with the user's Bearer token.
"""

from crewai_productfeature_planner.apis.agent_worker._route_credentials import (
    router as aw_credentials_router,
)
from crewai_productfeature_planner.apis.agent_worker._route_proxy import (
    router as aw_proxy_router,
)

__all__ = ["aw_credentials_router", "aw_proxy_router"]
