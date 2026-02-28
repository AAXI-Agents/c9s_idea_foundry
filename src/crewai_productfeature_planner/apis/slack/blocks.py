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

    project_select_<project_id> – Continue with an existing project
    project_create     – Create a new project
    project_switch     – Switch away from the current project
    project_continue   – Continue with the current project
    session_end        – Explicitly end the current session

    memory_configure   – Open the project memory configuration menu
    memory_idea        – Add idea & iteration guardrails
    memory_knowledge   – Add knowledge links / documents
    memory_tools       – Add implementation tools
    memory_view        – View current project memory
    memory_done        – Finish memory configuration
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


# ---------------------------------------------------------------------------
# Project session — selection & status
# ---------------------------------------------------------------------------


def project_selection_blocks(
    projects: list[dict],
    user_id: str,
) -> list[dict]:
    """Prompt the user to select an existing project or create a new one.

    *projects* is a list of project-config dicts (from
    ``list_projects()``).  Up to 5 are shown as buttons; the rest are
    mentioned in a context line.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":file_folder: Select a Project",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Which project would you like to work on?\n"
                    "Choose an existing project or create a new one."
                ),
            },
        },
        {"type": "divider"},
    ]

    # Show up to 5 project buttons
    buttons: list[dict] = []
    shown = projects[:5]
    for proj in shown:
        pid = proj.get("project_id", "")
        pname = proj.get("name", "Unnamed")
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": f":bookmark: {pname}"[:75]},
            "action_id": f"project_select_{pid}",
            "value": pid,
        })

    # Always offer "Create New"
    buttons.append({
        "type": "button",
        "text": {"type": "plain_text", "text": ":heavy_plus_sign: Create New Project"},
        "style": "primary",
        "action_id": "project_create",
        "value": user_id,
    })

    blocks.append({
        "type": "actions",
        "block_id": f"project_select_{user_id}",
        "elements": buttons,
    })

    if len(projects) > 5:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"_Showing 5 of {len(projects)} projects. "
                        "Type the project name to search._",
            }],
        })

    return blocks


def active_session_blocks(
    project_name: str,
    project_id: str,
    user_id: str,
) -> list[dict]:
    """Remind the user of their active project session.

    Offers to continue with the current project or switch to a
    different one.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":file_folder: You're currently working on "
                    f"*{project_name}*.\n\n"
                    "Continue with this project or switch to a different one."
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"session_status_{user_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":arrow_forward: Continue"},
                    "style": "primary",
                    "action_id": "project_continue",
                    "value": project_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":twisted_rightwards_arrows: Switch Project"},
                    "action_id": "project_switch",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":stop_button: End Session"},
                    "style": "danger",
                    "action_id": "session_end",
                    "value": user_id,
                },
            ],
        },
    ]


def project_create_prompt_blocks(user_id: str) -> list[dict]:
    """Tell the user to type the new project name."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":pencil: *Create a New Project*\n\n"
                    "Reply in this thread with the project name and I'll "
                    "set it up for you."
                ),
            },
        },
    ]


def project_setup_step_blocks(
    project_name: str, step: str, step_number: int, total_steps: int,
) -> list[dict]:
    """Prompt for the next project-setup field.

    Each step collects one optional configuration value.
    The user may reply with the value or type ``skip`` to leave it blank.
    """
    _STEP_LABELS = {
        "confluence_space_key": (
            ":confluence: *Confluence Space Key*\n\n"
            "Enter the Confluence space key for this project "
            "(e.g. `ENG`, `PROD`).  This is used when publishing PRDs.\n\n"
            "_Type `skip` to leave blank and use the default._"
        ),
        "jira_project_key": (
            ":jira2: *Jira Project Key*\n\n"
            "Enter the Jira project key (e.g. `MYPROJ`, `FEAT`).  "
            "This is used when creating Jira tickets for PRDs.\n\n"
            "_Type `skip` to leave blank and use the default._"
        ),
        "confluence_parent_id": (
            ":page_facing_up: *Confluence Parent Page ID*\n\n"
            "Enter the numeric ID of the Confluence parent page under "
            "which PRDs will be created (e.g. `123456`).\n\n"
            "_Type `skip` to leave blank and use the default._"
        ),
    }
    label = _STEP_LABELS.get(step, f"*{step}*")
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":gear: *Setting up project:* {project_name} "
                    f"(step {step_number}/{total_steps})\n\n"
                    f"{label}"
                ),
            },
        },
    ]


def project_setup_complete_blocks(project_name: str, details: dict) -> list[dict]:
    """Show the completed project setup summary."""
    lines = [
        f":white_check_mark: *Project '{project_name}' is set up and ready!*\n",
    ]
    csk = details.get("confluence_space_key", "")
    jpk = details.get("jira_project_key", "")
    cpid = details.get("confluence_parent_id", "")
    if csk:
        lines.append(f"• Confluence space key: `{csk}`")
    if jpk:
        lines.append(f"• Jira project key: `{jpk}`")
    if cpid:
        lines.append(f"• Confluence parent ID: `{cpid}`")
    if not (csk or jpk or cpid):
        lines.append("_No extra keys configured — defaults will be used._")
    lines.append(
        "\nYou can now start iterating ideas!  Just say something like "
        "`iterate an idea` or `create a PRD for ...`."
    )
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        },
    ]


def session_started_blocks(project_name: str) -> list[dict]:
    """Confirm that a project session has been activated."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: *Project session started:* {project_name}\n\n"
                    "All PRD flows will be linked to this project. "
                    "Say *switch project* or *end session* when you're done."
                ),
            },
        },
    ]


