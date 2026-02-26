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
) -> None:
    """Execute the PRD flow and post results to Slack."""
    from crewai_productfeature_planner.apis.prd.service import run_prd_flow
    from crewai_productfeature_planner.apis.shared import FlowRun, FlowStatus, runs
    from crewai_productfeature_planner.mongodb.crew_jobs import create_job
    from crewai_productfeature_planner.tools.slack_tools import (
        SlackPostPRDResultTool,
        SlackSendMessageTool,
    )

    send_tool = SlackSendMessageTool()

    # Create the FlowRun record and crew job
    runs[run_id] = FlowRun(run_id=run_id, flow_name="prd")
    create_job(run_id, idea)

    try:
        if notify:
            send_tool.run(
                channel=channel,
                text=f":memo: Starting PRD generation for:\n> _{idea}_",
                thread_ts=thread_ts or "",
            )

        # Run the PRD flow (blocks until complete)
        run_prd_flow(run_id, idea, auto_approve=auto_approve)

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
    dependencies=[Depends(verify_slack_request)],
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
    dependencies=[Depends(verify_slack_request)],
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
