"""Tests for admin_deps — require_enterprise_admin and resolve_tenant_context."""

import pytest

from crewai_productfeature_planner.apis.admin_deps import (
    require_enterprise_admin,
    resolve_tenant_context,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext


class TestRequireEnterpriseAdmin:
    """Unit tests for the require_enterprise_admin dependency."""

    @pytest.mark.asyncio
    async def test_admin_passes(self):
        user = {
            "user_id": "u1",
            "email": "admin@test.com",
            "roles": ["enterprise_admin"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }
        result = await require_enterprise_admin(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        from fastapi import HTTPException

        user = {
            "user_id": "u2",
            "email": "user@test.com",
            "roles": ["user"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }
        with pytest.raises(HTTPException) as exc_info:
            await require_enterprise_admin(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_without_enterprise_id_raises_403(self):
        from fastapi import HTTPException

        user = {
            "user_id": "u3",
            "email": "admin@test.com",
            "roles": ["enterprise_admin"],
            "enterprise_id": "",
            "organization_id": "org-1",
        }
        with pytest.raises(HTTPException) as exc_info:
            await require_enterprise_admin(user)
        assert exc_info.value.status_code == 403


class TestResolveTenantContext:
    """Unit tests for the resolve_tenant_context helper."""

    def test_regular_user_ignores_org_param(self):
        """Non-admins should have organization_id param ignored."""
        user = {
            "user_id": "u1",
            "roles": ["user"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }
        ctx = resolve_tenant_context(user, organization_id="org-OTHER")
        # Should use the user's own org, not the param
        assert ctx.organization_id == "org-1"
        assert ctx.is_enterprise_admin is False

    def test_admin_without_override_gets_enterprise_scope(self):
        """Enterprise admins without org param see all orgs (enterprise-level)."""
        user = {
            "user_id": "u1",
            "roles": ["enterprise_admin"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }
        ctx = resolve_tenant_context(user, organization_id=None)
        # Should be enterprise-scoped via is_enterprise_admin
        assert ctx.enterprise_id == "ent-1"
        assert ctx.is_enterprise_admin is True

    def test_admin_with_org_override(self):
        """Enterprise admins with org param get org-level scope."""
        user = {
            "user_id": "u1",
            "roles": ["enterprise_admin"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }
        ctx = resolve_tenant_context(user, organization_id="org-002")
        # Should scope to the specific org (not enterprise-wide)
        assert ctx.organization_id == "org-002"
        assert ctx.enterprise_id == "ent-1"
        assert ctx.is_enterprise_admin is False  # Acts as org scope

    def test_admin_empty_string_org_treated_as_none(self):
        """Empty string org_id should behave like None (enterprise scope)."""
        user = {
            "user_id": "u1",
            "roles": ["enterprise_admin"],
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }
        ctx = resolve_tenant_context(user, organization_id="")
        # Empty string is falsy, so should default to enterprise scope
        assert ctx.is_enterprise_admin is True
