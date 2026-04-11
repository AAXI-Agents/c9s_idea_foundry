"""Tests for scripts/cleanup_orphan_projects.py.

The cleanup script's helper functions are pure — they accept a ``db``
argument and don't import MongoDB at module level, so we can test
them without a real database connection.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the cleanup script as a module (no top-level DB imports).
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cleanup_orphan_projects.py"
_spec = importlib.util.spec_from_file_location("cleanup_orphan_projects", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


@pytest.fixture()
def cleanup_mod():
    """Return the cleanup script module."""
    return _mod


# ── helpers ────────────────────────────────────────────────────────────────

def _fake_db(project_ids: list[str], working_docs: list[dict]) -> MagicMock:
    """Build a mock ``db`` dict-like with projectConfig + workingIdeas."""
    db = MagicMock()
    # projectConfig.find returns project docs
    db.__getitem__.return_value.find.return_value = [
        {"project_id": pid} for pid in project_ids
    ]
    # Override keyed collection access
    collections: dict[str, MagicMock] = {}

    def getitem(name):
        if name not in collections:
            collections[name] = MagicMock()
        return collections[name]

    db.__getitem__.side_effect = getitem

    # projectConfig.find → valid IDs
    collections["projectConfig"] = MagicMock()
    collections["projectConfig"].find.return_value = [
        {"project_id": pid} for pid in project_ids
    ]

    # workingIdeas.distinct → all project_ids present
    all_pids = list({d.get("project_id") for d in working_docs if d.get("project_id")})
    collections["workingIdeas"] = MagicMock()
    collections["workingIdeas"].distinct.return_value = all_pids
    collections["workingIdeas"].find.return_value = working_docs

    return db


# ── unit tests ─────────────────────────────────────────────────────────────


class TestGetValidProjectIds:
    def test_returns_project_ids(self, cleanup_mod):
        db = MagicMock()
        db["projectConfig"].find.return_value = [
            {"project_id": "aaa"},
            {"project_id": "bbb"},
        ]
        assert cleanup_mod._get_valid_project_ids(db) == {"aaa", "bbb"}

    def test_skips_empty_project_id(self, cleanup_mod):
        db = MagicMock()
        db["projectConfig"].find.return_value = [
            {"project_id": "aaa"},
            {"project_id": ""},
            {},
        ]
        assert cleanup_mod._get_valid_project_ids(db) == {"aaa"}


class TestFindOrphanedProjects:
    def test_returns_empty_when_all_valid(self, cleanup_mod):
        db = MagicMock()
        db["workingIdeas"].distinct.return_value = ["aaa"]
        result = cleanup_mod._find_orphaned_projects(db, {"aaa"})
        assert result == {}

    def test_finds_orphan(self, cleanup_mod):
        db = MagicMock()
        db["workingIdeas"].distinct.return_value = ["aaa", "orphan-1"]
        db["workingIdeas"].find.return_value = [
            {"run_id": "r1", "idea": "test", "status": "completed", "project_id": "orphan-1"},
        ]
        result = cleanup_mod._find_orphaned_projects(db, {"aaa"})
        assert "orphan-1" in result
        assert len(result["orphan-1"]) == 1

    def test_ignores_empty_project_ids(self, cleanup_mod):
        db = MagicMock()
        db["workingIdeas"].distinct.return_value = [None, "", "orphan"]
        db["workingIdeas"].find.return_value = [
            {"run_id": "r1", "idea": "test", "status": "failed", "project_id": "orphan"},
        ]
        result = cleanup_mod._find_orphaned_projects(db, set())
        assert "orphan" in result
        assert None not in result
        assert "" not in result


class TestGetRunIds:
    def test_extracts_run_ids(self, cleanup_mod):
        docs = [{"run_id": "a"}, {"run_id": "b"}, {}]
        assert cleanup_mod._get_run_ids(docs) == ["a", "b"]


class TestArchiveOrphans:
    def test_archives_ideas_and_jobs(self, cleanup_mod):
        wi_col = MagicMock()
        wi_col.update_many.return_value = MagicMock(modified_count=3)
        cj_col = MagicMock()
        cj_col.update_many.return_value = MagicMock(modified_count=2)

        db = MagicMock()
        db.__getitem__ = lambda self, key: {"workingIdeas": wi_col, "crewJobs": cj_col}[key]

        orphans = {"proj-1": [
            {"run_id": "r1"}, {"run_id": "r2"}, {"run_id": "r3"},
        ]}
        counts = cleanup_mod._archive_orphans(db, orphans)
        assert counts["workingIdeas"] == 3
        assert counts["crewJobs"] == 2

        # Verify the status is set to 'archived'
        call_args = wi_col.update_many.call_args
        assert call_args[0][1]["$set"]["status"] == "archived"


class TestDeleteOrphans:
    def test_deletes_across_all_collections(self, cleanup_mod):
        wi_col = MagicMock()
        wi_col.delete_many.return_value = MagicMock(deleted_count=5)
        cj_col = MagicMock()
        cj_col.delete_many.return_value = MagicMock(deleted_count=3)
        ai_col = MagicMock()
        ai_col.delete_many.return_value = MagicMock(deleted_count=10)
        pr_col = MagicMock()
        pr_col.delete_many.return_value = MagicMock(deleted_count=2)

        cols = {
            "workingIdeas": wi_col,
            "crewJobs": cj_col,
            "agentInteraction": ai_col,
            "productRequirements": pr_col,
        }
        db = MagicMock()
        db.__getitem__ = lambda self, key: cols[key]

        orphans = {"proj-1": [
            {"run_id": "r1"}, {"run_id": "r2"},
        ]}
        counts = cleanup_mod._delete_orphans(db, orphans)
        assert counts["workingIdeas"] == 5
        assert counts["crewJobs"] == 3
        assert counts["agentInteraction"] == 10
        assert counts["productRequirements"] == 2


class TestPrintSummary:
    def test_no_orphans(self, capsys, cleanup_mod):
        cleanup_mod._print_summary({})
        assert "No orphaned" in capsys.readouterr().out

    def test_with_orphans(self, capsys, cleanup_mod):
        orphans = {"proj-1": [
            {"status": "completed"},
            {"status": "failed"},
            {"status": "completed"},
        ]}
        cleanup_mod._print_summary(orphans)
        output = capsys.readouterr().out
        assert "proj-1" in output
        assert "3" in output
