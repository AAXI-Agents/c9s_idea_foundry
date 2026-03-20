"""Pydantic response / request models for the Publishing API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Response models ──────────────────────────────────────────────────


class PendingPRDItem(BaseModel):
    """A single PRD pending publishing or Jira ticketing."""

    run_id: str = Field(..., description="Unique flow run identifier.")
    title: str = Field(..., description="Page title (e.g. 'Fitness App Feature').")
    source: str = Field("mongodb", description="Discovery source: 'mongodb' or 'disk'.")
    output_file: str = Field("", description="Absolute path to the output markdown file.")
    confluence_published: bool = Field(False, description="Whether Confluence page exists.")
    confluence_url: str = Field("", description="URL of the Confluence page (empty if unpublished).")
    jira_completed: bool = Field(False, description="Whether Jira tickets have been created.")
    jira_tickets: list[dict] = Field(default_factory=list, description="List of Jira ticket dicts.")
    status: str = Field("new", description="Delivery status: new | inprogress | completed.")


class PendingListResponse(BaseModel):
    """List of PRDs pending Confluence / Jira delivery."""

    count: int = Field(..., description="Total number of pending items.")
    items: list[PendingPRDItem] = Field(default_factory=list, description="Pending PRD items.")


class ConfluencePublishResult(BaseModel):
    """Result from a single Confluence publish operation."""

    run_id: str = Field(..., description="Run identifier.")
    title: str = Field("", description="Page title.")
    url: str = Field("", description="Confluence page URL.")
    page_id: str = Field("", description="Confluence page ID.")
    action: str = Field("created", description="'created' or 'updated'.")


class ConfluenceBatchResult(BaseModel):
    """Summary of a batch Confluence publish operation."""

    published: int = Field(0, description="Number successfully published.")
    failed: int = Field(0, description="Number that failed.")
    results: list[ConfluencePublishResult] = Field(
        default_factory=list, description="Per-item results.",
    )
    errors: list[dict] = Field(default_factory=list, description="Per-item errors.")
    message: str = Field("", description="Optional summary message.")


class JiraCreateResult(BaseModel):
    """Result from Jira ticket creation for a single run."""

    run_id: str = Field(..., description="Run identifier.")
    jira_completed: bool = Field(True, description="Whether Jira creation succeeded.")
    ticket_keys: list[str] = Field(default_factory=list, description="Created Jira issue keys.")
    progress: list[str] = Field(default_factory=list, description="Progress messages from the crew.")


class JiraBatchResult(BaseModel):
    """Summary of a batch Jira ticket creation."""

    completed: int = Field(0, description="Number successfully completed.")
    failed: int = Field(0, description="Number that failed.")
    results: list[JiraCreateResult] = Field(default_factory=list, description="Per-item results.")
    errors: list[dict] = Field(default_factory=list, description="Per-item errors.")
    message: str = Field("", description="Optional summary message.")


class CombinedPublishResult(BaseModel):
    """Combined Confluence publish + Jira creation result."""

    run_id: str = Field("", description="Run identifier (single-run) or empty (batch).")
    confluence: dict = Field(default_factory=dict, description="Confluence publish result.")
    jira: dict = Field(default_factory=dict, description="Jira creation result.")


class DeliveryStatusResponse(BaseModel):
    """Full delivery status for a run_id from the productRequirements collection."""

    run_id: str = Field(..., description="Run identifier.")
    confluence_published: bool = Field(False, description="Confluence page exists.")
    confluence_url: str = Field("", description="Confluence page URL.")
    confluence_page_id: str = Field("", description="Confluence page ID.")
    jira_completed: bool = Field(False, description="Jira tickets created.")
    jira_tickets: list[dict] = Field(default_factory=list, description="Created Jira tickets.")
    status: str = Field("new", description="new | inprogress | completed.")
    error: str | None = Field(None, description="Last error if any.")


class WatcherStatusResponse(BaseModel):
    """Status of the file watcher and cron scheduler."""

    watcher_running: bool = Field(False, description="Whether the file watcher is active.")
    watcher_directory: str = Field("", description="Directory being watched.")
    scheduler_running: bool = Field(False, description="Whether the cron scheduler is active.")
    scheduler_interval_seconds: int = Field(0, description="Scan interval in seconds.")


class PublishingErrorResponse(BaseModel):
    """Standard error envelope for publishing endpoints."""

    error_code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    detail: str = Field("", description="Additional details.")
