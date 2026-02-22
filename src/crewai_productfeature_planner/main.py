#!/usr/bin/env python
import sys
import warnings

from crewai_productfeature_planner.apis.prd.models import AGENT_OPENAI, AGENT_GEMINI, PRDDraft, SECTION_ORDER, get_default_agent
from crewai_productfeature_planner.flows.prd_flow import PAUSE_SENTINEL, IdeaFinalized, PauseRequested, PRDFlow, RequirementsFinalized
from crewai_productfeature_planner.mongodb import find_unfinalized, get_run_documents, mark_completed, save_finalized, save_iteration
from crewai_productfeature_planner.scripts.retry import BillingError, LLMError
from crewai_productfeature_planner.mongodb.crew_jobs import (
    create_job,
    fail_incomplete_jobs_on_startup,
    reactivate_job,
    update_job_completed,
    update_job_failed,
    update_job_started,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

logger = get_logger(__name__)


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
        created = run.get("created_at", "")
        if hasattr(created, "strftime"):
            created = created.strftime("%Y-%m-%d %H:%M")
        print(
            f"  [{i}] run_id={run['run_id']}  iter={run['iteration']}  "
            f"sections={len(sections)}  created={created}"
        )
        idea_preview = (run.get("idea") or "")[:80]
        print(f"      idea: {idea_preview}")
    print(f"  [n] Start a new idea")
    print(f"{'=' * 60}\n")

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
    """Rebuild a PRDFlow with its state restored from MongoDB documents.

    Reads all working documents for the run, reconstructs the PRDDraft
    with section content and approval status, and sets the flow to resume
    from the next unapproved section.
    """
    run_id = run_info["run_id"]
    idea = run_info["idea"]
    docs = get_run_documents(run_id)

    draft = PRDDraft.create_empty()
    section_keys_set = {key for key, _ in SECTION_ORDER}

    # Replay documents to reconstruct section state
    for doc in docs:
        section_key = doc.get("section_key", "")
        step = doc.get("step", "")
        draft_obj = doc.get("draft", {})
        critique = doc.get("critique", "")

        # Extract section content from the draft dict
        if isinstance(draft_obj, dict):
            content = draft_obj.get(section_key, "")
        else:
            # Backward-compat: legacy docs stored draft as a plain string
            content = draft_obj or ""

        if section_key and section_key in section_keys_set:
            section = draft.get_section(section_key)
            if section is None:
                continue

            # Update content with the latest draft for this section
            if content:
                section.content = content
            if critique:
                section.critique = critique
            section.iteration = max(section.iteration, doc.get("iteration", 0))

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

    # Calculate total iterations
    total_iterations = max((d.get("iteration", 0) for d in docs), default=0)

    flow = PRDFlow()
    flow.state.run_id = run_id
    flow.state.idea = idea
    flow.state.draft = draft
    flow.state.iteration = total_iterations

    next_section = draft.next_section()
    if next_section:
        flow.state.current_section_key = next_section.key

    approved_count = sum(1 for s in draft.sections if s.is_approved)
    logger.info(
        "Restored PRD state: run_id=%s, %d/%d sections approved, iteration=%d",
        run_id, approved_count, len(draft.sections), total_iterations,
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
                save_iteration(
                    run_id=run_id,
                    idea=current,
                    iteration=iteration,
                    draft={"idea_refinement": current},
                    step=f"idea_manual_{iteration}",
                    section_key="idea_refinement",
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
      * ``[y]es``  — finalize the idea: save to ``finalizeIdeas``, mark
        the working idea as completed, and **stop** (no PRD generation).
      * ``[c]ontinue`` — proceed to PRD section generation.

    Args:
        refined_idea: The idea after refinement.
        original_idea: The raw idea before refinement.
        run_id: The current flow run identifier.
        refinement_history: List of iteration dicts from the refinement
            process.  Persisted alongside the finalized idea.

    Returns:
        ``True`` to finalize (stop), ``False`` to continue to PRD.
    """
    history = refinement_history or []
    print(f"\n{'=' * 60}")
    print("  Idea Refinement Complete")
    print(f"{'=' * 60}")
    if original_idea:
        print(f"  Original ({len(original_idea)} chars) → Refined ({len(refined_idea)} chars)")
    print(f"\n{refined_idea}\n")
    print(f"{'=' * 60}")
    print("  [y] Approve — finalize this idea and save")
    print("  [c] Continue — proceed to PRD generation")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose action [y/c]: ").strip().lower()
        if choice in ("y", "yes"):
            logger.info(
                "[IdeaApproval] User approved refined idea (run_id=%s, %d chars)",
                run_id, len(refined_idea),
            )
            # Persist the finalized idea
            save_finalized(
                run_id=run_id,
                idea=refined_idea,
                iteration=len(history),
                final_prd="",
                original_idea=original_idea,
                finalized_type="idea",
                refinement_history=history,
            )
            mark_completed(run_id)
            return True
        if choice in ("c", "continue"):
            logger.info(
                "[IdeaApproval] User chose to continue to PRD generation (run_id=%s)",
                run_id,
            )
            return False
        print("Please enter 'y' to approve or 'c' to continue to PRD.")


def _approve_requirements(
    requirements: str,
    idea: str,
    run_id: str,
    breakdown_history: list[dict] | None = None,
) -> bool:
    """Show the requirements breakdown and let the user finalize or continue.

    This is used as the ``requirements_approval_callback`` on PRDFlow.
    It is called after the requirements breakdown agent completes.

    Displays the final requirements and offers:
      * ``[y]es``  — finalize the requirements: save to ``finalizeIdeas``,
        mark the working idea as completed, and **stop** (no PRD).
      * ``[c]ontinue`` — proceed to PRD section generation with the
        requirements as additional context.

    Args:
        requirements: The structured requirements breakdown.
        idea: The (possibly refined) product idea.
        run_id: The current flow run identifier.
        breakdown_history: Iteration history from the breakdown process.

    Returns:
        ``True`` to finalize (stop), ``False`` to continue to PRD.
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
    print("  [y] Approve — finalize these requirements and save")
    print("  [c] Continue — proceed to PRD generation")
    print(f"{'=' * 60}\n")

    while True:
        choice = input("Choose action [y/c]: ").strip().lower()
        if choice in ("y", "yes"):
            logger.info(
                "[RequirementsApproval] User approved requirements "
                "(run_id=%s, %d chars)",
                run_id, len(requirements),
            )
            # Persist the finalized requirements
            save_finalized(
                run_id=run_id,
                idea=idea,
                iteration=len(history),
                final_prd="",
                requirements_breakdown=requirements,
                finalized_type="requirements",
                breakdown_history=history,
            )
            mark_completed(run_id)
            return True
        if choice in ("c", "continue"):
            logger.info(
                "[RequirementsApproval] User chose to continue to PRD "
                "(run_id=%s)",
                run_id,
            )
            return False
        print("Please enter 'y' to approve or 'c' to continue to PRD.")


def _cli_approval_callback(iteration: int, section_key: str, agent_results: dict[str, str], draft, **kwargs) -> "tuple[str, bool | str] | str":
    """Interactive CLI callback — show agent results and let user pick & approve.

    When multiple agents produced results, the user first chooses which
    agent's output to keep, then decides whether to approve or refine.

    Returns:
        ``(agent_name, True)`` to approve using *agent_name*'s result,
        ``(agent_name, False)`` to refine, ``(agent_name, feedback)`` for
        user-provided critique, or ``PAUSE_SENTINEL`` to pause.
    """
    section = draft.get_section(section_key)
    step = section.step if section else "?"
    total = len(draft.sections)

    agent_names = list(agent_results.keys())
    multi = len(agent_names) > 1

    # --- Display agent results ------------------------------------------
    dropped = kwargs.get("dropped_agents", [])
    agent_errors = kwargs.get("agent_errors", {})
    idea_refined = kwargs.get("idea_refined", False)
    print(f"\n{'=' * 60}")
    print(f"  Step {step}/{total}: {section_key} — Iteration {iteration}")
    if idea_refined and step == 1 and iteration == 1:
        print(f"  ✦ Idea was enriched by the Idea Refinement agent")
    if multi:
        print(f"  {len(agent_names)} agent(s) produced results")
    if dropped:
        print(f"  Dropped agents: {', '.join(dropped)}")
        for agent_name in dropped:
            err = agent_errors.get(agent_name, "unknown error")
            label = _agent_display_name(agent_name)
            print(f"    ✖ {label}: {err}")
    print(f"{'=' * 60}")

    for idx, (agent_name, content) in enumerate(agent_results.items(), 1):
        label = _agent_display_name(agent_name)
        print(f"\n--- [{idx}] {label} ---")
        print(content[:2000])
        if len(content) > 2000:
            print(f"\n... ({len(content) - 2000} more chars) ...")
    print(f"\n{'=' * 60}")

    # --- Agent selection ------------------------------------------------
    if multi:
        selected = _select_agent(agent_names)
    else:
        selected = agent_names[0]

    # --- Action selection -----------------------------------------------
    print()
    while True:
        answer = (
            input(
                "Choose action — [y]es to approve / [n]o to refine "
                "/ [f]eedback to provide critique / [p]ause & save: "
            )
            .strip()
            .lower()
        )
        if answer in ("y", "yes"):
            return (selected, True)
        if answer in ("n", "no"):
            return (selected, False)
        if answer in ("p", "pause"):
            return PAUSE_SENTINEL
        if answer in ("f", "feedback"):
            print("Enter your critique feedback (press Enter twice to finish):")
            lines: list[str] = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            feedback = "\n".join(lines).strip()
            if feedback:
                return (selected, feedback)
            print("Empty feedback — please try again.")
        else:
            print("Please enter 'y', 'n', 'f', or 'p'.")


def _agent_display_name(agent_name: str) -> str:
    """Human-readable label for an agent key."""
    default = get_default_agent()
    names = {
        AGENT_OPENAI: "OpenAI PM",
        AGENT_GEMINI: "Gemini PM",
    }
    label = names.get(agent_name, agent_name)
    if agent_name == default:
        label += " (default)"
    return label


def _select_agent(agent_names: list[str]) -> str:
    """Prompt user to pick one of the available agents."""
    print("\nSelect which agent's result to use:")
    for idx, name in enumerate(agent_names, 1):
        print(f"  [{idx}] {_agent_display_name(name)}")
    while True:
        choice = input(f"Enter 1-{len(agent_names)}: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(agent_names):
                selected = agent_names[idx]
                print(f"  → Selected: {_agent_display_name(selected)}")
                return selected
        except ValueError:
            pass
        print(f"Please enter 1-{len(agent_names)}.")


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


def run():
    """
    Run the PRD generation flow with interactive approval.

    On startup, checks MongoDB for unfinalized working ideas and offers
    to resume from where the user left off.

    Usage:
        crewai run                              # interactive prompt
        crewai run "Add dark mode to dashboard" # idea as argument
    """
    # Startup recovery: mark any incomplete jobs as failed
    try:
        recovered = fail_incomplete_jobs_on_startup()
        if recovered:
            print(f"  Recovered {recovered} incomplete job(s) from previous run.")
    except Exception as exc:
        logger.debug("Startup recovery failed: %s", exc)

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
            next_section = resumed_flow.state.draft.next_section()
            if next_section:
                total = len(resumed_flow.state.draft.sections)
                print(f"Next: Step {next_section.step}/{total} — {next_section.title}")
            approved = sum(1 for s in resumed_flow.state.draft.sections if s.is_approved)
            print(f"Progress: {approved}/{len(resumed_flow.state.draft.sections)} sections approved\n")

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
        flow.approval_callback = _cli_approval_callback
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
            save_finalized(
                run_id=flow.state.run_id,
                idea=flow.state.idea,
                iteration=flow.state.iteration,
                final_prd=final_prd,
                confluence_xhtml=confluence_xhtml,
            )
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
        print(f"\nProgress saved ({approved}/{total} sections approved).")
        print(f"Run 'crewai run' again to resume from where you left off.")
        logger.info("PRD flow paused by user (run_id=%s, %d/%d approved)",
                    flow.state.run_id, approved, total)
    except BillingError as e:
        approved = sum(1 for s in flow.state.draft.sections if s.is_approved)
        total = len(flow.state.draft.sections)
        update_job_completed(flow.state.run_id, status="paused")
        logger.error("PRD flow paused due to billing error (run_id=%s): %s",
                     flow.state.run_id, e)
        print(f"\n{'=' * 60}")
        print(f"  BILLING / QUOTA ERROR")
        print(f"{'=' * 60}")
        print(f"  {e}")
        print(f"\n  Your progress has been saved ({approved}/{total} sections approved).")
        print(f"  Please fix your OpenAI billing or quota and then run")
        print(f"  'crewai run' to resume from where you left off.")
        print(f"{'=' * 60}")
    except LLMError as e:
        approved = sum(1 for s in flow.state.draft.sections if s.is_approved)
        total = len(flow.state.draft.sections)
        update_job_completed(flow.state.run_id, status="paused")
        logger.error("PRD flow paused due to LLM error (run_id=%s): %s",
                     flow.state.run_id, e)
        print(f"\n{'=' * 60}")
        print(f"  LLM ERROR")
        print(f"{'=' * 60}")
        print(f"  {e}")
        print(f"\n  Your progress has been saved ({approved}/{total} sections approved).")
        print(f"  Please check your OpenAI API configuration and then run")
        print(f"  'crewai run' to resume from where you left off.")
        print(f"{'=' * 60}")
    except Exception as e:
        update_job_failed(flow.state.run_id, error=str(e))
        logger.error("PRD flow failed: %s", e)
        print(f"\nPRD flow failed: {e}")
        print(f"Your progress has been saved. Run 'crewai run' to resume.")


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
