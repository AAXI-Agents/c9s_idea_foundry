"""Regression tests for multi-tenancy data isolation.

Verifies that:
1. ``TenantContext`` factory methods produce correct contexts
2. ``tenant_filter()`` returns correct MongoDB query filters
3. ``tenant_fields()`` returns correct document fields
4. ``tenant_filter(None)`` returns empty dict (backward compat)
"""

from __future__ import annotations

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    _SYSTEM_ENTERPRISE,
    _SYSTEM_ORG,
    tenant_fields,
    tenant_filter,
)


# ── TenantContext.from_user ───────────────────────────────────


class TestFromUser:
    def test_regular_user(self):
        user = {
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
            "roles": ["user"],
        }
        ctx = TenantContext.from_user(user)
        assert ctx.enterprise_id == "ent-1"
        assert ctx.organization_id == "org-1"
        assert ctx.is_enterprise_admin is False

    def test_enterprise_admin(self):
        user = {
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
            "roles": ["user", "enterprise_admin"],
        }
        ctx = TenantContext.from_user(user)
        assert ctx.is_enterprise_admin is True

    def test_missing_fields(self):
        ctx = TenantContext.from_user({})
        assert ctx.enterprise_id == ""
        assert ctx.organization_id == ""
        assert ctx.is_enterprise_admin is False

    def test_none_roles(self):
        ctx = TenantContext.from_user({"roles": None})
        assert ctx.is_enterprise_admin is False


# ── TenantContext.from_slack_install ──────────────────────────


class TestFromSlackInstall:
    def test_basic(self):
        install = {"enterprise_id": "ent-2", "organization_id": "org-2"}
        ctx = TenantContext.from_slack_install(install)
        assert ctx.enterprise_id == "ent-2"
        assert ctx.organization_id == "org-2"
        assert ctx.is_enterprise_admin is False

    def test_missing_fields(self):
        ctx = TenantContext.from_slack_install({})
        assert ctx.enterprise_id == ""
        assert ctx.organization_id == ""


# ── TenantContext.system ──────────────────────────────────────


class TestSystemContext:
    def test_system_sentinel(self):
        ctx = TenantContext.system()
        assert ctx.enterprise_id == _SYSTEM_ENTERPRISE
        assert ctx.organization_id == _SYSTEM_ORG


# ── tenant_filter ─────────────────────────────────────────────


class TestTenantFilter:
    def test_none_returns_empty(self):
        assert tenant_filter(None) == {}

    def test_system_returns_empty(self):
        ctx = TenantContext.system()
        assert tenant_filter(ctx) == {}

    def test_regular_user_scopes_by_org(self):
        ctx = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-1",
            is_enterprise_admin=False,
        )
        assert tenant_filter(ctx) == {"organization_id": "org-1"}

    def test_enterprise_admin_scopes_by_enterprise(self):
        ctx = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-1",
            is_enterprise_admin=True,
        )
        assert tenant_filter(ctx) == {"enterprise_id": "ent-1"}

    def test_no_org_falls_back_to_enterprise(self):
        ctx = TenantContext(
            enterprise_id="ent-1",
            organization_id="",
            is_enterprise_admin=False,
        )
        assert tenant_filter(ctx) == {"enterprise_id": "ent-1"}

    def test_no_tenant_info_returns_empty(self):
        ctx = TenantContext(
            enterprise_id="",
            organization_id="",
            is_enterprise_admin=False,
        )
        assert tenant_filter(ctx) == {}


# ── tenant_fields ─────────────────────────────────────────────


class TestTenantFields:
    def test_returns_both_fields(self):
        ctx = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-1",
        )
        fields = tenant_fields(ctx)
        assert fields == {
            "enterprise_id": "ent-1",
            "organization_id": "org-1",
        }

    def test_none_returns_empty(self):
        assert tenant_fields(None) == {}
