"""Handler for memory-configuration button clicks."""

from __future__ import annotations

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)


def _handle_memory_action(
    action_id: str,
    user_id: str,
    channel: str,
    thread_ts: str,
) -> None:
    """Process a memory-configuration button click in a background thread.

    In channels only workspace admins may modify memory.
    ``memory_view`` is allowed for all users.
    """
    from crewai_productfeature_planner.apis.slack.blocks import (
        memory_category_prompt_blocks,
        memory_configure_blocks,
        memory_saved_blocks,
        memory_view_blocks,
    )
    from crewai_productfeature_planner.apis.slack.session_manager import (
        can_manage_memory,
        get_context_session,
        mark_pending_memory,
    )
    from crewai_productfeature_planner.mongodb.project_memory import (
        MemoryCategory,
        get_project_memory,
        upsert_project_memory,
    )
    from crewai_productfeature_planner.tools.slack_tools import _get_slack_client

    client = _get_slack_client()
    if not client:
        return

    def _post(blocks=None, text=""):
        try:
            kwargs: dict = {
                "channel": channel,
                "thread_ts": thread_ts,
                "text": text or "Memory update",
            }
            if blocks:
                kwargs["blocks"] = blocks
            client.chat_postMessage(**kwargs)
        except Exception as exc:
            logger.error("Memory action post failed: %s", exc)

    # Admin gate — memory_view is read-only so anyone can use it
    if action_id != "memory_view" and not can_manage_memory(user_id, channel):
        _post(
            text=(
                ":lock: Only workspace admins can configure project "
                "memory in a channel."
            ),
        )
        return

    session = get_context_session(user_id, channel)
    if not session or not session.get("project_id"):
        _post(text=":warning: No active project session. Please select a project first.")
        return

    project_id = session["project_id"]
    project_name = session.get("project_name", "Unknown")

    # Ensure the memory document scaffold exists
    upsert_project_memory(project_id)

    _CATEGORY_MAP = {
        "memory_idea": (
            MemoryCategory.IDEA_ITERATION,
            "Idea & Iteration Guardrails",
            (
                "Describe how agents should behave when iterating "
                "through ideas.  Examples:\n"
                "• _Focus on MVP features only_\n"
                "• _Keep iterations concise, max 3 rounds_\n"
                "• _Prioritise user-facing value over technical debt_\n"
                "• _Follow lean startup methodology_"
            ),
        ),
        "memory_knowledge": (
            MemoryCategory.KNOWLEDGE,
            "Knowledge Links & Documents",
            (
                "Provide links, document references, or notes that "
                "serve as guidelines.  Examples:\n"
                "• _https://wiki.example.com/api-design-guide_\n"
                "• _See the brand guidelines PDF uploaded last week_\n"
                "• _Our API versioning strategy: URI-based /v1/_\n"
                "• _Competitor analysis: https://docs.example.com/competitor_"
            ),
        ),
        "memory_tools": (
            MemoryCategory.TOOLS,
            "Implementation Tools & Technologies",
            (
                "List the tools, databases, frameworks, and algorithms "
                "the team uses.  Examples:\n"
                "• _MongoDB Atlas for persistence_\n"
                "• _FastAPI for REST endpoints_\n"
                "• _React + TypeScript for frontend_\n"
                "• _Redis for caching and pub/sub_\n"
                "• _OpenAI GPT-4o for embeddings_"
            ),
        ),
    }

    try:
        if action_id == "memory_configure":
            _post(
                blocks=memory_configure_blocks(project_name, user_id),
                text="Configure project memory",
            )

        elif action_id in _CATEGORY_MAP:
            cat_enum, cat_label, help_text = _CATEGORY_MAP[action_id]
            mark_pending_memory(
                user_id=user_id,
                channel=channel,
                thread_ts=thread_ts,
                category=cat_enum.value,
                project_id=project_id,
            )
            _post(
                blocks=memory_category_prompt_blocks(
                    cat_enum.value, cat_label, help_text,
                ),
                text=f"Configure {cat_label}",
            )

        elif action_id == "memory_view":
            doc = get_project_memory(project_id) or {}
            _post(
                blocks=memory_view_blocks(
                    project_name,
                    doc.get("idea_iteration", []),
                    doc.get("knowledge", []),
                    doc.get("tools", []),
                ),
                text="Project memory",
            )

        elif action_id == "memory_done":
            _post(
                text=(
                    ":white_check_mark: Memory configuration complete! "
                    "All agents will now recall these guardrails "
                    "during PRD runs."
                ),
            )

    except Exception as exc:
        logger.error("_handle_memory_action failed: %s", exc, exc_info=True)
        _post(text=f":x: Something went wrong: {exc}")
