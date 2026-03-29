"""Tests for v0.42.1 — archive stops active flows.

Covers:
1. FlowCancelled exception and cancel registry in shared.py
2. _unblock_gates_for_cancel releases pending approval gates
3. execute_archive_idea signals cancellation
4. run_prd_flow catches FlowCancelled and sets archived status
5. check_cancelled raises FlowCancelled when event is set
6. kick_off_prd_flow registers cancel event
7. get_run_documents excludes archived status
8. archive_stale_jobs_on_startup cleans up stale crew jobs
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# 1. FlowCancelled exception + cancel registry
# ===========================================================================


class TestCancelRegistry:
    """Cancel event registry in shared.py."""

    def test_request_cancel_sets_event(self):
        from crewai_productfeature_planner.apis.shared import (
            cancel_events,
            request_cancel,
            is_cancelled,
        )
        evt = threading.Event()
        cancel_events["test-1"] = evt
        try:
            assert not is_cancelled("test-1")
            request_cancel("test-1")
            assert is_cancelled("test-1")
            assert evt.is_set()
        finally:
            cancel_events.pop("test-1", None)

    def test_request_cancel_missing_run_id(self):
        from crewai_productfeature_planner.apis.shared import cancel_events, request_cancel
        # Should not raise; creates the event and sets it
        request_cancel("nonexistent-run")
        assert cancel_events["nonexistent-run"].is_set()
        cancel_events.pop("nonexistent-run", None)

    def test_is_cancelled_missing_run_id(self):
        from crewai_productfeature_planner.apis.shared import cancel_events, is_cancelled
        cancel_events.pop("nonexistent-run", None)  # ensure clean state
        assert not is_cancelled("nonexistent-run")

    def test_check_cancelled_raises(self):
        from crewai_productfeature_planner.apis.shared import (
            FlowCancelled,
            cancel_events,
            check_cancelled,
        )
        evt = threading.Event()
        evt.set()
        cancel_events["test-2"] = evt
        try:
            with pytest.raises(FlowCancelled):
                check_cancelled("test-2")
        finally:
            cancel_events.pop("test-2", None)

    def test_check_cancelled_noop_when_not_set(self):
        from crewai_productfeature_planner.apis.shared import (
            cancel_events,
            check_cancelled,
        )
        evt = threading.Event()
        cancel_events["test-3"] = evt
        try:
            # Should not raise
            check_cancelled("test-3")
        finally:
            cancel_events.pop("test-3", None)


# ===========================================================================
# 2. _unblock_gates_for_cancel
# ===========================================================================


class TestUnblockGates:
    """_unblock_gates_for_cancel sets all pending gate events."""

    def test_unblocks_exec_feedback_gate(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            _unblock_gates_for_cancel,
        )
        gate_event = threading.Event()
        with _exec_feedback_lock:
            _pending_exec_feedback["unblock-1"] = {
                "event": gate_event,
                "decision": None,
            }
        try:
            _unblock_gates_for_cancel("unblock-1")
            assert gate_event.is_set()
        finally:
            with _exec_feedback_lock:
                _pending_exec_feedback.pop("unblock-1", None)

    def test_unblocks_exec_completion_gate(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_completion_lock,
            _pending_exec_completion,
            _unblock_gates_for_cancel,
        )
        gate_event = threading.Event()
        with _exec_completion_lock:
            _pending_exec_completion["unblock-2"] = {
                "event": gate_event,
                "decision": None,
            }
        try:
            _unblock_gates_for_cancel("unblock-2")
            assert gate_event.is_set()
        finally:
            with _exec_completion_lock:
                _pending_exec_completion.pop("unblock-2", None)

    def test_unblocks_requirements_gate(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _requirements_approval_lock,
            _pending_requirements_approval,
            _unblock_gates_for_cancel,
        )
        gate_event = threading.Event()
        with _requirements_approval_lock:
            _pending_requirements_approval["unblock-3"] = {
                "event": gate_event,
                "decision": None,
            }
        try:
            _unblock_gates_for_cancel("unblock-3")
            assert gate_event.is_set()
        finally:
            with _requirements_approval_lock:
                _pending_requirements_approval.pop("unblock-3", None)

    def test_unblocks_approval_event(self):
        from crewai_productfeature_planner.apis.shared import approval_events
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _unblock_gates_for_cancel,
        )
        gate_event = threading.Event()
        approval_events["unblock-4"] = gate_event
        try:
            _unblock_gates_for_cancel("unblock-4")
            assert gate_event.is_set()
        finally:
            approval_events.pop("unblock-4", None)

    def test_noop_when_no_gates(self):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _unblock_gates_for_cancel,
        )
        # Should not raise
        _unblock_gates_for_cancel("no-gates-run")


# ===========================================================================
# 3. execute_archive_idea signals cancellation
# ===========================================================================


class TestArchiveSignalsCancel:
    """execute_archive_idea should signal cancel and unblock gates."""

    @patch("crewai_productfeature_planner.apis.slack._flow_handlers._post_refreshed_idea_list")
    @patch("crewai_productfeature_planner.apis.slack._flow_handlers._unblock_gates_for_cancel")
    @patch("crewai_productfeature_planner.apis.shared.request_cancel")
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_archive_calls_cancel(
        self, mock_client, mock_cancel, mock_unblock, mock_refresh,
    ):
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            execute_archive_idea,
        )

        mock_client.return_value = MagicMock()

        with (
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.repository.find_run_any_status",
                return_value={"run_id": "arch-1", "idea": "Test idea"},
            ),
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.repository.mark_archived",
            ),
            patch(
                "crewai_productfeature_planner.mongodb.crew_jobs.repository.update_job_status",
            ),
            patch(
                "crewai_productfeature_planner.scripts.project_knowledge.archive_idea_knowledge",
            ),
        ):
            execute_archive_idea("arch-1", "C1", "ts1", "U1")

        mock_cancel.assert_called_once_with("arch-1")
        mock_unblock.assert_called_once_with("arch-1")


# ===========================================================================
# 4. run_prd_flow catches FlowCancelled
# ===========================================================================


class TestRunPrdFlowCancelled:
    """run_prd_flow should catch FlowCancelled and set archived status."""

    @patch("crewai_productfeature_planner.apis.prd.service.update_job_started")
    @patch("crewai_productfeature_planner.apis.prd.service.update_job_completed")
    def test_flow_cancelled_sets_archived(self, mock_complete, mock_start):
        from crewai_productfeature_planner.apis.prd.service import run_prd_flow
        from crewai_productfeature_planner.apis.shared import (
            FlowCancelled,
            FlowRun,
            FlowStatus,
            cancel_events,
            runs,
        )

        run_id = "cancel-test-1"
        runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")

        with patch(
            "crewai_productfeature_planner.flows.prd_flow.PRDFlow"
        ) as MockFlow:
            mock_flow = MockFlow.return_value
            mock_flow.kickoff.side_effect = FlowCancelled("cancelled")
            mock_flow.state = MagicMock()
            mock_flow.state.run_id = run_id

            run_prd_flow(run_id, "test idea")

        run = runs[run_id]
        assert run.status == FlowStatus.FAILED
        assert "CANCELLED" in (run.error or "")
        mock_complete.assert_called_with(run_id, status="archived")

        # Cleanup
        runs.pop(run_id, None)
        cancel_events.pop(run_id, None)


# ===========================================================================
# 5. kick_off_prd_flow registers cancel event
# ===========================================================================


class TestKickOffRegistersCancel:
    """kick_off_prd_flow should create a cancel event in the registry."""

    @patch("crewai_productfeature_planner.apis.slack.router._run_slack_prd_flow")
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_cancel_event_registered(self, mock_client, mock_run):
        from crewai_productfeature_planner.apis.shared import cancel_events
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            kick_off_prd_flow,
        )

        mock_client.return_value = MagicMock()

        # Capture the run_id from the thread that gets started
        original_thread_init = threading.Thread.__init__

        captured_run_id = []

        def patched_init(self_thread, *args, **kwargs):
            name = kwargs.get("name", "")
            if name.startswith("slack-prd-"):
                # Extract run_id from thread name
                rid = name.replace("slack-prd-", "")
                captured_run_id.append(rid)
            original_thread_init(self_thread, *args, **kwargs)

        with patch.object(threading.Thread, "__init__", patched_init):
            with patch.object(threading.Thread, "start"):
                kick_off_prd_flow(
                    channel="C1",
                    thread_ts="ts1",
                    user="U1",
                    idea="test idea",
                    event_ts="ev1",
                )

        assert len(captured_run_id) == 1
        rid = captured_run_id[0]
        assert rid in cancel_events
        assert not cancel_events[rid].is_set()

        # Cleanup
        cancel_events.pop(rid, None)


# ===========================================================================
# 6. Integration: archive cancels a flow waiting on a gate
# ===========================================================================


class TestArchiveCancelsWaitingFlow:
    """Simulate a flow waiting on a gate and verify archive unblocks it."""

    def test_gate_unblocked_by_archive_cancel(self):
        from crewai_productfeature_planner.apis.shared import (
            cancel_events,
            check_cancelled,
            FlowCancelled,
        )
        from crewai_productfeature_planner.apis.slack._flow_handlers import (
            _exec_feedback_lock,
            _pending_exec_feedback,
            _unblock_gates_for_cancel,
        )

        run_id = "integ-1"
        gate_event = threading.Event()
        cancel_event = threading.Event()
        cancel_events[run_id] = cancel_event

        with _exec_feedback_lock:
            _pending_exec_feedback[run_id] = {
                "event": gate_event,
                "decision": None,
            }

        unblocked = threading.Event()
        cancelled_raised = []

        def flow_thread():
            """Simulate a flow thread waiting on a gate."""
            gate_event.wait(timeout=5.0)
            try:
                check_cancelled(run_id)
            except FlowCancelled:
                cancelled_raised.append(True)
            unblocked.set()

        t = threading.Thread(target=flow_thread, daemon=True)
        t.start()

        # Simulate archive action
        cancel_event.set()
        _unblock_gates_for_cancel(run_id)

        unblocked.wait(timeout=5.0)
        assert unblocked.is_set()
        assert cancelled_raised == [True]

        # Cleanup
        cancel_events.pop(run_id, None)
        with _exec_feedback_lock:
            _pending_exec_feedback.pop(run_id, None)


# ===========================================================================
# 7. get_run_documents excludes archived status
# ===========================================================================


class TestGetRunDocumentsArchived:
    """get_run_documents should not return archived documents."""

    @patch("crewai_productfeature_planner.mongodb.working_ideas._queries._common")
    def test_archived_excluded(self, mock_common):
        from crewai_productfeature_planner.mongodb.working_ideas._queries import (
            get_run_documents,
        )

        mock_db = MagicMock()
        mock_common.get_db.return_value = mock_db
        mock_db.__getitem__ = MagicMock(return_value=MagicMock())
        mock_db.__getitem__.return_value.find_one.return_value = None

        get_run_documents("test-archived")

        # Verify the query excludes both "completed" and "archived"
        call_args = mock_db.__getitem__.return_value.find_one.call_args
        query = call_args[0][0]
        assert query["status"] == {"$nin": ["completed", "archived"]}


# ===========================================================================
# 8. archive_stale_jobs_on_startup
# ===========================================================================


class TestArchiveStaleJobsOnStartup:
    """archive_stale_jobs_on_startup cleans up crew jobs for archived ideas."""

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
    def test_archives_stale_jobs(self, mock_get_db):
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            archive_stale_jobs_on_startup,
        )
        from bson import ObjectId

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        job_oid = ObjectId()
        mock_crew_jobs = MagicMock()
        mock_working_ideas = MagicMock()

        # crew_jobs.find returns a running job
        mock_crew_jobs.find.return_value = [
            {"_id": job_oid, "job_id": "stale-1"},
        ]
        # workingIdeas.find returns it as archived
        mock_working_ideas.find.return_value = [
            {"run_id": "stale-1"},
        ]

        def get_collection(name):
            if name == "crewJobs":
                return mock_crew_jobs
            if name == "workingIdeas":
                return mock_working_ideas
            return MagicMock()

        mock_db.__getitem__ = MagicMock(side_effect=get_collection)

        count = archive_stale_jobs_on_startup()
        assert count == 1

        # Verify the crew job was updated to archived
        mock_crew_jobs.update_one.assert_called_once()
        update_call = mock_crew_jobs.update_one.call_args
        assert update_call[0][0] == {"_id": job_oid}
        assert update_call[0][1]["$set"]["status"] == "archived"

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.repository.get_db")
    def test_noop_when_no_stale_jobs(self, mock_get_db):
        from crewai_productfeature_planner.mongodb.crew_jobs.repository import (
            archive_stale_jobs_on_startup,
        )

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.__getitem__ = MagicMock(return_value=MagicMock(
            find=MagicMock(return_value=[]),
        ))

        count = archive_stale_jobs_on_startup()
        assert count == 0
