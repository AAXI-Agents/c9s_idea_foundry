"""CrewAI BaseTool wrapper for Jira issue creation."""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.jira import _operations as _ops_mod

logger = get_logger(__name__)


class JiraCreateIssueInput(BaseModel):
    """Input schema for JiraCreateIssueTool."""

    summary: str = Field(
        ...,
        description="Issue summary / title.",
    )
    description: str = Field(
        default="",
        description="Detailed description of the issue.",
    )
    issue_type: str = Field(
        default="Story",
        description="Jira issue type: Story, Task, Epic, or Bug.",
    )
    epic_key: str = Field(
        default="",
        description="Parent epic key to link this issue under (e.g. 'PRD-42').",
    )
    labels: str = Field(
        default="",
        description="Comma-separated labels to apply (e.g. 'prd,auto-generated').",
    )
    priority: str = Field(
        default="",
        description="Priority name: Highest, High, Medium, Low, Lowest.",
    )
    run_id: str = Field(
        default="",
        description="Optional run ID for tracking/logging.",
    )
    confluence_url: str = Field(
        default="",
        description="Confluence page URL to tag in the ticket description.",
    )
    component: str = Field(
        default="",
        description="Component/role name (e.g. 'UX', 'Engineering', 'QE').",
    )
    parent_key: str = Field(
        default="",
        description="Parent issue key for sub-tasks (e.g. 'PRD-101'). "
        "Used for Task issues under a Story.",
    )
    blocks_key: str = Field(
        default="",
        description="Issue key that this ticket blocks (creates a 'Blocks' link).",
    )
    is_blocked_by_key: str = Field(
        default="",
        description="Issue key that blocks this ticket (creates an 'is blocked by' link).",
    )


class JiraCreateIssueTool(BaseTool):
    """Creates a Jira issue (Story, Task, Epic, or Bug) in the configured project.

    Supports:
    - Epic → Story → Task hierarchy via ``epic_key`` and ``parent_key``
    - Confluence URL tagging in descriptions
    - Component/role designation (UX, Engineering, QE)
    - Dependency linking via ``blocks_key`` / ``is_blocked_by_key``
    """

    name: str = "jira_create_issue"
    description: str = (
        "Creates a Jira issue in the configured Atlassian Jira project. "
        "Supports Stories, Tasks, Epics, and Bugs. "
        "Use this to create tickets for PRD requirements, action items, "
        "and feature tracking.  Supports Epic→Story→Task hierarchy, "
        "Confluence URL tagging, component/role assignment (UX, Engineering, QE), "
        "and dependency linking (blocks / is blocked by)."
    )
    args_schema: Type[BaseModel] = JiraCreateIssueInput

    def _run(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "Story",
        epic_key: str = "",
        labels: str = "",
        priority: str = "",
        run_id: str = "",
        confluence_url: str = "",
        component: str = "",
        parent_key: str = "",
        blocks_key: str = "",
        is_blocked_by_key: str = "",
    ) -> str:
        label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []

        # parent_key takes precedence for sub-tasks; epic_key is the fallback
        effective_parent = parent_key or epic_key

        try:
            result = _ops_mod.create_jira_issue(
                summary=summary,
                description=description,
                issue_type=issue_type,
                epic_key=effective_parent,
                labels=label_list,
                priority=priority,
                run_id=run_id,
                confluence_url=confluence_url,
                component=component,
            )

            created_key = result["issue_key"]

            # Create dependency links if requested
            if blocks_key:
                try:
                    _ops_mod.create_issue_link(
                        inward_issue_key=blocks_key,
                        outward_issue_key=created_key,
                        link_type="Blocks",
                    )
                except Exception as exc:
                    logger.warning(
                        "[Jira] Failed to create 'Blocks' link %s → %s: %s",
                        created_key, blocks_key, exc,
                    )
            if is_blocked_by_key:
                try:
                    _ops_mod.create_issue_link(
                        inward_issue_key=created_key,
                        outward_issue_key=is_blocked_by_key,
                        link_type="Blocks",
                    )
                except Exception as exc:
                    logger.warning(
                        "[Jira] Failed to create 'is blocked by' link %s → %s: %s",
                        created_key, is_blocked_by_key, exc,
                    )

            return (
                f"Jira {issue_type} created: "
                f"key={result['issue_key']} url={result['url']}"
            )
        except EnvironmentError as exc:
            return f"Jira issue creation skipped: {exc}"
        except Exception as exc:
            logger.error("[Jira] Create issue failed: %s", exc)
            return f"Jira issue creation failed: {exc}"
