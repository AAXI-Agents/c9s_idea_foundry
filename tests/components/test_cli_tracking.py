"""Tests for agent interaction tracking in CLI components."""

from unittest.mock import MagicMock, patch, call

import pytest

from crewai_productfeature_planner.components.cli import (
    _choose_refinement_mode,
    _get_idea,
    _manual_idea_refinement,
    _approve_refined_idea,
    _approve_requirements,
    _track_cli,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


_LOG_PATH = "crewai_productfeature_planner.mongodb.agent_interactions.repository.log_interaction"


# ── _track_cli helper ─────────────────────────────────────────


class TestTrackCli:
    """Tests for the _track_cli helper itself."""

    def test_calls_log_interaction(self):
        with patch(_LOG_PATH) as mock_log:
            _track_cli(
                user_message="test msg",
                intent="test_intent",
                agent_response="test response",
                idea="my idea",
                run_id="run123",
                metadata={"key": "val"},
            )

        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["source"] == "cli"
        assert kw["user_message"] == "test msg"
        assert kw["intent"] == "test_intent"
        assert kw["agent_response"] == "test response"
        assert kw["idea"] == "my idea"
        assert kw["run_id"] == "run123"
        assert kw["user_id"] == "cli_user"
        assert kw["metadata"] == {"key": "val"}

    def test_does_not_raise_on_failure(self):
        with patch(_LOG_PATH, side_effect=RuntimeError("DB down")):
            # Should NOT raise
            _track_cli(
                user_message="test",
                intent="test",
                agent_response="test",
            )


# ── _get_idea ─────────────────────────────────────────────────


class TestGetIdeaTracking:

    def test_tracks_idea_from_argv(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["cmd", "my feature idea"])
        with patch(_LOG_PATH) as mock_log:
            result = _get_idea()
        assert result == "my feature idea"
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "create_prd"
        assert kw["idea"] == "my feature idea"
        assert kw["source"] == "cli"

    def test_tracks_idea_from_input(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["cmd"])
        monkeypatch.setattr("builtins.input", lambda _: "input idea")
        with patch(_LOG_PATH) as mock_log:
            result = _get_idea()
        assert result == "input idea"
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["idea"] == "input idea"


# ── _choose_refinement_mode ──────────────────────────────────


class TestRefinementModeTracking:

    def test_tracks_agent_mode(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "a")
        with patch(_LOG_PATH) as mock_log:
            result = _choose_refinement_mode()
        assert result == "agent"
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "refinement_mode"
        assert "Agent" in kw["agent_response"]

    def test_tracks_manual_mode(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "m")
        with patch(_LOG_PATH) as mock_log:
            result = _choose_refinement_mode()
        assert result == "manual"
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "refinement_mode"
        assert "Manual" in kw["agent_response"]


# ── _manual_idea_refinement ───────────────────────────────────


class TestManualRefinementTracking:

    def test_tracks_approve(self, monkeypatch):
        """Should track when user approves in first iteration."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        with patch(_LOG_PATH) as mock_log:
            result, history = _manual_idea_refinement("original idea", "run1")
        assert result == "original idea"
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "manual_refinement_approve"
        assert kw["run_id"] == "run1"
        assert kw["metadata"]["iteration"] == 1

    def test_tracks_edit_then_approve(self, monkeypatch):
        """Should track both the edit and approve steps."""
        inputs = iter(["e", "revised idea", "", "", "y"])
        monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
        with patch(_LOG_PATH) as mock_log:
            result, history = _manual_idea_refinement("original", "run1")
        assert result == "revised idea"
        assert mock_log.call_count == 2
        # First call: edit
        kw1 = mock_log.call_args_list[0][1]
        assert kw1["intent"] == "manual_refinement_edit"
        assert kw1["user_message"] == "revised idea"
        # Second call: approve
        kw2 = mock_log.call_args_list[1][1]
        assert kw2["intent"] == "manual_refinement_approve"


# ── _approve_refined_idea ─────────────────────────────────────


class TestIdeaApprovalTracking:

    def test_tracks_approve(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        with patch(_LOG_PATH) as mock_log:
            result = _approve_refined_idea("refined", "original", "run1")
        assert result is False  # continue
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "idea_approval"
        assert kw["agent_response"] == "Idea approved — proceeding to section drafting"
        assert kw["run_id"] == "run1"

    def test_tracks_cancel(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "c")
        with patch(_LOG_PATH) as mock_log:
            with pytest.raises(SystemExit):
                _approve_refined_idea("refined", "original", "run1")
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "idea_approval"
        assert "cancelled" in kw["agent_response"].lower()


# ── _approve_requirements ─────────────────────────────────────


class TestRequirementsApprovalTracking:

    def test_tracks_approve(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        with patch(_LOG_PATH) as mock_log:
            result = _approve_requirements("requirements text", "idea", "run1")
        assert result is False
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "requirements_approval"
        assert "approved" in kw["agent_response"].lower()

    def test_tracks_cancel(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "c")
        with patch(_LOG_PATH) as mock_log:
            with pytest.raises(SystemExit):
                _approve_requirements("requirements text", "idea", "run1")
        mock_log.assert_called_once()
        kw = mock_log.call_args[1]
        assert kw["intent"] == "requirements_approval"
        assert "cancelled" in kw["agent_response"].lower()
