"""MongoDB-based distributed lease for leader election.

Provides a simple lease mechanism so only one application instance
at a time runs singleton tasks (e.g. the Slack token refresh scheduler).

Lease document schema::

    {
        "lease_name":  str,               # unique key (e.g. "token_refresh")
        "holder":      str,               # instance ID of the current holder
        "expires_at":  float,             # UTC epoch when the lease expires
        "acquired_at": str (ISO-8601),    # when the lease was last acquired/renewed
    }

A lease is acquired via an atomic ``find_one_and_update`` with a filter
that matches either an expired lease or one held by the same instance.
This guarantees at most one holder at any time.
"""

from crewai_productfeature_planner.mongodb.leases.repository import (
    LEASES_COLLECTION,
    acquire_lease,
    release_lease,
    renew_lease,
)

__all__ = [
    "LEASES_COLLECTION",
    "acquire_lease",
    "release_lease",
    "renew_lease",
]
