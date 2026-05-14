"""Shared WebSocket JWT authentication helper.

Extracted from the ideation WebSocket to be reused across all WS
endpoints (ideation, knowledge, etc.).
"""

from __future__ import annotations

import os
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


async def validate_ws_token(token: str | None) -> dict[str, Any] | None:
    """Validate a JWT token for WebSocket auth.

    Returns user claims dict on success, None on failure.
    Mirrors the same validation logic as ``require_sso_user`` including
    the public-key refresh fallback.
    """
    # If SSO is disabled, allow all connections (dev mode)
    if os.environ.get("SSO_ENABLED", "false").strip().lower() not in ("true", "1", "yes"):
        return {
            "user_id": "anonymous",
            "roles": ["SYS_ADMIN"],
            "enterprise_id": os.environ.get("DEV_ENTERPRISE_ID", "dev-enterprise"),
            "organization_id": os.environ.get("DEV_ORGANIZATION_ID", "dev-org"),
        }

    if not token:
        return None

    from crewai_productfeature_planner.apis.sso_auth import (
        _decode_jwt_locally,
        _fetch_and_save_public_key,
        _introspect_remotely,
    )

    # Try remote introspection first, then local decode
    claims = await _introspect_remotely(token)
    if claims is None:
        claims = _decode_jwt_locally(token)

    # Fallback: refresh the public key and retry local decode
    if claims is None:
        new_key = await _fetch_and_save_public_key()
        if new_key:
            claims = _decode_jwt_locally(token)

    return claims
