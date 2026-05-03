"""Role-Based Access Control (RBAC) definitions.

Centralised role enum used across auth dependencies, tenant filtering,
and permission checks.  Roles are expected to arrive as string values
in the JWT ``roles`` claim issued by the SSO service.

Role hierarchy:
    SYS_ADMIN > ENT_ADMIN > USER

Access scope per role:
    - SYS_ADMIN: System-wide — manages platform settings, sees all enterprises.
    - ENT_ADMIN: Enterprise-scoped — manages enterprise settings, sees all orgs.
    - USER: Organization-scoped — sees only their own org's data.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Platform roles issued by the SSO service in the JWT ``roles`` claim."""

    SYS_ADMIN = "SYS_ADMIN"
    """Platform operator — manages system settings (e.g. PRD seed config)."""

    ENT_ADMIN = "ENT_ADMIN"
    """Enterprise administrator — manages enterprise settings, all orgs."""

    USER = "USER"
    """Regular user — org-scoped data access."""


def resolve_role(roles: list[str] | None) -> Role:
    """Determine the effective role from a list of JWT role strings.

    Picks the highest-privilege role present in the list.  Falls back
    to ``Role.USER`` if the list is empty or contains no known roles.

    Supports legacy role names for backward compatibility:
        - ``"enterprise_admin"`` → ``Role.ENT_ADMIN``
        - ``"system_admin"`` / ``"admin"`` → ``Role.SYS_ADMIN``

    Args:
        roles: The ``roles`` claim from the JWT (list of strings).

    Returns:
        The highest-privilege ``Role`` found.
    """
    if not roles:
        return Role.USER

    role_set = set(roles)

    # Direct matches (new JWT format)
    if Role.SYS_ADMIN in role_set:
        return Role.SYS_ADMIN
    if Role.ENT_ADMIN in role_set:
        return Role.ENT_ADMIN

    # Legacy role mappings (backward compat with existing JWT tokens)
    if "system_admin" in role_set or "admin" in role_set:
        return Role.SYS_ADMIN
    if "enterprise_admin" in role_set:
        return Role.ENT_ADMIN

    return Role.USER
