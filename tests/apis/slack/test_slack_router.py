"""Tests for the Slack kickoff router (/slack/kickoff, /slack/kickoff/sync)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "SLACK_SIGNING_SECRET", "SLACK_VERIFICATION_TOKEN",
        "SLACK_ACCESS_TOKEN", "SLACK_BYPASS", "SLACK_DEFAULT_CHANNEL",
    ):
        monkeypatch.delenv(key, raising=False)


async def _kickoff(payload: dict, sync: bool = False):
    transport = ASGITransport(app=app)
    path = "/slack/kickoff/sync" if sync else "/slack/kickoff"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(path, json=payload)


# ---- validation: no text → 422 ----

@pytest.mark.asyncio
async def test_kickoff_no_text():
    resp = await _kickoff({"channel": "C1"})
    assert resp.status_code == 422


# ---- async kickoff returns immediately ----

@pytest.mark.asyncio
async def test_kickoff_async_returns_pending():
    with patch(
        "crewai_productfeature_planner.apis.slack.router._run_slack_prd_flow",
    ):
        resp = await _kickoff({"text": "build a fitness app PRD"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["idea"] == "build a fitness app PRD"
    assert "run_id" in data


# ---- channel default ----

@pytest.mark.asyncio
async def test_kickoff_default_channel(monkeypatch):
    monkeypatch.setenv("SLACK_DEFAULT_CHANNEL", "my-channel")
    captured = {}

    def _capture_flow(run_id, text, channel, *args, **kwargs):
        captured["channel"] = channel

    with patch(
        "crewai_productfeature_planner.apis.slack.router._run_slack_prd_flow",
        side_effect=_capture_flow,
    ):
        resp = await _kickoff({"text": "some idea"})
    assert resp.status_code == 200
    assert captured["channel"] == "my-channel"


@pytest.mark.asyncio
async def test_kickoff_explicit_channel():
    captured = {}

    def _capture_flow(run_id, text, channel, *args, **kwargs):
        captured["channel"] = channel

    with patch(
        "crewai_productfeature_planner.apis.slack.router._run_slack_prd_flow",
        side_effect=_capture_flow,
    ):
        resp = await _kickoff({"text": "idea", "channel": "my-explicit"})
    assert resp.status_code == 200
    assert captured["channel"] == "my-explicit"


# ---- sync kickoff ----

@pytest.mark.asyncio
async def test_kickoff_sync_returns_result():
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs

    def _fake_flow(run_id, text, channel, *args, **kwargs):
        # The real _run_slack_prd_flow creates the FlowRun record.
        runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")
        runs[run_id].status = FlowStatus.COMPLETED
        runs[run_id].result = {"summary": "done"}

    with patch(
        "crewai_productfeature_planner.apis.slack.router._run_slack_prd_flow",
        side_effect=_fake_flow,
    ):
        resp = await _kickoff({"text": "sync idea"}, sync=True)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"


# ---- _deliver_webhook ----

def test_deliver_webhook_posts(monkeypatch):
    from crewai_productfeature_planner.apis.slack.router import _deliver_webhook

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as MockClient:
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.post.return_value = mock_resp
        MockClient.return_value = mock_client_instance

        _deliver_webhook("run123", {"summary": "ok"}, None, "https://hook.example.com")

    mock_client_instance.post.assert_called_once()
    call_args = mock_client_instance.post.call_args
    assert call_args[0][0] == "https://hook.example.com"
    assert call_args[1]["json"]["run_id"] == "run123"
    assert call_args[1]["json"]["status"] == "completed"


def test_deliver_webhook_error_does_not_raise():
    from crewai_productfeature_planner.apis.slack.router import _deliver_webhook

    with patch("httpx.Client", side_effect=Exception("network error")):
        # Should not raise
        _deliver_webhook("run_err", None, "boom", "https://hook.example.com")
