"""Slack-triggered PRD flow router.

Provides ``/slack/kickoff`` and ``/slack/kickoff/sync`` endpoints
that accept a natural-language idea from Slack and kick off the
PRD generation flow, posting results back to the Slack channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException

from crewai_productfeature_planner.apis.slack.verify import verify_slack_request
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

DEFAULT_SLACK_CHANNEL = "crewai-prd-planner"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

from typing import Optional

from pydantic import BaseModel, Field


class SlackPRDKickoffRequest(BaseModel):
    """Payload to start a PRD flow triggered via Slack."""

    channel: Optional[str] = Field(
        default=None,
        description=(
            "Slack channel name or ID to post results to. "
            "Defaults to ``SLACK_DEFAULT_CHANNEL`` env var."
        ),
        json_schema_extra={"example": "crewai-prd-planner"},
    )
    text: Optional[str] = Field(
        None,
        description=(
            "Natural-language product idea / feature description. "
            "E.g. 'create a PRD for a mobile fitness app'"
        ),
        json_schema_extra={"example": "create a PRD for a mobile fitness app"},
    )
    auto_approve: bool = Field(
        default=True,
        description="Run the full flow without pausing for manual approval.",
    )
    interactive: bool = Field(
        default=False,
        description=(
            "Enable interactive mode — mirrors the CLI experience in Slack. "
            "Prompts the user to choose refinement mode (agent/manual), "
            "approve the refined idea, and approve the requirements "
            "breakdown using Block Kit buttons before auto-generating "
            "all PRD sections.  Overrides ``auto_approve`` when ``True``."
        ),
    )
    notify: bool = Field(
        default=True,
        description="Post status updates and results back to the Slack channel.",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional callback URL for result delivery.",
        json_schema_extra={"example": "https://example.com/webhooks/prd-result"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "channel": "crewai-prd-planner",
                "text": "create a PRD for a mobile fitness tracking app",
                "auto_approve": True,
                "interactive": False,
                "notify": True,
            }
        }
    }


class SlackPRDKickoffResponse(BaseModel):
    """Returned after a Slack-triggered PRD kickoff."""

    run_id: str = Field(..., description="Unique identifier for the PRD flow run")
    status: str = Field(..., description="Current job status")
    idea: Optional[str] = Field(None, description="The extracted product idea")


# ---------------------------------------------------------------------------
# Flow runner
# ---------------------------------------------------------------------------


def _resolve_channel(req: SlackPRDKickoffRequest) -> str:
    if req.channel:
        return req.channel
    return os.environ.get("SLACK_DEFAULT_CHANNEL", "").strip() or DEFAULT_SLACK_CHANNEL


def _deliver_webhook(run_id: str, result: dict | None, error: str | None, webhook_url: str) -> None:
    """POST the flow result to the webhook URL."""
    import httpx

    payload = {
        "run_id": run_id,
        "status": "completed" if result else "failed",
        "result": result,
        "error": error,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
        logger.info("Webhook delivered for run %s to %s", run_id, webhook_url)
    except Exception as exc:
        logger.error("Webhook delivery failed for run %s: %s", run_id, exc)


def _run_slack_prd_flow(
    run_id: str,
    idea: str,
    channel: str,
    thread_ts: str | None = None,
    notify: bool = True,
    auto_approve: bool = True,
    webhook_url: str | None = None,
    project_id: str | None = None,
) -> None:
    """Execute the PRD flow and post results to Slack.

    If *project_id* is provided, the working-idea document is linked
    to the project after the flow completes.
    """
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
    from crewai_productfeature_planner.mongodb.crew_jobs import create_job
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackPostPRDResultTool,
        SlackSendMessageTool,
    )
    from crewai_productfeature_planner.apis.slack._flow_handlers import (
        make_progress_poster,
    )

    send_tool = SlackSendMessageTool()

    # Build progress callback for live heartbeat messages
    progress_cb = make_progress_poster(
        channel=channel,
        thread_ts=thread_ts or "",
        user="",  # not needed for progress messages
        send_tool=send_tool,
        run_id=run_id,
    )

    # Create the FlowRun record and crew job
    runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")
    create_job(run_id, idea, slack_channel=channel, slack_thread_ts=thread_ts or "")

    # Persist Slack context so auto-resume can notify the same thread
    try:
        from crewai_productfeature_planner.mongodb.working_ideas.repository import (
            save_slack_context,
        )
        save_slack_context(run_id, channel, thread_ts or "")
    except Exception:  # noqa: BLE001
        logger.debug("save_slack_context failed for %s", run_id, exc_info=True)

    try:
        if notify:
            send_tool.run(
                channel=channel,
                text=f":memo: Starting PRD generation for:\n> _{idea}_",
                thread_ts=thread_ts or "",
            )

        # Run the PRD flow (blocks until complete)
        run_prd_flow(
            run_id, idea,
            auto_approve=auto_approve,
            progress_callback=progress_cb,
        )

        # Link working idea to project (doc exists after flow completes)
        if project_id:
            try:
                from crewai_productfeature_planner.mongodb.working_ideas.repository import (
                    save_project_ref,
                )
                save_project_ref(run_id, project_id)
            except Exception:  # noqa: BLE001
                logger.debug("save_project_ref failed for %s", run_id, exc_info=True)

        run = runs.get(run_id)
        if run and run.status == FlowStatus.COMPLETED:
            if notify:
                post_tool = SlackPostPRDResultTool()
                post_tool.run(
                    channel=channel,
                    idea=idea,
                    output_file=run.output_file,
                    confluence_url=run.confluence_url,
                    jira_output=run.jira_output,
                    thread_ts=thread_ts or "",
                )
            logger.info("Slack PRD flow %s completed", run_id)
        elif run and run.status == FlowStatus.PAUSED:
            if notify:
                send_tool.run(
                    channel=channel,
                    text=(
                        f":pause_button: PRD flow paused (run_id: `{run_id}`). "
                        "Resume via the API or retry later."
                    ),
                    thread_ts=thread_ts or "",
                )
        else:
            error_msg = run.error if run else "Unknown error"
            if notify:
                send_tool.run(
                    channel=channel,
                    text=f":x: PRD flow failed: {error_msg}",
                    thread_ts=thread_ts or "",
                )

    except Exception as exc:
        logger.error("Slack PRD flow %s failed: %s", run_id, exc)
        if notify:
            try:
                send_tool.run(
                    channel=channel,
                    text=f":x: PRD flow failed: {exc}",
                    thread_ts=thread_ts or "",
                )
            except Exception:
                pass

    finally:
        if webhook_url:
            run = runs.get(run_id)
            _deliver_webhook(
                run_id,
                result=run.result if run else None,
                error=run.error if run else None,
                webhook_url=webhook_url,
            )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/slack/kickoff",
    response_model=SlackPRDKickoffResponse,
    tags=["Slack Messenger"],
    summary="Start a Slack-triggered PRD flow (async)",
    response_description="Job accepted – poll ``/flow/runs/{run_id}`` for progress",
    description=(
        "Accepts a natural-language product idea from Slack and kicks off the "
        "full PRD generation flow asynchronously. The API responds immediately "
        "with the ``run_id``; the flow runs in a background thread.\n\n"
        "**Flow phases:**\n\n"
        "1. **Idea Refinement** — A Gemini-powered agent enriches the raw idea "
        "(3–10 cycles).\n"
        "2. **Requirements Breakdown** — The enriched idea is decomposed into "
        "structured requirements.\n"
        "3. **Phase 1: Executive Summary** — Iterative drafting and critique.\n"
        "4. **Phase 2: Sections** — 9 remaining PRD sections are drafted, "
        "critiqued, and auto-approved.\n"
        "5. **Post-completion** — Publishes to Confluence, creates Jira tickets, "
        "and posts a summary back to the Slack channel (when ``notify=true``).\n\n"
        "**Interactive mode** (``interactive=true``): mirrors the CLI experience "
        "inside Slack using Block Kit buttons — the user chooses refinement mode, "
        "approves the idea, and approves requirements before auto-generating "
        "sections. Overrides ``auto_approve`` when enabled.\n\n"
        "**Webhook callback** (``webhook_url``): when provided, the server sends "
        "a ``POST`` with a JSON payload on completion or failure:\n\n"
        "```json\n"
        "{\n"
        '  "run_id": "a1b2c3d4e5f6",\n'
        '  "status": "completed",\n'
        '  "result": { ... },\n'
        '  "error": null\n'
        "}\n"
        "```\n\n"
        "**Authentication**: requires a valid Slack signing secret "
        "(``SLACK_SIGNING_SECRET``) via HMAC-SHA256 header verification.\n\n"
        "Poll ``GET /flow/runs/{run_id}`` for progress updates."
    ),
    dependencies=[Depends(verify_slack_request)],
    responses={
        200: {"description": "PRD flow accepted and running in background."},
        422: {"description": "No idea text provided."},
    },
)
async def slack_kickoff(req: SlackPRDKickoffRequest) -> SlackPRDKickoffResponse:
    """Parse a natural-language Slack command and kick off the PRD flow.

    The flow will:
    1. Refine the idea
    2. Break down requirements
    3. Generate all PRD sections
    4. Post a summary back to Slack

    Supply ``webhook_url`` to receive a POST with the result when done.
    """
    if not req.text:
        raise HTTPException(status_code=422, detail="No idea text provided")

    channel = _resolve_channel(req)
    req.channel = channel
    run_id = uuid.uuid4().hex[:12]

    if req.interactive:
        from crewai_productfeature_planner.apis.slack.interactive_handlers import (
            run_interactive_slack_flow,
        )
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            run_interactive_slack_flow,
            run_id,
            req.text,
            channel,
            None,  # thread_ts
            "",   # user (unknown from API call)
            req.notify,
            req.webhook_url,
        )
    else:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _run_slack_prd_flow,
            run_id,
            req.text,
            channel,
            None,  # thread_ts
            req.notify,
            req.auto_approve,
            req.webhook_url,
        )

    return SlackPRDKickoffResponse(
        run_id=run_id,
        status="pending",
        idea=req.text,
    )


@router.post(
    "/slack/kickoff/sync",
    response_model=SlackPRDKickoffResponse,
    tags=["Slack Messenger"],
    summary="Start a Slack-triggered PRD flow (synchronous)",
    response_description="Completed PRD flow result",
    description=(
        "Synchronous variant of ``POST /slack/kickoff``. Runs the full PRD "
        "flow and blocks until completion before returning the result.\n\n"
        "The response includes the final ``status`` (``completed`` or "
        "``paused``), the generated ``result`` content, and any ``error`` "
        "message.\n\n"
        "**Warning**: this endpoint may take several minutes to respond "
        "depending on the complexity of the idea and LLM response times. "
        "Use the async ``POST /slack/kickoff`` endpoint for production "
        "workloads.\n\n"
        "Supports the same request body as the async endpoint, including "
        "``webhook_url`` for result delivery and ``notify`` for Slack "
        "channel updates.\n\n"
        "**Authentication**: requires a valid Slack signing secret "
        "(``SLACK_SIGNING_SECRET``) via HMAC-SHA256 header verification."
    ),
    dependencies=[Depends(verify_slack_request)],
    responses={
        200: {"description": "PRD flow completed; result returned inline."},
        422: {"description": "No idea text provided."},
    },
)
async def slack_kickoff_sync(req: SlackPRDKickoffRequest) -> dict:
    """Synchronous Slack-triggered PRD kickoff.

    Runs the full flow and returns after completion.
    """
    if not req.text:
        raise HTTPException(status_code=422, detail="No idea text provided")

    channel = _resolve_channel(req)
    req.channel = channel
    run_id = uuid.uuid4().hex[:12]

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _run_slack_prd_flow,
        run_id,
        req.text,
        channel,
        None,
        req.notify,
        req.auto_approve,
        req.webhook_url,
    )

    from crewai_productfeature_planner.apis.shared import runs
    run = runs.get(run_id)
    if run:
        return {
            "run_id": run_id,
            "status": run.status.value,
            "idea": req.text,
            "result": run.result,
            "error": run.error,
        }
    return {"run_id": run_id, "status": "failed", "idea": req.text}
