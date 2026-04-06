"""Tests for timeline builder and response models."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Patch at the source modules — _build_timeline imports inside the function body
_IDEAS = "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status"
_JOBS = "crewai_productfeature_planner.mongodb.crew_jobs.find_job"
_INTERACTIONS = "crewai_productfeature_planner.mongodb.agent_interactions.find_interactions"
_DELIVERY = "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record"


class TestBuildTimeline:
    """Test the _build_timeline helper directly."""

    @patch(_DELIVERY, return_value=None)
    @patch(_INTERACTIONS, return_value=[])
    @patch(_JOBS, return_value=None)
    @patch(_IDEAS)
    def test_builds_from_idea_doc(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        mock_idea.return_value = {
            "run_id": "r1",
            "idea": "Build a fitness app",
            "created_at": "2026-04-05T10:00:00",
            "update_date": "2026-04-05T10:01:00",
            "finalized_idea": "A refined fitness app idea",
            "executive_summary": [
                {"content": "ES v1", "iteration": 1, "updated_date": "2026-04-05T10:02:00"},
            ],
            "section": {
                "problem_statement": [
                    {"content": "Problem v1", "iteration": 1, "updated_date": "2026-04-05T10:03:00"},
                ],
            },
        }
        events = _build_timeline("r1", limit=200)
        types = [e.event_type for e in events]
        assert "idea_submitted" in types
        assert "idea_refined" in types
        assert "exec_summary_iteration" in types
        assert "section_drafted" in types

    @patch(_DELIVERY)
    @patch(_INTERACTIONS, return_value=[])
    @patch(_JOBS, return_value=None)
    @patch(_IDEAS, return_value={"run_id": "r1", "created_at": "2026-04-05T10:00:00"})
    def test_includes_delivery_events(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        mock_del.return_value = {
            "confluence_published": True,
            "confluence_url": "https://conf.example.com/page",
            "confluence_page_id": "123",
            "jira_completed": True,
            "jira_tickets": [{"key": "PROJ-1"}, {"key": "PROJ-2"}],
            "updated_at": "2026-04-05T11:00:00",
        }
        events = _build_timeline("r1", limit=200)
        types = [e.event_type for e in events]
        assert "confluence_published" in types
        assert "jira_created" in types

    @patch(_DELIVERY, return_value=None)
    @patch(_INTERACTIONS, return_value=[])
    @patch(_JOBS)
    @patch(_IDEAS, return_value={"run_id": "r1", "created_at": "2026-04-05T10:00:00"})
    def test_includes_job_events(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        mock_job.return_value = {
            "job_id": "r1",
            "queued_at": "2026-04-05T10:00:00",
            "started_at": "2026-04-05T10:00:05",
            "queue_time_human": "5s",
        }
        events = _build_timeline("r1", limit=200)
        types = [e.event_type for e in events]
        assert "job_status" in types

    @patch(_DELIVERY, return_value=None)
    @patch(_INTERACTIONS)
    @patch(_JOBS, return_value=None)
    @patch(_IDEAS, return_value={"run_id": "r1", "created_at": "2026-04-05T10:00:00"})
    def test_includes_agent_interactions(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        mock_int.return_value = [
            {
                "interaction_id": "i1",
                "source": "slack",
                "intent": "create_prd",
                "agent_response": "Starting PRD generation...",
                "user_message": "Create a PRD for my app",
                "created_at": "2026-04-05T10:00:30",
            },
        ]
        events = _build_timeline("r1", limit=200)
        types = [e.event_type for e in events]
        assert "agent_interaction" in types

    @patch(_DELIVERY, return_value=None)
    @patch(_INTERACTIONS, return_value=[])
    @patch(_JOBS, return_value=None)
    @patch(_IDEAS, return_value=None)
    def test_empty_when_no_data(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        events = _build_timeline("r1", limit=200)
        assert events == []

    @patch(_DELIVERY, return_value=None)
    @patch(_INTERACTIONS, return_value=[])
    @patch(_JOBS, return_value=None)
    @patch(_IDEAS)
    def test_events_sorted_by_timestamp(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        mock_idea.return_value = {
            "run_id": "r1",
            "idea": "App",
            "created_at": "2026-04-05T10:00:00",
            "update_date": "2026-04-05T10:05:00",
            "finalized_idea": "Refined",
            "completed_at": "2026-04-05T10:10:00",
            "status": "completed",
        }
        events = _build_timeline("r1", limit=200)
        timestamps = [e.timestamp for e in events if e.timestamp]
        assert timestamps == sorted(timestamps)

    @patch(_DELIVERY, return_value=None)
    @patch(_INTERACTIONS, return_value=[])
    @patch(_JOBS, return_value=None)
    @patch(_IDEAS)
    def test_respects_limit(self, mock_idea, mock_job, mock_int, mock_del):
        from crewai_productfeature_planner.apis.prd._route_timeline import _build_timeline
        mock_idea.return_value = {
            "run_id": "r1",
            "idea": "App",
            "created_at": "2026-04-05T10:00:00",
            "update_date": "2026-04-05T11:00:00",
            "finalized_idea": "Refined",
            "completed_at": "2026-04-05T12:00:00",
            "status": "completed",
            "executive_summary": [
                {"content": f"ES v{i}", "iteration": i, "updated_date": f"2026-04-05T10:{i:02d}:00"}
                for i in range(1, 6)
            ],
        }
        events = _build_timeline("r1", limit=3)
        assert len(events) <= 3


class TestTimelineResponseModel:
    """Test the response model structure."""

    def test_timeline_event_defaults(self):
        from crewai_productfeature_planner.apis.prd._route_timeline import TimelineEvent
        event = TimelineEvent(
            timestamp="2026-04-05T10:00:00",
            event_type="idea_submitted",
            title="Submitted",
        )
        assert event.detail == ""
        assert event.agent == ""
        assert event.section_key == ""
        assert event.iteration == 0
        assert event.metadata == {}

    def test_timeline_response_model(self):
        from crewai_productfeature_planner.apis.prd._route_timeline import (
            TimelineEvent,
            TimelineResponse,
        )
        resp = TimelineResponse(
            run_id="r1",
            total_events=1,
            events=[TimelineEvent(
                timestamp="2026-04-05T10:00:00",
                event_type="idea_submitted",
                title="Submitted",
            )],
        )
        assert resp.run_id == "r1"
        assert resp.total_events == 1
