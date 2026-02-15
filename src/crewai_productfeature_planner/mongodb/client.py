"""MongoDB client configuration and connection management.

Connection is configured via environment variables:
    - ``MONGODB_URI``      — host (default ``localhost``)
    - ``MONGODB_PORT``     — port (default ``27017``)
    - ``MONGODB_DB``       — database name (default ``ideas``)
    - ``MONGODB_USERNAME`` — (optional)
    - ``MONGODB_PASSWORD`` — (optional)

The full ``mongodb://`` connection string is constructed automatically.
When both username and password are provided the URI becomes
``mongodb://user:pass@host:port``.
"""

import os

from pymongo import MongoClient

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DB_NAME = "ideas"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = "27017"

# Connection timeout — fail fast instead of hanging for 30 s.
_SERVER_SELECTION_TIMEOUT_MS = 5_000

_client: MongoClient | None = None


def _get_db_name() -> str:
    """Resolve the database name from ``MONGODB_DB`` env var or default."""
    return os.environ.get("MONGODB_DB", "").strip() or DEFAULT_DB_NAME


def _build_uri() -> str:
    """Build the full ``mongodb://`` connection string.

    ``MONGODB_URI`` is the host (e.g. ``localhost``) and ``MONGODB_PORT``
    is the port (e.g. ``27017``).  If the host already contains a scheme
    or port it is normalised so the result is always consistent.

    When both ``MONGODB_USERNAME`` and ``MONGODB_PASSWORD`` are set the
    credentials are embedded: ``mongodb://user:pass@host:port``.
    """
    host = os.environ.get("MONGODB_URI", DEFAULT_HOST).strip()
    port = os.environ.get("MONGODB_PORT", DEFAULT_PORT).strip() or DEFAULT_PORT

    # Strip scheme if the user accidentally included it
    if host.startswith("mongodb+srv://"):
        host = host[len("mongodb+srv://"):]
    elif host.startswith("mongodb://"):
        host = host[len("mongodb://"):]

    # Strip any embedded credentials
    if "@" in host:
        host = host.split("@", 1)[1]

    # Strip port from host if it was included there
    if ":" in host:
        host, port = host.rsplit(":", 1)

    username = os.environ.get("MONGODB_USERNAME", "").strip()
    password = os.environ.get("MONGODB_PASSWORD", "").strip()

    if username and password:
        return f"mongodb://{username}:{password}@{host}:{port}"
    return f"mongodb://{host}:{port}"


def get_client() -> MongoClient:
    """Return a shared MongoClient (lazy-initialised)."""
    global _client
    if _client is None:
        uri = _build_uri()
        logger.info("Connecting to MongoDB at %s", uri.split("@")[-1])
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
        )
    return _client


def get_db():
    """Return the configured database handle."""
    return get_client()[_get_db_name()]


def reset_client() -> None:
    """Close and clear the shared client (useful for testing)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
