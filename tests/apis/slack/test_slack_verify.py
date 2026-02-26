"""Tests for Slack request verification (HMAC-SHA256 + fallback)."""

import hashlib
import hmac
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from crewai_productfeature_planner.apis import app


def _sign(secret: str, body: bytes, timestamp: str | None = None) -> dict:
    """Compute valid Slack signature headers for test requests."""
    ts = timestamp or str(int(time.time()))
    base_string = f"v0:{ts}:".encode() + body
    sig = "v0=" + hmac.new(secret.encode(), base_string, hashlib.sha256).hexdigest()
    return {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
    }


@pytest.fixture
def _clear_slack_env(monkeypatch):
    """Remove all Slack env vars so tests start clean."""
    for key in (
        "SLACK_SIGNING_SECRET", "SLACK_VERIFICATION_TOKEN",
        "SLACK_ACCESS_TOKEN", "SLACK_BYPASS",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_url_verification_no_auth(_clear_slack_env):
    """No auth configured → passes through, url_verification works."""
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "abc123"


@pytest.mark.asyncio
async def test_signing_secret_valid(_clear_slack_env, monkeypatch):
    """Valid HMAC-SHA256 signature passes verification."""
    secret = "test_secret_12345"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    body = json.dumps({"type": "url_verification", "challenge": "xyz"}).encode()
    headers = _sign(secret, body)
    headers["Content-Type"] = "application/json"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "xyz"


@pytest.mark.asyncio
async def test_signing_secret_invalid(_clear_slack_env, monkeypatch):
    """Invalid signature is rejected with 401."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "real_secret")
    body = json.dumps({"type": "url_verification", "challenge": "bad"}).encode()
    headers = _sign("wrong_secret", body)
    headers["Content-Type"] = "application/json"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_signing_secret_missing_headers(_clear_slack_env, monkeypatch):
    """Missing signature headers are rejected with 401."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "some_secret")
    body = json.dumps({"type": "url_verification"}).encode()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_signing_secret_old_timestamp(_clear_slack_env, monkeypatch):
    """Timestamps older than 5 minutes are rejected."""
    secret = "ts_secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    body = json.dumps({"type": "url_verification"}).encode()
    old_ts = str(int(time.time()) - 600)
    headers = _sign(secret, body, timestamp=old_ts)
    headers["Content-Type"] = "application/json"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verification_token_fallback(_clear_slack_env, monkeypatch):
    """Deprecated verification token fallback works."""
    token = "legacy_token_abc"
    monkeypatch.setenv("SLACK_VERIFICATION_TOKEN", token)
    body = json.dumps({
        "type": "url_verification",
        "challenge": "fallback",
        "token": token,
    }).encode()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "fallback"


@pytest.mark.asyncio
async def test_verification_token_mismatch(_clear_slack_env, monkeypatch):
    """Wrong verification token is rejected."""
    monkeypatch.setenv("SLACK_VERIFICATION_TOKEN", "correct_token")
    body = json.dumps({
        "type": "url_verification",
        "challenge": "nope",
        "token": "wrong_token",
    }).encode()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/slack/events", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 401
