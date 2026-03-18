"""PRD document assembly helpers.

Pure-data functions that reconstruct PRD markdown from raw MongoDB
``workingIdeas`` documents.  No I/O, no side-effects — safe to call
from any context (CLI, API, background threads).
"""

from __future__ import annotations

import json
import re

from crewai_productfeature_planner.apis.prd.models import SECTION_ORDER

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

_ITERATION_RE = re.compile(r"\s*\(Iteration\s+\d+\)", re.IGNORECASE)

# Keys that identify a full workingIdeas document dump
_DOCUMENT_DUMP_KEYS = {"run_id", "executive_summary", "section"}

# Regex to strip leading/trailing code fences (```json … ``` or ``` … ```)
_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$",
    re.DOTALL,
)


def strip_iteration_tags(text: str) -> str:
    """Remove ``(Iteration N)`` markers from *text*.

    The LLM sometimes embeds iteration metadata (e.g. ``(Iteration 3)``)
    into headings or body text.  These are internal loop artefacts and
    should never appear in the final PRD output.
    """
    return _ITERATION_RE.sub("", text)


def sanitize_section_content(content: str, section_key: str = "") -> str:
    """Strip accidental JSON document dumps from section content.

    The LLM occasionally wraps its output in a JSON code block that
    mirrors the full ``workingIdeas`` MongoDB document structure.
    When detected, we extract the *actual* section text from within the
    JSON and return it.  Non-JSON content passes through unchanged.

    Args:
        content: Raw section content (possibly a JSON code block).
        section_key: The section identifier (e.g. ``"executive_summary"``).
            Used to look up the correct sub-key when extracting from a
            JSON dump.  When empty, the function still strips JSON
            wrappers but cannot extract a specific section.

    Returns:
        The cleaned section content with iteration tags removed.
    """
    if not content:
        return content

    text = content.strip()

    # Unwrap code-fenced blocks: ```json\n{...}\n```
    fence_match = _CODE_FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Quick check: does the text look like JSON?
    if not text.startswith("{"):
        return strip_iteration_tags(content)

    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return strip_iteration_tags(content)

    if not isinstance(obj, dict):
        return strip_iteration_tags(content)

    # Detect workingIdeas document dumps
    if not _DOCUMENT_DUMP_KEYS.issubset(obj.keys()):
        return strip_iteration_tags(content)

    logger.warning(
        "[Sanitize] Detected JSON document dump in section '%s' "
        "(%d chars) — extracting clean content",
        section_key or "unknown",
        len(content),
    )

    # --- Extract the actual content from the JSON dump ---

    # For executive_summary: look in obj["executive_summary"][-1]["content"]
    if section_key == "executive_summary":
        raw_exec = obj.get("executive_summary", [])
        if isinstance(raw_exec, list) and raw_exec:
            latest = raw_exec[-1]
            if isinstance(latest, dict) and latest.get("content"):
                return strip_iteration_tags(latest["content"])

    # For regular sections: look in obj["section"][section_key][-1]["content"]
    if section_key:
        section_obj = obj.get("section", {})
        if isinstance(section_obj, dict):
            iterations = section_obj.get(section_key, [])
            if isinstance(iterations, list) and iterations:
                latest = iterations[-1]
                if isinstance(latest, dict) and latest.get("content"):
                    return strip_iteration_tags(latest["content"])

    # Fallback: if we detected a dump but couldn't extract content, try
    # the finalized_idea field (often the clean executive summary).
    if section_key == "executive_summary":
        finalized = obj.get("finalized_idea", "")
        if finalized:
            return strip_iteration_tags(finalized)

    # Last resort: return original content with iteration tags stripped.
    # This path should rarely be hit.
    logger.warning(
        "[Sanitize] Could not extract clean content for section '%s' "
        "from JSON dump — returning raw content",
        section_key or "unknown",
    )
    return strip_iteration_tags(content)


def assemble_prd_from_doc(doc: dict) -> str:
    """Reconstruct a PRD markdown string from a ``workingIdeas`` document.

    Mirrors the structure used by ``PRDDraft.assemble()`` but works
    directly from the raw MongoDB document.
    """
    run_id = doc.get("run_id", "unknown")
    logger.debug("[Document] Assembling PRD from doc run_id=%s", run_id)
    parts: list[str] = []

    # Executive summary — use the last iteration's content
    raw_exec = doc.get("executive_summary", [])
    if isinstance(raw_exec, list) and raw_exec:
        latest = raw_exec[-1]
        if isinstance(latest, dict) and latest.get("content"):
            clean = sanitize_section_content(latest["content"], "executive_summary")
            parts.append(f"## Executive Summary\n\n{clean}")

    # Regular sections
    section_obj = doc.get("section", {})
    if isinstance(section_obj, dict):
        for key, title in SECTION_ORDER:
            # Skip executive_summary — already handled above
            if key == "executive_summary":
                continue
            iterations = section_obj.get(key, [])
            if isinstance(iterations, list) and iterations:
                latest = iterations[-1]
                if isinstance(latest, dict) and latest.get("content"):
                    clean = sanitize_section_content(latest["content"], key)
                    parts.append(f"## {title}\n\n{clean}")

    if not parts:
        return ""

    return "# Product Requirements Document\n\n" + "\n\n---\n\n".join(parts)


def max_iteration_from_doc(doc: dict) -> int:
    """Return the maximum iteration number found in a workingIdeas document."""
    max_iter = 0
    # Executive summary iterations
    raw_exec = doc.get("executive_summary", [])
    if isinstance(raw_exec, list):
        max_iter = max(max_iter, len(raw_exec))
    # Section iterations
    section_obj = doc.get("section", {})
    if isinstance(section_obj, dict):
        for entries in section_obj.values():
            if isinstance(entries, list):
                for entry in entries:
                    it = entry.get("iteration", 0) if isinstance(entry, dict) else 0
                    max_iter = max(max_iter, it)
    return max_iter
