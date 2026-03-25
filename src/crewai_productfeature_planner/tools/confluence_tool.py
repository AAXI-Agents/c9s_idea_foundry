"""Atlassian Confluence publishing tool.

Publishes Markdown content to a Confluence space as a new or updated
page via the Confluence REST API.

Key resolution order (highest priority first):

1. Explicit ``space_key`` parameter on :func:`publish_to_confluence`
2. ``_space_key_ctx`` context variable (set by orchestrator stages
   with project-level configuration)
3. ``CONFLUENCE_SPACE_KEY`` environment variable (integration / testing
   fallback)

Environment variables:

* ``ATLASSIAN_BASE_URL``   — e.g. ``https://yourcompany.atlassian.net``
* ``ATLASSIAN_USERNAME``   — Atlassian account email
* ``ATLASSIAN_API_TOKEN``  — API token (https://id.atlassian.com/manage-profile/security/api-tokens)
* ``CONFLUENCE_SPACE_KEY`` — fallback space key for testing / integration
* ``CONFLUENCE_PARENT_ID`` — (optional) parent page id to nest new pages under
"""

from __future__ import annotations

import contextvars
import json
import os
import ssl
from contextlib import contextmanager
from typing import Generator, Type

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

# ── Context-variable overrides (set by orchestrator with project config) ──

_space_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "confluence_space_key_override", default="",
)
_parent_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "confluence_parent_id_override", default="",
)


def set_confluence_space_key(key: str) -> contextvars.Token[str]:
    """Set the Confluence space key for the current context.

    Returns a reset token for use with :meth:`contextvars.ContextVar.reset`.
    """
    return _space_key_ctx.set(key)


def set_confluence_parent_id(parent_id: str) -> contextvars.Token[str]:
    """Set the Confluence parent page ID for the current context."""
    return _parent_id_ctx.set(parent_id)


@contextmanager
def confluence_project_context(
    *,
    space_key: str = "",
    parent_id: str = "",
) -> Generator[None, None, None]:
    """Context manager that sets project-level Confluence overrides.

    Usage::

        with confluence_project_context(space_key="PRJ", parent_id="12345"):
            publish_to_confluence(title, content, run_id=rid)
    """
    tokens: list[tuple[contextvars.ContextVar, contextvars.Token]] = []
    if space_key:
        tokens.append((_space_key_ctx, _space_key_ctx.set(space_key)))
    if parent_id:
        tokens.append((_parent_id_ctx, _parent_id_ctx.set(parent_id)))
    try:
        yield
    finally:
        for var, token in tokens:
            var.reset(token)


def _get_confluence_env(*, space_key: str | None = None) -> dict[str, str]:
    """Read Confluence config from environment with optional overrides.

    Resolution order for ``space_key``:

    1. Explicit *space_key* parameter
    2. ``_space_key_ctx`` context variable
    3. ``CONFLUENCE_SPACE_KEY`` environment variable

    Returns:
        Dict with keys ``base_url``, ``space_key``, ``username``,
        ``api_token``, and optionally ``parent_id``.

    Raises:
        EnvironmentError: If required vars are missing.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "").rstrip("/")
    resolved_space_key = (
        space_key
        or _space_key_ctx.get()
        or os.environ.get("CONFLUENCE_SPACE_KEY", "")
    )
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    missing: list[str] = []
    if not base_url:
        missing.append("ATLASSIAN_BASE_URL")
    if not resolved_space_key:
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

    resolved_parent_id = (
        _parent_id_ctx.get()
        or os.environ.get("CONFLUENCE_PARENT_ID", "")
    )

    return {
        "base_url": base_url,
        "space_key": resolved_space_key,
        "username": username,
        "api_token": api_token,
        "parent_id": resolved_parent_id,
    }


def _has_confluence_credentials() -> bool:
    """Return ``True`` when Atlassian connection credentials are set.

    Only checks the three connection-level env vars
    (``ATLASSIAN_BASE_URL``, ``ATLASSIAN_USERNAME``, ``ATLASSIAN_API_TOKEN``).
    ``CONFLUENCE_SPACE_KEY`` is intentionally excluded because it can be
    supplied per-project via ``projectConfig`` at publish time.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")
    return bool(base_url and username and api_token)


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
            raw = resp.read().decode()
            try:
                return json.loads(raw)
            except json.JSONDecodeError as jde:
                logger.error(
                    "[Confluence] %s %s — invalid JSON response: %s",
                    method, url, raw[:200],
                )
                raise RuntimeError(
                    f"Confluence API returned invalid JSON: {raw[:200]}"
                ) from jde
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


def _get_page_by_id(
    page_id: str,
    *,
    base_url: str,
    auth_header: str,
) -> dict | None:
    """Fetch an existing page by its Confluence page ID.

    Returns the page dict (with ``id``, ``version``, etc.) or ``None``
    if the page does not exist (404).
    """
    url = f"{base_url}/rest/api/content/{page_id}?expand=version"
    try:
        return _confluence_request("GET", url, auth_header=auth_header)
    except RuntimeError:
        # Page may have been deleted — fall back to title search
        return None


def publish_to_confluence(
    title: str,
    markdown_content: str,
    *,
    run_id: str = "",
    space_key: str | None = None,
    page_id: str | None = None,
) -> dict:
    """Publish a Markdown document to Confluence.

    When *page_id* is provided the existing page is updated directly
    (no title search needed).  Otherwise, if a page with the same
    *title* already exists in the target space it is **updated**;
    otherwise a new page is created.

    Args:
        title: Page title in Confluence.
        markdown_content: Raw Markdown to convert and publish.
        run_id: Optional run ID for logging context.
        space_key: Optional explicit space key override.  When omitted,
            resolved via context variable → ``CONFLUENCE_SPACE_KEY`` env.
        page_id: Optional existing Confluence page ID.  When provided,
            the page is updated by ID — avoiding duplicate creation
            when the same idea is published more than once.

    Returns:
        Dict with ``page_id``, ``url``, and ``action`` (``created`` or
        ``updated``).
    """
    env = _get_confluence_env(space_key=space_key)
    auth = _build_auth_header(env["username"], env["api_token"])

    xhtml = md_to_confluence_xhtml(markdown_content)
    logger.info(
        "[Confluence] Publishing '%s' (%d chars XHTML, run_id=%s, page_id=%s)",
        title, len(xhtml), run_id, page_id or "<new>",
    )

    # Resolve existing page: prefer stored page_id, fall back to title search
    existing = None
    if page_id:
        existing = _get_page_by_id(
            page_id,
            base_url=env["base_url"],
            auth_header=auth,
        )
    if not existing:
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
