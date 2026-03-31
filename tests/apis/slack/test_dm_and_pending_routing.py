"""Tests for DM message routing and pending-state thread dispatch.

Verifies that the ``slack_events`` endpoint correctly routes:

* DM messages (non-threaded) → ``_handle_app_mention``
* DM thread follow-ups → ``_handle_thread_message``
* Channel thread messages with pending user state → ``_handle_thread_message``
* Bot's own messages and edited messages are skipped
* ``has_pending_state`` helper works correctly
* app_mention with pending state → redirected to ``_handle_thread_message``
* Thread session isolation — only initiating user can reply
* Multiple user sessions each get their own thread
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app

_ER = "crewai_productfeature_planner.apis.slack.events_router"
_SM = "crewai_productfeature_planner.apis.slack.session_manager"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Reset module-level caches between tests."""
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("SLACK_VERIFICATION_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_BYPASS", raising=False)

    import crewai_productfeature_planner.apis.slack.events_router as er
    import crewai_productfeature_planner.apis.slack.session_manager as sm

    with er._thread_lock:
        er._thread_conversations.clear()
        er._thread_last_active.clear()
    with er._seen_events_lock:
        er._seen_events.clear()
    er._bot_user_id = None

    with sm._lock:
        sm._pending_project_creates.clear()
        sm._pending_memory_entries.clear()
        sm._pending_project_setup.clear()

    # Patch _get_slack_client so event-handler circuit breakers pass
    monkeypatch.setattr(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
        lambda: MagicMock(),
    )


async def _post(payload: dict):
    """POST a JSON payload to /slack/events and return the response."""
    body = json.dumps(payload).encode()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(
            "/slack/events",
            content=body,
            headers={"Content-Type": "application/json"},
        )


def _event_payload(event: dict, event_id: str = "Ev_TEST") -> dict:
    return {"type": "event_callback", "event_id": event_id, "event": event}


# ======================================================================
# has_pending_state helper
# ======================================================================


class TestHasPendingState:
    def test_no_pending(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            has_pending_state,
        )

        assert has_pending_state("U1") is False

    def test_pending_create(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            has_pending_state,
            mark_pending_create,
        )

        mark_pending_create("U1", "C1", "1234.0")
        assert has_pending_state("U1") is True

    def test_pending_memory(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            has_pending_state,
            mark_pending_memory,
        )

        mark_pending_memory("U2", "C1", "1234.0", "knowledge", "p1")
        assert has_pending_state("U2") is True

    def test_cleared_after_pop(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            has_pending_state,
            mark_pending_create,
            pop_pending_create,
        )

        mark_pending_create("U3", "C1", "1234.0")
        pop_pending_create("U3")
        assert has_pending_state("U3") is False


# ======================================================================
# DM message routing
# ======================================================================


