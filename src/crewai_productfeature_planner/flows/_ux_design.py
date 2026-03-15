"""UX Design step for the PRD flow.

Phase 1.5c: After the CEO review produces the Executive Product Summary,
the UX Designer agent generates a Figma Make prompt and (when credentials
are configured) submits it to Figma Make to produce a clickable prototype.

The resulting Figma URL (or prompt text) is persisted to MongoDB and
stored in ``PRDState.figma_design_url`` / ``PRDState.figma_design_prompt``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crewai import Crew, Process, Task

from crewai_productfeature_planner.mongodb import save_iteration
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.memory_loader import resolve_project_id
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)

# Regex patterns for extracting output from the agent.
_URL_PATTERN = re.compile(r"FIGMA_URL:\s*(\S+)")
_PROMPT_PATTERN = re.compile(r"FIGMA_PROMPT:\s*(.+)", re.DOTALL)
_ERROR_PATTERN = re.compile(r"FIGMA_ERROR:\s*(.+)")
_SKIPPED_PATTERN = re.compile(r"FIGMA_SKIPPED:\s*(.+)")


def _persist_figma_design(run_id: str, *, url: str = "", status: str = "") -> None:
    """Persist Figma design fields to the workingIdeas MongoDB document."""
    try:
        from crewai_productfeature_planner.mongodb.working_ideas._status import (
            save_figma_design,
        )
        save_figma_design(run_id, url=url, status=status)
    except Exception:  # noqa: BLE001
        logger.debug(
            "Failed to persist figma design for run_id=%s",
            run_id, exc_info=True,
        )


def run_ux_design(flow: PRDFlow) -> str:
    """Generate a UX design via the UX Designer agent + Figma Make.

    Reads ``flow.state.executive_product_summary`` and
    ``flow.state.idea``, runs the UX Designer crew, and stores the
    result in ``flow.state.figma_design_url`` / ``figma_design_prompt``.

    Returns the Figma URL (or empty string if skipped/failed).
    """
    from crewai_productfeature_planner.agents.ux_designer import (
        create_ux_designer,
        get_task_configs as get_ux_task_configs,
    )

    project_id = resolve_project_id(flow.state.run_id)
    eps = flow.state.executive_product_summary
    idea = flow.state.idea
    requirements = flow.state.requirements_breakdown

    if not eps:
        logger.info(
            "[UX Design] Skipping — no executive product summary available.",
        )
        return ""

    logger.info(
        "[UX Design] Starting Figma Make design generation "
        "(eps=%d chars, idea=%d chars)",
        len(eps), len(idea),
    )
    flow._notify_progress("ux_design_start", {
        "eps_length": len(eps),
    })

    # Mark as in-progress in MongoDB.
    flow.state.figma_design_status = "generating"
    _persist_figma_design(flow.state.run_id, status="generating")

    # Create agent.
    try:
        ux_agent = create_ux_designer(project_id=project_id)
    except EnvironmentError:
        logger.warning(
            "[UX Design] Skipping — no Gemini credentials available.",
        )
        flow.state.figma_design_status = ""
        _persist_figma_design(flow.state.run_id, status="")
        flow._notify_progress("ux_design_skipped", {
            "reason": "no_credentials",
        })
        return ""

    # Build task from YAML config.
    task_configs = get_ux_task_configs()
    task_cfg = task_configs["generate_figma_make_prompt_task"]

    ux_task = Task(
        description=task_cfg["description"].format(
            executive_product_summary=eps,
            idea=idea,
            requirements_breakdown=requirements or "(Not available)",
        ),
        expected_output=task_cfg["expected_output"],
        agent=ux_agent,
    )

    crew = Crew(
        agents=[ux_agent],
        tasks=[ux_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    # Update status — agent is now working (may call Figma Make tool).
    flow.state.figma_design_status = "prompting"
    _persist_figma_design(flow.state.run_id, status="prompting")

    result = crew_kickoff_with_retry(crew, step_label="ux_design")
    raw_output = result.raw.strip()

    logger.info(
        "[UX Design] Agent output (%d chars): %s",
        len(raw_output), raw_output[:200],
    )

    # Parse the agent's output.
    figma_url = ""
    figma_prompt = ""

    url_match = _URL_PATTERN.search(raw_output)
    if url_match:
        figma_url = url_match.group(1).strip()

    prompt_match = _PROMPT_PATTERN.search(raw_output)
    if prompt_match:
        figma_prompt = prompt_match.group(1).strip()

    error_match = _ERROR_PATTERN.search(raw_output)
    skipped_match = _SKIPPED_PATTERN.search(raw_output)

    # Store results.
    if figma_url:
        flow.state.figma_design_url = figma_url
        flow.state.figma_design_status = "completed"
        _persist_figma_design(
            flow.state.run_id, url=figma_url, status="completed",
        )
        logger.info("[UX Design] Figma URL captured: %s", figma_url)
    elif figma_prompt:
        flow.state.figma_design_prompt = figma_prompt
        flow.state.figma_design_status = "prompt_ready"
        _persist_figma_design(flow.state.run_id, status="prompt_ready")
        logger.info(
            "[UX Design] Figma prompt generated (%d chars) — "
            "no Figma credentials to submit",
            len(figma_prompt),
        )
    elif error_match or skipped_match:
        reason = (error_match or skipped_match).group(1).strip()
        flow.state.figma_design_status = "skipped"
        _persist_figma_design(flow.state.run_id, status="skipped")
        logger.warning("[UX Design] Skipped/error: %s", reason)
    else:
        # Agent output didn't match expected patterns — treat the
        # entire output as the prompt for manual use.
        flow.state.figma_design_prompt = raw_output
        flow.state.figma_design_status = "prompt_ready"
        _persist_figma_design(flow.state.run_id, status="prompt_ready")
        logger.info(
            "[UX Design] Raw output stored as prompt (%d chars)",
            len(raw_output),
        )

    # Persist the prompt to MongoDB iteration history.
    save_iteration(
        run_id=flow.state.run_id,
        idea=flow.state.original_idea or flow.state.idea,
        iteration=1,
        draft={"ux_design_prompt": figma_prompt or raw_output},
        step="ux_design",
        finalized_idea=flow.state.idea,
        section_key="ux_design",
        section_title="UX Design",
    )

    flow.state.update_date = datetime.now(timezone.utc).isoformat()
    flow._notify_progress("ux_design_complete", {
        "figma_url": figma_url,
        "has_prompt": bool(figma_prompt or raw_output),
        "status": flow.state.figma_design_status,
    })

    return figma_url
