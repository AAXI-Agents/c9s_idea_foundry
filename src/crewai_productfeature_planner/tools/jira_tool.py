"""Atlassian Jira ticket creation tool.

Creates issues (Stories, Tasks, Epics, Bugs) in a Jira project via the
Jira REST API v2.

Key resolution order (highest priority first):

1. Explicit ``project_key`` parameter on :func:`create_jira_issue` /
   :func:`search_jira_issues`
2. ``_project_key_ctx`` context variable (set by orchestrator stages
   with project-level configuration)
3. ``JIRA_PROJECT_KEY`` environment variable (integration / testing
   fallback)

Environment variables:

* ``ATLASSIAN_BASE_URL``  — e.g. ``https://yourcompany.atlassian.net``
* ``ATLASSIAN_USERNAME``  — Atlassian account email
* ``ATLASSIAN_API_TOKEN`` — API token (https://id.atlassian.com/manage-profile/security/api-tokens)
* ``JIRA_PROJECT_KEY``    — fallback project key for testing / integration
"""

from __future__ import annotations

import contextvars
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import base64
from contextlib import contextmanager
from typing import Generator, Type

import certifi
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ── Context-variable overrides (set by orchestrator with project config) ──

_project_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "jira_project_key_override", default="",
)


def set_jira_project_key(key: str) -> contextvars.Token[str]:
    """Set the Jira project key for the current context.

    Returns a reset token for use with :meth:`contextvars.ContextVar.reset`.
    """
    return _project_key_ctx.set(key)


@contextmanager
def jira_project_context(
    *,
    project_key: str = "",
) -> Generator[None, None, None]:
    """Context manager that sets a project-level Jira project key override.

    Usage::

        with jira_project_context(project_key="MYPROJ"):
            create_jira_issue(summary="...", run_id=rid)
    """
    token: contextvars.Token | None = None
    if project_key:
        token = _project_key_ctx.set(project_key)
    try:
        yield
    finally:
        if token is not None:
            _project_key_ctx.reset(token)


def _get_jira_env(*, project_key: str | None = None) -> dict[str, str]:
    """Read Jira config from environment with optional overrides.

    Resolution order for ``project_key``:

    1. Explicit *project_key* parameter
    2. ``_project_key_ctx`` context variable
    3. ``JIRA_PROJECT_KEY`` environment variable

    Returns:
        Dict with keys ``base_url``, ``project_key``, ``username``,
        ``api_token``.

    Raises:
        EnvironmentError: If required vars are missing.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "").rstrip("/")
    resolved_project_key = (
        project_key
        or _project_key_ctx.get()
        or os.environ.get("JIRA_PROJECT_KEY", "")
    )
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    missing: list[str] = []
    if not base_url:
        missing.append("ATLASSIAN_BASE_URL")
    if not resolved_project_key:
        missing.append("JIRA_PROJECT_KEY")
    if not username:
        missing.append("ATLASSIAN_USERNAME")
    if not api_token:
        missing.append("ATLASSIAN_API_TOKEN")

    if missing:
        raise EnvironmentError(
            f"Jira tool requires: {', '.join(missing)}"
        )

    return {
        "base_url": base_url,
        "project_key": resolved_project_key,
        "username": username,
        "api_token": api_token,
    }


def _has_jira_credentials() -> bool:
    """Return ``True`` when all required Jira env vars are set."""
    try:
        _get_jira_env()
        return True
    except EnvironmentError:
        return False


def _build_auth_header(username: str, api_token: str) -> str:
    """Build a Basic-auth header value."""
    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _jira_request(
    method: str,
    url: str,
    *,
    auth_header: str,
    data: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Execute an HTTP request against the Jira REST API.

    Args:
        method: HTTP method (GET, POST, PUT).
        url: Full URL.
        auth_header: Basic-auth header value.
        data: JSON body (for POST/PUT).
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: On non-2xx responses.
    """
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        logger.error(
            "[Jira] %s %s → %d: %s",
            method, url, exc.code, error_body[:500],
        )
        raise RuntimeError(
            f"Jira API error {exc.code}: {error_body[:300]}"
        ) from exc


def _strip_emails(text: str) -> str:
    """Remove email addresses from text to prevent credential leakage.

    The LLM agent may inadvertently include the ``ATLASSIAN_USERNAME``
    (which is an email) in issue summaries or descriptions.  This
    helper replaces any ``user@domain`` patterns with ``[redacted]``.
    """
    import re
    return re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[redacted]", text)


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
    import re

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


# Canonical Jira Cloud priority names (case-insensitive lookup).
_JIRA_PRIORITIES = {"highest", "high", "medium", "low", "lowest"}

