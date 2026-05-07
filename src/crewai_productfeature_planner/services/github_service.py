"""GitHub integration service.

Handles OAuth flow, repo cloning, and Coding Agent orchestration.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading

from crewai import Crew, Task

from crewai_productfeature_planner.agents.coding_agent import (
    create_coding_agent,
    get_task_configs,
)
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.code_repos import (
    set_analysis_result,
    update_code_repo,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def get_oauth_client_id() -> str | None:
    return os.environ.get("GITHUB_OAUTH_CLIENT_ID")


def get_oauth_client_secret() -> str | None:
    return os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")


def get_kb_pat() -> str | None:
    """Get the PAT for pushing to the knowledge base repo."""
    return os.environ.get("GITHUB_KB_PAT")


def build_oauth_url(*, project_id: str, redirect_uri: str) -> str | None:
    """Build the GitHub OAuth authorization URL.

    Args:
        project_id: Project ID (passed as state for callback routing).
        redirect_uri: The callback URL to redirect to after authorization.

    Returns:
        The authorization URL, or None if client ID is not configured.
    """
    client_id = get_oauth_client_id()
    if not client_id:
        return None

    from urllib.parse import urlencode

    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "repo read:org",
        "state": project_id,
    })
    return f"https://github.com/login/oauth/authorize?{params}"


async def exchange_code_for_token(code: str) -> dict | None:
    """Exchange an OAuth authorization code for an access token.

    Returns dict with access_token, token_type, scope or None on failure.
    """
    client_id = get_oauth_client_id()
    client_secret = get_oauth_client_secret()
    if not client_id or not client_secret:
        logger.error("[GitHub] OAuth credentials not configured")
        return None

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "access_token" in data:
                    return data
                logger.error("[GitHub] OAuth token exchange failed: %s", data.get("error"))
            else:
                logger.error("[GitHub] OAuth HTTP %d", resp.status_code)
    except Exception as exc:
        logger.error("[GitHub] OAuth exchange error: %s", exc, exc_info=True)
    return None


def _shallow_clone(repo_url: str, token: str | None = None) -> str | None:
    """Shallow clone a repo to a temp directory.

    Returns the temp directory path, or None on failure.
    """
    tmp_dir = tempfile.mkdtemp(prefix="c9s-repo-")
    clone_url = repo_url
    if token and "github.com" in repo_url:
        # Insert token for private repos
        clone_url = repo_url.replace("https://", f"https://x-access-token:{token}@")

    try:
        subprocess.run(
            ["git", "clone", "--depth=1", "--single-branch", clone_url, tmp_dir],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        return tmp_dir
    except (subprocess.SubprocessError, OSError) as exc:
        logger.error("[GitHub] Clone failed: %s", exc, exc_info=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None


def _get_file_tree(repo_dir: str, max_depth: int = 3) -> str:
    """Get a file tree representation of the cloned repo."""
    lines = []
    import pathlib

    root = pathlib.Path(repo_dir)
    for item in sorted(root.rglob("*")):
        rel = item.relative_to(root)
        # Skip hidden dirs and common noise
        parts = rel.parts
        if any(p.startswith(".") for p in parts):
            continue
        if any(p in ("node_modules", "__pycache__", ".git", "venv", ".venv") for p in parts):
            continue
        if len(parts) > max_depth:
            continue
        indent = "  " * (len(parts) - 1)
        name = parts[-1] + ("/" if item.is_dir() else "")
        lines.append(f"{indent}{name}")
        if len(lines) > 200:
            lines.append("  ... (truncated)")
            break
    return "\n".join(lines)


def _read_key_files(repo_dir: str) -> str:
    """Read key files from the repo for analysis."""
    import pathlib

    key_patterns = [
        "README.md", "readme.md", "README.rst",
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "Makefile", "CMakeLists.txt",
    ]
    root = pathlib.Path(repo_dir)
    content_parts = []
    total_chars = 0
    max_chars = 30000

    for pattern in key_patterns:
        for f in root.glob(pattern):
            if total_chars >= max_chars:
                break
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")[:5000]
                content_parts.append(f"=== {f.name} ===\n{text}\n")
                total_chars += len(text)
            except OSError:
                continue

    # Also look for main entry points
    entry_patterns = [
        "src/**/main.*", "app.*", "index.*", "server.*",
        "src/**/app.*", "cmd/**/*.go",
    ]
    for pattern in entry_patterns:
        for f in root.glob(pattern):
            if total_chars >= max_chars:
                break
            if f.is_file() and f.stat().st_size < 10000:
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")[:3000]
                    rel = f.relative_to(root)
                    content_parts.append(f"=== {rel} ===\n{text}\n")
                    total_chars += len(text)
                except OSError:
                    continue

    return "\n".join(content_parts) if content_parts else "(no key files found)"


def _parse_json_output(raw: str) -> dict | None:
    """Parse JSON from agent output."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_kb_path(
    tenant_slug: str,
    project_slug: str,
    repo_slug: str,
) -> str:
    """Build the knowledge base repo path following multi-tenancy convention."""
    return f"enterprises/{tenant_slug}/projects/{project_slug}/repos/{repo_slug}/"


