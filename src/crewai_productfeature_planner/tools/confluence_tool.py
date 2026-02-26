"""Atlassian Confluence publishing tool.

Publishes Markdown content to a Confluence space as a new or updated
page via the Confluence REST API.

Environment variables:

* ``ATLASSIAN_BASE_URL``   — e.g. ``https://yourcompany.atlassian.net``
* ``ATLASSIAN_USERNAME``   — Atlassian account email
* ``ATLASSIAN_API_TOKEN``  — API token (https://id.atlassian.com/manage-profile/security/api-tokens)
* ``CONFLUENCE_SPACE_KEY`` — target space key (e.g. ``PRD``)
* ``CONFLUENCE_PARENT_ID`` — (optional) parent page id to nest new pages under
"""

from __future__ import annotations

import json
import os
import ssl
from typing import Type

import certifi
import urllib.error
import urllib.parse
import urllib.request
import base64

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.confluence_xhtml import (
    md_to_confluence_xhtml,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _get_confluence_env() -> dict[str, str]:
    """Read Confluence config from environment.

    Returns:
        Dict with keys ``base_url``, ``space_key``, ``username``,
        ``api_token``, and optionally ``parent_id``.

    Raises:
        EnvironmentError: If required vars are missing.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "").rstrip("/")
    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    missing: list[str] = []
    if not base_url:
        missing.append("ATLASSIAN_BASE_URL")
    if not space_key:
        missing.append("CONFLUENCE_SPACE_KEY")
    if not username:
        missing.append("ATLASSIAN_USERNAME")
    if not api_token:
        missing.append("ATLASSIAN_API_TOKEN")

    if missing:
        raise EnvironmentError(
            f"Confluence tool requires: {', '.join(missing)}"
        )

    # Confluence Cloud REST API lives under /wiki.  If the shared
    # ATLASSIAN_BASE_URL does not already include the /wiki prefix,
    # append it so that all Confluence API calls hit the correct path.
    if not base_url.endswith("/wiki"):
        base_url = f"{base_url}/wiki"

    return {
        "base_url": base_url,
        "space_key": space_key,
        "username": username,
        "api_token": api_token,
        "parent_id": os.environ.get("CONFLUENCE_PARENT_ID", ""),
    }


def _has_confluence_credentials() -> bool:
    """Return ``True`` when all required Confluence env vars are set."""
    try:
        _get_confluence_env()
        return True
    except EnvironmentError:
        return False


def _build_auth_header(username: str, api_token: str) -> str:
    """Build a Basic-auth header value."""
    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _confluence_request(
    method: str,
    url: str,
    *,
    auth_header: str,
    data: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Execute an HTTP request against the Confluence REST API.

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
            "[Confluence] %s %s → %d: %s",
            method, url, exc.code, error_body[:500],
        )
        raise RuntimeError(
            f"Confluence API error {exc.code}: {error_body[:300]}"
        ) from exc


def find_page_by_title(
    title: str,
    *,
    base_url: str,
    space_key: str,
    auth_header: str,
) -> dict | None:
    """Search for an existing page by exact title in the given space.

    Returns the page dict (with ``id``, ``version``, etc.) or ``None``.
    """
    encoded_title = urllib.parse.quote(title)
    url = (
        f"{base_url}/rest/api/content"
        f"?spaceKey={space_key}"
        f"&title={encoded_title}"
        f"&expand=version"
    )
    result = _confluence_request("GET", url, auth_header=auth_header)
    results = result.get("results", [])
    return results[0] if results else None


def publish_to_confluence(
    title: str,
    markdown_content: str,
    *,
    run_id: str = "",
) -> dict:
    """Publish a Markdown document to Confluence.

    If a page with the same *title* already exists in the target space
    it is **updated**; otherwise a new page is created.

    Args:
        title: Page title in Confluence.
        markdown_content: Raw Markdown to convert and publish.
        run_id: Optional run ID for logging context.

    Returns:
        Dict with ``page_id``, ``url``, and ``action`` (``created`` or
        ``updated``).
    """
    env = _get_confluence_env()
    auth = _build_auth_header(env["username"], env["api_token"])

    xhtml = md_to_confluence_xhtml(markdown_content)
    logger.info(
        "[Confluence] Publishing '%s' (%d chars XHTML, run_id=%s)",
        title, len(xhtml), run_id,
    )

    existing = find_page_by_title(
        title,
        base_url=env["base_url"],
        space_key=env["space_key"],
        auth_header=auth,
    )

    if existing:
        # Update existing page
        page_id = existing["id"]
        current_version = existing["version"]["number"]
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "space": {"key": env["space_key"]},
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": xhtml,
                    "representation": "storage",
                },
            },
        }
        url = f"{env['base_url']}/rest/api/content/{page_id}"
        result = _confluence_request("PUT", url, auth_header=auth, data=payload)
        action = "updated"
    else:
        # Create new page
        payload: dict = {
            "type": "page",
            "title": title,
            "space": {"key": env["space_key"]},
            "body": {
                "storage": {
                    "value": xhtml,
                    "representation": "storage",
                },
            },
        }
        if env["parent_id"]:
            payload["ancestors"] = [{"id": env["parent_id"]}]

        url = f"{env['base_url']}/rest/api/content"
        result = _confluence_request("POST", url, auth_header=auth, data=payload)
        action = "created"

    page_id = result["id"]
    page_url = f"{env['base_url']}/pages/{page_id}"
    link_url = result.get("_links", {}).get("webui", "")
    if link_url:
        page_url = f"{env['base_url']}{link_url}"

    logger.info(
        "[Confluence] Page %s: id=%s url=%s (run_id=%s)",
        action, page_id, page_url, run_id,
    )
    return {"page_id": page_id, "url": page_url, "action": action}


# ── CrewAI Tool wrapper ──────────────────────────────────────────────


class ConfluencePublishInput(BaseModel):
    """Input schema for ConfluencePublishTool."""

    title: str = Field(
        ...,
        description="Title for the Confluence page.",
    )
    markdown_content: str = Field(
        ...,
        description="Markdown content to publish. Will be converted to "
        "Confluence XHTML automatically.",
    )
    run_id: str = Field(
        default="",
        description="Optional run ID for tracking/logging.",
    )


class ConfluencePublishTool(BaseTool):
    """Publishes Markdown content as a Confluence page.

    Creates a new page or updates an existing one with the same title
    in the configured Confluence space.
    """

    name: str = "confluence_publisher"
    description: str = (
        "Publishes a Markdown document to Atlassian Confluence. "
        "Creates a new page or updates an existing one. "
        "Use this to push PRD documents and project artefacts to Confluence."
    )
    args_schema: Type[BaseModel] = ConfluencePublishInput

    def _run(
        self,
        title: str,
        markdown_content: str,
        run_id: str = "",
    ) -> str:
        try:
            result = publish_to_confluence(
                title=title,
                markdown_content=markdown_content,
                run_id=run_id,
            )
            return (
                f"Confluence page {result['action']}: "
                f"id={result['page_id']} url={result['url']}"
            )
        except EnvironmentError as exc:
            return f"Confluence publish skipped: {exc}"
        except Exception as exc:
            logger.error("[Confluence] Publish failed: %s", exc)
            return f"Confluence publish failed: {exc}"
