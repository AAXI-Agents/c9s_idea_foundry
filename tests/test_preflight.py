import pytest

from crewai_productfeature_planner.scripts import preflight


def test_api_keys_have_check_functions():
    assert set(preflight.API_KEYS) == set(preflight.CHECKS)


def test_checks_fail_when_key_missing(monkeypatch: pytest.MonkeyPatch):
    for key, check in preflight.CHECKS.items():
        monkeypatch.delenv(key, raising=False)
        ok, detail = check()
        assert ok is False
        assert "empty" in detail


def test_checks_ok_when_http_200(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(preflight, "http_request", lambda *args, **kwargs: (200, ""))
    for key in preflight.CHECKS:
        monkeypatch.setenv(key, "x")

    for _key, check in preflight.CHECKS.items():
        ok, detail = check()
        assert ok is True
        assert "HTTP 200" in detail
