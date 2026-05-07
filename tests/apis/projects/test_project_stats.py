"""Tests for project stats (ideas_in_progress / features_completed)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.projects._stats import (
    _IN_PROGRESS_STATUSES,
    compute_project_stats_batch,
    compute_single_project_stats,
)

_ASYNC_CLIENT = "crewai_productfeature_planner.mongodb.async_client.get_async_db"


def _patch_async_db():
    return patch(
        f"{_ASYNC_CLIENT}",
        new_callable=lambda: MagicMock,
    )


# ── compute_project_stats_batch ──────────────────────────────


class TestComputeProjectStatsBatch:
    @pytest.mark.asyncio
    async def test_empty_project_ids(self):
        result = await compute_project_stats_batch([], {})
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_project_mixed_statuses(self):
        agg_results = [
            {"_id": "proj1", "in_progress": 2, "completed": 5},
        ]

        mock_coll = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: self
        mock_cursor.__anext__ = AsyncMock(side_effect=StopAsyncIteration)

        # Simulate async iteration over aggregation results
        async def _aiter():
            for doc in agg_results:
                yield doc

        mock_coll.aggregate.return_value = _aiter()

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            result = await compute_project_stats_batch(["proj1"], {})

        assert result == {"proj1": (2, 5)}

    @pytest.mark.asyncio
    async def test_multiple_projects(self):
        agg_results = [
            {"_id": "proj1", "in_progress": 1, "completed": 3},
            {"_id": "proj2", "in_progress": 0, "completed": 10},
        ]

        mock_coll = MagicMock()

        async def _aiter():
            for doc in agg_results:
                yield doc

        mock_coll.aggregate.return_value = _aiter()

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            result = await compute_project_stats_batch(["proj1", "proj2"], {})

        assert result == {"proj1": (1, 3), "proj2": (0, 10)}

    @pytest.mark.asyncio
    async def test_db_error_returns_empty(self):
        mock_coll = MagicMock()

        async def _aiter():
            raise RuntimeError("DB connection lost")
            yield  # noqa: unreachable — makes it an async generator

        mock_coll.aggregate.return_value = _aiter()

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            result = await compute_project_stats_batch(["proj1"], {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_tenant_filter_passed_to_pipeline(self):
        mock_coll = MagicMock()

        async def _aiter():
            return
            yield  # noqa: unreachable

        mock_coll.aggregate.return_value = _aiter()

        t_filter = {"enterprise_id": "ent1", "organization_id": "org1"}

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            await compute_project_stats_batch(["proj1"], t_filter)

        # Verify the $match stage includes tenant filter keys
        call_args = mock_coll.aggregate.call_args[0][0]
        match_stage = call_args[0]["$match"]
        assert match_stage["enterprise_id"] == "ent1"
        assert match_stage["organization_id"] == "org1"


# ── compute_single_project_stats ─────────────────────────────


class TestComputeSingleProjectStats:
    @pytest.mark.asyncio
    async def test_returns_counts(self):
        mock_coll = MagicMock()
        mock_coll.count_documents = AsyncMock(side_effect=[3, 7])

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            result = await compute_single_project_stats("proj1", {})

        assert result == (3, 7)

        # Verify the two count_documents calls
        calls = mock_coll.count_documents.call_args_list
        assert calls[0][0][0]["status"] == {"$in": _IN_PROGRESS_STATUSES}
        assert calls[1][0][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_db_error_returns_zeros(self):
        mock_coll = MagicMock()
        mock_coll.count_documents = AsyncMock(side_effect=RuntimeError("fail"))

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            result = await compute_single_project_stats("proj1", {})

        assert result == (0, 0)

    @pytest.mark.asyncio
    async def test_tenant_filter_included(self):
        mock_coll = MagicMock()
        mock_coll.count_documents = AsyncMock(return_value=0)

        t_filter = {"enterprise_id": "ent1"}

        with patch(_ASYNC_CLIENT) as mock_db:
            mock_db.return_value.__getitem__ = MagicMock(return_value=mock_coll)
            await compute_single_project_stats("proj1", t_filter)

        calls = mock_coll.count_documents.call_args_list
        for call in calls:
            assert call[0][0]["enterprise_id"] == "ent1"
            assert call[0][0]["project_id"] == "proj1"
