"""Global test fixtures — prevent any real MongoDB connections.

Every test in the suite is protected by the ``_no_real_mongodb``
autouse fixture which:

1. Patches ``get_db`` to return a fresh ``MagicMock`` database,
   so **no** function can accidentally reach a live MongoDB.
2. Resets the shared ``_client`` singleton in ``mongodb.client``
   after each test, preventing connection leakage between tests.

Individual tests that need finer-grained control over ``get_db``
(e.g. ``@patch("...repository.get_db")``) will simply shadow
this fixture — their decorator-level patch takes precedence.
"""

from unittest.mock import MagicMock, patch

import pytest

import crewai_productfeature_planner.mongodb.client as _mongo_client


@pytest.fixture(autouse=True)
def _no_real_mongodb():
    """Prevent any test from reaching a live MongoDB instance.

    Patches ``get_db`` at the **client module level** so every
    downstream import (``repository.get_db``, ``flows.prd_flow.*``,
    ``main.*``, etc.) resolves to a ``MagicMock()``.

    After the test, the ``_client`` singleton is forcibly cleared
    to avoid a stale ``MongoClient`` persisting across tests.
    """
    mock_db = MagicMock()
    with patch.object(_mongo_client, "get_db", return_value=mock_db):
        yield mock_db
    # Reset the module-level singleton so no real connection leaks
    if _mongo_client._client is not None:
        try:
            _mongo_client._client.close()
        except Exception:  # noqa: BLE001
            pass
        _mongo_client._client = None
