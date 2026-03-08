"""One-time script to generate a Jira skeleton for a completed PRD run.

Reconstructs the PRD flow state from MongoDB and runs the Jira skeleton
stage, printing the result to stdout.  This bypasses Slack entirely.

Falls back to reading the PRD from the on-disk output file when MongoDB
sections are empty (older runs stored content only on disk).

Usage:
    .venv/bin/python scripts/retry_jira_skeleton.py <run_id>
    .venv/bin/python scripts/retry_jira_skeleton.py <run_id> --force

Options:
    --force   Skip the Confluence URL prerequisite check and ignore
              existing jira_phase (allows re-generation even when
              Jira was already completed).

Example:
    .venv/bin/python scripts/retry_jira_skeleton.py dd7a2a1de86e --force
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python scripts/retry_jira_skeleton.py <run_id> [--force]")
        sys.exit(1)

    run_id = sys.argv[1]
    force = "--force" in sys.argv
    print(f"[RetryJira] Starting Jira skeleton generation for run_id={run_id}"
          f"{' (--force)' if force else ''}")

    # ── 1. Load the MongoDB document ──────────────────────────────────
    from crewai_productfeature_planner.mongodb.working_ideas.repository import (
        find_run_any_status,
    )

    doc = find_run_any_status(run_id)
    if not doc:
        print(f"[RetryJira] ERROR: No document found for run_id={run_id}")
        sys.exit(1)

    print(f"[RetryJira] Found doc: status={doc.get('status')}, "
          f"jira_phase={doc.get('jira_phase')}, "
          f"idea={str(doc.get('idea', ''))[:60]}")

    # ── 2. Restore PRD state ──────────────────────────────────────────
    from crewai_productfeature_planner.apis.prd.service import restore_prd_state
    from crewai_productfeature_planner.flows.prd_flow import PRDFlow

    flow = PRDFlow()
    flow.state.run_id = run_id
    flow.state.idea = doc.get("idea", "")

    restored = restore_prd_state(run_id)
    if restored:
        idea, draft, exec_summary, requirements_breakdown, breakdown_history, refinement_history = restored
        flow.state.idea = idea
        flow.state.draft = draft
        flow.state.iteration = max(
            (s.iteration for s in draft.sections), default=0,
        )
        flow.state.executive_summary = exec_summary
        flow.state.requirements_breakdown = requirements_breakdown
        flow.state.breakdown_history = breakdown_history
        if requirements_breakdown:
            flow.state.requirements_broken_down = True
        if exec_summary.latest_content:
            flow.state.finalized_idea = exec_summary.latest_content
        if refinement_history:
            flow.state.idea_refined = True
            flow.state.refinement_history = refinement_history
            latest = refinement_history[-1]
            if latest.get("idea"):
                flow.state.idea = latest["idea"]
        elif exec_summary.iterations:
            flow.state.idea_refined = True
        flow.state.final_prd = draft.assemble()
        print(f"[RetryJira] Restored PRD state: "
              f"sections={len(draft.sections)}, "
              f"final_prd_len={len(flow.state.final_prd)}")
    else:
        print("[RetryJira] WARNING: restore_prd_state returned None — "
              "proceeding with minimal state")

    # ── 2b. Fallback: read PRD from the on-disk output file ──────────
    #    Older completed runs may have empty MongoDB sections but a
    #    saved markdown file on disk.
    if len(flow.state.final_prd) < 100:
        output_file = doc.get("output_file", "")
        if output_file and os.path.isfile(output_file):
            prd_text = open(output_file, encoding="utf-8").read()
            if prd_text:
                flow.state.final_prd = prd_text
                print(f"[RetryJira] Loaded PRD from disk: {output_file} "
                      f"({len(prd_text)} chars)")
        else:
            print(f"[RetryJira] WARNING: No usable output file "
                  f"({output_file or 'not set'})")

    # Delivery fields from the document
    flow.state.confluence_url = doc.get("confluence_url") or ""
    flow.state.jira_phase = ""  # Reset to allow skeleton generation
    print(f"[RetryJira] confluence_url={flow.state.confluence_url or '(none)'}")
    print(f"[RetryJira] final_prd_len={len(flow.state.final_prd)}")

    # ── 3. Check prerequisites ────────────────────────────────────────
    from crewai_productfeature_planner.orchestrator._jira import (
        _check_jira_prerequisites,
        build_jira_skeleton_stage,
    )

    skip_reason = _check_jira_prerequisites(
        flow, require_confluence=not force,
    )
    if skip_reason:
        if not force:
            print(f"[RetryJira] ERROR: Prerequisites not met: {skip_reason}")
            print("[RetryJira] Hint: use --force to bypass Confluence URL check")
            sys.exit(1)
        else:
            print(f"[RetryJira] WARNING: Prerequisite skipped (--force): {skip_reason}")

    if not flow.state.final_prd or len(flow.state.final_prd) < 100:
        print("[RetryJira] ERROR: No PRD content available (final_prd is empty)")
        sys.exit(1)

    # ── 4. Run the skeleton stage ─────────────────────────────────────
    print("[RetryJira] Running Jira skeleton stage...")
    stage = build_jira_skeleton_stage(
        flow, require_confluence=not force,
    )
    if stage.should_skip():
        print("[RetryJira] Stage reports should_skip=True — aborting")
        sys.exit(1)

    result = stage.run()
    stage.apply(result)

    skeleton = flow.state.jira_skeleton
    if skeleton:
        print(f"\n[RetryJira] SUCCESS — skeleton ({len(skeleton)} chars):\n")
        print(skeleton[:4000])
        if len(skeleton) > 4000:
            print(f"\n... ({len(skeleton) - 4000} more chars)")
        print(f"\n[RetryJira] jira_phase is now: {flow.state.jira_phase}")
    else:
        print("[RetryJira] WARNING: Skeleton generation produced no output")
        sys.exit(1)


if __name__ == "__main__":
    main()
