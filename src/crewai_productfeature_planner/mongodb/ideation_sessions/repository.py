"""CRUD operations for the ``ideationSessions`` collection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb._tenant import (
    TenantContext,
    tenant_fields,
    tenant_filter,
)
from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

IDEATION_SESSIONS_COLLECTION = "ideationSessions"

# Ordered list of flow steps.
STEP_ORDER: list[str] = ["a", "b", "c", "d", "e"]

STEP_LABELS: dict[str, str] = {
    "a": "Ideation",
    "b": "Persona",
    "c": "Solution",
    "d": "Primary Goal",
    "e": "Technical Stack",
}

# Bidirectional mapping: internal letter ↔ frontend step name.
STEP_TO_NAME: dict[str, str] = {
    "a": "ideation",
    "b": "persona",
    "c": "solution",
    "d": "primary_goal",
    "e": "tech_stack",
}
NAME_TO_STEP: dict[str, str] = {v: k for k, v in STEP_TO_NAME.items()}


def step_to_name(step: str) -> str:
    """Convert internal step letter to frontend name (e.g. 'a' → 'ideation')."""
    return STEP_TO_NAME.get(step, step)


def name_to_step(name: str) -> str:
    """Convert frontend step name to internal letter (e.g. 'ideation' → 'a')."""
    return NAME_TO_STEP.get(name, name)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col():
    return get_db()[IDEATION_SESSIONS_COLLECTION]


# ── write ─────────────────────────────────────────────────────


def create_session(
    *,
    user_id: str,
    title: str | None = None,
    project_id: str | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Create a new ideation session and return the full document.

    Returns:
        The inserted session document, or ``None`` on failure.
    """
    session_id = uuid.uuid4().hex
    now = _now_iso()

    doc: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "project_id": project_id,
        "title": title or "Untitled Idea",
        "status": "active",
        "current_step": "a",
        "steps_data": {
            step: {"input": None, "output": None, "approved": False, "completed_at": None}
            for step in STEP_ORDER
        },
        "messages": [],
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        **(tenant_fields(tenant) if tenant else {}),
    }

    try:
        _col().insert_one(doc)
        logger.info(
            "[IdeationSession] Created session=%s user=%s title=%r",
            session_id,
            user_id,
            doc["title"],
        )
        doc.pop("_id", None)
        return doc
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to create session for user=%s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return None


def append_message(
    *,
    session_id: str,
    role: str,
    content: str,
    step: str,
    metadata: dict | None = None,
    agent_name: str | None = None,
    content_type: str | None = None,
    tenant: TenantContext | None = None,
) -> str | None:
    """Append a message to the session's message array.

    Args:
        role: 'user', 'agent', or 'system'.
        content: Markdown text content.
        step: Which flow step ('a'-'e') this message belongs to.
        metadata: Optional structured data (e.g. render_type, questions).
        agent_name: Agent identifier (e.g. 'product_ideation_specialist').
        content_type: Content format: 'text', 'markdown', or 'cards'.

    Returns:
        The message ``id`` on success, or ``None`` on failure.
    """
    msg_id = uuid.uuid4().hex
    now = _now_iso()

    message: dict = {
        "id": msg_id,
        "role": role,
        "content": content,
        "step": step,
        "timestamp": now,
    }
    if agent_name:
        message["agent_name"] = agent_name
    if content_type:
        message["content_type"] = content_type
    if metadata:
        message["metadata"] = metadata

    try:
        result = _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": now},
            },
        )
        if result.modified_count == 0:
            logger.warning(
                "[IdeationSession] No session found to append message: session=%s",
                session_id,
            )
            return None
        return msg_id
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to append message session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None


def save_step_data(
    *,
    session_id: str,
    step: str,
    input_data: Any = None,
    output_data: Any = None,
    approved: bool = False,
    tenant: TenantContext | None = None,
) -> bool:
    """Save input/output data for a specific step.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    update: dict[str, Any] = {"updated_at": now}

    if input_data is not None:
        update[f"steps_data.{step}.input"] = input_data
    if output_data is not None:
        update[f"steps_data.{step}.output"] = output_data
    if approved:
        update[f"steps_data.{step}.approved"] = True
        update[f"steps_data.{step}.completed_at"] = now

    try:
        result = _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {"$set": update},
        )
        if result.modified_count == 0:
            logger.warning(
                "[IdeationSession] No session updated for step data: session=%s step=%s",
                session_id,
                step,
            )
            return False
        logger.info(
            "[IdeationSession] Saved step data session=%s step=%s approved=%s",
            session_id,
            step,
            approved,
        )
        return True
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to save step data session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return False


def advance_step(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> str | None:
    """Advance the session to the next step.

    Marks the current step as approved and moves ``current_step`` forward.
    If already on the last step ('e'), marks the session as completed.

    Returns:
        The new step letter, or ``None`` if already at end or on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return None

    current = session["current_step"]
    current_idx = STEP_ORDER.index(current)
    now = _now_iso()

    # Mark current step as approved
    save_step_data(session_id=session_id, step=current, approved=True, tenant=tenant)

    if current_idx >= len(STEP_ORDER) - 1:
        # Last step — complete the session
        complete_session(session_id=session_id, tenant=tenant)
        return None

    next_step = STEP_ORDER[current_idx + 1]

    try:
        _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {"$set": {"current_step": next_step, "updated_at": now}},
        )
        logger.info(
            "[IdeationSession] Advanced session=%s from step=%s to step=%s",
            session_id,
            current,
            next_step,
        )
        return next_step
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to advance session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None


