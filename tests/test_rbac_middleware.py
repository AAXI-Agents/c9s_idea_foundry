"""Tests for the RBAC middleware — require_role dependency factory.

Validates that the per-endpoint role gate:
- Allows users with an allowed role
- Rejects users without the allowed role (403)
- Handles multiple allowed roles
- Handles empty/missing roles claim
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from crewai_productfeature_planner.apis.admin_deps import (
    require_enterprise_admin,
    require_role,
    require_sys_admin,
)
from crewai_productfeature_planner.rbac import Role


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── require_role factory ──────────────────────────────────────


class TestRequireRoleFactory:
    """Tests for the generic require_role(*allowed_roles) factory."""

    @pytest.mark.asyncio
    async def test_allowed_role_passes(self):
        """User with an allowed role should not raise."""
        guard = require_role(Role.SYS_ADMIN, Role.ENT_ADMIN)

        user = {"user_id": "u1", "roles": ["ENT_ADMIN"], "enterprise_id": "e1"}

        with patch(
            "crewai_productfeature_planner.apis.admin_deps.require_sso_user",
            new_callable=AsyncMock,
            return_value=user,
        ):
            # Call the inner guard function directly
            result = await guard(user=user)
            assert result["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_disallowed_role_raises_403(self):
        """User without an allowed role should get 403."""
        guard = require_role(Role.SYS_ADMIN)

        user = {"user_id": "u2", "roles": ["USER"], "enterprise_id": "e1"}

        with pytest.raises(HTTPException) as exc_info:
            await guard(user=user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_roles_defaults_to_user(self):
        """Empty roles list resolves to USER — only passes if USER is allowed."""
        guard_admin = require_role(Role.SYS_ADMIN)
        guard_user = require_role(Role.USER, Role.ENT_ADMIN, Role.SYS_ADMIN)

        user = {"user_id": "u3", "roles": [], "enterprise_id": "e1"}

        # Should fail for admin-only
        with pytest.raises(HTTPException):
            await guard_admin(user=user)

        # Should pass for user-level
        result = await guard_user(user=user)
        assert result["user_id"] == "u3"

    @pytest.mark.asyncio
    async def test_multiple_roles_picks_highest(self):
        """User with multiple roles should have highest privilege checked."""
        guard = require_role(Role.ENT_ADMIN, Role.SYS_ADMIN)

        user = {"user_id": "u4", "roles": ["USER", "ENT_ADMIN"], "enterprise_id": "e1"}
        result = await guard(user=user)
        assert result["user_id"] == "u4"


# ── require_enterprise_admin ──────────────────────────────────


class TestRequireEnterpriseAdmin:
    """Tests for the require_enterprise_admin dependency."""

    @pytest.mark.asyncio
    async def test_ent_admin_passes(self):
        """ENT_ADMIN with enterprise_id should pass."""
        user = {"user_id": "u1", "roles": ["ENT_ADMIN"], "enterprise_id": "e1"}
        result = await require_enterprise_admin(user=user)
        assert result["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_sys_admin_passes(self):
        """SYS_ADMIN should also pass enterprise admin check."""
        user = {"user_id": "u1", "roles": ["SYS_ADMIN"], "enterprise_id": "e1"}
        result = await require_enterprise_admin(user=user)
        assert result["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_regular_user_rejected(self):
        """Regular USER should be rejected."""
        user = {"user_id": "u2", "roles": ["USER"], "enterprise_id": "e1"}
        with pytest.raises(HTTPException) as exc_info:
            await require_enterprise_admin(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_enterprise_id_rejected(self):
        """ENT_ADMIN without enterprise_id should be rejected."""
        user = {"user_id": "u3", "roles": ["ENT_ADMIN"], "enterprise_id": ""}
        with pytest.raises(HTTPException) as exc_info:
            await require_enterprise_admin(user=user)
        assert exc_info.value.status_code == 403


# ── require_sys_admin ─────────────────────────────────────────


class TestRequireSysAdmin:
    """Tests for the require_sys_admin dependency."""

    @pytest.mark.asyncio
    async def test_sys_admin_passes(self):
        """SYS_ADMIN should pass."""
        user = {"user_id": "u1", "roles": ["SYS_ADMIN"], "enterprise_id": "e1"}
        result = await require_sys_admin(user=user)
        assert result["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_ent_admin_rejected(self):
        """ENT_ADMIN should be rejected from sys_admin gate."""
        user = {"user_id": "u2", "roles": ["ENT_ADMIN"], "enterprise_id": "e1"}
        with pytest.raises(HTTPException) as exc_info:
            await require_sys_admin(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_user_rejected(self):
        """Regular USER should be rejected."""
        user = {"user_id": "u3", "roles": ["USER"], "enterprise_id": "e1"}
        with pytest.raises(HTTPException) as exc_info:
            await require_sys_admin(user=user)
        assert exc_info.value.status_code == 403
