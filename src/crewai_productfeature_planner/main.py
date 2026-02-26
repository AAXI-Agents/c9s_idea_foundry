#!/usr/bin/env python
import os
import signal
import subprocess
import sys
import warnings

from crewai_productfeature_planner.apis.prd.models import ExecutiveSummaryDraft, ExecutiveSummaryIteration, PRDDraft, SECTION_ORDER
from crewai_productfeature_planner.flows.prd_flow import IdeaFinalized, PauseRequested, PRDFlow, RequirementsFinalized
from crewai_productfeature_planner.mongodb import find_completed_without_output, find_unfinalized, get_db, get_run_documents, mark_completed, save_executive_summary, save_iteration, save_output_file, save_pipeline_step, ensure_section_field
from crewai_productfeature_planner.scripts.retry import BillingError, LLMError
from crewai_productfeature_planner.mongodb.crew_jobs import (
    create_job,
    fail_incomplete_jobs_on_startup,
    reactivate_job,
    update_job_completed,
    update_job_started,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

logger = get_logger(__name__)

# Process names used by the project's console_scripts entry points.
_CREW_PROCESS_NAMES = ("run_crew", "crewai_productfeature_planner", "run_prd_flow")


def _kill_stale_crew_processes() -> int:
    """Kill any lingering CrewAI CLI processes from a previous run.

    Scans ``ps`` output for processes whose command line contains one of
    the known entry-point script names and sends ``SIGTERM``.

    The current process **and its entire ancestor chain** (parent,
    grandparent, …) are never killed.  This is important because
    ``crewai run`` spawns ``uv run run_crew`` as an intermediate parent
    whose command line matches the pattern.

    Returns the number of processes terminated.
    """
    my_pid = os.getpid()
    killed = 0

    try:
        # Use `ps` with PPID so we can build the ancestor chain.
        result = subprocess.run(
            ["ps", "axo", "pid,ppid,command"],
            capture_output=True, text=True, timeout=5,
        )

        # First pass: build pid→ppid map so we can walk ancestors.
        ppid_map: dict[int, int] = {}
        lines: list[tuple[int, str]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
            except ValueError:
                continue
            ppid_map[pid] = ppid
            lines.append((pid, parts[2]))

        # Build set of ancestor PIDs to protect.
        protected: set[int] = set()
        cur = my_pid
        while cur and cur not in protected:
            protected.add(cur)
            cur = ppid_map.get(cur, 0)

        # Second pass: kill matching processes that are NOT protected.
        for pid, cmd in lines:
            if pid in protected:
                continue
            if any(name in cmd for name in _CREW_PROCESS_NAMES):
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
                    logger.info(
                        "[Startup] Killed stale process PID %d: %s",
                        pid, cmd[:120],
                    )
                except ProcessLookupError:
                    pass  # already gone
                except PermissionError:
                    logger.debug(
                        "[Startup] No permission to kill PID %d", pid,
                    )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[Startup] Could not scan for stale processes: %s", exc)

    return killed


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

    # If executive summary has iterations the idea was already refined
    # (idea refinement runs before executive summary in the pipeline).
    if exec_summary_draft.iterations:
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


def _get_idea() -> str:
    """Get the feature idea from CLI args or interactive prompt.

    Resolution order:
        1. ``sys.argv[1]`` — passed as CLI argument
        2. Interactive ``input()`` prompt
    """
    if len(sys.argv) >= 2:
        return sys.argv[1]
    return input("Enter your product feature idea: ").strip()


def _choose_refinement_mode() -> str:
    """Prompt the user to choose how to refine the idea before PRD generation.

    Returns:
        ``"manual"`` for interactive manual iteration, or
        ``"agent"`` to let the Gemini Idea Refinement agent handle it.
    """
    print(f"\n{'=' * 60}")
    print("  How would you like to refine this idea?")
    print(f"{'=' * 60}")
    print("  [a] Agent — let the AI Idea Refinement agent iterate")
    print("  [m] Manual — iterate on the idea yourself")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose refinement mode [a/m]: ").strip().lower()
        if choice in ("a", "agent"):
            return "agent"
        if choice in ("m", "manual"):
            return "manual"
        print("Please enter 'a' for agent or 'm' for manual.")


def _manual_idea_refinement(idea: str, run_id: str = "") -> tuple[str, list[dict]]:
    """Interactive CLI loop for the user to manually refine an idea.

    Displays the current idea and lets the user revise it in multiple
    rounds until satisfied.  Each round the user can type a revised
    version (multi-line, finish with two blank lines) or approve the
    current version.

    When *run_id* is provided each iteration is persisted to the
    ``workingIdeas`` collection.

    Args:
        idea: The initial raw idea text.
        run_id: Optional flow run identifier for MongoDB persistence.

    Returns:
        A tuple of ``(refined_idea, refinement_history)`` where
        *refinement_history* is a list of dicts, each containing
        ``iteration`` and ``idea``.
    """
    current = idea
    iteration = 0
    refinement_history: list[dict] = []

    while True:
        iteration += 1
        print(f"\n{'=' * 60}")
        print(f"  Idea Refinement — Iteration {iteration}")
        print(f"{'=' * 60}")
        print(f"\n{current}\n")
        print(f"{'=' * 60}")
        print("  [y] Approve this idea and proceed to PRD generation")
        print("  [e] Edit / refine this idea")
        print(f"{'=' * 60}\n")

        while True:
            choice = input("Choose action [y/e]: ").strip().lower()
            if choice in ("y", "yes"):
                logger.info(
                    "[ManualRefine] Idea approved after %d iteration(s) (%d chars)",
                    iteration, len(current),
                )
                return current, refinement_history
            if choice in ("e", "edit"):
                break
            print("Please enter 'y' to approve or 'e' to edit.")

        print("Enter your revised idea (press Enter twice on a blank line to finish):")
        lines: list[str] = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        revised = "\n".join(lines).strip()
        if revised:
            current = revised
            logger.info("[ManualRefine] Iteration %d — revised (%d chars)",
                        iteration, len(current))
        else:
            print("Empty input — keeping previous version.")

        # Record iteration and persist to workingIdeas
        refinement_history.append({"iteration": iteration, "idea": current})
        if run_id:
            try:
                save_executive_summary(
                    run_id=run_id,
                    idea=idea,
                    iteration=iteration,
                    content=current,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[ManualRefine] Failed to save iteration %d: %s",
                    iteration, exc,
                )


def _approve_refined_idea(
    refined_idea: str,
    original_idea: str,
    run_id: str,
    refinement_history: list[dict] | None = None,
) -> bool:
    """Show the refined idea and let the user approve/finalize or continue.

    This is used as the ``idea_approval_callback`` on PRDFlow.  It is
    called after idea refinement (manual or agent) completes.

    Displays the final refined idea and offers:
      * ``[y]es``  — approve the idea: mark the working idea and
        proceed to section drafting (``draft_section_task`` →
        ``critique_section_task`` → ``refine_section_task``, iterated
        between min/max counts).
      * ``[c]ancel`` — stop without generating sections.

    Args:
        refined_idea: The idea after refinement.
        original_idea: The raw idea before refinement.
        run_id: The current flow run identifier.
        refinement_history: List of iteration dicts from the refinement
            process.  Persisted alongside the finalized idea.

    Returns:
        ``True`` to finalize early (stop), ``False`` to continue to
        section drafting.
    """
    history = refinement_history or []
    print(f"\n{'=' * 60}")
    print("  Idea Refinement Complete")
    print(f"{'=' * 60}")
    if original_idea:
        print(f"  Original ({len(original_idea)} chars) → Refined ({len(refined_idea)} chars)")
    print(f"\n{refined_idea}\n")
    print(f"{'=' * 60}")
    print("  [y] Approve — save this idea and define all sections:")
    print("        1. Draft each section independently (draft_section_task)")
    print("        2. Critique each section (critique_section_task)")
    print("        3. Refine with critique feedback (refine_section_task)")
    print("        Steps 2-3 iterate between min/max iteration count")
    print("  [c] Cancel — stop without generating sections")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose action [y/c]: ").strip().lower()
        if choice in ("y", "yes"):
            logger.info(
                "[IdeaApproval] User approved refined idea (run_id=%s, %d chars)",
                run_id, len(refined_idea),
            )
            return False  # continue to section drafting
        if choice in ("c", "cancel"):
            logger.info(
                "[IdeaApproval] User cancelled — exiting CLI (run_id=%s)",
                run_id,
            )
            print("\nGoodbye!")
            sys.exit(0)
        print("Please enter 'y' to approve or 'c' to cancel.")


def _approve_requirements(
    requirements: str,
    idea: str,
    run_id: str,
    breakdown_history: list[dict] | None = None,
) -> bool:
    """Show the requirements breakdown and let the user approve or cancel.

    This is used as the ``requirements_approval_callback`` on PRDFlow.
    It is called after the requirements breakdown agent completes.

    Displays the final requirements and offers:
      * ``[y]es``  — approve the requirements and proceed to PRD
        section drafting (draft → critique → refine for 9 sections).
      * ``[c]ancel`` — stop the flow without generating sections.
        Marks the working idea as completed.

    The return value semantics match ``_approve_refined_idea``:
    ``False`` to continue, ``True`` to finalize (stop).

    Args:
        requirements: The structured requirements breakdown.
        idea: The (possibly refined) product idea.
        run_id: The current flow run identifier.
        breakdown_history: Iteration history from the breakdown process.

    Returns:
        ``False`` to continue to PRD section drafting,
        ``True`` to finalize (stop).
    """
    history = breakdown_history or []
    print(f"\n{'=' * 60}")
    print("  Requirements Breakdown Complete")
    print(f"{'=' * 60}")
    print(f"  {len(history)} iteration(s) — {len(requirements)} chars")
    print(f"{'=' * 60}")
    # Show first 3000 chars with truncation
    if len(requirements) > 3000:
        print(f"\n{requirements[:3000]}")
        print(f"\n... ({len(requirements) - 3000} more chars) ...")
    else:
        print(f"\n{requirements}")
    print(f"\n{'=' * 60}")
    print("  [y] Approve — auto-generate all sections (no further prompts):")
    print("        1. Draft each section independently (draft_section_task)")
    print("        2. Critique each section (critique_section_task)")
    print("        3. Refine with critique feedback (refine_section_task)")
    print("        Steps 2-3 auto-iterate between min/max iteration count")
    print("        Once complete, status is set to 'completed'")
    print("  [c] Cancel — stop without generating sections")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose action [y/c]: ").strip().lower()
        if choice in ("y", "yes"):
            logger.info(
                "[RequirementsApproval] User approved requirements — "
                "continuing to PRD sections (run_id=%s, %d chars)",
                run_id, len(requirements),
            )
            return False  # continue to section drafting
        if choice in ("c", "cancel"):
            logger.info(
                "[RequirementsApproval] User cancelled — exiting CLI "
                "(run_id=%s)",
                run_id,
            )
            print("\nGoodbye!")
            sys.exit(0)
        print("Please enter 'y' to approve or 'c' to cancel.")




def _prompt_next_action() -> str | None:
    """Ask the user whether to start a new idea or exit.

    Returns:
        The new idea string, or ``None`` to exit.
    """
    print(f"\n{'=' * 60}")
    print("  What would you like to do next?")
    print(f"{'=' * 60}")
    print("  [n] Start a new idea")
    print("  [q] Exit")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose an option: ").strip().lower()
        if choice in ("q", "quit", "exit", "e"):
            return None
        if choice in ("n", "new"):
            new_idea = input("Enter your product feature idea: ").strip()
            if new_idea:
                return new_idea
            print("Empty idea — please try again.")
        else:
            print("Please enter 'n' for a new idea or 'q' to exit.")


# ── Startup delivery orchestrator ────────────────────────────────────


def _run_startup_delivery() -> int:
    """Autonomously deliver completed PRDs via CrewAI crew collaboration.

    Scans ``workingIdeas`` for completed runs, checks each against the
    ``productRequirements`` collection, and uses a **CrewAI Crew** with
    sequential process and agent collaboration to execute the delivery
    pipeline (Confluence publish + Jira ticketing).

    The crew comprises two agents:

    * **Delivery Manager** — coordinates the lifecycle, decides which
      steps are needed.  ``allow_delegation=True`` lets it hand off
      tool-bearing work.
    * **Orchestrator** — the specialist equipped with Confluence and
      Jira tools.

    Uses ``productRequirements`` to persist per-run delivery state so
    the agent can resume where it left off on subsequent restarts.

    Prints user-facing progress messages prefixed with ``[Orchestrator]``
    so the user can see what the agent is doing before the interactive
    CLI takes over.

    This is fully autonomous — no user involvement required.

    Returns:
        The number of runs that were fully delivered (Confluence + Jira).
    """
    from crewai_productfeature_planner.mongodb.product_requirements import (
        get_delivery_record,
        upsert_delivery_record,
    )
    from crewai_productfeature_planner.orchestrator.stages import (
        _discover_pending_deliveries,
        _has_confluence_credentials,
        _has_jira_credentials,
        _print_delivery_status,
        build_startup_delivery_crew,
    )
    from crewai_productfeature_planner.scripts.retry import (
        crew_kickoff_with_retry,
    )

    if not (_has_confluence_credentials() or _has_jira_credentials()):
        logger.debug(
            "[StartupDelivery] Skipped — neither Confluence nor Jira configured"
        )
        return 0

    # Discover pending deliveries from MongoDB
    try:
        items = _discover_pending_deliveries()
    except Exception as exc:
        logger.warning(
            "[StartupDelivery] Discovery failed: %s", exc,
        )
        return 0
    if not items:
        logger.info("[StartupDelivery] No pending deliveries found")
        return 0

    _print_delivery_status(
        f"Found {len(items)} completed PRD(s) pending delivery"
    )

    delivered = 0
    for item in items:
        run_id = item["run_id"]
        idea_preview = (item["idea"] or "PRD")[:60].strip()

        # --- Print what we're about to do ---
        pending_parts = []
        if not item["confluence_done"]:
            pending_parts.append("Confluence publish")
        if not item["jira_done"] and _has_jira_credentials():
            pending_parts.append("Jira ticketing")
        steps_label = " + ".join(pending_parts) or "finalising record"

        _print_delivery_status(
            f"Processing \"{idea_preview}\" — {steps_label}"
        )

        # Seed delivery record so we can resume on crash
        record = get_delivery_record(run_id)
        if not record:
            upsert_delivery_record(
                run_id,
                confluence_published=item["confluence_done"],
                jira_completed=item["jira_done"],
            )

        try:
            # Build the CrewAI crew with sequential process & collaboration
            crew = build_startup_delivery_crew(
                item, progress_callback=_print_delivery_status,
            )

            _print_delivery_status(
                f"Crew assembled — {len(crew.tasks)} task(s), "
                f"{len(crew.agents)} agent(s) collaborating"
            )

            # Kick off the crew (with retry for transient LLM failures)
            result = crew_kickoff_with_retry(
                crew, step_label=f"startup_delivery_{run_id}",
            )

            # Parse result to determine what was accomplished
            raw_output = result.raw if hasattr(result, "raw") else str(result)

            # Update delivery record from crew output
            new_conf_done = item["confluence_done"] or _confluence_completed_in_output(raw_output)

            # Jira must wait for Confluence to be verified first.
            # Only check Jira completion when Confluence is confirmed.
            if new_conf_done:
                new_jira_done = item["jira_done"] or _jira_completed_in_output(raw_output)
            else:
                new_jira_done = item["jira_done"]

            # Extract ticket keys from output and persist incrementally
            if new_jira_done or _jira_completed_in_output(raw_output):
                try:
                    import re as _re
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        append_jira_ticket,
                    )
                    from crewai_productfeature_planner.tools.jira_tool import (
                        search_jira_issues,
                    )
                    # Build key→type map from Jira so tickets are
                    # stored with the correct issue type (Epic/Story/Task).
                    _type_map: dict[str, str] = {}
                    try:
                        for _iss in search_jira_issues(run_id):
                            _type_map[_iss["issue_key"]] = _iss["issue_type"]
                    except Exception:  # noqa: BLE001
                        pass  # lookup is best-effort
                    for key in _re.findall(r"[A-Z]{2,10}-\d+", raw_output):
                        append_jira_ticket(run_id, {
                            "key": key,
                            "type": _type_map.get(key, "unknown"),
                        })
                except Exception:  # noqa: BLE001
                    pass  # best-effort

            upsert_delivery_record(
                run_id,
                confluence_published=new_conf_done,
                confluence_url=_extract_confluence_url(raw_output) or item.get("confluence_url", ""),
                jira_completed=new_jira_done,
                jira_output=raw_output if new_jira_done else None,
                error=None,
            )

            # Persist confluence_url to workingIdeas if new
            if new_conf_done and not item["doc"].get("confluence_url"):
                conf_url = _extract_confluence_url(raw_output)
                if conf_url:
                    try:
                        from crewai_productfeature_planner.mongodb import save_confluence_url
                        save_confluence_url(
                            run_id=run_id,
                            confluence_url=conf_url,
                            page_id="",
                        )
                    except Exception:
                        pass

            if new_conf_done and new_jira_done:
                delivered += 1
                _print_delivery_status(
                    f"✓ Fully delivered \"{idea_preview}\""
                )
            else:
                status_parts = []
                if new_conf_done:
                    status_parts.append("Confluence ✓")
                if new_jira_done:
                    status_parts.append("Jira ✓")
                _print_delivery_status(
                    f"Partial delivery for \"{idea_preview}\" — "
                    + ", ".join(status_parts or ["awaiting next restart"])
                )

            logger.info(
                "[StartupDelivery] Delivery crew completed for "
                "run_id=%s (confluence=%s, jira=%s)",
                run_id,
                "done" if new_conf_done else "pending",
                "done" if new_jira_done else "pending",
            )
        except Exception as exc:
            logger.warning(
                "[StartupDelivery] Delivery crew failed for "
                "run_id=%s: %s",
                run_id, exc,
            )
            upsert_delivery_record(run_id, error=str(exc))
            _print_delivery_status(
                f"✗ Delivery failed for \"{idea_preview}\": {exc}"
            )

    if delivered:
        logger.info(
            "[StartupDelivery] Fully delivered %d PRD(s) on startup",
            delivered,
        )
    return delivered


def _confluence_completed_in_output(output: str) -> bool:
    """Detect Confluence publish success in crew output.

    Requires **both** a success keyword AND a recognisable Confluence URL
    so that mere mentions of "Confluence" in assessment text do not
    trigger a false positive.
    """
    lower = output.lower()
    if "fail" in lower[:200]:
        return False
    has_keyword = any(kw in lower for kw in [
        "published", "created", "updated", "page_id", "page id",
    ])
    has_url = bool(_extract_confluence_url(output))
    return has_keyword and has_url


def _jira_completed_in_output(output: str) -> bool:
    """Detect Jira ticket creation in crew output.

    Requires **both** a Jira keyword AND a recognisable issue key
    pattern (e.g. ``PROJ-123``) to avoid false positives from
    assessment text that merely mentions "Jira".
    """
    import re
    lower = output.lower()
    if "fail" in lower[:200]:
        return False
    has_keyword = any(kw in lower for kw in [
        "epic", "story", "stories",
        "issue_key", "issue key",
    ])
    has_issue_key = bool(re.search(r"[A-Z]{2,10}-\d+", output))
    return has_keyword and has_issue_key


def _extract_confluence_url(output: str) -> str:
    """Extract a Confluence URL from crew output text."""
    import re
    match = re.search(r"https?://[^\s]+atlassian[^\s]*wiki[^\s]*", output)
    if match:
        return match.group(0).rstrip(".,;:()\"'")
    # Fallback: any URL with /wiki/ in it
    match = re.search(r"https?://[^\s]+/wiki/[^\s]*", output)
    if match:
        return match.group(0).rstrip(".,;:()\"'")
    return ""


def _generate_missing_outputs() -> int:
    """Generate markdown files for completed ideas that are missing output.

    On startup, queries MongoDB for ``workingIdeas`` documents whose
    ``status`` is ``"completed"`` but have no ``output_file`` recorded.
    For each, reconstructs the PRD content from the document and writes
    a markdown file via :class:`PRDFileWriteTool`.

    Returns:
        The number of output files generated.
    """
    from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool

    try:
        docs = find_completed_without_output()
    except Exception as exc:
        logger.debug("Could not check for completed ideas without output: %s", exc)
        return 0

    if not docs:
        return 0

    generated = 0
    for doc in docs:
        run_id = doc.get("run_id", "unknown")
        try:
            content = _assemble_prd_from_doc(doc)
            if not content:
                logger.debug(
                    "[StartupRecovery] Skipping run_id=%s — no content to assemble",
                    run_id,
                )
                continue

            # Determine version from section iterations
            version = _max_iteration_from_doc(doc)

            writer = PRDFileWriteTool()
            save_result = writer._run(
                content=content,
                filename="",
                version=max(version, 1),
            )
            # Extract path from "PRD saved to <path>"
            prefix = "PRD saved to "
            output_path = save_result[len(prefix):] if save_result.startswith(prefix) else save_result
            save_output_file(run_id, output_path)
            generated += 1
            logger.info(
                "[StartupRecovery] Generated missing output for run_id=%s: %s",
                run_id, save_result,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[StartupRecovery] Failed to generate output for run_id=%s: %s",
                run_id, exc,
            )

    if generated:
        logger.info(
            "[StartupRecovery] Generated %d missing output file(s)", generated,
        )
    return generated


def _publish_unpublished_prds() -> int:
    """Publish completed PRDs to Confluence that haven't been published yet.

    Scans MongoDB for completed working ideas whose ``confluence_url``
    field is missing or empty.  For each, assembles the PRD from the
    stored sections and publishes it to Confluence.

    Called on server startup and after each completed flow.

    Returns:
        Number of PRDs successfully published.
    """
    from crewai_productfeature_planner.tools.confluence_tool import (
        _has_confluence_credentials,
        publish_to_confluence,
    )

    if not _has_confluence_credentials():
        return 0

    try:
        from crewai_productfeature_planner.mongodb import (
            find_completed_without_confluence,
            save_confluence_url,
        )
        docs = find_completed_without_confluence()
    except Exception as exc:
        logger.debug(
            "Could not check for unpublished PRDs: %s", exc,
        )
        return 0

    if not docs:
        return 0

    published = 0
    for doc in docs:
        run_id = doc.get("run_id", "unknown")
        try:
            content = _assemble_prd_from_doc(doc)
            if not content:
                logger.debug(
                    "[StartupRecovery] Skipping Confluence publish for "
                    "run_id=%s — no content",
                    run_id,
                )
                continue

            idea = (doc.get("idea") or "PRD")[:80].strip()
            title = f"PRD — {idea}"

            result = publish_to_confluence(
                title=title,
                markdown_content=content,
                run_id=run_id,
            )
            save_confluence_url(
                run_id=run_id,
                confluence_url=result["url"],
                page_id=result["page_id"],
            )
            published += 1
            logger.info(
                "[StartupRecovery] Published PRD to Confluence for "
                "run_id=%s: %s",
                run_id, result["url"],
            )
        except Exception as exc:
            logger.warning(
                "[StartupRecovery] Failed to publish PRD for "
                "run_id=%s: %s",
                run_id, exc,
            )

    if published:
        logger.info(
            "[StartupRecovery] Published %d PRD(s) to Confluence",
            published,
        )
    return published


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


def run():
    """
    Run the PRD generation flow with interactive approval.

    On startup, checks MongoDB for unfinalized working ideas and offers
    to resume from where the user left off.

    Usage:
        crewai run                              # interactive prompt
        crewai run "Add dark mode to dashboard" # idea as argument
    """
    # Kill stale CrewAI processes from a previous run
    killed = _kill_stale_crew_processes()
    if killed:
        print(f"  Terminated {killed} stale process(es) from previous run.")

    # Startup recovery: mark any incomplete jobs as failed
    try:
        recovered = fail_incomplete_jobs_on_startup()
        if recovered:
            print(f"  Recovered {recovered} incomplete job(s) from previous run.")
    except Exception as exc:
        logger.debug("Startup recovery failed: %s", exc)

    # Startup recovery: generate markdown for completed ideas missing output
    generated = _generate_missing_outputs()
    if generated:
        print(f"  Generated {generated} missing output file(s) for completed idea(s).")

    # Startup pipeline: review markdown PRDs and publish to Confluence
    try:
        from crewai_productfeature_planner.orchestrator.stages import (
            build_startup_pipeline,
        )
        startup_pipeline = build_startup_pipeline()
        startup_pipeline.run_pipeline()
        if startup_pipeline.completed:
            print(
                f"  Startup pipeline: completed stage(s) "
                f"{startup_pipeline.completed}"
            )
        if startup_pipeline.skipped:
            logger.info(
                "Startup pipeline: skipped stage(s) %s",
                startup_pipeline.skipped,
            )
    except Exception as exc:
        logger.warning("Startup pipeline (markdown review) failed: %s", exc)

    # Startup delivery: autonomously run Confluence + Jira pipeline
    # in a background thread so the user can start working immediately.
    import threading

    delivery_thread = threading.Thread(
        target=_run_startup_delivery_background,
        name="startup-delivery",
        daemon=True,
    )
    delivery_thread.start()

    # If idea was passed as CLI arg, run once and exit
    if len(sys.argv) >= 2:
        _run_single_flow(idea=sys.argv[1])
        return

    # Interactive loop — keeps offering new ideas after each run
    idea = None
    while True:
        _run_single_flow(idea=idea)
        next_idea = _prompt_next_action()
        if next_idea is None:
            print("\nGoodbye!")
            return
        idea = next_idea


def _run_startup_delivery_background() -> None:
    """Wrapper for ``_run_startup_delivery`` that runs in a daemon thread.

    Catches all exceptions so the background thread never crashes the
    main process.  Prints a summary line when delivery completes.
    """
    try:
        delivered = _run_startup_delivery()
        if delivered:
            from crewai_productfeature_planner.orchestrator.stages import (
                _print_delivery_status,
            )
            _print_delivery_status(
                f"Background delivery complete — {delivered} PRD(s) fully delivered"
            )
    except Exception as exc:
        logger.warning("[StartupDelivery] Background thread failed: %s", exc)


def _run_single_flow(idea: str | None = None) -> None:
    """Execute one PRD flow cycle (new or resumed).

    Args:
        idea: When supplied, skip the resume check and use this idea directly.
    """
    # Check for resumable runs (skip if idea passed via CLI arg)
    resumed_flow = None

    if idea is None:
        run_info = _check_resumable_runs()
        if run_info is not None:
            resumed_flow = _restore_prd_state(run_info)
            print(f"\nResuming run_id={resumed_flow.state.run_id}")
            exec_iters = len(resumed_flow.state.executive_summary.iterations)
            if exec_iters:
                print(
                    f"Executive Summary: {exec_iters} iteration(s) "
                    f"({'approved — skipping to sections' if exec_iters >= 3 else 'in progress'})"
                )
            next_section = resumed_flow.state.draft.next_section()
            if next_section:
                total = len(resumed_flow.state.draft.sections)
                print(f"Next: Step {next_section.step}/{total} — {next_section.title}")
            approved = sum(1 for s in resumed_flow.state.draft.sections if s.is_approved)
            print(f"Progress: {approved}/{len(resumed_flow.state.draft.sections)} sections approved\n")

            # If the flow already progressed past requirements approval
            # (executive summary iterations or section content exist),
            # prompt to continue from where it left off instead of
            # re-showing the requirements approval gate.
            if (
                resumed_flow.state.executive_summary.iterations
                or any(s.content for s in resumed_flow.state.draft.sections)
            ):
                print(f"{'=' * 60}")
                print("  [y] Continue — auto-generate remaining sections")
                print("  [c] Cancel — exit the program")
                print(f"{'=' * 60}\n")
                while True:
                    choice = input("Choose action [y/c]: ").strip().lower()
                    if choice in ("y", "yes"):
                        break
                    if choice in ("c", "cancel"):
                        print("\nGoodbye!")
                        sys.exit(0)
                    print("Please enter 'y' to continue or 'c' to cancel.")

    if resumed_flow is not None:
        flow = resumed_flow
        idea = flow.state.idea
    elif idea is not None:
        flow = PRDFlow()
        flow.state.idea = idea
    else:
        idea = _get_idea()
        if not idea:
            raise SystemExit("No idea provided. Aborting.")
        flow = PRDFlow()
        flow.state.idea = idea

    # Offer refinement choice (for new runs, and resumed runs whose idea
    # hasn't been refined yet)
    if not flow.state.idea_refined:
        mode = _choose_refinement_mode()
        if mode == "manual":
            original = flow.state.idea
            refined, history = _manual_idea_refinement(
                flow.state.idea, run_id=flow.state.run_id,
            )
            flow.state.original_idea = original
            flow.state.idea = refined
            flow.state.idea_refined = True
            flow.state.refinement_history = history
            idea = refined
            print(f"\n  ✦ Idea refined manually ({len(original)} → {len(refined)} chars)")

            # Approve the manually-refined idea before proceeding
            finalized = _approve_refined_idea(
                refined, original, flow.state.run_id,
                refinement_history=history,
            )
            if finalized:
                # Track job and mark completed
                if resumed_flow is not None:
                    reactivate_job(flow.state.run_id)
                else:
                    create_job(job_id=flow.state.run_id, flow_name="prd", idea=idea)
                update_job_started(flow.state.run_id)
                update_job_completed(flow.state.run_id, status="completed")
                print(f"\n  ✦ Idea finalized and saved (run_id={flow.state.run_id})")
                return
        else:
            print("\n  ✦ Agent will refine the idea automatically before PRD generation")

    # Track job in crewJobs — reactivate for resumes, create for new runs
    if resumed_flow is not None:
        reactivate_job(flow.state.run_id)
    else:
        create_job(job_id=flow.state.run_id, flow_name="prd", idea=idea)
    update_job_started(flow.state.run_id)

    logger.info("Starting PRD flow (idea='%s')", idea)
    try:
        flow.idea_approval_callback = _approve_refined_idea
        flow.requirements_approval_callback = _approve_requirements
        result = flow.kickoff()

        # Safety net: if finalize() failed or was skipped, persist here
        if not flow.state.is_ready:
            logger.warning(
                "[CLI] finalize() incomplete for run_id=%s — "
                "persisting finalized PRD from main",
                flow.state.run_id,
            )
            from crewai_productfeature_planner.scripts.confluence_xhtml import md_to_confluence_xhtml

            final_prd = flow.state.final_prd or flow.state.draft.assemble()
            confluence_xhtml = md_to_confluence_xhtml(final_prd)
            mark_completed(flow.state.run_id)

        update_job_completed(flow.state.run_id, status="completed")
        logger.info("PRD flow completed successfully")
        print(f"\nPRD Flow completed. Result:\n{result}")
    except IdeaFinalized:
        update_job_completed(flow.state.run_id, status="completed")
        logger.info("Idea finalized without PRD generation (run_id=%s)",
                     flow.state.run_id)
        print(f"\n  ✦ Idea finalized and saved (run_id={flow.state.run_id})")
    except RequirementsFinalized:
        update_job_completed(flow.state.run_id, status="completed")
        logger.info(
            "Requirements finalized without PRD generation (run_id=%s)",
            flow.state.run_id,
        )
        print(
            f"\n  ✦ Requirements finalized and saved "
            f"(run_id={flow.state.run_id})"
        )
    except PauseRequested:
        approved = sum(1 for s in flow.state.draft.sections if s.is_approved)
        total = len(flow.state.draft.sections)
        update_job_completed(flow.state.run_id, status="paused")
        progress_file = flow.save_progress()
        print(f"\nProgress saved ({approved}/{total} sections approved).")
        if progress_file:
            print(f"  {progress_file}")
        print(f"Run 'crewai run' again to resume from where you left off.")
        logger.info("PRD flow paused by user (run_id=%s, %d/%d approved)",
                    flow.state.run_id, approved, total)
    except BillingError as e:
        approved = sum(1 for s in flow.state.draft.sections if s.is_approved)
        total = len(flow.state.draft.sections)
        update_job_completed(flow.state.run_id, status="paused")
        progress_file = flow.save_progress()
        logger.error("PRD flow paused due to billing error (run_id=%s): %s",
                     flow.state.run_id, e)
        print(f"\n{'=' * 60}")
        print(f"  BILLING / QUOTA ERROR")
        print(f"{'=' * 60}")
        print(f"  {e}")
        print(f"\n  Your progress has been saved ({approved}/{total} sections approved).")
        if progress_file:
            print(f"  {progress_file}")
        print(f"  Please fix your OpenAI billing or quota and then run")
        print(f"  'crewai run' to resume from where you left off.")
        print(f"{'=' * 60}")
    except LLMError as e:
        approved = sum(1 for s in flow.state.draft.sections if s.is_approved)
        total = len(flow.state.draft.sections)
        update_job_completed(flow.state.run_id, status="paused")
        progress_file = flow.save_progress()
        logger.error("PRD flow paused due to LLM error (run_id=%s): %s",
                     flow.state.run_id, e)
        print(f"\n{'=' * 60}")
        print(f"  LLM ERROR")
        print(f"{'=' * 60}")
        print(f"  {e}")
        print(f"\n  Your progress has been saved ({approved}/{total} sections approved).")
        if progress_file:
            print(f"  {progress_file}")
        print(f"  Please check your OpenAI API configuration and then run")
        print(f"  'crewai run' to resume from where you left off.")
        print(f"{'=' * 60}")
    except Exception as e:
        approved = sum(1 for s in flow.state.draft.sections if s.is_approved)
        total = len(flow.state.draft.sections)
        update_job_completed(flow.state.run_id, status="paused")
        progress_file = flow.save_progress()
        logger.error("PRD flow failed (kept inprogress): %s", e)
        print(f"\nPRD flow failed: {e}")
        print(f"Your progress has been saved ({approved}/{total} sections approved).")
        if progress_file:
            print(f"  {progress_file}")
        print(f"Run 'crewai run' to resume from where you left off.")


def run_prd_flow():
    """
    Run the iterative PRD generation flow (alias for ``run``).

    Usage:
        uv run run_prd_flow "Your feature idea here" [max_iterations]
    """
    run()


def start_api():
    """
    Start the FastAPI server for triggering flows via HTTP.

    Usage:
        uv run start_api                        # localhost:8000
        uv run start_api --ngrok                # with ngrok tunnel
        uv run start_api --port 3000            # custom port
        uv run start_api --host 0.0.0.0 --port 9000 --ngrok
    """
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Start the CrewAI Flow API server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--ngrok", action="store_true", help="Open an ngrok tunnel for remote access")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    logger.info("Starting API server on %s:%d", args.host, args.port)

    if args.ngrok:
        from crewai_productfeature_planner.scripts.ngrok_tunnel import start_tunnel
        public_url = start_tunnel(port=args.port)
        print(f"\n🌐 Ngrok tunnel: {public_url}")
        print(f"   Swagger docs: {public_url}/docs\n")

    uvicorn.run(
        "crewai_productfeature_planner.apis:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
