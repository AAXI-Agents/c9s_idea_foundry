"""Interactive CLI prompts — idea input, refinement, and approval.

Functions that handle user interaction during the PRD generation
flow: getting ideas, choosing refinement modes, manual iteration,
and approval gates.
"""

import sys

from crewai_productfeature_planner.mongodb import save_executive_summary
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _track_cli(*, user_message: str, intent: str, agent_response: str,
               idea: str | None = None, run_id: str | None = None,
               metadata: dict | None = None) -> None:
    """Best-effort tracking of a CLI interaction."""
    try:
        from crewai_productfeature_planner.mongodb.agent_interactions.repository import (
            log_interaction,
        )
        log_interaction(
            source="cli",
            user_message=user_message,
            intent=intent,
            agent_response=agent_response,
            idea=idea,
            run_id=run_id,
            user_id="cli_user",
            metadata=metadata,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to log CLI interaction", exc_info=True)


def _get_idea() -> str:
    """Get the feature idea from CLI args or interactive prompt.

    Resolution order:
        1. ``sys.argv[1]`` — passed as CLI argument
        2. Interactive ``input()`` prompt
    """
    if len(sys.argv) >= 2:
        idea = sys.argv[1]
    else:
        idea = input("Enter your product feature idea: ").strip()
    _track_cli(
        user_message=idea,
        intent="create_prd",
        agent_response="Idea captured from CLI input",
        idea=idea,
    )
    return idea


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
            _track_cli(
                user_message=choice,
                intent="refinement_mode",
                agent_response="Agent refinement mode selected",
            )
            return "agent"
        if choice in ("m", "manual"):
            _track_cli(
                user_message=choice,
                intent="refinement_mode",
                agent_response="Manual refinement mode selected",
            )
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
                _track_cli(
                    user_message=choice,
                    intent="manual_refinement_approve",
                    agent_response="Manual refinement approved",
                    idea=current,
                    run_id=run_id,
                    metadata={"iteration": iteration},
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
            _track_cli(
                user_message=revised,
                intent="manual_refinement_edit",
                agent_response="Idea revised by user",
                idea=current,
                run_id=run_id,
                metadata={"iteration": iteration},
            )
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
            _track_cli(
                user_message=choice,
                intent="idea_approval",
                agent_response="Idea approved — proceeding to section drafting",
                idea=refined_idea,
                run_id=run_id,
            )
            return False  # continue to section drafting
        if choice in ("c", "cancel"):
            logger.info(
                "[IdeaApproval] User cancelled — exiting CLI (run_id=%s)",
                run_id,
            )
            _track_cli(
                user_message=choice,
                intent="idea_approval",
                agent_response="Idea cancelled by user",
                idea=refined_idea,
                run_id=run_id,
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
            _track_cli(
                user_message=choice,
                intent="requirements_approval",
                agent_response="Requirements approved — proceeding to PRD sections",
                idea=idea,
                run_id=run_id,
            )
            return False  # continue to section drafting
        if choice in ("c", "cancel"):
            logger.info(
                "[RequirementsApproval] User cancelled — exiting CLI "
                "(run_id=%s)",
                run_id,
            )
            _track_cli(
                user_message=choice,
                intent="requirements_approval",
                agent_response="Requirements cancelled by user",
                idea=idea,
                run_id=run_id,
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
