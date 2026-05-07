"""GitHub push webhook handler with debouncing.

POST /webhooks/github — Receives GitHub push events, debounces rapid
pushes (e.g. CI commits), and triggers Coding Agent re-analysis on
registered repos.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Request, status

from crewai_productfeature_planner.mongodb.code_repos import (
    find_repos_by_github_identity,
)
from crewai_productfeature_planner.mongodb.project_config import get_project
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.services.github_service import analyze_repo_async

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# ── Configuration ────────────────────────────────────────────────

_GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

# Debounce window: ignore re-analysis if last analysis was within this
# many seconds (prevents rapid re-triggers from burst pushes).
_DEBOUNCE_SECONDS = int(os.environ.get("GITHUB_WEBHOOK_DEBOUNCE_SECONDS", "300"))

# In-memory debounce tracker: repo_id → last trigger timestamp.
# This is sufficient for single-instance deployments; for multi-instance
# deploy, replace with Redis TTL key.
_debounce_tracker: dict[str, float] = {}


# ── Helpers ──────────────────────────────────────────────────────


def _verify_github_signature(payload: bytes, signature: str | None) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    GitHub sends the signature as 'sha256=<hex>'.
    """
    if not _GITHUB_WEBHOOK_SECRET:
        # No secret configured — skip verification (dev mode).
        return True
    if not signature:
        return False
    if signature.startswith("sha256="):
        signature = signature[len("sha256="):]
    expected = hmac.HMAC(
        _GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _is_debounced(repo_id: str) -> bool:
    """Check if a repo was recently triggered and should be skipped."""
    last_trigger = _debounce_tracker.get(repo_id)
    if last_trigger is None:
        return False
    return (time.time() - last_trigger) < _DEBOUNCE_SECONDS


def _mark_triggered(repo_id: str) -> None:
    """Record that a repo analysis was triggered now."""
    _debounce_tracker[repo_id] = time.time()


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


# ── Endpoint ─────────────────────────────────────────────────────


@router.post(
    "/github",
    status_code=status.HTTP_200_OK,
    summary="GitHub push webhook receiver",
    description=(
        "Receives GitHub push events. Looks up registered repos by "
        "owner/name and triggers Coding Agent re-analysis with debouncing."
    ),
)
async def handle_github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(
        default=None, alias="x-hub-signature-256"
    ),
    x_github_event: str | None = Header(default=None, alias="x-github-event"),
):
    """Process GitHub webhook push event."""
    body = await request.body()

    # Verify webhook signature
    if not _verify_github_signature(body, x_hub_signature_256):
        logger.warning("[GitHubWebhook] Invalid signature — rejecting")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Only process push events
    if x_github_event != "push":
        return {"status": "ignored", "reason": f"Unhandled event: {x_github_event}"}

    payload: dict[str, Any] = await request.json()

    # Extract repo info from payload
    repo_info = payload.get("repository", {})
    repo_full_name = repo_info.get("full_name", "")
    if "/" not in repo_full_name:
        return {"status": "ignored", "reason": "Missing repository.full_name"}

    owner, name = repo_full_name.split("/", 1)
    ref = payload.get("ref", "")
    default_branch = repo_info.get("default_branch", "main")

    # Only trigger on pushes to the default branch
    if ref != f"refs/heads/{default_branch}":
        logger.debug(
            "[GitHubWebhook] Ignoring push to non-default branch ref=%s repo=%s",
            ref, repo_full_name,
        )
        return {"status": "ignored", "reason": f"Push to non-default branch: {ref}"}

    # Look up registered repos matching this GitHub repo
    repos = find_repos_by_github_identity(owner=owner, name=name)
    if not repos:
        logger.debug("[GitHubWebhook] No registered repos for %s", repo_full_name)
        return {"status": "ignored", "reason": "No registered repos match"}

    triggered = []
    debounced = []

    for repo in repos:
        repo_id = repo["repo_id"]
        project_id = repo["project_id"]

        # Debounce check
        if _is_debounced(repo_id):
            debounced.append(repo_id)
            logger.debug(
                "[GitHubWebhook] Debounced repo=%s (within %ds window)",
                repo_id, _DEBOUNCE_SECONDS,
            )
            continue

        # Resolve project for token and slug
        project = get_project(project_id=project_id)
        if not project:
            logger.warning(
                "[GitHubWebhook] Project not found for repo=%s project=%s",
                repo_id, project_id,
            )
            continue

        project_slug = _slugify(project.get("name", project_id))
        tenant_slug = _slugify(
            project.get("enterprise_id", "")
            or project.get("organization_id", "default")
        )
        github_token = project.get("github_token")

        # Trigger re-analysis
        analyze_repo_async(
            repo_id=repo_id,
            project_id=project_id,
            repo_url=repo["url"],
            repo_name=name,
            repo_owner=owner,
            project_slug=project_slug,
            tenant_slug=tenant_slug,
            github_token=github_token,
            tenant=None,
        )

        _mark_triggered(repo_id)
        triggered.append(repo_id)

    logger.info(
        "[GitHubWebhook] Push %s — triggered=%d debounced=%d",
        repo_full_name, len(triggered), len(debounced),
    )
    return {
        "status": "processed",
        "triggered": triggered,
        "debounced": debounced,
    }
