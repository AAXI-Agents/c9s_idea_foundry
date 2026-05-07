"""Tests for outbound Agentic Team API client (_service.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from crewai_productfeature_planner.apis.agentic_team._service import (
    _get_service_token,
    _invalidate_token,
    batch_kickoff_pipeline,
    get_idea_agent_status,
    get_pipeline_dashboard,
    get_project_features,
    get_task_status,
    kickoff_pipeline,
)


def _make_response(status_code: int, json_data: dict | None = None, text: str = "") -> MagicMock:
    """Create a mock httpx Response (sync .json() method)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


@pytest.fixture(autouse=True)
def _reset_token_cache():
    """Ensure cached token is cleared between tests."""
    _invalidate_token()
    yield
    _invalidate_token()


@pytest.fixture(autouse=True)
def _enable_integration():
    """Ensure AGENTIC_TEAM_ENABLED=true and URL is set for tests."""
    with patch(
        "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
        True,
    ), patch(
        "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_BASE_URL",
        "https://agentic.example.com/api",
    ):
        yield


# ── Token acquisition ─────────────────────────────────────────


class TestGetServiceToken:
    """Test SSO client_credentials token retrieval."""

    @pytest.mark.asyncio
    async def test_returns_token_on_success(self):
        resp = _make_response(200, {"access_token": "tok-abc", "expires_in": 3600})

        with patch.dict(
            "os.environ",
            {
                "SSO_BASE_URL": "https://sso.example.com",
                "SSO_CLIENT_ID": "client-id",
                "SSO_CLIENT_SECRET": "secret",
            },
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            token = await _get_service_token()
            assert token == "tok-abc"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_credentials(self):
        with patch.dict(
            "os.environ",
            {"SSO_BASE_URL": "", "SSO_CLIENT_ID": "", "SSO_CLIENT_SECRET": ""},
        ):
            token = await _get_service_token()
            assert token == ""

    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self):
        resp = _make_response(500)

        with patch.dict(
            "os.environ",
            {
                "SSO_BASE_URL": "https://sso.example.com",
                "SSO_CLIENT_ID": "client-id",
                "SSO_CLIENT_SECRET": "secret",
            },
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            token = await _get_service_token()
            assert token == ""


# ── get_project_features ──────────────────────────────────────


class TestGetProjectFeatures:
    """Test querying project features from Agentic Team."""

    @pytest.mark.asyncio
    async def test_returns_data_on_success(self):
        resp = _make_response(200, {"features": [{"key": "X-1"}]})

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok-123",
        ), patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await get_project_features("PROJ")
            assert result == {"features": [{"key": "X-1"}]}

    @pytest.mark.asyncio
    async def test_returns_none_on_401(self):
        resp = _make_response(401)

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="stale-token",
        ), patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await get_project_features("PROJ")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
            False,
        ):
            result = await get_project_features("PROJ")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await get_project_features("PROJ")
            assert result is None


# ── get_task_status ───────────────────────────────────────────


class TestGetTaskStatus:
    """Test querying single task status."""

    @pytest.mark.asyncio
    async def test_returns_status_on_success(self):
        resp = _make_response(200, {"key": "X-10", "status": "in_progress"})

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await get_task_status("X-10")
            assert result == {"key": "X-10", "status": "in_progress"}

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
            False,
        ):
            result = await get_task_status("X-10")
            assert result is None


# ── get_pipeline_dashboard ────────────────────────────────────


class TestGetPipelineDashboard:
    """Test pipeline dashboard query."""

    @pytest.mark.asyncio
    async def test_returns_dashboard_data(self):
        resp = _make_response(200, {"active": 3, "queued": 5})

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await get_pipeline_dashboard()
            assert result == {"active": 3, "queued": 5}

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
            False,
        ):
            result = await get_pipeline_dashboard()
            assert result is None


# ── kickoff_pipeline ──────────────────────────────────────────


class TestKickoffPipeline:
    """Test pipeline kickoff (outbound POST)."""

    @pytest.mark.asyncio
    async def test_returns_response_on_202(self):
        resp = _make_response(202, {"run_id": "run-99", "status": "queued"})

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            result = await kickoff_pipeline(
                project_key="PROJ",
                epic_keys=["PROJ-1", "PROJ-2"],
                idea_id="idea-abc",
                priority="high",
            )
            assert result == {"run_id": "run-99", "status": "queued"}

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        resp = _make_response(500, text="Internal Server Error")

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            result = await kickoff_pipeline(
                project_key="PROJ",
                epic_keys=["PROJ-1"],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
            False,
        ):
            result = await kickoff_pipeline(
                project_key="PROJ", epic_keys=["PROJ-1"],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_invalidates_token_on_401(self):
        resp = _make_response(401)

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="stale",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            result = await kickoff_pipeline(
                project_key="PROJ", epic_keys=["PROJ-1"],
            )
            assert result is None


# ── batch_kickoff_pipeline ────────────────────────────────────


class TestBatchKickoffPipeline:
    """Test batch pipeline kickoff (POST /pipeline/batch-kickoff)."""

    @pytest.mark.asyncio
    async def test_returns_response_on_202(self):
        resp = _make_response(202, {"accepted": 3, "skipped": 0, "errors": 0})

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            result = await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "Implement login", "topic": "login", "labels": ["idea:abc"]},
                {"issue_key": "PRD-11", "task_input": "Implement dashboard", "topic": "dashboard", "labels": ["idea:abc"]},
                {"issue_key": "PRD-12", "task_input": "Implement settings", "topic": "settings", "labels": ["idea:abc"]},
            ])
            assert result == {"accepted": 3, "skipped": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
            False,
        ):
            result = await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "test", "topic": "t", "labels": []},
            ])
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_tasks(self):
        result = await batch_kickoff_pipeline([])
        assert result is None

    @pytest.mark.asyncio
    async def test_retries_on_401(self):
        """First call gets 401, retries with fresh token."""
        resp_401 = _make_response(401)
        resp_202 = _make_response(202, {"accepted": 1, "skipped": 0, "errors": 0})

        call_count = 0

        async def _mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return resp_401
            return resp_202

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="fresh-tok",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_mock_post):
            result = await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "test", "topic": "t", "labels": []},
            ])
            assert result == {"accepted": 1, "skipped": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_returns_none_on_500(self):
        resp = _make_response(500, text="Internal Server Error")

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp):
            result = await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "test", "topic": "t", "labels": []},
            ])
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "test", "topic": "t", "labels": []},
            ])
            assert result is None


