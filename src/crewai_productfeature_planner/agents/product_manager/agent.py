"""Product Manager agent factory, configuration loader, and requirements breakdown.

Consolidates the former Product Manager and Requirements Breakdown agents
into a single module under one unified role.

Supports both OpenAI and Gemini LLM backends through a single unified
factory.  The ``provider`` parameter (``"openai"`` or ``"gemini"``)
controls which LLM is used:

* **openai** — uses ``OPENAI_RESEARCH_MODEL`` env var (default from
  ``DEFAULT_OPENAI_RESEARCH_MODEL``).
* **gemini** — uses ``GEMINI_PM_MODEL`` / ``GEMINI_RESEARCH_MODEL``
  env var (default from ``DEFAULT_GEMINI_RESEARCH_MODEL``).  Requires
  ``GOOGLE_API_KEY`` or ``GOOGLE_CLOUD_PROJECT``.

The Product Manager performs deep-thinking tasks (PRD section drafting,
requirements breakdown, critique, refinement) and uses the **research**
model tier.

Environment variables for requirements breakdown:

* ``REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS`` — minimum iterations (default 3).
* ``REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS`` — maximum iterations (default 10).
* ``REQUIREMENTS_BREAKDOWN_MODEL`` — override model (defaults to
  ``GEMINI_RESEARCH_MODEL`` → ``DEFAULT_GEMINI_RESEARCH_MODEL``).
"""

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.agents.gemini_utils import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GEMINI_RESEARCH_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_RESEARCH_MODEL,
    ensure_gemini_env,
)
from crewai_productfeature_planner.scripts.knowledge_sources import (
    build_prd_knowledge_sources,
    get_google_embedder_config,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry
from crewai_productfeature_planner.tools.file_read_tool import create_file_read_tool
from crewai_productfeature_planner.tools.directory_read_tool import create_directory_read_tool

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

# Recognised LLM provider identifiers.
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"

# LLM timeout / retry defaults.  Reasoning models (o3) can take 60-120 s;
# a generous default avoids premature timeouts while still failing eventually.
DEFAULT_LLM_TIMEOUT = 300      # seconds
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file from the agent's config directory."""
    logger.debug("Loading YAML config: %s", filename)
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_tools() -> list:
    """Assemble the full toolkit for the Product Manager agent.

    Tools included:
        - FileReadTool: Read knowledge files, existing PRDs, reference docs
        - DirectoryReadTool: List output and knowledge directories

    Note: PRDFileWriteTool is intentionally excluded — file writing is
    handled programmatically by finalize() and save_progress() to
    prevent the LLM from creating uncontrolled output files.

    Web research tools (SerperDevTool, ScrapeWebsiteTool,
    WebsiteSearchTool) were removed — the PRD workflow generates
    content from the user's idea and knowledge sources; the LLM never
    invoked internet search during section drafting.
    """
    logger.debug("Assembling Product Manager toolkit (2 tools)")
    return [
        create_file_read_tool(),
        create_directory_read_tool(directory="output/prds"),
    ]


def _build_llm(
    provider: str = PROVIDER_OPENAI,
    *,
    model_tier: str = "research",
) -> LLM:
    """Build the LLM for the Product Manager agent.

    Parameters
    ----------
    provider:
        ``"openai"`` or ``"gemini"``.
    model_tier:
        ``"research"`` (default) uses deep-reasoning models for complex
        sections; ``"basic"`` uses fast models for structured/derivative
        sections.

    **Research tier** resolution (default — complex reasoning):
        - Gemini: ``GEMINI_PM_MODEL`` → ``GEMINI_RESEARCH_MODEL`` → ``gemini-3.1-pro-preview``
        - OpenAI: ``OPENAI_RESEARCH_MODEL`` → ``o3``

    **Basic tier** resolution (structured/derivative content):
        - Gemini: ``GEMINI_MODEL`` → ``gemini-3-flash-preview``
        - OpenAI: ``OPENAI_MODEL`` → ``gpt-4.1-mini``

    Timeout and retry behaviour are controlled via:
        - ``LLM_TIMEOUT``      — request timeout in seconds (default 300)
        - ``LLM_MAX_RETRIES``  — number of retries on transient errors (default 3)
    """
    if model_tier == "basic":
        # Fast model for structured/derivative sections
        if provider == PROVIDER_GEMINI:
            ensure_gemini_env()
            model_name = os.environ.get(
                "GEMINI_MODEL", DEFAULT_GEMINI_MODEL,
            ).strip()
            if "/" not in model_name:
                model_name = f"gemini/{model_name}"
        else:
            model_name = os.environ.get(
                "OPENAI_MODEL", DEFAULT_OPENAI_MODEL,
            ).strip()
            if "/" not in model_name:
                model_name = f"openai/{model_name}"
    else:
        # Research model for complex reasoning sections
        if provider == PROVIDER_GEMINI:
            ensure_gemini_env()
            model_name = os.environ.get(
                "GEMINI_PM_MODEL",
                os.environ.get("GEMINI_RESEARCH_MODEL", DEFAULT_GEMINI_RESEARCH_MODEL),
            ).strip()
            if "/" not in model_name:
                model_name = f"gemini/{model_name}"
        else:
            model_name = os.environ.get(
                "OPENAI_RESEARCH_MODEL", DEFAULT_OPENAI_RESEARCH_MODEL,
            ).strip()
            if "/" not in model_name:
                model_name = f"openai/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info("Product Manager LLM (%s, tier=%s): %s (timeout=%ds, max_retries=%d)",
                provider, model_tier, model_name, timeout, max_retries)
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_product_manager(
    provider: str = PROVIDER_OPENAI,
    project_id: str | None = None,
    *,
    model_tier: str = "research",
) -> Agent:
    """Create a fully configured Product Manager agent.

    Parameters
    ----------
    provider:
        LLM backend — ``"openai"`` (default) or ``"gemini"``.
    project_id:
        Optional project identifier.  When provided, the agent's
        backstory is enriched with project-level memory entries
        (guardrails, knowledge, tech stack) from MongoDB.
    model_tier:
        ``"research"`` (default) for deep-reasoning sections or
        ``"basic"`` for structured/derivative sections.

    Raises
    ------
    EnvironmentError
        When *provider* is ``"gemini"`` and neither ``GOOGLE_API_KEY``
        nor ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    if provider == PROVIDER_GEMINI:
        has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
        has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if not has_api_key and not has_project:
            raise EnvironmentError(
                "Gemini Product Manager requires GOOGLE_API_KEY or "
                "GOOGLE_CLOUD_PROJECT to be set."
            )

    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info("Creating Product Manager agent (provider='%s', tier='%s', role='%s')",
                provider, model_tier, agent_config["role"].strip())

    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_llm(provider=provider, model_tier=model_tier),
        tools=_build_tools(),
        verbose=is_verbose(),
        allow_delegation=False,
        reasoning=True,
        max_reasoning_attempts=3,
        knowledge_sources=build_prd_knowledge_sources(),
        embedder=get_google_embedder_config(),
    )


# ── Lightweight critic agent ─────────────────────────────────────────

# Default timeout / retry for the critic — shorter timeout since the
# basic model responds faster.
DEFAULT_CRITIC_TIMEOUT = 120      # seconds
DEFAULT_CRITIC_MAX_RETRIES = 3


def _build_critic_llm() -> LLM:
    """Build a lightweight LLM for the critic agent.

    Uses the **basic** model tier (``GEMINI_CRITIC_MODEL`` /
    ``GEMINI_MODEL`` / ``DEFAULT_GEMINI_MODEL``) because critique is
    a judgment / evaluation task — not deep generation.

    Resolution order for model name:
        1. ``GEMINI_CRITIC_MODEL`` env var
        2. ``GEMINI_MODEL`` env var
        3. Hard-coded default (``DEFAULT_GEMINI_MODEL`` — flash)

    Always uses Gemini (regardless of the drafting agent's provider)
    because it offers the fastest inference for evaluation tasks.
    """
    ensure_gemini_env()

    model_name = os.environ.get(
        "GEMINI_CRITIC_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get(
        "CRITIC_LLM_TIMEOUT",
        os.environ.get("LLM_TIMEOUT", str(DEFAULT_CRITIC_TIMEOUT)),
    ))
    max_retries = int(os.environ.get(
        "LLM_MAX_RETRIES", str(DEFAULT_CRITIC_MAX_RETRIES),
    ))

    logger.info(
        "Critic LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_product_manager_critic(
    project_id: str | None = None,
) -> Agent:
    """Create a lightweight critic agent for evaluating PRD sections.

    The critic is optimised for speed:
      - Uses the **basic** (flash) model tier instead of research
      - Has **no tools** — critique is pure text evaluation
      - Uses cached knowledge sources (shared with the drafter)
      - Retains ``reasoning=True, max_reasoning_attempts=3``

    The critic evaluates drafts against a checklist and produces a
    readiness score.  It does not draft, refine, or call external
    APIs.

    Parameters
    ----------
    project_id:
        Optional project identifier.  When provided, the critic's
        backstory is enriched with project-level memory from MongoDB.

    Raises
    ------
    EnvironmentError
        When neither ``GOOGLE_API_KEY`` nor ``GOOGLE_CLOUD_PROJECT``
        is set (required for the Gemini basic model).
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Critic agent requires GOOGLE_API_KEY or "
            "GOOGLE_CLOUD_PROJECT to be set."
        )

    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info(
        "Creating Product Manager critic agent (role='%s')",
        agent_config["role"].strip(),
    )

    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_critic_llm(),
        tools=[],                       # No tools — pure text evaluation
        verbose=is_verbose(),
        allow_delegation=False,
        reasoning=True,
        max_reasoning_attempts=3,
        # No knowledge_sources / embedder — the critic is a pure
        # evaluation agent.  RAG retrieval adds per-call overhead
        # that is unnecessary for scoring an already-drafted section.
    )


