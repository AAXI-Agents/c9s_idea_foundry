"""Tests for ``scripts.setup_mongodb`` — collection & index bootstrapping."""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.scripts.setup_mongodb import (
    ALL_COLLECTIONS,
    _COLLECTION_INDEXES,
    ensure_collections,
)


_MODULE = "crewai_productfeature_planner.scripts.setup_mongodb"


@pytest.fixture()
def mock_db():
    """Return a fresh MagicMock database with sensible defaults."""
    db = MagicMock()
    db.list_collection_names.return_value = []
    return db


# ── ALL_COLLECTIONS list ─────────────────────────────────────


class TestAllCollections:
    """Verify the expected collections are listed."""

    EXPECTED = {
        "agentInteraction",
        "crewJobs",
        "leases",
        "userSession",
        "userSuggestions",
        "userPreferences",
        "productRequirements",
        "slackOAuth",
        "projectConfig",
        "projectMemory",
        "workingIdeas",
    }

    def test_contains_all_expected(self):
        assert set(ALL_COLLECTIONS) == self.EXPECTED

    def test_matches_index_map_keys(self):
        assert set(ALL_COLLECTIONS) == set(_COLLECTION_INDEXES.keys())


# ── ensure_collections ───────────────────────────────────────


class TestEnsureCollections:
    """Tests for the ``ensure_collections`` startup function."""

    def test_creates_missing_collections(self, mock_db):
        mock_db.list_collection_names.return_value = []

        with patch(f"{_MODULE}.get_db", return_value=mock_db):
            created = ensure_collections()

        assert created == len(ALL_COLLECTIONS)
        for name in ALL_COLLECTIONS:
            mock_db.create_collection.assert_any_call(name)

    def test_skips_existing_collections(self, mock_db):
        mock_db.list_collection_names.return_value = list(ALL_COLLECTIONS)

        with patch(f"{_MODULE}.get_db", return_value=mock_db):
            created = ensure_collections()

        assert created == 0
        mock_db.create_collection.assert_not_called()

    def test_creates_only_missing(self, mock_db):
        existing = ["crewJobs", "workingIdeas"]
        mock_db.list_collection_names.return_value = existing

        with patch(f"{_MODULE}.get_db", return_value=mock_db):
            created = ensure_collections()

        expected_new = len(ALL_COLLECTIONS) - len(existing)
        assert created == expected_new
        for name in existing:
            # Should not try to create existing collections
            calls = [c for c in mock_db.create_collection.call_args_list if c.args == (name,)]
            assert len(calls) == 0

    def test_creates_indexes_for_all_collections(self, mock_db):
        """Each collection should have create_indexes called with its index list."""
        # Use separate mock objects per collection so assert_called_once works.
        col_mocks: dict[str, MagicMock] = {}
        for name in ALL_COLLECTIONS:
            col_mocks[name] = MagicMock()
        mock_db.__getitem__.side_effect = lambda n: col_mocks.get(n, MagicMock())
        mock_db.list_collection_names.return_value = list(ALL_COLLECTIONS)

        with patch(f"{_MODULE}.get_db", return_value=mock_db):
            ensure_collections()

        for name, indexes in _COLLECTION_INDEXES.items():
            if indexes:
                col_mocks[name].create_indexes.assert_called_once_with(indexes)

    def test_create_collection_error_continues(self, mock_db):
        """A failed collection creation should not abort the rest."""
        mock_db.list_collection_names.return_value = []
        mock_db.create_collection.side_effect = PyMongoError("disk full")

        with patch(f"{_MODULE}.get_db", return_value=mock_db):
            created = ensure_collections()

        assert created == 0
        # All collections should still be attempted
        assert mock_db.create_collection.call_count == len(ALL_COLLECTIONS)

    def test_index_creation_error_continues(self, mock_db):
        """A failed index creation should not abort the rest."""
        col_mocks: dict[str, MagicMock] = {}
        for name in ALL_COLLECTIONS:
            col_mocks[name] = MagicMock()
        mock_db.__getitem__.side_effect = lambda n: col_mocks.get(n, MagicMock())
        mock_db.list_collection_names.return_value = list(ALL_COLLECTIONS)

        # Only the first collection's create_indexes raises
        first_col = ALL_COLLECTIONS[0]
        col_mocks[first_col].create_indexes.side_effect = PyMongoError("bad index")

        with patch(f"{_MODULE}.get_db", return_value=mock_db):
            created = ensure_collections()

        assert created == 0
        # Other collections' indexes should still be created
        for name in ALL_COLLECTIONS[1:]:
            indexes = _COLLECTION_INDEXES.get(name, [])
            if indexes:
                col_mocks[name].create_indexes.assert_called_once()

    def test_unique_indexes_defined(self):
        """Each collection should have at least one unique index for its primary key."""
        for name, indexes in _COLLECTION_INDEXES.items():
            unique_indexes = [idx for idx in indexes if idx.document.get("unique")]
            assert len(unique_indexes) >= 1, (
                f"Collection '{name}' has no unique index defined"
            )
