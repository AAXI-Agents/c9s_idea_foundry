"""Interactive Figma login — browser session or OAuth2.

Supports two modes:

1. **Session login** (default) — opens a visible Chromium browser,
   navigates to ``figma.com/login``, waits for the user to log in,
   and saves the Playwright session state to
   ``FIGMA_SESSION_DIR/state.json``.

2. **OAuth login** (``--oauth``) — drives the Figma OAuth2
   authorization flow via Playwright.  Opens the Figma consent page,
   captures the redirect with the authorization code, exchanges it
   for access + refresh tokens, and prints them for storage in the
   project config.

Usage::

    # Session login (saves state.json for Playwright reuse)
    python -m crewai_productfeature_planner.tools.figma.login

    # OAuth login (prints tokens for project config)
    python -m crewai_productfeature_planner.tools.figma.login --oauth
"""

from __future__ import annotations

import os
import secrets
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from crewai_productfeature_planner.tools.figma._config import (
    FIGMA_OAUTH_URL,
    OAUTH_REDIRECT_URI,
    get_figma_client_id,
    get_figma_client_secret,
    get_figma_session_dir,
    get_figma_session_path,
)


def main() -> None:
    if "--oauth" in sys.argv:
        _oauth_login()
    else:
        _session_login()


# ── Session-based login ─────────────────────────────────────


def _session_login() -> None:
    """Interactive browser login — save Playwright session state."""
    session_dir = get_figma_session_dir()
    state_path = get_figma_session_path()
    os.makedirs(session_dir, exist_ok=True)

    print("=" * 60)
    print("  Figma Make — Interactive Login")
    print("=" * 60)
    print()
    print("A browser window will open.  Log in to your Figma account")
    print("(complete 2FA if prompted).  Once you see the Figma file")
    print("browser / dashboard, press ENTER in this terminal to save")
    print("the session and close the browser.")
    print()
    print(f"  Session will be saved to: {state_path}")
    print()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.figma.com/login", wait_until="domcontentloaded")

        input(">>> Press ENTER after you have logged in to Figma... ")

        context.storage_state(path=state_path)
        print(f"\n  Session saved to {state_path}")

        context.close()
        browser.close()

    print("  Done — you can now use Figma Make automation.\n")


# ── OAuth2 login ────────────────────────────────────────────


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Captures the OAuth redirect and extracts the auth code."""

    auth_code: str | None = None
    returned_state: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        qs = parse_qs(urlparse(self.path).query)
        _OAuthCallbackHandler.auth_code = qs.get("code", [None])[0]
        _OAuthCallbackHandler.returned_state = qs.get("state", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Authorization complete!</h2>"
            b"<p>You can close this tab.</p></body></html>"
        )

    def log_message(self, *_args) -> None:  # noqa: ANN002
        pass  # suppress HTTP log noise


def _oauth_login() -> None:
    """Playwright-driven OAuth2 flow — prints tokens."""
    client_id = get_figma_client_id()
    client_secret = get_figma_client_secret()

    if not client_id or not client_secret:
        print(
            "ERROR: Set FIGMA_CLIENT_ID and FIGMA_CLIENT_SECRET "
            "environment variables first."
        )
        sys.exit(1)

    state = secrets.token_urlsafe(32)
    scopes = "file_content:read,files:read"

    auth_url = (
        f"{FIGMA_OAUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={OAUTH_REDIRECT_URI}"
        f"&scope={scopes}"
        f"&state={state}"
        f"&response_type=code"
    )

    print("=" * 60)
    print("  Figma Make — OAuth2 Login")
    print("=" * 60)
    print()
    print("A browser window will open Figma's authorization page.")
    print("Click 'Allow access' to grant permissions.")
    print()

    # Start local HTTP server to capture redirect
    parsed = urlparse(OAUTH_REDIRECT_URI)
    port = parsed.port or 3000
    server = HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
    server_thread = Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(auth_url, wait_until="domcontentloaded")

        # Wait for the callback to capture the code
        deadline = time.time() + 120
        while _OAuthCallbackHandler.auth_code is None and time.time() < deadline:
            time.sleep(0.5)

        context.close()
        browser.close()

    server.server_close()

    code = _OAuthCallbackHandler.auth_code
    returned_state = _OAuthCallbackHandler.returned_state

    if not code:
        print("\nERROR: No authorization code received (timed out or denied).")
        sys.exit(1)

    if returned_state != state:
        print("\nERROR: OAuth state mismatch — possible CSRF attack.")
        sys.exit(1)

    # Exchange code for tokens
    from crewai_productfeature_planner.tools.figma._api import exchange_oauth_code

    try:
        result = exchange_oauth_code(
            code,
            OAUTH_REDIRECT_URI,
            client_id=client_id,
            client_secret=client_secret,
        )
    except Exception as exc:
        print(f"\nERROR: Token exchange failed: {exc}")
        sys.exit(1)

    access_token = result.get("access_token", "")
    refresh_token = result.get("refresh_token", "")
    expires_in = result.get("expires_in", 0)

    print()
    print("  OAuth2 tokens obtained successfully!")
    print()
    print(f"  Access token:  {access_token[:20]}…")
    print(f"  Refresh token: {refresh_token[:20]}…")
    print(f"  Expires in:    {expires_in}s")
    print()
    print("  Store these in your project config via the setup wizard")
    print("  or update_project().")
    print()

    # Also write tokens to a file for easy retrieval
    session_dir = get_figma_session_dir()
    os.makedirs(session_dir, exist_ok=True)
    token_path = os.path.join(session_dir, "oauth_tokens.json")
    import json

    with open(token_path, "w") as f:
        json.dump(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
            },
            f,
            indent=2,
        )
    print(f"  Tokens also saved to: {token_path}\n")


if __name__ == "__main__":
    main()
