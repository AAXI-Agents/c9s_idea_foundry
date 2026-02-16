#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from crewai_productfeature_planner.apis.prd.models import AGENT_OPENAI, AGENT_GEMINI, PRDDraft, SECTION_ORDER, get_default_agent
from crewai_productfeature_planner.crew import CrewaiProductfeaturePlanner
from crewai_productfeature_planner.flows.prd_flow import PAUSE_SENTINEL, PauseRequested, PRDFlow
from crewai_productfeature_planner.mongodb import find_unfinalized, get_run_documents, mark_completed, save_finalized
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


def _cli_approval_callback(iteration: int, section_key: str, agent_results: dict[str, str], draft) -> "tuple[str, bool | str] | str":
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
    print(f"\n{'=' * 60}")
    print(f"  Step {step}/{total}: {section_key} — Iteration {iteration}")
    if multi:
        print(f"  {len(agent_names)} agent(s) produced results")
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

    # Track job in crewJobs — reactivate for resumes, create for new runs
    if resumed_flow is not None:
        reactivate_job(flow.state.run_id)
    else:
        create_job(job_id=flow.state.run_id, flow_name="prd", idea=idea)
    update_job_started(flow.state.run_id)

    logger.info("Starting PRD flow (idea='%s')", idea)
    try:
        flow.approval_callback = _cli_approval_callback
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


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    logger.info("Starting crew training (iterations=%s)", sys.argv[1])
    try:
        CrewaiProductfeaturePlanner().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)
        logger.info("Crew training completed")
    except Exception as e:
        logger.error("Crew training failed: %s", e)
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    logger.info("Starting crew replay (task_id=%s)", sys.argv[1])
    try:
        CrewaiProductfeaturePlanner().crew().replay(task_id=sys.argv[1])
        logger.info("Crew replay completed")
    except Exception as e:
        logger.error("Crew replay failed: %s", e)
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }

    logger.info("Starting crew test (iterations=%s, llm=%s)", sys.argv[1], sys.argv[2])
    try:
        CrewaiProductfeaturePlanner().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)
        logger.info("Crew test completed")
    except Exception as e:
        logger.error("Crew test failed: %s", e)
        raise Exception(f"An error occurred while testing the crew: {e}")

def run_with_trigger():
    """
    Run the crew with trigger payload.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    logger.info("Starting crew run with trigger payload")
    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        logger.error("Invalid JSON trigger payload")
        raise Exception("Invalid JSON payload provided as argument")

    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",
        "current_year": ""
    }

    try:
        result = CrewaiProductfeaturePlanner().crew().kickoff(inputs=inputs)
        logger.info("Crew trigger run completed")
        return result
    except Exception as e:
        logger.error("Crew trigger run failed: %s", e)
        raise Exception(f"An error occurred while running the crew with trigger: {e}")


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
