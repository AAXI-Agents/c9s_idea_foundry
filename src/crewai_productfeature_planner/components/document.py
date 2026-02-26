"""PRD document assembly helpers.

Pure-data functions that reconstruct PRD markdown from raw MongoDB
``workingIdeas`` documents.  No I/O, no side-effects — safe to call
from any context (CLI, API, background threads).
"""

import re

from crewai_productfeature_planner.apis.prd.models import SECTION_ORDER

_ITERATION_RE = re.compile(r"\s*\(Iteration\s+\d+\)", re.IGNORECASE)


def strip_iteration_tags(text: str) -> str:
    """Remove ``(Iteration N)`` markers from *text*.

    The LLM sometimes embeds iteration metadata (e.g. ``(Iteration 3)``)
    into headings or body text.  These are internal loop artefacts and
    should never appear in the final PRD output.
    """
    return _ITERATION_RE.sub("", text)


def assemble_prd_from_doc(doc: dict) -> str:
    """Reconstruct a PRD markdown string from a ``workingIdeas`` document.

    Mirrors the structure used by ``PRDDraft.assemble()`` but works
    directly from the raw MongoDB document.
    """
    parts: list[str] = []

    # Executive summary — use the last iteration's content
    raw_exec = doc.get("executive_summary", [])
    if isinstance(raw_exec, list) and raw_exec:
        latest = raw_exec[-1]
        if isinstance(latest, dict) and latest.get("content"):
            parts.append(f"## Executive Summary\n\n{strip_iteration_tags(latest['content'])}")

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
                    parts.append(f"## {title}\n\n{strip_iteration_tags(latest['content'])}")

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
