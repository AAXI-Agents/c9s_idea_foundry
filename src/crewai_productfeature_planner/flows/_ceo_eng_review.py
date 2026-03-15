"""CEO and Engineering Manager review steps for the PRD flow.

Phase 1.5: After the executive summary is approved, these two specialist
agents produce higher-level artefacts that feed into Phase 2.

  1. **CEO Review** — ``run_ceo_review()``
     The CEO Reviewer agent transforms the executive summary into an
     *Executive Product Summary* — a visionary document capturing the
     10-star product vision.

  2. **Engineering Plan** — ``run_eng_plan()``
     The Engineering Manager agent converts the executive product
     summary and requirements into an *Engineering Plan* — the basis
     for all Jira tickets.

Both artefacts are persisted to MongoDB (``save_iteration``) and stored
in the corresponding ``PRDDraft`` sections so they appear in the final
PRD document.  The sections are marked as approved immediately so the
Phase 2 section loop skips them.

Extracted from ``prd_flow.py`` for modularity, following the pattern of
``_executive_summary.py``.
"""

from __future__ import annotations

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


# ------------------------------------------------------------------
# Phase 1.5a — CEO Review → Executive Product Summary
# ------------------------------------------------------------------

def run_ceo_review(flow: PRDFlow) -> str:
    """Generate the Executive Product Summary via the CEO Reviewer agent.

    Reads ``flow.state.executive_summary.latest_content`` and
    ``flow.state.idea``, runs the CEO Reviewer crew, and stores the
    result in:
      - ``flow.state.executive_product_summary``
      - the ``executive_product_summary`` section of ``flow.state.draft``

    Returns the generated executive product summary text.
    """
    from crewai_productfeature_planner.agents.ceo_reviewer import (
        create_ceo_reviewer,
        get_task_configs as get_ceo_task_configs,
    )

    project_id = resolve_project_id(flow.state.run_id)
    exec_summary = flow.state.executive_summary.latest_content
    idea = flow.state.idea

    logger.info(
        "[CEO Review] Starting executive product summary generation "
        "(exec_summary=%d chars, idea=%d chars)",
        len(exec_summary), len(idea),
    )
    flow._notify_progress("ceo_review_start", {
        "exec_summary_length": len(exec_summary),
    })

    # Create agent
    try:
        ceo_agent = create_ceo_reviewer(project_id=project_id)
    except EnvironmentError:
        logger.warning(
            "[CEO Review] Skipping — no Gemini credentials available. "
            "Executive product summary will not be generated.",
        )
        flow._notify_progress("ceo_review_skipped", {
            "reason": "no_credentials",
        })
        return ""

    # Build task from YAML config
    task_configs = get_ceo_task_configs()
    task_cfg = task_configs["generate_executive_product_summary_task"]

    ceo_task = Task(
        description=task_cfg["description"].format(
            executive_summary=exec_summary,
            idea=idea,
        ),
        expected_output=task_cfg["expected_output"],
        agent=ceo_agent,
    )

    crew = Crew(
        agents=[ceo_agent],
        tasks=[ceo_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    result = crew_kickoff_with_retry(crew, step_label="ceo_review")
    content = result.raw.strip()

    logger.info(
        "[CEO Review] Executive product summary generated (%d chars)",
        len(content),
    )

    # Store in flow state
    flow.state.executive_product_summary = content

    # Populate and approve the draft section
    section = flow.state.draft.get_section("executive_product_summary")
    if section is not None:
        section.content = content
        section.is_approved = True
        section.iteration = 1
        section.updated_date = datetime.now(timezone.utc).isoformat()
        logger.info(
            "[CEO Review] Populated draft section "
            "'executive_product_summary' — marked approved",
        )

    # Persist to MongoDB
    save_iteration(
        run_id=flow.state.run_id,
        idea=flow.state.original_idea or flow.state.idea,
        iteration=1,
        draft={"executive_product_summary": content},
        step="ceo_review",
        finalized_idea=flow.state.idea,
        section_key="executive_product_summary",
        section_title="Executive Product Summary",
    )

    flow.state.update_date = datetime.now(timezone.utc).isoformat()
    flow._notify_progress("ceo_review_complete", {
        "content_length": len(content),
    })

    return content


# ------------------------------------------------------------------
# Phase 1.5b — Eng Manager Review → Engineering Plan
# ------------------------------------------------------------------

def run_eng_plan(flow: PRDFlow) -> str:
    """Generate the Engineering Plan via the Eng Manager agent.

    Reads ``flow.state.executive_product_summary``,
    ``flow.state.requirements_breakdown``, and ``flow.state.idea``,
    runs the Eng Manager crew, and stores the result in:
      - ``flow.state.engineering_plan``
      - the ``engineering_plan`` section of ``flow.state.draft``

    Returns the generated engineering plan text.
    """
    from crewai_productfeature_planner.agents.eng_manager import (
        create_eng_manager,
        get_task_configs as get_eng_task_configs,
    )

    project_id = resolve_project_id(flow.state.run_id)
    eps = flow.state.executive_product_summary
    idea = flow.state.idea
    requirements = flow.state.requirements_breakdown

    logger.info(
        "[Eng Plan] Starting engineering plan generation "
        "(eps=%d chars, idea=%d chars, requirements=%d chars)",
        len(eps), len(idea), len(requirements),
    )
    flow._notify_progress("eng_plan_start", {
        "eps_length": len(eps),
        "requirements_length": len(requirements),
    })

    # Create agent
    try:
        eng_agent = create_eng_manager(project_id=project_id)
    except EnvironmentError:
        logger.warning(
            "[Eng Plan] Skipping — no Gemini credentials available. "
            "Engineering plan will not be generated.",
        )
        flow._notify_progress("eng_plan_skipped", {
            "reason": "no_credentials",
        })
        return ""

    # Build task from YAML config
    task_configs = get_eng_task_configs()
    task_cfg = task_configs["generate_engineering_plan_task"]

    eng_task = Task(
        description=task_cfg["description"].format(
            executive_product_summary=eps,
            idea=idea,
            requirements_breakdown=requirements or "(Not available)",
        ),
        expected_output=task_cfg["expected_output"],
        agent=eng_agent,
    )

    crew = Crew(
        agents=[eng_agent],
        tasks=[eng_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    result = crew_kickoff_with_retry(crew, step_label="eng_plan")
    content = result.raw.strip()

    logger.info(
        "[Eng Plan] Engineering plan generated (%d chars)", len(content),
    )

    # Store in flow state
    flow.state.engineering_plan = content

    # Populate and approve the draft section
    section = flow.state.draft.get_section("engineering_plan")
    if section is not None:
        section.content = content
        section.is_approved = True
        section.iteration = 1
        section.updated_date = datetime.now(timezone.utc).isoformat()
        logger.info(
            "[Eng Plan] Populated draft section "
            "'engineering_plan' — marked approved",
        )

    # Persist to MongoDB
    save_iteration(
        run_id=flow.state.run_id,
        idea=flow.state.original_idea or flow.state.idea,
        iteration=1,
        draft={"engineering_plan": content},
        step="eng_plan",
        finalized_idea=flow.state.idea,
        section_key="engineering_plan",
        section_title="Engineering Plan",
    )

    flow.state.update_date = datetime.now(timezone.utc).isoformat()
    flow._notify_progress("eng_plan_complete", {
        "content_length": len(content),
    })

    return content
