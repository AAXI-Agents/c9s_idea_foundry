"""Tests for the crew_kickoff_with_retry helper."""

import time
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.retry import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    BillingError,
    LLMError,
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
    delays = [call.args[0] for call in mock_sleep.call_args_list]
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


def test_insufficient_quota_not_retried():
    """insufficient_quota errors should raise BillingError immediately without retrying."""
    crew = _make_crew(
        side_effect=RuntimeError(
            "Error code: 429 - {'error': {'type': 'insufficient_quota', "
            "'code': 'insufficient_quota'}}"
        ),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(BillingError, match="insufficient_quota"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_invalid_api_key_not_retried():
    """invalid_api_key errors should raise BillingError immediately without retrying."""
    crew = _make_crew(
        side_effect=RuntimeError("invalid_api_key: bad key"),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(BillingError, match="invalid_api_key"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_billing_hard_limit_not_retried():
    """billing_hard_limit_reached errors should raise BillingError immediately."""
    crew = _make_crew(
        side_effect=RuntimeError("billing_hard_limit_reached"),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(BillingError, match="billing_hard_limit_reached"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_exceeded_quota_not_retried():
    """'exceeded your current quota' should raise BillingError immediately."""
    crew = _make_crew(
        side_effect=RuntimeError("You exceeded your current quota, check your plan and billing details."),
    )
    with patch("crewai_productfeature_planner.scripts.retry.time.sleep") as mock_sleep:
        with pytest.raises(BillingError, match="exceeded your current quota"):
            crew_kickoff_with_retry(
                crew, step_label="test", max_retries=3, base_delay=5.0,
            )
    assert crew.kickoff.call_count == 1
    mock_sleep.assert_not_called()


def test_billing_error_is_runtime_error():
    """BillingError should be a subclass of RuntimeError for backward compat."""
    assert issubclass(BillingError, RuntimeError)


def test_llm_error_is_runtime_error():
    """LLMError should be a subclass of RuntimeError."""
    assert issubclass(LLMError, RuntimeError)


def test_billing_error_is_llm_error():
    """BillingError should be a subclass of LLMError."""
    assert issubclass(BillingError, LLMError)


def test_exhausted_retries_wraps_original():
    """LLMError raised after retry exhaustion should chain the original exception."""
    original = RuntimeError("model overloaded")
    crew = _make_crew(side_effect=original)
    with pytest.raises(LLMError, match="model overloaded") as exc_info:
        crew_kickoff_with_retry(crew, step_label="test", max_retries=0)
    assert exc_info.value.__cause__ is original


# ── Defaults ──────────────────────────────────────────────────


def test_defaults():
    """Module-level defaults should be sensible."""
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_RETRY_BASE_DELAY == 5
