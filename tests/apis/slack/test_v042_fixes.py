"""Tests for v0.42.0 fixes.

1. Admin-only config button in product list
2. Command-phrase idea guard (prevents auto-start for "add new idea")
3. Archive moves knowledge file
4. Summarize ideas intent routing
5. User suggestions collection
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# 1. Product list config button — admin guard
# ===========================================================================

class TestProductListAdminConfig:
    """Config button should only appear for admin users."""

    def test_config_hidden_for_non_admin(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            product_list_blocks,
        )
        products = [{"idea": "Test idea", "run_id": "r1"}]
        blocks = product_list_blocks(
            products, "U1", "Test Project", "proj1", is_admin=False,
        )
        config_blocks = [
            b for b in blocks
            if b["type"] == "actions"
            and b.get("block_id", "").startswith("product_project_actions_")
        ]
        assert len(config_blocks) == 0

    def test_config_visible_for_admin(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            product_list_blocks,
        )
        products = [{"idea": "Test idea", "run_id": "r1"}]
        blocks = product_list_blocks(
            products, "U1", "Test Project", "proj1", is_admin=True,
        )
        config_blocks = [
            b for b in blocks
            if b["type"] == "actions"
            and b.get("block_id", "").startswith("product_project_actions_")
        ]
        assert len(config_blocks) == 1
        assert config_blocks[0]["elements"][0]["action_id"] == "product_config"

    def test_config_hidden_by_default(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            product_list_blocks,
        )
        products = [{"idea": "Test idea", "run_id": "r1"}]
        blocks = product_list_blocks(
            products, "U1", "Test Project", "proj1",
        )
        config_blocks = [
            b for b in blocks
            if b["type"] == "actions"
            and b.get("block_id", "").startswith("product_project_actions_")
        ]
        assert len(config_blocks) == 0

    def test_product_config_handler_denies_non_admin(self):
        """_handle_product_config should deny non-admin users."""
        with patch(
            "crewai_productfeature_planner.apis.slack.session_manager"
            ".can_manage_memory",
            return_value=False,
        ), patch(
            "crewai_productfeature_planner.apis.slack._session_reply.reply"
        ) as mock_reply:
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_product_config,
            )
            _handle_product_config("proj1", "U1", "C1", "T1")
            mock_reply.assert_called_once()
            assert ":lock:" in mock_reply.call_args[0][2]


# ===========================================================================
# 2. Command-phrase idea guard
# ===========================================================================

class TestCommandPhraseIdeaGuard:
    """_is_command_phrase_idea should block bogus 'ideas'."""

    def test_exact_command_phrase(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_command_phrase_idea,
        )
        assert _is_command_phrase_idea("new idea") is True
        assert _is_command_phrase_idea("create a prd") is True
        assert _is_command_phrase_idea("iterate an idea") is True
        assert _is_command_phrase_idea("create idea") is True
        assert _is_command_phrase_idea("brainstorm an idea") is True

    def test_command_substring_short_text(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_command_phrase_idea,
        )
        assert _is_command_phrase_idea("add new idea") is True
        assert _is_command_phrase_idea("pls create prd") is True

    def test_real_idea_allowed(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_command_phrase_idea,
        )
        assert _is_command_phrase_idea(
            "a mobile app for tracking daily water intake"
        ) is False
        assert _is_command_phrase_idea(
            "integrate AI chatbot into customer support portal"
        ) is False

    def test_case_insensitive(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_command_phrase_idea,
        )
        assert _is_command_phrase_idea("New Idea") is True
        assert _is_command_phrase_idea("CREATE A PRD") is True

    def test_whitespace_handling(self):
        from crewai_productfeature_planner.apis.slack._message_handler import (
            _is_command_phrase_idea,
        )
        assert _is_command_phrase_idea("  new idea  ") is True


# ===========================================================================
# 3. Archive moves knowledge file
# ===========================================================================

class TestArchiveIdeaKnowledge:
    """archive_idea_knowledge should move the idea .md file."""

    @patch(
        "crewai_productfeature_planner.scripts.project_knowledge.generate_project_page",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.project_memory.repository.get_db",
    )
    @patch(
        "crewai_productfeature_planner.mongodb.project_config.repository.get_db",
    )
    @patch("crewai_productfeature_planner.mongodb.client.get_db")
    def test_moves_file_to_archive_folder(
        self, mock_client_db, mock_config_db, mock_mem_db, mock_gen_page,
        tmp_path, monkeypatch,
    ):
        from crewai_productfeature_planner.scripts.project_knowledge import (
            archive_idea_knowledge,
            _safe_dirname,
            _safe_filename,
            _idea_title_from_doc,
        )
        import crewai_productfeature_planner.scripts.project_knowledge as pk

        # Point _PROJECTS_ROOT to tmp_path
        monkeypatch.setattr(pk, "_PROJECTS_ROOT", tmp_path)

        doc = {
            "run_id": "r1",
            "idea": "Demo Idea For Testing",
            "project_id": "p1",
            "status": "completed",
        }

        # Mock the MongoDB calls
        mock_wi_coll = MagicMock()
        mock_wi_coll.find_one.return_value = doc
        mock_client_db.return_value.__getitem__.return_value = mock_wi_coll

        mock_config_coll = MagicMock()
        mock_config_coll.find_one.return_value = {"name": "Demo", "project_id": "p1"}
        mock_config_db.return_value.__getitem__.return_value = mock_config_coll

        mock_mem_coll = MagicMock()
        mock_mem_coll.find_one.return_value = None
        mock_mem_db.return_value.__getitem__.return_value = mock_mem_coll

        # Create the source file
        dirname = _safe_dirname("Demo")
        filename = _safe_filename(_idea_title_from_doc(doc))
        ideas_dir = tmp_path / dirname / "ideas"
        ideas_dir.mkdir(parents=True)
        source = ideas_dir / f"{filename}.md"
        source.write_text("# Demo Idea\nContent here")

        result = archive_idea_knowledge("r1")
        assert result is not None
        assert "archives" in str(result)
        assert not source.exists()
        assert result.exists()
        assert result.read_text() == "# Demo Idea\nContent here"

    @patch(
        "crewai_productfeature_planner.mongodb.project_config.repository.get_db",
    )
    @patch("crewai_productfeature_planner.mongodb.client.get_db")
    def test_returns_none_when_no_file(self, mock_client_db, mock_config_db, tmp_path, monkeypatch):
        import crewai_productfeature_planner.scripts.project_knowledge as pk
        monkeypatch.setattr(pk, "_PROJECTS_ROOT", tmp_path)

        doc = {"run_id": "r1", "idea": "No File", "project_id": "p1"}
        mock_wi_coll = MagicMock()
        mock_wi_coll.find_one.return_value = doc
        mock_client_db.return_value.__getitem__.return_value = mock_wi_coll

        mock_config_coll = MagicMock()
        mock_config_coll.find_one.return_value = {"name": "Demo", "project_id": "p1"}
        mock_config_db.return_value.__getitem__.return_value = mock_config_coll

        from crewai_productfeature_planner.scripts.project_knowledge import (
            archive_idea_knowledge,
        )
        result = archive_idea_knowledge("r1")
        assert result is None


# ===========================================================================
# 4. Summarize ideas intent routing
# ===========================================================================

class TestSummarizeIdeasPhrases:
    """_SUMMARIZE_IDEAS_PHRASES should match summary-of-ideas variant texts."""

    def test_phrase_fallback_matches_summarize(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("summary of ideas")
        assert result["intent"] == "summarize_ideas"

    def test_phrase_fallback_matches_summarize_all(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("summarize all ideas")
        assert result["intent"] == "summarize_ideas"

    def test_list_ideas_still_matches_when_no_summary(self):
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("list ideas")
        assert result["intent"] == "list_ideas"

    def test_summarize_takes_priority_over_list(self):
        """'summary of ideas' must not match 'list_ideas' intent."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("give me a summary of ideas")
        assert result["intent"] == "summarize_ideas"


