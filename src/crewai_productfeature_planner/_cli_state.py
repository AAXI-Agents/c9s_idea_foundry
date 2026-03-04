"""PRD state restoration and assembly from MongoDB documents.

Contains functions for checking resumable runs, restoring PRDFlow state
from persisted documents, and assembling PRD markdown from raw MongoDB docs.
"""
from __future__ import annotations

from crewai_productfeature_planner.apis.prd.models import (
    ExecutiveSummaryDraft,
    ExecutiveSummaryIteration,
    PRDDraft,
    SECTION_ORDER,
)
from crewai_productfeature_planner.flows.prd_flow import PRDFlow
from crewai_productfeature_planner.mongodb import (
    ensure_section_field,
    find_unfinalized,
    get_run_documents,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

__all__ = [
    "_check_resumable_runs",
    "_restore_prd_state",
    "_assemble_prd_from_doc",
    "_max_iteration_from_doc",
]


def _check_resumable_runs() -> dict | None:
    """Check MongoDB for unfinalized working ideas and let the user resume one.

    Returns:
        A dict with ``run_id`` and ``idea`` if the user chose to resume,
        or ``None`` to start a new idea.
    """
    try:
        unfinalized = find_unfinalized()
    except Exception as exc:
        logger.debug("Could not check for resumable runs: %s", exc)
        return None

    if not unfinalized:
        return None

    print(f"\n{'=' * 60}")
    print(f"  Found {len(unfinalized)} unfinalized idea(s)")
    print(f"{'=' * 60}")
    for i, run in enumerate(unfinalized, 1):
        sections = run.get("sections", [])
        exec_iters = run.get("exec_summary_iterations", 0)
        req_iters = run.get("req_breakdown_iterations", 0)
        created = run.get("created_at", "")
        if hasattr(created, "strftime"):
            created = created.strftime("%Y-%m-%d %H:%M")
        print(
            f"  [{i}] run_id={run['run_id']}  iter={run['iteration']}  "
            f"sections={len(sections)}  exec_summary={exec_iters}  "
            f"req_breakdown={req_iters}  created={created}"
        )
        idea_preview = (run.get("idea") or "")[:80]
        print(f"      idea: {idea_preview}")
    print(f"  [n] Start a new idea")
    print(f"{'=' * 60}\n")

    for i, run in enumerate(unfinalized, 1):
        if run.get("section_missing"):
            print(f"  ⚠  [{i}] section data missing — sections will be"
                  f" regenerated on resume")

    while True:
        choice = input("Choose a number to resume, or 'n' for new: ").strip().lower()
        if choice in ("n", "new"):
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(unfinalized):
                return unfinalized[idx]
        except ValueError:
            pass
        print(f"Please enter 1-{len(unfinalized)} or 'n'.")


def _restore_prd_state(run_info: dict) -> PRDFlow:
    """Rebuild a PRDFlow with its state restored from a MongoDB document.

    Reads the single working document for the run, reconstructs the
    PRDDraft with section content and approval status from iteration
    arrays, and sets the flow to resume from the next unapproved section.
    """
    run_id = run_info["run_id"]
    idea = run_info["idea"]
    docs = get_run_documents(run_id)

    draft = PRDDraft.create_empty()
    section_keys_set = {key for key, _ in SECTION_ORDER}

    total_iterations = 0

    if docs:
        doc = docs[0]  # single-document model
        section_obj = doc.get("section", {})

        # Edge case: section field was accidentally deleted or never
        # created.  Re-initialise it in MongoDB so save_iteration works
        # and let the flow reprocess all sections from scratch.
        if "section" not in doc:
            logger.warning(
                "Working-idea document for run_id=%s is missing the "
                "'section' field — re-initialising; sections will be "
                "regenerated",
                run_id,
            )
            ensure_section_field(run_id)
            section_obj = {}

        # Replay section iteration arrays to reconstruct section state
        if isinstance(section_obj, dict):
            for section_key, iterations in section_obj.items():
                if section_key not in section_keys_set:
                    continue
                section = draft.get_section(section_key)
                if section is None:
                    continue

                if isinstance(iterations, list) and iterations:
                    # Use the latest iteration record
                    latest = iterations[-1]
                    if isinstance(latest, dict):
                        content = latest.get("content", "")
                        if content:
                            section.content = content
                        critique = latest.get("critique", "")
                        if critique:
                            section.critique = critique
                        section.iteration = latest.get("iteration", 0)
                        section.updated_date = latest.get("updated_date", "")
                        if section.iteration > total_iterations:
                            total_iterations = section.iteration

    # Determine which sections are approved:
    # A section is considered approved if a later section already has content.
    # This means the flow moved past it.
    last_with_content = -1
    for i, section in enumerate(draft.sections):
        if section.content:
            last_with_content = i

    # All sections before the last one with content were approved
    for i, section in enumerate(draft.sections):
        if section.content and i < last_with_content:
            section.is_approved = True

    # Restore executive_summary iterations from the top-level array
    exec_summary_draft = ExecutiveSummaryDraft()
    if docs:
        doc = docs[0]
        raw_exec = doc.get("executive_summary", [])
        if isinstance(raw_exec, list):
            for entry in raw_exec:
                if not isinstance(entry, dict):
                    continue
                exec_summary_draft.iterations.append(
                    ExecutiveSummaryIteration(
                        content=entry.get("content", ""),
                        iteration=entry.get("iteration", 1),
                        critique=entry.get("critique"),
                        updated_date=entry.get("updated_date", ""),
                    )
                )
            if exec_summary_draft.iterations:
                exec_summary_draft.is_approved = True

    flow = PRDFlow()
    flow.state.run_id = run_id
    flow.state.idea = idea
    flow.state.draft = draft
    flow.state.executive_summary = exec_summary_draft
    flow.state.iteration = total_iterations
    flow.state.status = "inprogress"

    # Set finalized_idea from the last executive summary iteration
    if exec_summary_draft.latest_content:
        flow.state.finalized_idea = exec_summary_draft.latest_content

    # ── Restore refine_idea iterations ────────────────────────
    if docs:
        doc = docs[0]
        raw_refine = doc.get("refine_idea", [])
        if isinstance(raw_refine, list) and raw_refine:
            flow.state.idea_refined = True
            flow.state.refinement_history = [
                {
                    "iteration": entry.get("iteration", i + 1),
                    "idea": entry.get("content", ""),
                    "evaluation": entry.get("critique", ""),
                }
                for i, entry in enumerate(raw_refine)
                if isinstance(entry, dict)
            ]
            # Use the latest refined idea as the current idea
            latest_refine = raw_refine[-1]
            if isinstance(latest_refine, dict) and latest_refine.get("content"):
                flow.state.idea = latest_refine["content"]
                flow.state.original_idea = idea
            logger.info(
                "Restored refine_idea from %d iteration(s) (%d chars)",
                len(raw_refine),
                len(flow.state.idea),
            )

    # If executive summary has iterations the idea was already refined
    # (idea refinement runs before executive summary in the pipeline).
    if not flow.state.idea_refined and exec_summary_draft.iterations:
        flow.state.idea_refined = True

    # Restore requirements_breakdown from the top-level array so the
    # orchestrator skips re-running the breakdown on resume.
    if docs:
        doc = docs[0]
        raw_reqs = doc.get("requirements_breakdown", [])
        if isinstance(raw_reqs, list) and raw_reqs:
            # Use the latest iteration's content
            latest_req = raw_reqs[-1]
            if isinstance(latest_req, dict) and latest_req.get("content"):
                flow.state.requirements_breakdown = latest_req["content"]
                flow.state.requirements_broken_down = True
                # Reconstruct breakdown_history
                flow.state.breakdown_history = [
                    {
                        "iteration": entry.get("iteration", i + 1),
                        "requirements": entry.get("content", ""),
                        "evaluation": entry.get("critique", ""),
                    }
                    for i, entry in enumerate(raw_reqs)
                    if isinstance(entry, dict)
                ]
                logger.info(
                    "Restored requirements_breakdown from %d iteration(s) "
                    "(%d chars)",
                    len(raw_reqs),
                    len(flow.state.requirements_breakdown),
                )

    next_section = draft.next_section()
    if next_section:
        flow.state.current_section_key = next_section.key

    approved_count = sum(1 for s in draft.sections if s.is_approved)
    exec_iter_count = len(exec_summary_draft.iterations)
    req_iter_count = len(flow.state.breakdown_history)
    logger.info(
        "Restored PRD state: run_id=%s, %d/%d sections approved, "
        "iteration=%d, exec_summary_iterations=%d, "
        "requirements_breakdown_iterations=%d",
        run_id, approved_count, len(draft.sections), total_iterations,
        exec_iter_count, req_iter_count,
    )

    return flow


def _assemble_prd_from_doc(doc: dict) -> str:
    """Reconstruct a PRD markdown string from a ``workingIdeas`` document.

    Mirrors the structure used by ``PRDDraft.assemble()`` but works
    directly from the raw MongoDB document.
    """
    from crewai_productfeature_planner.components.document import (
        strip_iteration_tags,
    )

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


def _max_iteration_from_doc(doc: dict) -> int:
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
