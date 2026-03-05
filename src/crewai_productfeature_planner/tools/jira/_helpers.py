"""Text conversion and field-resolution helpers for Jira payloads."""

from __future__ import annotations

import json
import re

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.jira import _http as _http_mod

logger = get_logger(__name__)


# ── Text helpers ─────────────────────────────────────────────────────


def _strip_emails(text: str) -> str:
    """Remove email addresses from text to prevent credential leakage.

    The LLM agent may inadvertently include the ``ATLASSIAN_USERNAME``
    (which is an email) in issue summaries or descriptions.  This
    helper replaces any ``user@domain`` patterns with ``[redacted]``.
    """
    return re.sub(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "[redacted]",
        text,
    )


def _markdown_to_wiki(text: str) -> str:
    """Convert common Markdown formatting to Jira wiki markup.

    Jira REST API v2 interprets the ``description`` field as wiki
    markup, not Markdown.  This function performs best-effort
    conversion of the most common Markdown constructs so that
    agent-generated descriptions render correctly in Jira.

    Converted patterns:
    - ``### Heading`` → ``h3. Heading``
    - ``## Heading``  → ``h2. Heading``
    - ``# Heading``   → ``h1. Heading``
    - ``**bold**``    → ``*bold*``
    - `` `code` ``      → ``{{code}}``
    - ``````` code blocks → ``{code}…{code}``
    - ``- item``      → ``* item``
    - ``[text](url)`` → ``[text|url]``
    """
    # Fenced code blocks: ```lang\n...\n``` → {code:lang}...{code}
    def _replace_code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = m.group(2)
        if lang:
            return f"{{code:{lang}}}\n{code}\n{{code}}"
        return f"{{code}}\n{code}\n{{code}}"

    text = re.sub(
        r"```(\w*)\n(.*?)```",
        _replace_code_block,
        text,
        flags=re.DOTALL,
    )

    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        # Headings: ### → h3. , ## → h2. , # → h1.
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            line = f"h{level}. {heading_match.group(2)}"
        else:
            # Unordered list items: - item → * item
            list_match = re.match(r"^(\s*)- (.*)", line)
            if list_match:
                indent = list_match.group(1)
                # Nested indentation: each 2 spaces = another *
                depth = len(indent) // 2 + 1
                line = f"{'*' * depth} {list_match.group(2)}"

        # Bold: **text** → *text*  (only outside code blocks)
        line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)

        # Inline code: `code` → {{code}}
        line = re.sub(r"`([^`]+)`", r"{{\1}}", line)

        # Links: [text](url) → [text|url]
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\1|\2]", line)

        result.append(line)

    return "\n".join(result)


# ── Field retry helpers ──────────────────────────────────────────────

# Fields that may be safely stripped on a 400 retry.  If Jira reports
# an error for one of these, we remove it and retry once rather than
# failing the whole request.
_RETRYABLE_FIELDS = frozenset({"priority", "components", "labels"})


def _drop_rejected_fields(fields: dict, error_message: str) -> list[str]:
    """Parse a Jira 400 error and remove rejected fields from *fields*.

    The Jira REST API returns errors like::

        {"errorMessages":[], "errors":{"priority":"Specify the …"}}

    For each reported field that is in the *_RETRYABLE_FIELDS* allow-list
    we remove it from *fields* (in-place) so a subsequent request can
    succeed with the project's defaults.

    Returns:
        A list of field names that were removed.
    """
    idx = error_message.find("{")
    if idx == -1:
        return []

    try:
        body = json.loads(error_message[idx:])
    except (json.JSONDecodeError, ValueError):
        return []

    errors = body.get("errors", {})
    dropped: list[str] = []
    for field_name in errors:
        if field_name in _RETRYABLE_FIELDS and field_name in fields:
            dropped.append(field_name)
            del fields[field_name]

    return dropped


# ── Priority helpers ─────────────────────────────────────────────────

# Canonical Jira Cloud priority names (case-insensitive lookup).
_JIRA_PRIORITIES = {"highest", "high", "medium", "low", "lowest"}

# Cached map of canonical priority name → Jira priority id.
# Populated lazily by ``_fetch_priority_scheme()``.
_priority_id_cache: dict[str, str] | None = None


