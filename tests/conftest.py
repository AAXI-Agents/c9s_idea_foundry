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
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from unittest.mock import MagicMock, patch

import pytest

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
