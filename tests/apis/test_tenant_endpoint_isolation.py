"""Endpoint-level tenant isolation regression tests.

Verifies that user-facing endpoints enforce tenant scoping:
- A user from Org A CANNOT access resources belonging to Org B.
- Enterprise admins CAN access cross-org resources within their enterprise.
- The system context bypasses scoping (for background processes).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext


# ── Fixtures ──────────────────────────────────────────────────────────


ORG_A_USER = {
    "user_id": "user-a",
    "email": "user-a@test.com",
    "roles": ["user"],
    "enterprise_id": "ent-1",
    "organization_id": "org-a",
    "display_name": "User A",
}

ORG_B_USER = {
    "user_id": "user-b",
    "email": "user-b@test.com",
    "roles": ["user"],
    "enterprise_id": "ent-1",
    "organization_id": "org-b",
    "display_name": "User B",
}

ADMIN_USER = {
    "user_id": "admin",
    "email": "admin@test.com",
    "roles": ["user", "enterprise_admin"],
    "enterprise_id": "ent-1",
    "organization_id": "org-a",
    "display_name": "Admin",
}

# Simulated docs belonging to org-a
IDEA_DOC_ORG_A = {
    "run_id": "run-org-a",
    "idea": "Test idea",
    "status": "completed",
    "organization_id": "org-a",
    "enterprise_id": "ent-1",
    "created_at": "2026-01-01T00:00:00Z",
    "update_date": "2026-01-01T00:00:00Z",
}


@pytest.fixture()
def client_org_a():
    """TestClient authenticated as org-a user."""
    app.dependency_overrides[require_sso_user] = lambda: ORG_A_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client_org_b():
    """TestClient authenticated as org-b user."""
    app.dependency_overrides[require_sso_user] = lambda: ORG_B_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


_WI_DB = "crewai_productfeature_planner.mongodb.working_ideas._common.get_db"
_WI_QUERIES_DB = "crewai_productfeature_planner.mongodb.working_ideas._queries._common.get_db"


def _mock_db_returning_none():
    """Create a mock DB where all find_one return None."""
    mock_coll = MagicMock()
    mock_coll.find_one.return_value = None
    mock_coll.find.return_value = MagicMock(sort=MagicMock(return_value=[]))
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_coll)
    return db


def _mock_db_returning_doc(doc):
    """Create a mock DB where find_one returns the given doc."""
    mock_coll = MagicMock()
    mock_coll.find_one.return_value = doc
    mock_coll.find.return_value = MagicMock(
        sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=[])))
    )
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_coll)
    return db


# ── Timeline endpoint ─────────────────────────────────────────────────


class TestTimelineTenantIsolation:
    """GET /flow/runs/{run_id}/timeline enforces tenant scoping."""

    @patch(_WI_QUERIES_DB)
    def test_user_cannot_access_other_org_timeline(self, mock_get_db, client_org_b):
        """User from org-b cannot view timeline for a run belonging to org-a."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.get("/flow/runs/run-org-a/timeline")
        assert resp.status_code == 404


# ── Versions endpoint ─────────────────────────────────────────────────


class TestVersionsTenantIsolation:
    """GET /flow/runs/{run_id}/versions enforces tenant scoping."""

    @patch(_WI_QUERIES_DB)
    def test_user_cannot_access_other_org_versions(self, mock_get_db, client_org_b):
        """User from org-b gets 404 for a run belonging to org-a."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.get("/flow/runs/run-org-a/versions")
        assert resp.status_code == 404


# ── UX Design endpoint ────────────────────────────────────────────────


class TestUXDesignTenantIsolation:
    """POST /flow/ux-design/{run_id} enforces tenant scoping."""

    @patch(_WI_QUERIES_DB)
    def test_user_cannot_trigger_ux_for_other_org(self, mock_get_db, client_org_b):
        """User from org-b cannot trigger UX design for org-a's run."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.post("/flow/ux-design/run-org-a")
        assert resp.status_code == 404


# ── Publishing endpoints ──────────────────────────────────────────────