# Cached map of canonical priority name → Jira priority id.
# Populated lazily by ``_fetch_priority_scheme()``.
_priority_id_cache: dict[str, str] | None = None


def _fetch_priority_scheme(auth_header: str, base_url: str) -> dict[str, str]:
    """Fetch available priorities from Jira and build a name→id map.

    Calls ``GET /rest/api/2/priority`` once and caches the result for
    the lifetime of the process.  The returned dict maps **lower-cased**
    priority names to their string IDs.

    If the request fails the returned dict is empty so callers can
    fall back to omitting the priority field entirely.
    """
    global _priority_id_cache  # noqa: PLW0603
    if _priority_id_cache is not None:
        return _priority_id_cache

    url = f"{base_url}/rest/api/2/priority"
    try:
        result = _jira_request("GET", url, auth_header=auth_header)
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


def _run_id_label(run_id: str) -> str:
    """Build a Jira-safe label that encodes *run_id* for search.

    Jira labels cannot contain spaces.  The returned label has the form
    ``prd-run-<run_id>`` which can be located via JQL
    ``labels = "prd-run-<run_id>"``.
    """
    # Replace whitespace / special chars to keep the label Jira-safe.
    safe = run_id.strip().replace(" ", "-")
    return f"prd-run-{safe}"


def search_jira_issues(
    run_id: str,
    *,
    issue_type: str = "",
) -> list[dict]:
    """Search Jira for issues tagged with *run_id*.

    Issues are located via the ``prd-run-<run_id>`` label that
    :func:`create_jira_issue` attaches automatically when a ``run_id``
    is supplied.

    Args:
        run_id: The PRD run identifier.
        issue_type: Optional filter (``Epic``, ``Story``, ``Task``).

    Returns:
        A list of dicts, each with ``issue_key``, ``summary``, and
        ``issue_type``.  Empty list on error.
    """
    if not run_id:
        return []

    env = _get_jira_env()
    auth = _build_auth_header(env["username"], env["api_token"])

    label = _run_id_label(run_id)
    jql_parts = [
        f"project = {env['project_key']}",
        f'labels = "{label}"',
    ]
    if issue_type:
        jql_parts.append(f'issuetype = "{issue_type}"')

    jql = " AND ".join(jql_parts)
    url = (
        f"{env['base_url']}/rest/api/2/search?"
        f"jql={urllib.parse.quote(jql)}"
        f"&fields=key,summary,issuetype&maxResults=100"
    )

    try:
        result = _jira_request("GET", url, auth_header=auth)
        issues: list[dict] = []
        for issue in result.get("issues", []):
            issues.append({
                "issue_key": issue["key"],
                "summary": issue["fields"]["summary"],
                "issue_type": issue["fields"]["issuetype"]["name"],
            })
        logger.info(
            "[Jira] Search for run_id=%s type=%s → %d issue(s)",
            run_id, issue_type or "*", len(issues),
        )
        return issues
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[Jira] Search failed for run_id=%s: %s", run_id, exc,
        )
        return []


