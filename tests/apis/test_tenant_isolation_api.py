"""Cross-tenant isolation regression tests for PRD REST + WebSocket.

These tests prove that:

1.  In-memory ``FlowRun`` objects carry the originating user's
    ``enterprise_id``/``organization_id`` and are not visible to other
    tenants via REST endpoints (404 — never 403, to avoid leaking
    existence).
2.  The PRD WebSocket rejects connections that do not authenticate or
    that target a run owned by a different tenant.
3.  The Slack OAuth signed-state helpers round-trip a tenant and reject
    tampered/expired payloads.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.shared import (
    FlowRun,
    FlowStatus,
    run_visible_to_tenant,
    runs,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    # Disable SSO so REST/WS auth helpers return synthetic users when no
    # token is supplied — individual tests that need real auth will set
    # SSO_ENABLED themselves.
    monkeypatch.delenv("SSO_ENABLED", raising=False)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_runs():
    runs.clear()
    yield
    runs.clear()


@pytest.fixture(autouse=True)
def _disable_poll_loop():
    import crewai_productfeature_planner.apis.prd._route_websocket as ws_mod

    ws_mod._enable_poll_loop = False
    yield
    ws_mod._enable_poll_loop = True


def _ent_a_user() -> dict:
    return {
        "user_id": "user-a",
        "enterprise_id": "ent-A",
        "organization_id": "org-A1",
        "roles": ["USER"],
    }


def _ent_b_user() -> dict:
    return {
        "user_id": "user-b",
        "enterprise_id": "ent-B",
        "organization_id": "org-B1",
        "roles": ["USER"],
    }


# ── run_visible_to_tenant unit tests ──────────────────────────


class TestRunVisibleToTenant:
    def test_legacy_run_without_tenant_is_invisible_to_users(self):
        run = FlowRun(run_id="legacy", flow_name="prd")
        # No tenant fields on this run.
        tenant = TenantContext.from_user(_ent_a_user())
        assert run_visible_to_tenant(run, tenant) is False

    def test_user_sees_own_org(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A1",
        )
        tenant = TenantContext.from_user(_ent_a_user())
        assert run_visible_to_tenant(run, tenant) is True

    def test_user_blocked_from_other_org_same_enterprise(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A2",
        )
        tenant = TenantContext.from_user(_ent_a_user())
        assert run_visible_to_tenant(run, tenant) is False

    def test_user_blocked_from_other_enterprise(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-B",
            organization_id="org-B1",
        )
        tenant = TenantContext.from_user(_ent_a_user())
        assert run_visible_to_tenant(run, tenant) is False

    def test_ent_admin_sees_all_orgs_in_enterprise(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A2",
        )
        admin = {
            "user_id": "admin-a",
            "enterprise_id": "ent-A",
            "organization_id": "org-A1",
            "roles": ["ENT_ADMIN"],
        }
        tenant = TenantContext.from_user(admin)
        assert run_visible_to_tenant(run, tenant) is True

    def test_ent_admin_blocked_from_other_enterprise(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-B",
            organization_id="org-B1",
        )
        admin = {
            "user_id": "admin-a",
            "enterprise_id": "ent-A",
            "organization_id": "org-A1",
            "roles": ["ENT_ADMIN"],
        }
        tenant = TenantContext.from_user(admin)
        assert run_visible_to_tenant(run, tenant) is False

    def test_sys_admin_sees_everything(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-Z",
            organization_id="org-Z9",
        )
        sysadmin = {
            "user_id": "root",
            "enterprise_id": "ent-A",
            "organization_id": "org-A1",
            "roles": ["SYS_ADMIN"],
        }
        tenant = TenantContext.from_user(sysadmin)
        assert run_visible_to_tenant(run, tenant) is True

    def test_system_context_sees_everything(self):
        run = FlowRun(
            run_id="r1",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A1",
        )
        assert run_visible_to_tenant(run, TenantContext.system()) is True


# ── PRD REST cross-tenant rejection ───────────────────────────


class TestPrdRestCrossTenantRejection:
    def _seed_run(self, tenant_ent: str, tenant_org: str) -> str:
        run = FlowRun(
            run_id="rest-1",
            flow_name="prd",
            enterprise_id=tenant_ent,
            organization_id=tenant_org,
        )
        run.status = FlowStatus.RUNNING
        runs[run.run_id] = run
        return run.run_id

    def test_get_run_status_blocks_cross_tenant(self, client, monkeypatch):
        from crewai_productfeature_planner.apis.sso_auth import require_sso_user

        run_id = self._seed_run("ent-A", "org-A1")

        app.dependency_overrides[require_sso_user] = lambda: _ent_b_user()
        try:
            with patch(
                "crewai_productfeature_planner.apis.prd.router.find_job",
                return_value=None,
            ):
                resp = client.get(f"/flow/runs/{run_id}")
        finally:
            app.dependency_overrides.pop(require_sso_user, None)
        assert resp.status_code == 404


# ── PRD WebSocket cross-tenant rejection ──────────────────────


class TestPrdWebSocketTenantIsolation:
    def test_ws_rejects_other_tenant(self, client, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        run = FlowRun(
            run_id="ws-x",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A1",
        )
        run.status = FlowStatus.RUNNING
        runs[run.run_id] = run

        monkeypatch.setenv("SSO_ENABLED", "true")

        async def _fake_introspect(_token: str):
            return _ent_b_user()

        with patch(
            "crewai_productfeature_planner.apis.sso_auth._introspect_remotely",
            new=_fake_introspect,
        ), patch(
            "crewai_productfeature_planner.mongodb.crew_jobs.find_job",
            return_value=None,
        ):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    "/flow/runs/ws-x/ws?token=fake-jwt"
                ) as ws:
                    ws.receive_json()
        assert exc_info.value.code == 4004

    def test_ws_rejects_missing_token_when_sso_enabled(self, client, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        run = FlowRun(
            run_id="ws-y",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A1",
        )
        runs[run.run_id] = run

        monkeypatch.setenv("SSO_ENABLED", "true")

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/flow/runs/ws-y/ws") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4001

    def test_ws_accepts_owner(self, client, monkeypatch):
        run = FlowRun(
            run_id="ws-z",
            flow_name="prd",
            enterprise_id="ent-A",
            organization_id="org-A1",
        )
        run.status = FlowStatus.RUNNING
        runs[run.run_id] = run

        monkeypatch.setenv("SSO_ENABLED", "true")

        async def _fake_introspect(_token: str):
            return _ent_a_user()

        with patch(
            "crewai_productfeature_planner.apis.sso_auth._introspect_remotely",
            new=_fake_introspect,
        ):
            with client.websocket_connect(
                "/flow/runs/ws-z/ws?token=fake-jwt"
            ) as ws:
                msg = ws.receive_json()
        assert msg["type"] == "status_update"
        assert msg["run_id"] == "ws-z"


# ── Slack OAuth signed-state ──────────────────────────────────


class TestSlackOAuthSignedState:
    @pytest.fixture(autouse=True)
    def _set_secret(self, monkeypatch):
        monkeypatch.setenv("SLACK_OAUTH_STATE_SECRET", "test-secret-xyz")

    def test_round_trip(self):
        from crewai_productfeature_planner.apis.slack.oauth_router import (
            sign_install_state,
            verify_install_state,
        )

        tenant = TenantContext.from_user(_ent_a_user())
        state = sign_install_state(tenant)
        verified = verify_install_state(state)
        assert verified is not None
        assert verified.enterprise_id == "ent-A"
        assert verified.organization_id == "org-A1"

    def test_tampered_payload_rejected(self):
        from crewai_productfeature_planner.apis.slack.oauth_router import (
            sign_install_state,
            verify_install_state,
            _b64url_encode,
        )
        import json

        tenant = TenantContext.from_user(_ent_a_user())
        state = sign_install_state(tenant)
        _, sig = state.split(".", 1)
        # Re-sign would require the secret; substitute a different payload
        # but keep the original signature → must fail HMAC check.
        evil_payload = _b64url_encode(
            json.dumps({"e": "ent-B", "o": "org-B1", "exp": int(time.time()) + 60},
                       separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        evil_state = f"{evil_payload}.{sig}"
        assert verify_install_state(evil_state) is None

    def test_expired_state_rejected(self, monkeypatch):
        from crewai_productfeature_planner.apis.slack.oauth_router import (
            sign_install_state,
            verify_install_state,
        )

        tenant = TenantContext.from_user(_ent_a_user())
        state = sign_install_state(tenant, ttl=-1)  # already expired
        assert verify_install_state(state) is None

    def test_missing_state_rejected(self):
        from crewai_productfeature_planner.apis.slack.oauth_router import (
            verify_install_state,
        )
        assert verify_install_state("") is None
        assert verify_install_state("garbage") is None