# ── get_idea_agent_status ─────────────────────────────────────


class TestGetIdeaAgentStatus:
    """Test querying pipeline status for an idea."""

    @pytest.mark.asyncio
    async def test_returns_status_on_success(self):
        resp = _make_response(200, {
            "tasks": [
                {"key": "PRD-10", "status": "completed"},
                {"key": "PRD-11", "status": "in_progress"},
            ],
            "completion_pct": 50,
        })

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await get_idea_agent_status("idea-abc")
            assert result["completion_pct"] == 50
            assert len(result["tasks"]) == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service.AGENTIC_TEAM_ENABLED",
            False,
        ):
            result = await get_idea_agent_status("idea-abc")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_401(self):
        resp = _make_response(401)

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="stale",
        ), patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await get_idea_agent_status("idea-abc")
            assert result is None


# ── Callback URL and Idempotency-Key ──────────────────────────


class TestCallbackUrlAndIdempotency:
    """Test that outbound kickoff requests include callback_url and Idempotency-Key."""

    @pytest.mark.asyncio
    async def test_kickoff_includes_callback_url(self):
        resp = _make_response(202, {"status": "accepted"})
        captured_kwargs = {}

        async def _capture_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.IDEA_FOUNDRY_BASE_URL",
            "https://ideafoundry.example.com",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_capture_post):
            result = await kickoff_pipeline(
                project_key="PROJ", epic_keys=["PROJ-1"], idea_id="idea-1",
            )
            assert result is not None
            # Verify callback_url in payload
            payload = captured_kwargs.get("json", {})
            assert payload["callback_url"] == "https://ideafoundry.example.com/webhooks/agentic-team"

    @pytest.mark.asyncio
    async def test_kickoff_includes_idempotency_key_header(self):
        resp = _make_response(202, {"status": "accepted"})
        captured_kwargs = {}

        async def _capture_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.IDEA_FOUNDRY_BASE_URL",
            "https://ideafoundry.example.com",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_capture_post):
            await kickoff_pipeline(project_key="PROJ", epic_keys=["PROJ-1"])
            headers = captured_kwargs.get("headers", {})
            assert "Idempotency-Key" in headers
            # Should be a valid UUID
            import uuid
            uuid.UUID(headers["Idempotency-Key"])  # raises if not valid

    @pytest.mark.asyncio
    async def test_kickoff_omits_callback_url_when_not_configured(self):
        resp = _make_response(202, {"status": "accepted"})
        captured_kwargs = {}

        async def _capture_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.IDEA_FOUNDRY_BASE_URL",
            "",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_capture_post):
            await kickoff_pipeline(project_key="PROJ", epic_keys=["PROJ-1"])
            payload = captured_kwargs.get("json", {})
            assert "callback_url" not in payload

    @pytest.mark.asyncio
    async def test_batch_kickoff_includes_callback_url(self):
        resp = _make_response(202, {"accepted": 1, "skipped": 0, "errors": 0})
        captured_kwargs = {}

        async def _capture_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.IDEA_FOUNDRY_BASE_URL",
            "https://ideafoundry.example.com",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_capture_post):
            await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "test", "topic": "t", "labels": []},
            ])
            payload = captured_kwargs.get("json", {})
            assert payload["callback_url"] == "https://ideafoundry.example.com/webhooks/agentic-team"

    @pytest.mark.asyncio
    async def test_batch_kickoff_includes_idempotency_key(self):
        resp = _make_response(202, {"accepted": 1, "skipped": 0, "errors": 0})
        captured_kwargs = {}

        async def _capture_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        with patch(
            "crewai_productfeature_planner.apis.agentic_team._service._get_service_token",
            new_callable=AsyncMock,
            return_value="tok",
        ), patch(
            "crewai_productfeature_planner.apis.agentic_team._service.IDEA_FOUNDRY_BASE_URL",
            "",
        ), patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=_capture_post):
            await batch_kickoff_pipeline([
                {"issue_key": "PRD-10", "task_input": "test", "topic": "t", "labels": []},
            ])
            headers = captured_kwargs.get("headers", {})
            assert "Idempotency-Key" in headers