def _fetch_priority_scheme(auth_header: str, base_url: str) -> dict[str, str]:
    """Fetch available priorities from Jira and build a name→id map.

    Calls ``GET /rest/api/3/priority`` once and caches the result for
    the lifetime of the process.  The returned dict maps **lower-cased**
    priority names to their string IDs.

    If the request fails the returned dict is empty so callers can
    fall back to omitting the priority field entirely.
    """
    global _priority_id_cache  # noqa: PLW0603
    if _priority_id_cache is not None:
        return _priority_id_cache

    url = f"{base_url}/rest/api/3/priority"
    try:
        result = _http_mod._jira_request("GET", url, auth_header=auth_header)
        _priority_id_cache = {
            p["name"].lower(): str(p["id"])
            for p in result
            if "name" in p and "id" in p
        }
        logger.info(
            "[Jira] Fetched priority scheme — %d priorities: %s",
            len(_priority_id_cache),
            ", ".join(
                f"{n}(id={i})" for n, i in _priority_id_cache.items()
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[Jira] Failed to fetch priority scheme: %s — "
            "priority field will be omitted on 400", exc,
        )
        _priority_id_cache = {}

    return _priority_id_cache


def _normalize_priority(raw: object) -> str:
    """Coerce an LLM-provided priority value into a valid Jira name.

    The LLM may return the priority as:
    * a plain string — ``"High"``
    * a dict — ``{"name": "High"}``
    * a numeric/id string — ``"3"``
    * a completely unknown string — ``"P1"``

    Returns the canonical name (title-cased) when recognised, or
    ``"Medium"`` as a safe fallback.
    """
    # Unwrap dict (e.g. {"name": "High"}) — LLM may pass structured value
    if isinstance(raw, dict):
        raw = raw.get("name", "") or raw.get("id", "")

    text = str(raw).strip().strip("\"'")
    if not text:
        return "Medium"

    # Direct match (case-insensitive)
    if text.lower() in _JIRA_PRIORITIES:
        return text.capitalize()

    # Common aliases / abbreviations
    aliases = {
        "critical": "Highest",
        "urgent": "Highest",
        "p1": "Highest",
        "p2": "High",
        "p3": "Medium",
        "p4": "Low",
        "p5": "Lowest",
        "normal": "Medium",
        "minor": "Low",
        "trivial": "Lowest",
        "blocker": "Highest",
        "major": "High",
    }
    mapped = aliases.get(text.lower())
    if mapped:
        return mapped

    logger.warning(
        "[Jira] Unrecognised priority '%s' — defaulting to 'Medium'", text,
    )
    return "Medium"


def _resolve_priority_field(
    canonical_name: str,
    auth_header: str,
    base_url: str,
) -> dict[str, str] | None:
    """Return the ``priority`` sub-dict for a Jira payload, or *None*.

    Attempts to resolve *canonical_name* (e.g. ``"High"``) to a concrete
    priority **id** using the project's priority scheme.  Falls back to
    ``{"name": canonical_name}`` when the scheme has not been fetched
    yet.  Returns *None* when the canonical name is not found in the
    fetched scheme (avoids a guaranteed 400).
    """
    scheme = _fetch_priority_scheme(auth_header, base_url)
    if not scheme:
        # Scheme unavailable — send name; retry-on-400 will strip if needed.
        return {"name": canonical_name}

    pid = scheme.get(canonical_name.lower())
    if pid:
        return {"id": pid}

    # Name not in project scheme — don't send a value Jira will reject.
    logger.info(
        "[Jira] Priority '%s' not in project scheme — omitting",
        canonical_name,
    )
    return None


# ── Label helpers ────────────────────────────────────────────────────


def _run_id_label(run_id: str) -> str:
    """Build a Jira-safe label that encodes *run_id* for search.

    Jira labels cannot contain spaces.  The returned label has the form
    ``prd-run-<run_id>`` which can be located via JQL
    ``labels = "prd-run-<run_id>"``.
    """
    # Replace whitespace / special chars to keep the label Jira-safe.
    safe = run_id.strip().replace(" ", "-")
    return f"prd-run-{safe}"
