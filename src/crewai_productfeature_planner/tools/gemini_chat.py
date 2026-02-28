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

  "intent"  – one of: "create_project", "list_projects", "switch_project", \
              "current_project", "end_session", "configure_memory", \
              "create_prd", "publish", "check_publish", "help", \
              "greeting", "unknown"
  "idea"    – the product or feature idea extracted from the message, or null
  "reply"   – a SHORT friendly reply (1-2 sentences) appropriate to the intent:
       • "create_project" → confirm you will create a new project and ask for the project name
       • "list_projects" → confirm you will show the available projects
       • "switch_project" → confirm you will show the project picker to switch
       • "current_project" → confirm you will show which project is active
       • "end_session" → confirm you will end the current session
       • "configure_memory" → confirm you will open memory configuration
       • "create_prd" with idea → confirm you will start planning
       • "create_prd" without idea → ask the user for the idea
       • "publish" → confirm you will publish pending PRDs to Confluence and create Jira tickets
       • "check_publish" → confirm you will check the publishing status of pending PRDs
       • "help" → briefly list what you can do
       • "greeting" → respond conversationally and offer help
       • "unknown" → say you didn't understand and show a quick example

=== CRITICAL RULE — "project" vs "PRD" / "idea" ===
The word "project" and the word "PRD" / "idea" mean DIFFERENT things:
• "project" = a workspace/container/channel grouping.  **create_project** \
  is ONLY for creating a new workspace container.
• "PRD" / "idea" / "feature" / "product idea" = a product concept the \
  user wants to plan or iterate on.  This is ALWAYS **create_prd**.

ONLY use create_project when the message EXPLICITLY asks to create, set up, \
or start a NEW PROJECT / WORKSPACE / CHANNEL GROUPING.  If the user talks \
about an "idea", "feature", "PRD", "iterate", "brainstorm", "plan", or \
describes any product concept, the intent is ALWAYS **create_prd** — even if \
the word "project" does not appear.

=== Intent examples ===
  "create a new project for this channel" → create_project
  "create new project"                    → create_project
  "new project"                           → create_project
  "set up a project"                      → create_project
  "start a project for us"                → create_project
  "I need a project"                      → create_project
  "show me available projects"             → list_projects
  "list projects"                         → list_projects
  "what projects are there"               → list_projects
  "show projects"                         → list_projects
  "available projects"                    → list_projects
  "which projects exist"                  → list_projects
  "switch project"                        → switch_project
  "change project"                        → switch_project
  "use a different project"               → switch_project
  "I want to switch to another project"   → switch_project
  "change to another project"             → switch_project
  "what's my current project"             → current_project
  "which project am I on"                 → current_project
  "what project is active"                → current_project
  "current project"                       → current_project
  "end session"                           → end_session
  "stop session"                          → end_session
  "close session"                         → end_session
  "I'm done"                              → end_session
  "configure memory"                      → configure_memory
  "project memory"                        → configure_memory
  "setup memory"                          → configure_memory
  "edit memory"                           → configure_memory
  "show memory"                           → configure_memory
  "create a PRD for a fitness app"        → create_prd
  "plan a feature for user auth"          → create_prd
  "I have an idea for an AI chatbot"      → create_prd
  "build a requirements doc"              → create_prd
  "iterate an idea"                       → create_prd  (idea iteration)
  "iterate a new idea"                    → create_prd
  "brainstorm an idea"                    → create_prd
  "let's work on a new idea"              → create_prd
  "I want to plan something"              → create_prd
  "help me iterate"                       → create_prd
  "start an idea"                         → create_prd
  "new idea"                              → create_prd
  "refine my idea"                        → create_prd

=== Other rules ===
- Intent "list_projects" means the user wants to SEE, LIST, BROWSE, or \
  SHOW existing projects.  Keywords: "list projects", "show projects", \
  "available projects", "what projects", "which projects".
- Intent "switch_project" means the user wants to CHANGE to a different \
  project.  Keywords: "switch project", "change project", "different \
  project", "another project".
- Intent "current_project" means the user wants to KNOW which project \
  is currently active.  Keywords: "current project", "my project", \
  "which project am I", "what project".
- Intent "end_session" means the user wants to STOP or END their active \
  session.  Keywords: "end session", "stop session", "close session", \
  "I'm done", "goodbye", "quit".
- Intent "configure_memory" means the user wants to VIEW or EDIT the \
  project's memory configuration (guardrails, knowledge, tools).  \
  Keywords: "memory", "configure memory", "setup memory", "edit memory", \
  "view memory", "show memory", "project memory".
- Intent "create_prd" means the user wants to create a PRD, plan a product \
  feature, build a requirements document, iterate on an idea, brainstorm, \
  or discuss a product concept. Be generous: if the message contains \
  something that looks like a product or feature description, OR the words \
  "idea", "iterate", "brainstorm", "refine", "plan", assume "create_prd".
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