# ===========================================================================
# 5. Summarize ideas button in help
# ===========================================================================

class TestSummarizeIdeasButton:
    """BTN_SUMMARIZE_IDEAS should appear in help_blocks."""

    def test_summarize_button_exists(self):
        from crewai_productfeature_planner.apis.slack.blocks import (
            BTN_SUMMARIZE_IDEAS,
        )
        assert BTN_SUMMARIZE_IDEAS["action_id"] == "cmd_summarize_ideas"

    def test_help_blocks_includes_summarize(self):
        from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
            help_blocks,
        )
        blocks = help_blocks("U1", has_project=True, is_admin=True)
        all_action_ids = []
        for b in blocks:
            if b["type"] == "actions":
                for el in b["elements"]:
                    all_action_ids.append(el["action_id"])
        assert "cmd_summarize_ideas" in all_action_ids

    def test_cmd_summarize_in_cmd_actions(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._command_handler import (
            CMD_ACTIONS,
        )
        assert "cmd_summarize_ideas" in CMD_ACTIONS


# ===========================================================================
# 6. User suggestions collection
# ===========================================================================

class TestUserSuggestionsCollection:
    """userSuggestions collection constants and setup."""

    def test_collection_name(self):
        from crewai_productfeature_planner.mongodb.user_suggestions import (
            USER_SUGGESTIONS_COLLECTION,
        )
        assert USER_SUGGESTIONS_COLLECTION == "userSuggestions"

    def test_registered_in_all_collections(self):
        from crewai_productfeature_planner.scripts.setup_mongodb import (
            ALL_COLLECTIONS,
        )
        assert "userSuggestions" in ALL_COLLECTIONS

    @patch("crewai_productfeature_planner.mongodb.user_suggestions.repository.get_db")
    def test_log_suggestion_returns_id(self, mock_db):
        mock_db.return_value.__getitem__.return_value.insert_one.return_value = (
            MagicMock()
        )
        from crewai_productfeature_planner.mongodb.user_suggestions import (
            log_suggestion,
        )
        result = log_suggestion(
            user_message="what do you think?",
            agent_interpretation="[CLARIFICATION] ...",
            user_id="U1",
            project_id="p1",
        )
        assert result is not None
        assert len(result) == 32  # UUID hex

    @patch("crewai_productfeature_planner.mongodb.user_suggestions.repository.get_db")
    def test_find_suggestions_by_project(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = [
            {"suggestion_id": "abc", "user_message": "test"},
        ]
        mock_db.return_value.__getitem__.return_value.find.return_value = mock_cursor
        from crewai_productfeature_planner.mongodb.user_suggestions import (
            find_suggestions_by_project,
        )
        results = find_suggestions_by_project("p1")
        assert len(results) == 1
