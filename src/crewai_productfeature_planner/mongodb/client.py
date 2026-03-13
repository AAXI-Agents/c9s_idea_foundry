"""MongoDB client configuration and connection management.

Connection is configured via environment variables:
    - ``MONGODB_ATLAS_URI`` — full ``mongodb+srv://`` connection string (required)
    - ``MONGODB_DB``        — database name (default ``ideas``)

The Atlas URI is used directly as the connection string.  It must be a
valid ``mongodb+srv://`` or ``mongodb://`` URI including credentials.
"""

import os

import certifi
from pymongo import MongoClient

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DB_NAME = "ideas"

# Connection timeout — fail fast instead of hanging for 30 s.
_SERVER_SELECTION_TIMEOUT_MS = 5_000

_client: MongoClient | None = None


def _get_db_name() -> str:
    """Resolve the database name from ``MONGODB_DB`` env var or default."""
    return os.environ.get("MONGODB_DB", "").strip() or DEFAULT_DB_NAME


def _build_uri() -> str:
    """Return the ``MONGODB_ATLAS_URI`` connection string.

    Raises ``RuntimeError`` if the variable is not set or empty.
    """
    uri = os.environ.get("MONGODB_ATLAS_URI", "").strip()
    if not uri:
        raise RuntimeError(
            "MONGODB_ATLAS_URI environment variable is required but not set. "
            "Provide a valid mongodb+srv:// connection string."
        )
    return uri


def get_client() -> MongoClient:
    """Return a shared MongoClient (lazy-initialised)."""
    global _client
    if _client is None:
        uri = _build_uri()
        # Log the host portion only (after @) to avoid leaking credentials.
        safe_host = uri.split("@")[-1] if "@" in uri else uri
        logger.info("Connecting to MongoDB Atlas at %s", safe_host)
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
            tls=True,
            tlsCAFile=certifi.where(),
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
