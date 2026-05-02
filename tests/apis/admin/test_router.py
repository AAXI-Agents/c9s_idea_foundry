"""Tests for the admin router endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.apis.admin_deps import require_enterprise_admin
from crewai_productfeature_planner.apis.sso_auth import require_sso_user

_ASYNC_CLIENT = "crewai_productfeature_planner.mongodb.async_client"
_AUDIT_REPO = "crewai_productfeature_planner.mongodb.admin_audit_log"
_ADMIN_ROUTER = "crewai_productfeature_planner.apis.admin.router"


def _admin_user():
    """Simulate an enterprise admin user from require_sso_user."""
    return {
        "user_id": "admin-001",
        "email": "admin@example.com",
        "roles": ["admin", "enterprise_admin"],
        "app_id": "idea-foundry",
        "app_name": "Idea Foundry",
        "enterprise_id": "ent-abc",
        "organization_id": "org-001",
        "display_name": "Admin User",
    }


def _regular_user():
    """Simulate a regular (non-admin) user."""
    return {
        "user_id": "user-002",
        "email": "user@example.com",
        "roles": ["user"],
        "app_id": "idea-foundry",
        "app_name": "Idea Foundry",
        "enterprise_id": "ent-abc",
        "organization_id": "org-001",
        "display_name": "Regular User",
    }


@pytest.fixture()
def client():
    """TestClient with admin dependency overridden."""
    app.dependency_overrides[require_sso_user] = lambda: _admin_user()
    app.dependency_overrides[require_enterprise_admin] = lambda: _admin_user()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client_regular():
    """TestClient with a regular (non-admin) user — no overrides."""
    app.dependency_overrides[require_sso_user] = lambda: _regular_user()
    app.dependency_overrides.pop(require_enterprise_admin, None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Access control ────────────────────────────────────────────


class TestAdminAccessControl:
    """Verify enterprise_admin role is enforced."""

    def test_non_admin_gets_403(self, client_regular):
        """Regular users should get 403 on admin endpoints."""
        resp = client_regular.get("/admin/organizations")
        assert resp.status_code == 403

    def test_no_enterprise_id_gets_403(self):
        """Users with admin role but no enterprise_id should get 403."""
        user_no_ent = _admin_user()
        user_no_ent["enterprise_id"] = ""

        async def _no_ent_admin():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="No enterprise_id in token.")

        app.dependency_overrides[require_sso_user] = lambda: user_no_ent
        app.dependency_overrides.pop(require_enterprise_admin, None)
        try:
            with TestClient(app) as c:
                resp = c.get("/admin/organizations")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


# ── GET /admin/organizations ──────────────────────────────────


class TestListOrganizations:
    def _mock_collection(self, agg_results):
        coll = MagicMock()
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=agg_results)
        coll.aggregate.return_value = cursor
        return coll

    def test_returns_orgs(self, client):
        agg_results = [
            {"_id": "org-001", "organization_name": "Org One", "project_count": 3},
            {"_id": "org-002", "organization_name": "Org Two", "project_count": 1},
        ]
        coll = self._mock_collection(agg_results)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/admin/organizations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["items"][0]["organization_id"] == "org-001"
        assert body["items"][0]["project_count"] == 3

    def test_empty_enterprise(self, client):
        coll = self._mock_collection([])
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/admin/organizations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── GET /admin/projects ───────────────────────────────────────


class TestListAdminProjects:
    def _mock_collection(self, docs, total=None):
        if total is None:
            total = len(docs)
        coll = MagicMock()
        coll.count_documents = AsyncMock(return_value=total)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.to_list = AsyncMock(return_value=list(docs))
        coll.find.return_value = cursor
        return coll

    def test_returns_projects(self, client):
        docs = [
            {
                "project_id": "p1",
                "name": "Project 1",
                "description": "Desc",
                "organization_id": "org-001",
                "organization_name": "Org One",
                "enterprise_id": "ent-abc",
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
            }
        ]
        coll = self._mock_collection(docs, total=1)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/admin/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["project_id"] == "p1"

    def test_pagination(self, client):
        coll = self._mock_collection([], total=50)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/admin/projects?page=2&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 10

    def test_filter_by_org(self, client):
        coll = self._mock_collection([], total=0)
        with patch(f"{_ASYNC_CLIENT}.get_async_db") as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=coll)
            resp = client.get("/admin/projects?organization_id=org-002")
        assert resp.status_code == 200
        # Verify the query included the org filter
        call_args = coll.find.call_args
        assert call_args is not None


# ── GET /admin/projects/{id}/cascade-preview ──────────────────


class TestCascadePreview:
    def _mock_db(self, project_doc, ideas=0, jobs=0, reqs=0):
        """Build a mock async DB with separate collection mocks."""
        db = MagicMock()
        colls = {}

        # Project config collection
        project_coll = MagicMock()
        project_coll.find_one = AsyncMock(return_value=project_doc)
        colls["projectConfig"] = project_coll

        # Working ideas
        ideas_coll = MagicMock()
        ideas_coll.count_documents = AsyncMock(return_value=ideas)
        colls["workingIdeas"] = ideas_coll

        # Crew jobs
        jobs_coll = MagicMock()
        jobs_coll.count_documents = AsyncMock(return_value=jobs)
        colls["crewJobs"] = jobs_coll

        # Product requirements
        reqs_coll = MagicMock()
        reqs_coll.count_documents = AsyncMock(return_value=reqs)
        colls["productRequirements"] = reqs_coll

        db.__getitem__ = MagicMock(side_effect=lambda k: colls.get(k, MagicMock()))
        return db

    def test_preview_success(self, client):
        project = {
            "project_id": "p1",
            "name": "Test",
            "organization_id": "org-001",
            "organization_name": "Org One",
            "enterprise_id": "ent-abc",
        }
        db = self._mock_db(project, ideas=5, jobs=3, reqs=2)
        with patch(f"{_ASYNC_CLIENT}.get_async_db", return_value=db):
            resp = client.get("/admin/projects/p1/cascade-preview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["working_ideas_count"] == 5
        assert body["crew_jobs_count"] == 3
        assert body["product_requirements_count"] == 2
        assert body["total_documents"] == 10

    def test_not_found(self, client):
        db = self._mock_db(None)
        with patch(f"{_ASYNC_CLIENT}.get_async_db", return_value=db):
            resp = client.get("/admin/projects/nonexistent/cascade-preview")
        assert resp.status_code == 404


# ── PATCH /admin/projects/{id}/tenant ─────────────────────────


class TestReassignTenant:
    def _mock_db(self, project_doc):
        db = MagicMock()
        colls = {}

        # Project config
        project_coll = MagicMock()
        project_coll.find_one = AsyncMock(return_value=project_doc)
        project_coll.update_one = AsyncMock()
        colls["projectConfig"] = project_coll

        # Working ideas
        ideas_coll = MagicMock()
        ideas_coll.update_many = AsyncMock(return_value=MagicMock(modified_count=5))
        colls["workingIdeas"] = ideas_coll

        # Crew jobs
        jobs_coll = MagicMock()
        jobs_coll.update_many = AsyncMock(return_value=MagicMock(modified_count=3))
        colls["crewJobs"] = jobs_coll

        # Product requirements
        reqs_coll = MagicMock()
        reqs_coll.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
        colls["productRequirements"] = reqs_coll

        db.__getitem__ = MagicMock(side_effect=lambda k: colls.get(k, MagicMock()))
        return db

    def test_reassign_success(self, client):
        project = {
            "project_id": "p1",
            "name": "Test Project",
            "organization_id": "org-001",
            "organization_name": "Org One",
            "enterprise_id": "ent-abc",
        }
        db = self._mock_db(project)
        with (
            patch(f"{_ASYNC_CLIENT}.get_async_db", return_value=db),
            patch(
                f"{_AUDIT_REPO}.create_audit_entry",
                return_value={"audit_id": "aud-123"},
            ),
        ):
            resp = client.patch(
                "/admin/projects/p1/tenant",
                json={
                    "to_organization_id": "org-002",
                    "to_organization_name": "Org Two",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["from_organization_id"] == "org-001"
        assert body["to_organization_id"] == "org-002"
        assert body["cascaded_documents"] == 10
        assert body["audit_id"] == "aud-123"

    def test_same_org_returns_400(self, client):
        project = {
            "project_id": "p1",
            "name": "Test",
            "organization_id": "org-001",
            "enterprise_id": "ent-abc",
        }
        db = self._mock_db(project)
        with patch(f"{_ASYNC_CLIENT}.get_async_db", return_value=db):
            resp = client.patch(
                "/admin/projects/p1/tenant",
                json={"to_organization_id": "org-001"},
            )
        assert resp.status_code == 400

    def test_not_found(self, client):
        db = self._mock_db(None)
        with patch(f"{_ASYNC_CLIENT}.get_async_db", return_value=db):
            resp = client.patch(
                "/admin/projects/nonexistent/tenant",
                json={"to_organization_id": "org-002"},
            )
        assert resp.status_code == 404


# ── GET /admin/audit-log ──────────────────────────────────────


class TestAuditLog:
    def test_returns_entries(self, client):
        from datetime import datetime, timezone

        entries = [
            {
                "audit_id": "a1",
                "action": "project_reassignment",
                "actor_id": "admin-001",
                "actor_email": "admin@example.com",
                "project_id": "p1",
                "project_name": "Project 1",
                "from_organization_id": "org-001",
                "from_organization_name": "Org One",
                "to_organization_id": "org-002",
                "to_organization_name": "Org Two",
                "cascaded_documents": 10,
                "timestamp": datetime(2026, 4, 14, 10, 30, tzinfo=timezone.utc),
            }
        ]
        with patch(
            f"{_AUDIT_REPO}.list_audit_entries",
            return_value=(entries, 1),
        ):
            resp = client.get("/admin/audit-log")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "project_reassignment"

    def test_pagination_params(self, client):
        with patch(
            f"{_AUDIT_REPO}.list_audit_entries",
            return_value=([], 0),
        ):
            resp = client.get("/admin/audit-log?page=2&page_size=5&action=project_reassignment")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 5

    def test_action_filter(self, client):
        with patch(
            f"{_AUDIT_REPO}.list_audit_entries",
            return_value=([], 0),
        ) as mock_list:
            resp = client.get("/admin/audit-log?action=project_reassignment")
        assert resp.status_code == 200
        # Verify action filter was passed
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs["action"] == "project_reassignment"
