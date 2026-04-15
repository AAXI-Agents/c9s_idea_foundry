"""Workaround for CrewAI event-bus shutdown corruption.

The CrewAI ``crewai_event_bus`` singleton registers an ``atexit``
handler that permanently shuts down its internal
``ThreadPoolExecutor``.  In long-running server processes, this makes
the event bus unusable after any shutdown signal, process fork, or
stale-atexit trigger — all subsequent ``crew.kickoff()`` calls crash
with ``RuntimeError: cannot schedule new futures after shutdown``.

This module provides :func:`ensure_crewai_event_bus` which detects
a dead event bus and reinitialises its internal state so flows can
continue to run.

Call it once before each ``crew.kickoff()`` or at server startup.
"""

from __future__ import annotations

import atexit
import threading
from concurrent.futures import ThreadPoolExecutor

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_fix_lock = threading.Lock()


def _is_executor_alive(bus) -> bool:
    """Return True if the event bus's sync executor can accept work."""
    executor: ThreadPoolExecutor | None = getattr(bus, "_sync_executor", None)
    if executor is None:
        return False
    # ThreadPoolExecutor sets _shutdown = True after .shutdown()
    return not getattr(executor, "_shutdown", True)


def ensure_crewai_event_bus() -> None:
    """Ensure the CrewAI event bus is alive and can emit events.

    If the ``_sync_executor`` has been shut down (e.g. by an atexit
    handler or a prior server restart), this function reinitialises
    the executor and event-loop thread so that subsequent
    ``crew.kickoff()`` calls succeed.

    Safe to call multiple times — it's a no-op when the bus is healthy.
    """
    from crewai.events.event_bus import crewai_event_bus as bus

    if _is_executor_alive(bus) and not bus._shutting_down:
        return  # bus is healthy

    with _fix_lock:
        # Double-check after acquiring the lock
        if _is_executor_alive(bus) and not bus._shutting_down:
            return

        logger.warning(
            "[CrewAI-BusFix] Event bus is dead (_shutting_down=%s, "
            "executor_alive=%s) — reinitialising",
            bus._shutting_down,
            _is_executor_alive(bus),
        )

        # Reinitialise the event bus.  _initialize() resets all
        # internal state including _shutting_down, creates a fresh
        # ThreadPoolExecutor, and starts a new event-loop thread.
        bus._initialize()

        # Defensively remove the atexit handler again — while
        # _initialize() itself doesn't re-register it, future
        # CrewAI versions might.
        try:
            atexit.unregister(bus.shutdown)
        except Exception:
            pass

        logger.info(
            "[CrewAI-BusFix] Event bus reinitialised successfully "
            "(executor_alive=%s)",
            _is_executor_alive(bus),
        )


def _unregister_crewai_atexit() -> None:
    """Remove the CrewAI event bus atexit handler.

    The ``atexit.register(crewai_event_bus.shutdown)`` call in
    ``crewai/events/event_bus.py`` poisons the event bus when
    Python's atexit hooks fire (e.g. during a ``SIGTERM`` that
    doesn't immediately kill the process).  By unregistering it,
    we prevent the event bus from being shut down at process exit
    — for a long-running server this is harmless since the process
    is about to terminate anyway.
    """
    from crewai.events.event_bus import crewai_event_bus as bus

    try:
        atexit.unregister(bus.shutdown)
        logger.debug("[CrewAI-BusFix] Unregistered atexit shutdown handler")
    except Exception:
        # atexit.unregister silently ignores unregistered functions,
        # but guard against unexpected issues.
        pass


def install_crewai_bus_fix() -> None:
    """One-time setup: unregister the atexit handler and ensure the bus.

    Call this at server startup (in the FastAPI lifespan) to prevent
    future corruption and to repair any leftover state from a prior
    dirty shutdown.
    """
    _unregister_crewai_atexit()
    ensure_crewai_event_bus()