def create_jira_issue(
    summary: str,
    description: str = "",
    issue_type: str = "Story",
    *,
    epic_key: str = "",
    labels: list[str] | None = None,
    priority: str = "",
    run_id: str = "",
    confluence_url: str = "",
    component: str = "",
) -> dict:
    """Create a Jira issue in the configured project.

    When *run_id* is provided, a ``prd-run-<run_id>`` label is added
    automatically **and** a duplicate search is performed before
    creating the issue.  If an existing issue with the same run_id
    label, issue type, and summary is found, the existing issue is
    returned instead — making the call **idempotent**.

    Args:
        summary: Issue summary / title.
        description: Detailed description (plain text or Jira wiki markup).
        issue_type: Jira issue type — ``Story``, ``Task``, ``Epic``, ``Bug``.
        epic_key: Optional parent epic key (e.g. ``PRD-42``).
        labels: Optional list of labels to apply.
        priority: Optional priority name (e.g. ``High``, ``Medium``).
        run_id: Optional run ID for logging context.
        confluence_url: Optional Confluence page URL to tag in the
            description.
        component: Optional component/role name (e.g. ``UX``,
            ``Engineering``, ``QE``).

    Returns:
        Dict with ``issue_key``, ``issue_id``, ``url``.
    """
    env = _get_jira_env()
    auth = _build_auth_header(env["username"], env["api_token"])

    # ── Attach run_id label & deduplicate ─────────────────────
    if run_id:
        rl = _run_id_label(run_id)
        if labels is None:
            labels = []
        if rl not in labels:
            labels.append(rl)

        existing = search_jira_issues(run_id, issue_type=issue_type)
        if existing:
            # For Epics only one should exist per run_id.
            # For Stories / Tasks match on summary to allow multiple.
            clean_summary = _strip_emails(summary).lower().strip()
            for hit in existing:
                if issue_type == "Epic" or hit["summary"].lower().strip() == clean_summary:
                    logger.info(
                        "[Jira] Reusing existing %s %s for run_id=%s "
                        "(summary=%s) — skipping creation",
                        issue_type,
                        hit["issue_key"],
                        run_id,
                        hit["summary"][:80],
                    )
                    return {
                        "issue_key": hit["issue_key"],
                        "issue_id": "",
                        "url": f"{env['base_url']}/browse/{hit['issue_key']}",
                        "reused": True,
                    }

    # Build full description with Confluence link when provided
    full_description = _strip_emails(description) if description else ""
    if full_description:
        full_description = _markdown_to_wiki(full_description)
    if confluence_url:
        conf_line = f"PRD Confluence page: {confluence_url}"
        if full_description:
            full_description = f"{full_description}\n\n---\n{conf_line}"
        else:
            full_description = conf_line

    fields: dict = {
        "project": {"key": env["project_key"]},
        "summary": _strip_emails(summary),
        "issuetype": {"name": issue_type},
    }

    if full_description:
        fields["description"] = full_description
    if labels:
        fields["labels"] = labels
    if priority:
        canonical = _normalize_priority(priority)
        prio_field = _resolve_priority_field(canonical, auth, env["base_url"])
        if prio_field is not None:
            fields["priority"] = prio_field
    if epic_key and issue_type != "Epic":
        # Jira Cloud uses "parent" field for epic linkage.
        # Epics are top-level issues — never set a parent on them.
        fields["parent"] = {"key": epic_key}
    elif epic_key and issue_type == "Epic":
        logger.warning(
            "[Jira] Ignoring epic_key='%s' — Epics cannot have a parent",
            epic_key,
        )
    if component:
        fields["components"] = [{"name": component}]

    payload = {"fields": fields}
    url = f"{env['base_url']}/rest/api/2/issue"

    logger.info(
        "[Jira] Creating %s '%s' in %s (run_id=%s)",
        issue_type, summary, env["project_key"], run_id,
    )
    logger.debug("[Jira] Payload: %s", json.dumps(payload, default=str))

    try:
        result = _jira_request("POST", url, auth_header=auth, data=payload)
    except RuntimeError as exc:
        err_msg = str(exc)
        # On 400 errors, check which optional fields Jira rejected,
        # strip them, and retry once so the issue is still created
        # (e.g. project priority scheme doesn't have "High").
        if "400" in err_msg:
            dropped = _drop_rejected_fields(fields, err_msg)
            if dropped:
                logger.warning(
                    "[Jira] Retrying without rejected field(s): %s",
                    ", ".join(dropped),
                )
                payload = {"fields": fields}
                logger.debug(
                    "[Jira] Retry payload: %s",
                    json.dumps(payload, default=str),
                )
                result = _jira_request(
                    "POST", url, auth_header=auth, data=payload,
                )
            else:
                raise
        else:
            raise

    issue_key = result.get("key", "")
    issue_id = result.get("id", "")
    issue_url = f"{env['base_url']}/browse/{issue_key}"

    logger.info(
        "[Jira] Created %s: key=%s id=%s url=%s (run_id=%s)",
        issue_type, issue_key, issue_id, issue_url, run_id,
    )

    return {
        "issue_key": issue_key,
        "issue_id": issue_id,
        "url": issue_url,
    }


def create_issue_link(
    inward_issue_key: str,
    outward_issue_key: str,
    link_type: str = "Blocks",
) -> None:
    """Create a dependency link between two Jira issues.

    Uses the Jira REST API ``/rest/api/2/issueLink`` endpoint.

    Args:
        inward_issue_key: The issue key that *is blocked by* or depends
            on the outward issue (e.g. ``PRD-102``).
        outward_issue_key: The blocking / prerequisite issue key
            (e.g. ``PRD-101``).
        link_type: Link type name — ``Blocks``, ``Cloners``,
            ``Duplicate``, ``Relates``, etc.  Defaults to ``Blocks``.

    Raises:
        RuntimeError: On non-2xx responses from Jira.
    """
    env = _get_jira_env()
    auth = _build_auth_header(env["username"], env["api_token"])

    payload = {
        "type": {"name": link_type},
        "inwardIssue": {"key": inward_issue_key},
        "outwardIssue": {"key": outward_issue_key},
    }

    url = f"{env['base_url']}/rest/api/2/issueLink"

    logger.info(
        "[Jira] Linking %s → %s (type=%s)",
        outward_issue_key, inward_issue_key, link_type,
    )

    _jira_request("POST", url, auth_header=auth, data=payload)