class TestDmMessageRouting:
    """DMs use ``message`` events (not ``app_mention``).

    Non-threaded DMs should be routed to ``_handle_app_mention``
    so the bot processes them like a first interaction.
    Threaded DMs should be routed to ``_handle_thread_message``.
    """

    @pytest.mark.asyncio
    async def test_dm_non_threaded_dispatches_handler(self):
        """First DM message (no thread_ts) → _handle_app_mention."""
        payload = _event_payload(
            {
                "type": "message",
                "channel": "D_USER1",
                "user": "U1",
                "text": "hello bot",
                "ts": "1000.0",
            },
            event_id="Ev_DM1",
        )
        with patch(f"{_ER}._handle_app_mention") as mock_mention, \
             patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_mention.assert_called_once()
        mock_thread.assert_not_called()
        event_arg = mock_mention.call_args[0][0]
        assert event_arg["channel"] == "D_USER1"

    @pytest.mark.asyncio
    async def test_dm_threaded_dispatches_thread_handler(self):
        """DM thread reply (has thread_ts) → _handle_thread_message."""
        payload = _event_payload(
            {
                "type": "message",
                "channel": "D_USER1",
                "user": "U1",
                "text": "reply in thread",
                "ts": "1000.2",
                "thread_ts": "1000.0",
            },
            event_id="Ev_DM2",
        )
        with patch(f"{_ER}._handle_app_mention") as mock_mention, \
             patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()
        mock_mention.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_skips_bot_own_message(self):
        """Bot's own DM messages are ignored."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        er._bot_user_id = "BBOT"

        payload = _event_payload(
            {
                "type": "message",
                "channel": "D_USER1",
                "user": "BBOT",
                "text": "my own reply",
                "ts": "1000.1",
            },
            event_id="Ev_DM3",
        )
        with patch(f"{_ER}._handle_app_mention") as mock_mention, \
             patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_mention.assert_not_called()
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_skips_message_subtype(self):
        """DM message_changed / message_deleted events are ignored."""
        payload = _event_payload(
            {
                "type": "message",
                "subtype": "message_changed",
                "channel": "D_USER1",
                "user": "U1",
                "text": "edited",
                "ts": "1000.1",
            },
            event_id="Ev_DM4",
        )
        with patch(f"{_ER}._handle_app_mention") as mock_mention:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_mention.assert_not_called()


# ======================================================================
# Channel thread with pending state
# ======================================================================


class TestPendingStateRouting:
    """Thread messages from users with pending creates/memory should
    be dispatched even when the thread conversation cache is empty.
    """

    @pytest.mark.asyncio
    async def test_channel_thread_dispatches_with_pending_create(self):
        """Pending project-create → thread message dispatched."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        mark_pending_create("U5", "C_CHAN", "7777.0")

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "U5",
                "text": "My New Project",
                "ts": "7777.1",
                "thread_ts": "7777.0",
            },
            event_id="Ev_PEND1",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_channel_thread_dispatches_with_pending_memory(self):
        """Pending memory entry → thread message dispatched."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U6", "C_CHAN", "8888.0", "knowledge", "p42")

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "U6",
                "text": "https://docs.example.com",
                "ts": "8888.1",
                "thread_ts": "8888.0",
            },
            event_id="Ev_PEND2",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_channel_thread_ignored_without_context(self):
        """No conversation, no interactive, no pending → ignored."""
        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "U_RAND",
                "text": "random reply",
                "ts": "9999.1",
                "thread_ts": "9999.0",
            },
            event_id="Ev_PEND3",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_non_threaded_message_ignored(self):
        """Non-threaded channel messages (no @mention) are not processed."""
        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "U7",
                "text": "just chatting",
                "ts": "1234.0",
            },
            event_id="Ev_CHAN_NT",
        )
        with patch(f"{_ER}._handle_app_mention") as mock_mention, \
             patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_mention.assert_not_called()
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_bot_message_skipped(self):
        """Bot's own channel messages are not re-processed."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        er._bot_user_id = "BBOT"

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "BBOT",
                "text": "echo",
                "ts": "1234.1",
                "thread_ts": "1234.0",
            },
            event_id="Ev_CHAN_BOT",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_not_called()


# ======================================================================
# app_mention with pending state → redirect to thread handler
# ======================================================================


