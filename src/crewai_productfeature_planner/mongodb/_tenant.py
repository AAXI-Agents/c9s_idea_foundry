"""Multi-tenancy helpers for MongoDB query scoping.

Every repository function that reads or writes documents **must** use
``tenant_filter()`` or ``tenant_fields()`` to ensure data isolation.

Hierarchy (Decision 1 — Two-Level with Enterprise Override):

    Enterprise (corporate)
        └── Organization (division/subsidiary)
              └── Projects, Ideas, PRDs, etc.

Access rules:
    - ``SYS_ADMIN`` role → global access (system-level)
    - ``ENT_ADMIN`` role → see all orgs in their enterprise
    - ``USER`` role → see only their own organization's data
    - Background/system processes → pass ``TenantContext.system()`` to bypass

Strict isolation policy:
    - **Reads** with ``ctx=None`` return an impossible filter (no results).
    - **Writes** with ``ctx=None`` raise ``TenantWriteViolation``.
    - This prevents accidental cross-tenant data leaks.

A **regression test** (``tests/test_tenant_isolation.py``) ensures every
repository function includes tenant filtering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crewai_productfeature_planner.rbac import Role, resolve_role
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Sentinel value for system/background processes that need global access.
_SYSTEM_ENTERPRISE = "__system__"
_SYSTEM_ORG = "__system__"

# Impossible filter — used to block reads when no tenant context is provided.
_BLOCKED_FILTER: dict[str, Any] = {"enterprise_id": "__BLOCKED_NO_TENANT__"}


class TenantWriteViolation(Exception):
    """Raised when a write operation is attempted without tenant context.

    This is a security guard — writes MUST always carry tenant context
    so documents are properly scoped to an enterprise/organization.
    """


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Immutable tenant identity extracted from the authenticated user.

    Attributes:
        enterprise_id: Corporate parent ID (from JWT ``enterprise_id``).
        organization_id: Division/subsidiary ID (from JWT ``organization_id``).
        role: The effective RBAC role for this context.
    """

    enterprise_id: str
    organization_id: str
    role: Role = Role.USER

    @property
    def is_enterprise_admin(self) -> bool:
        """Backward-compatible property: True if role is ENT_ADMIN or SYS_ADMIN."""
        return self.role in (Role.ENT_ADMIN, Role.SYS_ADMIN)

    @property
    def is_sys_admin(self) -> bool:
        """True if the context has system-admin privileges."""
        return self.role == Role.SYS_ADMIN

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
        role = resolve_role(roles)
        return cls(
            enterprise_id=user.get("enterprise_id") or "",
            organization_id=user.get("organization_id") or "",
            role=role,
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
            role=Role.USER,
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
            role=Role.SYS_ADMIN,
        )

    # ------------------------------------------------------------------
    # Serialization (for flow state threading)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, str]:
        """Serialize to a plain dict for embedding in Pydantic models."""
        return {
            "enterprise_id": self.enterprise_id,
            "organization_id": self.organization_id,
            "role": self.role.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> TenantContext | None:
        """Reconstruct from a serialized dict.

        Returns ``None`` if data is empty or missing required fields.
        """
        if not data or "enterprise_id" not in data:
            return None
        return cls(
            enterprise_id=data["enterprise_id"],
            organization_id=data.get("organization_id", ""),
            role=Role(data["role"]) if "role" in data else Role.USER,
        )


def tenant_filter(ctx: TenantContext | None) -> dict[str, Any]:
    """Build a MongoDB query filter that enforces tenant isolation.

    Returns a filter dict to be merged (``{**tenant_filter(ctx), ...}``)
    or ``$and``-ed with additional query conditions.

    Access rules:
        - **None / no context** → impossible filter (blocks all reads)
        - **System context** → ``{}`` (no filter — global access)
        - **SYS_ADMIN** → ``{}`` (no filter — global access)
        - **ENT_ADMIN** → ``{"enterprise_id": ctx.enterprise_id}``
          (sees all orgs in their enterprise)
        - **USER** → ``{"organization_id": ctx.organization_id}``
          (sees only their own org)

    Args:
        ctx: The tenant context from the authenticated user, or None.

    Returns:
        A MongoDB filter dict for tenant scoping.
    """
    if ctx is None:
        logger.warning(
            "[Tenant] tenant_filter() called with None — returning blocked filter"
        )
        return dict(_BLOCKED_FILTER)

    # System / background processes — global access.
    if ctx.enterprise_id == _SYSTEM_ENTERPRISE:
        return {}

    # SYS_ADMIN — global access across all enterprises.
    if ctx.role == Role.SYS_ADMIN:
        return {}

    # ENT_ADMIN — sees all orgs under their enterprise.
    if ctx.role == Role.ENT_ADMIN and ctx.enterprise_id:
        return {"enterprise_id": ctx.enterprise_id}

    # Regular user — sees only their own org.
    if ctx.organization_id:
        return {"organization_id": ctx.organization_id}

    # Fallback: if enterprise_id is set but no org, scope to enterprise.
    if ctx.enterprise_id:
        return {"enterprise_id": ctx.enterprise_id}

    # No tenant info at all — block the read.
    logger.warning(
        "[Tenant] No enterprise_id or organization_id — returning blocked filter"
    )
    return dict(_BLOCKED_FILTER)


def tenant_fields(ctx: TenantContext | None) -> dict[str, str]:
    """Return the tenant fields to embed in a new document.

    Every ``insert_one`` or ``update_one`` (upsert) MUST include these
    fields so the document is properly scoped.

    Raises:
        TenantWriteViolation: If *ctx* is None — writes without tenant
            context are forbidden.

    Args:
        ctx: The tenant context from the authenticated user.

    Returns:
        A dict with ``enterprise_id`` and ``organization_id``.
    """
    if ctx is None:
        raise TenantWriteViolation(
            "tenant_fields() called with ctx=None — writes require tenant context. "
            "Pass TenantContext.system() for background processes."
        )
    return {
        "enterprise_id": ctx.enterprise_id,
        "organization_id": ctx.organization_id,
    }
