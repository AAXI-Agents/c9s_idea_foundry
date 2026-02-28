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
        "predicted_next_step": dict | None,     # LLM-predicted next action for the user
        "next_step_accepted":  bool | None,     # whether user followed the prediction
        "next_step_feedback_at": datetime | None, # when the feedback was recorded
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
    predicted_next_step: dict[str, Any] | None = None,
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
        predicted_next_step: LLM-predicted next action for the user
            (e.g. ``{"next_step": "configure_confluence",
            "message": "...", "confidence": 0.8, "reason": "..."}``).

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
        "predicted_next_step": predicted_next_step,
        "next_step_accepted": None,
        "next_step_feedback_at": None,
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


# ── next-step prediction tracking ─────────────────────────────


def update_next_step_prediction(
    interaction_id: str,
    predicted_next_step: dict[str, Any],
) -> bool:
    """Store the LLM's predicted next step on an existing interaction.

    Args:
        interaction_id: The ``interaction_id`` to update.
        predicted_next_step: Dict with ``next_step``, ``message``,
            ``confidence``, ``reason``.

    Returns:
        ``True`` if the document was updated, ``False`` otherwise.
    """
    try:
        result = get_db()[AGENT_INTERACTIONS_COLLECTION].update_one(
            {"interaction_id": interaction_id},
            {"$set": {"predicted_next_step": predicted_next_step}},
        )
        if result.modified_count:
            logger.info(
                "[AgentInteraction] Updated next-step prediction for %s: %s",
                interaction_id,
                predicted_next_step.get("next_step", ""),
            )
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[AgentInteraction] Failed to update next-step prediction: %s",
            exc,
        )
        return False


def record_next_step_feedback(
    interaction_id: str,
    accepted: bool,
) -> bool:
    """Record whether the user followed the predicted next step.

    Called when the user clicks "Accept" or "Dismiss" on the
    next-step suggestion block, or when the user's next action
    matches or differs from the prediction.

    Args:
        interaction_id: The ``interaction_id`` whose prediction to update.
        accepted: ``True`` if the user followed the suggestion,
            ``False`` if they dismissed or chose a different action.

    Returns:
        ``True`` if the document was updated, ``False`` otherwise.
    """
    now = datetime.now(timezone.utc)
    try:
        result = get_db()[AGENT_INTERACTIONS_COLLECTION].update_one(
            {"interaction_id": interaction_id},
            {
                "$set": {
                    "next_step_accepted": accepted,
                    "next_step_feedback_at": now,
                },
            },
        )
        if result.modified_count:
            logger.info(
                "[AgentInteraction] Next-step feedback for %s: accepted=%s",
                interaction_id,
                accepted,
            )
            return True
        return False
    except PyMongoError as exc:
        logger.error(
            "[AgentInteraction] Failed to record next-step feedback: %s",
            exc,
        )
        return False


def get_next_step_accuracy(
    *,
    user_id: str | None = None,
    since: datetime | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Calculate the accuracy of LLM next-step predictions.

    Returns a summary dict with total predictions, accepted/rejected
    counts, accuracy percentage, and per-step breakdown.

    Args:
        user_id: Optionally filter by user.
        since: Optionally filter interactions after this datetime.
        limit: Max interactions to consider.

    Returns:
        Dict with ``total``, ``accepted``, ``rejected``,
        ``pending`` (no feedback yet), ``accuracy``, and
        ``by_step`` breakdown.
    """
    query: dict[str, Any] = {
        "predicted_next_step": {"$ne": None},
    }
    if user_id:
        query["user_id"] = user_id
    if since:
        query["created_at"] = {"$gte": since}

    try:
        cursor = (
            get_db()[AGENT_INTERACTIONS_COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        docs = list(cursor)
    except PyMongoError as exc:
        logger.error(
            "[AgentInteraction] Failed to query prediction accuracy: %s",
            exc,
        )
        return {"total": 0, "accepted": 0, "rejected": 0, "pending": 0,
                "accuracy": 0.0, "by_step": {}}

    total = len(docs)
    accepted = sum(1 for d in docs if d.get("next_step_accepted") is True)
    rejected = sum(1 for d in docs if d.get("next_step_accepted") is False)
    pending = total - accepted - rejected

    accuracy = (accepted / (accepted + rejected)) if (accepted + rejected) > 0 else 0.0

    # Per-step breakdown
    by_step: dict[str, dict[str, int]] = {}
    for doc in docs:
        step = (doc.get("predicted_next_step") or {}).get("next_step", "unknown")
        if step not in by_step:
            by_step[step] = {"total": 0, "accepted": 0, "rejected": 0, "pending": 0}
        by_step[step]["total"] += 1
        if doc.get("next_step_accepted") is True:
            by_step[step]["accepted"] += 1
        elif doc.get("next_step_accepted") is False:
            by_step[step]["rejected"] += 1
        else:
            by_step[step]["pending"] += 1

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
        "accuracy": round(accuracy, 4),
        "by_step": by_step,
    }
