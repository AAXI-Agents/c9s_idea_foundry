"""State restoration — rebuild a PRDFlow from MongoDB.

Handles resuming interrupted PRD runs by reading ``workingIdeas``
documents and reconstructing in-memory ``PRDFlow`` state (draft,
executive summary, requirements breakdown, section approvals).
"""

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


def check_resumable_runs() -> dict | None:
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


def restore_prd_state(run_info: dict) -> PRDFlow:
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

    # ── Restore specialist sections (CEO review, Eng plan) ────
    if docs:
        doc = docs[0]
        section_obj = doc.get("section", {})
        if isinstance(section_obj, dict):
            # executive_product_summary
            eps_iters = section_obj.get("executive_product_summary", [])
            if isinstance(eps_iters, list) and eps_iters:
                latest_eps = eps_iters[-1]
                if isinstance(latest_eps, dict) and latest_eps.get("content"):
                    flow.state.executive_product_summary = latest_eps["content"]
                    logger.info(
                        "Restored executive_product_summary (%d chars)",
                        len(flow.state.executive_product_summary),
                    )
            # engineering_plan
            eng_iters = section_obj.get("engineering_plan", [])
            if isinstance(eng_iters, list) and eng_iters:
                latest_eng = eng_iters[-1]
                if isinstance(latest_eng, dict) and latest_eng.get("content"):
                    flow.state.engineering_plan = latest_eng["content"]
                    logger.info(
                        "Restored engineering_plan (%d chars)",
                        len(flow.state.engineering_plan),
                    )

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
