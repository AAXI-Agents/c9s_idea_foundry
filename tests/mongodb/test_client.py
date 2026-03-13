"""Tests for mongodb.client — connection management and Atlas URI."""

import pytest

from crewai_productfeature_planner.mongodb.client import (
    DEFAULT_DB_NAME,
    _build_uri,
    _get_db_name,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.delenv("MONGODB_ATLAS_URI", raising=False)


# ── _build_uri ────────────────────────────────────────────────


def test_build_uri_returns_atlas_uri(monkeypatch):
    """MONGODB_ATLAS_URI should be returned as-is."""
    monkeypatch.setenv("MONGODB_ATLAS_URI", "mongodb+srv://user:pass@cluster.example.net/?appName=Test")
    uri = _build_uri()
    assert uri == "mongodb+srv://user:pass@cluster.example.net/?appName=Test"


def test_build_uri_strips_whitespace(monkeypatch):
    """Leading/trailing whitespace should be stripped."""
    monkeypatch.setenv("MONGODB_ATLAS_URI", "  mongodb+srv://user:pass@cluster.example.net  ")
    uri = _build_uri()
    assert uri == "mongodb+srv://user:pass@cluster.example.net"


def test_build_uri_raises_when_missing(monkeypatch):
    """Should raise RuntimeError when MONGODB_ATLAS_URI is not set."""
    monkeypatch.delenv("MONGODB_ATLAS_URI", raising=False)
    with pytest.raises(RuntimeError, match="MONGODB_ATLAS_URI"):
        _build_uri()


def test_build_uri_raises_when_empty(monkeypatch):
    """Should raise RuntimeError when MONGODB_ATLAS_URI is empty."""
    monkeypatch.setenv("MONGODB_ATLAS_URI", "")
    with pytest.raises(RuntimeError, match="MONGODB_ATLAS_URI"):
        _build_uri()


def test_build_uri_raises_when_whitespace_only(monkeypatch):
    """Should raise RuntimeError when MONGODB_ATLAS_URI is only whitespace."""
    monkeypatch.setenv("MONGODB_ATLAS_URI", "   ")
    with pytest.raises(RuntimeError, match="MONGODB_ATLAS_URI"):
        _build_uri()


def test_build_uri_standard_mongo_uri(monkeypatch):
    """A regular mongodb:// URI should also work."""
    monkeypatch.setenv("MONGODB_ATLAS_URI", "mongodb://admin:pass@host:27017")
    uri = _build_uri()
    assert uri == "mongodb://admin:pass@host:27017"


# ── _get_db_name ──────────────────────────────────────────────


def test_get_db_name_default(monkeypatch):
    """Without MONGODB_DB, should return the default."""
    monkeypatch.delenv("MONGODB_DB", raising=False)
    assert _get_db_name() == DEFAULT_DB_NAME


def test_get_db_name_custom(monkeypatch):
    """MONGODB_DB should override the default."""
    monkeypatch.setenv("MONGODB_DB", "my_custom_db")
    assert _get_db_name() == "my_custom_db"


def test_get_db_name_empty_string_uses_default(monkeypatch):
    """MONGODB_DB set to empty string should fall back to default."""
    monkeypatch.setenv("MONGODB_DB", "")
    assert _get_db_name() == DEFAULT_DB_NAME