def analyze_repo(
    *,
    repo_id: str,
    project_id: str,
    repo_url: str,
    repo_name: str,
    repo_owner: str,
    project_slug: str,
    tenant_slug: str,
    github_token: str | None = None,
    tenant: TenantContext | None = None,
) -> dict | None:
    """Clone and analyze a repository using the Coding Agent.

    Args:
        repo_id: Code repo record ID.
        project_id: Project ID.
        repo_url: Full GitHub URL.
        repo_name: Repo name.
        repo_owner: Repo owner/org.
        project_slug: Slugified project name.
        tenant_slug: Slugified tenant name.
        github_token: OAuth token for private repos.
        tenant: Tenant context.

    Returns:
        Analysis dict or None on failure.
    """
    logger.info("[GitHub] Analyzing repo=%s url=%s", repo_id, repo_url)

    update_code_repo(
        repo_id=repo_id,
        project_id=project_id,
        updates={"status": "analyzing"},
        tenant=tenant,
    )

    # Clone
    repo_dir = _shallow_clone(repo_url, token=github_token)
    if not repo_dir:
        update_code_repo(
            repo_id=repo_id,
            project_id=project_id,
            updates={"status": "clone_failed"},
            tenant=tenant,
        )
        return None

    try:
        file_tree = _get_file_tree(repo_dir)
        key_files = _read_key_files(repo_dir)

        # Run Coding Agent
        agent = create_coding_agent()
        task_configs = get_task_configs()
        analyze_config = task_configs["analyze_repository_task"]

        task = Task(
            description=analyze_config["description"].format(
                repo_name=repo_name,
                repo_url=repo_url,
                repo_owner=repo_owner,
                file_tree=file_tree,
                key_files=key_files,
            ),
            expected_output=analyze_config["expected_output"],
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = crew.kickoff()

        parsed = _parse_json_output(str(result))
        if not parsed:
            logger.warning("[GitHub] Analysis parse failed repo=%s", repo_id)
            update_code_repo(
                repo_id=repo_id,
                project_id=project_id,
                updates={"status": "analysis_failed"},
                tenant=tenant,
            )
            return None

        # Build KB path
        repo_slug = repo_name.lower().replace(" ", "-").replace("/", "-")
        kb_path = _build_kb_path(tenant_slug, project_slug, repo_slug)

        set_analysis_result(
            repo_id=repo_id,
            project_id=project_id,
            analysis=parsed,
            kb_path=kb_path,
            tenant=tenant,
        )

        # Commit Obsidian-format docs to the KB repo
        if get_kb_pat():
            commit_to_kb_repo(
                repo_name=repo_name,
                repo_owner=repo_owner,
                repo_url=repo_url,
                project_slug=project_slug,
                tenant_slug=tenant_slug,
                analysis=parsed,
            )

        logger.info("[GitHub] Analysis complete repo=%s kb_path=%s", repo_id, kb_path)
        return parsed

    except Exception as exc:
        logger.error(
            "[GitHub] Analysis failed repo=%s: %s", repo_id, exc, exc_info=True
        )
        update_code_repo(
            repo_id=repo_id,
            project_id=project_id,
            updates={"status": "analysis_failed"},
            tenant=tenant,
        )
        return None
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)


