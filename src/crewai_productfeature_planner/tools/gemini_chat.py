"""Lightweight Gemini chat helper for interpreting Slack messages.

Uses Google Gemini (``gemini-3-flash-preview`` by default) to classify
user intent and extract structured parameters from natural language
messages about product feature planning.

Replaces the previous OpenAI-based interpreter with the same
contract — callers receive a dict with:

    intent   – "create_prd" | "help" | "greeting" | "unknown"
    idea     – extracted product/feature idea or null
    reply    – friendly reply text

Environment variables:

* ``GOOGLE_API_KEY`` — required for Google AI Studio authentication.
* ``GOOGLE_CLOUD_PROJECT`` + ``GOOGLE_CLOUD_LOCATION`` — alternative
  Vertex AI authentication (see ``gemini_utils.ensure_gemini_env``).
* ``GEMINI_MODEL`` — override the model name (default:
  ``gemini-3-flash-preview``).
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request

from crewai_productfeature_planner.agents.gemini_utils import (
    DEFAULT_GEMINI_MODEL,
    ensure_gemini_env,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (identical semantics to the old OpenAI version)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an intent-classification and entity-extraction assistant for a \
product feature planning bot. Given a user message (which may be part of \
an ongoing thread conversation), return a JSON object with EXACTLY these keys:

  "intent"  – one of: "create_prd", "publish", "check_publish", "help", "greeting", "unknown"
  "idea"    – the product or feature idea extracted from the message, or null
  "reply"   – a SHORT friendly reply (1-2 sentences) appropriate to the intent:
       • "create_prd" with idea → confirm you will start planning
       • "create_prd" without idea → ask the user for the idea
       • "publish" → confirm you will publish pending PRDs to Confluence and create Jira tickets
       • "check_publish" → confirm you will check the publishing status of pending PRDs
       • "help" → briefly list what you can do
       • "greeting" → respond conversationally and offer help
       • "unknown" → say you didn't understand and show a quick example

Rules:
- Intent "create_prd" means the user wants to create a PRD, plan a product \
  feature, build a requirements document, or discuss a product idea. Be \
  generous: if the message contains something that looks like a product \
  or feature description, assume "create_prd".
- If the user provides ONLY a product idea (no command word), still classify \
  as "create_prd".
- Intent "publish" means the user wants to publish PRDs to Confluence, \
  create Jira tickets, or trigger the delivery pipeline. Keywords: \
  "publish", "deploy", "push to confluence", "create tickets", "deliver", \
  "push all", "publish all".
- Intent "check_publish" means the user wants to see the publishing status, \
  check which PRDs are pending, or view delivery progress. Keywords: \
  "check publish", "publishing status", "what's pending", "delivery status", \
  "unpublished", "check status", "list pending".
- If the user asks "what can you do", "how do I use this", etc. → "help".
- If the user says "hi", "hey", "hello", etc. with no idea → "greeting".
- Always return valid JSON — no markdown fences, no extra text.

Conversation context (if any) is provided as previous assistant/user turns.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def interpret_message(
    user_message: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Send *user_message* to Gemini and return the structured interpretation.

    Uses the Gemini ``generateContent`` REST endpoint with JSON-mode
    (``responseMimeType: application/json``).  Falls back to the
    ``_fallback()`` sentinel when credentials are missing or the API
    call fails.
    """
    ensure_gemini_env()

    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set – falling back to unknown intent")
        return _fallback()

    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()

    # ── Build contents array (Gemini chat format) ──────────────
    contents: list[dict] = []

    if conversation_history:
        for turn in conversation_history:
            role = turn.get("role", "user")
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": turn.get("content", "")}],
            })

    contents.append({
        "role": "user",
        "parts": [{"text": user_message}],
    })

    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": _SYSTEM_PROMPT}],
        },
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    ssl_context: ssl.SSLContext | None = None
    try:
        import certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as resp:
            resp_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        logger.error("Gemini API HTTP error %s: %s", exc.code, body)
        return _fallback()
    except urllib.error.URLError as exc:
        logger.error("Gemini API connection error: %s", exc.reason)
        return _fallback()
    except Exception as exc:
        logger.error("Gemini API unexpected error: %s", exc)
        return _fallback()

    # ── Parse Gemini response ──────────────────────────────────
    try:
        content = (
            resp_payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
    except (IndexError, KeyError, TypeError):
        logger.warning("Gemini returned unexpected response structure")
        return _fallback()

    if not content:
        logger.warning("Gemini returned empty content")
        return _fallback()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown fences or surrounding text.
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Could not parse Gemini response as JSON")
                return _fallback()
        else:
            logger.warning("Could not parse Gemini response as JSON")
            return _fallback()

    return {
        "intent": result.get("intent", "unknown"),
        "idea": result.get("idea") or None,
        "reply": result.get("reply", ""),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fallback() -> dict:
    return {
        "intent": "unknown",
        "idea": None,
        "reply": (
            "I'm having trouble understanding right now. "
            "Try: `@crewai-prd-bot create a PRD for a mobile fitness app`"
        ),
    }
