"""Gemini-powered Idea Refinement agent factory and runner.

Creates an agent that acts as an industry-expert user to iteratively
refine a raw product idea before PRD generation.  Uses Google Gemini
exclusively.

The agent identifies the relevant industry from the idea, adopts the
persona of a domain expert, and runs 3-10 self-critique iterations
until the idea is rich enough for a PRD.

Environment variables:

* ``IDEA_REFINER_MIN_ITERATIONS`` — minimum refinement iterations
  (default 3).
* ``IDEA_REFINER_MAX_ITERATIONS`` — maximum refinement iterations
  (default 10).
* ``IDEA_REFINER_MODEL`` — override the Gemini model used
  (defaults to ``GEMINI_RESEARCH_MODEL`` → ``DEFAULT_GEMINI_RESEARCH_MODEL``).
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
from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_MIN_ITERATIONS = 3
DEFAULT_MAX_ITERATIONS = 10

# Re-use Gemini defaults from the Gemini PM agent.
DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the idea refiner's config directory."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_refiner_llm() -> LLM:
    """Build the Gemini LLM for the idea refiner agent.

    Uses the **research** model tier because idea refinement involves
    deep iterative reasoning (3-10 self-critique cycles).

    Resolution order for model name:
        1. ``IDEA_REFINER_MODEL`` env var
        2. ``GEMINI_RESEARCH_MODEL`` env var
        3. Hard-coded default (``DEFAULT_GEMINI_RESEARCH_MODEL``)
    """
    from crewai_productfeature_planner.agents.gemini_utils import (
        DEFAULT_GEMINI_RESEARCH_MODEL,
        ensure_gemini_env,
    )

    ensure_gemini_env()

    model_name = os.environ.get(
        "IDEA_REFINER_MODEL",
        os.environ.get("GEMINI_RESEARCH_MODEL", DEFAULT_GEMINI_RESEARCH_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info(
        "Idea Refiner LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_idea_refiner(project_id: str | None = None) -> Agent:
    """Create the Idea Refinement agent powered by Google Gemini.

    Args:
        project_id: Optional project identifier.  When provided, the
            agent's backstory is enriched with project-level memory
            (guardrails, knowledge, tech stack) from MongoDB.

    Raises ``EnvironmentError`` when neither ``GOOGLE_API_KEY`` nor
    ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required "
            "to create the Idea Refinement agent."
        )

    agent_config = _load_yaml("agent.yaml")["idea_refiner"]
    logger.info(
        "Creating Idea Refiner agent (role='%s')",
        agent_config["role"].strip(),
    )

    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_refiner_llm(),
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
        "IDEA_REFINER_MIN_ITERATIONS", str(DEFAULT_MIN_ITERATIONS),
    ))
    max_iter = int(os.environ.get(
        "IDEA_REFINER_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS),
    ))
    # Sanity clamp
    min_iter = max(1, min(min_iter, 10))
    max_iter = max(min_iter, min(max_iter, 20))
    return min_iter, max_iter


def refine_idea(
    raw_idea: str,
    run_id: str = "",
    project_id: str | None = None,
) -> tuple[str, list[dict]]:
    """Iteratively refine a raw idea using the Gemini-powered refiner agent.

    Runs between ``IDEA_REFINER_MIN_ITERATIONS`` (default 3) and
    ``IDEA_REFINER_MAX_ITERATIONS`` (default 10) refinement cycles.
    Each cycle:
      1. Refine — the agent enriches the idea from an expert-user lens.
      2. Evaluate — the agent scores the refined idea; if ``IDEA_READY``
         appears in the output (and min iterations met), the loop stops.

    When *run_id* is provided each iteration is persisted to the
    ``workingIdeas`` collection so that the refinement history is
    auditable.

    Args:
        raw_idea: The raw feature idea string from the user.
        run_id: Optional flow run identifier for MongoDB persistence.
        project_id: Optional project identifier for memory enrichment.

    Returns:
        A tuple of ``(final_idea, refinement_history)`` where
        *refinement_history* is a list of dicts, each containing
        ``iteration``, ``idea``, and ``evaluation``.
    """
    min_iterations, max_iterations = _get_iteration_limits()
    task_configs = _load_yaml("tasks.yaml")
    agent = create_idea_refiner(project_id=project_id)

    current_idea = raw_idea
    previous_feedback = ""
    refinement_history: list[dict] = []

    logger.info(
        "[IdeaRefiner] Starting refinement (min=%d, max=%d) for idea: '%s'",
        min_iterations, max_iterations, raw_idea[:80],
    )

    for iteration in range(1, max_iterations + 1):
        # ── Build dual-task Crew: Refine → Evaluate ───────────
        # Uses context chaining so the evaluate task receives the
        # refined idea automatically via Process.sequential.
        feedback_section = (
            f"Previous evaluation feedback:\n{previous_feedback}"
            if previous_feedback
            else "This is the first iteration — no prior feedback."
        )

        refine_task = Task(
            description=task_configs["refine_idea_task"]["description"].format(
                idea=current_idea,
                iteration=iteration,
                max_iterations=max_iterations,
                previous_feedback=feedback_section,
            ),
            expected_output=task_configs["refine_idea_task"]["expected_output"],
            agent=agent,
        )

        evaluate_task = Task(
            description=task_configs["evaluate_quality_task"]["description"].format(
                refined_idea="{Use the refined idea from the previous task}",
                iteration=iteration,
                max_iterations=max_iterations,
                min_iterations=min_iterations,
            ),
            expected_output=task_configs["evaluate_quality_task"]["expected_output"],
            agent=agent,
            context=[refine_task],
        )

        crew = Crew(
            agents=[agent],
            tasks=[refine_task, evaluate_task],
            process=Process.sequential,
            verbose=is_verbose(),
        )
        result = crew_kickoff_with_retry(
            crew, step_label=f"idea_refine_evaluate_iter{iteration}",
        )

        # Extract individual task outputs from the sequential crew.
        # refine_task.output is populated after kickoff; the crew
        # result itself is the last task's (evaluation) output.
        if hasattr(refine_task, "output") and refine_task.output:
            current_idea = refine_task.output.raw
        else:
            # Fallback: if task output attribute is unavailable,
            # the evaluation context includes the refined idea.
            current_idea = result.raw

        evaluation = result.raw
        previous_feedback = evaluation

        logger.info(
            "[IdeaRefiner] Iteration %d/%d — refined (%d chars), "
            "evaluation (%d chars)",
            iteration, max_iterations, len(current_idea), len(evaluation),
        )

        # Record this iteration in history
        refinement_history.append({
            "iteration": iteration,
            "idea": current_idea,
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
                    idea=raw_idea,
                    pipeline_key="refine_idea",
                    iteration=iteration,
                    content=current_idea,
                    critique=evaluation,
                    step=f"refine_idea_{iteration}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[IdeaRefiner] Failed to save iteration %d: %s",
                    iteration, exc,
                )

        # Check if ready (only after min iterations)
        if iteration >= min_iterations and "IDEA_READY" in evaluation.upper():
            logger.info(
                "[IdeaRefiner] Idea marked READY at iteration %d/%d",
                iteration, max_iterations,
            )
            break

        if iteration < max_iterations:
            logger.info(
                "[IdeaRefiner] Needs more refinement — continuing to iteration %d",
                iteration + 1,
            )

    logger.info(
        "[IdeaRefiner] Refinement complete (%d iterations, %d chars)",
        iteration, len(current_idea),
    )
    return current_idea, refinement_history
