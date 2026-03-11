"""Tests for the crew_kickoff_with_retry helper."""

import time
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.retry import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT_BASE_DELAY,
    DEFAULT_RATE_LIMIT_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    BillingError,
    LLMError,
    ModelBusyError,
    ShutdownError,
    crew_kickoff_with_retry,
)


def _make_crew(side_effect=None, return_value=None):
    """Build a mock Crew whose kickoff() behaviour is controllable."""
    crew = MagicMock()
    if side_effect is not None:
        crew.kickoff.side_effect = side_effect
    else:
        crew.kickoff.return_value = return_value or MagicMock(raw="ok")
    return crew


# ── Success paths ─────────────────────────────────────────────


def test_succeeds_on_first_attempt():
    """No retries needed when kickoff succeeds immediately."""
    crew = _make_crew(return_value=MagicMock(raw="# PRD"))
    result = crew_kickoff_with_retry(crew, step_label="test")
    assert result.raw == "# PRD"
    assert crew.kickoff.call_count == 1


def test_succeeds_on_retry(monkeypatch):
    """Should succeed when kickoff fails then succeeds on retry."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    ok = MagicMock(raw="done")
    crew = _make_crew(side_effect=[RuntimeError("timeout"), ok])

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        result = crew_kickoff_with_retry(crew, step_label="test", base_delay=0)

    assert result.raw == "done"
    assert crew.kickoff.call_count == 2


# ── Failure paths ─────────────────────────────────────────────


def test_raises_after_exhausting_retries(monkeypatch):
    """Should raise LLMError wrapping the last exception after all retries are exhausted."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    crew = _make_crew(side_effect=RuntimeError("LLM timeout"))

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        with pytest.raises(LLMError, match="LLM timeout"):
            crew_kickoff_with_retry(crew, step_label="test", base_delay=0)

    # 1 initial + 1 retry = 2 attempts
    assert crew.kickoff.call_count == 2


def test_zero_retries_raises_immediately():
    """With max_retries=0, should fail on first error with LLMError."""
    crew = _make_crew(side_effect=RuntimeError("boom"))
    with pytest.raises(LLMError, match="boom"):
        crew_kickoff_with_retry(crew, step_label="test", max_retries=0)
    assert crew.kickoff.call_count == 1


# ── Exponential back-off ──────────────────────────────────────


def test_exponential_backoff_delays():
    """Sleep durations should follow exponential back-off."""
    crew = _make_crew(
        side_effect=[
            RuntimeError("e1"),
            RuntimeError("e2"),
            RuntimeError("e3"),
            MagicMock(raw="ok"),
        ],
    )

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=2.0,
        )

    assert result.raw == "ok"
    # Filter out noise from background threads that may call time.sleep()
    # while the mock is active (the patch intercepts ALL time.sleep calls
    # since retry.time IS the global time module).
    delays = [
        call.args[0] for call in mock_sleep.call_args_list
        if call.args[0] >= 1.0
    ]
    assert delays == [2.0, 4.0, 8.0]  # 2^0 * 2, 2^1 * 2, 2^2 * 2


# ── Env var overrides ─────────────────────────────────────────


