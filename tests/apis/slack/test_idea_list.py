"""Tests for idea list Block Kit builder and interaction handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.blocks import idea_list_blocks


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_PROJECT_ID = "proj-test-123"
_PROJECT_NAME = "Test Project"
_USER = "U_TEST"

_IDEAS = [
    {
        "run_id": "run-aaa",
        "idea": "Build a mobile fitness tracker",
        "status": "paused",
        "iteration": 3,
        "sections_done": 5,
        "total_sections": 10,
    },
    {
        "run_id": "run-bbb",
        "idea": "Add social login feature",
        "status": "inprogress",
        "iteration": 1,
        "sections_done": 2,
        "total_sections": 10,
    },
    {
        "run_id": "run-ccc",
        "idea": "Dark mode implementation",
        "status": "completed",
        "iteration": 5,
        "sections_done": 10,
        "total_sections": 10,
    },
    {
        "run_id": "run-ddd",
        "idea": "Error reporting dashboard",
        "status": "failed",
        "iteration": 2,
        "sections_done": 3,
        "total_sections": 10,
    },
]


# ---------------------------------------------------------------------------
# idea_list_blocks builder
# ---------------------------------------------------------------------------


class TestIdeaListBlocks:
    """Verify the Block Kit builder returns correct blocks with actions."""

    def test_header_present(self):
        blocks = idea_list_blocks(_IDEAS, _USER, _PROJECT_NAME, _PROJECT_ID)
        assert blocks[0]["type"] == "header"
        assert _PROJECT_NAME in blocks[0]["text"]["text"]

    def test_each_idea_has_section_block(self):
        blocks = idea_list_blocks(_IDEAS, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        assert len(section_blocks) == len(_IDEAS)

    def test_paused_idea_has_resume_and_restart(self):
        """Paused ideas should offer both Resume and Restart buttons."""
        blocks = idea_list_blocks(_IDEAS[:1], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "idea_resume_1" in action_ids
        assert "idea_restart_1" in action_ids

    def test_inprogress_idea_has_resume_and_restart(self):
        """In-progress ideas should have both Resume and Restart."""
        ideas = [_IDEAS[1]]  # inprogress
        blocks = idea_list_blocks(ideas, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "idea_resume_1" in action_ids
        assert "idea_restart_1" in action_ids

    def test_completed_idea_has_both_buttons(self):
        """Completed ideas should also have Resume and Rescan buttons."""
        ideas = [_IDEAS[2]]  # completed
        blocks = idea_list_blocks(ideas, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "idea_resume_1" in action_ids
        assert "idea_restart_1" in action_ids

    def test_failed_idea_has_resume_and_restart(self):
        """Failed ideas should have Resume and Restart buttons."""
        ideas = [_IDEAS[3]]  # failed
        blocks = idea_list_blocks(ideas, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "idea_resume_1" in action_ids
        assert "idea_restart_1" in action_ids

    def test_button_values_contain_project_id_and_number(self):
        """Button values should encode project_id|idea_number."""
        blocks = idea_list_blocks(_IDEAS[:2], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 2
        # First idea
        first_vals = [e["value"] for e in action_blocks[0]["elements"]]
        assert all(v == f"{_PROJECT_ID}|1" for v in first_vals)
        # Second idea
        second_vals = [e["value"] for e in action_blocks[1]["elements"]]
        assert all(v == f"{_PROJECT_ID}|2" for v in second_vals)

    def test_long_idea_text_truncated(self):
        """Ideas longer than 120 chars should be truncated."""
        long_idea = [{
            "run_id": "run-long",
            "idea": "x" * 200,
            "status": "paused",
            "iteration": 1,
            "sections_done": 0,
            "total_sections": 10,
        }]
        blocks = idea_list_blocks(long_idea, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert "…" in text

    def test_footer_context_present(self):
        """Should end with a context block hint."""
        blocks = idea_list_blocks(_IDEAS[:1], _USER, _PROJECT_NAME, _PROJECT_ID)
        assert blocks[-1]["type"] == "context"
        ctx_text = blocks[-1]["elements"][0]["text"]
        assert "new idea" in ctx_text.lower()

    def test_rescan_button_label(self):
        """Rescan buttons should use 'Rescan' label."""
        blocks = idea_list_blocks(_IDEAS[:1], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        restart_btn = [
            e for e in action_blocks[0]["elements"]
            if e["action_id"].startswith("idea_restart_")
        ]
        assert len(restart_btn) == 1
        assert "Rescan" in restart_btn[0]["text"]["text"]
        assert restart_btn[0].get("style") == "danger"

    def test_empty_idea_text_shows_untitled(self):
        """Ideas with empty or missing idea text show 'Untitled'."""
        empty_ideas = [
            {
                "run_id": "run-empty",
                "idea": "",
                "status": "failed",
                "iteration": 2,
                "sections_done": 3,
                "total_sections": 10,
            },
            {
                "run_id": "run-none",
                "status": "failed",
                "iteration": 1,
                "sections_done": 0,
                "total_sections": 10,
            },
        ]
        blocks = idea_list_blocks(empty_ideas, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        for sb in section_blocks:
            assert "Untitled" in sb["text"]["text"]

    def test_multiple_ideas_get_numbered_actions(self):
        """Each idea should get uniquely numbered action IDs."""
        blocks = idea_list_blocks(_IDEAS, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        # All 4 ideas now get buttons
        assert len(action_blocks) == 4
        all_action_ids = []
        for ab in action_blocks:
            all_action_ids.extend(e["action_id"] for e in ab["elements"])
        # Each action_id should be unique
        assert len(all_action_ids) == len(set(all_action_ids))


# ---------------------------------------------------------------------------
# handle_list_ideas — session handler
# ---------------------------------------------------------------------------


class TestHandleListIdeas:
    """Verify handle_list_ideas posts Block Kit instead of plain text."""

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_ideas_by_project",
        return_value=_IDEAS,
    )
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_posts_blocks_to_slack(self, mock_client, mock_find):
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_list_ideas,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack
        session = {"project_id": _PROJECT_ID, "project_name": _PROJECT_NAME}

        handle_list_ideas("C1", "T1", _USER, session)

        mock_slack.chat_postMessage.assert_called_once()
        call_kw = mock_slack.chat_postMessage.call_args[1]
        assert "blocks" in call_kw
        assert call_kw["channel"] == "C1"
        assert call_kw["thread_ts"] == "T1"
        # Blocks should contain a header
        blocks = call_kw["blocks"]
        assert blocks[0]["type"] == "header"

    @patch(
        "crewai_productfeature_planner.mongodb.working_ideas.repository.find_ideas_by_project",
        return_value=[],
    )
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_empty_ideas_posts_plain_text(self, mock_client, mock_find):
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            handle_list_ideas,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack
        session = {"project_id": _PROJECT_ID, "project_name": _PROJECT_NAME}

        handle_list_ideas("C1", "T1", _USER, session)

        # Empty ideas should use plain text reply, not blocks
        mock_slack.chat_postMessage.assert_called_once()
        call_kw = mock_slack.chat_postMessage.call_args[1]
        assert "No ideas found" in call_kw["text"]


# ---------------------------------------------------------------------------
# _handle_idea_list_action — interaction router
# ---------------------------------------------------------------------------


class TestHandleIdeaListAction:
    """Verify the interaction router correctly dispatches idea actions."""

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd",
    )
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_resume_calls_handle_resume_prd(self, mock_client, mock_resume):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _handle_idea_list_action,
        )

        mock_slack = MagicMock()
        mock_client.return_value = mock_slack

        _handle_idea_list_action(
            "idea_resume_2", f"{_PROJECT_ID}|2", _USER, "C1", "T1",
        )

        mock_resume.assert_called_once()
        call_kw = mock_resume.call_args[1]
        assert call_kw["project_id"] == _PROJECT_ID
        assert call_kw["idea_number"] == 2
        assert call_kw["channel"] == "C1"
        assert call_kw["user"] == _USER

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.handle_restart_prd",
    )
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_restart_calls_handle_restart_prd(self, mock_client, mock_restart):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _handle_idea_list_action,
        )

        _handle_idea_list_action(
            "idea_restart_3", f"{_PROJECT_ID}|3", _USER, "C1", "T1",
        )

        mock_restart.assert_called_once()
        call_kw = mock_restart.call_args[1]
        assert call_kw["project_id"] == _PROJECT_ID
        assert call_kw["idea_number"] == 3
        assert call_kw["channel"] == "C1"

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd",
    )
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_invalid_value_format_logs_warning(self, mock_client, mock_resume):
        """Invalid value format should not call any handler."""
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _handle_idea_list_action,
        )

        _handle_idea_list_action(
            "idea_resume_1", "invalid-no-pipe", _USER, "C1", "T1",
        )

        mock_resume.assert_not_called()

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.handle_resume_prd",
    )
    @patch("crewai_productfeature_planner.tools.slack_tools._get_slack_client")
    def test_non_numeric_idea_number_logs_warning(self, mock_client, mock_resume):
        """Non-numeric idea number should not call any handler."""
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _handle_idea_list_action,
        )

        _handle_idea_list_action(
            "idea_resume_1", f"{_PROJECT_ID}|abc", _USER, "C1", "T1",
        )

        mock_resume.assert_not_called()


# ---------------------------------------------------------------------------
# _ack_action — dynamic labels for idea actions
# ---------------------------------------------------------------------------


class TestAckActionIdeaLabels:
    """Verify _ack_action produces readable labels for idea actions."""

    def test_resume_ack_label(self):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _ack_action,
        )

        result = _ack_action("idea_resume_3", "testuser")
        assert "Resuming idea #3" in result
        assert "testuser" in result

    def test_restart_ack_label(self):
        from crewai_productfeature_planner.apis.slack.interactions_router import (
            _ack_action,
        )

        result = _ack_action("idea_restart_1", "testuser")
        assert "Restarting idea #1" in result
        assert "testuser" in result


# ---------------------------------------------------------------------------
# _backfill_missing_idea_titles
# ---------------------------------------------------------------------------


class TestBackfillMissingIdeaTitles:
    """Verify crew-job fallback for empty idea titles."""

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.find_job")
    def test_fills_from_crew_job(self, mock_find_job):
        """Empty idea text should be filled from the crew-jobs collection."""
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            _backfill_missing_idea_titles,
        )

        mock_find_job.return_value = {"idea": "Backfilled idea title"}
        ideas = [{"run_id": "run-abc", "idea": "", "status": "failed"}]
        _backfill_missing_idea_titles(ideas)
        assert ideas[0]["idea"] == "Backfilled idea title"
        mock_find_job.assert_called_once_with("run-abc")

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.find_job")
    def test_skips_ideas_with_text(self, mock_find_job):
        """Ideas that already have text should not trigger a lookup."""
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            _backfill_missing_idea_titles,
        )

        ideas = [{"run_id": "run-abc", "idea": "Has text", "status": "paused"}]
        _backfill_missing_idea_titles(ideas)
        mock_find_job.assert_not_called()

    @patch("crewai_productfeature_planner.mongodb.crew_jobs.find_job")
    def test_handles_missing_job_gracefully(self, mock_find_job):
        """When crew-job is not found, idea stays empty."""
        from crewai_productfeature_planner.apis.slack._session_handlers import (
            _backfill_missing_idea_titles,
        )

        mock_find_job.return_value = None
        ideas = [{"run_id": "run-abc", "idea": "", "status": "failed"}]
        _backfill_missing_idea_titles(ideas)
        assert ideas[0]["idea"] == ""
