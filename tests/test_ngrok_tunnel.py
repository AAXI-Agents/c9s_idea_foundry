"""Tests for the ngrok tunnel helper."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.ngrok_tunnel import (
    start_tunnel,
    stop_tunnel,
    _configure_auth,
    get_server_env,
    get_public_url,
    is_dev,
    DEFAULT_PORT,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    """Provide dummy keys so tests don't hit real services."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("NGROK_AUTHTOKEN", "test-ngrok-token")


# ── _configure_auth ──────────────────────────────────────────


def test_configure_auth_sets_token(monkeypatch):
    """Auth token should be applied to pyngrok config."""
    monkeypatch.setenv("NGROK_AUTHTOKEN", "my-token-123")
    with patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf:
        mock_cfg = MagicMock()
        mock_conf.get_default.return_value = mock_cfg
        _configure_auth()
        assert mock_cfg.auth_token == "my-token-123"


def test_configure_auth_raises_when_missing(monkeypatch):
    """Should raise RuntimeError when NGROK_AUTHTOKEN is not set."""
    monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
    with pytest.raises(RuntimeError, match="NGROK_AUTHTOKEN is not set"):
        _configure_auth()


# ── start_tunnel ─────────────────────────────────────────────


def test_start_tunnel_returns_public_url():
    """start_tunnel should return the public URL from ngrok."""
    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://abc123.ngrok.io"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        url = start_tunnel(port=3000)

    assert url == "https://abc123.ngrok.io"
    mock_ngrok.connect.assert_called_once_with(3000)


def test_start_tunnel_uses_default_port():
    """When no port is given it should use DEFAULT_PORT."""
    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://xyz.ngrok.io"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        start_tunnel()

    mock_ngrok.connect.assert_called_once_with(DEFAULT_PORT)


def test_start_tunnel_forwards_kwargs():
    """Extra kwargs should be forwarded to ngrok.connect."""
    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://sub.ngrok.io"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        start_tunnel(port=5000, subdomain="myapp")

    mock_ngrok.connect.assert_called_once_with(5000, subdomain="myapp")


# ── NGROK_DOMAIN (static domain) ─────────────────────────────


def test_start_tunnel_uses_ngrok_domain_env(monkeypatch):
    """When NGROK_DOMAIN is set, the domain kwarg should be forwarded."""
    monkeypatch.setenv("NGROK_DOMAIN", "myapp.ngrok-free.dev")

    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://myapp.ngrok-free.dev"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        url = start_tunnel(port=8000)

    assert url == "https://myapp.ngrok-free.dev"
    mock_ngrok.connect.assert_called_once_with(8000, domain="myapp.ngrok-free.dev")


def test_start_tunnel_without_ngrok_domain(monkeypatch):
    """Without NGROK_DOMAIN, no domain kwarg should be added."""
    monkeypatch.delenv("NGROK_DOMAIN", raising=False)

    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://random.ngrok.io"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        start_tunnel()

    # Should be called with only the port, no domain kwarg.
    mock_ngrok.connect.assert_called_once_with(DEFAULT_PORT)


def test_start_tunnel_explicit_domain_overrides_env(monkeypatch):
    """An explicit ``domain`` kwarg should take precedence over NGROK_DOMAIN."""
    monkeypatch.setenv("NGROK_DOMAIN", "env-domain.ngrok-free.dev")

    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://explicit.ngrok-free.dev"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        start_tunnel(port=8000, domain="explicit.ngrok-free.dev")

    mock_ngrok.connect.assert_called_once_with(
        8000, domain="explicit.ngrok-free.dev",
    )


def test_start_tunnel_subdomain_kwarg_skips_ngrok_domain(monkeypatch):
    """When ``subdomain`` is passed, NGROK_DOMAIN should not be injected."""
    monkeypatch.setenv("NGROK_DOMAIN", "env-domain.ngrok-free.dev")

    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://sub.ngrok.io"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        start_tunnel(port=8000, subdomain="sub")

    mock_ngrok.connect.assert_called_once_with(8000, subdomain="sub")


# ── stop_tunnel ──────────────────────────────────────────────


def test_stop_tunnel_disconnects_and_kills():
    """stop_tunnel should call disconnect_all and kill."""
    with patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok:
        stop_tunnel()

    mock_ngrok.disconnect_all.assert_called_once()
    mock_ngrok.kill.assert_called_once()


