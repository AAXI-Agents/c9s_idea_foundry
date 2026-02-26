"""Slack Block Kit message builders for interactive PRD flow prompts.

Each builder returns a list of Block Kit block dicts suitable for use
with ``chat.postMessage`` or ``chat.update``.  Every actionable block
encodes the ``run_id`` in the button ``value`` so the interactions
router can route decisions back to the correct flow run.

Action ID conventions (used in :mod:`interactions_router`):

    refinement_agent   – Choose agent-driven idea refinement
    refinement_manual  – Choose manual idea refinement
    idea_approve       – Approve the refined idea
    idea_cancel        – Cancel the flow after idea refinement
    requirements_approve – Approve requirements breakdown
    requirements_cancel  – Cancel the flow after requirements breakdown
    flow_cancel        – Cancel an in-progress flow at any point
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Refinement mode choice
# ---------------------------------------------------------------------------


def refinement_mode_blocks(run_id: str, idea: str) -> list[dict]:
    """Ask the user how they want to refine the idea before PRD generation.

    Mirrors the CLI ``_choose_refinement_mode()`` prompt.
    """
    idea_preview = idea[:300] + ("…" if len(idea) > 300 else "")
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":gear: How would you like to refine this idea?",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Your idea:*\n> _{idea_preview}_",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Agent* — Let the AI Idea Refinement agent iterate "
                    "on your idea automatically before PRD generation.\n\n"
                    "*Manual* — Refine the idea yourself in a thread "
                    "conversation before starting the PRD flow."
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"refinement_mode_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":robot_face: Agent"},
                    "style": "primary",
                    "action_id": "refinement_agent",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil2: Manual"},
                    "action_id": "refinement_manual",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Cancel"},
                    "action_id": "flow_cancel",
                    "value": run_id,
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Idea approval
# ---------------------------------------------------------------------------


def idea_approval_blocks(
    run_id: str,
    refined_idea: str,
    original_idea: str,
) -> list[dict]:
    """Show the refined idea and let the user approve or cancel.

    Mirrors the CLI ``_approve_refined_idea()`` prompt.
    """
    refined_preview = refined_idea[:2000] + ("…" if len(refined_idea) > 2000 else "")
    header_text = ":bulb: Idea Refinement Complete"
    size_note = ""
    if original_idea:
        size_note = (
            f"Original ({len(original_idea)} chars) → "
            f"Refined ({len(refined_idea)} chars)"
        )

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text},
        },
    ]
    if size_note:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": size_note}],
        })
    blocks += [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": refined_preview},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":white_check_mark: *Approve* — save this idea and "
                    "generate all PRD sections:\n"
                    "  1. Draft each section independently\n"
                    "  2. Critique each section\n"
                    "  3. Refine with critique feedback\n"
                    "  Steps 2-3 iterate between min/max iteration count"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"idea_approval_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve"},
                    "style": "primary",
                    "action_id": "idea_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Cancel"},
                    "style": "danger",
                    "action_id": "idea_cancel",
                    "value": run_id,
                },
            ],
        },
    ]
    return blocks


# ---------------------------------------------------------------------------
# Requirements approval
# ---------------------------------------------------------------------------


def requirements_approval_blocks(
    run_id: str,
    requirements: str,
    iteration_count: int = 0,
) -> list[dict]:
    """Show the requirements breakdown and let the user approve or cancel.

    Mirrors the CLI ``_approve_requirements()`` prompt.
    """
    # Slack has a 3000-char limit per text block
    if len(requirements) > 2800:
        requirements_preview = requirements[:2800] + f"\n\n_… ({len(requirements) - 2800} more chars)_"
    else:
        requirements_preview = requirements

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":clipboard: Requirements Breakdown Complete",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"{iteration_count} iteration(s) — "
                        f"{len(requirements)} chars"
                    ),
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": requirements_preview},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":white_check_mark: *Approve* — auto-generate all "
                    "PRD sections (no further prompts):\n"
                    "  1. Draft each section independently\n"
                    "  2. Critique each section\n"
                    "  3. Refine with critique feedback\n"
                    "  Steps 2-3 auto-iterate; status is set to "
                    "'completed' when done."
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"requirements_approval_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve"},
                    "style": "primary",
                    "action_id": "requirements_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Cancel"},
                    "style": "danger",
                    "action_id": "requirements_cancel",
                    "value": run_id,
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Flow progress / status
# ---------------------------------------------------------------------------


def flow_started_blocks(run_id: str, idea: str) -> list[dict]:
    """Acknowledge that a PRD flow has been kicked off."""
    idea_preview = idea[:300] + ("…" if len(idea) > 300 else "")
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":rocket: *PRD flow started* (`{run_id}`)\n\n"
                    f"> _{idea_preview}_\n\n"
                    "I'll post updates here as the flow progresses."
                ),
            },
        },
    ]


def flow_cancelled_blocks(run_id: str, stage: str) -> list[dict]:
    """Inform the user the flow was cancelled."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":no_entry_sign: *PRD flow cancelled* (`{run_id}`)\n"
                    f"Cancelled at: _{stage}_"
                ),
            },
        },
    ]


def manual_refinement_prompt_blocks(run_id: str, current_idea: str, iteration: int) -> list[dict]:
    """Prompt the user to refine the idea or approve it (manual mode).

    Sent in a thread for multi-turn manual refinement.
    """
    idea_preview = current_idea[:2000] + ("…" if len(current_idea) > 2000 else "")
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":pencil2: Idea Refinement — Iteration {iteration}",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": idea_preview},
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Reply in this thread with your revised idea, "
                        "or click a button below."
                    ),
                },
            ],
        },
        {
            "type": "actions",
            "block_id": f"manual_refinement_{run_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve Idea"},
                    "style": "primary",
                    "action_id": "idea_approve",
                    "value": run_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Cancel"},
                    "style": "danger",
                    "action_id": "idea_cancel",
                    "value": run_id,
                },
            ],
        },
    ]
