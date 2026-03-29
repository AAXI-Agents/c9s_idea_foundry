"""Project knowledge base builder.

Generates and maintains an Obsidian-style knowledge base under
``projects/`` that agents can read for historical context.

Structure::

    projects/
        {project_name}/
            {project_name}.md          ← Project overview (config, memory, tools)
            ideas/
                {idea_title}.md        ← Completed idea pages (PRD in Obsidian format)

Functions:
    - ``generate_project_page`` — Create/update the project overview page
    - ``generate_idea_page``    — Create a completed-idea page from a workingIdeas doc
    - ``load_completed_ideas_context`` — Load all completed idea summaries for agent backstory
    - ``sync_project_knowledge`` — Ensure project folder + overview page exist
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Root directory for the project knowledge base.
_PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "projects"


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_dirname(name: str) -> str:
    """Convert a project/idea name into a filesystem-safe directory name.

    Lowercases, replaces non-alphanum/space with hyphens, collapses
    runs of hyphens, strips leading/trailing hyphens.
    """
    # Normalize unicode, lowercase
    s = unicodedata.normalize("NFKD", name).lower()
    # Replace non-alphanum (except spaces/hyphens) with hyphen
    s = re.sub(r"[^a-z0-9\s-]", "-", s)
    # Collapse whitespace + hyphens into single hyphen
    s = re.sub(r"[\s-]+", "-", s).strip("-")
    return s or "unnamed"


def _safe_filename(name: str) -> str:
    """Convert an idea title into a safe markdown filename (without .md)."""
    return _safe_dirname(name)


def _truncate(text: str, limit: int = 500) -> str:
    """Truncate text to *limit* characters with ellipsis."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _idea_title_from_doc(doc: dict[str, Any]) -> str:
    """Extract a clean title from a workingIdeas document."""
    idea = doc.get("idea") or doc.get("finalized_idea") or ""
    # Use first line (often the title/headline)
    first_line = idea.strip().split("\n")[0].strip()
    # Strip markdown heading markers
    first_line = re.sub(r"^#+\s*", "", first_line)
    # Truncate very long titles
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."
    return first_line or "Untitled Idea"


# ── Project Overview Page ────────────────────────────────────────────


