"""Tests for deliverables route (Phase 4)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app

_ROUTE = "crewai_productfeature_planner.apis.project_ideas._route_deliverables"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _idea_doc(**overrides):
    doc = {
        "idea_id": "idea-001",
        "project_id": "proj-1",
        "title": "Test Idea",
        "description": "",
        "status": "completed",
        "features": [],
        "overall_completion": 100.0,
        "active_run_id": "run-123",
        "run_ids": ["run-123"],
        "design_url": "https://figma.com/design",
        "design_url_type": "figma",
        "created_by": "user-1",
        "organization_id": "org-1",
        "enterprise_id": "ent-1",
    }
    doc.update(overrides)
    return doc


class TestGetDeliverables:
    def test_returns_deliverables(self, client):
        doc = _idea_doc()
        wi_doc = {
            "run_id": "run-123",
            "finalized_idea": "The executive summary...",
            "confluence_url": "https://confluence.example.com/page/123",
            "jira_output": "Created 5 tickets",
            "output_file": "output/prds/run-123.md",
            "section": {
                "executive_summary": [
                    {"content": "Exec content", "iteration": 3, "is_approved": True, "critique": ""},
                ],
                "goals_objectives": [
                    {"content": "Goals...", "iteration": 2, "is_approved": True, "critique": ""},
                ],
            },
            "ux_design_content": "UX wireframes...",
            "ux_design_status": "completed",
        }
        with (
            patch(f"{_ROUTE}.get_idea", return_value=doc),
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status",
                return_value=wi_doc,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record",
                return_value=None,
            ),
        ):
            resp = client.get("/projects/proj-1/ideas/idea-001/deliverables")
        assert resp.status_code == 200
        body = resp.json()
        assert body["idea_id"] == "idea-001"
        assert body["confluence_url"] == "https://confluence.example.com/page/123"
        assert body["design_url"] == "https://figma.com/design"
        assert len(body["prd_sections"]) == 2
        assert body["prd_sections"][0]["key"] == "executive_summary"
        assert body["prd_sections"][0]["is_approved"] is True
        assert body["ux_design"]["status"] == "completed"

    def test_no_run_id(self, client):
        doc = _idea_doc(active_run_id=None, run_ids=[])
        with patch(f"{_ROUTE}.get_idea", return_value=doc):
            resp = client.get("/projects/proj-1/ideas/idea-001/deliverables")
        assert resp.status_code == 200
        body = resp.json()
        assert body["prd_sections"] == []
        assert body["run_id"] is None

    def test_404_not_found(self, client):
        with patch(f"{_ROUTE}.get_idea", return_value=None):
            resp = client.get("/projects/proj-1/ideas/missing/deliverables")
        assert resp.status_code == 404

    def test_uses_latest_run_id(self, client):
        doc = _idea_doc(active_run_id=None, run_ids=["run-old", "run-latest"])
        wi_doc = {
            "run_id": "run-latest",
            "finalized_idea": None,
            "confluence_url": None,
            "jira_output": None,
            "output_file": None,
            "section": {},
        }
        with (
            patch(f"{_ROUTE}.get_idea", return_value=doc),
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status",
                return_value=wi_doc,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record",
                return_value=None,
            ),
        ):
            resp = client.get("/projects/proj-1/ideas/idea-001/deliverables")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run-latest"