class TestAppMentionPendingRedirect:
    """When a user @-mentions the bot in a thread where they have pending
    state (e.g. awaiting a project name), the app_mention handler should
    redirect to _handle_thread_message so the pending-state logic fires.
    """

    @pytest.mark.asyncio
    async def test_app_mention_with_pending_create_redirects(self):
        """@mention in thread + pending create → thread handler."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        mark_pending_create("U10", "C_CHAN", "5555.0")

        payload = _event_payload(
            {
                "type": "app_mention",
                "channel": "C_CHAN",
                "user": "U10",
                "text": "<@BBOT> My Cool Project",
                "ts": "5555.1",
                "thread_ts": "5555.0",
            },
            event_id="Ev_MENTION_PEND1",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()
        mock_interpret.assert_not_called()

    @pytest.mark.asyncio
    async def test_app_mention_without_pending_goes_to_interpret(self):
        """@mention in thread + NO pending state → normal interpret."""
        payload = _event_payload(
            {
                "type": "app_mention",
                "channel": "C_CHAN",
                "user": "U11",
                "text": "<@BBOT> hello there",
                "ts": "6666.1",
                "thread_ts": "6666.0",
            },
            event_id="Ev_MENTION_NOPEND1",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_interpret.assert_called_once()
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_app_mention_no_thread_goes_to_interpret(self):
        """@mention NOT in a thread → normal interpret (even with pending)."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        # Pending create exists but the mention is not in a thread
        mark_pending_create("U12", "C_CHAN", "7777.0")

        payload = _event_payload(
            {
                "type": "app_mention",
                "channel": "C_CHAN",
                "user": "U12",
                "text": "<@BBOT> create a project",
                "ts": "8888.0",
                # No thread_ts → not a thread reply
            },
            event_id="Ev_MENTION_NOTHREAD",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_interpret.assert_called_once()
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_app_mention_with_pending_memory_redirects(self):
        """@mention in thread + pending memory → thread handler."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U13", "C_CHAN", "9999.0", "knowledge", "p1")

        payload = _event_payload(
            {
                "type": "app_mention",
                "channel": "C_CHAN",
                "user": "U13",
                "text": "<@BBOT> https://docs.example.com",
                "ts": "9999.1",
                "thread_ts": "9999.0",
            },
            event_id="Ev_MENTION_PENDMEM",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()
        mock_interpret.assert_not_called()


# ======================================================================
# Thread session isolation
# ======================================================================


class TestThreadSessionIsolation:
    """Only the user who initiated a pending-create session should be
    able to provide the project name.  Other users' replies in the
    same thread should be rejected.
    """

    def test_initiating_user_project_name_accepted(self):
        """The user who started the create flow can provide the name."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        mark_pending_create("U_OWNER", "C1", "T1")

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_OWNER",
            "text": "My Project Name",
            "ts": "T1.1",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._handle_project_name_reply") as mock_name, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret, \
             patch(f"{_ER}._reply") as mock_reply:
            er._handle_thread_message(event)

        mock_name.assert_called_once_with(
            channel="C1", thread_ts="T1",
            user="U_OWNER", project_name="My Project Name",
        )
        mock_interpret.assert_not_called()
        mock_reply.assert_not_called()

    def test_other_user_rejected_during_pending_create(self):
        """Another user replying in a pending-create thread is told to wait."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        mark_pending_create("U_OWNER", "C1", "T1")

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_INTRUDER",
            "text": "My Project Attempt",
            "ts": "T1.2",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._handle_project_name_reply") as mock_name, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret, \
             patch(f"{_ER}._reply") as mock_reply:
            er._handle_thread_message(event)

        # Project name reply should NOT be called for the intruder
        mock_name.assert_not_called()
        # Normal interpret should NOT run either
        mock_interpret.assert_not_called()
        # A rejection message should be posted
        mock_reply.assert_called_once()
        reply_text = mock_reply.call_args[0][2]
        assert "U_OWNER" in reply_text
        assert "U_INTRUDER" in reply_text

    def test_pending_create_owner_for_thread(self):
        """get_pending_create_owner_for_thread returns the correct owner."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_create_owner_for_thread,
            mark_pending_create,
        )

        assert get_pending_create_owner_for_thread("C1", "T1") is None

        mark_pending_create("U_OWNER", "C1", "T1")
        assert get_pending_create_owner_for_thread("C1", "T1") == "U_OWNER"
        assert get_pending_create_owner_for_thread("C1", "T_OTHER") is None
        assert get_pending_create_owner_for_thread("C_OTHER", "T1") is None

    def test_pending_cleared_after_pop(self):
        """After pop, owner lookup returns None."""
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_pending_create_owner_for_thread,
            mark_pending_create,
            pop_pending_create,
        )

        mark_pending_create("U_OWNER", "C1", "T1")
        pop_pending_create("U_OWNER")
        assert get_pending_create_owner_for_thread("C1", "T1") is None


# ======================================================================
# Multiple concurrent user sessions
# ======================================================================


