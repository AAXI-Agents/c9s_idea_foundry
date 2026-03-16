"""Playwright-based client for Figma Make browser automation.

Drives the Figma Make web UI via a headless Chromium browser to create
AI-generated designs.  Supports three auth modes (tried in order):

1. **OAuth2 token** — injected as a cookie into the browser context.
2. **Playwright session state** — a stored ``state.json`` with cookies.
3. **No auth** — raises ``FigmaMakeError``.

After a design is created the resulting file URL and file key are
returned so the caller can persist them in MongoDB.

Prerequisites:
    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.figma._config import (
    FIGMA_MAKE_URL,
    get_figma_credentials,
    get_figma_headless,
    get_figma_make_timeout,
    get_figma_session_path,
)

logger = get_logger(__name__)

# Regex to extract the file key from a Figma Make URL.
_FILE_KEY_RE = re.compile(r"figma\.com/make/(?!new)([A-Za-z0-9]+)")

# Selector candidates for the chat prompt input.
_INPUT_SELECTOR = "textarea, [role='textbox'], [contenteditable='true']"


class FigmaMakeError(Exception):
    """Raised when Figma Make automation fails."""


# ── public API ───────────────────────────────────────────────


def run_figma_make(
    prompt: str,
    *,
    timeout: int = 0,
    project_config: dict[str, Any] | None = None,
) -> dict:
    """Generate a design in Figma Make via Playwright.

    Opens a headless Chromium browser, authenticates using project
    credentials (OAuth token) or a stored Playwright session, enters
    the *prompt* in the Figma Make chat, waits for the file to be
    created, and returns a dict with ``file_url``, ``file_key``,
    and ``status``.

    Raises :class:`FigmaMakeError` on failure or timeout.
    """
    timeout = timeout or get_figma_make_timeout()
    state_path = get_figma_session_path()
    headless = get_figma_headless()
    timeout_ms = timeout * 1000
    creds = get_figma_credentials(project_config)

    logger.info(
        "[Figma] Starting Playwright Make session "
        "(prompt=%d chars, headless=%s)",
        len(prompt), headless,
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)

        # Build browser context with best available auth
        context = _build_context(
            browser, creds=creds, state_path=state_path,
        )
        page = context.new_page()

        try:
            # 1. Navigate to Figma Make --------------------------------
            logger.info("[Figma] Navigating to %s", FIGMA_MAKE_URL)
            page.goto(
                FIGMA_MAKE_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            # 2. Detect login redirect (session expired) ---------------
            if "/login" in page.url or "/signin" in page.url:
                raise FigmaMakeError(
                    "Figma session expired. Re-run OAuth login or: "
                    "python -m crewai_productfeature_planner"
                    ".tools.figma.login"
                )

            # 3. Enter prompt ------------------------------------------
            chat_input = _find_chat_input(page, timeout_ms=30_000)
            chat_input.fill(prompt)
            logger.info("[Figma] Prompt entered (%d chars)", len(prompt))

            # 4. Send --------------------------------------------------
            _send_prompt(page, chat_input, timeout_ms=10_000)
            logger.info(
                "[Figma] Prompt sent, waiting for file creation…",
            )

            # 5. Wait for URL to change (file created) -----------------
            page.wait_for_url(
                lambda url: "/make/" in url and "/make/new" not in url,
                timeout=timeout_ms,
            )
            file_url = page.url

            match = _FILE_KEY_RE.search(file_url)
            file_key = match.group(1) if match else ""

            logger.info(
                "[Figma] File created: key=%s url=%s",
                file_key, file_url,
            )

            # 6. Wait for generation to settle -------------------------
            _wait_for_generation(page, timeout_ms=timeout_ms)

            # 7. Persist refreshed session cookies ---------------------
            if os.path.isfile(state_path) or not creds.get("oauth_token"):
                context.storage_state(path=state_path)

            return {
                "file_url": file_url,
                "file_key": file_key,
                "status": "completed",
            }

        except PlaywrightTimeout as exc:
            logger.error("[Figma] Timeout: %s", exc)
            raise FigmaMakeError(
                f"Figma Make timed out after {timeout}s"
            ) from exc
        except FigmaMakeError:
            raise
        except Exception as exc:
            logger.error("[Figma] Unexpected error: %s", exc)
            raise FigmaMakeError(
                f"Figma Make browser error: {exc}"
            ) from exc
        finally:
            context.close()
            browser.close()


# ── auth helpers ─────────────────────────────────────────────


def _build_context(browser, *, creds: dict[str, str], state_path: str):
    """Create a Playwright browser context with the best available auth.

    Priority:
    1. OAuth token → inject as a cookie
    2. Stored Playwright session state file
    3. Empty context (will likely redirect to login)
    """
    oauth_token = creds.get("oauth_token", "")

    # Try OAuth token first — inject it as Figma session cookie
    if oauth_token:
        logger.info("[Figma] Using OAuth token for browser auth")
        context = browser.new_context()
        context.add_cookies([
            {
                "name": "figma.authn",
                "value": oauth_token,
                "domain": ".figma.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
        ])
        return context

    # Fall back to stored Playwright session
    if os.path.isfile(state_path):
        logger.info("[Figma] Using stored Playwright session: %s", state_path)
        return browser.new_context(storage_state=state_path)

    logger.warning("[Figma] No auth available — login redirect likely")
    return browser.new_context()


# ── UI interaction helpers ───────────────────────────────────


def _find_chat_input(page, *, timeout_ms: int = 30_000):
    """Locate the Figma Make chat prompt input."""
    page.wait_for_selector(
        _INPUT_SELECTOR,
        state="visible",
        timeout=timeout_ms,
    )

    for locator_fn in (
        lambda: page.locator("textarea").first,
        lambda: page.get_by_role("textbox").first,
        lambda: page.locator("[contenteditable='true']").first,
    ):
        try:
            el = locator_fn()
            if el.is_visible():
                return el
        except Exception:  # noqa: BLE001
            continue

    raise FigmaMakeError("Could not find chat input in Figma Make UI")


def _send_prompt(page, chat_input, *, timeout_ms: int = 10_000):
    """Send the prompt by pressing Enter or clicking the send button."""
    # Try pressing Enter first — standard chat shortcut.
    chat_input.press("Enter")

    # If a dedicated send button exists, click it as backup.
    for get_btn in (
        lambda: page.get_by_role(
            "button", name=re.compile(r"(?i)send"),
        ),
        lambda: page.locator(
            "button[aria-label*='end' i], button[type='submit']",
        ).first,
    ):
        try:
            btn = get_btn()
            if btn.is_visible(timeout=2000):
                btn.click()
                return
        except Exception:  # noqa: BLE001
            continue


def _wait_for_generation(page, *, timeout_ms: int = 300_000):
    """Best-effort wait for design generation to finish."""
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 120_000))
    except PlaywrightTimeout:
        logger.debug(
            "[Figma] networkidle not reached — file URL already captured.",
        )
