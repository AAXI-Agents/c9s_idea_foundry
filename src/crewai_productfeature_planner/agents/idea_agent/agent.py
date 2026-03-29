"""Idea Agent — in-thread analyst for active idea iterations.

Answers user questions about the current iteration state (refined idea,
sections, critiques, requirements) and produces steering recommendations
that other agents can incorporate into subsequent iterations.

Uses the **basic** Gemini model tier since this is a conversational
Q&A task — no deep reasoning required.

Environment variables:

* ``IDEA_AGENT_MODEL`` — override the Gemini model used
  (defaults to ``GEMINI_MODEL`` → ``DEFAULT_GEMINI_MODEL``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Crew, Process, Task, LLM

from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose

logger = get_logger(__name__)
CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_LLM_TIMEOUT = 120
DEFAULT_LLM_MAX_RETRIES = 3


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the idea agent's config directory."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_idea_agent_llm() -> LLM:
    """Build the Gemini LLM for the idea agent.

    Uses the **basic** model tier — fast conversational Q&A.
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

    timeout = int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_LLM_TIMEOUT)))
    max_retries = int(
        os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES))
    )

    logger.info(
        "Idea Agent LLM: %s (timeout=%ds, max_retries=%d)",
        model_name, timeout, max_retries,
    )
    return LLM(model=model_name, timeout=timeout, max_retries=max_retries)


def create_idea_agent() -> Agent:
    """Create the Idea Agent powered by Google Gemini.

    Raises ``EnvironmentError`` when neither ``GOOGLE_API_KEY`` nor
    ``GOOGLE_CLOUD_PROJECT`` is set.
    """
    has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
    has_project = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not has_api_key and not has_project:
        raise EnvironmentError(
            "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT is required "
            "to create the Idea Agent."
        )

    agent_config = _load_yaml("agent.yaml")["idea_agent"]
    logger.info(
        "Creating Idea Agent (role='%s')",
        agent_config["role"].strip(),
    )

    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=agent_config["backstory"].strip(),
        llm=_build_idea_agent_llm(),
        tools=[],
        verbose=is_verbose(),
        allow_delegation=False,
        respect_context_window=True,
        max_iter=5,
    )


# ── Context extraction from MongoDB document ──────────────────


def _extract_iteration_context(doc: dict) -> dict[str, str]:
    """Extract structured context from a working-idea MongoDB document.

    Returns a dict with keys matching the task template placeholders.
    """
    from crewai_productfeature_planner.apis.prd._sections import SECTION_ORDER

    status = doc.get("status", "unknown")
    iteration = doc.get("iteration", 0)

    # Status summary
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

    # Current idea
    current_idea = doc.get("idea") or doc.get("finalized_idea") or "(no idea text)"

    # Refinement history from pipeline steps
    refinement_history = "(no refinement history)"
    pipeline = doc.get("pipeline") or {}
    refine_steps = pipeline.get("refine_idea", [])
    if isinstance(refine_steps, list) and refine_steps:
        history_parts = []
        for entry in refine_steps[-5:]:  # Last 5 iterations
            it = entry.get("iteration", "?")
            content = (entry.get("content") or "")[:300]
            critique = (entry.get("critique") or "")[:200]
            history_parts.append(
                f"Iteration {it}:\n  Idea: {content}\n  Eval: {critique}"
            )
        refinement_history = "\n\n".join(history_parts)

    # Executive summary
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

    # Check for executive_product_summary (CEO review) in sections
    exec_prod_summary = ""
    if "executive_product_summary" in section_obj:
        eps_entries = section_obj["executive_product_summary"]
        if isinstance(eps_entries, list) and eps_entries:
            latest_eps = eps_entries[-1]
            eps_content = (latest_eps.get("content") or "")[:500]
            exec_summary += f"\n\n*CEO Review (Executive Product Summary):*\n{eps_content}"

    # Requirements breakdown
    requirements = "(not started)"
    req_steps = pipeline.get("requirements_breakdown", [])
    if isinstance(req_steps, list) and req_steps:
        latest_req = req_steps[-1]
        requirements = (latest_req.get("content") or "")[:800]

    # Engineering plan
    eng_plan = "(not started)"
    eng_steps = pipeline.get("engineering_plan", [])
    if isinstance(eng_steps, list) and eng_steps:
        latest_eng = eng_steps[-1]
        eng_plan = (latest_eng.get("content") or "")[:800]
    elif "engineering_plan" in section_obj:
        eng_entries = section_obj["engineering_plan"]
        if isinstance(eng_entries, list) and eng_entries:
            eng_plan = (eng_entries[-1].get("content") or "")[:800]

    # Completed sections content
    completed_sections = "(no sections completed yet)"
    if completed_keys:
        parts = []
        for key, label in SECTION_ORDER:
            if key in ("executive_summary", "executive_product_summary",
                        "engineering_plan"):
                continue  # Already shown above
            if key in section_obj:
                entries = section_obj[key]
                if isinstance(entries, list) and entries:
                    latest = entries[-1]
                    content = (latest.get("content") or "")[:400]
                    parts.append(f"*{label}:*\n{content}")
        completed_sections = "\n\n".join(parts) if parts else "(none)"

    # Active critiques
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


