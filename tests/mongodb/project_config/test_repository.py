"""Tests for mongodb.project_config.repository — CRUD for projectConfig collection."""

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from crewai_productfeature_planner.mongodb.project_config.repository import (
    PROJECT_CONFIG_COLLECTION,
    add_reference_url,
    add_slack_file_ref,
    create_project,
    delete_project,
    get_project,
    get_project_by_name,
    get_project_for_run,
    list_projects,
    update_project,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── helpers ──────────────────────────────────────────────────


def _mock_db(collection_mock: MagicMock | None = None) -> tuple[MagicMock, MagicMock]:
    """Return (mock_db, mock_collection) wired together."""
    col = collection_mock or MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    return db, col


# ── create_project ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_create_project_basic(mock_get_db):
    """create_project should insert a doc and return a uuid hex."""
    col = MagicMock()
    col.insert_one.return_value = MagicMock(inserted_id="abc")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    pid = create_project(name="MyProject")

    assert pid is not None
    assert len(pid) == 32  # uuid hex
    db.__getitem__.assert_called_with(PROJECT_CONFIG_COLLECTION)
    col.insert_one.assert_called_once()

    doc = col.insert_one.call_args[0][0]
    assert doc["name"] == "MyProject"
    assert doc["project_id"] == pid
    assert doc["confluence_space_key"] == ""
    assert doc["jira_project_key"] == ""
    assert doc["reference_urls"] == []
    assert doc["slack_file_refs"] == []
    assert "created_at" in doc
    assert "updated_at" in doc


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_create_project_with_keys(mock_get_db):
    """Extra fields should be included in the inserted document."""
    col = MagicMock()
    col.insert_one.return_value = MagicMock(inserted_id="xyz")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    pid = create_project(
        name="Proj2",
        confluence_space_key="CS",
        jira_project_key="JP",
        confluence_parent_id="PID",
        reference_urls=["https://example.com"],
        slack_file_refs=[{"file_id": "f1", "name": "n1", "url": "u1", "uploaded_at": "t1"}],
    )

    doc = col.insert_one.call_args[0][0]
    assert doc["confluence_space_key"] == "CS"
    assert doc["jira_project_key"] == "JP"
    assert doc["confluence_parent_id"] == "PID"
    assert doc["reference_urls"] == ["https://example.com"]
    assert doc["slack_file_refs"][0]["file_id"] == "f1"
    assert pid is not None


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_create_project_db_error(mock_get_db):
    """Should return None on a DB failure."""
    col = MagicMock()
    col.insert_one.side_effect = ServerSelectionTimeoutError("conn refused")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert create_project(name="Fail") is None


# ── get_project ──────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_found(mock_get_db):
    """Should return the project doc when found."""
    expected = {"project_id": "aaa", "name": "P1"}
    col = MagicMock()
    col.find_one.return_value = expected
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = get_project("aaa")
    assert result == expected
    col.find_one.assert_called_once_with({"project_id": "aaa"}, {"_id": 0})


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_not_found(mock_get_db):
    """Should return None when the doc doesn't exist."""
    col = MagicMock()
    col.find_one.return_value = None
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project("nonexistent") is None


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_db_error(mock_get_db):
    """Should return None on DB failure."""
    col = MagicMock()
    col.find_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project("xxx") is None


# ── get_project_by_name ──────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_by_name_found(mock_get_db):
    """Should return the project doc by name."""
    expected = {"project_id": "bbb", "name": "Foo"}
    col = MagicMock()
    col.find_one.return_value = expected
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = get_project_by_name("Foo")
    assert result == expected
    col.find_one.assert_called_once_with({"name": "Foo"}, {"_id": 0})


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_by_name_db_error(mock_get_db):
    """Should return None on DB failure."""
    col = MagicMock()
    col.find_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project_by_name("X") is None


# ── list_projects ────────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_list_projects(mock_get_db):
    """Should return a list of project docs."""
    docs = [{"project_id": "a"}, {"project_id": "b"}]
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = iter(docs)

    col = MagicMock()
    col.find.return_value = cursor
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    result = list_projects(limit=50)
    assert result == docs
    cursor.sort.assert_called_once_with("created_at", -1)
    cursor.limit.assert_called_once_with(50)


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_list_projects_db_error(mock_get_db):
    """Should return an empty list on DB failure."""
    col = MagicMock()
    col.find.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert list_projects() == []


# ── get_project_for_run ──────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_for_run_linked(mock_get_db):
    """Should traverse workingIdeas → projectConfig."""
    wi_col = MagicMock()
    wi_col.find_one.return_value = {"project_id": "proj-1"}

    pc_col = MagicMock()
    pc_col.find_one.return_value = {"project_id": "proj-1", "name": "Demo"}

    db = MagicMock()

    def _getitem(name):
        return {"workingIdeas": wi_col, PROJECT_CONFIG_COLLECTION: pc_col}.get(
            name, MagicMock()
        )

    db.__getitem__ = MagicMock(side_effect=_getitem)
    mock_get_db.return_value = db

    result = get_project_for_run("run-42")
    assert result is not None
    assert result["name"] == "Demo"
    wi_col.find_one.assert_called_once_with(
        {"run_id": "run-42"}, {"project_id": 1, "_id": 0}
    )


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_for_run_no_project_id(mock_get_db):
    """Should return None when working idea has no project_id."""
    col = MagicMock()
    col.find_one.return_value = {"run_id": "run-42"}  # no project_id
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project_for_run("run-42") is None


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_for_run_no_working_idea(mock_get_db):
    """Should return None when working idea doc not found."""
    col = MagicMock()
    col.find_one.return_value = None
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project_for_run("nope") is None


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_get_project_for_run_db_error(mock_get_db):
    """Should return None on DB failure."""
    col = MagicMock()
    col.find_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert get_project_for_run("run-x") is None


# ── update_project ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_update_project(mock_get_db):
    """Should $set the given fields + updated_at."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    count = update_project("p1", confluence_space_key="NEW")
    assert count == 1
    call_args = col.update_one.call_args
    assert call_args[0][0] == {"project_id": "p1"}
    set_fields = call_args[0][1]["$set"]
    assert set_fields["confluence_space_key"] == "NEW"
    assert "updated_at" in set_fields


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_update_project_no_fields(mock_get_db):
    """Should return 0 immediately if no fields."""
    assert update_project("p1") == 0
    mock_get_db.assert_not_called()


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_update_project_db_error(mock_get_db):
    """Should return 0 on DB failure."""
    col = MagicMock()
    col.update_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert update_project("p1", name="X") == 0


# ── add_reference_url ────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_add_reference_url(mock_get_db):
    """Should use $addToSet to append a URL."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    count = add_reference_url("p1", "https://docs.example.com")
    assert count == 1
    call_args = col.update_one.call_args
    assert call_args[0][1]["$addToSet"]["reference_urls"] == "https://docs.example.com"
    assert "$set" in call_args[0][1]  # updated_at


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_add_reference_url_db_error(mock_get_db):
    """Should return 0 on DB failure."""
    col = MagicMock()
    col.update_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert add_reference_url("p1", "https://x") == 0


# ── add_slack_file_ref ───────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_add_slack_file_ref(mock_get_db):
    """Should $push a slack_file_refs entry."""
    col = MagicMock()
    col.update_one.return_value = MagicMock(modified_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    count = add_slack_file_ref("p1", file_id="F1", name="design.pdf", url="https://slack/F1")
    assert count == 1
    call_args = col.update_one.call_args
    pushed = call_args[0][1]["$push"]["slack_file_refs"]
    assert pushed["file_id"] == "F1"
    assert pushed["name"] == "design.pdf"
    assert pushed["url"] == "https://slack/F1"
    assert "uploaded_at" in pushed


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_add_slack_file_ref_db_error(mock_get_db):
    """Should return 0 on DB failure."""
    col = MagicMock()
    col.update_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert add_slack_file_ref("p1", file_id="F", name="n", url="u") == 0


# ── delete_project ───────────────────────────────────────────


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_delete_project(mock_get_db):
    """Should delete by project_id and return deleted_count."""
    col = MagicMock()
    col.delete_one.return_value = MagicMock(deleted_count=1)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert delete_project("p1") == 1
    col.delete_one.assert_called_once_with({"project_id": "p1"})


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_delete_project_not_found(mock_get_db):
    """Should return 0 when doc not found."""
    col = MagicMock()
    col.delete_one.return_value = MagicMock(deleted_count=0)
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert delete_project("nope") == 0


@patch("crewai_productfeature_planner.mongodb.project_config.repository.get_db")
def test_delete_project_db_error(mock_get_db):
    """Should return 0 on DB failure."""
    col = MagicMock()
    col.delete_one.side_effect = ServerSelectionTimeoutError("fail")
    db, _ = _mock_db(col)
    mock_get_db.return_value = db

    assert delete_project("xxx") == 0
