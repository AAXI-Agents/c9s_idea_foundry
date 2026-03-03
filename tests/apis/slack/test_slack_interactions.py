"""Tests for the Slack interactions router (/slack/interactions)."""

import json
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "SLACK_SIGNING_SECRET", "SLACK_VERIFICATION_TOKEN",
        "SLACK_ACCESS_TOKEN", "SLACK_BYPASS",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _clean_interactive_state():
    """Clear interactive handler state between tests."""
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _interactive_runs,
        _lock,
        _manual_refinement_text,
    )
    with _lock:
        _interactive_runs.clear()
        _manual_refinement_text.clear()
    yield
    with _lock:
        _interactive_runs.clear()
        _manual_refinement_text.clear()


async def _post_interaction(payload: dict) -> object:
    """POST a Slack interaction payload to /slack/interactions."""
    body = urlencode({"payload": json.dumps(payload)}).encode()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(
            "/slack/interactions",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )


# ---- invalid payload ----

@pytest.mark.asyncio
async def test_invalid_payload():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/slack/interactions",
            content=b"garbage",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert resp.status_code == 400


# ---- unknown action_id returns ok ----

@pytest.mark.asyncio
async def test_unknown_action_id():
    payload = {
        "type": "block_actions",
        "user": {"id": "U1", "username": "testuser"},
        "actions": [{"action_id": "unknown_thing", "value": "run123"}],
        "channel": {"id": "C1"},
        "message": {"ts": "1234.5"},
    }
    resp = await _post_interaction(payload)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---- known action with no pending run ----

@pytest.mark.asyncio
async def test_action_no_pending_run():
    payload = {
        "type": "block_actions",
        "user": {"id": "U1", "username": "testuser"},
        "actions": [{"action_id": "refinement_agent", "value": "nonexistent"}],
        "channel": {"id": "C1"},
        "message": {"ts": "1234.5"},
    }
    resp = await _post_interaction(payload)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---- known action with pending run resolves ----

@pytest.mark.asyncio
async def test_action_resolves_pending_run():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        get_interactive_run,
        register_interactive_run,
    )

    register_interactive_run("run_abc", "C1", "1234.0", "U42", "test idea")

    payload = {
        "type": "block_actions",
        "user": {"id": "U42", "username": "alice"},
        "actions": [{"action_id": "refinement_agent", "value": "run_abc"}],
        "channel": {"id": "C1"},
        "message": {"ts": "1234.5", "thread_ts": "1234.0"},
    }

    with patch(
        "crewai_productfeature_planner.apis.slack.interactions_router._dispatch._post_ack",
    ):
        resp = await _post_interaction(payload)

    assert resp.status_code == 200

    info = get_interactive_run("run_abc")
    assert info is not None
    assert info["decision"] == "refinement_agent"


# ---- cancel action sets cancelled flag ----

@pytest.mark.asyncio
async def test_cancel_action_sets_flag():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        get_interactive_run,
        register_interactive_run,
    )

    register_interactive_run("run_cancel", "C1", "1234.0", "U42", "test idea")

    payload = {
        "type": "block_actions",
        "user": {"id": "U42", "username": "alice"},
        "actions": [{"action_id": "flow_cancel", "value": "run_cancel"}],
        "channel": {"id": "C1"},
        "message": {"ts": "1234.5"},
    }

    with patch(
        "crewai_productfeature_planner.apis.slack.interactions_router._dispatch._post_ack",
    ):
        resp = await _post_interaction(payload)

    assert resp.status_code == 200
    info = get_interactive_run("run_cancel")
    assert info["cancelled"] is True


# ---- view_submission returns clear ----

@pytest.mark.asyncio
async def test_view_submission():
    payload = {
        "type": "view_submission",
        "view": {"callback_id": "test"},
        "user": {"id": "U1"},
    }
    resp = await _post_interaction(payload)
    assert resp.status_code == 200
    assert resp.json().get("response_action") == "clear"


# ---- empty actions list returns ok ----

@pytest.mark.asyncio
async def test_empty_actions():
    payload = {
        "type": "block_actions",
        "user": {"id": "U1"},
        "actions": [],
    }
    resp = await _post_interaction(payload)
    assert resp.status_code == 200


# ---- missing value in action returns ok ----

@pytest.mark.asyncio
async def test_missing_value():
    payload = {
        "type": "block_actions",
        "user": {"id": "U1", "username": "testuser"},
        "actions": [{"action_id": "refinement_agent", "value": ""}],
        "channel": {"id": "C1"},
        "message": {"ts": "1234.5"},
    }
    resp = await _post_interaction(payload)
    assert resp.status_code == 200
