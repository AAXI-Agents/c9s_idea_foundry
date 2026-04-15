"""UX Design flow — standalone, post-PRD design generation.

Two-phase flow triggered after PRD completion:

- **Phase 1** (Draft): UX Designer + Design Partner collaborate to
  produce the initial design specification → ``ux_design_draft.md``
- **Phase 2** (Final): Senior Designer applies 7-pass review and
  produces the production-ready design → ``ux_design_final.md``

Agents produce markdown design specifications only — no external
tool integrations.  Only two files are ever written per product idea.
The draft is overwritten on each iteration; the final is created once.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from crewai import Crew, Process, Task

from crewai_productfeature_planner.mongodb import save_iteration
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.memory_loader import resolve_project_id
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

if TYPE_CHECKING:
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

logger = get_logger(__name__)

# Fixed filenames — only 2 files per product idea.
DRAFT_FILENAME = "ux_design_draft.md"
FINAL_FILENAME = "ux_design_final.md"


def _persist_ux_design_status(run_id: str, *, status: str = "") -> None:
    """Persist UX design status to the workingIdeas MongoDB document."""
    try:
        from crewai_productfeature_planner.mongodb.working_ideas._status import (
            save_ux_design,
        )
        save_ux_design(run_id, status=status)
    except Exception:  # noqa: BLE001
        logger.debug(
            "Failed to persist UX design status for run_id=%s",
            run_id, exc_info=True,
        )


def _resolve_output_dir(project_id: str | None) -> str:
    """Return the output directory for UX design files."""
    if project_id:
        return f"output/{project_id}/ux design"
    return "output/prds"


def _write_design_file(
    output_dir: str,
    filename: str,
    content: str,
) -> str:
    """Write a design markdown file, overwriting any existing file.

    Returns the file path written.
    """
    parts = ["# UX Design Specification\n", f"\n{content}\n"]
    text = "".join(parts)

    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    file_path.write_text(text, encoding="utf-8")
    logger.info("[UX Design] Wrote file: %s", file_path)

    # Also upload to GCS when configured
    try:
        from crewai_productfeature_planner.tools.output_storage import (
            _gcs_bucket_name,
            _write_to_gcs,
        )
        bucket = _gcs_bucket_name()
        if bucket:
            rel_dir = output_dir
            if rel_dir.startswith("output/"):
                rel_dir = rel_dir[len("output/"):]
            _write_to_gcs(bucket, f"{rel_dir}/{filename}", text)
    except Exception:  # noqa: BLE001
        pass  # GCS is best-effort

    return str(file_path)


# ------------------------------------------------------------------
# Phase 1: UX Designer + Design Partner → Draft
# ------------------------------------------------------------------

def run_ux_design_draft(flow: PRDFlow) -> str:
    """Phase 1: Generate the initial design draft.

    UX Designer and Design Partner collaborate to produce a comprehensive
    markdown design specification.  The result is written to
    ``ux_design_draft.md`` (overwriting any previous draft).

    Returns the draft content, or empty string if skipped.
    """
    from crewai_productfeature_planner.agents.ux_designer import (
        create_design_partner,
        create_ux_designer,
        get_ux_design_flow_task_configs,
    )

    project_id = resolve_project_id(flow.state.run_id)
    eps = flow.state.executive_product_summary
    idea = flow.state.idea
    requirements = flow.state.requirements_breakdown

    if not eps:
        logger.info(
            "[UX Design Phase 1] Skipping — no executive product summary.",
        )
        flow._notify_progress("ux_design_skipped", {
            "reason": "no_executive_product_summary",
        })
        return ""

    logger.info(
        "[UX Design Phase 1] Starting draft generation "
        "(eps=%d chars, idea=%d chars)",
        len(eps), len(idea),
    )
    flow._notify_progress("ux_design_start", {"eps_length": len(eps)})

    flow.state.ux_design_status = "generating"
    _persist_ux_design_status(flow.state.run_id, status="generating")

    # Create agents.
    try:
        ux_agent = create_ux_designer(project_id=project_id)
    except EnvironmentError:
        logger.warning(
            "[UX Design Phase 1] Skipping — no Gemini credentials.",
        )
        flow.state.ux_design_status = ""
        _persist_ux_design_status(flow.state.run_id, status="")
        flow._notify_progress("ux_design_skipped", {
            "reason": "no_credentials",
        })
        return ""

    try:
        partner_agent = create_design_partner(project_id=project_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "[UX Design Phase 1] Could not create Design Partner — "
            "proceeding with UX Designer only.",
            exc_info=True,
        )
        partner_agent = None

    # Load existing design system reference from output/design/ if present.
    design_ref = ""
    design_file = Path("output/design/DESIGN.md")
    if design_file.is_file():
        try:
            design_ref = design_file.read_text(encoding="utf-8")[:8000]
            logger.info(
                "[UX Design Phase 1] Loaded design reference (%d chars)",
                len(design_ref),
            )
        except OSError:
            pass

    # Build tasks.
    task_configs = get_ux_design_flow_task_configs()
    draft_cfg = task_configs["create_initial_design_draft_task"]

    draft_task = Task(
        description=draft_cfg["description"].format(
            executive_product_summary=eps,
            idea=idea,
            requirements_breakdown=requirements or "(Not available)",
            design_system_reference=design_ref or "(No existing design system)",
        ),
        expected_output=draft_cfg["expected_output"],
        agent=ux_agent,
    )

    agents = [ux_agent]
    if partner_agent:
        agents.append(partner_agent)

    crew = Crew(
        agents=agents,
        tasks=[draft_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    flow._notify_progress("agent_activity", {
        "agent": "UX Designer",
        "action": "creating design specification draft",
    })
    result = crew_kickoff_with_retry(crew, step_label="ux_design_draft")
    raw_output = result.raw.strip()

    logger.info(
        "[UX Design Phase 1] Draft output (%d chars): %s",
        len(raw_output), raw_output[:200],
    )

    # Store the design content and update status.
    flow.state.ux_design_content = raw_output
    flow.state.ux_design_status = "completed"
    _persist_ux_design_status(flow.state.run_id, status="completed")

    # Persist to MongoDB.
    save_iteration(
        run_id=flow.state.run_id,
        idea=flow.state.original_idea or flow.state.idea,
        iteration=1,
        draft={"ux_design_draft": raw_output},
        step="ux_design_draft",
        finalized_idea=flow.state.idea,
        section_key="ux_design",
        section_title="UX Design — Draft",
    )

    # Write draft file (overwrite any existing).
    output_dir = _resolve_output_dir(project_id)
    _write_design_file(output_dir, DRAFT_FILENAME, raw_output)

    flow.state.update_date = datetime.now(timezone.utc).isoformat()
    flow._notify_progress("ux_design_draft_complete", {
        "has_prompt": bool(raw_output),
        "status": flow.state.ux_design_status,
        "prompt_preview": raw_output[:500],
    })

    return raw_output


# ------------------------------------------------------------------
# Phase 2: Senior Designer → Final
# ------------------------------------------------------------------

def run_ux_design_review(flow: PRDFlow, initial_draft: str) -> str:
    """Phase 2: Senior Designer reviews and finalizes the design.

    Takes the initial draft from Phase 1, applies a 7-pass review,
    and produces the final design specification → ``ux_design_final.md``.

    Returns the final design content, or the draft unchanged on failure.
    """
    from crewai_productfeature_planner.agents.ux_designer import (
        create_senior_designer,
        get_ux_design_flow_task_configs,
    )

    project_id = resolve_project_id(flow.state.run_id)

    if not initial_draft:
        logger.info("[UX Design Phase 2] Skipping — no initial draft.")
        return ""

    logger.info(
        "[UX Design Phase 2] Starting Senior Designer review "
        "(%d chars draft)",
        len(initial_draft),
    )
    flow._notify_progress("ux_design_review_start", {
        "draft_length": len(initial_draft),
    })

    try:
        senior_agent = create_senior_designer(project_id=project_id)
    except EnvironmentError:
        logger.warning(
            "[UX Design Phase 2] Skipping — no Gemini credentials.",
        )
        return initial_draft

    task_configs = get_ux_design_flow_task_configs()
    review_cfg = task_configs["review_and_finalize_design_task"]

    review_task = Task(
        description=review_cfg["description"].format(
            initial_design_draft=initial_draft,
            idea=flow.state.idea,
        ),
        expected_output=review_cfg["expected_output"],
        agent=senior_agent,
    )

    crew = Crew(
        agents=[senior_agent],
        tasks=[review_task],
        process=Process.sequential,
        verbose=is_verbose(),
    )

    flow._notify_progress("agent_activity", {
        "agent": "Senior Designer",
        "action": "reviewing and finalizing design (7-pass review)",
    })
    result = crew_kickoff_with_retry(crew, step_label="ux_design_review")
    final_output = result.raw.strip()

    logger.info(
        "[UX Design Phase 2] Final output (%d chars): %s",
        len(final_output), final_output[:200],
    )

    # Persist to MongoDB.
    save_iteration(
        run_id=flow.state.run_id,
        idea=flow.state.original_idea or flow.state.idea,
        iteration=2,
        draft={"ux_design_final": final_output},
        step="ux_design_review",
        finalized_idea=flow.state.idea,
        section_key="ux_design",
        section_title="UX Design — Final",
    )

    # Write final file.
    output_dir = _resolve_output_dir(project_id)
    _write_design_file(output_dir, FINAL_FILENAME, final_output)

    # ── UX Design review gate ────────────────────────────────────
    # Let the user review the final design before it is appended to
    # the PRD. Mirrors the CEO Review approval gate pattern.
    ux_cb = flow._resolve_callback("ux_design_review_approval_callback")
    if ux_cb is not None:
        logger.info("[UX Design Phase 2] Waiting for user review")
        flow._notify_progress("ux_design_review_awaiting_approval", {
            "content_length": len(final_output),
        })
        try:
            decision, _edited = ux_cb(final_output, flow.state.run_id)
        except Exception:
            logger.exception("[UX Design Phase 2] Review callback failed")
            decision = "approve"

        if decision == "reject":
            logger.info("[UX Design Phase 2] User skipped UX design")
            flow.state.ux_design_content = ""
            flow.state.ux_design_status = "skipped"
            flow._notify_progress("ux_design_skipped", {
                "reason": "user_rejected",
            })
            return ""
        else:
            logger.info("[UX Design Phase 2] User approved UX design")
    else:
        logger.info(
            "[UX Design Phase 2] No review callback — auto-approving",
        )

    # Update state.
    flow.state.ux_design_content = final_output
    flow.state.update_date = datetime.now(timezone.utc).isoformat()
    flow._notify_progress("ux_design_complete", {
        "has_prompt": True,
        "status": flow.state.ux_design_status,
        "prompt_preview": final_output[:500],
    })

    return final_output


# ------------------------------------------------------------------
# Full UX Design Flow (Phase 1 + Phase 2)
# ------------------------------------------------------------------

def run_ux_design_flow(flow: PRDFlow) -> str:
    """Run the complete UX design flow: draft → review → final.

    Called after PRD finalization when the PRD is ready for Confluence
    publication.  Produces exactly two markdown files:
    - ``ux_design_draft.md`` — initial draft (overwritten each run)
    - ``ux_design_final.md`` — reviewed final design

    Returns the final UX design content, or empty string on failure.
    """
    logger.info(
        "[UX Design Flow] Starting for run_id=%s",
        flow.state.run_id,
    )

    # Phase 1: Draft
    initial_draft = run_ux_design_draft(flow)
    if not initial_draft:
        logger.info("[UX Design Flow] Phase 1 produced no draft — stopping.")
        return ""

    # Phase 2: Review
    run_ux_design_review(flow, initial_draft)

    return flow.state.ux_design_content


# ------------------------------------------------------------------
# Legacy single-phase entry point (backward compatibility)
# ------------------------------------------------------------------

def run_ux_design(flow: PRDFlow) -> str:
    """Legacy entry point — delegates to the full 2-phase flow.

    Kept for backward compatibility with existing Slack handlers and
    tests that call ``run_ux_design(flow)`` directly.
    """
    return run_ux_design_flow(flow)
