"""Ngrok tunnel helper and public URL resolution.

Provides three main capabilities:

1. **Ngrok tunnel management** — :func:`start_tunnel` / :func:`stop_tunnel`
2. **Public URL resolution** — :func:`get_public_url` reads ``SERVER_ENV``
   to determine the correct public-facing URL:

   * ``DEV``  — starts an ngrok tunnel and returns the tunnel URL.
   * ``UAT``  — returns ``https://{DOMAIN_NAME_UAT}``, no tunnel.
   * ``PROD`` — returns ``https://{DOMAIN_NAME_PROD}``, no tunnel.

3. **Environment helper** — :func:`get_server_env` returns the normalised
   ``SERVER_ENV`` value (``DEV``, ``UAT``, or ``PROD``; default ``DEV``).

Requires ``NGROK_AUTHTOKEN`` for DEV mode, ``DOMAIN_NAME_UAT`` for UAT,
and ``DOMAIN_NAME_PROD`` for PROD.
"""

from __future__ import annotations

import logging
import os
import ssl

import certifi
from pyngrok import conf, ngrok

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Suppress noisy pyngrok process-level ERROR logs (e.g. stale tunnel
# cleanup on restart).  Genuine failures are caught by our own code.
logging.getLogger("pyngrok").setLevel(logging.CRITICAL)

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


# ---------------------------------------------------------------------------
# SERVER_ENV & public URL resolution
# ---------------------------------------------------------------------------

_VALID_SERVER_ENVS = {"DEV", "UAT", "PROD"}


def get_server_env() -> str:
    """Return the normalised ``SERVER_ENV`` value (``DEV``, ``UAT``, or ``PROD``).

    Defaults to ``DEV`` when the variable is unset or empty.
    Raises ``ValueError`` for unrecognised values.
    """
    raw = os.environ.get("SERVER_ENV", "DEV").strip().upper()
    if raw not in _VALID_SERVER_ENVS:
        raise ValueError(
            f"Invalid SERVER_ENV='{raw}'. Must be one of: {sorted(_VALID_SERVER_ENVS)}"
        )
    return raw


def is_dev() -> bool:
    """Return ``True`` when running in DEV mode (ngrok tunnel)."""
    return get_server_env() == "DEV"


def get_public_url(port: int = DEFAULT_PORT) -> str:
    """Resolve the public URL based on ``SERVER_ENV``.

    * ``DEV``  — starts an ngrok tunnel on *port* and returns the tunnel URL.
    * ``UAT``  — returns ``https://{DOMAIN_NAME_UAT}``.
    * ``PROD`` — returns ``https://{DOMAIN_NAME_PROD}``.

    Raises ``RuntimeError`` when a required env var is missing.
    """
    env = get_server_env()

    if env == "DEV":
        logger.info("[Env] SERVER_ENV=DEV — starting ngrok tunnel on port %d", port)
        return start_tunnel(port=port)

    if env == "UAT":
        domain = os.environ.get("DOMAIN_NAME_UAT", "").strip()
        if not domain:
            raise RuntimeError(
                "SERVER_ENV=UAT but DOMAIN_NAME_UAT is not set. "
                "Add it to your .env file."
            )
    else:  # PROD
        domain = os.environ.get("DOMAIN_NAME_PROD", "").strip()
        if not domain:
            raise RuntimeError(
                "SERVER_ENV=PROD but DOMAIN_NAME_PROD is not set. "
                "Add it to your .env file."
            )

    # Ensure the domain has a scheme
    if not domain.startswith("http"):
        domain = f"https://{domain}"

    logger.info("[Env] SERVER_ENV=%s — using domain %s", env, domain)
    return domain
