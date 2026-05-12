"""Code Repos + GitHub OAuth REST API.

Endpoints for:
- GitHub OAuth connect/disconnect
- Register/list/detail/delete repos
- Trigger Coding Agent analysis
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.mongodb.code_repos import (
    count_code_repos,
    create_code_repo,
    delete_code_repo,
    get_code_repo,
    list_code_repos,
)
from crewai_productfeature_planner.mongodb.project_config import get_project
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.services.field_encryption import (
    decrypt_value,
    encrypt_value,
)
from crewai_productfeature_planner.services.github_service import (
    analyze_repo_async,
    build_oauth_url,
    exchange_code_for_token,
)

logger = get_logger(__name__)

router = APIRouter(
    tags=["Code Repos"],
    dependencies=[Depends(require_sso_user)],
)


# ── Response Models ──────────────────────────────────────────────


class GithubConnectResponse(BaseModel):
    auth_url: str = Field(..., description="GitHub OAuth authorization URL")


class CodeRepoResponse(BaseModel):
    """Repo response matching frontend Repo type."""

    repo_id: str
    project_id: str
    url: str
    name: str
    status: str
    last_analyzed: str | None = None
    architecture_summary: str | None = None
    primary_language: str | None = None
    frameworks: list[str] = Field(default_factory=list)
    dependencies_count: int | None = None
    api_surface_count: int | None = None
    schema_entities_count: int | None = None
    kb_hub_link: str | None = None
    created_at: str


class CodeRepoListResponse(BaseModel):
    """Paginated list matching frontend RepoList type."""

    items: list[CodeRepoResponse]
    total: int


class RegisterRepoRequest(BaseModel):
    url: str = Field(..., description="Full GitHub repository URL")


class GithubCallbackResponse(BaseModel):
    project_id: str
    connected: bool


# Map internal MongoDB statuses to the frontend contract values.
# MongoDB keeps granular statuses (clone_failed, analysis_failed, analyzed)
# for debugging; the API returns the simplified set the frontend expects.
_STATUS_MAP: dict[str, str] = {
    "analyzed": "ready",
    "clone_failed": "failed",
    "analysis_failed": "failed",
}


def _doc_to_response(doc: dict) -> CodeRepoResponse:
    """Map MongoDB code_repo document to the frontend response shape.

    Flattens the nested `analysis` dict and renames fields to match
    the frontend Repo type contract.
    """
    raw_status = doc.get("status", "pending")
    analysis = doc.get("analysis") or {}
    return CodeRepoResponse(
        repo_id=doc["repo_id"],
        project_id=doc["project_id"],
        url=doc["url"],
        name=doc["name"],
        status=_STATUS_MAP.get(raw_status, raw_status),
        last_analyzed=doc.get("last_analyzed_at"),
        architecture_summary=analysis.get("architecture_summary"),
        primary_language=analysis.get("primary_language"),
        frameworks=analysis.get("frameworks") or [],
        dependencies_count=analysis.get("dependencies_count"),
        api_surface_count=analysis.get("api_surface_count"),
        schema_entities_count=analysis.get("schema_entities_count"),
        kb_hub_link=doc.get("kb_path"),
        created_at=doc.get("created_at", ""),
    )


# ── GitHub OAuth Endpoints ───────────────────────────────────────


@router.post(
    "/projects/{project_id}/github/connect",
    summary="Start GitHub OAuth flow",
    description="Returns a GitHub OAuth authorization URL. Redirect the user to it.",
    response_model=GithubConnectResponse,
    responses={503: {"description": "GitHub OAuth not configured."}},
)
async def github_connect(
    project_id: str,
    request: Request,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)

    # Verify project exists
    project = get_project(project_id=project_id, tenant=tenant)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/github/callback"

    auth_url = build_oauth_url(project_id=project_id, redirect_uri=redirect_uri)
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured. Set GITHUB_OAUTH_CLIENT_ID.",
        )

    logger.info("[CodeRepos] OAuth connect initiated project=%s user=%s", project_id, user.get("user_id"))
    return GithubConnectResponse(auth_url=auth_url)


@router.get(
    "/auth/github/callback",
    summary="GitHub OAuth callback",
    description="Handles the OAuth callback from GitHub. Exchanges code for token.",
    response_model=GithubCallbackResponse,
)
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="Project ID passed as state"),
    user: dict[str, Any] = Depends(require_sso_user),
):
    project_id = state
    token_data = await exchange_code_for_token(code)
    if not token_data:
        raise HTTPException(status_code=502, detail="GitHub token exchange failed.")

    # Store token encrypted at rest
    from crewai_productfeature_planner.mongodb.project_config import update_project

    tenant = TenantContext.from_user(user)
    update_project(
        project_id=project_id,
        updates={"github_token": encrypt_value(token_data["access_token"])},
        tenant=tenant,
    )

    logger.info("[CodeRepos] GitHub connected project=%s", project_id)
    return GithubCallbackResponse(project_id=project_id, connected=True)


@router.delete(
    "/projects/{project_id}/github",
    summary="Disconnect GitHub",
    description="Remove the stored GitHub OAuth token for a project.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Project not found."}},
)
async def github_disconnect(
    project_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)

    project = get_project(project_id=project_id, tenant=tenant)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    from crewai_productfeature_planner.mongodb.project_config import update_project

    update_project(
        project_id=project_id,
        updates={"github_token": None},
        tenant=tenant,
    )
    logger.info("[CodeRepos] GitHub disconnected project=%s", project_id)


# ── Code Repos CRUD ──────────────────────────────────────────────


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Parse owner and name from a GitHub URL.

    Returns (owner, name) or None if invalid.
    """
    pattern = r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
    match = re.match(pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


@router.post(
    "/projects/{project_id}/repos",
    summary="Register a repository",
    description="Register a GitHub repo and kick off Coding Agent analysis.",
    response_model=CodeRepoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Repo registered, analysis started."},
        400: {"description": "Invalid GitHub URL."},
    },
)
async def register_repo(
    project_id: str,
    body: RegisterRepoRequest,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    user_id = user.get("user_id", "")

    parsed = _parse_github_url(body.url)
    if not parsed:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub URL. Expected: https://github.com/{owner}/{repo}",
        )

    owner, name = parsed

    # Verify project exists
    project = get_project(project_id=project_id, tenant=tenant)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Create record
    doc = create_code_repo(
        project_id=project_id,
        url=body.url,
        name=name,
        owner=owner,
        created_by=user_id,
        tenant=tenant,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to register repo.")

    repo_id = doc["repo_id"]

    # Derive slugs for KB path
    project_slug = _slugify(project.get("name", project_id))
    tenant_slug = _slugify(
        user.get("enterprise_id", "") or user.get("organization_id", "default")
    )

    # Get GitHub token from project if available (decrypt from storage)
    raw_token = project.get("github_token")
    github_token = decrypt_value(raw_token) if raw_token else None

    # Kick off analysis
    analyze_repo_async(
        repo_id=repo_id,
        project_id=project_id,
        repo_url=body.url,
        repo_name=name,
        repo_owner=owner,
        project_slug=project_slug,
        tenant_slug=tenant_slug,
        github_token=github_token,
        tenant=tenant,
    )

    logger.info("[CodeRepos] Registered repo=%s project=%s url=%s", repo_id, project_id, body.url)
    return _doc_to_response(doc)


@router.get(
    "/projects/{project_id}/repos",
    summary="List code repos",
    description="List all registered code repos for a project with pagination.",
    response_model=CodeRepoListResponse,
)
async def list_repos(
    project_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    repos = list_code_repos(project_id=project_id, tenant=tenant, skip=skip, limit=limit)
    total = count_code_repos(project_id=project_id, tenant=tenant)
    items = [_doc_to_response(r) for r in repos]
    return CodeRepoListResponse(items=items, total=total)


@router.get(
    "/projects/{project_id}/repos/{repo_id}",
    summary="Get code repo detail",
    description="Get a single repo with its analysis summary and KB hub link.",
    response_model=CodeRepoResponse,
    responses={404: {"description": "Repo not found."}},
)
async def get_repo(
    project_id: str,
    repo_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    repo = get_code_repo(repo_id=repo_id, project_id=project_id, tenant=tenant)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found.")
    return _doc_to_response(repo)


@router.post(
    "/projects/{project_id}/repos/{repo_id}/analyze",
    summary="Re-run Coding Agent analysis",
    description="Re-analyze the repository with the Coding Agent.",
    response_model=CodeRepoResponse,
    responses={404: {"description": "Repo not found."}},
)
async def reanalyze_repo(
    project_id: str,
    repo_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)

    repo = get_code_repo(repo_id=repo_id, project_id=project_id, tenant=tenant)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found.")

    # Get project for token and slug
    project = get_project(project_id=project_id, tenant=tenant)
    project_slug = _slugify(project.get("name", project_id)) if project else project_id
    tenant_slug = _slugify(
        user.get("enterprise_id", "") or user.get("organization_id", "default")
    )
    raw_token = project.get("github_token") if project else None
    github_token = decrypt_value(raw_token) if raw_token else None

    analyze_repo_async(
        repo_id=repo_id,
        project_id=project_id,
        repo_url=repo["url"],
        repo_name=repo["name"],
        repo_owner=repo["owner"],
        project_slug=project_slug,
        tenant_slug=tenant_slug,
        github_token=github_token,
        tenant=tenant,
    )

    # Return updated repo with analyzing status
    repo["status"] = "analyzing"
    logger.info("[CodeRepos] Re-analysis triggered repo=%s", repo_id)
    return _doc_to_response(repo)


@router.delete(
    "/projects/{project_id}/repos/{repo_id}",
    summary="Delete a code repo",
    description="Remove a registered repo and its analysis record.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Repo not found."}},
)
async def delete_repo(
    project_id: str,
    repo_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)

    success = delete_code_repo(repo_id=repo_id, project_id=project_id, tenant=tenant)
    if not success:
        raise HTTPException(status_code=404, detail="Repo not found.")
    logger.info("[CodeRepos] Deleted repo=%s project=%s", repo_id, project_id)