def session_ended_blocks() -> list[dict]:
    """Confirm that the project session has been ended."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":stop_button: *Project session ended.*\n\n"
                    "Mention me again to start a new session with a project."
                ),
            },
        },
    ]


# ---------------------------------------------------------------------------
# Project Memory configuration
# ---------------------------------------------------------------------------


def memory_configure_blocks(project_name: str, user_id: str) -> list[dict]:
    """Offer memory-configuration options for the active project.

    Shown after a session starts or when the user says
    "configure memory" / "project memory".
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":brain: Project Memory — {project_name}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Project Memory stores guardrails and context that "
                    "all agents recall during every PRD run.\n\n"
                    "*Choose a category to configure:*"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"memory_menu_{user_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":bulb: Idea & Iteration"},
                    "action_id": "memory_idea",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":books: Knowledge"},
                    "action_id": "memory_knowledge",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":wrench: Tools"},
                    "action_id": "memory_tools",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":mag: View Memory"},
                    "action_id": "memory_view",
                    "value": user_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Done"},
                    "action_id": "memory_done",
                    "value": user_id,
                    "style": "primary",
                },
            ],
        },
    ]


def memory_category_prompt_blocks(
    category: str,
    category_label: str,
    help_text: str,
) -> list[dict]:
    """Prompt the user to type entries for a memory category.

    The user replies in the thread; each line becomes a separate entry.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":pencil: *Configure {category_label}*\n\n"
                    f"{help_text}\n\n"
                    "Reply in this thread with your entries — "
                    "*one per line*.  When you're finished, I'll "
                    "save them all."
                ),
            },
        },
    ]


def memory_saved_blocks(
    category_label: str,
    count: int,
) -> list[dict]:
    """Confirm that memory entries have been saved."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: Saved *{count}* "
                    f"{category_label} "
                    f"{'entry' if count == 1 else 'entries'}.\n\n"
                    "Say *configure memory* to add more, or start "
                    "creating PRDs!"
                ),
            },
        },
    ]


def memory_view_blocks(
    project_name: str,
    idea_entries: list[dict],
    knowledge_entries: list[dict],
    tools_entries: list[dict],
) -> list[dict]:
    """Display all stored project memory entries."""
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":brain: Project Memory — {project_name}",
            },
        },
    ]

    def _section(label: str, emoji: str, entries: list[dict]) -> None:
        if entries:
            lines = "\n".join(
                f"• {e.get('content', '')}" for e in entries
            )
            text = f"{emoji} *{label}* ({len(entries)}):\n{lines}"
        else:
            text = f"{emoji} *{label}*: _none configured_"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        })

    _section("Idea & Iteration", ":bulb:", idea_entries)
    _section("Knowledge", ":books:", knowledge_entries)
    _section("Tools", ":wrench:", tools_entries)

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Say *configure memory* to update.",
        }],
    })
    return blocks


# ---------------------------------------------------------------------------
# Next-step suggestion (proactive navigation)
# ---------------------------------------------------------------------------

# Emoji mapping for next-step categories
_NEXT_STEP_EMOJI = {
    "configure_confluence": ":confluence:",
    "configure_jira": ":jira2:",
    "configure_memory": ":brain:",
    "configure_missing_keys": ":key:",
    "create_prd": ":rocket:",
    "publish": ":outbox_tray:",
    "review_prd": ":mag:",
}


def next_step_suggestion_blocks(
    next_step: str,
    message: str,
    user_id: str,
    interaction_id: str | None = None,
) -> list[dict]:
    """Build a proactive next-step suggestion block.

    Shown after key actions (project selection, PRD completion, etc.)
    to guide the user toward the most useful next action.

    The ``interaction_id`` is encoded in the button values so the
    feedback loop can update the correct ``agentInteraction`` document.
    """
    emoji = _NEXT_STEP_EMOJI.get(next_step, ":bulb:")
    # Encode interaction_id in button value for feedback tracking
    accept_value = f"{next_step}|{interaction_id or ''}"
    dismiss_value = f"dismiss|{interaction_id or ''}"

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *Suggested next step:*\n"
                    f"{message}"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"next_step_{user_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Let's do it",
                    },
                    "style": "primary",
                    "action_id": "next_step_accept",
                    "value": accept_value,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":x: Not now",
                    },
                    "action_id": "next_step_dismiss",
                    "value": dismiss_value,
                },
            ],
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": "_This suggestion is based on your project's current state._",
            }],
        },
    ]
