"""Idea Manager — unified agent for idea refinement and iteration advisory.

Consolidates the former Idea Refiner (iterative refinement) and Idea Agent
(in-thread Q&A) into a single module under one conceptual role.

Capabilities:
  1. **Iterative Refinement** — runs 3-10 self-critique cycles to enrich a
     raw product idea, presents alternative directions at decision points.
  2. **Real-time Q&A** — answers user questions about active iterations,
     provides steering recommendations for downstream agents.

LLM Tiers:
  - ``tier="research"`` — deep reasoning for refinement (default)
  - ``tier="basic"`` — fast conversational Q&A

Environment variables:

* ``IDEA_REFINER_MODEL`` — override the research-tier model
  (defaults to ``GEMINI_RESEARCH_MODEL`` → ``DEFAULT_GEMINI_RESEARCH_MODEL``).
* ``IDEA_AGENT_MODEL`` — override the basic-tier model
  (defaults to ``GEMINI_MODEL`` → ``DEFAULT_GEMINI_MODEL``).
* ``IDEA_REFINER_MIN_ITERATIONS`` — minimum refinement iterations (default 3).
* ``IDEA_REFINER_MAX_ITERATIONS`` — maximum refinement iterations (default 10).
* ``IDEA_AGENT_USE_CREWAI`` — force CrewAI path for Q&A (default: fast path).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable

import yaml
from crewai import Agent, Crew, Process, Task, LLM

from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_MIN_ITERATIONS = 3
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_LLM_TIMEOUT = 300
DEFAULT_LLM_MAX_RETRIES = 3
DEFAULT_BASIC_TIMEOUT = 120


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the idea manager's config directory."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── LLM Builders ─────────────────────────────────────────────


def _build_research_llm() -> LLM:
    """Build the research-tier LLM for iterative refinement.

    Resolution order: IDEA_REFINER_MODEL → GEMINI_RESEARCH_MODEL → default.
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
        "Idea Manager LLM (research): %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def _build_basic_llm() -> LLM:
    """Build the basic-tier LLM for conversational Q&A.

    Resolution order: IDEA_AGENT_MODEL → GEMINI_MODEL → default.
    """
    from crewai_productfeature_planner.agents.gemini_utils import (
        DEFAULT_GEMINI_MODEL,
        ensure_gemini_env,
    )

    ensure_gemini_env()

    model_name = os.environ.get(
        "IDEA_AGENT_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_BASIC_TIMEOUT)))
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES)))

    logger.info(
        "Idea Manager LLM (basic): %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


# ── Unified Agent Factory ─────────────────────────────────────


def create_idea_manager(
    *,
    tier: str = "research",
    project_id: str | None = None,
) -> Agent:
    """Create the Idea Manager agent.

    Parameters
    ----------
    tier:
        ``"research"`` (default) for iterative refinement tasks, or
        ``"basic"`` for real-time Q&A advisory tasks.
    project_id:
        Optional project identifier. When provided, the agent's backstory
        is enriched with project-level memory from MongoDB.

    Raises
    ------
    EnvironmentError
        When neither ``GOOGLE_API_KEY`` nor ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required "
            "to create the Idea Manager agent."
        )

    agent_config = _load_yaml("agent.yaml")["idea_manager"]
    logger.info(
        "Creating Idea Manager agent (tier='%s', role='%s')",
        tier, agent_config["role"].strip(),
    )

    if tier == "research":
        from crewai_productfeature_planner.scripts.knowledge_sources import (
            build_idea_refinement_knowledge_source,
            build_prd_knowledge_sources,
            get_google_embedder_config,
        )
        from crewai_productfeature_planner.scripts.memory_loader import enrich_backstory

        backstory = enrich_backstory(
            agent_config["backstory"].strip(), project_id,
        )

        return Agent(
            role=agent_config["role"].strip(),
            goal=agent_config["goal"].strip(),
            backstory=backstory,
            llm=_build_research_llm(),
            tools=[],
            verbose=is_verbose(),
            allow_delegation=False,
            reasoning=True,
            max_reasoning_attempts=3,
            knowledge_sources=[
                *build_prd_knowledge_sources(),
                build_idea_refinement_knowledge_source(),
            ],
            embedder=get_google_embedder_config(),
        )
    else:
        # Basic tier — fast Q&A, no knowledge sources needed
        return Agent(
            role=agent_config["role"].strip(),
            goal=agent_config["goal"].strip(),
            backstory=agent_config["backstory"].strip(),
            llm=_build_basic_llm(),
            tools=[],
            verbose=is_verbose(),
            allow_delegation=False,
            respect_context_window=True,
            max_iter=5,
        )


# ── Legacy compatibility aliases ──────────────────────────────


def create_idea_refiner(project_id: str | None = None) -> Agent:
    """Create the Idea Manager in research tier (legacy alias for Idea Refiner).

    Equivalent to ``create_idea_manager(tier="research", project_id=project_id)``.
    """
    return create_idea_manager(tier="research", project_id=project_id)


def create_idea_agent() -> Agent:
    """Create the Idea Manager in basic tier (legacy alias for Idea Agent).

    Equivalent to ``create_idea_manager(tier="basic")``.
    """
    return create_idea_manager(tier="basic")


# ── Iteration limits ──────────────────────────────────────────


def _get_iteration_limits() -> tuple[int, int]:
    """Return ``(min_iterations, max_iterations)`` from env or defaults."""
    min_iter = int(os.environ.get(
        "IDEA_REFINER_MIN_ITERATIONS", str(DEFAULT_MIN_ITERATIONS),
    ))
    max_iter = int(os.environ.get(
        "IDEA_REFINER_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS),
    ))
    min_iter = max(1, min(min_iter, 10))
    max_iter = max(min_iter, min(max_iter, 20))
    return min_iter, max_iter


# ── Score parsing and direction change detection ──────────────

_SCORE_RE = re.compile(r"(\d)\s*/?\s*5", re.IGNORECASE)


def parse_evaluation_scores(evaluation: str) -> list[int]:
    """Extract criterion scores (1-5) from an evaluation string."""
    return [int(m.group(1)) for m in _SCORE_RE.finditer(evaluation)]


def compute_average_confidence(evaluation: str) -> float:
    """Return the average score from an evaluation, or 5.0 if unparseable."""
    scores = parse_evaluation_scores(evaluation)
    if not scores:
        return 5.0
    return sum(scores) / len(scores)


def detect_direction_change(
    current_idea: str,
    previous_idea: str,
    *,
    threshold: float = 0.40,
) -> bool:
    """Return ``True`` when the current idea deviates significantly from the previous."""
    if not previous_idea:
        return False

    def _significant_words(text: str) -> set[str]:
        words = set(text.lower().split())
        return {w for w in words if len(w) > 3}

    curr_words = _significant_words(current_idea)
    prev_words = _significant_words(previous_idea)
    if not prev_words:
        return False
    overlap = len(curr_words & prev_words) / len(prev_words)
    return overlap < (1.0 - threshold)


# Callback type for presenting alternatives to the user.
OptionsCallback = Callable[[list[str], str, int, str], int]


def _generate_alternatives(
    agent: Agent,
    current_idea: str,
    task_configs: dict,
) -> list[str]:
    """Run the ``generate_alternatives_task`` and parse 3 options."""

    alt_task = Task(
        description=task_configs["generate_alternatives_task"]["description"].format(
            idea=current_idea,
        ),
        expected_output=task_configs["generate_alternatives_task"]["expected_output"],
        agent=agent,
    )
    crew = Crew(
        agents=[agent],
        tasks=[alt_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )
    result = crew_kickoff_with_retry(
        crew, step_label="idea_generate_alternatives",
    )
    return _parse_options(result.raw, current_idea)


def _parse_options(raw_text: str, fallback_idea: str) -> list[str]:
    """Parse 3 options from the alternatives task output."""
    parts = re.split(r"OPTION\s+\d+\s*:", raw_text, flags=re.IGNORECASE)
    options = [p.strip() for p in parts[1:] if p.strip()]
    while len(options) < 3:
        options.append(fallback_idea)
    return options[:3]


# ── Idea Refinement (formerly idea_refiner) ───────────────────


def refine_idea(
    raw_idea: str,
    run_id: str = "",
    project_id: str | None = None,
    options_callback: OptionsCallback | None = None,
) -> tuple[str, list[dict], list[dict]]:
    """Iteratively refine a raw idea using the Idea Manager agent (research tier).

    Runs between ``IDEA_REFINER_MIN_ITERATIONS`` and ``IDEA_REFINER_MAX_ITERATIONS``
    refinement cycles. Each cycle:
      1. Refine — the agent enriches the idea from an expert-user lens.
      2. Evaluate — the agent scores the refined idea; if ``IDEA_READY``
         appears (and min iterations met), the loop stops.

    At key decision points the agent generates 3 alternative directions
    and presents them via *options_callback*.

    Returns:
        A tuple of ``(final_idea, refinement_history, options_history)``.
    """

    min_iterations, max_iterations = _get_iteration_limits()
    task_configs = _load_yaml("tasks.yaml")
    agent = create_idea_manager(tier="research", project_id=project_id)

    current_idea = raw_idea
    previous_feedback = ""
    refinement_history: list[dict] = []
    options_history: list[dict] = []
    previous_idea_text = ""
    options_presented_this_run = False

    logger.info(
        "[IdeaManager] Starting refinement (min=%d, max=%d) for idea: '%s'",
        min_iterations, max_iterations, raw_idea[:80],
    )

    for iteration in range(1, max_iterations + 1):
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

        if hasattr(refine_task, "output") and refine_task.output:
            current_idea = refine_task.output.raw
        else:
            current_idea = result.raw

        evaluation = result.raw
        previous_feedback = evaluation

        logger.info(
            "[IdeaManager] Iteration %d/%d — refined (%d chars), "
            "evaluation (%d chars)",
            iteration, max_iterations, len(current_idea), len(evaluation),
        )

        refinement_history.append({
            "iteration": iteration,
            "idea": current_idea,
            "evaluation": evaluation,
        })

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
                    "[IdeaManager] Failed to save iteration %d: %s",
                    iteration, exc,
                )

        # ── 3-Options check at key decision points ─────────────
        avg_confidence = compute_average_confidence(evaluation)
        direction_changed = detect_direction_change(
            current_idea, previous_idea_text,
        )
        previous_idea_text = current_idea

        trigger: str | None = None
        if iteration == min_iterations:
            trigger = "auto_cycles_complete"
        elif avg_confidence < 3.0:
            trigger = "low_confidence"
        elif direction_changed:
            trigger = "direction_change"

        if trigger and not options_presented_this_run:
            options_presented_this_run = True
            logger.info(
                "[IdeaManager] Trigger '%s' at iteration %d — "
                "generating 3 alternative directions",
                trigger, iteration,
            )
            try:
                options = _generate_alternatives(
                    agent, current_idea, task_configs,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[IdeaManager] Failed to generate alternatives: %s",
                    exc,
                )
                options = []

            if options:
                if options_callback:
                    selected = options_callback(
                        options, run_id, iteration, trigger,
                    )
                    selected = max(0, min(selected, 2))
                else:
                    selected = 0
                    logger.info(
                        "[IdeaManager] Autonomous mode — auto-selected "
                        "option %d", selected + 1,
                    )

                options_entry = {
                    "iteration": iteration,
                    "trigger": trigger,
                    "options": options,
                    "selected": selected,
                }
                options_history.append(options_entry)
                current_idea = options[selected]
                logger.info(
                    "[IdeaManager] User selected option %d at iteration %d",
                    selected + 1, iteration,
                )

        if iteration >= min_iterations and "IDEA_READY" in evaluation.upper():
            logger.info(
                "[IdeaManager] Idea marked READY at iteration %d/%d",
                iteration, max_iterations,
            )
            break

        if iteration < max_iterations:
            logger.info(
                "[IdeaManager] Needs more refinement — continuing to iteration %d",
                iteration + 1,
            )

    logger.info(
        "[IdeaManager] Refinement complete (%d iterations, %d chars)",
        iteration, len(current_idea),
    )
    return current_idea, refinement_history, options_history


# ── Idea Query / Advisory (formerly idea_agent) ───────────────


def _extract_iteration_context(doc: dict) -> dict[str, str]:
    """Extract structured context from a working-idea MongoDB document."""
    from crewai_productfeature_planner.apis.prd._sections import SECTION_ORDER

    status = doc.get("status", "unknown")
    iteration = doc.get("iteration", 0)

    section_obj = doc.get("section") or {}
    completed_keys: list[str] = []
    remaining_keys: list[str] = []
    for key, label in SECTION_ORDER:
        if key == "executive_summary":
            raw_exec = doc.get("executive_summary", [])
            if isinstance(raw_exec, list) and raw_exec:
                completed_keys.append(label)
            else:
                remaining_keys.append(label)
        elif key in section_obj:
            entries = section_obj[key]
            if isinstance(entries, list) and entries:
                completed_keys.append(label)
            else:
                remaining_keys.append(label)
        else:
            remaining_keys.append(label)

    total = len(SECTION_ORDER)
    done = len(completed_keys)
    status_summary = (
        f"Status: {status} | Iteration: {iteration} | "
        f"Sections: {done}/{total} complete\n"
        f"Done: {', '.join(completed_keys) if completed_keys else '(none)'}\n"
        f"Remaining: {', '.join(remaining_keys) if remaining_keys else '(none)'}"
    )

    current_idea = doc.get("idea") or doc.get("finalized_idea") or "(no idea text)"

    refinement_history = "(no refinement history)"
    pipeline = doc.get("pipeline") or {}
    refine_steps = pipeline.get("refine_idea", [])
    if isinstance(refine_steps, list) and refine_steps:
        history_parts = []
        for entry in refine_steps[-5:]:
            it = entry.get("iteration", "?")
            content = (entry.get("content") or "")[:300]
            critique = (entry.get("critique") or "")[:200]
            history_parts.append(
                f"Iteration {it}:\n  Idea: {content}\n  Eval: {critique}"
            )
        refinement_history = "\n\n".join(history_parts)

    exec_summary = "(not started)"
    raw_exec = doc.get("executive_summary", [])
    if isinstance(raw_exec, list) and raw_exec:
        latest = raw_exec[-1]
        content = latest.get("content", "")[:500]
        critique = latest.get("critique", "")[:200]
        exec_summary = (
            f"Iteration {latest.get('iteration', '?')} "
            f"(of {len(raw_exec)} total):\n{content}"
        )
        if critique:
            exec_summary += f"\n\nCritique: {critique}"

    exec_prod_summary = ""
    if "executive_product_summary" in section_obj:
        eps_entries = section_obj["executive_product_summary"]
        if isinstance(eps_entries, list) and eps_entries:
            latest_eps = eps_entries[-1]
            eps_content = (latest_eps.get("content") or "")[:500]
            exec_summary += f"\n\n*CEO Review (Executive Product Summary):*\n{eps_content}"

    requirements = "(not started)"
    req_steps = pipeline.get("requirements_breakdown", [])
    if isinstance(req_steps, list) and req_steps:
        latest_req = req_steps[-1]
        requirements = (latest_req.get("content") or "")[:800]

    eng_plan = "(not started)"
    eng_steps = pipeline.get("engineering_plan", [])
    if isinstance(eng_steps, list) and eng_steps:
        latest_eng = eng_steps[-1]
        eng_plan = (latest_eng.get("content") or "")[:800]
    elif "engineering_plan" in section_obj:
        eng_entries = section_obj["engineering_plan"]
        if isinstance(eng_entries, list) and eng_entries:
            eng_plan = (eng_entries[-1].get("content") or "")[:800]

    completed_sections = "(no sections completed yet)"
    if completed_keys:
        parts = []
        for key, label in SECTION_ORDER:
            if key in ("executive_summary", "executive_product_summary",
                        "engineering_plan"):
                continue
            if key in section_obj:
                entries = section_obj[key]
                if isinstance(entries, list) and entries:
                    latest = entries[-1]
                    content = (latest.get("content") or "")[:400]
                    parts.append(f"*{label}:*\n{content}")
        completed_sections = "\n\n".join(parts) if parts else "(none)"

    critiques = "(no active critiques)"
    critique_parts = []
    for key, label in SECTION_ORDER:
        if key in section_obj:
            entries = section_obj[key]
            if isinstance(entries, list) and entries:
                latest = entries[-1]
                crit = latest.get("critique") or ""
                if crit:
                    critique_parts.append(
                        f"*{label}:* {crit[:200]}"
                    )
    if critique_parts:
        critiques = "\n".join(critique_parts)

    return {
        "status_summary": status_summary,
        "current_idea": current_idea[:2000],
        "refinement_history": refinement_history,
        "executive_summary": exec_summary,
        "requirements_breakdown": requirements,
        "engineering_plan": eng_plan,
        "completed_sections": completed_sections,
        "active_critiques": critiques,
    }


def handle_idea_query(
    user_message: str,
    flow_doc: dict,
    conversation_history: list[dict] | None = None,
) -> str:
    """Run the Idea Manager to answer a user question about an active iteration.

    Uses a **direct Gemini REST API call** to avoid CrewAI framework
    overhead (~2-4 s). Falls back to CrewAI when
    ``IDEA_AGENT_USE_CREWAI=true`` or when the fast path fails.
    """
    use_crewai = os.environ.get(
        "IDEA_AGENT_USE_CREWAI", ""
    ).strip().lower() in ("true", "1", "yes")

    if not use_crewai:
        result = _handle_idea_query_fast(
            user_message, flow_doc, conversation_history,
        )
        if result is not None:
            return result
        logger.warning("[IdeaManager] Fast path failed — falling back to CrewAI")

    return _handle_idea_query_crewai(
        user_message, flow_doc, conversation_history,
    )


def _handle_idea_query_fast(
    user_message: str,
    flow_doc: dict,
    conversation_history: list[dict] | None,
) -> str | None:
    """Fast path: direct Gemini REST API call (~200-800 ms)."""
    from crewai_productfeature_planner.tools.gemini_chat import (
        generate_chat_response,
    )

    agent_config = _load_yaml("agent.yaml")["idea_manager"]
    task_configs = _load_yaml("tasks.yaml")

    history_str = "(no prior conversation)"
    if conversation_history:
        history_str = json.dumps(
            conversation_history[-10:], ensure_ascii=False,
        )

    ctx = _extract_iteration_context(flow_doc)

    system_prompt = (
        f"Role: {agent_config['role'].strip()}\n"
        f"Goal: {agent_config['goal'].strip()}\n\n"
        f"{agent_config['backstory'].strip()}"
    )

    task_description = task_configs["idea_query_task"]["description"].format(
        user_message=user_message,
        conversation_history=history_str,
        **ctx,
    )
    expected_output = task_configs["idea_query_task"]["expected_output"]
    user_prompt = f"{task_description}\n\n## Expected Output\n{expected_output}"

    model = os.environ.get(
        "IDEA_AGENT_MODEL",
        os.environ.get("GEMINI_MODEL", ""),
    ).strip() or None

    logger.info(
        "[IdeaManager] Fast path for run_id=%s: '%s'",
        flow_doc.get("run_id", "?"), user_message[:80],
    )

    response = generate_chat_response(
        system_prompt=system_prompt,
        user_message=user_prompt,
        conversation_history=conversation_history,
    )

    if response:
        logger.info(
            "[IdeaManager] Fast response (%d chars): '%s'",
            len(response), response[:200],
        )
    return response


def _handle_idea_query_crewai(
    user_message: str,
    flow_doc: dict,
    conversation_history: list[dict] | None,
) -> str:
    """Slow path: CrewAI Crew.kickoff() (~3-5 s)."""

    task_configs = _load_yaml("tasks.yaml")
    agent = create_idea_manager(tier="basic")

    history_str = "(no prior conversation)"
    if conversation_history:
        history_str = json.dumps(
            conversation_history[-10:], ensure_ascii=False,
        )

    ctx = _extract_iteration_context(flow_doc)

    task = Task(
        description=task_configs["idea_query_task"]["description"].format(
            user_message=user_message,
            conversation_history=history_str,
            **ctx,
        ),
        expected_output=task_configs["idea_query_task"]["expected_output"],
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    logger.info(
        "[IdeaManager] CrewAI path for run_id=%s: '%s'",
        flow_doc.get("run_id", "?"), user_message[:80],
    )

    result = crew_kickoff_with_retry(crew, step_label="idea_manager_query")
    response = str(result).strip()

    logger.info(
        "[IdeaManager] CrewAI response (%d chars): '%s'",
        len(response), response[:200],
    )
    return response


def extract_steering_feedback(response: str) -> str | None:
    """Extract steering recommendation from Idea Manager response.

    Returns the instruction text if a ``## Steering Recommendation``
    section is found, otherwise ``None``.
    """
    marker = "## Steering Recommendation"
    idx = response.find(marker)
    if idx == -1:
        marker_alt = "*Steering Recommendation*"
        idx = response.find(marker_alt)
        if idx == -1:
            return None
        marker = marker_alt

    section = response[idx + len(marker):].strip()

    for line in section.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("**instruction**:") or \
           stripped.lower().startswith("*instruction*:"):
            return stripped.split(":", 1)[1].strip()

    return section[:500] if section else None