class TestMultipleUserSessions:
    """Multiple users can each have their own pending-create in
    separate threads.  Each user's reply goes to their own session.
    """

    def test_two_users_separate_threads(self):
        """Two users with pending creates in different threads both work."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        mark_pending_create("U_ALICE", "C1", "T_ALICE")
        mark_pending_create("U_BOB", "C1", "T_BOB")

        # Alice replies in her thread
        event_alice = {
            "type": "message",
            "channel": "C1",
            "user": "U_ALICE",
            "text": "Alice Project",
            "ts": "T_ALICE.1",
            "thread_ts": "T_ALICE",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._handle_project_name_reply") as mock_name, \
             patch(f"{_ER}._reply"):
            er._handle_thread_message(event_alice)

        mock_name.assert_called_once_with(
            channel="C1", thread_ts="T_ALICE",
            user="U_ALICE", project_name="Alice Project",
        )

        # Bob replies in his thread
        event_bob = {
            "type": "message",
            "channel": "C1",
            "user": "U_BOB",
            "text": "Bob Project",
            "ts": "T_BOB.1",
            "thread_ts": "T_BOB",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._handle_project_name_reply") as mock_name, \
             patch(f"{_ER}._reply"):
            er._handle_thread_message(event_bob)

        mock_name.assert_called_once_with(
            channel="C1", thread_ts="T_BOB",
            user="U_BOB", project_name="Bob Project",
        )

    def test_user_cannot_answer_in_other_users_thread(self):
        """Bob replying in Alice's pending-create thread is rejected."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        mark_pending_create("U_ALICE", "C1", "T_ALICE")
        mark_pending_create("U_BOB", "C1", "T_BOB")

        # Bob tries to reply in Alice's thread
        event_wrong = {
            "type": "message",
            "channel": "C1",
            "user": "U_BOB",
            "text": "Hijack Attempt",
            "ts": "T_ALICE.2",
            "thread_ts": "T_ALICE",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._handle_project_name_reply") as mock_name, \
             patch(f"{_ER}._reply") as mock_reply, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            er._handle_thread_message(event_wrong)

        # Bob's pending create is NOT consumed (it's for a different thread)
        mock_name.assert_not_called()
        mock_interpret.assert_not_called()
        mock_reply.assert_called_once()
        reply_text = mock_reply.call_args[0][2]
        assert "U_ALICE" in reply_text

    def test_new_user_starts_own_thread_via_app_mention(self):
        """A new user's @mention in the channel starts their own session,
        independent of any existing pending sessions in other threads.
        """
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_create,
        )

        # Alice has an active pending create in her thread
        mark_pending_create("U_ALICE", "C1", "T_ALICE")

        # Bob @mentions the bot at the top level (no thread_ts)
        payload = _event_payload(
            {
                "type": "app_mention",
                "channel": "C1",
                "user": "U_BOB",
                "text": "<@BBOT> create a new project",
                "ts": "2000.0",
                # No thread_ts → top-level mention
            },
            event_id="Ev_BOB_NEW",
        )
        with patch(f"{_ER}._handle_thread_message") as mock_thread, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            import asyncio
            resp = asyncio.get_event_loop().run_until_complete(_post(payload))

        assert resp.status_code == 200
        # Should go to interpret (new session), NOT thread handler
        mock_interpret.assert_called_once()
        mock_thread.assert_not_called()


# ======================================================================
# Thread history fallback (agentInteraction-based)
# ======================================================================


_AI_MODULE = (
    "crewai_productfeature_planner.mongodb.agent_interactions"
)