def get_task_configs() -> dict:
    """Load task configurations for the Product Manager."""
    logger.debug("Loading Product Manager task configs")
    return _load_yaml("tasks.yaml")


# ── Requirements Breakdown (consolidated from former agent) ───────────

DEFAULT_REQUIREMENTS_MIN_ITERATIONS = 3
DEFAULT_REQUIREMENTS_MAX_ITERATIONS = 10


def _build_requirements_llm() -> LLM:
    """Build the Gemini LLM for requirements breakdown.

    Resolution order: REQUIREMENTS_BREAKDOWN_MODEL → GEMINI_RESEARCH_MODEL → default.
    """
    ensure_gemini_env()

    model_name = os.environ.get(
        "REQUIREMENTS_BREAKDOWN_MODEL",
        os.environ.get("GEMINI_RESEARCH_MODEL", DEFAULT_GEMINI_RESEARCH_MODEL),
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


def create_requirements_breakdown_agent(
    project_id: str | None = None,
) -> Agent:
    """Create the Requirements Breakdown agent (Product Manager in architect mode).

    Uses the unified Product Manager config with a research-tier Gemini
    model specialised for requirements decomposition.

    Args:
        project_id: Optional project identifier for memory enrichment.

    Raises ``EnvironmentError`` when Gemini credentials are missing.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required "
            "to create the Requirements Breakdown agent."
        )

    agent_config = _load_yaml("agent.yaml")["product_manager"]
    logger.info(
        "Creating Requirements Breakdown agent (role='%s')",
        agent_config["role"].strip(),
    )

    backstory = enrich_backstory(
        agent_config["backstory"].strip(), project_id,
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=backstory,
        llm=_build_requirements_llm(),
        tools=[],
        verbose=is_verbose(),
        allow_delegation=False,
        reasoning=True,
        max_reasoning_attempts=3,
        knowledge_sources=build_prd_knowledge_sources(),
        embedder=get_google_embedder_config(),
    )


def _get_requirements_iteration_limits() -> tuple[int, int]:
    """Return ``(min_iterations, max_iterations)`` for requirements breakdown."""
    min_iter = int(os.environ.get(
        "REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS",
        str(DEFAULT_REQUIREMENTS_MIN_ITERATIONS),
    ))
    max_iter = int(os.environ.get(
        "REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS",
        str(DEFAULT_REQUIREMENTS_MAX_ITERATIONS),
    ))
    min_iter = max(1, min(min_iter, 10))
    max_iter = max(min_iter, min(max_iter, 20))
    return min_iter, max_iter


def breakdown_requirements(
    refined_idea: str,
    run_id: str = "",
    original_idea: str = "",
    project_id: str | None = None,
) -> tuple[str, list[dict]]:
    """Iteratively break down a refined idea into product requirements.

    Runs between ``REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS`` and
    ``REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS`` cycles. Each cycle:
      1. Breakdown — decompose into features with entities, state machines,
         AI augmentation, and API contracts.
      2. Evaluate — score completeness; if ``REQUIREMENTS_READY`` appears
         (and min iterations met), the loop stops.

    Returns:
        A tuple of ``(final_requirements, breakdown_history)``.
    """
    from crewai import Crew, Process, Task

    min_iterations, max_iterations = _get_requirements_iteration_limits()
    task_configs = _load_yaml("tasks.yaml")
    agent = create_requirements_breakdown_agent(project_id=project_id)

    current_requirements = ""
    previous_feedback = ""
    breakdown_history: list[dict] = []

    logger.info(
        "[RequirementsBreakdown] Starting breakdown (min=%d, max=%d) "
        "for idea: '%s'",
        min_iterations, max_iterations, refined_idea[:80],
    )

    for iteration in range(1, max_iterations + 1):
        feedback_section = (
            f"Previous evaluation feedback:\n{previous_feedback}"
            if previous_feedback
            else "This is the first iteration — no prior feedback."
        )

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

        if hasattr(breakdown_task, "output") and breakdown_task.output:
            current_requirements = breakdown_task.output.raw
        else:
            current_requirements = result.raw

        evaluation = result.raw
        previous_feedback = evaluation

        logger.info(
            "[RequirementsBreakdown] Iteration %d/%d — "
            "requirements (%d chars), evaluation (%d chars)",
            iteration, max_iterations,
            len(current_requirements), len(evaluation),
        )

        breakdown_history.append({
            "iteration": iteration,
            "requirements": current_requirements,
            "evaluation": evaluation,
        })

        if run_id:
            try:
                from crewai_productfeature_planner.mongodb import (
                    save_pipeline_step,
                )

                save_pipeline_step(
                    run_id=run_id,
                    idea=original_idea or refined_idea,
                    pipeline_key="requirements_breakdown",
                    iteration=iteration,
                    content=current_requirements,
                    critique=evaluation,
                    step=f"requirements_breakdown_{iteration}",
                    finalized_idea=refined_idea,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[RequirementsBreakdown] Failed to save iteration "
                    "%d: %s",
                    iteration, exc,
                )

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
