"""Async MongoDB client using Motor for FastAPI endpoints.

Provides a native async ``AsyncIOMotorClient`` for use in FastAPI
handlers, eliminating the need for ``run_in_executor`` wrappers.
The synchronous ``pymongo`` client (in ``client.py``) remains for
CrewAI agents, orchestrator, and other sync code.

Connection uses the same ``MONGODB_ATLAS_URI`` and ``MONGODB_DB``
environment variables as the synchronous client.
"""

from __future__ import annotations

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from crewai_productfeature_planner.mongodb.client import (
    _build_uri,
    _get_db_name,
    _SERVER_SELECTION_TIMEOUT_MS,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_async_client: AsyncIOMotorClient | None = None


def get_async_client() -> AsyncIOMotorClient:
    """Return a shared Motor client (lazy-initialised)."""
    global _async_client
    if _async_client is None:
        uri = _build_uri()
        safe_host = uri.split("@")[-1] if "@" in uri else uri
        logger.info("Motor async client connecting to %s", safe_host)
        _async_client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
            tls=True,
            tlsCAFile=certifi.where(),
        )
    return _async_client


def get_async_db() -> AsyncIOMotorDatabase:
    """Return the configured async database handle."""
    return get_async_client()[_get_db_name()]


def reset_async_client() -> None:
    """Close and clear the shared async client (useful for testing)."""
    global _async_client
    if _async_client is not None:
        _async_client.close()
        _async_client = None
