"""Tests for orchestrator._startup_review — startup markdown review & pipeline."""

from unittest.mock import patch

import pytest

from crewai_productfeature_planner.orchestrator.orchestrator import (
    AgentOrchestrator,
    StageResult,
)
from crewai_productfeature_planner.orchestrator._startup_review import (
    _discover_publishable_prds,
    build_startup_markdown_review_stage,
    build_startup_pipeline,
)


_MOD = "crewai_productfeature_planner.orchestrator._startup_review"
_FIND_NO_CONF = (
    "crewai_productfeature_planner.mongodb"
    ".find_completed_without_confluence"
)
_ASSEMBLE = (
    "crewai_productfeature_planner.components.document"
    ".assemble_prd_from_doc"
)
_HAS_CONF = f"{_MOD}._has_confluence_credentials"
_DISCOVER_PRDS = f"{_MOD}._discover_publishable_prds"
_PUBLISH = (
    "crewai_productfeature_planner.tools.confluence_tool"
    ".publish_to_confluence"
)
_UPSERT_DR = (
    "crewai_productfeature_planner.mongodb.product_requirements"
    ".upsert_delivery_record"
)


# ── _discover_publishable_prds ───────────────────────────────────────


class TestDiscoverPublishablePrds:
    """Tests for _discover_publishable_prds helper."""

    @patch(_ASSEMBLE, return_value="")
    @patch(_FIND_NO_CONF, return_value=[])
    def test_empty_when_no_docs_and_no_files(self, _find, _assemble):
        """Returns empty when MongoDB has no unpublished docs."""
        items = _discover_publishable_prds()
        assert items == []

    @patch(_ASSEMBLE, return_value="# PRD\n\nContent")
    @patch(_FIND_NO_CONF)
    def test_returns_mongodb_docs(self, mock_find, _assemble):
        mock_find.return_value = [
            {"run_id": "run-1", "idea": "Feature A", "output_file": ""},
        ]
        items = _discover_publishable_prds()
        assert len(items) == 1
        assert items[0]["run_id"] == "run-1"
        assert items[0]["source"] == "mongodb"
        assert items[0]["title"] == "PRD — Feature A"

    @patch(_ASSEMBLE, return_value="")
    @patch(_FIND_NO_CONF)
    def test_skips_docs_with_no_content(self, mock_find, _assemble):
        mock_find.return_value = [
            {"run_id": "run-1", "idea": "Empty", "output_file": ""},
        ]
        items = _discover_publishable_prds()
        assert items == []

    @patch(_FIND_NO_CONF, side_effect=Exception("db error"))
    def test_mongodb_failure_returns_empty(self, _find):
        items = _discover_publishable_prds()
        assert items == []



# ── Startup Markdown Review Stage ────────────────────────────────────


