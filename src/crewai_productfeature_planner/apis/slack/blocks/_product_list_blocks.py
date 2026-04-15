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
    "subtasks_done": "Sub-tasks created",
    "review_ready": "Review sub-tasks in progress",
    "review_pending": "Review sub-tasks awaiting approval",
    "review_done": "Review sub-tasks created",
    "qa_test_ready": "QA test sub-tasks in progress",
    "qa_test_pending": "QA test sub-tasks awaiting approval",
    "qa_test_done": "Complete",
}


def product_list_blocks(
    products: list[dict],
    user: str,
    project_name: str,
    project_id: str,
    *,
    is_admin: bool = False,
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
                        "Use the buttons to manage UX designs and view details."
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]

    # Project-level actions (Config button — admin only)
    if is_admin:
        blocks.append(
            {
                "type": "actions",
                "block_id": f"product_project_actions_{project_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": ":gear: Config"},
                        "action_id": "product_config",
                        "value": project_id,
                    },
                ],
            },
        )
    blocks.append({"type": "divider"})

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
        ux_status = (
            product.get("ux_design_status")
            or product.get("figma_design_status")
            or ""
        )

        # Build status lines — completed steps get a checkmark,
        # in-progress steps show their current phase.
        completed_parts: list[str] = []

        # UX design status
        if ux_status == "completed":
            completed_parts.append(
                ":white_check_mark: UX Design"
            )
        elif ux_status == "generating":
            completed_parts.append(":hourglass_flowing_sand: UX Design in progress")

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
            pass  # Confluence publishing removed from Slack in v0.71.0

        # UX Design buttons
        if ux_status != "generating":
            btn_text = ":art: Start UX Design" if not ux_status else ":art: Retry UX Design"
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": btn_text},
                    "action_id": f"product_ux_design_{idx}",
                    "value": btn_value,
                },
            )

        # Jira buttons removed from Slack in v0.71.0 — Jira ticketing
        # is managed through the web API.

        # Always include "View Details" for fully delivered products
        if conf_published:
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

        # Archive button — always available so users can remove a
        # product from the list without deleting it.
        elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": f":file_folder: Archive #{idx}"},
                "action_id": f"product_archive_{idx}",
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

    # Footer buttons
    from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
        product_list_footer_buttons,
    )
    blocks.extend(product_list_footer_buttons())

    return blocks
