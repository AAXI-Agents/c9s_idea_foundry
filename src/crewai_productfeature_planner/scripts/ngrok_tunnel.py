"""Ngrok tunnel helper for remote access.

Usage:
    from crewai_productfeature_planner.ngrok_tunnel import start_tunnel, stop_tunnel

    # Open a tunnel on port 8000
    public_url = start_tunnel(port=8000)
    print(f"Remote URL: {public_url}")

    # When done
    stop_tunnel()

Requires NGROK_AUTHTOKEN in the environment (loaded from .env).
"""

import os
import ssl

import certifi
from pyngrok import conf, ngrok

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_PORT = 8000


def _configure_auth() -> None:
    """Set the ngrok auth token and SSL certs from the environment."""
    token = os.environ.get("NGROK_AUTHTOKEN", "")
    if not token:
        raise RuntimeError(
            "NGROK_AUTHTOKEN is not set. "
            "Add it to your .env or export it in the shell."
        )
    # Ensure SSL uses certifi CA bundle (fixes macOS / pyenv cert errors)
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    ssl._create_default_https_context = ssl.create_default_context  # noqa: SLF001

    conf.get_default().auth_token = token
    logger.debug("Ngrok auth token configured")


def start_tunnel(port: int = DEFAULT_PORT, **kwargs) -> str:
    """Open an ngrok tunnel and return the public URL.

    When the ``NGROK_DOMAIN`` environment variable is set (e.g.
    ``myapp.ngrok-free.dev``), pyngrok will request that specific
    static domain so the public URL stays the same across restarts.
    Ngrok's free tier includes **one** static domain — claim yours at
    https://dashboard.ngrok.com/domains.

    Args:
        port: Local port to expose (default 8000).
        **kwargs: Extra args forwarded to ``ngrok.connect()``
                  (e.g. ``proto="http"``, ``domain="myapp.ngrok-free.dev"``).

    Returns:
        The public https URL assigned by ngrok.
    """
    _configure_auth()

    # Use a stable domain when NGROK_DOMAIN is set and caller didn't
    # explicitly pass ``domain`` (or the legacy ``subdomain``) kwarg.
    ngrok_domain = os.environ.get("NGROK_DOMAIN", "").strip()
    if ngrok_domain and "domain" not in kwargs and "subdomain" not in kwargs:
        kwargs["domain"] = ngrok_domain
        logger.info("Using static ngrok domain: %s", ngrok_domain)

    tunnel = ngrok.connect(port, **kwargs)
    public_url = tunnel.public_url
    logger.info("Ngrok tunnel opened: %s -> localhost:%d", public_url, port)
    return public_url


def stop_tunnel() -> None:
    """Disconnect all active ngrok tunnels."""
    ngrok.disconnect_all()
    ngrok.kill()
    logger.info("All ngrok tunnels closed")