def analyze_repo_async(
    *,
    repo_id: str,
    project_id: str,
    repo_url: str,
    repo_name: str,
    repo_owner: str,
    project_slug: str,
    tenant_slug: str,
    github_token: str | None = None,
    tenant: TenantContext | None = None,
) -> None:
    """Fire-and-forget repo analysis in a background thread."""
    thread = threading.Thread(
        target=analyze_repo,
        kwargs={
            "repo_id": repo_id,
            "project_id": project_id,
            "repo_url": repo_url,
            "repo_name": repo_name,
            "repo_owner": repo_owner,
            "project_slug": project_slug,
            "tenant_slug": tenant_slug,
            "github_token": github_token,
            "tenant": tenant,
        },
        name=f"analyze-{repo_id}",
        daemon=True,
    )
    thread.start()


# ── KB Repo Commit ───────────────────────────────────────────────


_KB_FILES_TEMPLATE = {
    "_index.md": (
        "---\n"
        "aliases: [{repo_name}]\n"
        "tags: [code-repo, {primary_language}]\n"
        "cssclasses: [kb-repo]\n"
        "---\n\n"
        "# {repo_owner}/{repo_name}\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| URL | {repo_url} |\n"
        "| Language | {primary_language} |\n"
        "| Frameworks | {frameworks} |\n"
        "| Last Analyzed | {analyzed_at} |\n\n"
        "## Pages\n\n"
        "- [[Architecture]]\n"
        "- [[APIs]]\n"
        "- [[Schema]]\n"
        "- [[Dependencies]]\n"
        "- [[Frameworks]]\n"
        "- [[ThirdParty]]\n"
        "- [[Queries]]\n"
    ),
    "Architecture.md": (
        "---\n"
        "aliases: [Architecture - {repo_name}]\n"
        "tags: [architecture, {primary_language}]\n"
        "---\n\n"
        "# Architecture\n\n"
        "{architecture_blurb}\n"
    ),
    "APIs.md": (
        "---\n"
        "aliases: [APIs - {repo_name}]\n"
        "tags: [api, endpoints]\n"
        "---\n\n"
        "# APIs\n\n"
        "Endpoint count: {api_endpoints_count}\n\n"
        "{api_details}\n"
    ),
    "Schema.md": (
        "---\n"
        "aliases: [Schema - {repo_name}]\n"
        "tags: [schema, database]\n"
        "---\n\n"
        "# Data Schema\n\n"
        "Entity count: {schema_entities_count}\n\n"
        "{schema_details}\n"
    ),
    "Dependencies.md": (
        "---\n"
        "aliases: [Dependencies - {repo_name}]\n"
        "tags: [dependencies]\n"
        "---\n\n"
        "# Dependencies\n\n"
        "Total: {dependencies_count}\n\n"
        "{dependencies_details}\n"
    ),
    "Frameworks.md": (
        "---\n"
        "aliases: [Frameworks - {repo_name}]\n"
        "tags: [frameworks, {primary_language}]\n"
        "---\n\n"
        "# Frameworks\n\n"
        "{frameworks_details}\n"
    ),
    "ThirdParty.md": (
        "---\n"
        "aliases: [Third Party - {repo_name}]\n"
        "tags: [third-party, integrations]\n"
        "---\n\n"
        "# Third-Party Services\n\n"
        "{third_party_details}\n"
    ),
    "Queries.md": (
        "---\n"
        "aliases: [Queries - {repo_name}]\n"
        "tags: [queries, database]\n"
        "---\n\n"
        "# Queries\n\n"
        "{queries_details}\n"
    ),
}


