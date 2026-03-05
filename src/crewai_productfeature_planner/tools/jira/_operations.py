"""Jira issue CRUD operations — search, create, and link."""

from __future__ import annotations

import json
import urllib.parse

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.jira import (
    _config as _config_mod,
    _helpers as _helpers_mod,
    _http as _http_mod,
)

logger = get_logger(__name__)


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

    env = _config_mod._get_jira_env()
    auth = _config_mod._build_auth_header(env["username"], env["api_token"])

    label = _helpers_mod._run_id_label(run_id)
    jql_parts = [
        f"project = {env['project_key']}",
        f'labels = "{label}"',
    ]
    if issue_type:
        jql_parts.append(f'issuetype = "{issue_type}"')

    jql = " AND ".join(jql_parts)
    url = (
        f"{env['base_url']}/rest/api/3/search/jql?"
        f"jql={urllib.parse.quote(jql)}"
        f"&fields=key,summary,issuetype&maxResults=100"
    )

    try:
        result = _http_mod._jira_request("GET", url, auth_header=auth)
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
    env = _config_mod._get_jira_env()
    auth = _config_mod._build_auth_header(env["username"], env["api_token"])

    # ── Attach run_id label & deduplicate ─────────────────────
    if run_id:
        rl = _helpers_mod._run_id_label(run_id)
        if labels is None:
            labels = []
        if rl not in labels:
            labels.append(rl)

        existing = search_jira_issues(run_id, issue_type=issue_type)
        if existing:
            # For Epics only one should exist per run_id.
            # For Stories / Tasks match on summary to allow multiple.
            clean_summary = _helpers_mod._strip_emails(summary).lower().strip()
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

    # Build full description with Confluence link when provided.
    # Strip emails first, then construct the raw text before ADF conversion.
    full_description = _helpers_mod._strip_emails(description) if description else ""
    if confluence_url:
        conf_line = f"PRD Confluence page: {confluence_url}"
        if full_description:
            full_description = f"{full_description}\n\n---\n{conf_line}"
        else:
            full_description = conf_line

    fields: dict = {
        "project": {"key": env["project_key"]},
        "summary": _helpers_mod._strip_emails(summary),
        "issuetype": {"name": issue_type},
    }

    if full_description:
        # Jira API v3 requires description in Atlassian Document Format
        fields["description"] = _helpers_mod._markdown_to_adf(full_description)
    if labels:
        fields["labels"] = labels
    if priority:
        canonical = _helpers_mod._normalize_priority(priority)
        prio_field = _helpers_mod._resolve_priority_field(canonical, auth, env["base_url"])
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
    url = f"{env['base_url']}/rest/api/3/issue"

    logger.info(
        "[Jira] Creating %s '%s' in %s (run_id=%s)",
        issue_type, summary, env["project_key"], run_id,
    )
    logger.debug("[Jira] Payload: %s", json.dumps(payload, default=str))

    try:
        result = _http_mod._jira_request("POST", url, auth_header=auth, data=payload)
    except RuntimeError as exc:
        err_msg = str(exc)
        # On 400 errors, check which optional fields Jira rejected,
        # strip them, and retry once so the issue is still created
        # (e.g. project priority scheme doesn't have "High").
        if "400" in err_msg:
            dropped = _helpers_mod._drop_rejected_fields(fields, err_msg)
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
                result = _http_mod._jira_request(
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

    Uses the Jira REST API ``/rest/api/3/issueLink`` endpoint.

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
    env = _config_mod._get_jira_env()
    auth = _config_mod._build_auth_header(env["username"], env["api_token"])

    payload = {
        "type": {"name": link_type},
        "inwardIssue": {"key": inward_issue_key},
        "outwardIssue": {"key": outward_issue_key},
    }

    url = f"{env['base_url']}/rest/api/3/issueLink"

    logger.info(
        "[Jira] Linking %s → %s (type=%s)",
        outward_issue_key, inward_issue_key, link_type,
    )

    _http_mod._jira_request("POST", url, auth_header=auth, data=payload)
