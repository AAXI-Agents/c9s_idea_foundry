"""product_requirements sub-package — tracks Confluence & Jira delivery state.

The ``productRequirements`` collection records per-run delivery status
so the startup orchestrator can resume incomplete publishes without
repeating work.

Re-exports the public repository API::

    from crewai_productfeature_planner.mongodb.product_requirements import (
        find_pending_delivery,
        get_delivery_record,
        upsert_delivery_record,
    )
"""

from crewai_productfeature_planner.mongodb.product_requirements.repository import (
    PRODUCT_REQUIREMENTS_COLLECTION,
    find_pending_delivery,
    get_delivery_record,
    upsert_delivery_record,
)

__all__ = [
    "PRODUCT_REQUIREMENTS_COLLECTION",
    "find_pending_delivery",
    "get_delivery_record",
    "upsert_delivery_record",
]
