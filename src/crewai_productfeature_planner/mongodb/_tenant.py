"""Multi-tenancy helpers for MongoDB query scoping.

Every repository function that reads or writes documents **must** use
``tenant_filter()`` or ``tenant_fields()`` to ensure data isolation.

Hierarchy (Decision 1 — Two-Level with Enterprise Override):

    Enterprise (corporate)
        └── Organization (division/subsidiary)
              └── Projects, Ideas, PRDs, etc.

Access rules:
    - Users with ``enterprise_admin`` role → see all orgs in their enterprise
    - All other users → see only their own organization's data
    - Background/system processes → pass ``TenantContext.SYSTEM`` to bypass

A **regression test** (``tests/test_tenant_isolation.py``) ensures every
repository function includes tenant filtering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Sentinel value for system/background processes that need global access.
_SYSTEM_ENTERPRISE = "__system__"
_SYSTEM_ORG = "__system__"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Immutable tenant identity extracted from the authenticated user.

    Attributes:
        enterprise_id: Corporate parent ID (from JWT ``enterprise_id``).
        organization_id: Division/subsidiary ID (from JWT ``organization_id``).
        is_enterprise_admin: Whether the user has the ``enterprise_admin`` role.
    """

    enterprise_id: str
    organization_id: str
    is_enterprise_admin: bool = False

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_user(cls, user: dict[str, Any]) -> TenantContext:
        """Build a ``TenantContext`` from the dict returned by ``require_sso_user()``.

        Args:
            user: The authenticated user dict containing ``enterprise_id``,
                ``organization_id``, and ``roles``.

        Returns:
            A ``TenantContext`` with the user's tenant identity.
        """
        roles = user.get("roles") or []
        return cls(
            enterprise_id=user.get("enterprise_id") or "",
            organization_id=user.get("organization_id") or "",
            is_enterprise_admin="enterprise_admin" in roles,
        )

    @classmethod
    def from_slack_install(cls, install: dict[str, Any]) -> TenantContext:
        """Build a ``TenantContext`` from a ``slackOAuth`` document.

        Slack events don't carry JWT claims, so we derive the tenant
        from the OAuth installation record.

        Args:
            install: The ``slackOAuth`` document for the workspace.

        Returns:
            A ``TenantContext`` scoped to the Slack workspace's org.
        """
        return cls(
            enterprise_id=install.get("enterprise_id") or "",
            organization_id=install.get("organization_id") or "",
            is_enterprise_admin=False,
        )

    @classmethod
    def system(cls) -> TenantContext:
        """Tenant context for background/system processes.

        System processes need to query across all tenants.
        ``tenant_filter()`` returns ``{}`` for system contexts.
        """
        return cls(
            enterprise_id=_SYSTEM_ENTERPRISE,
            organization_id=_SYSTEM_ORG,
            is_enterprise_admin=False,
        )


def tenant_filter(ctx: TenantContext | None) -> dict[str, Any]:
    """Build a MongoDB query filter that enforces tenant isolation.

    Returns a filter dict to be merged (``{**tenant_filter(ctx), ...}``)
    or ``$and``-ed with additional query conditions.

    Access rules:
        - **None / no context** → ``{}`` (no filter — backward compat)
        - **System context** → ``{}`` (no filter — global access)
        - **Enterprise admin** → ``{"enterprise_id": ctx.enterprise_id}``
          (sees all orgs in their enterprise)
        - **Regular user** → ``{"organization_id": ctx.organization_id}``
          (sees only their own org)

    Args:
        ctx: The tenant context from the authenticated user, or None.

    Returns:
        A MongoDB filter dict for tenant scoping.
    """
    if ctx is None:
        return {}

    # System / background processes — global access.
    if ctx.enterprise_id == _SYSTEM_ENTERPRISE:
        return {}

    # Enterprise admin — sees all orgs under their enterprise.
    if ctx.is_enterprise_admin and ctx.enterprise_id:
        return {"enterprise_id": ctx.enterprise_id}

    # Regular user — sees only their own org.
    if ctx.organization_id:
        return {"organization_id": ctx.organization_id}

    # Fallback: if enterprise_id is set but no org, scope to enterprise.
    if ctx.enterprise_id:
        return {"enterprise_id": ctx.enterprise_id}

    # No tenant info at all — return empty filter.
    # This handles SSO-disabled mode / anonymous users.
    logger.warning(
        "[Tenant] No enterprise_id or organization_id — query is unscoped"
    )
    return {}


def tenant_fields(ctx: TenantContext | None) -> dict[str, str]:
    """Return the tenant fields to embed in a new document.

    Every ``insert_one`` or ``update_one`` (upsert) MUST include these
    fields so the document is properly scoped.

    Args:
        ctx: The tenant context from the authenticated user, or None.

    Returns:
        A dict with ``enterprise_id`` and ``organization_id``,
        or an empty dict if *ctx* is None.
    """
    if ctx is None:
        return {}
    return {
        "enterprise_id": ctx.enterprise_id,
        "organization_id": ctx.organization_id,
    }
