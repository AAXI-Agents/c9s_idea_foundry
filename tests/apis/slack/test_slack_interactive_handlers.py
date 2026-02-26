"""Tests for Slack interactive handlers — state management and callbacks."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ---- register / get / cleanup ----

def test_register_and_get():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        cleanup_interactive_run,
        get_interactive_run,
        register_interactive_run,
    )

    register_interactive_run("run1", "C1", "1234.0", "U1", "my idea")
    info = get_interactive_run("run1")
    assert info is not None
    assert info["channel"] == "C1"
    assert info["thread_ts"] == "1234.0"
    assert info["user"] == "U1"
    assert info["idea"] == "my idea"
    assert info["cancelled"] is False

    cleanup_interactive_run("run1")
    assert get_interactive_run("run1") is None


# ---- resolve_interaction ----

def test_resolve_interaction():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        cleanup_interactive_run,
        get_interactive_run,
        register_interactive_run,
        resolve_interaction,
    )

    register_interactive_run("run2", "C1", "1234.0", "U1", "idea")
    assert resolve_interaction("run2", "refinement_agent", "U1") is True

    info = get_interactive_run("run2")
    assert info["decision"] == "refinement_agent"
    assert info["event"].is_set()

    cleanup_interactive_run("run2")


def test_resolve_nonexistent():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        resolve_interaction,
    )

    assert resolve_interaction("nonexistent", "refinement_agent", "U1") is False


def test_resolve_cancel_sets_flag():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        cleanup_interactive_run,
        get_interactive_run,
        register_interactive_run,
        resolve_interaction,
    )

    register_interactive_run("run_c", "C1", "1234.0", "U1", "idea")
    resolve_interaction("run_c", "flow_cancel", "U1")
    info = get_interactive_run("run_c")
    assert info["cancelled"] is True
    cleanup_interactive_run("run_c")


# ---- submit_manual_refinement ----

def test_submit_manual_refinement():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _lock,
        _manual_refinement_text,
        cleanup_interactive_run,
        register_interactive_run,
        submit_manual_refinement,
    )

    register_interactive_run("run_m", "C1", "1234.0", "U1", "idea")
    assert submit_manual_refinement("run_m", "revised idea") is True

    with _lock:
        assert _manual_refinement_text.get("run_m") == "revised idea"

    cleanup_interactive_run("run_m")


def test_submit_manual_refinement_nonexistent():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        submit_manual_refinement,
    )

    assert submit_manual_refinement("nope", "text") is False


# ---- is_manual_refinement_active ----

def test_is_manual_refinement_active():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _interactive_runs,
        _lock,
        cleanup_interactive_run,
        is_manual_refinement_active,
        register_interactive_run,
    )

    register_interactive_run("run_mra", "C1", "1234.0", "U1", "idea")
    assert is_manual_refinement_active("run_mra") is False

    with _lock:
        _interactive_runs["run_mra"]["pending_action"] = "manual_refinement"
    assert is_manual_refinement_active("run_mra") is True

    cleanup_interactive_run("run_mra")


# ---- stale entry expiration ----

def test_stale_entries_expire():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _INTERACTIVE_TTL_SECONDS,
        _interactive_runs,
        _lock,
        get_interactive_run,
        register_interactive_run,
    )

    register_interactive_run("run_old", "C1", "1234.0", "U1", "idea")

    # Artificially age the entry
    with _lock:
        _interactive_runs["run_old"]["created_at"] = (
            time.time() - _INTERACTIVE_TTL_SECONDS - 10
        )

    # Registering a new one triggers expiry
    register_interactive_run("run_new", "C2", "5678.0", "U2", "idea2")
    assert get_interactive_run("run_old") is None
    assert get_interactive_run("run_new") is not None

    # Cleanup
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        cleanup_interactive_run,
    )
    cleanup_interactive_run("run_new")


# ---- _wait_for_decision with threading ----

def test_wait_for_decision_resolves():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _wait_for_decision,
        cleanup_interactive_run,
        register_interactive_run,
        resolve_interaction,
    )

    register_interactive_run("run_w", "C1", "1234.0", "U1", "idea")

    result = [None]

    def _wait():
        result[0] = _wait_for_decision("run_w", "test_action", timeout=5.0)

    t = threading.Thread(target=_wait)
    t.start()

    # Give the waiter time to start
    time.sleep(0.1)
    resolve_interaction("run_w", "idea_approve", "U1")
    t.join(timeout=5.0)

    assert result[0] == "idea_approve"
    cleanup_interactive_run("run_w")


def test_wait_for_decision_timeout():
    from crewai_productfeature_planner.apis.slack.interactive_handlers import (
        _wait_for_decision,
        cleanup_interactive_run,
        register_interactive_run,
    )

    register_interactive_run("run_to", "C1", "1234.0", "U1", "idea")
    result = _wait_for_decision("run_to", "test_action", timeout=0.1)
    assert result is None
    cleanup_interactive_run("run_to")


# ---- Block builders produce valid structures ----

def test_refinement_mode_blocks():
    from crewai_productfeature_planner.apis.slack.blocks import refinement_mode_blocks

    blocks = refinement_mode_blocks("run_b", "Build a fitness app")
    assert len(blocks) >= 3
    # Find actions block
    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    elements = actions[0]["elements"]
    action_ids = {e["action_id"] for e in elements}
    assert "refinement_agent" in action_ids
    assert "refinement_manual" in action_ids
    assert all(e["value"] == "run_b" for e in elements)


def test_idea_approval_blocks():
    from crewai_productfeature_planner.apis.slack.blocks import idea_approval_blocks

    blocks = idea_approval_blocks("run_b", "Refined idea text", "Original idea")
    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    action_ids = {e["action_id"] for e in actions[0]["elements"]}
    assert "idea_approve" in action_ids
    assert "idea_cancel" in action_ids


def test_requirements_approval_blocks():
    from crewai_productfeature_planner.apis.slack.blocks import requirements_approval_blocks

    blocks = requirements_approval_blocks("run_b", "Requirements text", 3)
    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    action_ids = {e["action_id"] for e in actions[0]["elements"]}
    assert "requirements_approve" in action_ids
    assert "requirements_cancel" in action_ids


def test_flow_started_blocks():
    from crewai_productfeature_planner.apis.slack.blocks import flow_started_blocks

    blocks = flow_started_blocks("run_b", "Test idea")
    assert any("run_b" in str(b) for b in blocks)


def test_flow_cancelled_blocks():
    from crewai_productfeature_planner.apis.slack.blocks import flow_cancelled_blocks

    blocks = flow_cancelled_blocks("run_b", "refinement")
    assert any("cancelled" in str(b).lower() for b in blocks)


def test_manual_refinement_prompt_blocks():
    from crewai_productfeature_planner.apis.slack.blocks import manual_refinement_prompt_blocks

    blocks = manual_refinement_prompt_blocks("run_b", "My idea", 2)
    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    action_ids = {e["action_id"] for e in actions[0]["elements"]}
    assert "idea_approve" in action_ids


# ---- Long text truncation in blocks ----

def test_blocks_truncate_long_text():
    from crewai_productfeature_planner.apis.slack.blocks import (
        idea_approval_blocks,
        requirements_approval_blocks,
    )

    long_text = "x" * 5000
    idea_blocks = idea_approval_blocks("run_t", long_text, "original")
    # The section block text should be truncated
    section_texts = [
        b["text"]["text"] for b in idea_blocks if b.get("type") == "section"
    ]
    assert all(len(t) <= 2100 for t in section_texts)

    req_blocks = requirements_approval_blocks("run_t", long_text, 1)
    section_texts = [
        b["text"]["text"] for b in req_blocks if b.get("type") == "section"
    ]
    assert all(len(t) <= 3000 for t in section_texts)