def generate_project_page(
    project_config: dict[str, Any],
    project_memory: dict[str, Any] | None = None,
) -> Path:
    """Create or overwrite the project overview markdown page.

    Generates ``projects/{name}/{name}.md`` with config, memory, tools,
    and links to idea pages.

    Returns:
        Path to the generated file.
    """
    name = project_config.get("name", "Unnamed Project")
    project_id = project_config.get("project_id", "")
    dirname = _safe_dirname(name)
    project_dir = _PROJECTS_ROOT / dirname
    project_dir.mkdir(parents=True, exist_ok=True)

    # Also ensure ideas/ subdirectory exists
    (project_dir / "ideas").mkdir(exist_ok=True)

    parts: list[str] = []

    # Header
    parts.append(f"# {name}\n")
    parts.append(f"> Project ID: `{project_id}`\n")
    parts.append(f"> Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    # Configuration
    parts.append("## Configuration\n")
    config_items = [
        ("Confluence Space", project_config.get("confluence_space_key", "")),
        ("Jira Project", project_config.get("jira_project_key", "")),
        ("Confluence Parent ID", project_config.get("confluence_parent_id", "")),
        ("Figma Team ID", project_config.get("figma_team_id", "")),
    ]
    for label, value in config_items:
        if value:
            parts.append(f"- **{label}**: {value}")
    parts.append("")

    # Reference URLs
    ref_urls = project_config.get("reference_urls", [])
    if ref_urls:
        parts.append("## Reference URLs\n")
        for url in ref_urls:
            parts.append(f"- {url}")
        parts.append("")

    # Slack File References
    slack_refs = project_config.get("slack_file_refs", [])
    if slack_refs:
        parts.append("## Uploaded Documents\n")
        for ref in slack_refs:
            parts.append(f"- **{ref.get('name', 'Unknown')}** (uploaded {ref.get('uploaded_at', 'N/A')})")
        parts.append("")

    # Project Memory
    if project_memory:
        idea_entries = project_memory.get("idea_iteration", [])
        knowledge_entries = project_memory.get("knowledge", [])
        tools_entries = project_memory.get("tools", [])

        if idea_entries:
            parts.append("## Idea-Iteration Guardrails\n")
            for entry in idea_entries:
                parts.append(f"- {entry.get('content', '')}")
            parts.append("")

        if knowledge_entries:
            parts.append("## Knowledge References\n")
            for entry in knowledge_entries:
                kind = entry.get("kind", "")
                content = entry.get("content", "")
                if kind:
                    parts.append(f"- [{kind}] {content}")
                else:
                    parts.append(f"- {content}")
            parts.append("")

        if tools_entries:
            parts.append("## Technology Stack\n")
            for entry in tools_entries:
                parts.append(f"- {entry.get('content', '')}")
            parts.append("")

    # Completed Ideas — list links to idea pages
    ideas_dir = project_dir / "ideas"
    idea_files = sorted(ideas_dir.glob("*.md"))
    if idea_files:
        parts.append("## Completed Ideas\n")
        for f in idea_files:
            link_name = f.stem.replace("-", " ").title()
            parts.append(f"- [[ideas/{f.name}|{link_name}]]")
        parts.append("")

    content = "\n".join(parts)
    filepath = project_dir / f"{dirname}.md"
    filepath.write_text(content, encoding="utf-8")
    logger.info(
        "[ProjectKnowledge] Generated project page: %s (%d bytes)",
        filepath, len(content),
    )
    return filepath


# ── Completed Idea Page ──────────────────────────────────────────────


def generate_idea_page(
    doc: dict[str, Any],
    project_name: str,
) -> Path | None:
    """Create a completed-idea page from a workingIdeas MongoDB document.

    The page is formatted using Obsidian conventions:
    - YAML frontmatter with metadata
    - Wikilinks back to the project page
    - PRD sections restructured as Obsidian headings

    Returns:
        Path to the generated file, or ``None`` on error.
    """
    from crewai_productfeature_planner.apis.prd.models import SECTION_ORDER
    from crewai_productfeature_planner.components.document import (
        sanitize_section_content,
        strip_iteration_tags,
    )

    run_id = doc.get("run_id", "unknown")
    title = _idea_title_from_doc(doc)
    dirname = _safe_dirname(project_name)
    ideas_dir = _PROJECTS_ROOT / dirname / "ideas"
    ideas_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename(title)
    filepath = ideas_dir / f"{filename}.md"

    parts: list[str] = []

    # YAML frontmatter
    status = doc.get("status", "unknown")
    created_at = doc.get("created_at", "")
    completed_at = doc.get("completed_at", "")
    parts.append("---")
    parts.append(f"run_id: {run_id}")
    parts.append(f"status: {status}")
    parts.append(f"created: {created_at}")
    parts.append(f"completed: {completed_at}")
    parts.append(f"project: \"[[{dirname}]]\"")
    parts.append("tags: [idea, prd, completed]")
    parts.append("---\n")

    # Title
    parts.append(f"# {title}\n")
    parts.append(f"> Part of [[{dirname}/{dirname}|{project_name}]] project\n")

    # Original Idea
    original = doc.get("idea") or ""
    finalized = doc.get("finalized_idea") or ""
    if original and finalized and original != finalized:
        parts.append("## Original Idea\n")
        parts.append(f"{original.strip()}\n")
        parts.append("## Refined Idea\n")
        parts.append(f"{finalized.strip()}\n")
    elif finalized:
        parts.append("## Idea\n")
        parts.append(f"{finalized.strip()}\n")
    elif original:
        parts.append("## Idea\n")
        parts.append(f"{original.strip()}\n")

    # Executive Summary
    raw_exec = doc.get("executive_summary", [])
    if isinstance(raw_exec, list) and raw_exec:
        latest = raw_exec[-1]
        if isinstance(latest, dict) and latest.get("content"):
            clean = sanitize_section_content(latest["content"], "executive_summary")
            clean = strip_iteration_tags(clean)
            parts.append("## Executive Summary\n")
            parts.append(f"{clean.strip()}\n")

    # Executive Product Summary (CEO review)
    eps = doc.get("section", {}).get("executive_product_summary", [])
    if isinstance(eps, list) and eps:
        latest = eps[-1]
        if isinstance(latest, dict) and latest.get("content"):
            clean = sanitize_section_content(latest["content"], "executive_product_summary")
            clean = strip_iteration_tags(clean)
            parts.append("## Executive Product Summary\n")
            parts.append(f"{clean.strip()}\n")

    # Engineering Plan
    eng_plan = doc.get("section", {}).get("engineering_plan", [])
    if isinstance(eng_plan, list) and eng_plan:
        latest = eng_plan[-1]
        if isinstance(latest, dict) and latest.get("content"):
            clean = sanitize_section_content(latest["content"], "engineering_plan")
            clean = strip_iteration_tags(clean)
            parts.append("## Engineering Plan\n")
            parts.append(f"{clean.strip()}\n")

    # Regular PRD Sections
    section_obj = doc.get("section", {})
    skip_keys = {"executive_summary", "executive_product_summary", "engineering_plan"}
    if isinstance(section_obj, dict):
        for key, section_title in SECTION_ORDER:
            if key in skip_keys:
                continue
            iterations = section_obj.get(key, [])
            if isinstance(iterations, list) and iterations:
                latest = iterations[-1]
                if isinstance(latest, dict) and latest.get("content"):
                    clean = sanitize_section_content(latest["content"], key)
                    clean = strip_iteration_tags(clean)
                    parts.append(f"## {section_title}\n")
                    parts.append(f"{clean.strip()}\n")

    # UX Design appendix
    figma_url = doc.get("figma_design_url", "")
    figma_prompt = doc.get("figma_design_prompt", "")
    ux_section = doc.get("section", {}).get("ux_design", [])
    ux_content = ""
    if isinstance(ux_section, list) and ux_section:
        latest = ux_section[-1]
        if isinstance(latest, dict):
            ux_content = latest.get("content") or ""

    if figma_url or figma_prompt or ux_content:
        parts.append("## UX Design\n")
        if figma_url:
            parts.append(f"**Figma Prototype:** [{figma_url}]({figma_url})\n")
        if figma_prompt:
            parts.append(f"{figma_prompt.strip()}\n")
        elif ux_content:
            parts.append(f"{ux_content.strip()}\n")

    # Delivery status
    confluence_url = doc.get("confluence_url", "")
    jira_phase = doc.get("jira_phase", "")
    if confluence_url or jira_phase:
        parts.append("## Delivery Status\n")
        if confluence_url:
            parts.append(f"- **Confluence:** [{confluence_url}]({confluence_url})")
        if jira_phase:
            parts.append(f"- **Jira Phase:** {jira_phase}")
        parts.append("")

    content = "\n".join(parts)
    filepath.write_text(content, encoding="utf-8")
    logger.info(
        "[ProjectKnowledge] Generated idea page: %s (%d bytes, run_id=%s)",
        filepath, len(content), run_id,
    )
    return filepath


# ── Agent Memory Context ─────────────────────────────────────────────


def load_completed_ideas_context(project_id: str) -> str:
    """Load summaries of all completed ideas for a project.

    Used to enrich agent backstory so agents understand what's been
    built and avoid duplicating existing ideas.

    Returns:
        A formatted context block, or empty string if no completed ideas.
    """
    if not project_id:
        return ""

    try:
        from crewai_productfeature_planner.mongodb.client import get_db

        docs = list(
            get_db()["workingIdeas"]
            .find(
                {"project_id": project_id, "status": "completed"},
                {
                    "run_id": 1,
                    "idea": 1,
                    "finalized_idea": 1,
                    "executive_summary": 1,
                    "completed_at": 1,
                    "_id": 0,
                },
            )
            .sort("completed_at", -1)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[ProjectKnowledge] Failed to load completed ideas for "
            "project_id=%s: %s",
            project_id, exc,
        )
        return ""

    if not docs:
        return ""

    lines: list[str] = [
        "",
        "── Completed Ideas (avoid duplication) ─────────────",
        f"This project has {len(docs)} completed idea(s). Review them",
        "to understand what already exists and create synergy with new work:",
        "",
    ]

    for idx, doc in enumerate(docs, 1):
        title = _idea_title_from_doc(doc)
        completed = doc.get("completed_at", "N/A")

        # Get executive summary (just the latest content, truncated)
        exec_summary = ""
        raw_exec = doc.get("executive_summary", [])
        if isinstance(raw_exec, list) and raw_exec:
            latest = raw_exec[-1]
            if isinstance(latest, dict):
                exec_summary = latest.get("content", "")

        lines.append(f"{idx}. **{title}** (completed: {completed})")
        if exec_summary:
            lines.append(f"   Summary: {_truncate(exec_summary, 300)}")
        lines.append("")

    context = "\n".join(lines)
    logger.info(
        "[ProjectKnowledge] Loaded %d completed idea(s) for project_id=%s "
        "(%d chars)",
        len(docs), project_id, len(context),
    )
    return context


# ── Sync / Orchestration ────────────────────────────────────────────


def sync_project_knowledge(project_id: str) -> Path | None:
    """Ensure the project folder and overview page exist.

    Loads project config + memory from MongoDB, generates the overview
    page, and returns its path.  Safe to call repeatedly (overwrites).

    Returns:
        Path to the project overview page, or ``None`` on error.
    """
    try:
        from crewai_productfeature_planner.mongodb.project_config import (
            get_project,
        )
        from crewai_productfeature_planner.mongodb.project_memory import (
            get_project_memory,
        )

        config = get_project(project_id)
        if not config:
            logger.warning(
                "[ProjectKnowledge] No project config for project_id=%s",
                project_id,
            )
            return None

        memory = get_project_memory(project_id)
        return generate_project_page(config, memory)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[ProjectKnowledge] Failed to sync project knowledge for "
            "project_id=%s: %s",
            project_id, exc,
        )
        return None


