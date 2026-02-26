"""Lightweight OpenAI chat helper for interpreting Slack messages.

Uses the OpenAI Chat Completions API with JSON-mode to classify user
intent and extract structured parameters from natural language messages
about product feature planning.

Returns a dict with:
    intent   – "create_prd" | "help" | "greeting" | "unknown"
    idea     – extracted product/feature idea or null
    reply    – friendly reply text
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an intent-classification and entity-extraction assistant for a \
product feature planning bot. Given a user message (which may be part of \
an ongoing thread conversation), return a JSON object with EXACTLY these keys:

  "intent"  – one of: "create_prd", "help", "greeting", "unknown"
  "idea"    – the product or feature idea extracted from the message, or null
  "reply"   – a SHORT friendly reply (1-2 sentences) appropriate to the intent:
       • "create_prd" with idea → confirm you will start planning
       • "create_prd" without idea → ask the user for the idea
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
    """Send *user_message* to OpenAI and return the structured interpretation."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENAI_API_KEY not set – falling back to unknown intent")
        return _fallback()

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
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
        logger.error("OpenAI API HTTP error %s", exc.code)
        return _fallback()
    except urllib.error.URLError as exc:
        logger.error("OpenAI API connection error: %s", exc.reason)
        return _fallback()
    except Exception as exc:
        logger.error("OpenAI API unexpected error: %s", exc)
        return _fallback()

    content = (
        resp_payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not content:
        logger.warning("OpenAI returned empty content")
        return _fallback()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Could not parse OpenAI response as JSON")
                return _fallback()
        else:
            logger.warning("Could not parse OpenAI response as JSON")
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
