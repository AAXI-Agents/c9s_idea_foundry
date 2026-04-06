"""Tests for Confluence preview service function."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Patch at the source modules — preview_confluence_content imports inside the function body
_IDEAS = "crewai_productfeature_planner.mongodb.working_ideas.find_run_any_status"
_ASSEMBLE = "crewai_productfeature_planner.components.document.assemble_prd_from_doc"
_XHTML = "crewai_productfeature_planner.scripts.confluence_xhtml.md_to_confluence_xhtml"
_VERSIONS = "crewai_productfeature_planner.mongodb.product_requirements.get_version_history"


class TestPreviewConfluenceContent:
    """Test the preview service function directly (no app startup needed)."""

    @patch(_VERSIONS, return_value=[])
    @patch(_XHTML, return_value="<p>Hello</p>")
    @patch(_ASSEMBLE, return_value="# Hello")
    @patch(_IDEAS)
    def test_generates_preview(self, mock_find, mock_assemble, mock_xhtml, mock_versions):
        from crewai_productfeature_planner.apis.publishing.service import (
            preview_confluence_content,
        )
        mock_find.return_value = {
            "run_id": "r1",
            "idea": "Build a fitness app",
            "section": {"problem_statement": [{"content": "v1"}]},
        }
        result = preview_confluence_content("r1")
        assert result["run_id"] == "r1"
        assert result["xhtml"] == "<p>Hello</p>"
        assert result["markdown"] == "# Hello"
        assert "problem_statement" in result["sections_changed"]

    @patch(_IDEAS, return_value=None)
    def test_raises_when_not_found(self, mock_find):
        from crewai_productfeature_planner.apis.publishing.service import (
            preview_confluence_content,
        )
        with pytest.raises(ValueError, match="No PRD found"):
            preview_confluence_content("bad")

    @patch(_VERSIONS)
    @patch(_XHTML, return_value="<p>Hello</p>")
    @patch(_ASSEMBLE, return_value="# Hello")
    @patch(_IDEAS)
    def test_identifies_changed_sections(self, mock_find, mock_assemble, mock_xhtml, mock_versions):
        from crewai_productfeature_planner.apis.publishing.service import (
            preview_confluence_content,
        )
        mock_find.return_value = {
            "run_id": "r1",
            "idea": "App",
            "section": {
                "problem_statement": [{"content": "updated content"}],
                "user_personas": [{"content": "same content"}],
            },
        }
        mock_versions.return_value = [
            {
                "version": 1,
                "sections": {
                    "problem_statement": "old content",
                    "user_personas": "same content",
                },
            },
        ]
        result = preview_confluence_content("r1")
        assert "problem_statement" in result["sections_changed"]
        assert "user_personas" not in result["sections_changed"]

    @patch(_ASSEMBLE, return_value="")
    @patch(_IDEAS, return_value={"run_id": "r1", "idea": "App"})
    def test_raises_when_no_content(self, mock_find, mock_assemble):
        from crewai_productfeature_planner.apis.publishing.service import (
            preview_confluence_content,
        )
        with pytest.raises(ValueError, match="Could not assemble"):
            preview_confluence_content("r1")


class TestConfluencePreviewResponseModel:
    """Test the response model."""

    def test_model_fields(self):
        from crewai_productfeature_planner.apis.publishing.models import (
            ConfluencePreviewResponse,
        )
        resp = ConfluencePreviewResponse(
            run_id="r1",
            title="My PRD",
            markdown="# Hello",
            xhtml="<h1>Hello</h1>",
            sections_changed=["problem_statement"],
        )
        assert resp.run_id == "r1"
        assert resp.sections_changed == ["problem_statement"]
