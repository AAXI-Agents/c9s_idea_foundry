"""CRUD operations for the ``leases`` MongoDB collection.

Implements a distributed lease (leader election) using MongoDB's
atomic ``find_one_and_update``.  Only one application instance can
hold a given lease at a time.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

LEASES_COLLECTION = "leases"

_DEFAULT_TTL_SECONDS = 120  # 2 minutes


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _instance_id() -> str:
    """Return a unique identifier for this process instance.

    Combines hostname and PID so each container/process gets a
    distinct identity without requiring external configuration.
    """
    import socket

    return f"{socket.gethostname()}-{os.getpid()}"


def acquire_lease(
    lease_name: str,
    *,
    ttl_seconds: int | None = None,
    holder: str | None = None,
) -> bool:
    """Try to acquire (or re-acquire) the named lease.

    The lease is granted when:

    * No document exists for ``lease_name`` (first acquisition).
    * The existing lease has expired (``expires_at < now``).
    * The existing lease is held by the same ``holder`` (renewal).

    Returns ``True`` if this instance now holds the lease.
    """
    ttl = ttl_seconds or _DEFAULT_TTL_SECONDS
    holder = holder or _instance_id()
    now = time.time()
    now_iso = _now_iso()

    try:
        result = get_db()[LEASES_COLLECTION].find_one_and_update(
            {
                "lease_name": lease_name,
                "$or": [
                    {"expires_at": {"$lt": now}},
                    {"holder": holder},
                ],
            },
            {
                "$set": {
                    "holder": holder,
                    "expires_at": now + ttl,
                    "acquired_at": now_iso,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if result and result.get("holder") == holder:
            logger.debug(
                "[Lease] Acquired '%s' (holder=%s, ttl=%ds)",
                lease_name,
                holder,
                ttl,
            )
            return True
    except PyMongoError as exc:
        # DuplicateKeyError is expected when two instances race to
        # create the document — the loser simply doesn't hold the lease.
        if "duplicate key" in str(exc).lower():
            logger.debug(
                "[Lease] Lost race for '%s' — another instance acquired it",
                lease_name,
            )
            return False
        logger.warning(
            "[Lease] Failed to acquire '%s': %s", lease_name, exc,
        )
    return False


def renew_lease(
    lease_name: str,
    *,
    ttl_seconds: int | None = None,
    holder: str | None = None,
) -> bool:
    """Extend the lease TTL if still held by this instance.

    Returns ``True`` if the lease was successfully renewed.
    """
    ttl = ttl_seconds or _DEFAULT_TTL_SECONDS
    holder = holder or _instance_id()
    now = time.time()

    try:
        result = get_db()[LEASES_COLLECTION].update_one(
            {"lease_name": lease_name, "holder": holder},
            {
                "$set": {
                    "expires_at": now + ttl,
                    "acquired_at": _now_iso(),
                },
            },
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        logger.warning(
            "[Lease] Failed to renew '%s': %s", lease_name, exc,
        )
        return False


def release_lease(
    lease_name: str,
    *,
    holder: str | None = None,
) -> bool:
    """Release the lease so another instance can acquire it.

    Only succeeds if the lease is currently held by ``holder``.
    Returns ``True`` if the lease was released.
    """
    holder = holder or _instance_id()

    try:
        result = get_db()[LEASES_COLLECTION].delete_one(
            {"lease_name": lease_name, "holder": holder},
        )
        released = result.deleted_count > 0
        if released:
            logger.debug("[Lease] Released '%s'", lease_name)
        return released
    except PyMongoError as exc:
        logger.warning(
            "[Lease] Failed to release '%s': %s", lease_name, exc,
        )
        return False
