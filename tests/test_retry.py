"""Tests for the crew_kickoff_with_retry helper."""

import time
from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.scripts.retry import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
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
    """Should raise the last exception after all retries are exhausted."""
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    crew = _make_crew(side_effect=RuntimeError("LLM timeout"))

    with patch("crewai_productfeature_planner.scripts.retry.time.sleep"):
        with pytest.raises(RuntimeError, match="LLM timeout"):
            crew_kickoff_with_retry(crew, step_label="test", base_delay=0)

    # 1 initial + 1 retry = 2 attempts
    assert crew.kickoff.call_count == 2


def test_zero_retries_raises_immediately():
    """With max_retries=0, should fail on first error without retrying."""
    crew = _make_crew(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
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


# ── Defaults ──────────────────────────────────────────────────


def test_defaults():
    """Module-level defaults should be sensible."""
    assert DEFAULT_MAX_RETRIES == 3
    assert DEFAULT_RETRY_BASE_DELAY == 5