class TestThreadHistoryFallback:
    """When the in-memory thread cache has expired and no project is
    selected yet, the bot should still process thread messages if it
    has previously responded in that thread (persisted in
    ``agentInteraction``).
    """

    @pytest.mark.asyncio
    async def test_dispatches_when_thread_history_exists(self):
        """Thread with prior bot interaction → dispatched."""
        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "U_HIST",
                "text": "configure the project",
                "ts": "5555.1",
                "thread_ts": "5555.0",
            },
            event_id="Ev_HIST1",
        )
        with patch(
            f"{_AI_MODULE}.has_bot_thread_history", return_value=True,
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignored_when_no_thread_history(self):
        """No conversation, no interactive, no pending, no session,
        no thread history → ignored.
        """
        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_CHAN",
                "user": "U_NOHIST",
                "text": "random reply",
                "ts": "6666.1",
                "thread_ts": "6666.0",
            },
            event_id="Ev_HIST2",
        )
        with patch(
            f"{_AI_MODULE}.has_bot_thread_history", return_value=False,
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_thread_history_re_registers_in_memory_cache(self):
        """When thread history fallback fires, the thread is re-added
        to the in-memory cache so subsequent messages skip the DB
        lookup.
        """
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack._thread_state import (
            has_thread_conversation,
        )

        channel, thread_ts = "C_REREGISTER", "7777.0"
        assert not has_thread_conversation(channel, thread_ts)

        payload = _event_payload(
            {
                "type": "message",
                "channel": channel,
                "user": "U_REREG",
                "text": "hello again",
                "ts": "7777.1",
                "thread_ts": thread_ts,
            },
            event_id="Ev_HIST3",
        )
        with patch(
            f"{_AI_MODULE}.has_bot_thread_history", return_value=True,
        ), patch(f"{_ER}._handle_thread_message"):
            await _post(payload)

        # Thread should now be in the in-memory cache
        assert has_thread_conversation(channel, thread_ts)


# ======================================================================
# Bot mention gating on fallback conditions (v0.32.0)
# ======================================================================


_BOT_ID = "U_BOT_123"


class TestMentionGateActiveSession:
    """When the only reason to process is ``active_session``, the bot
    must be @mentioned in the message text.
    """

    @pytest.mark.asyncio
    async def test_no_mention_ignores(self):
        """No @mention + active_session → ignored."""
        import crewai_productfeature_planner.apis.slack._thread_state as ts

        ts._bot_user_id = _BOT_ID

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_GATE",
                "user": "U_NOBOT",
                "text": "configure",
                "ts": "8001.1",
                "thread_ts": "8001.0",
            },
            event_id="Ev_GATE1",
        )
        with patch(
            f"{_SM}.get_channel_project_id", return_value="proj_123",
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_mention_dispatches(self):
        """@mention + active_session → dispatched."""
        import crewai_productfeature_planner.apis.slack._thread_state as ts

        ts._bot_user_id = _BOT_ID

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_GATE",
                "user": "U_NOBOT",
                "text": f"<@{_BOT_ID}> configure",
                "ts": "8002.1",
                "thread_ts": "8002.0",
            },
            event_id="Ev_GATE2",
        )
        with patch(
            f"{_SM}.get_channel_project_id", return_value="proj_123",
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()


class TestMentionGateThreadHistory:
    """When the only reason to process is ``thread_history``, the bot
    does NOT need to be @mentioned — the thread is an established
    conversation (the bot has already replied).  This ensures thread
    continuity survives server restarts that clear the in-memory cache.
    """

    @pytest.mark.asyncio
    async def test_no_mention_dispatches_with_thread_history(self):
        """No @mention + thread_history → dispatched (bot already replied)."""
        import crewai_productfeature_planner.apis.slack._thread_state as ts

        ts._bot_user_id = _BOT_ID

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_GATE2",
                "user": "U_NOBOT",
                "text": "list of ideas",
                "ts": "9001.1",
                "thread_ts": "9001.0",
            },
            event_id="Ev_GATE3",
        )
        with patch(
            f"{_AI_MODULE}.has_bot_thread_history", return_value=True,
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_mention_dispatches(self):
        """@mention + thread_history → dispatched."""
        import crewai_productfeature_planner.apis.slack._thread_state as ts

        ts._bot_user_id = _BOT_ID

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_GATE2",
                "user": "U_NOBOT",
                "text": f"<@{_BOT_ID}> list of ideas",
                "ts": "9002.1",
                "thread_ts": "9002.0",
            },
            event_id="Ev_GATE4",
        )
        with patch(
            f"{_AI_MODULE}.has_bot_thread_history", return_value=True,
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()


class TestNoMentionGateForActiveWorkflows:
    """Active workflows (interactive, pending, conversation) do NOT
    require a mention — the user is replying to a bot prompt.
    """

    @pytest.mark.asyncio
    async def test_interactive_no_mention_still_dispatches(self):
        """has_interactive=True → dispatched even without mention."""
        import crewai_productfeature_planner.apis.slack._thread_state as ts
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            _interactive_runs,
            _lock as _ih_lock,
        )

        ts._bot_user_id = _BOT_ID

        with _ih_lock:
            _interactive_runs["run_gate"] = {
                "channel": "C_GATE3",
                "thread_ts": "10001.0",
            }

        try:
            payload = _event_payload(
                {
                    "type": "message",
                    "channel": "C_GATE3",
                    "user": "U_NOBOT",
                    "text": "approve",
                    "ts": "10001.1",
                    "thread_ts": "10001.0",
                },
                event_id="Ev_GATE5",
            )
            with patch(f"{_ER}._handle_thread_message") as mock_thread:
                resp = await _post(payload)
            assert resp.status_code == 200
            mock_thread.assert_called_once()
        finally:
            with _ih_lock:
                _interactive_runs.pop("run_gate", None)

    @pytest.mark.asyncio
    async def test_pending_no_mention_still_dispatches(self):
        """has_pending=True → dispatched even without mention."""
        import crewai_productfeature_planner.apis.slack._thread_state as ts

        ts._bot_user_id = _BOT_ID

        payload = _event_payload(
            {
                "type": "message",
                "channel": "C_GATE4",
                "user": "U_PENDING",
                "text": "My Project Name",
                "ts": "11001.1",
                "thread_ts": "11001.0",
            },
            event_id="Ev_GATE6",
        )
        with patch(
            f"{_SM}.has_pending_state", return_value=True,
        ), patch(f"{_ER}._handle_thread_message") as mock_thread:
            resp = await _post(payload)
        assert resp.status_code == 200
        mock_thread.assert_called_once()


