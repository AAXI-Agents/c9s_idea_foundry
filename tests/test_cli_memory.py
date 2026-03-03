"""Tests for CLI project memory configuration functions."""

from unittest.mock import MagicMock, call, patch

import pytest


_MAIN_MODULE = "crewai_productfeature_planner._cli_project"
_PM_MODULE = "crewai_productfeature_planner.mongodb.project_memory"


class TestOfferMemoryConfiguration:
    """Tests for _offer_memory_configuration."""

    def test_skip(self, monkeypatch):
        """User chooses 'n' → skips memory config."""
        from crewai_productfeature_planner.main import _offer_memory_configuration

        inputs = iter(["n"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with patch(f"{_MAIN_MODULE}._configure_project_memory_cli") as mock_config:
            _offer_memory_configuration("p1", "TestProj")
            mock_config.assert_not_called()

    def test_configure(self, monkeypatch):
        """User chooses 'y' → _configure_project_memory_cli is called."""
        from crewai_productfeature_planner.main import _offer_memory_configuration

        inputs = iter(["y"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with patch(f"{_MAIN_MODULE}._configure_project_memory_cli") as mock_config:
            _offer_memory_configuration("p1", "TestProj")
            mock_config.assert_called_once_with("p1", "TestProj")


class TestConfigureProjectMemoryCli:
    """Tests for _configure_project_memory_cli."""

    @patch(f"{_PM_MODULE}.upsert_project_memory")
    @patch(f"{_PM_MODULE}.get_project_memory")
    @patch(f"{_PM_MODULE}.add_memory_entry")
    def test_add_entries_to_empty_project(
        self, mock_add, mock_get, mock_upsert, monkeypatch,
    ):
        """Adds entries to all three categories when project has no memory."""
        from crewai_productfeature_planner.main import _configure_project_memory_cli

        mock_get.return_value = None  # no existing memory

        # Simulate user input:
        # idea_iteration: 2 entries then empty
        # knowledge: 1 entry then empty
        # tools: empty immediately
        inputs = iter([
            "Be concise",
            "Focus on MVP",
            "",
            "https://docs.example.com",
            "",
            "",
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        mock_add.return_value = True

        _configure_project_memory_cli("p1", "TestProj")

        mock_upsert.assert_called_once_with("p1")
        assert mock_add.call_count == 3  # 2 idea + 1 knowledge

    @patch(f"{_PM_MODULE}.upsert_project_memory")
    @patch(f"{_PM_MODULE}.get_project_memory")
    @patch(f"{_PM_MODULE}.add_memory_entry")
    def test_skip_when_existing_memory(
        self, mock_add, mock_get, mock_upsert, monkeypatch,
    ):
        """User skips when memory already exists and chooses 's'."""
        from crewai_productfeature_planner.main import _configure_project_memory_cli

        mock_get.return_value = {
            "project_id": "p1",
            "idea_iteration": [{"content": "existing"}],
            "knowledge": [],
            "tools": [],
        }

        inputs = iter(["s"])  # skip
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        _configure_project_memory_cli("p1", "TestProj")

        mock_add.assert_not_called()

    @patch(f"{_PM_MODULE}.upsert_project_memory")
    @patch(f"{_PM_MODULE}.get_project_memory")
    @patch(f"{_PM_MODULE}.add_memory_entry")
    def test_knowledge_link_detection(
        self, mock_add, mock_get, mock_upsert, monkeypatch,
    ):
        """Knowledge entries starting with http are tagged as 'link'."""
        from crewai_productfeature_planner.mongodb.project_memory import MemoryCategory
        from crewai_productfeature_planner.main import _configure_project_memory_cli

        mock_get.return_value = None

        inputs = iter([
            "",          # skip idea
            "https://docs.example.com",
            "design guide notes",
            "",          # end knowledge
            "",          # skip tools
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        mock_add.return_value = True

        _configure_project_memory_cli("p1", "TestProj")

        # Find the knowledge calls
        knowledge_calls = [
            c for c in mock_add.call_args_list
            if c[0][1] == MemoryCategory.KNOWLEDGE
        ]
        assert len(knowledge_calls) == 2

        # First call: link
        assert knowledge_calls[0].kwargs.get("kind") == "link"
        # Second call: note
        assert knowledge_calls[1].kwargs.get("kind") == "note"

    @patch(f"{_PM_MODULE}.upsert_project_memory")
    @patch(f"{_PM_MODULE}.get_project_memory")
    @patch(f"{_PM_MODULE}.add_memory_entry")
    def test_all_empty_skips_gracefully(
        self, mock_add, mock_get, mock_upsert, monkeypatch,
    ):
        """Pressing Enter immediately for all categories adds nothing."""
        from crewai_productfeature_planner.main import _configure_project_memory_cli

        mock_get.return_value = None

        inputs = iter(["", "", ""])  # empty for all 3 categories
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        _configure_project_memory_cli("p1", "TestProj")

        mock_add.assert_not_called()
