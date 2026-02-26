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


# ── Atlassian integration checks ─────────────────────────────


class TestCheckConfluence:
    """Tests for ``check_confluence``."""

    CONFLUENCE_ENV = {
        "ATLASSIAN_BASE_URL": "https://example.atlassian.net",
        "CONFLUENCE_SPACE_KEY": "CS",
        "ATLASSIAN_USERNAME": "user@example.com",
        "ATLASSIAN_API_TOKEN": "tok123",
    }

    def test_missing_all_vars(self, monkeypatch: pytest.MonkeyPatch):
        for key in self.CONFLUENCE_ENV:
            monkeypatch.delenv(key, raising=False)
        ok, detail = preflight.check_confluence()
        assert ok is False
        assert "Missing" in detail
        for key in self.CONFLUENCE_ENV:
            assert key in detail

    def test_missing_some_vars(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.CONFLUENCE_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.delenv("ATLASSIAN_API_TOKEN", raising=False)
        ok, detail = preflight.check_confluence()
        assert ok is False
        assert "ATLASSIAN_API_TOKEN" in detail

    def test_ok_when_http_200(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.CONFLUENCE_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.setattr(
            preflight, "http_request", lambda *a, **kw: (200, "")
        )
        ok, detail = preflight.check_confluence()
        assert ok is True
        assert "HTTP 200" in detail

    def test_fail_when_http_401(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.CONFLUENCE_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.setattr(
            preflight, "http_request", lambda *a, **kw: (401, "")
        )
        ok, detail = preflight.check_confluence()
        assert ok is False
        assert "HTTP 401" in detail

    def test_trailing_slash_stripped(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.CONFLUENCE_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/")
        urls_called: list[str] = []
        monkeypatch.setattr(
            preflight,
            "http_request",
            lambda url, **kw: (urls_called.append(url), (200, ""))[1],  # type: ignore[return-value]
        )
        ok, _ = preflight.check_confluence()
        assert ok is True
        assert urls_called[0] == "https://example.atlassian.net/rest/api/space/CS"

    def test_sends_basic_auth(self, monkeypatch: pytest.MonkeyPatch):
        import base64

        for key, val in self.CONFLUENCE_ENV.items():
            monkeypatch.setenv(key, val)
        headers_seen: list[dict] = []
        monkeypatch.setattr(
            preflight,
            "http_request",
            lambda url, headers=None, **kw: (
                headers_seen.append(headers or {}),
                (200, ""),
            )[1],
        )
        ok, _ = preflight.check_confluence()
        assert ok is True
        auth = headers_seen[0]["Authorization"]
        expected = base64.b64encode(b"user@example.com:tok123").decode()
        assert auth == f"Basic {expected}"


class TestCheckJira:
    """Tests for ``check_jira``."""

    JIRA_ENV = {
        "ATLASSIAN_BASE_URL": "https://example.atlassian.net",
        "JIRA_PROJECT_KEY": "PRJ",
        "ATLASSIAN_USERNAME": "user@example.com",
        "ATLASSIAN_API_TOKEN": "jtok456",
    }

    def test_missing_all_vars(self, monkeypatch: pytest.MonkeyPatch):
        for key in self.JIRA_ENV:
            monkeypatch.delenv(key, raising=False)
        ok, detail = preflight.check_jira()
        assert ok is False
        assert "Missing" in detail
        for key in self.JIRA_ENV:
            assert key in detail

    def test_missing_some_vars(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.JIRA_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.delenv("ATLASSIAN_USERNAME", raising=False)
        ok, detail = preflight.check_jira()
        assert ok is False
        assert "ATLASSIAN_USERNAME" in detail

    def test_ok_when_http_200(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.JIRA_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.setattr(
            preflight, "http_request", lambda *a, **kw: (200, "")
        )
        ok, detail = preflight.check_jira()
        assert ok is True
        assert "HTTP 200" in detail

    def test_fail_when_http_403(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.JIRA_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.setattr(
            preflight, "http_request", lambda *a, **kw: (403, "")
        )
        ok, detail = preflight.check_jira()
        assert ok is False
        assert "HTTP 403" in detail

    def test_trailing_slash_stripped(self, monkeypatch: pytest.MonkeyPatch):
        for key, val in self.JIRA_ENV.items():
            monkeypatch.setenv(key, val)
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/")
        urls_called: list[str] = []
        monkeypatch.setattr(
            preflight,
            "http_request",
            lambda url, **kw: (urls_called.append(url), (200, ""))[1],  # type: ignore[return-value]
        )
        ok, _ = preflight.check_jira()
        assert ok is True
        assert urls_called[0] == "https://example.atlassian.net/rest/api/2/project/PRJ"

    def test_sends_basic_auth(self, monkeypatch: pytest.MonkeyPatch):
        import base64

        for key, val in self.JIRA_ENV.items():
            monkeypatch.setenv(key, val)
        headers_seen: list[dict] = []
        monkeypatch.setattr(
            preflight,
            "http_request",
            lambda url, headers=None, **kw: (
                headers_seen.append(headers or {}),
                (200, ""),
            )[1],
        )
        ok, _ = preflight.check_jira()
        assert ok is True
        auth = headers_seen[0]["Authorization"]
        expected = base64.b64encode(b"user@example.com:jtok456").decode()
        assert auth == f"Basic {expected}"


class TestAtlassianChecksDict:
    """Verify the ATLASSIAN_CHECKS dict is wired correctly."""

    def test_contains_confluence_and_jira(self):
        assert "Confluence" in preflight.ATLASSIAN_CHECKS
        assert "Jira" in preflight.ATLASSIAN_CHECKS

    def test_functions_are_callable(self):
        for label, fn in preflight.ATLASSIAN_CHECKS.items():
            assert callable(fn), f"{label} check is not callable"


class TestRunChecksAtlassian:
    """Verify ``run_checks`` prints Atlassian section."""

    def test_run_checks_prints_atlassian_section(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # Stub out everything so run_checks doesn't hit the network
        monkeypatch.setattr(preflight, "load_env_file", lambda _: None)
        monkeypatch.setattr(
            preflight, "http_request", lambda *a, **kw: (200, "")
        )
        for key in preflight.API_KEYS:
            monkeypatch.setenv(key, "x")
        monkeypatch.setattr(preflight, "check_mongodb", lambda: (True, "ok"))

        # Set Confluence vars, leave Jira project key empty
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "SP")
        monkeypatch.setenv("ATLASSIAN_USERNAME", "u@x.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "tok")
        monkeypatch.delenv("JIRA_PROJECT_KEY", raising=False)

        exit_code = preflight.run_checks()
        captured = capsys.readouterr().out

        assert exit_code == 0
        assert "Atlassian integrations" in captured
        assert "OK: Confluence" in captured
        assert "WARN: Jira" in captured

    def test_atlassian_warnings_are_non_blocking(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        monkeypatch.setattr(preflight, "load_env_file", lambda _: None)
        monkeypatch.setattr(
            preflight, "http_request", lambda *a, **kw: (200, "")
        )
        for key in preflight.API_KEYS:
            monkeypatch.setenv(key, "x")
        monkeypatch.setattr(preflight, "check_mongodb", lambda: (True, "ok"))

        # All Atlassian vars missing
        for key in list(preflight.CONFLUENCE_KEYS) + list(preflight.JIRA_KEYS):
            monkeypatch.delenv(key, raising=False)

        exit_code = preflight.run_checks()
        captured = capsys.readouterr().out

        # Should still pass — Atlassian is non-blocking
        assert exit_code == 0
        assert "Preflight passed" in captured
        assert "WARN: Confluence" in captured
        assert "WARN: Jira" in captured
