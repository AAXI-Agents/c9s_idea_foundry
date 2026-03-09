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
import time
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

  "intent"  – one of: "create_project", "list_projects", "list_products_intent", \
              "switch_project", \
              "current_project", "end_session", "configure_memory", \
              "update_config", "create_prd", "resume_prd", "publish", \
              "create_jira", "check_publish", "general_question", \
              "help", "greeting", "unknown"
  "idea"    – the product or feature idea extracted from the message, or null
  "confluence_space_key" – extracted Confluence space key, or null
  "jira_project_key"     – extracted Jira project key, or null
  "reply"   – a SHORT friendly reply (1-2 sentences) appropriate to the intent:
       • "create_project" → confirm you will create a new project and ask for the project name
       • "list_projects" → confirm you will show the available projects
       • "list_products_intent" → confirm you will show the completed products ready for delivery
       • "switch_project" → confirm you will show the project picker to switch
       • "current_project" → confirm you will show which project is active
       • "end_session" → confirm you will end the current session
       • "configure_memory" → confirm you will open memory configuration
       • "update_config" → confirm you will update the project configuration with the provided keys
       • "create_prd" with idea → confirm you will start planning
       • "create_prd" without idea → ask the user for the idea
       • "resume_prd" → confirm you will resume the paused/unfinished PRD flow
       • "publish" → confirm you will publish pending PRDs to Confluence
       • "create_jira" → confirm you will create Jira tickets for the completed PRD
       • "check_publish" → confirm you will check the publishing status of pending PRDs
       • "general_question" → answer the question conversationally; if it \
         relates to PRDs or product planning, explain that this bot generates \
         comprehensive Product Requirements Documents by iterating on the \
         user's idea through multiple refinement rounds
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
  "list products"                          → list_products_intent
  "show products"                          → list_products_intent
  "completed ideas"                        → list_products_intent
  "show completed"                         → list_products_intent
  "delivery status"                        → list_products_intent
  "ready for delivery"                     → list_products_intent
  "my products"                            → list_products_intent
  "what products"                          → list_products_intent
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
  "configure more memory"                 → configure_memory
  "add more memory"                       → configure_memory
  "project memory"                        → configure_memory
  "setup memory"                          → configure_memory
  "edit memory"                           → configure_memory
  "manage memory"                         → configure_memory
  "show memory"                           → configure_memory
  "update knowledge"                      → configure_memory
  "configure knowledge"                   → configure_memory
  "project knowledge"                     → configure_memory
  "add knowledge"                         → configure_memory
  "add more knowledge"                    → configure_memory
  "edit knowledge"                        → configure_memory
  "manage knowledge"                      → configure_memory
  "show knowledge"                        → configure_memory
  "view knowledge"                        → configure_memory
  "add confluence key ABC"                 → update_config  (confluence_space_key="ABC")
  "set jira project key PROJ"             → update_config  (jira_project_key="PROJ")
  "confluence space key is XYZ"           → update_config  (confluence_space_key="XYZ")
  "add confluence project space key CrewAITS and jira project key CJT" → update_config  (confluence_space_key="CrewAITS", jira_project_key="CJT")
  "set confluence key ABC and jira key DEF" → update_config  (confluence_space_key="ABC", jira_project_key="DEF")
  "jira key is MYPROJ"                    → update_config  (jira_project_key="MYPROJ")
  "update project config confluence XYZ jira ABC" → update_config
  "configure confluence key"              → update_config  (ask for value if missing)
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
  "resume prd flow"                       → resume_prd
  "resume prd"                            → resume_prd
  "continue prd flow"                     → resume_prd
  "continue the prd"                      → resume_prd
  "resume the flow"                       → resume_prd
  "pick up where you left off"            → resume_prd
  "unpause prd"                           → resume_prd
  "resume run"                            → resume_prd
  "restart prd flow"                      → resume_prd
  "continue flow"                         → resume_prd

=== CRITICAL RULE — "resume" vs "create" PRD ===
When the user says "resume", "continue", "unpause", "restart", or \
"pick up where" in relation to a PRD or flow, that is ALWAYS **resume_prd** — \
not create_prd.  "resume_prd" means the user wants to continue a previously \
paused or unfinished PRD generation run.

=== Other rules ===
- Intent "list_projects" means the user wants to SEE, LIST, BROWSE, or \
  SHOW existing projects.  Keywords: "list projects", "show projects", \
  "available projects", "what projects", "which projects".
- Intent "list_products_intent" means the user wants to see COMPLETED \
  ideas that are ready for delivery (Confluence publish, Jira ticketing).  \
  Keywords: "list products", "show products", "completed ideas", \
  "show completed", "delivery status", "ready for delivery", \
  "my products", "what products".  Do NOT confuse with "list_projects" \
  (which shows projects) or "create_prd" (which starts a new idea).
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
  Keywords: "memory", "knowledge", "configure memory", "setup memory", \
  "edit memory", "view memory", "show memory", "project memory", \
  "update knowledge", "configure knowledge", "project knowledge", \
  "add knowledge", "edit knowledge", "manage knowledge", \
  "show knowledge".  "knowledge" and "memory" are synonyms here.
