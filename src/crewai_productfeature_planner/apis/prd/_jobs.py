"""Job tracking response models."""

from pydantic import BaseModel, Field


class JobDetail(BaseModel):
    """A persistent job record from the ``crewJobs`` collection."""

    job_id: str = Field(..., description="Unique job identifier (same as run_id).")
    flow_name: str = Field(..., description="Name of the flow (e.g. 'prd').")
    idea: str = Field(default="", description="The feature idea / input text.")
    status: str = Field(
        ...,
        description=(
            "Job lifecycle status: queued, running, awaiting_approval, "
            "paused, or completed. Note: flow errors always result in "
            "'paused' (not 'failed'), allowing the run to be resumed."
        ),
    )
    error: str | None = Field(
        default=None,
        description=(
            "Error message when the job was paused due to an error. "
            "Present when the job encountered an LLM, billing, or "
            "internal error and was automatically paused."
        ),
    )

    queued_at: str | None = Field(default=None, description="ISO-8601 timestamp when the job was created.")
    started_at: str | None = Field(default=None, description="ISO-8601 timestamp when execution began.")
    completed_at: str | None = Field(
        default=None, description="ISO-8601 timestamp when the job reached a terminal state."
    )

    queue_time_ms: int | None = Field(
        default=None, description="Time spent in queue (started_at - queued_at) in milliseconds."
    )
    queue_time_human: str | None = Field(
        default=None, description="Queue duration in human-readable form (e.g. '0h 1m 30s')."
    )
    running_time_ms: int | None = Field(
        default=None, description="Time spent running (completed_at - started_at) in milliseconds."
    )
    running_time_human: str | None = Field(
        default=None, description="Running duration in human-readable form (e.g. '1h 23m 45s')."
    )
    updated_at: str | None = Field(default=None, description="ISO-8601 timestamp of last update.")
    output_file: str | None = Field(
        default=None,
        description="Path to the generated PRD markdown file, if available.",
    )
    confluence_url: str | None = Field(
        default=None,
        description="URL of the published Confluence page, if available.",
    )


class JobListResponse(BaseModel):
    """Response for GET /flow/jobs."""

    count: int = Field(..., description="Number of jobs returned.")
    jobs: list[JobDetail] = Field(default_factory=list, description="List of job records.")
