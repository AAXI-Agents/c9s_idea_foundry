"""Retry helper for LLM-backed crew operations.

Wraps ``crew.kickoff()`` so that transient LLM failures (timeouts 、
rate-limits, server errors) are retried with exponential back-off
instead of killing the entire flow.

Usage::

    from crewai_productfeature_planner.retry import crew_kickoff_with_retry

    result = crew_kickoff_with_retry(crew, step_label="initial_draft")

Configuration via environment variables:

- ``LLM_MAX_RETRIES`` — total retry attempts (default 3).
- ``LLM_RETRY_BASE_DELAY`` — base delay in seconds for exponential
  back-off (default 5).
"""

import os
import time

from crewai import Crew

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 5  # seconds

# Patterns that indicate a billing / account issue (not transient).
_BILLING_PATTERNS: list[str] = [
    "insufficient_quota",
    "invalid_api_key",
    "billing_hard_limit_reached",
    "billing_not_active",
    "exceeded your current quota",
    "account_deactivated",
]

# Patterns that indicate the model is temporarily overloaded (503).
# Not worth retrying immediately — pause the flow and let the
# periodic resume pick it up in ~5 minutes.
_MODEL_BUSY_PATTERNS: list[str] = [
    "currently experiencing high demand",
    "model is overloaded",
    "model is currently overloaded",
    "the model is currently busy",
    "503 unavailable",
    "service unavailable",
    "try again later",
]


class LLMError(RuntimeError):
    """Raised when an OpenAI / LLM error causes all retries to be exhausted.

    Callers should treat this as a recoverable pause — the user can fix the
    issue and resume the flow.
    """


class BillingError(LLMError):
    """Raised when an OpenAI billing / quota error is detected.

    Callers should treat this as non-retryable and pause the flow so the
    user can fix their billing before running again.
    """


class ModelBusyError(LLMError):
    """Raised when the LLM reports a 503 / model-overloaded error.

    Not retried — the flow is paused immediately so the periodic
    resume (every ~5 minutes) can pick it up when load subsides,
    avoiding wasted retry waits.
    """


def _get_max_retries() -> int:
    return int(os.environ.get("LLM_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))


def _get_base_delay() -> float:
    return float(os.environ.get("LLM_RETRY_BASE_DELAY", str(DEFAULT_RETRY_BASE_DELAY)))


def crew_kickoff_with_retry(
    crew: Crew,
    *,
    step_label: str = "",
    max_retries: int | None = None,
    base_delay: float | None = None,
):
    """Execute ``crew.kickoff()`` with exponential-backoff retries.

    Args:
        crew: A fully-configured ``Crew`` instance.
        step_label: Human-readable label for log messages (e.g. "initial_draft").
        max_retries: Override retry count (defaults to ``LLM_MAX_RETRIES`` env var).
        base_delay: Override base delay in seconds (defaults to env var).

    Returns:
        The ``CrewOutput`` from a successful ``crew.kickoff()`` call.

    Raises:
        The last exception if all attempts are exhausted.
    """
    retries = max_retries if max_retries is not None else _get_max_retries()
    delay = base_delay if base_delay is not None else _get_base_delay()
    last_exc: Exception | None = None

    for attempt in range(1, retries + 2):  # attempt 1 = first try, +retries
        try:
            result = crew.kickoff()
            if attempt > 1:
                logger.info(
                    "[Retry] %s succeeded on attempt %d/%d",
                    step_label,
                    attempt,
                    retries + 1,
                )
            return result
        except Exception as exc:
            last_exc = exc
            # Don't retry on non-transient billing / account errors
            exc_str = str(exc).lower()
            if any(pat in exc_str for pat in _BILLING_PATTERNS):
                logger.error(
                    "[Retry] %s hit a non-retryable billing error: %s",
                    step_label, exc,
                )
                raise BillingError(str(exc)) from exc
            # Don't retry on 503 model-busy errors — pause immediately
            # and let the periodic resume pick it up later.
            if any(pat in exc_str for pat in _MODEL_BUSY_PATTERNS):
                logger.warning(
                    "[Retry] %s hit model-busy (503) — pausing flow "
                    "for later resume: %s",
                    step_label, exc,
                )
                raise ModelBusyError(str(exc)) from exc
            if attempt <= retries:
                wait = delay * (2 ** (attempt - 1))
                logger.warning(
                    "[Retry] %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    step_label,
                    attempt,
                    retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "[Retry] %s failed after %d attempts: %s",
                    step_label,
                    retries + 1,
                    exc,
                )

    raise LLMError(str(last_exc)) from last_exc  # type: ignore[misc]
