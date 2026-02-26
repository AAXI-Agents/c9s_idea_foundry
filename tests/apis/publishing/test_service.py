"""Tests for the publishing service layer."""

from unittest.mock import MagicMock, patch

import pytest


# ── list_pending_prds ────────────────────────────────────────────────


class TestListPendingPrds:
    def test_empty_sources(self):
        with (
            patch(
                "crewai_productfeature_planner.orchestrator._startup_review._discover_publishable_prds",
                return_value=[],
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_delivery._discover_pending_deliveries",
                return_value=[],
            ),
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                list_pending_prds,
            )
            result = list_pending_prds()
        assert result == []

    def test_deduplicates_by_run_id(self):
        item = {
            "run_id": "r1",
            "title": "PRD — test",
            "source": "mongodb",
            "output_file": "",
            "content": "# PRD",
        }
        with (
            patch(
                "crewai_productfeature_planner.orchestrator._startup_review._discover_publishable_prds",
                return_value=[item],
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_delivery._discover_pending_deliveries",
                return_value=[item],  # same run_id
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.repository.get_delivery_record",
                return_value=None,
            ),
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                list_pending_prds,
            )
            result = list_pending_prds()
        assert len(result) == 1

    def test_combines_both_sources(self):
        pub_item = {
            "run_id": "r1",
            "title": "PRD — alpha",
            "source": "mongodb",
            "output_file": "",
            "content": "# PRD alpha",
        }
        del_item = {
            "run_id": "r2",
            "title": "PRD — beta",
            "source": "mongodb",
            "output_file": "",
            "content": "# PRD beta",
        }
        with (
            patch(
                "crewai_productfeature_planner.orchestrator._startup_review._discover_publishable_prds",
                return_value=[pub_item],
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_delivery._discover_pending_deliveries",
                return_value=[del_item],
            ),
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.repository.get_delivery_record",
                return_value=None,
            ),
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                list_pending_prds,
            )
            result = list_pending_prds()
        assert len(result) == 2
        run_ids = {r["run_id"] for r in result}
        assert run_ids == {"r1", "r2"}


# ── publish_confluence_single ────────────────────────────────────────


class TestPublishConfluenceSingle:
    def test_no_credentials(self):
        with patch(
            "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
            return_value=False,
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                publish_confluence_single,
            )
            with pytest.raises(RuntimeError, match="credentials"):
                publish_confluence_single("r1")

    def test_not_found(self):
        with (
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.find_completed_without_confluence",
                return_value=[],
            ),
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                publish_confluence_single,
            )
            with pytest.raises(ValueError, match="No unpublished PRD"):
                publish_confluence_single("nonexistent")

    def test_successful_publish(self):
        doc = {"run_id": "r1", "idea": "fitness tracker"}
        publish_result = {"url": "https://example.com/page/1", "page_id": "1", "action": "created"}

        with (
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.find_completed_without_confluence",
                return_value=[doc],
            ),
            patch(
                "crewai_productfeature_planner.components.document.assemble_prd_from_doc",
                return_value="# PRD content",
            ),
            patch(
                "crewai_productfeature_planner.tools.confluence_tool.publish_to_confluence",
                return_value=publish_result,
            ),
            patch(
                "crewai_productfeature_planner.mongodb.save_confluence_url",
            ) as mock_save,
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                publish_confluence_single,
            )
            result = publish_confluence_single("r1")

        assert result["url"] == "https://example.com/page/1"
        assert result["action"] == "created"
        mock_save.assert_called_once()


# ── publish_confluence_all ───────────────────────────────────────────


class TestPublishConfluenceAll:
    def test_no_pending(self):
        with (
            patch(
                "crewai_productfeature_planner.tools.confluence_tool._has_confluence_credentials",
                return_value=True,
            ),
            patch(
                "crewai_productfeature_planner.orchestrator._startup_review._discover_publishable_prds",
                return_value=[],
            ),
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                publish_confluence_all,
            )
            result = publish_confluence_all()
        assert result["published"] == 0
        assert "No pending" in result.get("message", "")


# ── get_delivery_status ──────────────────────────────────────────────


class TestGetDeliveryStatus:
    def test_not_found(self):
        with patch(
            "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record",
            return_value=None,
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                get_delivery_status,
            )
            with pytest.raises(ValueError, match="No delivery record"):
                get_delivery_status("nonexistent")

    def test_found(self):
        record = {
            "_id": "mongo_id_obj",
            "run_id": "r1",
            "confluence_published": True,
            "confluence_url": "https://example.com",
            "status": "partial",
        }
        with patch(
            "crewai_productfeature_planner.mongodb.product_requirements.get_delivery_record",
            return_value=record,
        ):
            from crewai_productfeature_planner.apis.publishing.service import (
                get_delivery_status,
            )
            result = get_delivery_status("r1")
        assert "_id" not in result
        assert result["run_id"] == "r1"
