"""Shared fixtures for working_ideas repository tests.

Eliminates the repeated 4-line mock-chain boilerplate that appeared in
every test: ``mock_collection → mock_db → mock_get_db.return_value``.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def wi_mocks():
    """Patch ``get_db`` and yield ``(mock_collection, mock_db)``.

    The fixture builds the standard mock chain that most tests need:

    * ``mock_collection`` — the collection mock returned by
      ``mock_db[WORKING_COLLECTION]``.  Tests can customise return
      values (e.g. ``mock_collection.find_one.return_value = {...}``)
      before calling the function under test.
    * ``mock_db`` — the database mock returned by ``get_db()``.

    Default write-operation results use safe concrete values
    (``upserted_id=None, modified_count=0, …``) so comparisons like
    ``result.modified_count > 0`` work without extra setup.
    """
    _write_result = MagicMock(
        modified_count=0,
        matched_count=0,
        upserted_id=None,
        inserted_id=None,
        acknowledged=True,
    )

    mock_collection = MagicMock()
    mock_collection.update_one.return_value = _write_result
    mock_collection.update_many.return_value = _write_result
    mock_collection.insert_one.return_value = _write_result
    mock_collection.delete_one.return_value = _write_result
    mock_collection.find_one.return_value = None
    mock_collection.find.return_value = []

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch(
        "crewai_productfeature_planner.mongodb.working_ideas._common.get_db",
        return_value=mock_db,
    ):
        yield mock_collection, mock_db
