"""Tests for the boot-time webhook-secret validator + signature
fail-closed behaviour (#1 — c9s_idea_foundry).

Closes the silent-acceptance bug where an unset
``AGENTIC_TEAM_WEBHOOK_SECRET`` would let anyone with the URL post fake
``task.completed`` events and update Mongo idea/feature progress.
"""

from __future__ import annotations


import pytest

from crewai_productfeature_planner.apis import _validate_required_secrets
from crewai_productfeature_planner.apis.agentic_team import _webhook


def test_dev_boot_does_not_require_secret(monkeypatch):
    monkeypatch.setenv("SERVER_ENV", "DEV")
    monkeypatch.delenv("AGENTIC_TEAM_WEBHOOK_SECRET", raising=False)
    _validate_required_secrets()  # must not raise


def test_uat_boot_refuses_when_secret_missing(monkeypatch):
    monkeypatch.setenv("SERVER_ENV", "UAT")
    monkeypatch.delenv("AGENTIC_TEAM_WEBHOOK_SECRET", raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        _validate_required_secrets()
    assert "AGENTIC_TEAM_WEBHOOK_SECRET" in str(excinfo.value)


def test_prod_boot_refuses_when_secret_missing(monkeypatch):
    monkeypatch.setenv("SERVER_ENV", "PROD")
    monkeypatch.delenv("AGENTIC_TEAM_WEBHOOK_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        _validate_required_secrets()


def test_prod_boot_passes_when_secret_present(monkeypatch):
    monkeypatch.setenv("SERVER_ENV", "PROD")
    monkeypatch.setenv("AGENTIC_TEAM_WEBHOOK_SECRET", "x")
    _validate_required_secrets()


def test_verify_signature_rejects_unsigned_in_prod(monkeypatch):
    monkeypatch.setenv("SERVER_ENV", "PROD")
    # Force the module-level constant to empty by reloading the config.
    monkeypatch.setattr(_webhook, "AGENTIC_TEAM_WEBHOOK_SECRET", "")
    assert _webhook._verify_signature(b"payload", None) is False
    assert _webhook._verify_signature(b"payload", "any-sig") is False


def test_verify_signature_skips_in_dev(monkeypatch):
    monkeypatch.setenv("SERVER_ENV", "DEV")
    monkeypatch.setattr(_webhook, "AGENTIC_TEAM_WEBHOOK_SECRET", "")
    # Legacy permissive behaviour for local dev.
    assert _webhook._verify_signature(b"payload", None) is True


def test_verify_signature_validates_hmac_when_secret_set(monkeypatch):
    import hashlib
    import hmac

    monkeypatch.setenv("SERVER_ENV", "PROD")
    monkeypatch.setattr(_webhook, "AGENTIC_TEAM_WEBHOOK_SECRET", "topsecret")
    payload = b'{"event":"task.completed"}'
    good_sig = hmac.HMAC(b"topsecret", payload, hashlib.sha256).hexdigest()
    assert _webhook._verify_signature(payload, good_sig) is True
    assert _webhook._verify_signature(payload, "bad-sig") is False
    assert _webhook._verify_signature(payload, None) is False