def commit_to_kb_repo(
    *,
    repo_name: str,
    repo_owner: str,
    repo_url: str,
    project_slug: str,
    tenant_slug: str,
    analysis: dict,
    commit_sha: str = "",
) -> bool:
    """Commit Obsidian-format analysis docs to the knowledge base repo.

    Uses the GitHub Contents API with GITHUB_KB_PAT to create/update files
    directly on the main branch.

    Args:
        repo_name: Repository name.
        repo_owner: Repository owner.
        repo_url: Full repo URL.
        project_slug: Slugified project name.
        tenant_slug: Slugified tenant name (default: cloudninesoftware).
        analysis: Parsed analysis dict from Coding Agent.
        commit_sha: Optional commit SHA for the commit message.

    Returns:
        True on success, False on failure.
    """
    kb_pat = get_kb_pat()
    if not kb_pat:
        logger.warning("[KB] No GITHUB_KB_PAT — skipping KB commit")
        return False

    kb_owner = os.environ.get("KB_REPO_OWNER", "AAXI-Agents")
    kb_repo = os.environ.get("KB_REPO_NAME", "c9s_agentic_knowledgebase")
    kb_branch = os.environ.get("KB_REPO_BRANCH", "main")

    repo_slug = repo_name.lower().replace(" ", "-").replace("/", "-")
    base_path = f"enterprises/{tenant_slug}/projects/{project_slug}/repos/{repo_slug}"

    # Extract analysis fields with safe defaults
    primary_language = analysis.get("primary_language", "unknown")
    frameworks = ", ".join(analysis.get("frameworks", []))
    architecture_blurb = analysis.get("architecture_blurb", "(not available)")
    api_endpoints_count = analysis.get("api_endpoints_count", 0)
    schema_entities_count = analysis.get("schema_entities_count", 0)
    dependencies_count = analysis.get("dependencies_count", 0)

    # Detailed sections (may be strings or lists)
    api_details = _format_detail(analysis.get("api_details", ""))
    schema_details = _format_detail(analysis.get("schema_details", ""))
    dependencies_details = _format_detail(analysis.get("dependencies_details", ""))
    frameworks_details = _format_detail(analysis.get("frameworks_details", ""))
    third_party_details = _format_detail(analysis.get("third_party_details", ""))
    queries_details = _format_detail(analysis.get("queries_details", ""))

    from datetime import datetime, timezone
    analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    format_vars = {
        "repo_name": repo_name,
        "repo_owner": repo_owner,
        "repo_url": repo_url,
        "primary_language": primary_language,
        "frameworks": frameworks,
        "analyzed_at": analyzed_at,
        "architecture_blurb": architecture_blurb,
        "api_endpoints_count": api_endpoints_count,
        "schema_entities_count": schema_entities_count,
        "dependencies_count": dependencies_count,
        "api_details": api_details,
        "schema_details": schema_details,
        "dependencies_details": dependencies_details,
        "frameworks_details": frameworks_details,
        "third_party_details": third_party_details,
        "queries_details": queries_details,
    }

    sha_short = commit_sha[:7] if commit_sha else "latest"
    commit_msg = f"chore(kb): refresh {project_slug}/{repo_slug} @ {sha_short}"

    import base64
    import httpx

    headers = {
        "Authorization": f"token {kb_pat}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    success_count = 0
    for filename, template in _KB_FILES_TEMPLATE.items():
        content = template.format(**format_vars)
        file_path = f"{base_path}/{filename}"
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

        # Check if file exists (to get its SHA for update)
        existing_sha = _get_file_sha(
            kb_owner, kb_repo, file_path, kb_branch, headers
        )

        payload: dict = {
            "message": commit_msg,
            "content": encoded,
            "branch": kb_branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        url = f"https://api.github.com/repos/{kb_owner}/{kb_repo}/contents/{file_path}"
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.put(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    success_count += 1
                else:
                    logger.warning(
                        "[KB] Failed to commit %s: HTTP %d — %s",
                        file_path,
                        resp.status_code,
                        resp.text[:200],
                    )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[KB] Error committing %s: %s", file_path, exc, exc_info=True
            )

    logger.info(
        "[KB] Committed %d/%d files to %s/%s at %s",
        success_count,
        len(_KB_FILES_TEMPLATE),
        kb_owner,
        kb_repo,
        base_path,
    )
    return success_count > 0


def _get_file_sha(
    owner: str, repo: str, path: str, branch: str, headers: dict
) -> str | None:
    """Get the SHA of an existing file (for updates)."""
    import httpx

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("sha")
    except Exception:  # noqa: BLE001
        pass
    return None


def _format_detail(value) -> str:
    """Format a detail field that may be a string or list."""
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value) if value else "(not available)"
