#!/usr/bin/env python
"""CLI entry points for the CrewAI Product Feature Planner.

This module provides the three console-script entry points registered
in ``pyproject.toml``:

* ``run()`` / ``run_prd_flow()`` — interactive CLI for PRD generation
* ``start_api()`` — FastAPI server launcher

Heavy logic is delegated to sub-modules:
* ``_cli_state``       — PRD state restoration & assembly from MongoDB
* ``_cli_project``     — Project selection, creation & memory config
* ``_cli_refinement``  — Idea input, refinement & approval gates
* ``_cli_startup``     — Startup process cleanup, delivery & recovery
"""
import sys
import warnings

from crewai_productfeature_planner.flows.prd_flow import (
    IdeaFinalized,
    PauseRequested,
    PRDFlow,
    RequirementsFinalized,
)
from crewai_productfeature_planner.mongodb import (
    ensure_section_field,
    find_completed_without_output,
    find_unfinalized,
    get_db,
    get_run_documents,
    mark_completed,
    save_executive_summary,
    save_iteration,
    save_output_file,
    save_pipeline_step,
)
from crewai_productfeature_planner.mongodb.crew_jobs import (
    create_job,
    fail_incomplete_jobs_on_startup,
    reactivate_job,
    update_job_completed,
    update_job_started,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.scripts.retry import BillingError, LLMError

# ── Re-export sub-module symbols into this namespace ─────────────────
# Tests use @patch("crewai_productfeature_planner.main.<name>") to mock
# these functions.  Star-importing them ensures they exist as module-
# level attributes so unittest.mock.patch can find them.
from crewai_productfeature_planner._cli_state import (  # noqa: F401
    _assemble_prd_from_doc,
    _check_resumable_runs,
    _max_iteration_from_doc,
    _restore_prd_state,
)
from crewai_productfeature_planner._cli_project import (  # noqa: F401
    _configure_project_memory_cli,
    _create_project_interactive,
    _offer_memory_configuration,
    _save_project_link,
    _select_or_create_project,
)
from crewai_productfeature_planner._cli_refinement import (  # noqa: F401
    _approve_refined_idea,
    _approve_requirements,
    _choose_refinement_mode,
    _get_idea,
    _manual_idea_refinement,
    _prompt_next_action,
)
from crewai_productfeature_planner._cli_startup import (  # noqa: F401
    _CREW_PROCESS_NAMES,
    _confluence_completed_in_output,
    _extract_confluence_url,
    _generate_missing_outputs,
    _jira_completed_in_output,
    _kill_stale_crew_processes,
    _publish_unpublished_prds,
    _run_startup_delivery,
    _run_startup_delivery_background,
)

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
# Suppress FutureWarning from the deprecated google-generativeai package.
# We no longer use it directly (switched to google-vertex / google-genai SDK),
# but chromadb still imports it transitively.
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

logger = get_logger(__name__)


# ── Entry points ─────────────────────────────────────────────────────


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
        # Step 1: Select or create a project
        project_id, project_name = _select_or_create_project()
        _offer_memory_configuration(project_id, project_name)
        _run_single_flow(idea=sys.argv[1], project_id=project_id)
        return

    # Step 1: Select or create a project (once per session)
    project_id, project_name = _select_or_create_project()
    _offer_memory_configuration(project_id, project_name)

    # Interactive loop — keeps offering new ideas after each run
    idea = None
    while True:
        _run_single_flow(idea=idea, project_id=project_id)
        next_idea = _prompt_next_action()
        if next_idea is None:
            print("\nGoodbye!")
            return
        idea = next_idea


def _run_single_flow(
    idea: str | None = None,
    *,
    project_id: str | None = None,
) -> None:
    """Execute one PRD flow cycle (new or resumed).

    Args:
        idea: When supplied, skip the resume check and use this idea directly.
        project_id: The project configuration to link this run to.
            When provided, ``save_project_ref`` is called after the
            working-idea document is created so that publishing can
            resolve project-level Confluence/Jira keys.
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
                if project_id:
                    _save_project_link(flow.state.run_id, project_id)
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

        # Link working idea to project configuration
        if project_id:
            _save_project_link(flow.state.run_id, project_id)

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
        if project_id:
            _save_project_link(flow.state.run_id, project_id)
        update_job_completed(flow.state.run_id, status="completed")
        logger.info("Idea finalized without PRD generation (run_id=%s)",
                     flow.state.run_id)
        print(f"\n  ✦ Idea finalized and saved (run_id={flow.state.run_id})")
    except RequirementsFinalized:
        if project_id:
            _save_project_link(flow.state.run_id, project_id)
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
        if project_id:
            _save_project_link(flow.state.run_id, project_id)
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
        if project_id:
            _save_project_link(flow.state.run_id, project_id)
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
        if project_id:
            _save_project_link(flow.state.run_id, project_id)
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
        if project_id:
            _save_project_link(flow.state.run_id, project_id)
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

    from crewai_productfeature_planner.version import get_version
    logger.info(
        "Starting API server v%s on %s:%d",
        get_version(), args.host, args.port,
    )

    if args.ngrok:
        from crewai_productfeature_planner.scripts.ngrok_tunnel import start_tunnel
        public_url = start_tunnel(port=args.port)
        print(f"\n🌐 Ngrok tunnel: {public_url}")
        print(f"   Swagger docs: {public_url}/docs\n")

        # Auto-update Slack app request URLs to match the new tunnel.
        from crewai_productfeature_planner.scripts.slack_config import update_slack_app_urls
        update_slack_app_urls(public_url)

    uvicorn.run(
        "crewai_productfeature_planner.apis:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