# ======================================================================
# get_thread_owner — unified thread ownership lookup
# ======================================================================


class TestGetThreadOwner:
    """get_thread_owner checks pending creates, setup wizard, and
    memory entries to determine who owns a given thread.
    """

    def test_no_pending_state_returns_none(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_thread_owner,
        )
        assert get_thread_owner("C1", "T1") is None

    def test_pending_create_returns_owner(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_thread_owner,
            mark_pending_create,
        )
        mark_pending_create("U_ADMIN", "C1", "T1")
        assert get_thread_owner("C1", "T1") == "U_ADMIN"

    def test_setup_wizard_returns_owner(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_thread_owner,
        )
        import crewai_productfeature_planner.apis.slack.session_manager as sm
        with sm._lock:
            sm._pending_project_setup["U_ADMIN"] = {
                "channel": "C1", "thread_ts": "T1",
                "project_id": "proj-1", "project_name": "Test",
                "step": "confluence_space_key",
            }
        assert get_thread_owner("C1", "T1") == "U_ADMIN"

    def test_memory_entry_returns_owner(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_thread_owner,
            mark_pending_memory,
        )
        mark_pending_memory("U_ADMIN", "C1", "T1", "knowledge", "proj-1")
        assert get_thread_owner("C1", "T1") == "U_ADMIN"

    def test_different_thread_returns_none(self):
        from crewai_productfeature_planner.apis.slack.session_manager import (
            get_thread_owner,
            mark_pending_create,
        )
        mark_pending_create("U_ADMIN", "C1", "T1")
        assert get_thread_owner("C1", "T_OTHER") is None


# ======================================================================
# Thread session isolation — setup wizard and memory entries
# ======================================================================


