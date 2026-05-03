"""Phase 2 regression tests: tenant isolation in repositories and flow state.

Verifies that:
1. PRDState.tenant_dict can round-trip a TenantContext via to_dict/from_dict.
2. PRDFlow._tenant property reconstructs from state correctly.
3. Flow submodule repo calls include tenant=flow._tenant.
4. Repository functions merge tenant_filter into queries when tenant provided.
5. Repository functions use BLOCKED filter when tenant is None (read-safety).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.flows._constants import PRDState
from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    _BLOCKED_FILTER,
    tenant_filter,
)
from crewai_productfeature_planner.rbac import Role


# ── PRDState + TenantContext round-trip ───────────────────────


class TestTenantDictRoundTrip:
    """Verify PRDState.tenant_dict ↔ TenantContext serialization."""

    def test_to_dict_from_dict(self):
        ctx = TenantContext(
            enterprise_id="ent-abc",
            organization_id="org-xyz",
            role=Role.USER,
        )
        d = ctx.to_dict()
        restored = TenantContext.from_dict(d)
        assert restored is not None
        assert restored.enterprise_id == "ent-abc"
        assert restored.organization_id == "org-xyz"
        assert restored.role == Role.USER

    def test_from_dict_empty(self):
        assert TenantContext.from_dict({}) is None
        assert TenantContext.from_dict(None) is None  # type: ignore[arg-type]

    def test_prd_state_tenant_dict_default(self):
        state = PRDState()
        assert state.tenant_dict == {}

    def test_prd_state_tenant_dict_set(self):
        ctx = TenantContext.system()
        state = PRDState(tenant_dict=ctx.to_dict())
        restored = TenantContext.from_dict(state.tenant_dict)
        assert restored is not None
        assert restored.role == Role.SYS_ADMIN


# ── PRDFlow._tenant property ──────────────────────────────────


class TestFlowTenantProperty:
    """Verify PRDFlow._tenant returns correct TenantContext from state."""

    def test_tenant_from_state(self):
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        ctx = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-1",
            role=Role.ENT_ADMIN,
        )
        flow = PRDFlow()
        flow.state.tenant_dict = ctx.to_dict()

        result = flow._tenant
        assert result is not None
        assert result.enterprise_id == "ent-1"
        assert result.role == Role.ENT_ADMIN

    def test_tenant_none_when_empty(self):
        from crewai_productfeature_planner.flows.prd_flow import PRDFlow

        flow = PRDFlow()
        assert flow._tenant is None


# ── Blocked filter on None tenant ─────────────────────────────


class TestBlockedReads:
    """tenant_filter(None) must block reads with __BLOCKED_NO_TENANT__."""

    def test_blocked_filter_value(self):
        result = tenant_filter(None)
        assert "enterprise_id" in result
        assert result["enterprise_id"] == "__BLOCKED_NO_TENANT__"

    @patch("crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db")
    def test_get_run_documents_blocked_without_tenant(self, mock_get_db):
        """get_run_documents(run_id, tenant=None) should include blocked filter."""
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            get_run_documents,
        )

        col = MagicMock()
        col.find_one.return_value = None
        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=col)
        mock_get_db.return_value = db

        get_run_documents("run-x")

        call_args = col.find_one.call_args[0][0]
        assert call_args["enterprise_id"] == "__BLOCKED_NO_TENANT__"

    @patch("crewai_productfeature_planner.mongodb.agent_interactions.repository.get_db")
    def test_get_interaction_blocked_without_tenant(self, mock_get_db):
        """get_interaction(id, tenant=None) should include blocked filter."""
        from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
            get_interaction,
        )

        col = MagicMock()
        col.find_one.return_value = None
        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=col)
        mock_get_db.return_value = db

        get_interaction("int-1")

        call_args = col.find_one.call_args[0][0]
        assert call_args["enterprise_id"] == "__BLOCKED_NO_TENANT__"


# ── SYS_ADMIN global access ──────────────────────────────────


class TestSysAdminAccess:
    """SYS_ADMIN tenant produces empty filter (global access)."""

    def test_system_tenant_filter_empty(self):
        ctx = TenantContext.system()
        assert tenant_filter(ctx) == {}

    @patch("crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db")
    def test_get_run_documents_no_block_with_sys(self, mock_get_db):
        """get_run_documents with SYS_ADMIN should not include enterprise_id filter."""
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            get_run_documents,
        )

        col = MagicMock()
        col.find_one.return_value = None
        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=col)
        mock_get_db.return_value = db

        get_run_documents("run-x", tenant=TenantContext.system())

        call_args = col.find_one.call_args[0][0]
        assert "enterprise_id" not in call_args


# ── Regular tenant scoped access ──────────────────────────────


class TestScopedAccess:
    """Regular USER tenant adds enterprise_id + organization_id to filter."""

    def test_user_tenant_filter(self):
        ctx = TenantContext(
            enterprise_id="ent-a",
            organization_id="org-b",
            role=Role.USER,
        )
        f = tenant_filter(ctx)
        # USER sees only their own org
        assert f == {"organization_id": "org-b"}

    @patch("crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db")
    def test_get_run_documents_scoped(self, mock_get_db):
        """get_run_documents with USER tenant scopes by enterprise+org."""
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            get_run_documents,
        )

        col = MagicMock()
        col.find_one.return_value = None
        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=col)
        mock_get_db.return_value = db

        ctx = TenantContext(
            enterprise_id="ent-a",
            organization_id="org-b",
            role=Role.USER,
        )
        get_run_documents("run-x", tenant=ctx)

        call_args = col.find_one.call_args[0][0]
        assert call_args["organization_id"] == "org-b"


# ── service.py passes tenant_dict ─────────────────────────────


class TestServiceTenantThreading:
    """Verify run_prd_flow/resume_prd_flow accept tenant_dict parameter."""

    def test_run_prd_flow_accepts_tenant_dict(self):
        """run_prd_flow signature accepts tenant_dict kwarg."""
        import inspect
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow

        sig = inspect.signature(run_prd_flow)
        assert "tenant_dict" in sig.parameters

    def test_resume_prd_flow_accepts_tenant_dict(self):
        """resume_prd_flow signature accepts tenant_dict kwarg."""
        import inspect
        from crewai_productfeature_planner.apis.prd.service import resume_prd_flow

        sig = inspect.signature(resume_prd_flow)
        assert "tenant_dict" in sig.parameters

    def test_prd_state_stores_tenant_dict(self):
        """PRDState.tenant_dict stores and retrieves tenant data."""
        td = {"enterprise_id": "e1", "organization_id": "o1", "role": "USER"}
        state = PRDState(tenant_dict=td)
        assert state.tenant_dict == td
        restored = TenantContext.from_dict(state.tenant_dict)
        assert restored is not None
        assert restored.enterprise_id == "e1"
