import json
import os
import ssl
import sys
import urllib.error
import urllib.request

import certifi
from pymongo import MongoClient

ENV_FILE = ".env"

API_KEYS = {
    "OPENAI_API_KEY": "OpenAI",
    "SONNET_API_KEY": "Sonnet",
    "GEOAPIFY_API_KEY": "Geoapify",
    "GROK_API_KEY": "Grok",
    "GOOGLE_API_KEY": "Gemini",
    "HUNTER_API_KEY": "Hunter",
    "FIRECRAWL_API_KEY": "Firecrawl",
}


def load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def mask_value(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 6:
        return "***"
    return f"***{value[-4:]}"


def http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: dict | None = None,
    timeout: int = 15,
) -> tuple[int, str]:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if body is not None:
        request.add_header("Content-Type", "application/json")

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return response.status, payload


def check_openai() -> tuple[bool, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return False, "OPENAI_API_KEY is empty"
    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    status, _ = http_request(url, headers=headers)
    return status == 200, f"HTTP {status}"


def check_sonnet() -> tuple[bool, str]:
    api_key = os.environ.get("SONNET_API_KEY", "")
    if not api_key:
        return False, "SONNET_API_KEY is empty"
    model = os.environ.get("SONNET_MODEL_NAME", "sonnet-default")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    status, _ = http_request(url, method="POST", headers=headers, body=body)
    return status == 200, f"HTTP {status}"


def check_gemini() -> tuple[bool, str]:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return False, "GOOGLE_API_KEY is empty"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    status, _ = http_request(url)
    return status == 200, f"HTTP {status}"


def check_geoapify() -> tuple[bool, str]:
    api_key = os.environ.get("GEOAPIFY_API_KEY", "")
    if not api_key:
        return False, "GEOAPIFY_API_KEY is empty"
    url = (
        "https://api.geoapify.com/v1/geocode/search"
        f"?text=1600+Amphitheatre+Parkway&apiKey={api_key}&limit=1"
    )
    status, _ = http_request(url)
    return status == 200, f"HTTP {status}"


def check_grok() -> tuple[bool, str]:
    api_key = os.environ.get("GROK_API_KEY", "")
    if not api_key:
        return False, "GROK_API_KEY is empty"
    url = "https://api.x.ai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    status, _ = http_request(url, headers=headers)
    return status == 200, f"HTTP {status}"


def check_hunter() -> tuple[bool, str]:
    api_key = os.environ.get("HUNTER_API_KEY", "")
    if not api_key:
        return False, "HUNTER_API_KEY is empty"
    url = f"https://api.hunter.io/v2/account?api_key={api_key}"
    status, _ = http_request(url)
    return status == 200, f"HTTP {status}"


def check_firecrawl() -> tuple[bool, str]:
    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        return False, "FIRECRAWL_API_KEY is empty"
    url = "https://api.firecrawl.dev/v1/usage"
    headers = {"Authorization": f"Bearer {api_key}"}
    status, _ = http_request(url, headers=headers)
    return status == 200, f"HTTP {status}"


CHECKS = {
    "OPENAI_API_KEY": check_openai,
    "SONNET_API_KEY": check_sonnet,
    "GEOAPIFY_API_KEY": check_geoapify,
    "GROK_API_KEY": check_grok,
    "GOOGLE_API_KEY": check_gemini,
    "HUNTER_API_KEY": check_hunter,
    "FIRECRAWL_API_KEY": check_firecrawl,
}


# ── Atlassian integration checks ─────────────────────────────

ATLASSIAN_KEYS = {
    "ATLASSIAN_BASE_URL": "Base URL",
    "ATLASSIAN_USERNAME": "Username",
    "ATLASSIAN_API_TOKEN": "API token",
}

CONFLUENCE_KEYS = {
    **ATLASSIAN_KEYS,
    "CONFLUENCE_SPACE_KEY": "Space key",
}


JIRA_KEYS = {
    **ATLASSIAN_KEYS,
    "JIRA_PROJECT_KEY": "Project key",
}


def check_confluence() -> tuple[bool, str]:
    """Validate Confluence credentials by fetching the target space.

    Requires ``ATLASSIAN_BASE_URL``, ``ATLASSIAN_USERNAME``,
    ``ATLASSIAN_API_TOKEN``, and ``CONFLUENCE_SPACE_KEY``.  Sends a
    ``GET /rest/api/space/{key}`` request to verify the credentials
    can access the configured space.

    Returns:
        ``(True, "HTTP 200")`` on success, or ``(False, detail)`` with
        the reason for failure.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "").rstrip("/")
    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    missing = [
        k for k, v in {
            "ATLASSIAN_BASE_URL": base_url,
            "CONFLUENCE_SPACE_KEY": space_key,
            "ATLASSIAN_USERNAME": username,
            "ATLASSIAN_API_TOKEN": api_token,
        }.items() if not v
    ]
    if missing:
        return False, f"Missing: {', '.join(missing)}"

    import base64

    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded}"

    url = f"{base_url}/rest/api/space/{space_key}"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
    }

    status, _ = http_request(url, headers=headers)
    return status == 200, f"HTTP {status}"


def check_jira() -> tuple[bool, str]:
    """Validate Jira credentials by fetching the target project.

    Requires ``ATLASSIAN_BASE_URL``, ``ATLASSIAN_USERNAME``,
    ``ATLASSIAN_API_TOKEN``, and ``JIRA_PROJECT_KEY``.  Sends a
    ``GET /rest/api/3/project/{key}`` request to verify the
    credentials can access the configured project.

    Returns:
        ``(True, "HTTP 200")`` on success, or ``(False, detail)`` with
        the reason for failure.
    """
    base_url = os.environ.get("ATLASSIAN_BASE_URL", "").rstrip("/")
    project_key = os.environ.get("JIRA_PROJECT_KEY", "")
    username = os.environ.get("ATLASSIAN_USERNAME", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    missing = [
        k for k, v in {
            "ATLASSIAN_BASE_URL": base_url,
            "JIRA_PROJECT_KEY": project_key,
            "ATLASSIAN_USERNAME": username,
            "ATLASSIAN_API_TOKEN": api_token,
        }.items() if not v
    ]
    if missing:
        return False, f"Missing: {', '.join(missing)}"

    import base64

    credentials = f"{username}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded}"

    url = f"{base_url}/rest/api/3/project/{project_key}"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
    }

    status, _ = http_request(url, headers=headers)
    return status == 200, f"HTTP {status}"


ATLASSIAN_CHECKS = {
    "Confluence": check_confluence,
    "Jira": check_jira,
}


def check_mongodb() -> tuple[bool, str]:
    mongo_uri = os.environ.get("MONGODB_URI", "").strip()
    mongo_db = os.environ.get("MONGODB_DB", "").strip() or "ideas"
    if not mongo_uri:
        return False, "MONGODB_URI is empty"

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        return False, f"MongoDB connection error: {exc}"
    finally:
        try:
            client.close()
        except Exception:
            pass

    return True, "MongoDB ping ok"


def run_checks() -> int:
    load_env_file(ENV_FILE)
    failures = []

    print("Preflight: validating API keys")
    for key, label in API_KEYS.items():
        value = os.environ.get(key, "")
        print(f"- {label}: {mask_value(value)}")

    for key, check in CHECKS.items():
        label = API_KEYS[key]
        try:
            ok, detail = check()
        except urllib.error.HTTPError as exc:
            ok = False
            detail = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            ok = False
            detail = f"Network error: {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail = f"Unexpected error: {exc}"

        status = "OK" if ok else "FAIL"
        print(f"{status}: {label} ({detail})")
        if not ok:
            failures.append(label)

    if failures:
        print("\nPreflight failed for:")
        for label in failures:
            print(f"- {label}")
        return 1

    ok, detail = check_mongodb()
    status = "OK" if ok else "FAIL"
    print(f"{status}: MongoDB ({detail})")
    if not ok:
        return 1

    # ── Optional Atlassian integrations ───────────────────────
    atlassian_warnings: list[str] = []
    print("\nPreflight: validating Atlassian integrations (optional)")

    for label, check in ATLASSIAN_CHECKS.items():
        try:
            ok, detail = check()
        except urllib.error.HTTPError as exc:
            ok = False
            detail = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            ok = False
            detail = f"Network error: {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            ok = False
            detail = f"Unexpected error: {exc}"

        status = "OK" if ok else "WARN"
        print(f"{status}: {label} ({detail})")
        if not ok:
            atlassian_warnings.append(label)

    if atlassian_warnings:
        print("\nAtlassian warnings (non-blocking):")
        for label in atlassian_warnings:
            print(f"- {label}")

    print("\nPreflight passed. All API keys responded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(run_checks())
