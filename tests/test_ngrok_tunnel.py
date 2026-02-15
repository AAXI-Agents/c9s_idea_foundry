"""Tests for the ngrok tunnel helper."""

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.ngrok_tunnel import (
    start_tunnel,
    stop_tunnel,
    _configure_auth,
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


# ── stop_tunnel ──────────────────────────────────────────────


def test_stop_tunnel_disconnects_and_kills():
    """stop_tunnel should call disconnect_all and kill."""
    with patch("crewai_productfeature_planner.scripts.ngrok_tunnel.ngrok") as mock_ngrok:
        stop_tunnel()

    mock_ngrok.disconnect_all.assert_called_once()
    mock_ngrok.kill.assert_called_once()
