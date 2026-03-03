"""Standard error response model."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error envelope returned by all API endpoints.

    Returned for any unexpected server-side error (HTTP 500) or when
    the upstream LLM / OpenAI service is unavailable (HTTP 503).

    Error codes:
        ``LLM_ERROR``      — The LLM backend returned an unrecoverable
                             error after exhausting all retry attempts
                             (e.g. timeouts, model overload).
        ``BILLING_ERROR``  — OpenAI billing / quota issue detected
                             (e.g. ``insufficient_quota``,
                             ``billing_hard_limit_reached``).
        ``INTERNAL_ERROR`` — Any other unexpected server-side failure.
    """

    error_code: str = Field(
        ...,
        description=(
            "Machine-readable error code. One of: "
            "LLM_ERROR, BILLING_ERROR, INTERNAL_ERROR."
        ),
        examples=["LLM_ERROR"],
    )
    message: str = Field(
        ...,
        description="Human-readable description of the error.",
        examples=["LLM timeout after 4 attempts"],
    )
    run_id: str | None = Field(
        default=None,
        description="The run_id affected by this error, if applicable.",
        examples=["a1b2c3d4e5f6"],
    )
    detail: str | None = Field(
        default=None,
        description="Additional diagnostic detail (e.g. the original exception message).",
    )