# ── Main entry point ─────────────────────────────────────────


def handle_idea_query(
    user_message: str,
    flow_doc: dict,
    conversation_history: list[dict] | None = None,
) -> str:
    """Run the Idea Agent to answer a user question about an active iteration.

    Uses a **direct Gemini REST API call** to avoid CrewAI framework
    overhead (~2-4 s).  Falls back to CrewAI when
    ``IDEA_AGENT_USE_CREWAI=true`` or when the fast path fails.

    Args:
        user_message: The user's raw message text.
        flow_doc: The full working-idea MongoDB document.
        conversation_history: Optional prior thread messages.

    Returns:
        The agent's response text.
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
        logger.warning("[IdeaAgent] Fast path failed — falling back to CrewAI")

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

    agent_config = _load_yaml("agent.yaml")["idea_agent"]
    task_configs = _load_yaml("tasks.yaml")

    # Build conversation history string
    history_str = "(no prior conversation)"
    if conversation_history:
        history_str = json.dumps(
            conversation_history[-10:], ensure_ascii=False,
        )

    # Extract rich context from the working-idea document
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
        "[IdeaAgent] Fast path for run_id=%s: '%s'",
        flow_doc.get("run_id", "?"), user_message[:80],
    )

    response = generate_chat_response(
        system_prompt=system_prompt,
        user_message=user_prompt,
        conversation_history=conversation_history,
    )

    if response:
        logger.info(
            "[IdeaAgent] Fast response (%d chars): '%s'",
            len(response), response[:200],
        )
    return response


def _handle_idea_query_crewai(
    user_message: str,
    flow_doc: dict,
    conversation_history: list[dict] | None,
) -> str:
    """Slow path: CrewAI Crew.kickoff() (~3-5 s)."""
    from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

    task_configs = _load_yaml("tasks.yaml")
    agent = create_idea_agent()

    # Build conversation history string
    history_str = "(no prior conversation)"
    if conversation_history:
        history_str = json.dumps(
            conversation_history[-10:], ensure_ascii=False,
        )

    # Extract rich context from the working-idea document
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
        "[IdeaAgent] CrewAI path for run_id=%s: '%s'",
        flow_doc.get("run_id", "?"), user_message[:80],
    )

    result = crew_kickoff_with_retry(crew, step_label="idea_agent_query")
    response = str(result).strip()

    logger.info(
        "[IdeaAgent] CrewAI response (%d chars): '%s'",
        len(response), response[:200],
    )
    return response


def extract_steering_feedback(response: str) -> str | None:
    """Extract steering recommendation from Idea Agent response.

    If the response contains a ``## Steering Recommendation`` section,
    returns the instruction text that can be appended to the next
    agent's context.  Otherwise returns ``None``.
    """
    marker = "## Steering Recommendation"
    idx = response.find(marker)
    if idx == -1:
        # Try Slack-compatible bold marker
        marker_alt = "*Steering Recommendation*"
        idx = response.find(marker_alt)
        if idx == -1:
            return None
        marker = marker_alt

    section = response[idx + len(marker):].strip()

    # Extract just the Instruction line if present
    for line in section.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("**instruction**:") or \
           stripped.lower().startswith("*instruction*:"):
            return stripped.split(":", 1)[1].strip()

    # Return the full section (truncated) if no specific instruction
    return section[:500] if section else None