class TestStartupMarkdownReviewStage:
    """Tests for build_startup_markdown_review_stage."""

    def test_stage_name(self):
        stage = build_startup_markdown_review_stage()
        assert stage.name == "startup_markdown_review"

    def test_description_mentions_confluence(self):
        stage = build_startup_markdown_review_stage()
        assert "confluence" in stage.description.lower()

    def test_no_approval_gate(self):
        stage = build_startup_markdown_review_stage()
        assert stage.get_approval is None
        assert stage.finalized_exc is None
        assert stage.requires_approval is None

    @patch(_HAS_CONF, return_value=False)
    def test_skips_without_credentials(self, _hc):
        stage = build_startup_markdown_review_stage()
        assert stage.should_skip() is True

    @patch(_DISCOVER_PRDS, return_value=[])
    @patch(_HAS_CONF, return_value=True)
    def test_skips_when_no_publishable_prds(self, _hc, _disc):
        stage = build_startup_markdown_review_stage()
        assert stage.should_skip() is True

    @patch(
        _DISCOVER_PRDS,
        return_value=[
            {
                "run_id": "r1",
                "title": "PRD — Test",
                "content": "# PRD",
                "source": "mongodb",
                "output_file": "",
            }
        ],
    )
    @patch(_HAS_CONF, return_value=True)
    def test_does_not_skip_with_publishable_prds(self, _hc, _disc):
        stage = build_startup_markdown_review_stage()
        assert stage.should_skip() is False

    @patch(_UPSERT_DR)
    @patch(
        _PUBLISH,
        return_value={"url": "https://wiki/page/1", "page_id": "1", "action": "created"},
    )
    @patch(
        _DISCOVER_PRDS,
        return_value=[
            {
                "run_id": "r1",
                "title": "PRD — Test",
                "content": "# PRD content",
                "source": "mongodb",
                "output_file": "",
            }
        ],
    )
    @patch(_HAS_CONF, return_value=True)
    def test_run_publishes_and_saves_url(self, _hc, _disc, mock_pub, mock_upsert):
        stage = build_startup_markdown_review_stage()
        assert stage.should_skip() is False  # prime _ctx
        result = stage.run()

        mock_pub.assert_called_once_with(
            title="PRD — Test",
            markdown_content="# PRD content",
            run_id="r1",
        )
        mock_upsert.assert_called_once_with(
            run_id="r1",
            confluence_published=True,
            confluence_url="https://wiki/page/1",
            confluence_page_id="1",
        )
        assert "Published 1 PRD(s)" in result.output

    @patch(
        _PUBLISH,
        return_value={"url": "https://wiki/p/2", "page_id": "2", "action": "created"},
    )
    @patch(
        _DISCOVER_PRDS,
        return_value=[
            {
                "run_id": "",
                "title": "PRD — disk_file",
                "content": "# Disk PRD",
                "source": "disk",
                "output_file": "/output/prds/test.md",
            }
        ],
    )
    @patch(_HAS_CONF, return_value=True)
    def test_run_disk_item_skips_save_url(self, _hc, _disc, mock_pub):
        """Disk items without a run_id should not call upsert_delivery_record."""
        stage = build_startup_markdown_review_stage()
        stage.should_skip()  # prime _ctx
        result = stage.run()

        mock_pub.assert_called_once()
        assert "Published 1 PRD(s)" in result.output

    @patch(
        _PUBLISH,
        side_effect=RuntimeError("API error 500"),
    )
    @patch(
        _DISCOVER_PRDS,
        return_value=[
            {
                "run_id": "r1",
                "title": "PRD — Fail",
                "content": "content",
                "source": "mongodb",
                "output_file": "",
            }
        ],
    )
    @patch(_HAS_CONF, return_value=True)
    def test_run_handles_publish_failure(self, _hc, _disc, _pub):
        stage = build_startup_markdown_review_stage()
        stage.should_skip()  # prime _ctx
        with pytest.raises(RuntimeError, match="All 1 Confluence publish"):
            stage.run()

    @patch(_UPSERT_DR)
    @patch(
        _PUBLISH,
        return_value={"url": "https://wiki/p/1", "page_id": "1", "action": "created"},
    )
    @patch(
        _DISCOVER_PRDS,
        return_value=[
            {
                "run_id": "r1",
                "title": "PRD — A",
                "content": "# A",
                "source": "mongodb",
                "output_file": "",
            },
            {
                "run_id": "r2",
                "title": "PRD — B",
                "content": "# B",
                "source": "mongodb",
                "output_file": "",
            },
        ],
    )
    @patch(_HAS_CONF, return_value=True)
    def test_run_publishes_multiple(self, _hc, _disc, mock_pub, mock_upsert):
        stage = build_startup_markdown_review_stage()
        stage.should_skip()  # prime _ctx
        result = stage.run()

        assert mock_pub.call_count == 2
        assert mock_upsert.call_count == 2
        assert "Published 2 PRD(s)" in result.output

    def test_apply_is_noop(self):
        stage = build_startup_markdown_review_stage()
        sr = StageResult(output="Published 1 PRD(s) to Confluence.")
        # Should not raise
        stage.apply(sr)


# ── Startup Pipeline ─────────────────────────────────────────────────


class TestStartupPipeline:
    """Tests for build_startup_pipeline."""

    def test_returns_orchestrator(self):
        pipeline = build_startup_pipeline()
        assert isinstance(pipeline, AgentOrchestrator)

    def test_has_one_stage(self):
        pipeline = build_startup_pipeline()
        assert len(pipeline.stages) == 1

    def test_first_stage_is_markdown_review(self):
        pipeline = build_startup_pipeline()
        assert pipeline.stages[0].name == "startup_markdown_review"

    @patch(_HAS_CONF, return_value=False)
    def test_pipeline_skips_when_no_credentials(self, _hc):
        pipeline = build_startup_pipeline()
        pipeline.run_pipeline()
        assert pipeline.skipped == ["startup_markdown_review"]
        assert pipeline.completed == []

    @patch(_UPSERT_DR)
    @patch(
        _PUBLISH,
        return_value={"url": "https://wiki/p/1", "page_id": "1", "action": "created"},
    )
    @patch(
        _DISCOVER_PRDS,
        return_value=[
            {
                "run_id": "r1",
                "title": "PRD — Pipeline",
                "content": "# PRD",
                "source": "mongodb",
                "output_file": "",
            }
        ],
    )
    @patch(_HAS_CONF, return_value=True)
    def test_pipeline_completes_with_publishable_prds(
        self, _hc, _disc, _pub, _upsert,
    ):
        pipeline = build_startup_pipeline()
        pipeline.run_pipeline()
        assert pipeline.completed == ["startup_markdown_review"]
        assert pipeline.skipped == []
