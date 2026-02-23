"""Atlassian Jira ticket creation tool.

Creates issues (Stories, Tasks, Epics, Bugs) in a Jira project via the
Jira REST API v2.

Environment variables:

* ``JIRA_BASE_URL``    — e.g. ``https://yourcompany.atlassian.net``
* ``JIRA_PROJECT_KEY`` — target project key (e.g. ``PRD``)
* ``JIRA_USERNAME``    — Atlassian account email
* ``JIRA_API_TOKEN``   — API token (https://id.atlassian.com/manage-profile/security/api-tokens)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import base64
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _get_jira_env() -> dict[str, str]:
    """Read Jira config from environment.

    Returns:
        Dict with keys ``base_url``, ``project_key``, ``username``,
        ``api_token``.

    Raises:
        EnvironmentError: If required vars are missing.
    """
    base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    project_key = os.environ.get("JIRA_PROJECT_KEY", "")
    username = os.environ.get("JIRA_USERNAME", "")
    api_token = os.environ.get("JIRA_API_TOKEN", "")

    missing: list[str] = []
    if not base_url:
        missing.append("JIRA_BASE_URL")
    if not project_key:
        missing.append("JIRA_PROJECT_KEY")
    if not username:
        missing.append("JIRA_USERNAME")
    if not api_token:
        missing.append("JIRA_API_TOKEN")

    if missing:
        raise EnvironmentError(
            f"Jira tool requires: {', '.join(missing)}"
        )

    return {
        "base_url": base_url,
        "project_key": project_key,
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

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def create_jira_issue(
    summary: str,
    description: str = "",
    issue_type: str = "Story",
    *,
    epic_key: str = "",
    labels: list[str] | None = None,
    priority: str = "",
    run_id: str = "",
) -> dict:
    """Create a Jira issue in the configured project.

    Args:
        summary: Issue summary / title.
        description: Detailed description (plain text or Jira wiki markup).
        issue_type: Jira issue type — ``Story``, ``Task``, ``Epic``, ``Bug``.
        epic_key: Optional parent epic key (e.g. ``PRD-42``).
        labels: Optional list of labels to apply.
        priority: Optional priority name (e.g. ``High``, ``Medium``).
        run_id: Optional run ID for logging context.

    Returns:
        Dict with ``issue_key``, ``issue_id``, ``url``.
    """
    env = _get_jira_env()
    auth = _build_auth_header(env["username"], env["api_token"])

    fields: dict = {
        "project": {"key": env["project_key"]},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }

    if description:
        fields["description"] = description
    if labels:
        fields["labels"] = labels
    if priority:
        fields["priority"] = {"name": priority}
    if epic_key:
        # Jira Cloud uses "parent" field for epic linkage
        fields["parent"] = {"key": epic_key}

    payload = {"fields": fields}
    url = f"{env['base_url']}/rest/api/2/issue"

    logger.info(
        "[Jira] Creating %s '%s' in %s (run_id=%s)",
        issue_type, summary, env["project_key"], run_id,
    )

    result = _jira_request("POST", url, auth_header=auth, data=payload)

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


class JiraCreateIssueTool(BaseTool):
    """Creates a Jira issue (Story, Task, Epic, or Bug) in the configured project."""

    name: str = "jira_create_issue"
    description: str = (
        "Creates a Jira issue in the configured Atlassian Jira project. "
        "Supports Stories, Tasks, Epics, and Bugs. "
        "Use this to create tickets for PRD requirements, action items, "
        "and feature tracking."
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
    ) -> str:
        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []

        try:
            result = create_jira_issue(
                summary=summary,
                description=description,
                issue_type=issue_type,
                epic_key=epic_key,
                labels=label_list,
                priority=priority,
                run_id=run_id,
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