def rollback_step(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> str | None:
    """Roll back the session to the previous step.

    Returns:
        The previous step letter, or ``None`` if already at start or on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return None

    current = session["current_step"]
    current_idx = STEP_ORDER.index(current)

    if current_idx == 0:
        logger.warning(
            "[IdeationSession] Cannot rollback — already at first step: session=%s",
            session_id,
        )
        return None

    prev_step = STEP_ORDER[current_idx - 1]
    now = _now_iso()

    try:
        _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {
                "$set": {
                    "current_step": prev_step,
                    f"steps_data.{prev_step}.approved": False,
                    f"steps_data.{prev_step}.completed_at": None,
                    "updated_at": now,
                },
            },
        )
        logger.info(
            "[IdeationSession] Rolled back session=%s from step=%s to step=%s",
            session_id,
            current,
            prev_step,
        )
        return prev_step
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to rollback session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None


def complete_session(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Mark a session as completed.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    try:
        result = _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {"$set": {"status": "completed", "completed_at": now, "updated_at": now}},
        )
        if result.modified_count:
            logger.info("[IdeationSession] Completed session=%s", session_id)
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to complete session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return False


def update_session_status(
    *,
    session_id: str,
    status: str,
    tenant: TenantContext | None = None,
) -> bool:
    """Update session status ('active', 'completed', 'abandoned').

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    now = _now_iso()
    update: dict[str, Any] = {"status": status, "updated_at": now}
    if status in ("completed", "abandoned"):
        update["completed_at"] = now

    try:
        result = _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {"$set": update},
        )
        if result.modified_count:
            logger.info(
                "[IdeationSession] Updated status session=%s status=%s",
                session_id,
                status,
            )
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to update status session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return False


# ── queries ───────────────────────────────────────────────────


def get_session(
    *,
    session_id: str,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Fetch a single session by ID.

    Returns:
        The session document (without ``_id``), or ``None``.
    """
    try:
        doc = _col().find_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {"_id": 0},
        )
        return doc
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to get session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None


def list_sessions(
    *,
    user_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant: TenantContext | None = None,
) -> list[dict[str, Any]]:
    """List sessions for a user, newest first.

    Args:
        user_id: The SSO user ID.
        status: Optional filter by status ('active', 'completed', 'abandoned').
        limit: Max results to return.
        offset: Number of results to skip.

    Returns:
        List of session documents (without ``_id`` or ``messages``).
    """
    query: dict[str, Any] = {"user_id": user_id, **tenant_filter(tenant)}
    if status:
        query["status"] = status
    else:
        # Exclude soft-deleted and archived sessions by default.
        query["status"] = {"$nin": ["archived", "deleted"]}

    try:
        cursor = (
            _col()
            .find(query, {"_id": 0, "messages": 0})
            .sort("created_at", DESCENDING)
            .skip(offset)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to list sessions user=%s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return []


def get_messages(
    *,
    session_id: str,
    step: str | None = None,
    tenant: TenantContext | None = None,
) -> list[dict[str, Any]]:
    """Get messages for a session, optionally filtered by step.

    Returns:
        List of message dicts, or empty list on failure.
    """
    session = get_session(session_id=session_id, tenant=tenant)
    if not session:
        return []

    messages = session.get("messages") or []
    if step:
        messages = [m for m in messages if m.get("step") == step]
    return messages


def count_sessions(
    *,
    user_id: str,
    status: str | None = None,
    search: str | None = None,
    project_id: str | None = None,
    tenant: TenantContext | None = None,
) -> int:
    """Count sessions matching filters (for pagination)."""
    query: dict[str, Any] = {"user_id": user_id, **tenant_filter(tenant)}
    if status:
        query["status"] = status
    else:
        # Exclude soft-deleted and archived sessions by default.
        query["status"] = {"$nin": ["archived", "deleted"]}
    if project_id:
        query["project_id"] = project_id
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    try:
        return _col().count_documents(query)
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to count sessions user=%s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return 0


def list_sessions_paginated(
    *,
    user_id: str,
    status: str | None = None,
    project_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext | None = None,
) -> list[dict[str, Any]]:
    """List sessions with pagination support, newest first."""
    query: dict[str, Any] = {"user_id": user_id, **tenant_filter(tenant)}
    if status:
        query["status"] = status
    else:
        # Exclude soft-deleted and archived sessions by default.
        query["status"] = {"$nin": ["archived", "deleted"]}
    if project_id:
        query["project_id"] = project_id
    if search:
        query["title"] = {"$regex": search, "$options": "i"}

    offset = (page - 1) * page_size
    try:
        cursor = (
            _col()
            .find(query, {"_id": 0, "messages": 0})
            .sort("created_at", DESCENDING)
            .skip(offset)
            .limit(page_size)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to list_sessions_paginated user=%s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return []


def update_session_metadata(
    *,
    session_id: str,
    title: str | None = None,
    project_id: str | None = None,
    tenant: TenantContext | None = None,
) -> dict[str, Any] | None:
    """Update session metadata (title and/or project_id).

    Returns:
        The updated session document, or None on failure.
    """
    now = _now_iso()
    update: dict[str, Any] = {"updated_at": now}
    if title is not None:
        update["title"] = title
    if project_id is not None:
        update["project_id"] = project_id

    if len(update) == 1:
        # Nothing to update besides updated_at
        return get_session(session_id=session_id, tenant=tenant)

    try:
        _col().update_one(
            {"session_id": session_id, **tenant_filter(tenant)},
            {"$set": update},
        )
        logger.info(
            "[IdeationSession] Updated metadata session=%s title=%r project=%s",
            session_id,
            title,
            project_id,
        )
        return get_session(session_id=session_id, tenant=tenant)
    except PyMongoError as exc:
        logger.error(
            "[IdeationSession] Failed to update metadata session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return None
