"""Repository for the ``agentInteraction`` collection.

Tracks every agent interaction from Slack or CLI for fine-tuning data.

Standard document schema
------------------------
::

    {
        "interaction_id":     str,              # unique identifier (UUID hex)
        "source":             str,              # "slack" | "cli" | "slack_interactive"
        "user_message":       str,              # the raw user message / input
        "intent":             str,              # classified intent (create_prd, help, etc.)
        "agent_response":     str,              # the agent's reply / response text
        "idea":               str | None,       # extracted idea (if any)
        "run_id":             str | None,       # associated flow run_id (if any)
        "project_id":         str | None,       # FK → projectConfig.project_id
        "channel":            str | None,       # Slack channel (if from Slack)
        "thread_ts":          str | None,       # Slack thread timestamp (if from Slack)
        "user_id":            str | None,       # Slack user ID or "cli_user"
        "conversation_history": list | None,    # conversation context (for training)
        "metadata":           dict | None,      # additional context (interactive mode, etc.)
        "created_at":         datetime (UTC),   # when the interaction occurred
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import PyMongoError

from crewai_productfeature_planner.mongodb.client import get_db
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

AGENT_INTERACTIONS_COLLECTION = "agentInteraction"


# ── write ─────────────────────────────────────────────────────


def log_interaction(
    *,
    source: str,
    user_message: str,
    intent: str,
    agent_response: str,
    idea: str | None = None,
    run_id: str | None = None,
    project_id: str | None = None,
    channel: str | None = None,
    thread_ts: str | None = None,
    user_id: str | None = None,
    conversation_history: list[dict] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """Insert a new agent interaction document.

    Args:
        source: Origin of the interaction (``"slack"``, ``"cli"``,
            ``"slack_interactive"``).
        user_message: The raw text the user sent.
        intent: The classified intent (``"create_prd"``, ``"help"``,
            ``"greeting"``, ``"publish"``, ``"check_publish"``,
            ``"unknown"``, or a CLI action like ``"refinement_mode"``,
            ``"idea_approval"``, ``"requirements_approval"``).
        agent_response: The text the agent sent back to the user.
        idea: Extracted product/feature idea, if any.
        run_id: Associated flow run identifier, if any.
        project_id: Associated project configuration ID, if any.
        channel: Slack channel ID (Slack interactions only).
        thread_ts: Slack thread timestamp (Slack interactions only).
        user_id: Slack user ID or ``"cli_user"``.
        conversation_history: Thread history for fine-tuning context.
        metadata: Any additional context (e.g. ``{"interactive": True}``).

    Returns:
        The ``interaction_id`` on success, or ``None`` on failure.
    """
    interaction_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    doc: dict[str, Any] = {
        "interaction_id": interaction_id,
        "source": source,
        "user_message": user_message,
        "intent": intent,
        "agent_response": agent_response,
        "idea": idea,
        "run_id": run_id,
        "project_id": project_id,
        "channel": channel,
        "thread_ts": thread_ts,
        "user_id": user_id,
        "conversation_history": conversation_history,
        "metadata": metadata,
        "created_at": now,
    }

    try:
        get_db()[AGENT_INTERACTIONS_COLLECTION].insert_one(doc)
        logger.info(
            "[AgentInteraction] Logged interaction %s (source=%s, intent=%s)",
            interaction_id,
            source,
            intent,
        )
        return interaction_id
    except PyMongoError as exc:
        logger.error(
            "[AgentInteraction] Failed to log interaction: %s", exc
        )
        return None


# ── queries ───────────────────────────────────────────────────


def get_interaction(interaction_id: str) -> dict[str, Any] | None:
    """Find a single interaction by its ``interaction_id``.

    Returns:
        The interaction document, or ``None``.
    """
    try:
        return get_db()[AGENT_INTERACTIONS_COLLECTION].find_one(
            {"interaction_id": interaction_id}
        )
    except PyMongoError as exc:
        logger.error("[AgentInteraction] Failed to find interaction %s: %s",
                     interaction_id, exc)
        return None


def find_interactions_by_source(
    source: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return interactions filtered by source, newest first.

    Args:
        source: ``"slack"``, ``"cli"``, or ``"slack_interactive"``.
        limit: Maximum number of documents to return.

    Returns:
        List of interaction documents.
    """
    try:
        cursor = (
            get_db()[AGENT_INTERACTIONS_COLLECTION]
            .find({"source": source})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error("[AgentInteraction] Failed to query by source %s: %s",
                     source, exc)
        return []


def find_interactions_by_intent(
    intent: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return interactions filtered by intent, newest first.

    Args:
        intent: The intent name (e.g. ``"create_prd"``).
        limit: Maximum number of documents to return.

    Returns:
        List of interaction documents.
    """
    try:
        cursor = (
            get_db()[AGENT_INTERACTIONS_COLLECTION]
            .find({"intent": intent})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error("[AgentInteraction] Failed to query by intent %s: %s",
                     intent, exc)
        return []


def find_interactions(
    *,
    source: str | None = None,
    intent: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Flexible query for interactions with optional filters.

    All filter parameters are optional.  When omitted, no filtering
    is applied for that field.

    Args:
        source: Filter by source.
        intent: Filter by intent.
        user_id: Filter by user ID.
        run_id: Filter by run ID.
        since: Return only interactions created after this datetime.
        limit: Maximum number of documents to return.

    Returns:
        List of interaction documents, newest first.
    """
    query: dict[str, Any] = {}
    if source is not None:
        query["source"] = source
    if intent is not None:
        query["intent"] = intent
    if user_id is not None:
        query["user_id"] = user_id
    if run_id is not None:
        query["run_id"] = run_id
    if since is not None:
        query["created_at"] = {"$gte": since}

    try:
        cursor = (
            get_db()[AGENT_INTERACTIONS_COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error("[AgentInteraction] Failed to query interactions: %s", exc)
        return []


def list_interactions(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent interactions, newest first.

    Args:
        limit: Maximum number of documents to return.

    Returns:
        List of interaction documents.
    """
    try:
        cursor = (
            get_db()[AGENT_INTERACTIONS_COLLECTION]
            .find()
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except PyMongoError as exc:
        logger.error("[AgentInteraction] Failed to list interactions: %s", exc)
        return []
