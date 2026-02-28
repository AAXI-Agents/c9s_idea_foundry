"""Tests for the Slack Events API router."""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app


@pytest.fixture(autouse=True)
def _clean_event_state(monkeypatch):
    """Clear module-level caches between tests."""
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("SLACK_VERIFICATION_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_BYPASS", raising=False)

    import crewai_productfeature_planner.apis.slack.events_router as er
    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    er._bot_user_id = None


def _post(payload: dict):
    """Return an awaitable that POSTs to /slack/events."""
    body = json.dumps(payload).encode()
    transport = ASGITransport(app=app)

    async def _do():
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.post(
                "/slack/events",
                content=body,
                headers={"Content-Type": "application/json"},
            )

    return _do


# ---- url_verification ----

@pytest.mark.asyncio
async def test_url_verification():
    resp = await _post({"type": "url_verification", "challenge": "abc"})()
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "abc"


# ---- duplicate event dedup ----

@pytest.mark.asyncio
async def test_duplicate_event_ignored():
    payload = {
        "type": "event_callback",
        "event_id": "Ev_DUPE",
        "event": {"type": "app_mention", "channel": "C1", "text": "hi", "user": "U1", "ts": "1234.5"},
    }
    with patch(
        "crewai_productfeature_planner.apis.slack.events_router._handle_app_mention",
    ) as mock_handle:
        resp1 = await _post(payload)()
        resp2 = await _post(payload)()
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Handler called only once
    mock_handle.assert_called_once()


# ---- member_joined_channel: bot intro ----

@pytest.mark.asyncio
async def test_member_joined_bot_posts_intro():
    import crewai_productfeature_planner.apis.slack.events_router as er
    er._bot_user_id = "BBOT"

    payload = {
        "type": "event_callback",
        "event_id": "Ev_JOIN1",
        "event": {"type": "member_joined_channel", "user": "BBOT", "channel": "C42"},
    }
    with patch.object(er, "_post_intro") as mock_intro:
        resp = await _post(payload)()
    assert resp.status_code == 200
    mock_intro.assert_called_once_with("C42", "")


@pytest.mark.asyncio
async def test_member_joined_other_user_no_intro():
    import crewai_productfeature_planner.apis.slack.events_router as er
    er._bot_user_id = "BBOT"

    payload = {
        "type": "event_callback",
        "event_id": "Ev_JOIN2",
        "event": {"type": "member_joined_channel", "user": "U_OTHER", "channel": "C42"},
    }
    with patch.object(er, "_post_intro") as mock_intro:
        resp = await _post(payload)()
    assert resp.status_code == 200
    mock_intro.assert_not_called()


# ---- app_mention dispatches handler ----

@pytest.mark.asyncio
async def test_app_mention_dispatches_handler():
    payload = {
        "type": "event_callback",
        "event_id": "Ev_MENT1",
        "event": {
            "type": "app_mention",
            "channel": "C10",
            "user": "U10",
            "text": "<@BBOT> create a PRD for a test",
            "ts": "1111.0",
        },
    }
    with patch(
        "crewai_productfeature_planner.apis.slack.events_router._handle_app_mention",
    ) as mock_handle:
        resp = await _post(payload)()
    assert resp.status_code == 200
    mock_handle.assert_called_once()
    event_arg = mock_handle.call_args[0][0]
    assert event_arg["type"] == "app_mention"
    assert event_arg["channel"] == "C10"


# ---- thread follow-up only when conversation exists ----

@pytest.mark.asyncio
async def test_thread_message_ignored_when_no_conversation():
    payload = {
        "type": "event_callback",
        "event_id": "Ev_THR1",
        "event": {
            "type": "message",
            "channel": "C99",
            "user": "U7",
            "text": "follow up",
            "ts": "5555.1",
            "thread_ts": "5555.0",
        },
    }
    with patch(
        "crewai_productfeature_planner.apis.slack.events_router._handle_thread_message",
    ) as mock_handle:
        resp = await _post(payload)()
    assert resp.status_code == 200
    mock_handle.assert_not_called()


@pytest.mark.asyncio
async def test_thread_message_dispatches_when_conversation_exists():
    import crewai_productfeature_planner.apis.slack.events_router as er
    # Seed a conversation
    er._append_to_thread("C99", "5555.0", "user", "first message")

    payload = {
        "type": "event_callback",
        "event_id": "Ev_THR2",
        "event": {
            "type": "message",
            "channel": "C99",
            "user": "U7",
            "text": "follow up",
            "ts": "5555.2",
            "thread_ts": "5555.0",
        },
    }
    with patch(
        "crewai_productfeature_planner.apis.slack.events_router._handle_thread_message",
    ) as mock_handle:
        resp = await _post(payload)()
    assert resp.status_code == 200
    mock_handle.assert_called_once()


# ---- unhandled event subtypes return ok ----

@pytest.mark.asyncio
async def test_unhandled_event_subtype():
    payload = {
        "type": "event_callback",
        "event_id": "Ev_UNK1",
        "event": {"type": "reaction_added", "user": "U1"},
    }
    resp = await _post(payload)()
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---- thread helpers ----

def test_thread_history_append_and_cap():
    import crewai_productfeature_planner.apis.slack.events_router as er

    for i in range(25):
        er._append_to_thread("C", "T", "user", f"msg-{i}")

    history = er._get_thread_history("C", "T")
    assert len(history) == 20  # capped at 20
    assert history[0]["content"] == "msg-5"


def test_thread_expiration():
    import crewai_productfeature_planner.apis.slack.events_router as er
    import time

    er._append_to_thread("C_EXP", "T_EXP", "user", "old msg")
    # Artificially age the entry
    er._thread_last_active[("C_EXP", "T_EXP")] = time.time() - 700
    history = er._get_thread_history("C_EXP", "T_EXP")
    assert len(history) == 0