# ── get_server_env ───────────────────────────────────────────


def test_get_server_env_default_is_dev(monkeypatch):
    """Unset SERVER_ENV should default to DEV."""
    monkeypatch.delenv("SERVER_ENV", raising=False)
    assert get_server_env() == "DEV"


def test_get_server_env_reads_env_var(monkeypatch):
    """get_server_env should return the normalised value from the env."""
    for val in ("UAT", "uat", " Uat ", "PROD", "prod", " Prod "):
        monkeypatch.setenv("SERVER_ENV", val)
        assert get_server_env() == val.strip().upper()


def test_get_server_env_rejects_invalid(monkeypatch):
    """Invalid SERVER_ENV values should raise ValueError."""
    monkeypatch.setenv("SERVER_ENV", "STAGING")
    with pytest.raises(ValueError, match="Invalid SERVER_ENV"):
        get_server_env()


# ── is_dev ───────────────────────────────────────────────────


def test_is_dev_true_for_dev(monkeypatch):
    """is_dev() should return True when SERVER_ENV is DEV."""
    monkeypatch.setenv("SERVER_ENV", "DEV")
    assert is_dev() is True


def test_is_dev_false_for_uat(monkeypatch):
    """is_dev() should return False when SERVER_ENV is UAT."""
    monkeypatch.setenv("SERVER_ENV", "UAT")
    assert is_dev() is False


def test_is_dev_false_for_prod(monkeypatch):
    """is_dev() should return False when SERVER_ENV is PROD."""
    monkeypatch.setenv("SERVER_ENV", "PROD")
    assert is_dev() is False


# ── get_public_url ───────────────────────────────────────────


def test_get_public_url_dev_calls_start_tunnel(monkeypatch):
    """DEV mode should delegate to start_tunnel and return its URL."""
    monkeypatch.setenv("SERVER_ENV", "DEV")

    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "https://dev.ngrok.io"

    with (
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.conf") as mock_conf,
        patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok,
    ):
        mock_conf.get_default.return_value = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel

        url = get_public_url(port=9000)

    assert url == "https://dev.ngrok.io"
    mock_ngrok.connect.assert_called_once()


def test_get_public_url_uat_returns_domain(monkeypatch):
    """UAT mode should return https://{DOMAIN_NAME_UAT}."""
    monkeypatch.setenv("SERVER_ENV", "UAT")
    monkeypatch.setenv("DOMAIN_NAME_UAT", "prd-uat.example.com")

    url = get_public_url()

    assert url == "https://prd-uat.example.com"


def test_get_public_url_prod_returns_domain(monkeypatch):
    """PROD mode should return https://{DOMAIN_NAME_PROD}."""
    monkeypatch.setenv("SERVER_ENV", "PROD")
    monkeypatch.setenv("DOMAIN_NAME_PROD", "prd.example.com")

    url = get_public_url()

    assert url == "https://prd.example.com"


def test_get_public_url_uat_missing_domain_raises(monkeypatch):
    """UAT mode without DOMAIN_NAME_UAT should raise RuntimeError."""
    monkeypatch.setenv("SERVER_ENV", "UAT")
    monkeypatch.delenv("DOMAIN_NAME_UAT", raising=False)

    with pytest.raises(RuntimeError, match="DOMAIN_NAME_UAT is not set"):
        get_public_url()


def test_get_public_url_prod_missing_domain_raises(monkeypatch):
    """PROD mode without DOMAIN_NAME_PROD should raise RuntimeError."""
    monkeypatch.setenv("SERVER_ENV", "PROD")
    monkeypatch.delenv("DOMAIN_NAME_PROD", raising=False)

    with pytest.raises(RuntimeError, match="DOMAIN_NAME_PROD is not set"):
        get_public_url()


def test_get_public_url_prepends_https(monkeypatch):
    """Domain without scheme should get https:// prepended."""
    monkeypatch.setenv("SERVER_ENV", "UAT")
    monkeypatch.setenv("DOMAIN_NAME_UAT", "bare-domain.example.com")

    assert get_public_url() == "https://bare-domain.example.com"


def test_get_public_url_preserves_existing_scheme(monkeypatch):
    """Domain already starting with http should not get double scheme."""
    monkeypatch.setenv("SERVER_ENV", "PROD")
    monkeypatch.setenv("DOMAIN_NAME_PROD", "https://already-set.example.com")

    assert get_public_url() == "https://already-set.example.com"
