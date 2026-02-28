"""LLM-powered next-step prediction for Slack bot navigation.

Uses Gemini to analyse the user's current context (project config,
session state, PRD flow stage) and predict the most useful next action.

The prediction is:
* Posted as a Slack suggestion block with accept/dismiss buttons
* Logged in ``agentInteraction`` with the ``predicted_next_step`` field
* Updated with user feedback when the user accepts or dismisses

This module is the core of the proactive navigation system that helps
users move through the PRD flow without guessing what to do next.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Next-step system prompt
# ---------------------------------------------------------------------------

_NEXT_STEP_SYSTEM_PROMPT = """\
You are a navigation assistant for a Product Requirements Document (PRD) \
planning bot.  Given the user's current context, predict the SINGLE most \
useful next step the user should take.

=== Context variables you will receive ===
- trigger_action: what just happened (e.g. "project_selected", \
  "project_setup_complete", "session_started", "prd_completed", \
  "idea_approved", "requirements_approved", "publish_completed")
- project_config: the project's configuration (may include \
  confluence_space_key, jira_project_key, confluence_parent_id)
- session_active: whether the user has an active session
- has_confluence_key: whether Confluence space key is configured
- has_jira_key: whether Jira project key is configured
- has_confluence_parent: whether Confluence parent page ID is configured
- has_memory_entries: whether the project has memory configured
- pending_prds: count of PRDs not yet published
- recent_intents: recent user intents for pattern analysis

=== Next-step categories ===
Return ONE of these suggested next steps:

1. "configure_confluence" — Suggest configuring Confluence space key \
   (when missing and user may want to publish later)
2. "configure_jira" — Suggest configuring Jira project key \
   (when missing and user may want Jira tickets later)
3. "configure_memory" — Suggest setting up project memory / guardrails \
   (when project is new and no memory configured)
4. "create_prd" — Suggest creating a PRD / iterating an idea \
   (when project is ready and no recent PRD activity)
5. "publish" — Suggest publishing pending PRDs to Confluence / Jira \
   (when there are unpublished PRDs and keys are configured)
6. "configure_missing_keys" — Suggest setting up Confluence/Jira \
   before publishing (when PRDs exist but keys are missing)
