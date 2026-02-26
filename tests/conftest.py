"""Global test fixtures — prevent real MongoDB and HTTP connections.

Every test in the suite is protected by two autouse fixtures:

1. ``_no_real_mongodb`` — patches ``get_db`` at the client module
   **and** at every module that imports it via ``from … import get_db``,
   so the mock intercepts all call-sites, not just attribute lookups
   on the client module.
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
import crewai_productfeature_planner.mongodb.working_ideas.repository as _wi_repo
import crewai_productfeature_planner.mongodb.crew_jobs.repository as _cj_repo
import crewai_productfeature_planner.mongodb.product_requirements.repository as _pr_repo
import crewai_productfeature_planner.main as _main_mod
import crewai_productfeature_planner.scripts.logging_config as _lc_mod


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


@pytest.fixture(autouse=True)
def _no_real_mongodb():
    """Prevent any test from reaching a live MongoDB instance.

    Patches ``get_db`` at the **client module level** *and* in every
    module that binds it via ``from … import get_db`` at import time.
    This ensures that even direct calls through locally-bound names
    (e.g. ``repository.get_db()``) resolve to the same ``MagicMock()``.

    The mock database is configured so that common write-operation
    results (``update_one``, ``insert_one``, etc.) return objects
    whose ``modified_count`` / ``upserted_id`` / ``inserted_id``
    attributes are concrete values (not *MagicMock*), preventing
    ``TypeError`` on comparisons like ``result.modified_count > 0``.

    After the test, the ``_client`` singleton is forcibly cleared
    to avoid a stale ``MongoClient`` persisting across tests.
    """
    # Build a mock result that won't explode on integer comparisons
    _write_result = MagicMock(
        modified_count=0,
        matched_count=0,
        upserted_id=None,
        inserted_id=None,
        acknowledged=True,
    )
    mock_db = MagicMock()
    # Any collection returned by mock_db[name] should yield the safe
    # write-result for mutating operations.
    _default_col = mock_db.__getitem__.return_value
    _default_col.update_one.return_value = _write_result
    _default_col.update_many.return_value = _write_result
    _default_col.insert_one.return_value = _write_result
    _default_col.delete_one.return_value = _write_result
    _default_col.find_one.return_value = None

    with (
        patch.object(_mongo_client, "get_db", return_value=mock_db),
        patch.object(_mongo_pkg, "get_db", return_value=mock_db),
        patch.object(_wi_repo, "get_db", return_value=mock_db),
        patch.object(_cj_repo, "get_db", return_value=mock_db),
        patch.object(_pr_repo, "get_db", return_value=mock_db),
        patch.object(_main_mod, "get_db", return_value=mock_db),
    ):
        yield mock_db
    # Reset the module-level singleton so no real connection leaks
    if _mongo_client._client is not None:
        try:
            _mongo_client._client.close()
        except Exception:  # noqa: BLE001
            pass
        _mongo_client._client = None


@pytest.fixture(autouse=True)
def _no_real_http():
    """Prevent any test from making real HTTP requests.

    Patches ``urllib.request.urlopen`` globally so calls to
    Confluence, Jira, or any external service raise immediately
    instead of leaking real data.
    """
    with patch(
        "urllib.request.urlopen",
        side_effect=RuntimeError(
            "Real HTTP calls are blocked in tests — "
            "mock urllib.request.urlopen or the tool function instead"
        ),
    ):
        yield