def test_env_var_max_retries(monkeypatch):
    """LLM_MAX_RETRIES env var should control retry count."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    crew = _make_crew(side_effect=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        crew_kickoff_with_retry(crew, step_label="test")
    assert crew.kickoff.call_count == 1


def test_env_var_base_delay(monkeypatch):
    """LLM_RETRY_BASE_DELAY env var should control initial delay."""
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY", "10")
    crew = _make_crew(side_effect=[RuntimeError("e1"), MagicMock(raw="ok")])

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        crew_kickoff_with_retry(crew, step_label="test", max_retries=1)

    mock_sleep.assert_called_once_with(10.0)


# ── Non-retryable errors ──────────────────────────────────────


@pytest.mark.parametrize("error_msg,match_str", [
    (
        "Error code: 429 - {'error': {'type': 'insufficient_quota', "
        "'code': 'insufficient_quota'}}",
        "insufficient_quota",
    ),
    ("invalid_api_key: bad key", "invalid_api_key"),
    ("billing_hard_limit_reached", "billing_hard_limit_reached"),
    (
        "You exceeded your current quota, check your plan and billing details.",
        "exceeded your current quota",
    ),
])
def test_billing_error_not_retried(error_msg, match_str):
    """Billing errors should raise BillingError immediately without retrying."""
    crew = _make_crew(side_effect=RuntimeError(error_msg))
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(BillingError, match=match_str):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.parametrize("child,parent", [
    (BillingError, RuntimeError),
    (BillingError, LLMError),
    (LLMError, RuntimeError),
    (ModelBusyError, LLMError),
    (ModelBusyError, RuntimeError),
    (ShutdownError, LLMError),
    (ShutdownError, RuntimeError),
])
def test_error_hierarchy(child, parent):
    """Custom error types should form the documented inheritance hierarchy."""
    assert issubclass(child, parent)


def test_exhausted_retries_wraps_original():
    """LLMError raised after retry exhaustion should chain the original exception."""
    original = RuntimeError("LLM timeout after 30s")
    crew = _make_crew(side_effect=original)
    with pytest.raises(LLMError, match="LLM timeout after 30s") as exc_info:
        crew_kickoff_with_retry(crew, step_label="test", max_retries=0)
    assert exc_info.value.__cause__ is original


# ── Model Busy (503) ──────────────────────────────────────────────


def test_model_busy_503_not_retried():
    """503 'model is currently experiencing high demand' should raise ModelBusyError
    immediately without retrying."""
    crew = _make_crew(
        side_effect=RuntimeError(
            "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
            "'This model is currently experiencing high demand. "
            "Spikes in demand are usually temporary. "
            "Please try again later.', 'status': 'UNAVAILABLE'}}"
        ),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(ModelBusyError, match="high demand"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_model_busy_service_unavailable_not_retried():
    """'service unavailable' variant should also raise ModelBusyError."""
    crew = _make_crew(
        side_effect=RuntimeError("The service unavailable, please retry"),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(ModelBusyError):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_try_again_later_is_rate_limit_not_model_busy():
    """'try again later' should be treated as a rate-limit (retried with backoff)
    rather than a model-busy error (paused immediately)."""
    ok = MagicMock(raw="recovered")
    crew = _make_crew(
        side_effect=[RuntimeError("Please try again later"), ok],
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=5.0,
        )
    assert result.raw == "recovered"
    assert crew.kickoff.call_count == 2
    # First rate-limit retry should wait DEFAULT_RATE_LIMIT_BASE_DELAY
    mock_sleep.assert_called_once_with(DEFAULT_RATE_LIMIT_BASE_DELAY)


# ── Rate-limit retries (429 / RESOURCE_EXHAUSTED) ────────────


def test_rate_limit_resource_exhausted_retried():
    """429 RESOURCE_EXHAUSTED should be retried with extended backoff."""
    ok = MagicMock(raw="done")
    crew = _make_crew(
        side_effect=[
            RuntimeError("429 RESOURCE_EXHAUSTED: out of quota"),
            ok,
        ],
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=5.0,
        )
    assert result.raw == "done"
    assert crew.kickoff.call_count == 2
    # First rate-limit attempt: 30s base delay
    mock_sleep.assert_called_once_with(DEFAULT_RATE_LIMIT_BASE_DELAY)


def test_rate_limit_exponential_backoff():
    """Consecutive rate-limit errors should use exponential backoff
    (30s, 60s, 120s …) before eventually raising ModelBusyError."""
    errors = [
        RuntimeError("resource_exhausted") for _ in range(DEFAULT_RATE_LIMIT_RETRIES)
    ]
    crew = _make_crew(side_effect=errors + [MagicMock(raw="ok")])

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=5.0,
        )
    assert result.raw == "ok"
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    expected = [DEFAULT_RATE_LIMIT_BASE_DELAY * (2 ** i) for i in range(DEFAULT_RATE_LIMIT_RETRIES)]
    assert delays == expected


def test_rate_limit_exhausted_raises_model_busy():
    """After exhausting rate-limit retries, should raise ModelBusyError."""
    errors = [
        RuntimeError("resource exhausted") for _ in range(DEFAULT_RATE_LIMIT_RETRIES + 1)
    ]
    crew = _make_crew(side_effect=errors)

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        with pytest.raises(ModelBusyError, match="resource exhausted"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    # Should have attempted DEFAULT_RATE_LIMIT_RETRIES + 1 (initial) calls
    # But rate-limit retries don't count against normal retries,
    # so it's the rate-limit path that exhausts.
    assert crew.kickoff.call_count == DEFAULT_RATE_LIMIT_RETRIES + 1


def test_rate_limit_does_not_consume_normal_retries():
    """Rate-limit retries should not count against normal retry budget."""
    ok = MagicMock(raw="ok")
    crew = _make_crew(
        side_effect=[
            RuntimeError("rate limit exceeded"),  # rate-limit retry 1
            RuntimeError("rate limit exceeded"),  # rate-limit retry 2
            RuntimeError("generic LLM error"),    # normal retry 1
            ok,                                     # success
        ],
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=0,
        )
    assert result.raw == "ok"
    assert crew.kickoff.call_count == 4


def test_rate_limit_too_many_requests():
    """'too many requests' should trigger rate-limit retry path."""
    ok = MagicMock(raw="ok")
    crew = _make_crew(
        side_effect=[RuntimeError("429: too many requests"), ok],
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=5.0,
        )
    assert result.raw == "ok"
    mock_sleep.assert_called_once_with(DEFAULT_RATE_LIMIT_BASE_DELAY)


# ── Defaults ──────────────────────────────────────────────────


def test_defaults():
    """Module-level defaults should be sensible."""
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_RETRY_BASE_DELAY == 5


def test_rate_limit_defaults():
    """Rate-limit defaults should be sensible."""
    assert DEFAULT_RATE_LIMIT_RETRIES == 5
    assert DEFAULT_RATE_LIMIT_BASE_DELAY == 30


# ── Server error (500) retries ────────────────────────────────


@pytest.mark.parametrize("error_msg", [
    "500 Internal Server Error",
    "502 bad gateway",
    "504 gateway timeout",
])
def test_server_error_retried(error_msg):
    """Server errors (500/502/504) should be retried with normal backoff."""
    ok = MagicMock(raw="done")
    crew = _make_crew(side_effect=[RuntimeError(error_msg), ok])
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=1.0,
        )
    assert result.raw == "done"
    assert crew.kickoff.call_count == 2


def test_server_error_exhausted_raises_llm_error():
    """After exhausting retries on server errors, should raise LLMError."""
    errors = [
        RuntimeError("an internal error has occurred")
        for _ in range(4)  # 1 initial + 3 retries
    ]
    crew = _make_crew(side_effect=errors)

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        with pytest.raises(LLMError, match="an internal error has occurred"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=1.0,
            )
    assert crew.kickoff.call_count == 4


def test_server_error_uses_normal_retry_budget():
    """Server error retries should share the normal retry budget."""
    ok = MagicMock(raw="ok")
    crew = _make_crew(
        side_effect=[
            RuntimeError("internal server error"),  # normal retry 1
            RuntimeError("generic network error"),   # normal retry 2
            ok,                                       # success
        ],
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        result = crew_kickoff_with_retry(
            crew, step_label="test", max_retries=3, base_delay=1.0,
        )
    assert result.raw == "ok"
    assert crew.kickoff.call_count == 3


# ── Shutdown errors ───────────────────────────────────────────


def test_shutdown_futures_not_retried():
    """'cannot schedule new futures after shutdown' should raise ShutdownError
    immediately without retrying."""
    crew = _make_crew(
        side_effect=RuntimeError(
            "cannot schedule new futures after shutdown"
        ),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(ShutdownError, match="cannot schedule new futures"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_shutdown_interpreter_not_retried():
    """'interpreter shutdown' should raise ShutdownError immediately."""
    crew = _make_crew(
        side_effect=RuntimeError(
            "cannot schedule new futures after interpreter shutdown"
        ),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(ShutdownError, match="interpreter shutdown"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_shutdown_error_chains_original():
    """ShutdownError should chain the original exception."""
    original = RuntimeError("cannot schedule new futures after shutdown")
    crew = _make_crew(side_effect=original)
    with pytest.raises(ShutdownError) as exc_info:
        crew_kickoff_with_retry(crew, step_label="test", max_retries=3)
    assert exc_info.value.__cause__ is original