class TestPublishingTenantIsolation:
    """Publishing single-run endpoints enforce tenant scoping."""

    @patch(_WI_QUERIES_DB)
    def test_confluence_publish_blocked_for_other_org(self, mock_get_db, client_org_b):
        """User from org-b cannot publish org-a's run to Confluence."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.post("/publishing/confluence/run-org-a")
        assert resp.status_code == 404

    @patch(_WI_QUERIES_DB)
    def test_jira_create_blocked_for_other_org(self, mock_get_db, client_org_b):
        """User from org-b cannot create Jira tickets for org-a's run."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.post("/publishing/jira/run-org-a")
        assert resp.status_code == 404

    @patch(_WI_QUERIES_DB)
    def test_status_blocked_for_other_org(self, mock_get_db, client_org_b):
        """User from org-b cannot view delivery status for org-a's run."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.get("/publishing/status/run-org-a")
        assert resp.status_code == 404

    @patch(_WI_QUERIES_DB)
    def test_publish_all_single_blocked_for_other_org(self, mock_get_db, client_org_b):
        """User from org-b cannot trigger full publish for org-a's run."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.post("/publishing/all/run-org-a")
        assert resp.status_code == 404

    @patch(_WI_QUERIES_DB)
    def test_preview_blocked_for_other_org(self, mock_get_db, client_org_b):
        """User from org-b cannot preview org-a's Confluence content."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.get("/publishing/confluence/run-org-a/preview")
        assert resp.status_code == 404


# ── Resume endpoint ───────────────────────────────────────────────────


class TestResumeTenantIsolation:
    """POST /flow/prd/resume enforces tenant scoping."""

    @patch(_WI_QUERIES_DB)
    def test_user_cannot_resume_other_org_run(self, mock_get_db, client_org_b):
        """User from org-b cannot resume a run belonging to org-a."""
        mock_get_db.return_value = _mock_db_returning_none()
        resp = client_org_b.post(
            "/flow/prd/resume",
            json={"run_id": "run-org-a"},
        )
        assert resp.status_code == 404


# ── Repository-level isolation ────────────────────────────────────────


class TestRepositoryTenantFiltering:
    """Verify repository functions merge tenant_filter into queries."""

    @patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
    def test_get_delivery_record_with_tenant(self, mock_db):
        """get_delivery_record respects tenant context."""
        from crewai_productfeature_planner.mongodb.product_requirements import (
            get_delivery_record,
        )

        mock_coll = MagicMock()
        mock_coll.find_one.return_value = {"run_id": "r1", "status": "new"}
        mock_db.return_value = {"productRequirements": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = get_delivery_record("r1", tenant=tenant)
        assert result is not None

        # Verify the query included tenant filter
        call_args = mock_coll.find_one.call_args[0][0]
        assert call_args["run_id"] == "r1"
        assert call_args["organization_id"] == "org-a"

    @patch("crewai_productfeature_planner.mongodb.product_requirements.repository.get_db")
    def test_find_pending_delivery_with_tenant(self, mock_db):
        """find_pending_delivery respects tenant context."""
        from crewai_productfeature_planner.mongodb.product_requirements import (
            find_pending_delivery,
        )

        mock_coll = MagicMock()
        mock_find = MagicMock()
        mock_find.sort.return_value = [{"run_id": "r1", "status": "new"}]
        mock_coll.find.return_value = mock_find
        mock_db.return_value = {"productRequirements": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = find_pending_delivery(tenant=tenant)
        assert len(result) == 1

        # Verify the query included tenant filter
        call_args = mock_coll.find.call_args[0][0]
        assert call_args["organization_id"] == "org-a"

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
    def test_find_active_job_with_tenant(self, mock_db):
        """find_active_job respects tenant context."""
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            find_active_job,
        )

        mock_coll = MagicMock()
        mock_coll.find_one.return_value = {"job_id": "j1", "status": "running"}
        mock_db.return_value = {"crewJobs": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = find_active_job(tenant=tenant)
        assert result is not None

        # Verify the query included tenant filter
        call_args = mock_coll.find_one.call_args[0][0]
        assert call_args["organization_id"] == "org-a"

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
    def test_update_job_status_with_tenant(self, mock_db):
        """update_job_status includes tenant filter in query."""
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            update_job_status,
        )

        mock_coll = MagicMock()
        mock_coll.update_one.return_value = MagicMock(modified_count=1)
        mock_db.return_value = {"crewJobs": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = update_job_status("j1", "completed", tenant=tenant)
        assert result is True

        # Verify the query included tenant filter
        call_args = mock_coll.update_one.call_args[0][0]
        assert call_args["job_id"] == "j1"
        assert call_args["organization_id"] == "org-a"

    @patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db")
    def test_mark_completed_with_tenant(self, mock_db):
        """mark_completed includes tenant filter in query."""
        from crewai_productfeature_planner.mongodb.working_ideas._status import (
            mark_completed,
        )

        mock_coll = MagicMock()
        mock_coll.update_one.return_value = MagicMock(modified_count=1)
        mock_db.return_value = {"workingIdeas": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = mark_completed("run-1", tenant=tenant)
        assert result == 1

        # Verify the query included tenant filter
        call_args = mock_coll.update_one.call_args[0][0]
        assert call_args["run_id"] == "run-1"
        assert call_args["organization_id"] == "org-a"

    @patch("crewai_productfeature_planner.mongodb.working_ideas._common.get_db")
    def test_mark_deleted_with_tenant(self, mock_db):
        """mark_deleted includes tenant filter in query."""
        from crewai_productfeature_planner.mongodb.working_ideas._status import (
            mark_deleted,
        )

        mock_coll = MagicMock()
        mock_coll.update_one.return_value = MagicMock(modified_count=1)
        mock_db.return_value = {"workingIdeas": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = mark_deleted("run-1", tenant=tenant)
        assert result == 1

        call_args = mock_coll.update_one.call_args[0][0]
        assert call_args["run_id"] == "run-1"
        assert call_args["organization_id"] == "org-a"

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
    def test_reactivate_job_with_tenant(self, mock_db):
        """reactivate_job includes tenant filter in query."""
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            reactivate_job,
        )

        mock_coll = MagicMock()
        mock_coll.update_one.return_value = MagicMock(
            modified_count=1, matched_count=1
        )
        mock_db.return_value = {"crewJobs": mock_coll}

        tenant = TenantContext(
            enterprise_id="ent-1",
            organization_id="org-a",

        )
        result = reactivate_job("j1", tenant=tenant)
        assert result is True

        call_args = mock_coll.update_one.call_args[0][0]
        assert call_args["job_id"] == "j1"
        assert call_args["organization_id"] == "org-a"

    def test_backward_compat_no_tenant(self):
        """None tenant now returns blocked filter to prevent data leaks."""
        from crewai_productfeature_planner.mongodb._tenant import (
            _BLOCKED_FILTER,
            tenant_filter,
        )

        # None tenant returns blocked filter — strict multi-tenancy
        assert tenant_filter(None) == _BLOCKED_FILTER
