"""Product-list Block Kit builder with delivery action buttons.

Lists completed (not archived) ideas with buttons for each delivery
action the user can take:

* **Publish to Confluence** — when Confluence is not yet published
* **Review Jira Skeleton** — resume/start phased Jira ticketing
* **Publish Epics & Stories** — create Jira Epics and User Stories
* **Publish Sub-tasks** — create Jira Sub-tasks

Action IDs follow the pattern ``product_<action>_<N>`` where *N* is
the 1-based index matching the product list order.
"""

from __future__ import annotations


# Jira-phase → human-readable status
_JIRA_PHASE_LABELS: dict[str, str] = {
    "": "Not started",
    "skeleton_pending": "Skeleton awaiting approval",
    "skeleton_approved": "Skeleton approved",
    "epics_stories_done": "Epics & Stories created",
    "subtasks_ready": "Sub-tasks in progress",
    "subtasks_pending": "Sub-tasks awaiting approval",
    "subtasks_done": "Complete",
}


def product_list_blocks(
    products: list[dict],
    user: str,
    project_name: str,
    project_id: str,
) -> list[dict]:
    """Build Block Kit blocks for listing completed products with
    delivery action buttons.

    Each product gets contextual action buttons based on its delivery
    state — only showing actions that are relevant.  The button
    ``value`` carries ``<project_id>|<idea_number>|<run_id>`` so the
    interactions router can resolve the product.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":package: Products for {project_name}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "Completed ideas ready for delivery. "
                        "Use the buttons to manage Confluence & Jira publishing."
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]

    for idx, product in enumerate(products, 1):
        idea_text = product.get("idea") or "Untitled"
        if len(idea_text) > 120:
            idea_text = idea_text[:117] + "\u2026"
        run_id = product.get("run_id", "")

        # Delivery status indicators
        conf_published = product.get("confluence_published", False)
        jira_completed = product.get("jira_completed", False)
        jira_phase = product.get("jira_phase") or ""
        confluence_url = product.get("confluence_url") or ""

        # Build status lines — completed steps get a checkmark,
        # in-progress steps show their current phase.
        completed_parts: list[str] = []
        if conf_published:
            if confluence_url:
                completed_parts.append(
                    f":white_check_mark: <{confluence_url}|Confluence PRD Page>"
                )
            else:
                completed_parts.append(":white_check_mark: Confluence PRD Page")
        if conf_published:
            if jira_completed:
                completed_parts.append(":white_check_mark: Jira Ticketing")
            elif jira_phase:
                phase_label = _JIRA_PHASE_LABELS.get(
                    jira_phase, f"Phase: {jira_phase}",
                )
                completed_parts.append(
                    f":hourglass_flowing_sand: Jira: {phase_label}"
                )

        section_text = f"*{idx}.* _{idea_text}_"
        if completed_parts:
            section_text += "\n" + " · ".join(completed_parts)

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": section_text,
                },
            }
        )

        # Build contextual action buttons
        btn_value = f"{project_id}|{idx}|{run_id}"
        elements: list[dict] = []

        # Always add a "View Confluence" link-button when URL is available
        if conf_published and confluence_url:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":link: View Confluence"},
                    "action_id": f"product_open_confluence_{idx}",
                    "url": confluence_url,
                },
            )

        if not conf_published:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":globe_with_meridians: Publish Confluence"},
                    "action_id": f"product_confluence_{idx}",
                    "value": btn_value,
                    "style": "primary",
                },
            )

        if conf_published and not jira_completed:
            if jira_phase == "skeleton_pending":
                # Skeleton generated — show review/approve button
                elements.append(
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":clipboard: Review Jira Skeleton",
                        },
                        "action_id": f"product_jira_skeleton_{idx}",
                        "value": btn_value,
                        "style": "primary",
                    },
                )
            elif not jira_phase:
                # Skeleton not yet created
                elements.append(
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":clipboard: Start Jira Skeleton",
                        },
                        "action_id": f"product_jira_skeleton_{idx}",
                        "value": btn_value,
                    },
                )
            if jira_phase == "skeleton_approved":
                # Ready for Epics & Stories
                elements.append(
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":jigsaw: Publish Epics & Stories"},
                        "action_id": f"product_jira_epics_{idx}",
                        "value": btn_value,
                        "style": "primary",
                    },
                )
            if jira_phase in ("epics_stories_done", "subtasks_ready"):
                # Ready for Sub-tasks
                elements.append(
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":hammer_and_wrench: Publish Sub-tasks"},
                        "action_id": f"product_jira_subtasks_{idx}",
                        "value": btn_value,
                        "style": "primary",
                    },
                )
            if jira_phase == "subtasks_pending":
                # Sub-tasks generated, awaiting approval via review blocks
                elements.append(
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":eyes: Review Sub-tasks"},
                        "action_id": f"product_jira_subtasks_{idx}",
                        "value": btn_value,
                    },
                )
            # Fallback for any unrecognised jira_phase value — let the
            # user start/restart the skeleton flow.
            if jira_phase and jira_phase not in _JIRA_PHASE_LABELS:
                elements.append(
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":clipboard: Restart Jira Skeleton",
                        },
                        "action_id": f"product_jira_skeleton_{idx}",
                        "value": btn_value,
                    },
                )

        # Always include "View Details" for fully delivered products
        if conf_published and jira_completed:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":eyes: View Details"},
                    "action_id": f"product_view_{idx}",
                    "value": btn_value,
                },
            )

        # Fallback — if no elements at all, add View Details
        if not elements:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":eyes: View Details"},
                    "action_id": f"product_view_{idx}",
                    "value": btn_value,
                },
            )

        blocks.append(
            {
                "type": "actions",
                "block_id": f"product_actions_{project_id}_{idx}",
                "elements": elements,
            }
        )

        blocks.append({"type": "divider"})

    # Footer hint
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        ":bulb: Say *list ideas* to see in-progress ideas, "
                        "or describe a new idea to start fresh!"
                    ),
                }
            ],
        }
    )

    return blocks
