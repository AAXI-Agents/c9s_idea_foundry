"""Tests for the Publishing API router endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ── GET /publishing/pending ──────────────────────────────────────────


class TestListPending:
    def test_empty_list(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.list_pending_prds",
            return_value=[],
        ):
            resp = client.get("/publishing/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["items"] == []

    def test_with_items(self, client):
        items = [
            {
                "run_id": "abc123",
                "title": "PRD — fitness app",
                "source": "mongodb",
                "output_file": "",
                "confluence_published": False,
                "confluence_url": "",
                "jira_completed": False,
                "jira_tickets": [],
                "status": "pending",
            },
        ]
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.list_pending_prds",
            return_value=items,
        ):
            resp = client.get("/publishing/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["items"][0]["run_id"] == "abc123"

    def test_internal_error(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.list_pending_prds",
            side_effect=RuntimeError("db down"),
        ):
            resp = client.get("/publishing/pending")
        assert resp.status_code == 500


# ── POST /publishing/confluence/all ──────────────────────────────────


class TestPublishConfluenceAll:
    def test_success(self, client):
        result = {
            "published": 1,
            "failed": 0,
            "results": [
                {
                    "run_id": "abc123",
                    "title": "PRD — test",
                    "url": "https://example.atlassian.net/wiki/page/123",
                    "page_id": "123",
                    "action": "created",
                }
            ],
            "errors": [],
        }
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.publish_confluence_all",
            return_value=result,
        ):
            resp = client.post("/publishing/confluence/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["published"] == 1

    def test_no_credentials(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.publish_confluence_all",
            side_effect=RuntimeError("Confluence credentials are not configured"),
        ):
            resp = client.post("/publishing/confluence/all")
        assert resp.status_code == 503


# ── POST /publishing/confluence/{run_id} ─────────────────────────────


class TestPublishConfluenceSingle:
    def test_success(self, client):
        result = {
            "run_id": "abc123",
            "title": "PRD — test",
            "url": "https://example.atlassian.net/wiki/page/123",
            "page_id": "123",
            "action": "created",
        }
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.publish_confluence_single",
            return_value=result,
        ):
            resp = client.post("/publishing/confluence/abc123")
        assert resp.status_code == 200
        assert resp.json()["url"] == result["url"]

    def test_not_found(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.publish_confluence_single",
            side_effect=ValueError("No unpublished PRD found"),
        ):
            resp = client.post("/publishing/confluence/bad_id")
        assert resp.status_code == 404


# ── POST /publishing/jira/all ────────────────────────────────────────


class TestCreateJiraAll:
    def test_success(self, client):
        result = {
            "completed": 1,
            "failed": 0,
            "results": [
                {"run_id": "abc123", "jira_completed": True, "ticket_keys": ["PROJ-1"], "progress": []}
            ],
            "errors": [],
        }
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.create_jira_all",
            return_value=result,
        ):
            resp = client.post("/publishing/jira/all")
        assert resp.status_code == 200
        assert resp.json()["completed"] == 1


# ── POST /publishing/jira/{run_id} ──────────────────────────────────


class TestCreateJiraSingle:
    def test_not_found(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.create_jira_single",
            side_effect=ValueError("No pending delivery found"),
        ):
            resp = client.post("/publishing/jira/bad_id")
        assert resp.status_code == 404


# ── POST /publishing/all ─────────────────────────────────────────────


class TestPublishAll:
    def test_success(self, client):
        result = {
            "confluence": {"published": 1, "failed": 0, "results": [], "errors": []},
            "jira": {"completed": 0, "failed": 0, "results": [], "errors": []},
        }
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.publish_all_and_create_tickets",
            return_value=result,
        ):
            resp = client.post("/publishing/all")
        assert resp.status_code == 200


# ── POST /publishing/all/{run_id} ───────────────────────────────────


class TestPublishAllSingle:
    def test_not_found(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.publish_and_create_tickets",
            side_effect=ValueError("No deliverable content"),
        ):
            resp = client.post("/publishing/all/bad_id")
        assert resp.status_code == 404


# ── GET /publishing/status/{run_id} ─────────────────────────────────


class TestGetStatus:
    def test_found(self, client):
        record = {
            "run_id": "abc123",
            "confluence_published": True,
            "confluence_url": "https://example.atlassian.net/wiki/page/123",
            "confluence_page_id": "123",
            "jira_completed": False,
            "jira_tickets": [],
            "status": "partial",
        }
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.get_delivery_status",
            return_value=record,
        ):
            resp = client.get("/publishing/status/abc123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "partial"

    def test_not_found(self, client):
        with patch(
            "crewai_productfeature_planner.apis.publishing.service.get_delivery_status",
            side_effect=ValueError("No delivery record found"),
        ):
            resp = client.get("/publishing/status/bad_id")
        assert resp.status_code == 404


# ── GET /publishing/automation/status ────────────────────────────────


class TestAutomationStatus:
    def test_status(self, client):
        with (
            patch(
                "crewai_productfeature_planner.apis.publishing.watcher.get_watcher_status",
                return_value={"running": False, "directory": "/tmp/prds"},
            ),
            patch(
                "crewai_productfeature_planner.apis.publishing.scheduler.get_scheduler_status",
                return_value={"running": False, "interval_seconds": 300},
            ),
        ):
            resp = client.get("/publishing/automation/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["watcher_running"] is False
        assert body["scheduler_interval_seconds"] == 300
