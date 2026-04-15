"""Tests for crewai_bus_fix — CrewAI event-bus recovery."""

import atexit
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest


# ── Module under test ──────────────────────────────────────────────
from crewai_productfeature_planner.scripts.crewai_bus_fix import (
    _is_executor_alive,
    ensure_crewai_event_bus,
    install_crewai_bus_fix,
)


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _restore_event_bus():
    """Ensure the real CrewAI event bus is restored after each test."""
    from crewai.events.event_bus import crewai_event_bus as bus

    orig_shutting_down = bus._shutting_down
    orig_executor = bus._sync_executor
    yield
    bus._shutting_down = orig_shutting_down
    bus._sync_executor = orig_executor


# ── _is_executor_alive ─────────────────────────────────────────────

class TestIsExecutorAlive:
    def test_live_executor(self):
        bus = MagicMock()
        bus._sync_executor = ThreadPoolExecutor(max_workers=1)
        assert _is_executor_alive(bus) is True
        bus._sync_executor.shutdown(wait=False)

    def test_dead_executor(self):
        bus = MagicMock()
        executor = ThreadPoolExecutor(max_workers=1)
        executor.shutdown(wait=True)
        bus._sync_executor = executor
        assert _is_executor_alive(bus) is False

    def test_no_executor_attr(self):
        bus = object()
        assert _is_executor_alive(bus) is False


# ── ensure_crewai_event_bus ────────────────────────────────────────

class TestEnsureCrewaiEventBus:
    def test_noop_when_healthy(self):
        """When the bus is healthy, ensure is a no-op."""
        from crewai.events.event_bus import crewai_event_bus as bus

        bus._shutting_down = False
        orig_executor = bus._sync_executor
        ensure_crewai_event_bus()
        # Executor should be the same object (not replaced)
        assert bus._sync_executor is orig_executor

    def test_reinitialises_after_shutdown_flag(self):
        """When _shutting_down is True, ensure reinitialises."""
        from crewai.events.event_bus import crewai_event_bus as bus

        bus._shutting_down = True
        old_executor = bus._sync_executor
        ensure_crewai_event_bus()
        assert bus._shutting_down is False
        assert _is_executor_alive(bus)

    def test_reinitialises_after_dead_executor(self):
        """When the executor is dead, ensure reinitialises."""
        from crewai.events.event_bus import crewai_event_bus as bus

        bus._sync_executor.shutdown(wait=False)
        bus._shutting_down = False
        ensure_crewai_event_bus()
        assert _is_executor_alive(bus)

    def test_safe_to_call_multiple_times(self):
        """Calling ensure multiple times is safe."""
        ensure_crewai_event_bus()
        ensure_crewai_event_bus()
        ensure_crewai_event_bus()
        from crewai.events.event_bus import crewai_event_bus as bus
        assert _is_executor_alive(bus)


# ── install_crewai_bus_fix ─────────────────────────────────────────

class TestInstallCrewaiBusFix:
    def test_unregisters_atexit_and_ensures_bus(self):
        """install_crewai_bus_fix unregisters atexit and ensures bus."""
        from crewai.events.event_bus import crewai_event_bus as bus

        bus._shutting_down = True
        with patch("atexit.unregister") as mock_unreg:
            install_crewai_bus_fix()
        # Called once in _unregister_crewai_atexit, and once
        # defensively after _initialize() inside ensure_crewai_event_bus.
        assert mock_unreg.call_count == 2
        mock_unreg.assert_called_with(bus.shutdown)
        assert bus._shutting_down is False
        assert _is_executor_alive(bus)

    def test_idempotent(self):
        """Calling install twice is safe."""
        with patch("atexit.unregister"):
            install_crewai_bus_fix()
            install_crewai_bus_fix()
        from crewai.events.event_bus import crewai_event_bus as bus
        assert _is_executor_alive(bus)