7. "review_prd" — Suggest reviewing a completed PRD
8. "none" — No proactive suggestion needed (user seems to know \
   what they're doing)

=== Decision guidelines ===
- After project creation/selection with NO Confluence/Jira keys: \
  suggest "configure_confluence" or "configure_jira" (optional but \
  helpful for later publishing)
- After project setup where keys were skipped: suggest \
  "configure_memory" or "create_prd"
- After project setup where keys were provided: suggest \
  "configure_memory" if not set, otherwise "create_prd"
- After PRD completion: suggest "publish" if keys are configured, \
  or "configure_missing_keys" if not
- After publishing: suggest "create_prd" for more ideas
- If everything is configured and ready: suggest "create_prd"
- If the user has been very active recently: "none" \
  (don't over-suggest)

=== Output format ===
Return a JSON object with EXACTLY these keys:
  "next_step": one of the categories above
  "message": a SHORT (1-2 sentence) friendly suggestion text for the \
             user, written as if addressing them directly. Use Slack \
             markdown (*bold*, _italic_). Include a specific example \
             or hint when possible.
  "confidence": float 0.0 to 1.0 — how confident you are this is the \
                right next step
  "reason": a brief internal reason for the prediction (for logging)

Always return valid JSON — no markdown fences, no extra text.
"""

# ---------------------------------------------------------------------------
# Predefined next-step messages (fallback when LLM output is truncated)
# ---------------------------------------------------------------------------

_DEFAULT_MESSAGES: dict[str, str] = {
    "configure_confluence": (
        "You haven't configured a *Confluence space key* yet. "
        "Would you like to set one so PRDs can be published?"
    ),
    "configure_jira": (
        "You haven't configured a *Jira project key* yet. "
        "Would you like to set one so I can create Jira tickets?"
    ),
    "configure_memory": (
        "Your project memory isn't configured yet. "
        "Would you like to set up guardrails, knowledge, or tools?"
    ),
    "create_prd": (
        "Your project is ready! Would you like to *create a PRD* "
        "or *iterate on an idea*?"
    ),
    "publish": (
        "You have pending PRDs. Would you like to *publish* them "
        "to Confluence and create Jira tickets?"
    ),
    "configure_missing_keys": (
        "You have PRDs ready but Confluence/Jira keys aren't set. "
        "Would you like to configure them first?"
    ),
    "review_prd": "Would you like to *review* a completed PRD?",
}


def _salvage_truncated(
    text: str, finish_reason: str,
) -> dict[str, Any] | None:
    """Try to extract ``next_step`` from truncated JSON text.

    When the model hits ``MAX_TOKENS``, the JSON may be cut off
    mid-string, but the critical ``next_step`` value is usually
    present near the top.  We regex-extract it and fill in a
    default message.
    """
    import re

    m = re.search(r'"next_step"\s*:\s*"([^"]+)"', text)
    if not m:
        logger.warning(
            "Could not salvage truncated next-step prediction "
            "(finishReason=%s, len=%d): %s",
            finish_reason, len(text), text[:300],
        )
        return None

    next_step = m.group(1)
    # Try to extract confidence too
    c = re.search(r'"confidence"\s*:\s*([\d.]+)', text)
    confidence = float(c.group(1)) if c else 0.7

    message = _DEFAULT_MESSAGES.get(next_step, "Here's a suggested next step.")

    logger.info(
        "Salvaged truncated next-step prediction: step=%s (finishReason=%s)",
        next_step, finish_reason,
    )
    return {
        "next_step": next_step,
        "message": message,
        "confidence": confidence,
        "reason": f"salvaged from truncated response (finishReason={finish_reason})",
    }


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------


def _gather_context(
    *,
    user: str,
    project_id: str | None = None,
    trigger_action: str = "",
    project_config: dict | None = None,
) -> dict[str, Any]:
    """Build the context dict sent to the LLM for next-step prediction."""
    context: dict[str, Any] = {
        "trigger_action": trigger_action,
        "session_active": project_id is not None,
        "has_confluence_key": False,
        "has_jira_key": False,
        "has_confluence_parent": False,
        "has_memory_entries": False,
        "pending_prds": 0,
        "recent_intents": [],
    }

    # Project configuration
    if project_config:
        context["has_confluence_key"] = bool(project_config.get("confluence_space_key"))
        context["has_jira_key"] = bool(project_config.get("jira_project_key"))
        context["has_confluence_parent"] = bool(project_config.get("confluence_parent_id"))
    elif project_id:
        try:
            from crewai_productfeature_planner.mongodb.project_config import get_project
            proj = get_project(project_id)
            if proj:
                context["has_confluence_key"] = bool(proj.get("confluence_space_key"))
                context["has_jira_key"] = bool(proj.get("jira_project_key"))
                context["has_confluence_parent"] = bool(proj.get("confluence_parent_id"))
                project_config = proj
        except Exception:
            logger.debug("Failed to load project config for next-step", exc_info=True)

    # Project memory
    if project_id:
        try:
            from crewai_productfeature_planner.mongodb.project_memory import get_project_memory
            mem = get_project_memory(project_id)
            if mem:
                has_any = (
                    bool(mem.get("idea_iteration"))
                    or bool(mem.get("knowledge"))
                    or bool(mem.get("tools"))
                )
                context["has_memory_entries"] = has_any
        except Exception:
            logger.debug("Failed to load project memory for next-step", exc_info=True)

    # Pending PRDs
    try:
        from crewai_productfeature_planner.apis.publishing.service import list_pending_prds
        items = list_pending_prds()
        context["pending_prds"] = len(items) if items else 0
    except Exception:
        pass

    # Recent user intents (last 5)
    try:
        from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
            find_interactions,
        )
        recent = find_interactions(user_id=user, limit=5)
        context["recent_intents"] = [r.get("intent", "") for r in recent if r.get("intent")]
    except Exception:
        pass

    if project_config:
        # Include sanitised project config (name and key fields only)
        context["project_config"] = {
            "name": project_config.get("name", ""),
            "confluence_space_key": project_config.get("confluence_space_key", ""),
            "jira_project_key": project_config.get("jira_project_key", ""),
            "confluence_parent_id": project_config.get("confluence_parent_id", ""),
        }

    return context


# ---------------------------------------------------------------------------
# LLM prediction
# ---------------------------------------------------------------------------


def predict_next_step(
    *,
    user: str,
    project_id: str | None = None,
    trigger_action: str = "",
    project_config: dict | None = None,
) -> dict[str, Any] | None:
    """Call the LLM to predict the next step for the user.

    Returns a dict with ``next_step``, ``message``, ``confidence``,
    ``reason`` — or ``None`` if prediction fails or is not applicable.
    """
    from crewai_productfeature_planner.agents.gemini_utils import (
        DEFAULT_GEMINI_MODEL,
        ensure_gemini_env,
    )

    ensure_gemini_env()
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.debug("GOOGLE_API_KEY not set — skipping next-step prediction")
        return None

    context = _gather_context(
        user=user,
        project_id=project_id,
        trigger_action=trigger_action,
        project_config=project_config,
    )

    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )

    request_body = {
        "systemInstruction": {
            "parts": [{"text": _NEXT_STEP_SYSTEM_PROMPT}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(context, default=str)}],
            },
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }

    try:
        data = json.dumps(request_body).encode("utf-8")
        # Use certifi for SSL (consistent with gemini_chat.py)
        ssl_ctx: ssl.SSLContext | None = None
        try:
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_ctx = ssl.create_default_context()
        if os.environ.get("GEMINI_ALLOW_SELF_SIGNED"):
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # Retry once on transient failures
        resp_data = None
        for _attempt in range(1, 3):
            try:
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
                    raw = resp.read()
                    resp_data = json.loads(raw.decode("utf-8", errors="replace"))
                break
            except (urllib.error.URLError, OSError) as net_exc:
                logger.warning(
                    "Gemini next-step request failed (attempt %d/2): %s",
                    _attempt, net_exc,
                )
                if _attempt == 2:
                    return None

        if resp_data is None:
            return None

        # Extract the text from the Gemini response
        candidates = resp_data.get("candidates", [])
        if not candidates:
            logger.warning("Gemini next-step prediction returned no candidates")
            return None

        candidate = candidates[0]

        # Check finishReason — truncated responses won't have valid JSON
        finish_reason = candidate.get("finishReason", "")
        if finish_reason not in ("STOP", ""):
            logger.warning(
                "Gemini next-step prediction stopped early: finishReason=%s",
                finish_reason,
            )

        # Concatenate ALL parts (Gemini may split output across parts)
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            return None

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown fences or surrounding text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    result = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    result = _salvage_truncated(text, finish_reason)
                    if result is None:
                        return None
            else:
                # No closing brace — try salvaging truncated JSON
                result = _salvage_truncated(text, finish_reason)
                if result is None:
                    return None

        # Validate required fields
        if not isinstance(result, dict) or "next_step" not in result:
            logger.warning("Gemini next-step prediction missing required fields")
            return None

        # Skip if prediction is "none" or low confidence
        if result.get("next_step") == "none":
            logger.debug("Next-step prediction is 'none' — skipping")
            return None

        confidence = result.get("confidence", 0.5)
        if confidence < 0.3:
            logger.debug(
                "Next-step prediction confidence too low (%.2f) — skipping",
                confidence,
            )
            return None

        logger.info(
            "Next-step prediction: step=%s confidence=%.2f reason=%s",
            result.get("next_step"),
            confidence,
            result.get("reason", ""),
        )
        return result

    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Gemini next-step prediction failed: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected error in next-step prediction: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Post prediction to Slack
# ---------------------------------------------------------------------------


def predict_and_post_next_step(
    *,
    channel: str,
    thread_ts: str,
    user: str,
    project_id: str | None = None,
    trigger_action: str = "",
    project_config: dict | None = None,
    interaction_id: str | None = None,
) -> dict[str, Any] | None:
    """Predict the next step and post it as a suggestion block in Slack.

    If *interaction_id* is provided, the prediction is also stored on
    the ``agentInteraction`` document for tracking.

    Returns the prediction dict, or ``None`` if no suggestion was made.
    """
    prediction = predict_next_step(
        user=user,
        project_id=project_id,
        trigger_action=trigger_action,
        project_config=project_config,
    )

    if not prediction:
        return None

    # ------------------------------------------------------------------
    # Resolve interaction_id BEFORE building blocks so the accept/dismiss
    # buttons always carry a valid ID for the feedback loop.
    # ------------------------------------------------------------------
    effective_interaction_id = interaction_id
    try:
        from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
            log_interaction,
            update_next_step_prediction,
        )

        if interaction_id:
            update_next_step_prediction(
                interaction_id=interaction_id,
                predicted_next_step=prediction,
            )
        else:
            # Log as a new interaction and capture the returned id
            effective_interaction_id = log_interaction(
                source="slack",
                user_message=f"[system] {trigger_action}",
                intent="next_step_prediction",
                agent_response=prediction.get("message", ""),
                project_id=project_id,
                channel=channel,
                thread_ts=thread_ts,
                user_id=user,
                metadata={
                    "trigger_action": trigger_action,
                    "predicted_next_step": prediction,
                },
                predicted_next_step=prediction,
            )
    except Exception:
        logger.debug("Failed to log next-step prediction", exc_info=True)

    # Post Slack blocks with the suggestion
    from crewai_productfeature_planner.apis.slack.blocks import next_step_suggestion_blocks
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return prediction

    blocks = next_step_suggestion_blocks(
        next_step=prediction["next_step"],
        message=prediction.get("message", ""),
        user_id=user,
        interaction_id=effective_interaction_id,
    )

    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=blocks,
            text=f"Suggestion: {prediction.get('message', '')}",
        )
    except Exception as exc:
        logger.error("Failed to post next-step suggestion: %s", exc)

    return prediction