- Intent "update_config" means the user wants to SET, ADD, or UPDATE \
  specific project configuration keys — Confluence space key or Jira \
  project key.  The user may provide one \
  or more key values inline.  Extract the values into \
  "confluence_space_key" and/or "jira_project_key" \
  fields.  Keywords: "confluence key", "confluence space key", "jira key", \
  "jira project key", "set confluence", "add jira", "project key", \
  "space key", "update config", "set config", \
  "configure confluence", "configure jira".  \
  IMPORTANT: Do NOT confuse "update_config" with "configure_memory". \
  "update_config" is specifically about Confluence/Jira key values, \
  while "configure_memory" is about broader project memory settings.
- Intent "create_prd" means the user wants to create a PRD, plan a product \
  feature, build a requirements document, iterate on an idea, brainstorm, \
  or discuss a product concept. Be generous: if the message contains \
  something that looks like a product or feature description, OR the words \
  "idea", "iterate", "brainstorm", "refine", "plan", assume "create_prd".
- If the user provides ONLY a product idea (no command word), still classify \
  as "create_prd".
- Intent "resume_prd" means the user wants to RESUME, CONTINUE, UNPAUSE, \
  or RESTART a previously paused or unfinished PRD flow.  Keywords: \
  "resume prd", "resume flow", "continue prd", "continue flow", \
  "unpause", "restart prd", "pick up where", "resume run".  \
  Do NOT confuse with "create_prd" — resume is about continuing an \
  existing run, not starting a new one.
- Intent "publish" means the user wants to publish PRDs to Confluence \
  or trigger the Confluence delivery pipeline.  This is ONLY about \
  Confluence publishing — NOT about Jira ticket creation.  Keywords: \
  "publish", "deploy", "push to confluence", "deliver", \
  "push all", "publish all".
- Intent "create_jira" means the user wants to create Jira tickets, \
  generate a Jira skeleton, or start the Jira ticketing process for a \
  completed PRD.  Keywords: "create jira", "jira tickets", "make jira", \
  "generate jira", "jira skeleton", "set up jira".  \
  Do NOT confuse with "publish" (which is Confluence only) or \
  "update_config" (which sets Jira key values).
- Intent "check_publish" means the user wants to see the publishing status, \
  check which PRDs are pending, or view delivery progress. Keywords: \
  "check publish", "publishing status", "what's pending", "delivery status", \
  "unpublished", "check status", "list pending".
- Intent "general_question" is for informational or conceptual questions \
  about terminology, concepts, or how things work — for example, \
  "what is a PRD?", "what does PRD stand for?", "what is a product \
  requirements document?", "explain PRD", "tell me about PRDs".  \
  These are NOT "help" — the user is asking a knowledge question, not \
  asking what the bot can do.  Answer the question and mention that \
  this bot generates PRDs through iterative idea refinement.
- If the user asks "what can you do", "how do I use this", \
  "help", "help me" → "help" (the user wants to know the bot's features).
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

    # Retry on transient errors (429, 500, 502, 503, 504) with backoff
    resp_payload = None
    _MAX_RETRIES = 3
    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    for _attempt in range(1, _MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as resp:
                resp_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            break  # success
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            logger.error("OpenAI API HTTP error %s (attempt %d/%d): %s", exc.code, _attempt, _MAX_RETRIES, body)
            if exc.code not in _RETRYABLE_STATUS_CODES or _attempt == _MAX_RETRIES:
                return _fallback()
            time.sleep(2 ** (_attempt - 1))
        except urllib.error.URLError as exc:
            logger.error("OpenAI API connection error (attempt %d/%d): %s", _attempt, _MAX_RETRIES, exc.reason)
            if _attempt == _MAX_RETRIES:
                return _fallback()
            time.sleep(2 ** (_attempt - 1))
        except Exception as exc:
            logger.error("OpenAI API unexpected error (attempt %d/%d): %s", _attempt, _MAX_RETRIES, exc)
            if _attempt == _MAX_RETRIES:
                return _fallback()
            time.sleep(2 ** (_attempt - 1))

    if resp_payload is None:
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

    # Guard: LLM sometimes returns a JSON array instead of an object
    if isinstance(result, list):
        result = result[0] if result else {}
    if not isinstance(result, dict):
        logger.warning("OpenAI returned non-dict JSON: %s", type(result).__name__)
        return _fallback()

    return {
        "intent": result.get("intent", "unknown"),
        "idea": result.get("idea") or None,
        "reply": result.get("reply", ""),
        "confluence_space_key": result.get("confluence_space_key") or None,
        "jira_project_key": result.get("jira_project_key") or None,
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
