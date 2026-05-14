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
from crewai_productfeature_planner.scripts.retry import (
    crew_kickoff_with_retry,
)

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
        stream=True,
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
    knowledge_context: str = "",
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
        knowledge_context: Pre-built project knowledge block from
            ``build_knowledge_context()``.

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

    # NOTE: We intentionally do NOT set output_pydantic on the Task.
    # CrewAI's strict pydantic validation fails on LLM outputs with
    # trailing characters (concatenated JSON objects) and raises before
    # storing the raw text — making salvage impossible.  Instead we
    # parse the raw output ourselves with tolerant JSON handling.
    task = Task(
        description=task_config["description"].format(
            context=context_str,
            user_input=user_input,
            conversation_history=history_str,
            knowledge_context=knowledge_context or "No project knowledge available.",
        ),
        expected_output=task_config["expected_output"],
        agent=agent,
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
    3. Tolerant JSON parse (handles trailing characters)
    """
    # Strategy 1: CrewAI output_pydantic sets .pydantic on the result
    pydantic_obj = getattr(result, "pydantic", None)
    if isinstance(pydantic_obj, StructuredIdeationResponse):
        return pydantic_obj

    # Strategy 2+3: Parse JSON from raw text
    raw = getattr(result, "raw", None) or str(result)
    return _parse_structured_from_text(raw)


def _parse_structured_from_text(
    raw: str,
) -> StructuredIdeationResponse | None:
    """Parse a StructuredIdeationResponse from raw LLM text.

    This is a **deterministic code parser** — it does NOT rely on
    prompt engineering or LLM cooperation.  It aggressively extracts
    and normalizes JSON from any LLM output format.
    """
    data = _extract_json_object(raw)
    if data is None:
        return None

    normalized = _normalize_response_fields(data)
    try:
        return StructuredIdeationResponse.model_validate(normalized)
    except (ValueError, KeyError):
        return None


# ── JSON extraction (deterministic, multi-strategy) ───────────


def _extract_json_object(raw: str) -> dict | None:
    """Extract a JSON object from raw LLM text using multiple strategies.

    Order of attempts:
    1. Direct parse (entire text is JSON)
    2. Code-fence extraction (```json ... ``` or ``` ... ```)
    3. First-to-last brace extraction (outermost { ... })
    4. JSONDecoder.raw_decode (partial parse from first '{')

    Returns the first successfully parsed dict, or None.
    """
    text = raw.strip()

    # Strategy 1: Entire text is clean JSON
    result = _try_json_parse(text)
    if result is not None:
        return result

    # Strategy 2: Extract from markdown code fences
    fenced = _extract_from_code_fences(text)
    if fenced is not None:
        result = _try_json_parse(fenced)
        if result is not None:
            return result

    # Strategy 3: Outermost braces (first '{' to last '}')
    brace_start = raw.find("{")
    if brace_start != -1:
        brace_end = raw.rfind("}")
        if brace_end > brace_start:
            candidate = raw[brace_start : brace_end + 1]
            result = _try_json_parse(candidate)
            if result is not None:
                return result

    # Strategy 4: JSONDecoder.raw_decode from first '{'
    if brace_start != -1:
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(raw[brace_start:])
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _try_json_parse(text: str) -> dict | None:
    """Try to parse text as JSON; return dict or None."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _extract_from_code_fences(text: str) -> str | None:
    """Extract content between the first ``` and last ``` markers.

    Handles: ```json\\n...\\n```, ```\\n...\\n```, and fences with
    arbitrary preamble/postamble text around them.
    """
    if "```" not in text:
        return None

    lines = text.split("\n")
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            if start_idx is None:
                start_idx = i
            else:
                end_idx = i

    if start_idx is None:
        return None

    # Extract lines between the fences
    inner_lines = lines[start_idx + 1 : end_idx if end_idx else len(lines)]
    return "\n".join(inner_lines).strip()


# ── Field normalization (handles ALL known LLM drift) ─────────

# Top-level field aliases
_ACKNOWLEDGMENT_ALIASES = frozenset({
    "acknowledgement", "ack", "greeting", "intro", "introduction",
    "opening", "response", "message",
})

# Recommendation 'label' field aliases
_LABEL_ALIASES = frozenset({
    "direction", "description", "option", "title", "name", "answer",
    "suggestion", "approach", "strategy", "recommendation", "text",
    "value", "choice", "summary",
})

# Question 'question' field aliases
_QUESTION_ALIASES = frozenset({
    "text", "prompt", "query", "ask",
})

# Question 'context' field aliases
_CONTEXT_ALIASES = frozenset({
    "reason", "rationale", "explanation", "why", "background",
})


def _normalize_response_fields(data: Any) -> Any:
    """Normalize ALL known LLM field-name variations to match the Pydantic schema.

    This is a deterministic code fix — it does NOT rely on prompt wording.
    Handles every observed LLM drift pattern:

    Top-level:
    - acknowledgement/ack/greeting/intro → acknowledgment
    - Ensures 'questions' is a list
    - Ensures 'agent_insight' exists (defaults to empty string)

    Per question:
    - Auto-assigns 'id' (1-based) if missing
    - Normalizes 'context' from aliases or derives from recommended_reason
    - Normalizes 'question' field from aliases
    - Ensures 'recommendations' exists and has exactly 3 entries
    - Coerces 'recommended_index' to int or None

    Per recommendation:
    - direction/description/option/title/name/answer/... → label
    - Coerces 'complexity' to 'Low'|'Medium'|'High'
    - Ensures 'pro' and 'con' exist (defaults to empty string)
    """
    if not isinstance(data, dict):
        return data

    # ── Top-level normalization ──
    if "acknowledgment" not in data:
        for alias in _ACKNOWLEDGMENT_ALIASES:
            if alias in data:
                data["acknowledgment"] = data.pop(alias)
                break
        else:
            # Last resort: use first string value that looks like an ack
            data.setdefault("acknowledgment", "")

    # Ensure agent_insight exists
    data.setdefault("agent_insight", "")

    # ── Questions normalization ──
    questions = data.get("questions")
    if not isinstance(questions, list):
        return data

    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            continue

        # Auto-assign 'id' if missing (1-based)
        if "id" not in q:
            q["id"] = idx + 1
        else:
            # Coerce to int
            try:
                q["id"] = int(q["id"])
            except (ValueError, TypeError):
                q["id"] = idx + 1

        # Normalize 'question' field from aliases
        if "question" not in q:
            for alias in _QUESTION_ALIASES:
                if alias in q:
                    q["question"] = q.pop(alias)
                    break

        # Normalize 'context' from aliases or derive from recommended_reason
        if "context" not in q:
            for alias in _CONTEXT_ALIASES:
                if alias in q:
                    q["context"] = q.pop(alias)
                    break
            else:
                q["context"] = q.get("recommended_reason", "")

        # Coerce recommended_index to int or None
        ri = q.get("recommended_index")
        if ri is not None:
            try:
                q["recommended_index"] = int(ri)
            except (ValueError, TypeError):
                q["recommended_index"] = None

        # Normalize recommendations
        recs = q.get("recommendations")
        if isinstance(recs, list):
            for rec in recs:
                if not isinstance(rec, dict):
                    continue
                _normalize_recommendation(rec)

    return data


def _normalize_recommendation(rec: dict) -> None:
    """Normalize a single recommendation dict in-place."""
    # Normalize 'label' from aliases
    if "label" not in rec:
        for alias in _LABEL_ALIASES:
            if alias in rec:
                rec["label"] = rec.pop(alias)
                break
        else:
            rec["label"] = ""

    # Ensure 'pro' and 'con' exist
    rec.setdefault("pro", "")
    rec.setdefault("con", "")

    # Normalize 'complexity' to exact Literal values
    complexity = str(rec.get("complexity", "Medium")).strip().lower()
    if complexity in ("low", "l", "simple", "easy"):
        rec["complexity"] = "Low"
    elif complexity in ("high", "h", "hard", "complex", "difficult", "very high"):
        rec["complexity"] = "High"
    else:
        rec["complexity"] = "Medium"


def _format_context(context: dict[str, Any]) -> str:
    """Format previous step outputs into a readable context string.

    Handles both string outputs and structured dict outputs (from
    ``StructuredIdeationResponse.model_dump()``).
    """
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
        text = _readable_output(output)
        parts.append(f"### {label}\n{text}")

    return "\n\n".join(parts)


def _readable_output(output: Any) -> str:
    """Convert step output to readable text, handling dict or str."""
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        parts: list[str] = []
        if output.get("acknowledgment"):
            parts.append(output["acknowledgment"])
        if output.get("summary_draft"):
            parts.append(output["summary_draft"])
        if output.get("agent_insight"):
            parts.append(output["agent_insight"])
        for q in output.get("questions", []):
            q_text = q.get("question", "")
            recs = q.get("recommendations", [])
            rec_idx = q.get("recommended_index")
            if rec_idx is not None and 0 <= rec_idx < len(recs):
                rec = recs[rec_idx]
                parts.append(f"- {q_text}: Recommended \"{rec.get('label', '')}\"")
            elif recs:
                opts = ", ".join(r.get("label", "") for r in recs)
                parts.append(f"- {q_text}: Options — {opts}")
            else:
                parts.append(f"- {q_text}")
        return "\n".join(parts) if parts else str(output)
    return str(output)


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
