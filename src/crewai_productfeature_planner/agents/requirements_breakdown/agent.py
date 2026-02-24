"""Gemini-powered Requirements Breakdown agent factory and runner.

Creates an agent that takes a refined product idea and decomposes it
into structured, implementation-ready product requirements.  Each
feature includes data entities, state machines, AI augmentation
points, and API contract sketches — ready for a data architect.

The agent runs iterative breakdown → evaluation cycles (similar to the
Idea Refiner) until the requirements are detailed enough.

Environment variables:

* ``REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS`` — minimum breakdown
  iterations (default 3).
* ``REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS`` — maximum breakdown
  iterations (default 10).
* ``REQUIREMENTS_BREAKDOWN_MODEL`` — override the Gemini model used
  (defaults to ``GEMINI_MODEL`` → ``DEFAULT_GEMINI_MODEL``).
"""

import os
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task, LLM

from crewai_productfeature_planner.scripts.knowledge_sources import (
    build_prd_knowledge_sources,
    get_google_embedder_config,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_MIN_ITERATIONS = 3
DEFAULT_MAX_ITERATIONS = 10

# Re-use Gemini defaults from the Gemini PM agent.
DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the requirements breakdown config dir."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_breakdown_llm() -> LLM:
    """Build the Gemini LLM for the requirements breakdown agent.

    Resolution order for model name:
        1. ``REQUIREMENTS_BREAKDOWN_MODEL`` env var
        2. ``GEMINI_MODEL`` env var
        3. Hard-coded default (same as Gemini PM)
    """
    from crewai_productfeature_planner.agents.gemini_utils import (
        DEFAULT_GEMINI_MODEL,
        ensure_gemini_env,
    )

    ensure_gemini_env()

    model_name = os.environ.get(
        "REQUIREMENTS_BREAKDOWN_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info(
        "Requirements Breakdown LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_requirements_breakdown_agent() -> Agent:
    """Create the Requirements Breakdown agent powered by Google Gemini.

    Raises ``EnvironmentError`` when neither ``GOOGLE_API_KEY`` nor
    ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required "
            "to create the Requirements Breakdown agent."
        )

    agent_config = _load_yaml("agent.yaml")["requirements_breakdown"]
    logger.info(
        "Creating Requirements Breakdown agent (role='%s')",
        agent_config["role"].strip(),
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=agent_config["backstory"].strip(),
        llm=_build_breakdown_llm(),
        tools=[],  # Pure reasoning — no external tools needed
        verbose=is_verbose(),
        allow_delegation=False,
        reasoning=True,
        max_reasoning_attempts=3,
        knowledge_sources=build_prd_knowledge_sources(),
        embedder=get_google_embedder_config(),
    )


def _get_iteration_limits() -> tuple[int, int]:
    """Return ``(min_iterations, max_iterations)`` from env or defaults."""
    min_iter = int(os.environ.get(
        "REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS", str(DEFAULT_MIN_ITERATIONS),
    ))
    max_iter = int(os.environ.get(
        "REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS),
    ))
    # Sanity clamp
    min_iter = max(1, min(min_iter, 10))
    max_iter = max(min_iter, min(max_iter, 20))
    return min_iter, max_iter


def breakdown_requirements(
    refined_idea: str,
    run_id: str = "",
) -> tuple[str, list[dict]]:
    """Iteratively break down a refined idea into product requirements.

    Runs between ``REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS`` (default 3)
    and ``REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS`` (default 10) cycles.
    Each cycle:
      1. Breakdown — the agent decomposes the idea into features with
         entities, state machines, AI augmentation, and API contracts.
      2. Evaluate — the agent scores completeness; if
         ``REQUIREMENTS_READY`` appears (and min iterations met), the
         loop stops.

    When *run_id* is provided each iteration is persisted to the
    ``workingIdeas`` collection.

    Args:
        refined_idea: The refined product idea string.
        run_id: Optional flow run identifier for MongoDB persistence.

    Returns:
        A tuple of ``(final_requirements, breakdown_history)`` where
        *breakdown_history* is a list of dicts, each containing
        ``iteration``, ``requirements``, and ``evaluation``.
    """
    min_iterations, max_iterations = _get_iteration_limits()
    task_configs = _load_yaml("tasks.yaml")
    agent = create_requirements_breakdown_agent()

    current_requirements = ""
    previous_feedback = ""
    breakdown_history: list[dict] = []

    logger.info(
        "[RequirementsBreakdown] Starting breakdown (min=%d, max=%d) "
        "for idea: '%s'",
        min_iterations, max_iterations, refined_idea[:80],
    )

    for iteration in range(1, max_iterations + 1):
        # ── Build dual-task Crew: Breakdown → Evaluate ────────
        # Uses context chaining so the evaluate task receives the
        # breakdown output automatically via Process.sequential.
        feedback_section = (
            f"Previous evaluation feedback:\n{previous_feedback}"
            if previous_feedback
            else "This is the first iteration — no prior feedback."
        )

        # On iteration 1 there are no prior requirements; on subsequent
        # iterations the agent receives its own output to build upon.
        if current_requirements:
            prev_reqs_section = current_requirements
        else:
            prev_reqs_section = (
                "(First iteration — no prior requirements. "
                "Generate the initial breakdown from the idea above.)"
            )

        breakdown_task = Task(
            description=task_configs["breakdown_requirements_task"][
                "description"
            ].format(
                idea=refined_idea,
                iteration=iteration,
                max_iterations=max_iterations,
                previous_feedback=feedback_section,
                previous_requirements=prev_reqs_section,
            ),
            expected_output=task_configs["breakdown_requirements_task"][
                "expected_output"
            ],
            agent=agent,
        )

        evaluate_task = Task(
            description=task_configs["evaluate_requirements_task"][
                "description"
            ].format(
                requirements="{Use the requirements from the previous task}",
                iteration=iteration,
                max_iterations=max_iterations,
                min_iterations=min_iterations,
            ),
            expected_output=task_configs["evaluate_requirements_task"][
                "expected_output"
            ],
            agent=agent,
            context=[breakdown_task],
        )

        crew = Crew(
            agents=[agent],
            tasks=[breakdown_task, evaluate_task],
            process=Process.sequential,
            verbose=is_verbose(),
        )
        result = crew_kickoff_with_retry(
            crew, step_label=f"req_breakdown_evaluate_iter{iteration}",
        )

        # Extract individual task outputs from the sequential crew.
        # breakdown_task.output is populated after kickoff; the crew
        # result itself is the last task's (evaluation) output.
        if hasattr(breakdown_task, "output") and breakdown_task.output:
            current_requirements = breakdown_task.output.raw
        else:
            # Fallback: use the raw result (evaluation) which contains
            # context from the breakdown.
            current_requirements = result.raw

        evaluation = result.raw
        previous_feedback = evaluation

        logger.info(
            "[RequirementsBreakdown] Iteration %d/%d — "
            "requirements (%d chars), evaluation (%d chars)",
            iteration, max_iterations,
            len(current_requirements), len(evaluation),
        )

        # Record this iteration in history
        breakdown_history.append({
            "iteration": iteration,
            "requirements": current_requirements,
            "evaluation": evaluation,
        })

        # Persist to workingIdeas when run_id is available
        if run_id:
            try:
                from crewai_productfeature_planner.mongodb import (
                    save_pipeline_step,
                )

                save_pipeline_step(
                    run_id=run_id,
                    idea=refined_idea,
                    pipeline_key="requirements_breakdown",
                    iteration=iteration,
                    content=current_requirements,
                    critique=evaluation,
                    step=f"requirements_breakdown_{iteration}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[RequirementsBreakdown] Failed to save iteration "
                    "%d: %s",
                    iteration, exc,
                )

        # Check if ready (only after min iterations)
        if (
            iteration >= min_iterations
            and "REQUIREMENTS_READY" in evaluation.upper()
        ):
            logger.info(
                "[RequirementsBreakdown] Requirements marked READY at "
                "iteration %d/%d",
                iteration, max_iterations,
            )
            break

        if iteration < max_iterations:
            logger.info(
                "[RequirementsBreakdown] Needs more detail — continuing "
                "to iteration %d",
                iteration + 1,
            )

    logger.info(
        "[RequirementsBreakdown] Breakdown complete (%d iterations, "
        "%d chars)",
        iteration,  # noqa: F821 — always defined by the loop
        len(current_requirements),
    )
    return current_requirements, breakdown_history
