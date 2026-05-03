"""Admin-level FastAPI dependencies.

Provides ``require_enterprise_admin`` — a dependency that enforces
the ``ENT_ADMIN`` (or ``SYS_ADMIN``) role. Also provides
``resolve_tenant_context`` which supports the ``organization_id``
query param override for enterprise admins.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Query, status

from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.rbac import Role, resolve_role
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


async def require_enterprise_admin(
    user: dict[str, Any] = Depends(require_sso_user),
) -> dict[str, Any]:
    """FastAPI dependency that requires the ``ENT_ADMIN`` or ``SYS_ADMIN`` role.

    Returns the user dict unchanged if authorized, raises 403 otherwise.
    """
    roles = user.get("roles") or []
    role = resolve_role(roles)
    if role not in (Role.ENT_ADMIN, Role.SYS_ADMIN):
        logger.warning(
            "[Admin] Forbidden: user_id=%s attempted admin action without ENT_ADMIN/SYS_ADMIN role",
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


async def require_sys_admin(
    user: dict[str, Any] = Depends(require_sso_user),
) -> dict[str, Any]:
    """FastAPI dependency that requires the ``SYS_ADMIN`` role.

    Only platform operators can access system-level settings.
    Returns the user dict unchanged if authorized, raises 403 otherwise.
    """
    roles = user.get("roles") or []
    role = resolve_role(roles)
    if role != Role.SYS_ADMIN:
        logger.warning(
            "[Admin] Forbidden: user_id=%s attempted sys_admin action without SYS_ADMIN role",
            user.get("user_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin role required.",
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
    role = resolve_role(roles)
    is_admin = role in (Role.ENT_ADMIN, Role.SYS_ADMIN)

    if is_admin and organization_id:
        # Enterprise admin scoping to a specific org
        return TenantContext(
            enterprise_id=user.get("enterprise_id") or "",
            organization_id=organization_id,
            role=Role.USER,  # Act as org-level scope
        )

    # Default: regular TenantContext.from_user behavior
    return TenantContext.from_user(user)


# ── Generic role gate factory ─────────────────────────────────────────


def require_role(*allowed_roles: Role):
    """Return a FastAPI dependency that enforces membership in *allowed_roles*.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role(Role.SYS_ADMIN))])
        async def admin_endpoint(): ...

        @router.get("/org", dependencies=[Depends(require_role(Role.USER, Role.ENT_ADMIN, Role.SYS_ADMIN))])
        async def org_endpoint(): ...
    """
    allowed = frozenset(allowed_roles)

    async def _guard(
        user: dict[str, Any] = Depends(require_sso_user),
    ) -> dict[str, Any]:
        roles = user.get("roles") or []
        role = resolve_role(roles)
        if role not in allowed:
            logger.warning(
                "[RBAC] Forbidden: user_id=%s role=%s not in %s",
                user.get("user_id"), role.value, [r.value for r in allowed],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {' or '.join(r.value for r in sorted(allowed, key=lambda r: r.value))}",
            )
        return user

    return _guard
