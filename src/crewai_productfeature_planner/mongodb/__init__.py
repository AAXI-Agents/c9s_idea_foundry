"""MongoDB persistence package.

Re-exports public symbols for backward-compatible imports::

    from crewai_productfeature_planner.mongodb import save_iteration, save_finalized

Sub-modules:
    - ``mongodb.client``               — connection management
    - ``mongodb.working_ideas``        — ``workingIdeas`` collection
    - ``mongodb.finalized_ideas``      — ``finalizeIdeas`` collection
"""

from crewai_productfeature_planner.mongodb.client import (
    DEFAULT_DB_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    _build_uri,
    _get_db_name,
    get_client,
    get_db,
    reset_client,
)
from crewai_productfeature_planner.mongodb.finalized_ideas.repository import (
    FINALIZED_COLLECTION,
    save_finalized,
)
from crewai_productfeature_planner.mongodb.working_ideas.repository import (
    WORKING_COLLECTION,
    find_unfinalized,
    get_run_documents,
    save_failed,
    save_iteration,
)

__all__ = [
    "DEFAULT_DB_NAME",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "FINALIZED_COLLECTION",
    "WORKING_COLLECTION",
    "_build_uri",
    "_get_db_name",
    "find_unfinalized",
    "get_client",
    "get_db",
    "get_run_documents",
    "reset_client",
    "save_failed",
    "save_finalized",
    "save_iteration",
]