def sync_completed_idea(run_id: str) -> Path | None:
    """Generate the idea page for a completed run and refresh the project page.

    Called after ``mark_completed()`` to persist the completed idea
    into the project knowledge base.

    Returns:
        Path to the generated idea page, or ``None`` on error.
    """
    try:
        from crewai_productfeature_planner.mongodb.client import get_db
        from crewai_productfeature_planner.mongodb.project_config import (
            get_project,
        )
        from crewai_productfeature_planner.mongodb.project_memory import (
            get_project_memory,
        )

        doc = get_db()["workingIdeas"].find_one(
            {"run_id": run_id},
            {"_id": 0},
        )
        if not doc:
            logger.warning(
                "[ProjectKnowledge] No workingIdeas doc for run_id=%s",
                run_id,
            )
            return None

        project_id = doc.get("project_id")
        if not project_id:
            logger.debug(
                "[ProjectKnowledge] No project_id for run_id=%s — skipping",
                run_id,
            )
            return None

        config = get_project(project_id)
        if not config:
            logger.warning(
                "[ProjectKnowledge] No project config for project_id=%s",
                project_id,
            )
            return None

        project_name = config.get("name", "Unnamed Project")

        # Generate the idea page
        idea_path = generate_idea_page(doc, project_name)

        # Refresh the project overview page (includes updated idea list)
        memory = get_project_memory(project_id)
        generate_project_page(config, memory)

        return idea_path
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[ProjectKnowledge] Failed to sync completed idea for "
            "run_id=%s: %s",
            run_id, exc,
        )
        return None


