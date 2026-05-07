"""Build knowledge context for PRD flow agents.

Fetches the project's aggregated knowledge summary and code repo
architecture blurbs, then formats them into a structured text block
that can be prepended to the idea for agent consumption.

Budget: ≤4000 tokens (~16000 chars). If the combined context exceeds
this limit, bullet points and repo blurbs are truncated.
"""

from __future__ import annotations

from crewai_productfeature_planner.mongodb._tenant import TenantContext
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Approximate char budget (4000 tokens × ~4 chars/token)
_MAX_CONTEXT_CHARS = 16000
_SUMMARY_BUDGET = 10000  # chars reserved for unified summary + bullets
_REPOS_BUDGET = 6000  # chars reserved for repo architecture blurbs


def build_knowledge_context(
    project_id: str,
    *,
    tenant: TenantContext | None = None,
) -> str:
    """Build a structured knowledge context block for a project.

    Returns an empty string if no knowledge or repos exist, so callers
    can safely prepend without branching.

    Args:
        project_id: The project to fetch knowledge for.
        tenant: Tenant context for scoped queries.

    Returns:
        A formatted text block (may be empty).
    """
    if not project_id:
        return ""

    parts: list[str] = []

    # ── Knowledge summary ──
    summary_text = _fetch_knowledge_summary(project_id, tenant=tenant)
    if summary_text:
        parts.append(summary_text)

    # ── Code repo blurbs ──
    repos_text = _fetch_repo_blurbs(project_id, tenant=tenant)
    if repos_text:
        parts.append(repos_text)

    if not parts:
        logger.debug(
            "[KnowledgeContext] No knowledge context for project=%s",
            project_id,
        )
        return ""

    context = (
        "## Project Knowledge Context\n\n"
        "The following context was gathered from the project's uploaded "
        "knowledge documents and linked code repositories. Use this as "
        "background information when refining the idea and generating "
        "requirements.\n\n"
        + "\n\n".join(parts)
    )

    # Safety truncation
    if len(context) > _MAX_CONTEXT_CHARS:
        context = context[:_MAX_CONTEXT_CHARS] + "\n\n[...truncated]"
        logger.warning(
            "[KnowledgeContext] Context truncated to %d chars for project=%s",
            _MAX_CONTEXT_CHARS,
            project_id,
        )

    logger.info(
        "[KnowledgeContext] Built context for project=%s (%d chars)",
        project_id,
        len(context),
    )
    return context


def _fetch_knowledge_summary(
    project_id: str,
    *,
    tenant: TenantContext | None = None,
) -> str:
    """Fetch and format the unified knowledge summary."""
    try:
        from crewai_productfeature_planner.mongodb.knowledge_summaries import (
            get_knowledge_summary,
        )

        doc = get_knowledge_summary(project_id=project_id, tenant=tenant)
        if not doc:
            return ""

        unified = doc.get("unified_summary", "")
        bullets = doc.get("unified_bullets", [])
        contradictions = doc.get("contradictions", [])

        if not unified and not bullets:
            return ""

        lines = ["### Knowledge Summary\n"]

        if unified:
            summary = unified[:_SUMMARY_BUDGET]
            lines.append(summary)

        if bullets:
            lines.append("\n**Key Points:**")
            for bullet in bullets[:20]:  # Cap at 20 bullets
                lines.append(f"- {bullet}")

        if contradictions:
            lines.append("\n**Contradictions Detected:**")
            for c in contradictions[:5]:  # Cap at 5
                lines.append(
                    f"- {c.get('claim_a', '?')} vs {c.get('claim_b', '?')} "
                    f"(severity: {c.get('severity', 'unknown')})"
                )

        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[KnowledgeContext] Failed to fetch summary for project=%s: %s",
            project_id,
            exc,
        )
        return ""


def _fetch_repo_blurbs(
    project_id: str,
    *,
    tenant: TenantContext | None = None,
) -> str:
    """Fetch architecture blurbs from analyzed code repos."""
    try:
        from crewai_productfeature_planner.mongodb.code_repos import (
            list_code_repos,
        )

        repos = list_code_repos(project_id=project_id, tenant=tenant)
        if not repos:
            return ""

        # Only include repos that have completed analysis
        ready_repos = [
            r for r in repos
            if r.get("status") == "ready" and r.get("analysis")
        ]
        if not ready_repos:
            return ""

        lines = ["### Code Repository Context\n"]
        total_chars = 0

        for repo in ready_repos:
            analysis = repo.get("analysis", {})
            blurb = analysis.get("architecture_blurb", "")
            if not blurb:
                continue

            repo_header = f"**{repo.get('owner', '')}/{repo.get('name', '')}**"

            # Include key metadata
            meta_parts = []
            if analysis.get("primary_language"):
                meta_parts.append(f"Language: {analysis['primary_language']}")
            if analysis.get("frameworks"):
                meta_parts.append(
                    f"Frameworks: {', '.join(analysis['frameworks'][:5])}"
                )

            entry = f"{repo_header}\n"
            if meta_parts:
                entry += f"  {' | '.join(meta_parts)}\n"
            entry += f"  {blurb}\n"

            if total_chars + len(entry) > _REPOS_BUDGET:
                lines.append("\n[...additional repos truncated]")
                break

            lines.append(entry)
            total_chars += len(entry)

        if len(lines) <= 1:
            return ""  # Only header, no content

        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[KnowledgeContext] Failed to fetch repos for project=%s: %s",
            project_id,
            exc,
        )
        return ""
