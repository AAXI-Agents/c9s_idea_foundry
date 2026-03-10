"""CrewAI BaseTool wrapper for Jira issue creation."""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.tools.jira import _operations as _ops_mod

logger = get_logger(__name__)

# Canonical Jira issue type names.  The LLM often uses variant
# spellings ("task", "Sub-Task", "subtask") — normalise them so
# MongoDB always stores the correct display name.
_ISSUE_TYPE_CANONICAL: dict[str, str] = {
    "epic": "Epic",
    "story": "Story",
    "bug": "Bug",
    "task": "Sub-task",
    "sub-task": "Sub-task",
    "subtask": "Sub-task",
}


def _normalise_issue_type(raw: str, *, has_parent: bool = False) -> str:
    """Return the canonical Jira issue type for *raw*.

    Falls back to ``"Story"`` when the input is empty or unrecognised,
    except when *has_parent* is ``True`` (the issue has a ``parent_key``
    or ``epic_key``), in which case the fallback is ``"Sub-task"``.
    """
    key = raw.strip().lower()
    canonical = _ISSUE_TYPE_CANONICAL.get(key)
    if canonical:
        return canonical
    # Exact-case match (e.g. "Story" as-is)
    if raw.strip() in ("Epic", "Story", "Sub-task", "Bug"):
        return raw.strip()
    # Context-based inference
    if has_parent:
        return "Sub-task"
    return "Story"

# Lazy import to avoid circular dependency at module load time.
# Imported here so tests can patch it at
# ``crewai_productfeature_planner.tools.jira._tool.find_run_any_status``.
from crewai_productfeature_planner.mongodb.working_ideas._queries import (  # noqa: E402
    find_run_any_status,
)


def _resolve_confluence_url(run_id: str, llm_provided_url: str) -> str:
    """Return the authoritative Confluence URL for a run.

    Resolution order:
        1. MongoDB ``working_ideas`` document for *run_id* — this is the
           URL recorded by the actual Confluence publish step and is
           always correct.
        2. The *llm_provided_url* — only used as fallback when MongoDB
           lookup fails (e.g. no DB connection).

    The LLM frequently hallucinates fake confluence URLs like
    ``https://confluence.internal/pages/…`` or
    ``https://confluence.example.com/display/…`` instead of using the
    real URL provided in the task description.  By resolving from
    MongoDB we guarantee the correct URL ends up in ticket descriptions.
    """
    if not run_id:
        return llm_provided_url

    try:
        doc = find_run_any_status(run_id)
        if doc:
            db_url = doc.get("confluence_url", "")
            if db_url:
                if llm_provided_url and llm_provided_url != db_url:
                    logger.info(
                        "[Jira] Overriding LLM-provided confluence_url "
                        "(%s) with authoritative MongoDB value (%s)",
                        llm_provided_url, db_url,
                    )
                return db_url
    except Exception:  # noqa: BLE001
        logger.debug(
            "[Jira] Could not resolve confluence_url from MongoDB "
            "for run_id=%s — using LLM-provided value",
            run_id, exc_info=True,
        )
    return llm_provided_url


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

        # Normalise the LLM-provided issue_type to a canonical value
        # so MongoDB never stores "unknown", "task", "Sub-Task", etc.
        issue_type = _normalise_issue_type(
            issue_type, has_parent=bool(effective_parent and issue_type != "Epic"),
        )

        # ── Resolve authoritative Confluence URL from MongoDB ─────
        # The LLM often hallucinates fake URLs (e.g.
        # "https://confluence.internal/pages/...") instead of using the
        # real value.  Always prefer the URL stored in MongoDB, which
        # was set by the actual Confluence publish step.
        resolved_confluence_url = _resolve_confluence_url(run_id, confluence_url)

        try:
            result = _ops_mod.create_jira_issue(
                summary=summary,
                description=description,
                issue_type=issue_type,
                epic_key=effective_parent,
                labels=label_list,
                priority=priority,
                run_id=run_id,
                confluence_url=resolved_confluence_url,
                component=component,
            )

            created_key = result["issue_key"]

            # ── Persist ticket to MongoDB immediately ─────────
            if run_id and created_key:
                try:
                    from crewai_productfeature_planner.mongodb.product_requirements import (
                        append_jira_ticket,
                    )
                    append_jira_ticket(run_id, {
                        "key": created_key,
                        "type": issue_type,
                        "summary": summary,
                        "url": result.get("url", ""),
                        "reused": result.get("reused", False),
                    })
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[Jira] Failed to persist ticket %s to MongoDB: %s",
                        created_key, exc,
                    )

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
