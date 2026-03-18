"""
Slack integration tools for the Product Feature Planner.

Provides tools to send messages, read messages, post PRD results,
and interpret messages via OpenAI for Slack interactions.
"""

from __future__ import annotations

import contextvars
import json
import os
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Thread-local team context
# ---------------------------------------------------------------------------

#: Set by the events / interactions routers before dispatching.  Every
#: downstream call to :func:`_get_slack_client` will pick this up
#: automatically so individual helper functions don't need a ``team_id``
#: parameter.
current_team_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_team_id", default=None,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLACK_BYPASS_KEY = "SLACK_BYPASS"


def _is_bypass() -> bool:
    return os.environ.get(_SLACK_BYPASS_KEY, "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _get_slack_client(team_id: str | None = None):
    """Return a ``slack_sdk.WebClient`` for the given *team_id*.

    Resolution order (handled by ``get_valid_token(team_id)``):
    1. In-memory per-team cache (fast path).
    2. MongoDB ``slackOAuth`` collection.
    3. Token refresh via ``SLACK_CLIENT_ID`` / ``SLACK_CLIENT_SECRET``.
    4. *None* when bypassed or no token is available.

    When *team_id* is ``None`` the function checks the
    :data:`current_team_id` context variable (set by the event /
    interaction routers).  If that is also ``None`` and exactly one
    team is installed, that team's token is used automatically.
    """
    if _is_bypass():
        return None

    resolved_team_id = team_id or current_team_id.get()

    from crewai_productfeature_planner.tools.slack_token_manager import get_valid_token

    token = get_valid_token(resolved_team_id)
    if not token:
        logger.warning("[Slack] No token available team_id=%s — dry-run mode", resolved_team_id)
        return None
    try:
        from slack_sdk import WebClient
        import ssl as _ssl

        ssl_ctx = None
        try:
            import certifi
            ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass

        return WebClient(token=token, ssl=ssl_ctx)
    except ImportError:
        logger.error("slack_sdk is not installed – run `pip install slack_sdk`")
        return None


def _is_token_error(exc: Exception) -> bool:
    err = str(exc).lower()
    return any(kw in err for kw in (
        "token_expired", "token_revoked", "invalid_auth",
        "not_authed", "account_inactive",
    ))


def _retry_on_token_error(exc: Exception, team_id: str | None = None):
    """If *exc* is a token-related error, invalidate and return a fresh client."""
    if not _is_token_error(exc):
        return None

    resolved_team_id = team_id or current_team_id.get()
    logger.warning("[Slack] Token error team_id=%s: %s — refreshing", resolved_team_id, exc)

    from crewai_productfeature_planner.tools.slack_token_manager import (
        get_valid_token,
        invalidate,
    )

    invalidate(resolved_team_id)
    new_token = get_valid_token(resolved_team_id)
    if not new_token:
        return None

    try:
        from slack_sdk import WebClient
        import ssl as _ssl

        ssl_ctx = None
        try:
            import certifi
            ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass

        return WebClient(token=new_token, ssl=ssl_ctx)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class SlackSendMessageInput(BaseModel):
    channel: str = Field(..., description="Slack channel ID or name.")
    text: str = Field(..., description="Message text (supports Slack mrkdwn).")
    thread_ts: Optional[str] = Field(None, description="Thread timestamp.")


class SlackReadMessagesInput(BaseModel):
    channel: str = Field(..., description="Slack channel ID to read from.")
    limit: int = Field(5, ge=1, le=100, description="Number of recent messages.")
    thread_ts: Optional[str] = Field(None, description="Read thread replies instead.")


class SlackPostPRDResultInput(BaseModel):
    channel: str = Field(..., description="Slack channel ID or name.")
    idea: str = Field(..., description="The product idea that was planned.")
    output_file: Optional[str] = Field(None, description="Path to generated PRD markdown.")
    confluence_url: Optional[str] = Field(None, description="Confluence page URL.")
    jira_output: Optional[str] = Field(None, description="Jira tickets summary.")
    thread_ts: Optional[str] = Field(None, description="Thread timestamp.")
    run_id: Optional[str] = Field(None, description="PRD run identifier for action buttons.")


class SlackInterpretMessageInput(BaseModel):
    text: str = Field(..., description="The cleaned Slack message text.")
    conversation_history: Optional[str] = Field(
        None,
        description="JSON-encoded list of prior conversation turns.",
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class SlackSendMessageTool(BaseTool):
    """Send a message to a Slack channel or thread."""

    name: str = "Slack Send Message"
    description: str = "Send a text message to a Slack channel or thread."
    args_schema: Type[BaseModel] = SlackSendMessageInput

    def _run(
        self,
        channel: str = "",
        text: str = "",
        thread_ts: Optional[str] = None,
    ) -> str:
        if _is_bypass():
            return json.dumps({"status": "bypass", "channel": channel, "text": text})

        client = _get_slack_client()
        if client is None:
            return json.dumps({"status": "dry_run", "channel": channel, "text": text})

        kwargs: Dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        try:
            response = client.chat_postMessage(**kwargs)
            return json.dumps({
                "status": "ok",
                "channel": response["channel"],
                "ts": response["ts"],
                "text": text,
            })
        except Exception as exc:
            client = _retry_on_token_error(exc)
            if client is not None:
                try:
                    response = client.chat_postMessage(**kwargs)
                    return json.dumps({
                        "status": "ok",
                        "channel": response["channel"],
                        "ts": response["ts"],
                        "text": text,
                    })
                except Exception as retry_exc:
                    exc = retry_exc
            logger.error("[Slack] Send failed channel=%s thread_ts=%s: %s", channel, thread_ts, exc)
            return json.dumps({"status": "error", "error": str(exc)})


class SlackReadMessagesTool(BaseTool):
    """Read recent messages from a Slack channel or thread."""

    name: str = "Slack Read Messages"
    description: str = "Read recent messages from a Slack channel."
    args_schema: Type[BaseModel] = SlackReadMessagesInput

    def _run(
        self,
        channel: str = "",
        limit: int = 5,
        thread_ts: Optional[str] = None,
    ) -> str:
        if _is_bypass():
            return json.dumps({"status": "bypass", "channel": channel, "messages": []})

        client = _get_slack_client()
        if client is None:
            return json.dumps({"status": "dry_run", "channel": channel, "messages": []})

        def _do_read(c):
            if thread_ts:
                return c.conversations_replies(channel=channel, ts=thread_ts, limit=limit)
            return c.conversations_history(channel=channel, limit=limit)

        try:
            response = _do_read(client)
        except Exception as exc:
            client = _retry_on_token_error(exc)
            if client is not None:
                try:
                    response = _do_read(client)
                except Exception as retry_exc:
                    logger.error("[Slack] Read failed channel=%s: %s", channel, retry_exc)
                    return json.dumps({"status": "error", "error": str(retry_exc)})
            else:
                logger.error("[Slack] Read failed channel=%s: %s", channel, exc)
                return json.dumps({"status": "error", "error": str(exc)})

        messages: List[Dict[str, Any]] = []
        for msg in response.get("messages", []):
            messages.append({
                "user": msg.get("user"),
                "text": msg.get("text", ""),
                "ts": msg.get("ts"),
            })
        return json.dumps({"status": "ok", "channel": channel, "messages": messages})


class SlackPostPRDResultTool(BaseTool):
    """Post a formatted PRD flow result summary to Slack."""

    name: str = "Slack Post PRD Result"
    description: str = (
        "Format and post a summary of a completed PRD flow to a Slack channel."
    )
    args_schema: Type[BaseModel] = SlackPostPRDResultInput

    def _build_blocks(
        self,
        idea: str,
        output_file: Optional[str],
        confluence_url: Optional[str],
        jira_output: Optional[str],
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "PRD Generation Complete"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Idea:* {idea}"},
            },
        ]

        details = []
        if confluence_url:
            details.append(f"*Confluence:* <{confluence_url}|View PRD>")
        if jira_output:
            details.append(f"*Jira:* {jira_output}")

        if details:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(details)},
            })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: PRD has been generated successfully!",
            },
        })

        # Interactive next-step buttons when delivery wasn't completed
        if run_id and (not confluence_url or not jira_output):
            from crewai_productfeature_planner.apis.slack.blocks import (
                delivery_next_step_blocks,
            )
            blocks.extend(
                delivery_next_step_blocks(
                    run_id,
                    show_publish=not confluence_url,
                    show_jira=not jira_output,
                )
            )

        return blocks

    def _run(
        self,
        channel: str = "",
        idea: str = "",
        output_file: Optional[str] = None,
        confluence_url: Optional[str] = None,
        jira_output: Optional[str] = None,
        thread_ts: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> str:
        blocks = self._build_blocks(idea, output_file, confluence_url, jira_output, run_id=run_id)
        fallback_text = f"PRD generation complete for: {idea}"

        if _is_bypass():
            return json.dumps({
                "status": "bypass", "channel": channel,
                "blocks": blocks, "text": fallback_text,
            })

        client = _get_slack_client()
        if client is None:
            return json.dumps({
                "status": "dry_run", "channel": channel,
                "blocks": blocks, "text": fallback_text,
            })

        kwargs: Dict[str, Any] = {
            "channel": channel, "text": fallback_text, "blocks": blocks,
        }
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        try:
            response = client.chat_postMessage(**kwargs)
            msg_result = {
                "status": "ok",
                "channel": response["channel"],
                "ts": response["ts"],
            }
        except Exception as exc:
            client = _retry_on_token_error(exc)
            if client is not None:
                try:
                    response = client.chat_postMessage(**kwargs)
                    msg_result = {
                        "status": "ok",
                        "channel": response["channel"],
                        "ts": response["ts"],
                    }
                except Exception as retry_exc:
                    exc = retry_exc
                    logger.error("[Slack] Post PRD result failed channel=%s run_id=%s: %s", channel, run_id, exc)
                    return json.dumps({"status": "error", "error": str(exc)})
            else:
                logger.error("[Slack] Post PRD result failed channel=%s run_id=%s: %s", channel, run_id, exc)
                return json.dumps({"status": "error", "error": str(exc)})

        # Upload the PRD markdown file to the thread
        if output_file:
            self._upload_prd_file(client, channel, thread_ts, output_file)

        return json.dumps(msg_result)

    @staticmethod
    def _upload_prd_file(
        client,
        channel: str,
        thread_ts: Optional[str],
        output_file: str,
    ) -> None:
        """Upload the PRD markdown file to the Slack thread."""
        import pathlib

        # Resolve absolute path (output_file is workspace-relative)
        path = pathlib.Path(output_file)
        if not path.is_absolute():
            # Try workspace root first, then src/ subfolder
            for base in (
                pathlib.Path.cwd(),
                pathlib.Path.cwd() / "src",
            ):
                candidate = base / path
                if candidate.exists():
                    path = candidate
                    break

        if not path.exists():
            logger.warning(
                "PRD file not found for upload: %s", output_file,
            )
            return

        try:
            upload_kwargs: Dict[str, Any] = {
                "channel": channel,
                "file": str(path),
                "title": path.name,
                "initial_comment": ":page_facing_up: PRD document attached.",
            }
            if thread_ts:
                upload_kwargs["thread_ts"] = thread_ts

            client.files_upload_v2(**upload_kwargs)
            logger.info("[Slack] PRD file uploaded channel=%s file=%s", channel, path.name)
        except Exception as exc:
            logger.warning("[Slack] PRD file upload failed channel=%s: %s", channel, exc)


class SlackInterpretMessageTool(BaseTool):
    """Interpret a Slack message using Gemini LLM to classify intent."""

    name: str = "Slack Interpret Message"
    description: str = (
        "Use Gemini LLM to interpret a Slack message. Returns intent "
        "(create_project/list_projects/switch_project/current_project/"
        "end_session/configure_memory/create_prd/publish/check_publish/"
        "general_question/help/greeting/unknown), idea, and reply text."
    )
    args_schema: Type[BaseModel] = SlackInterpretMessageInput

    def _run(
        self, text: str = "", conversation_history: Optional[str] = None,
    ) -> str:
        from crewai_productfeature_planner.tools.gemini_chat import interpret_message

        logger.info("[Slack] Interpreting message len=%d", len(text))
        history = None
        if conversation_history:
            try:
                history = json.loads(conversation_history)
            except (json.JSONDecodeError, TypeError):
                pass

        result = interpret_message(text, history)
        logger.info("[Slack] Interpreted intent=%s", result.get("intent", "unknown"))
        return json.dumps(result, ensure_ascii=False)