def archive_idea_knowledge(run_id: str) -> Path | None:
    """Move the idea knowledge page to an archive folder.

    Moves ``projects/{name}/ideas/{title}.md`` →
    ``projects/{name}/archives/{YYYY}/{MM}/{DD}/{title}.md``
    and refreshes the project overview page.

    Returns:
        Path to the archived file, or ``None`` if no file existed.
    """
    try:
        from crewai_productfeature_planner.mongodb.client import get_db
        from crewai_productfeature_planner.mongodb.project_config import get_project
        from crewai_productfeature_planner.mongodb.project_memory import (
            get_project_memory,
        )

        doc = get_db()["workingIdeas"].find_one(
            {"run_id": run_id},
            {"_id": 0},
        )
        if not doc:
            logger.debug(
                "[ProjectKnowledge] No doc for run_id=%s — nothing to archive",
                run_id,
            )
            return None

        project_id = doc.get("project_id")
        if not project_id:
            return None

        config = get_project(project_id)
        if not config:
            return None

        project_name = config.get("name", "Unnamed Project")
        dirname = _safe_dirname(project_name)
        title = _idea_title_from_doc(doc)
        filename = _safe_filename(title)

        ideas_dir = _PROJECTS_ROOT / dirname / "ideas"
        source = ideas_dir / f"{filename}.md"

        if not source.exists():
            logger.debug(
                "[ProjectKnowledge] No idea file to archive: %s", source,
            )
            return None

        # Build archive path: projects/{name}/archives/{YYYY}/{MM}/{DD}/
        now = datetime.now(timezone.utc)
        archive_dir = (
            _PROJECTS_ROOT / dirname / "archives"
            / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        )
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / f"{filename}.md"

        source.rename(dest)
        logger.info(
            "[ProjectKnowledge] Archived idea file: %s → %s",
            source, dest,
        )

        # Refresh the project overview page (idea list updated)
        memory = get_project_memory(project_id)
        generate_project_page(config, memory)

        return dest
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[ProjectKnowledge] Failed to archive idea knowledge for "
            "run_id=%s: %s",
            run_id, exc,
        )
        return None
