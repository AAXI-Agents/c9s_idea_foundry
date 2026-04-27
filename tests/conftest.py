"""Global test fixtures — prevent real MongoDB and HTTP connections.

Every test in the suite is protected by two **session-scoped** autouse
safety-net fixtures:

1. ``_no_real_mongodb`` — patches ``get_db`` at the client module
   **and** at every module that imports it via ``from … import get_db``,
   so the mock intercepts all call-sites, not just attribute lookups
   on the client module.  Session-scoped so the 9 ``patch.object``
   contexts are created once instead of for each of the 1600+ tests.
2. ``_no_real_http`` — patches ``urllib.request.urlopen`` to raise
   ``RuntimeError``, preventing real HTTP calls to Confluence,
   Jira, or any other external service.

Individual tests that need finer-grained control can shadow
these fixtures with their own patches.

.. note::
   CrewAI 1.9.x + newer starlette/sse-starlette versions produce
   deeply-nested pydantic model hierarchies that exceed the default
   recursion limit (1000) during ``model_rebuild``.  We raise it at
   import time so every test (and the conftest import chain) succeeds.
"""

import os as _os
import sys as _sys
_sys.setrecursionlimit(max(_sys.getrecursionlimit(), 5000))

# Store exit status so atexit handler can use it
_ci_exit_status = None


def pytest_sessionfinish(session, exitstatus):
    """Record exit status for the atexit handler."""
    global _ci_exit_status
    if _os.environ.get("CI"):
        _ci_exit_status = exitstatus


def pytest_unconfigure(config):
    """Force-exit in CI after all reporting is done to prevent background thread hangs."""
    if _ci_exit_status is not None:
        _os._exit(_ci_exit_status)


import logging
from logging.handlers import TimedRotatingFileHandler
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import crewai_productfeature_planner.mongodb.async_client as _async_mongo_client
import crewai_productfeature_planner.mongodb.client as _mongo_client
import crewai_productfeature_planner.mongodb as _mongo_pkg
import crewai_productfeature_planner.mongodb.working_ideas._common as _wi_repo
import crewai_productfeature_planner.mongodb.crew_jobs.repository as _cj_repo
import crewai_productfeature_planner.mongodb.product_requirements.repository as _pr_repo
import crewai_productfeature_planner.mongodb.agent_interactions.repository as _ai_repo
import crewai_productfeature_planner.mongodb.project_config.repository as _pc_repo
import crewai_productfeature_planner.mongodb.user_session as _us_repo
import crewai_productfeature_planner.main as _main_mod
import crewai_productfeature_planner.scripts.logging_config as _lc_mod
import crewai_productfeature_planner.scripts.setup_mongodb as _setup_mongo


def _make_mock_db() -> MagicMock:
    """Build a mock database whose collections return safe write-results.

    Reusable by any test that needs a *fresh* ``mock_db`` with no
    accumulated call history.
    """
    _write_result = MagicMock(
        modified_count=0,
        matched_count=0,
        upserted_id=None,
        inserted_id=None,
        acknowledged=True,
    )
    mock_db = MagicMock()
    _default_col = mock_db.__getitem__.return_value
    _default_col.update_one.return_value = _write_result
    _default_col.update_many.return_value = _write_result
    _default_col.insert_one.return_value = _write_result
    _default_col.delete_one.return_value = _write_result
    _default_col.find_one.return_value = None
    return mock_db


# All modules whose top-level ``get_db`` binding must be replaced.
_PATCH_TARGETS: list[object] = [
    _mongo_client,
    _mongo_pkg,
    _wi_repo,
    _cj_repo,
    _pr_repo,
    _ai_repo,
    _pc_repo,
    _us_repo,
    _main_mod,
    _setup_mongo,
]


@pytest.fixture(autouse=True, scope="session")
def _no_log_file(tmp_path_factory):
    """Prevent tests from writing to the production log file.

    Two complementary mechanisms:

    1. **Strip existing file handlers** from the project logger so
       intentional failure-path tests don't pollute ``logs/crewai.log``.
    2. **Redirect ``_LOG_DIR``** to a temporary directory so that if
       ``setup_logging()`` is re-invoked mid-session (e.g. after
       ``test_logging_config`` resets ``_configured``), any new file
       handler writes to temp instead of production.
    """
    safe_log_dir = tmp_path_factory.mktemp("test_logs")
    original_log_dir = _lc_mod._LOG_DIR
    _lc_mod._LOG_DIR = safe_log_dir

    proj_logger = logging.getLogger("crewai_productfeature_planner")
    removed: list[logging.Handler] = []
    for handler in list(proj_logger.handlers):
        if isinstance(handler, (logging.FileHandler, TimedRotatingFileHandler)):
            proj_logger.removeHandler(handler)
            removed.append(handler)
    yield
    _lc_mod._LOG_DIR = original_log_dir
    for handler in removed:
        proj_logger.addHandler(handler)


