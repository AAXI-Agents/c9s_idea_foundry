"""Ideation agent factory — creates CrewAI agents for each ideation step.

Each step in the ideation flow is powered by a specialist agent with a
C-suite persona:
    a) CEO & Founder — Product Visionary
    b) Product Manager — User Research Lead
    c) Product Manager & UX Architect
    d) CEO & Product Manager — Goal Strategist
    e) CTO & Staff Engineer — Technical Architect

All steps output structured JSON via ``StructuredIdeationResponse``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Crew, Process, Task, LLM

from crewai_productfeature_planner.apis.ideation.models import (
    StructuredIdeationResponse,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

logger = get_logger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"

# Step → agent config key mapping
STEP_AGENT_KEYS: dict[str, str] = {
    "a": "product_ideation_specialist",
    "b": "user_research_specialist",
    "c": "solution_architect",
    "d": "goal_strategist",
    "e": "tech_stack_advisor",
}

STEP_TASK_KEYS: dict[str, str] = {
    "a": "ideation_task",
    "b": "persona_task",
    "c": "solution_task",
    "d": "goal_task",
    "e": "tech_stack_task",
}


def _load_yaml(filename: str) -> dict:
    """Load a YAML config from the ideation config directory."""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_ideation_llm() -> LLM:
    """Build the LLM for ideation agents.

    Uses the Gemini conversational model tier for interactive
    back-and-forth exchanges.

    Resolution order:
        1. ``IDEATION_MODEL`` env var
        2. ``GEMINI_MODEL`` env var
        3. Hard-coded default
    """
    from crewai_productfeature_planner.agents.gemini_utils import (
        DEFAULT_GEMINI_MODEL,
        ensure_gemini_env,
    )

    ensure_gemini_env()

    model_name = os.environ.get(
        "IDEATION_MODEL",
        os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    ).strip()

    return LLM(
        model=f"gemini/{model_name}",
        timeout=120,
        max_retries=3,
    )


def build_ideation_agent(step: str) -> Agent:
    """Build the CrewAI agent for a given ideation step.

    Args:
        step: One of 'a', 'b', 'c', 'd', 'e'.

    Returns:
        A configured CrewAI Agent.
    """
    agents_config = _load_yaml("agents.yaml")
    agent_key = STEP_AGENT_KEYS[step]
    config = agents_config[agent_key]

    llm = _build_ideation_llm()

    return Agent(
        role=config["role"].strip(),
        goal=config["goal"].strip(),
        backstory=config["backstory"].strip(),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def run_ideation_step(
    *,
    step: str,
    user_input: str,
    context: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str | StructuredIdeationResponse:
    """Run a single ideation step and return the agent's response.

    All steps produce structured JSON output via ``output_pydantic``.
    On parse failure the raw text is returned as a graceful fallback.

    Args:
        step: One of 'a', 'b', 'c', 'd', 'e'.
        user_input: The user's latest message.
        context: Accumulated outputs from previous steps.
        conversation_history: Prior messages in the current step for
            multi-turn awareness.

    Returns:
        A ``StructuredIdeationResponse`` on success, or a plain string
        if the LLM output could not be parsed.
    """
    tasks_config = _load_yaml("tasks.yaml")
    task_key = STEP_TASK_KEYS[step]
    task_config = tasks_config[task_key]

    agent = build_ideation_agent(step)

    # Format context string from previous steps
    context_str = _format_context(context or {})

    # Format conversation history for multi-turn awareness
    history_str = _format_conversation_history(conversation_history or [])

    task = Task(
        description=task_config["description"].format(
            context=context_str,
            user_input=user_input,
            conversation_history=history_str,
        ),
        expected_output=task_config["expected_output"],
        agent=agent,
        output_pydantic=StructuredIdeationResponse,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    logger.info(
        "[IdeationAgent] Running step=%s agent=%s",
        step,
        STEP_AGENT_KEYS[step],
    )

    result = crew_kickoff_with_retry(crew, max_retries=2)

    # Try to extract the Pydantic model from the result
    parsed = _extract_structured_response(result)
    if parsed is not None:
        logger.info(
            "[IdeationAgent] Completed step=%s questions=%d structured=True",
            step,
            len(parsed.questions),
        )
        return parsed

    # Fallback: return raw text
    output = result.raw if hasattr(result, "raw") else str(result)
    logger.warning(
        "[IdeationAgent] Fallback to raw text step=%s output_len=%d",
        step,
        len(output),
    )
    return output


def _extract_structured_response(
    result: Any,
) -> StructuredIdeationResponse | None:
    """Try to extract a StructuredIdeationResponse from a CrewAI result.

    Attempts multiple strategies:
    1. Direct pydantic attribute (``result.pydantic``)
    2. JSON parse from raw text
    """
    # Strategy 1: CrewAI output_pydantic sets .pydantic on the result
    pydantic_obj = getattr(result, "pydantic", None)
    if isinstance(pydantic_obj, StructuredIdeationResponse):
        return pydantic_obj

    # Strategy 2: Parse JSON from raw text
    raw = getattr(result, "raw", None) or str(result)
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            first_nl = text.index("\n")
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        return StructuredIdeationResponse.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    return None


def _format_context(context: dict[str, Any]) -> str:
    """Format previous step outputs into a readable context string."""
    if not context:
        return "No previous context — this is the first step."

    labels = {
        "a": "Ideation (Executive Summary & Mission)",
        "b": "User Personas",
        "c": "Solution Architecture",
        "d": "Feature Goals",
        "e": "Technology Stack",
    }

    parts: list[str] = []
    for step_key, output in context.items():
        label = labels.get(step_key, step_key)
        parts.append(f"### {label}\n{output}")

    return "\n\n".join(parts)


def _format_conversation_history(messages: list[dict[str, str]]) -> str:
    """Format prior messages in the current step for multi-turn context.

    Args:
        messages: List of dicts with 'role' and 'content' keys.

    Returns:
        Formatted conversation string or 'No prior conversation' placeholder.
    """
    if not messages:
        return "No prior conversation in this step — this is the first exchange."

    role_labels = {"user": "User", "agent": "You (Agent)", "system": "System"}
    parts: list[str] = []
    for msg in messages:
        role = role_labels.get(msg.get("role", ""), msg.get("role", ""))
        content = msg.get("content", "")
        parts.append(f"**{role}**: {content}")

    return "\n\n".join(parts)
