"""Tests for the health check and version endpoints."""

import pytest
from fastapi.testclient import TestClient

from crewai_productfeature_planner.apis import app
from crewai_productfeature_planner.version import get_version


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == get_version()


def test_version_endpoint(client):
    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == get_version()
    # latest entry should match the current version
    assert data["latest"]["version"] == get_version()
    assert "date" in data["latest"]
    assert "summary" in data["latest"]
    # codex should be a non-empty list
    assert isinstance(data["codex"], list)
    assert len(data["codex"]) >= 1
    # last codex entry version should equal the current version
    assert data["codex"][-1]["version"] == get_version()