@pytest.fixture(autouse=True, scope="session")
def _no_real_mongodb():
    """Prevent any test from reaching a live MongoDB instance.

    **Session-scoped** — the nine ``patch.object`` context-managers are
    entered once for the entire test run instead of once per test,
    eliminating ~14 s of cumulative fixture setup/teardown overhead.

    The mock database is configured so that common write-operation
    results (``update_one``, ``insert_one``, etc.) return objects
    whose ``modified_count`` / ``upserted_id`` / ``inserted_id``
    attributes are concrete values (not *MagicMock*), preventing
    ``TypeError`` on comparisons like ``result.modified_count > 0``.

    Because this is session-scoped the mock accumulates call history
    across the entire run.  Tests that need to inspect calls should
    use ``fresh_mock_db`` (function-scoped) or patch ``get_db``
    themselves.
    """
    mock_db = _make_mock_db()

    patchers = [
        patch.object(mod, "get_db", return_value=mock_db)
        for mod in _PATCH_TARGETS
    ]
    for p in patchers:
        p.start()
    yield mock_db
    for p in reversed(patchers):
        p.stop()
    # Reset the module-level singleton so no real connection leaks
    if _mongo_client._client is not None:
        try:
            _mongo_client._client.close()
        except Exception:  # noqa: BLE001
            pass
        _mongo_client._client = None


@pytest.fixture(autouse=True, scope="session")
def _no_real_async_mongodb():
    """Prevent any test from reaching a live MongoDB via Motor.

    Patches ``get_async_db`` on the async_client module so no real
    ``AsyncIOMotorClient`` is ever created.
    """
    mock_async_db = MagicMock()
    with patch.object(
        _async_mongo_client, "get_async_db", return_value=mock_async_db
    ):
        yield mock_async_db
    # Reset singleton
    _async_mongo_client._async_client = None


@pytest.fixture(autouse=True, scope="session")
def _no_real_slack():
    """Return a mock Slack client so the circuit breaker in
    ``_handle_thread_message`` does not block tests that lack a token."""
    import crewai_productfeature_planner.tools.slack_tools as _slack_tools
    mock_client = MagicMock()
    with patch.object(_slack_tools, "_get_slack_client", return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def _clear_response_cache():
    """Clear the API response cache between tests."""
    yield
    from crewai_productfeature_planner.apis._response_cache import response_cache
    response_cache.invalidate()


@pytest.fixture()
def fresh_mock_db():
    """Provide a *fresh* mock database with clean call history.

    Use this in any test that needs to inspect ``mock_db`` calls
    without interference from other tests.  The fixture temporarily
    overrides the session-scoped ``_no_real_mongodb`` patches for
    the duration of the test.
    """
    mock_db = _make_mock_db()
    patchers = [
        patch.object(mod, "get_db", return_value=mock_db)
        for mod in _PATCH_TARGETS
    ]
    for p in patchers:
        p.start()
    yield mock_db
    for p in reversed(patchers):
        p.stop()


@pytest.fixture(autouse=True, scope="session")
def _no_real_http():
    """Prevent any test from making real HTTP requests.

    **Session-scoped** — the patch is entered once for the entire suite
    instead of once per test.
    """
    with patch(
        "urllib.request.urlopen",
        side_effect=RuntimeError(
            "Real HTTP calls are blocked in tests — "
            "mock urllib.request.urlopen or the tool function instead"
        ),
    ):
        yield


@pytest.fixture(autouse=True, scope="session")
def _warm_crewai_agent():
    """Pre-warm the CrewAI Agent pydantic model hierarchy.

    The **first** ``Agent()`` instantiation in a process triggers
    pydantic ``model_rebuild()`` across the entire Agent class tree,
    costing ~1.2 s.  Subsequent instantiations only cost ~0.12 s.

    By creating (and discarding) one throwaway Agent here, every
    test that later calls ``create_*()`` agent factories avoids
    the cold-start penalty.
    """
    from crewai import Agent
    Agent(
        role="_warmup",
        goal="_warmup",
        backstory="_warmup",
        llm="openai/gpt-4o-mini",
        verbose=False,
    )