class TestThreadOwnerGuard:
    """Non-owner users replying in threads with active pending state
    (setup wizard, memory entries) are silently ignored.
    """

    def test_other_user_ignored_during_setup_wizard(self):
        """User B's reply in a thread where User A is in the setup
        wizard is silently ignored — no _interpret_and_act.
        """
        import crewai_productfeature_planner.apis.slack.events_router as er
        import crewai_productfeature_planner.apis.slack.session_manager as sm

        with sm._lock:
            sm._pending_project_setup["U_ADMIN"] = {
                "channel": "C1", "thread_ts": "T1",
                "project_id": "proj-1", "project_name": "Test",
                "step": "confluence_space_key",
            }

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_BYSTANDER",
            "text": "nice",
            "ts": "T1.2",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._interpret_and_act") as mock_interpret, \
             patch(f"{_ER}._handle_project_setup_reply") as mock_setup:
            er._handle_thread_message(event)

        mock_interpret.assert_not_called()
        mock_setup.assert_not_called()

    def test_other_user_ignored_during_memory_entry(self):
        """User B's reply in a thread where User A is typing memory
        entries is silently ignored.
        """
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.session_manager import (
            mark_pending_memory,
        )

        mark_pending_memory("U_ADMIN", "C1", "T1", "knowledge", "proj-1")

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_BYSTANDER",
            "text": "nice",
            "ts": "T1.3",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._interpret_and_act") as mock_interpret, \
             patch(f"{_ER}.handle_memory_reply") as mock_memory:
            er._handle_thread_message(event)

        mock_interpret.assert_not_called()
        mock_memory.assert_not_called()

    def test_owner_can_still_reply_in_own_setup_thread(self):
        """The setup wizard owner can still provide input."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        import crewai_productfeature_planner.apis.slack.session_manager as sm

        with sm._lock:
            sm._pending_project_setup["U_ADMIN"] = {
                "channel": "C1", "thread_ts": "T1",
                "project_id": "proj-1", "project_name": "Test",
                "step": "confluence_space_key",
            }

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_ADMIN",
            "text": "MY_SPACE_KEY",
            "ts": "T1.4",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        with patch(f"{_ER}._handle_project_setup_reply") as mock_setup, \
             patch(f"{_ER}._interpret_and_act") as mock_interpret:
            er._handle_thread_message(event)

        mock_setup.assert_called_once()
        mock_interpret.assert_not_called()


# ======================================================================
# Thread session isolation — interactive runs and exec feedback
# ======================================================================


class TestInteractiveRunIsolation:
    """Interactive run threads reject messages from non-owner users."""

    def test_other_user_ignored_during_interactive_run(self):
        """User B's reply in a thread with an interactive run owned by
        User A is silently ignored.
        """
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            _interactive_runs,
            _lock as _ih_lock,
        )

        with _ih_lock:
            _interactive_runs["run-1"] = {
                "channel": "C1",
                "thread_ts": "T1",
                "user": "U_ADMIN",
                "pending_action": "manual_refinement",
            }

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_BYSTANDER",
            "text": "nice",
            "ts": "T1.5",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        _IH = "crewai_productfeature_planner.apis.slack.interactive_handlers"
        try:
            with patch(f"{_ER}._interpret_and_act") as mock_interp, \
                 patch(f"{_IH}.submit_manual_refinement") as mock_submit, \
                 patch(f"{_IH}.queue_feedback") as mock_queue:
                er._handle_thread_message(event)

            mock_interp.assert_not_called()
            mock_submit.assert_not_called()
            mock_queue.assert_not_called()
        finally:
            with _ih_lock:
                _interactive_runs.pop("run-1", None)

    def test_owner_can_reply_in_interactive_run_thread(self):
        """The owner can still submit manual refinement feedback."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            _interactive_runs,
            _lock as _ih_lock,
        )

        with _ih_lock:
            _interactive_runs["run-2"] = {
                "channel": "C1",
                "thread_ts": "T1",
                "user": "U_ADMIN",
                "pending_action": "manual_refinement",
            }

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_ADMIN",
            "text": "refine the idea further",
            "ts": "T1.6",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        _IH = "crewai_productfeature_planner.apis.slack.interactive_handlers"
        try:
            with patch(f"{_IH}.submit_manual_refinement") as mock_submit, \
                 patch(f"{_ER}.append_to_thread"), \
                 patch(f"{_ER}._interpret_and_act") as mock_interp:
                er._handle_thread_message(event)

            mock_submit.assert_called_once_with("run-2", "refine the idea further")
            mock_interp.assert_not_called()
        finally:
            with _ih_lock:
                _interactive_runs.pop("run-2", None)

    def test_other_user_ignored_during_exec_feedback(self):
        """User B's reply in a thread with pending exec feedback
        owned by User A is silently ignored.
        """
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock as _ef_lock,
            _pending_exec_feedback,
        )

        with _ef_lock:
            _pending_exec_feedback["run-3"] = {
                "channel": "C1",
                "thread_ts": "T1",
                "user": "U_ADMIN",
            }

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_BYSTANDER",
            "text": "nice",
            "ts": "T1.7",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        _FH = "crewai_productfeature_planner.apis.slack._flow_handlers"
        try:
            with patch(f"{_ER}._interpret_and_act") as mock_interp, \
                 patch(f"{_FH}.resolve_exec_feedback") as mock_resolve:
                er._handle_thread_message(event)

            mock_interp.assert_not_called()
            mock_resolve.assert_not_called()
        finally:
            with _ef_lock:
                _pending_exec_feedback.pop("run-3", None)

    def test_owner_can_reply_to_exec_feedback(self):
        """The owner can still provide exec summary feedback."""
        import crewai_productfeature_planner.apis.slack.events_router as er
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock as _ef_lock,
            _pending_exec_feedback,
        )

        with _ef_lock:
            _pending_exec_feedback["run-4"] = {
                "channel": "C1",
                "thread_ts": "T1",
                "user": "U_ADMIN",
            }

        event = {
            "type": "message",
            "channel": "C1",
            "user": "U_ADMIN",
            "text": "add more details",
            "ts": "T1.8",
            "thread_ts": "T1",
            "_team_id": "TEAM1",
        }

        _FH = "crewai_productfeature_planner.apis.slack._flow_handlers"
        try:
            with patch(f"{_FH}.resolve_exec_feedback") as mock_resolve, \
                 patch(f"{_ER}.append_to_thread"), \
                 patch(f"{_ER}._interpret_and_act") as mock_interp:
                er._handle_thread_message(event)

            mock_resolve.assert_called_once_with("run-4", "feedback", "add more details")
            mock_interp.assert_not_called()
        finally:
            with _ef_lock:
                _pending_exec_feedback.pop("run-4", None)