# ── CrewAI Tool wrapper ──────────────────────────────────────────────


class JiraCreateIssueInput(BaseModel):
    """Input schema for JiraCreateIssueTool."""

    summary: str = Field(
        ...,
        description="Issue summary / title.",
    )
    description: str = Field(
        default="",
        description="Detailed description of the issue.",
    )
    issue_type: str = Field(
        default="Story",
        description="Jira issue type: Story, Task, Epic, or Bug.",
    )
    epic_key: str = Field(
        default="",
        description="Parent epic key to link this issue under (e.g. 'PRD-42').",
    )
    labels: str = Field(
        default="",
        description="Comma-separated labels to apply (e.g. 'prd,auto-generated').",
    )
    priority: str = Field(
        default="",
        description="Priority name: Highest, High, Medium, Low, Lowest.",
    )
    run_id: str = Field(
        default="",
        description="Optional run ID for tracking/logging.",
    )
    confluence_url: str = Field(
        default="",
        description="Confluence page URL to tag in the ticket description.",
    )
    component: str = Field(
        default="",
        description="Component/role name (e.g. 'UX', 'Engineering', 'QE').",
    )
    parent_key: str = Field(
        default="",
        description="Parent issue key for sub-tasks (e.g. 'PRD-101'). "
        "Used for Task issues under a Story.",
    )
    blocks_key: str = Field(
        default="",
        description="Issue key that this ticket blocks (creates a 'Blocks' link).",
    )
    is_blocked_by_key: str = Field(
        default="",
        description="Issue key that blocks this ticket (creates an 'is blocked by' link).",
    )


class JiraCreateIssueTool(BaseTool):
    """Creates a Jira issue (Story, Task, Epic, or Bug) in the configured project.

    Supports:
    - Epic → Story → Task hierarchy via ``epic_key`` and ``parent_key``
    - Confluence URL tagging in descriptions
    - Component/role designation (UX, Engineering, QE)
    - Dependency linking via ``blocks_key`` / ``is_blocked_by_key``
    """

    name: str = "jira_create_issue"
    description: str = (
        "Creates a Jira issue in the configured Atlassian Jira project. "
        "Supports Stories, Tasks, Epics, and Bugs. "
        "Use this to create tickets for PRD requirements, action items, "
        "and feature tracking.  Supports Epic→Story→Task hierarchy, "
        "Confluence URL tagging, component/role assignment (UX, Engineering, QE), "
        "and dependency linking (blocks / is blocked by)."
    )
    args_schema: Type[BaseModel] = JiraCreateIssueInput

    def _run(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "Story",
        epic_key: str = "",
        labels: str = "",
        priority: str = "",
        run_id: str = "",
        confluence_url: str = "",
        component: str = "",
        parent_key: str = "",
        blocks_key: str = "",
        is_blocked_by_key: str = "",
    ) -> str:
        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []

        # parent_key takes precedence for sub-tasks; epic_key is the fallback
        effective_parent = parent_key or epic_key

        try:
            result = create_jira_issue(
                summary=summary,
                description=description,
                issue_type=issue_type,
                epic_key=effective_parent,
                labels=label_list,
                priority=priority,
                run_id=run_id,
                confluence_url=confluence_url,
                component=component,
            )

            created_key = result["issue_key"]

            # Create dependency links if requested
            if blocks_key:
                try:
                    create_issue_link(
                        inward_issue_key=blocks_key,
                        outward_issue_key=created_key,
                        link_type="Blocks",
                    )
                except Exception as exc:
                    logger.warning(
                        "[Jira] Failed to create 'Blocks' link %s → %s: %s",
                        created_key, blocks_key, exc,
                    )
            if is_blocked_by_key:
                try:
                    create_issue_link(
                        inward_issue_key=created_key,
                        outward_issue_key=is_blocked_by_key,
                        link_type="Blocks",
                    )
                except Exception as exc:
                    logger.warning(
                        "[Jira] Failed to create 'is blocked by' link %s → %s: %s",
                        created_key, is_blocked_by_key, exc,
                    )

            return (
                f"Jira {issue_type} created: "
                f"key={result['issue_key']} url={result['url']}"
            )
        except EnvironmentError as exc:
            return f"Jira issue creation skipped: {exc}"
        except Exception as exc:
            logger.error("[Jira] Create issue failed: %s", exc)
            return f"Jira issue creation failed: {exc}"
