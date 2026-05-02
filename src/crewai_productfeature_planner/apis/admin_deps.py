"""Admin-level FastAPI dependencies.

Provides ``require_enterprise_admin`` — a dependency that enforces
the ``enterprise_admin`` role. Also provides ``resolve_tenant_context``
which supports the ``organization_id`` query param override for
enterprise admins.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


async def require_enterprise_admin(
    user: dict[str, Any] = Depends(require_sso_user),
) -> dict[str, Any]:
    """FastAPI dependency that requires the ``enterprise_admin`` role.

    Returns the user dict unchanged if authorized, raises 403 otherwise.
    """
    roles = user.get("roles") or []
    if "enterprise_admin" not in roles:
        logger.warning(
            "[Admin] Forbidden: user_id=%s attempted admin action without enterprise_admin role",
            user.get("user_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise admin role required.",
        )
    if not user.get("enterprise_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No enterprise_id in token — cannot scope admin request.",
        )
    return user


def resolve_tenant_context(
    user: dict[str, Any],
    organization_id: str | None = None,
) -> TenantContext:
    """Build a TenantContext with optional org override for enterprise admins.

    Enterprise admins may pass ``organization_id`` to filter results to
    a specific org within their enterprise.  Non-admins have the param
    ignored.

    When an enterprise admin omits ``organization_id``, they see
    aggregated data across all orgs in their enterprise (default
    TenantContext behavior).

    Args:
        user: Authenticated user dict from ``require_sso_user``.
        organization_id: Optional org override (only honored for enterprise admins).

    Returns:
        A TenantContext scoped appropriately.
    """
    roles = user.get("roles") or []
    is_admin = "enterprise_admin" in roles

    if is_admin and organization_id:
        # Enterprise admin scoping to a specific org
        return TenantContext(
            enterprise_id=user.get("enterprise_id") or "",
            organization_id=organization_id,
            is_enterprise_admin=False,  # Act as org-level scope
        )

    # Default: regular TenantContext.from_user behavior
    return TenantContext.from_user(user)
