"""Tests for mongodb.client — connection management and URI building."""

import pytest

from crewai_productfeature_planner.mongodb.client import (
    DEFAULT_DB_NAME,
    _build_uri,
    _get_db_name,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_PORT", raising=False)
    monkeypatch.delenv("MONGODB_USERNAME", raising=False)
    monkeypatch.delenv("MONGODB_PASSWORD", raising=False)


# ── _build_uri ────────────────────────────────────────────────


def test_build_uri_default(monkeypatch):
    """Without env vars, URI should be mongodb://localhost:27017."""
    uri = _build_uri()
    assert uri == "mongodb://localhost:27017"


def test_build_uri_custom_host(monkeypatch):
    """MONGODB_URI as host should get scheme and default port."""
    monkeypatch.setenv("MONGODB_URI", "myhost")
    uri = _build_uri()
    assert uri == "mongodb://myhost:27017"


def test_build_uri_custom_port(monkeypatch):
    """MONGODB_PORT should override the default port."""
    monkeypatch.setenv("MONGODB_PORT", "27018")
    uri = _build_uri()
    assert uri == "mongodb://localhost:27018"


def test_build_uri_custom_host_and_port(monkeypatch):
    """Both MONGODB_URI and MONGODB_PORT should be used."""
    monkeypatch.setenv("MONGODB_URI", "myhost")
    monkeypatch.setenv("MONGODB_PORT", "27018")
    uri = _build_uri()
    assert uri == "mongodb://myhost:27018"


def test_build_uri_host_with_port_uses_embedded(monkeypatch):
    """Port embedded in host should be extracted and used."""
    monkeypatch.setenv("MONGODB_URI", "myhost:27018")
    uri = _build_uri()
    assert uri == "mongodb://myhost:27018"


def test_build_uri_port_env_overrides_embedded(monkeypatch):
    """MONGODB_PORT should not override port embedded in host — embedded wins."""
    monkeypatch.setenv("MONGODB_URI", "myhost:27018")
    monkeypatch.setenv("MONGODB_PORT", "9999")
    uri = _build_uri()
    assert uri == "mongodb://myhost:27018"


def test_build_uri_strips_existing_scheme(monkeypatch):
    """If the user includes mongodb:// it should still work."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://myhost")
    uri = _build_uri()
    assert uri == "mongodb://myhost:27017"


def test_build_uri_with_credentials(monkeypatch):
    """Username and password should be embedded in the URI."""
    monkeypatch.setenv("MONGODB_URI", "myhost")
    monkeypatch.setenv("MONGODB_PORT", "27017")
    monkeypatch.setenv("MONGODB_USERNAME", "admin")
    monkeypatch.setenv("MONGODB_PASSWORD", "secret")
    uri = _build_uri()
    assert uri == "mongodb://admin:secret@myhost:27017"


def test_build_uri_with_credentials_strips_scheme(monkeypatch):
    """Credentials should work even if URI has mongodb:// prefix."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://myhost")
    monkeypatch.setenv("MONGODB_PORT", "27017")
    monkeypatch.setenv("MONGODB_USERNAME", "admin")
    monkeypatch.setenv("MONGODB_PASSWORD", "secret")
    uri = _build_uri()
    assert uri == "mongodb://admin:secret@myhost:27017"


def test_build_uri_replaces_embedded_creds(monkeypatch):
    """Env credentials should replace any embedded in the URI."""
    monkeypatch.setenv("MONGODB_URI", "mongodb://old:creds@myhost")
    monkeypatch.setenv("MONGODB_PORT", "27017")
    monkeypatch.setenv("MONGODB_USERNAME", "admin")
    monkeypatch.setenv("MONGODB_PASSWORD", "secret")
    uri = _build_uri()
    assert uri == "mongodb://admin:secret@myhost:27017"


def test_build_uri_no_inject_with_only_username(monkeypatch):
    """Should not inject if only username is set (no password)."""
    monkeypatch.setenv("MONGODB_USERNAME", "admin")
    uri = _build_uri()
    assert "@" not in uri


def test_build_uri_no_inject_with_only_password(monkeypatch):
    """Should not inject if only password is set (no username)."""
    monkeypatch.setenv("MONGODB_PASSWORD", "secret")
    uri = _build_uri()
    assert "@" not in uri


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
