"""Tests for product list Block Kit builder, session handler, and intent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crewai_productfeature_planner.apis.slack.blocks import product_list_blocks


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_PROJECT_ID = "proj-prod-999"
_PROJECT_NAME = "Delivery Project"
_USER = "U_DELIVERY"

_PRODUCTS = [
    {
        "run_id": "run-p1",
        "idea": "Fitness tracker mobile app",
        "status": "completed",
        "iteration": 5,
        "sections_done": 10,
        "total_sections": 10,
        "confluence_published": False,
        "confluence_url": "",
        "jira_completed": False,
        "jira_phase": "",
        "jira_tickets": [],
    },
    {
        "run_id": "run-p2",
        "idea": "Social login feature",
        "status": "completed",
        "iteration": 3,
        "sections_done": 10,
        "total_sections": 10,
        "confluence_published": True,
        "confluence_url": "https://wiki.example.com/page/123",
        "jira_completed": False,
        "jira_phase": "skeleton_approved",
        "jira_tickets": [],
    },
    {
        "run_id": "run-p3",
        "idea": "Dark mode implementation",
        "status": "completed",
        "iteration": 4,
        "sections_done": 10,
        "total_sections": 10,
        "confluence_published": True,
        "confluence_url": "https://wiki.example.com/page/456",
        "jira_completed": True,
        "jira_phase": "subtasks_done",
        "jira_tickets": ["PROJ-1", "PROJ-2"],
    },
]


# ---------------------------------------------------------------------------
# product_list_blocks builder
# ---------------------------------------------------------------------------


class TestProductListBlocks:
    """Verify the Block Kit builder returns correct blocks with actions."""

    def test_header_present(self):
        """Header block should contain the project name."""
        blocks = product_list_blocks(_PRODUCTS, _USER, _PROJECT_NAME, _PROJECT_ID)
        assert blocks[0]["type"] == "header"
        assert _PROJECT_NAME in blocks[0]["text"]["text"]

    def test_context_instructions_present(self):
        """Second block should be a context block with instructions."""
        blocks = product_list_blocks(_PRODUCTS, _USER, _PROJECT_NAME, _PROJECT_ID)
        assert blocks[1]["type"] == "context"
        assert "delivery" in blocks[1]["elements"][0]["text"].lower()

    def test_each_product_has_section_block(self):
        """Each product should have a section block."""
        blocks = product_list_blocks(_PRODUCTS, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        assert len(section_blocks) == len(_PRODUCTS)

    def test_unpublished_product_has_confluence_button(self):
        """Product without Confluence should have Publish Confluence button."""
        products = [_PRODUCTS[0]]  # confluence_published=False
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 1
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_confluence_1" in action_ids

    def test_unpublished_product_has_jira_skeleton_button(self):
        """Product with no Jira phase should have Review Jira Skeleton button."""
        products = [_PRODUCTS[0]]  # jira_phase=""
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_jira_skeleton_1" in action_ids

    def test_skeleton_approved_has_epics_button(self):
        """Product with skeleton_approved should have Publish Epics & Stories button."""
        products = [_PRODUCTS[1]]  # jira_phase="skeleton_approved"
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_jira_epics_1" in action_ids
        # Should NOT have skeleton button
        assert "product_jira_skeleton_1" not in action_ids

    def test_fully_delivered_has_view_details(self):
        """Fully delivered product should show View Details button."""
        products = [_PRODUCTS[2]]  # confluence=True, jira_completed=True
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_view_1" in action_ids
        # Should also have View Confluence link-button
        assert "product_open_confluence_1" in action_ids
        # Should NOT have publish/skeleton buttons
        assert "product_confluence_1" not in action_ids
        assert "product_jira_skeleton_1" not in action_ids

    def test_view_confluence_button_has_url(self):
        """When confluence URL exists, View Confluence button should have url."""
        products = [_PRODUCTS[1]]  # confluence=True, has URL
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        conf_btn = next(
            (e for e in elements if e["action_id"].startswith("product_open_confluence_")),
            None,
        )
        assert conf_btn is not None
        assert conf_btn["url"] == "https://wiki.example.com/page/123"

    def test_button_value_format(self):
        """Button values should carry project_id|index|run_id."""
        products = [_PRODUCTS[0]]
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        first_btn = action_blocks[0]["elements"][0]
        parts = first_btn["value"].split("|")
        assert len(parts) == 3
        assert parts[0] == _PROJECT_ID
        assert parts[1] == "1"
        assert parts[2] == "run-p1"

    def test_empty_product_list(self):
        """Empty product list should still produce header + context + footer."""
        blocks = product_list_blocks([], _USER, _PROJECT_NAME, _PROJECT_ID)
        # header + context + divider + footer
        assert blocks[0]["type"] == "header"
        assert blocks[-1]["type"] == "context"  # footer hint

    def test_long_idea_title_truncated(self):
        """Idea text longer than 120 chars should be truncated."""
        long_idea = {
            **_PRODUCTS[0],
            "idea": "A" * 200,
        }
        blocks = product_list_blocks([long_idea], _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        # truncated text should end with \u2026 (ellipsis)
        assert "\u2026" in text

    def test_confluence_view_link_shown_when_published(self):
        """Published Confluence URL should appear as a completed status link."""
        products = [_PRODUCTS[1]]  # confluence_published=True, has URL
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert ":white_check_mark:" in text
        assert "Confluence PRD" in text
        assert "wiki.example.com" in text

    def test_epics_stories_done_has_subtasks_button(self):
        """Product with epics_stories_done should have Publish Sub-tasks button."""
        product = {
            **_PRODUCTS[0],
            "confluence_published": True,
            "jira_phase": "epics_stories_done",
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_jira_subtasks_1" in action_ids

    def test_skeleton_pending_has_skeleton_button(self):
        """Product with skeleton_pending should still show Review Jira Skeleton."""
        product = {
            **_PRODUCTS[0],
            "confluence_published": True,
            "jira_phase": "skeleton_pending",
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_jira_skeleton_1" in action_ids

    def test_footer_hint_present(self):
        """Footer should hint about list ideas."""
        blocks = product_list_blocks(_PRODUCTS, _USER, _PROJECT_NAME, _PROJECT_ID)
        footer = blocks[-1]
        assert footer["type"] == "context"
        assert "list ideas" in footer["elements"][0]["text"].lower()

    def test_multiple_products_indexed_correctly(self):
        """Action IDs should use correct 1-based indices for multiple products."""
        blocks = product_list_blocks(_PRODUCTS, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) == 3
        # First product (idx=1) — has confluence + jira skeleton
        ids_1 = {e["action_id"] for e in action_blocks[0]["elements"]}
        assert any("_1" in aid for aid in ids_1)
        # Second product (idx=2) — has jira epics
        ids_2 = {e["action_id"] for e in action_blocks[1]["elements"]}
        assert any("_2" in aid for aid in ids_2)
        # Third product (idx=3) — fully delivered, view details
        ids_3 = {e["action_id"] for e in action_blocks[2]["elements"]}
        assert any("_3" in aid for aid in ids_3)

    def test_none_jira_phase_shows_skeleton_button(self):
        """Product with jira_phase=None should show Start Jira Skeleton button."""
        product = {
            **_PRODUCTS[0],
            "jira_phase": None,  # from MongoDB when field is None
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_jira_skeleton_1" in action_ids

    def test_none_confluence_url_treated_as_empty(self):
        """Product with confluence_url=None should not show View Confluence button."""
        product = {
            **_PRODUCTS[0],
            "confluence_published": True,
            "confluence_url": None,  # from MongoDB when field is None
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        # Should NOT have View Confluence button (URL is None)
        assert not any(aid.startswith("product_open_confluence_") for aid in action_ids)

    def test_unknown_jira_phase_shows_restart_skeleton_button(self):
        """Product with an unrecognised jira_phase should show Restart Jira Skeleton."""
        product = {
            **_PRODUCTS[0],
            "jira_completed": False,
            "jira_phase": "approved_skeleton",  # legacy / unknown phase
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        action_ids = [e["action_id"] for e in elements]
        assert "product_jira_skeleton_1" in action_ids
        # Check the button text contains "Restart"
        skeleton_btn = next(e for e in elements if e["action_id"] == "product_jira_skeleton_1")
        assert "Restart" in skeleton_btn["text"]["text"]

    def test_known_jira_phase_no_restart_button(self):
        """Product with a known jira_phase should NOT show Restart Jira Skeleton."""
        product = {
            **_PRODUCTS[0],
            "jira_completed": False,
            "jira_phase": "skeleton_approved",  # known phase
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        # Should show the epics button, not restart
        texts = [e["text"]["text"] for e in elements]
        assert not any("Restart" in t for t in texts)


# ---------------------------------------------------------------------------
# handle_list_products session handler
# ---------------------------------------------------------------------------

_SESSION_MODULE = "crewai_productfeature_planner.apis.slack._session_products"


class TestHandleListProducts:
    """Verify the session handler for listing products."""

    def test_no_session_prompts_project_selection(self):
        """If no project session, prompt_project_selection is called."""
        with patch(f"{_SESSION_MODULE}.prompt_project_selection") as mock_prompt:
            from crewai_productfeature_planner.apis.slack._session_products import handle_list_products
            handle_list_products("C1", "T1", "U1", None)
        mock_prompt.assert_called_once_with("C1", "T1", "U1")

    def test_no_project_id_prompts_selection(self):
        """If session has no project_id, prompt_project_selection is called."""
        with patch(f"{_SESSION_MODULE}.prompt_project_selection") as mock_prompt:
            from crewai_productfeature_planner.apis.slack._session_products import handle_list_products
            handle_list_products("C1", "T1", "U1", {"project_name": "Foo"})
        mock_prompt.assert_called_once()

    def test_no_products_sends_info_message(self):
        """If no completed products exist, an info message is sent."""
        session = {"project_id": "p1", "project_name": "Test"}
        with (
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.repository.find_completed_ideas_by_project",
                return_value=[],
            ),
            patch(f"{_SESSION_MODULE}.reply") as mock_reply,
        ):
            from crewai_productfeature_planner.apis.slack._session_products import handle_list_products
            handle_list_products("C1", "T1", "U1", session)
        mock_reply.assert_called_once()
        text = mock_reply.call_args[0][2]
        assert "no completed products" in text.lower()

    def test_products_posted_as_blocks(self):
        """When products exist, blocks are posted via Slack client."""
        session = {"project_id": "p1", "project_name": "Test"}
        mock_client = MagicMock()

        with (
            patch(
                "crewai_productfeature_planner.mongodb.working_ideas.repository.find_completed_ideas_by_project",
                return_value=[_PRODUCTS[0]],
            ),
            patch(
                "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
                return_value=mock_client,
            ),
            patch(
                "crewai_productfeature_planner.apis.slack._session_ideas._backfill_missing_idea_titles",
            ),
        ):
            from crewai_productfeature_planner.apis.slack._session_products import handle_list_products
            handle_list_products("C1", "T1", "U1", session)

        mock_client.chat_postMessage.assert_called_once()
        call_kw = mock_client.chat_postMessage.call_args[1]
        assert call_kw["channel"] == "C1"
        assert call_kw["thread_ts"] == "T1"
        assert isinstance(call_kw["blocks"], list)


# ---------------------------------------------------------------------------
# Intent phrase matching
# ---------------------------------------------------------------------------


class TestListProductsIntentPhrases:
    """Verify list_products_intent phrase matching works correctly."""

    def test_list_products_phrase_matches(self):
        """'list products' should match _LIST_PRODUCTS_PHRASES."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _LIST_PRODUCTS_PHRASES,
        )
        assert any(p in "list products" for p in _LIST_PRODUCTS_PHRASES)

    def test_show_products_phrase_matches(self):
        """'show products' should match _LIST_PRODUCTS_PHRASES."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _LIST_PRODUCTS_PHRASES,
        )
        assert any(p in "show products" for p in _LIST_PRODUCTS_PHRASES)

    def test_delivery_status_phrase_matches(self):
        """'delivery status' should match _LIST_PRODUCTS_PHRASES."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _LIST_PRODUCTS_PHRASES,
        )
        assert any(p in "show me delivery status" for p in _LIST_PRODUCTS_PHRASES)

    def test_completed_ideas_phrase_matches(self):
        """'completed ideas' should match _LIST_PRODUCTS_PHRASES."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _LIST_PRODUCTS_PHRASES,
        )
        assert any(p in "show completed ideas" for p in _LIST_PRODUCTS_PHRASES)

    def test_phrase_fallback_returns_list_products_intent(self):
        """_phrase_fallback should return 'list_products_intent' for product phrases."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("list products")
        assert result["intent"] == "list_products_intent"

    def test_phrase_fallback_returns_list_products_for_delivery_status(self):
        """_phrase_fallback should return 'list_products_intent' for 'delivery status'."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _phrase_fallback,
        )
        result = _phrase_fallback("delivery status")
        assert result["intent"] == "list_products_intent"

    def test_list_ideas_does_not_match_products(self):
        """'list ideas' should NOT match _LIST_PRODUCTS_PHRASES."""
        from crewai_productfeature_planner.apis.slack._intent_phrases import (
            _LIST_PRODUCTS_PHRASES,
        )
        # 'list ideas' should match _LIST_IDEAS_PHRASES, not products
        matches = any(p in "list ideas" for p in _LIST_PRODUCTS_PHRASES)
        assert not matches


# ---------------------------------------------------------------------------
# Dispatch routing — product action prefixes
# ---------------------------------------------------------------------------


class TestProductDispatchRouting:
    """Verify that product action IDs are routed correctly in ack labels."""

    def test_confluence_ack_label(self):
        """product_confluence_ prefix should produce correct ack label."""
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _ack_action,
        )
        label = _ack_action("product_confluence_1", "testuser")
        assert "Confluence" in label
        assert "testuser" in label

    def test_jira_skeleton_ack_label(self):
        """product_jira_skeleton_ prefix should produce correct ack label."""
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _ack_action,
        )
        label = _ack_action("product_jira_skeleton_2", "testuser")
        assert "skeleton" in label.lower()
        assert "testuser" in label

    def test_jira_epics_ack_label(self):
        """product_jira_epics_ prefix should produce correct ack label."""
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _ack_action,
        )
        label = _ack_action("product_jira_epics_3", "testuser")
        assert "epics" in label.lower()

    def test_jira_subtasks_ack_label(self):
        """product_jira_subtasks_ prefix should produce correct ack label."""
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _ack_action,
        )
        label = _ack_action("product_jira_subtasks_1", "testuser")
        assert "sub-tasks" in label.lower() or "subtasks" in label.lower()

    def test_view_details_ack_label(self):
        """product_view_ prefix should produce correct ack label."""
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _ack_action,
        )
        label = _ack_action("product_view_1", "testuser")
        assert "details" in label.lower() or "view" in label.lower()


# ---------------------------------------------------------------------------
# Jira icon differentiation (issue #2)
# ---------------------------------------------------------------------------


class TestDeliveryStatusDisplay:
    """Verify that only completed steps show :white_check_mark: status text;
    incomplete steps appear only as interactive buttons."""

    def test_nothing_completed_no_status_text(self):
        """When neither Confluence nor Jira is done, section has only title."""
        products = [_PRODUCTS[0]]  # conf=False, jira_completed=False
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert ":white_check_mark:" not in text
        assert "Confluence" not in text
        assert "Jira" not in text

    def test_confluence_completed_shows_checkmark(self):
        """Completed Confluence should show :white_check_mark: Confluence PRD."""
        products = [_PRODUCTS[1]]  # confluence_published=True
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert ":white_check_mark:" in text
        assert "Confluence PRD" in text

    def test_confluence_not_published_has_button_only(self):
        """Unpublished Confluence should NOT appear in status text,
        only as a button."""
        products = [_PRODUCTS[0]]  # confluence_published=False
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert "Confluence" not in text
        # But button should exist
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        action_ids = [e["action_id"] for e in action_blocks[0]["elements"]]
        assert "product_confluence_1" in action_ids

    def test_jira_completed_shows_checkmark(self):
        """Completed Jira should show :white_check_mark: Jira Ticketing."""
        products = [_PRODUCTS[2]]  # jira_completed=True
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert ":white_check_mark: Jira Ticketing" in text

    def test_jira_not_started_not_in_status_text(self):
        """Jira not started should NOT appear in section status text."""
        products = [_PRODUCTS[0]]  # jira_phase="", jira_completed=False
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert "Jira" not in text

    def test_jira_in_progress_shows_phase_status(self):
        """Jira in-progress should show the current phase as status text."""
        product = {
            **_PRODUCTS[0],
            "jira_phase": "skeleton_pending",
            "jira_completed": False,
            "confluence_published": True,
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert ":hourglass_flowing_sand:" in text
        assert "Skeleton awaiting approval" in text
        # Confluence should also be there (it's completed)
        assert ":white_check_mark:" in text
        assert "Confluence PRD" in text

    def test_jira_epics_stories_done_shows_phase(self):
        """jira_phase='epics_stories_done' should show its label."""
        product = {
            **_PRODUCTS[0],
            "jira_phase": "epics_stories_done",
            "jira_completed": False,
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert "Epics & Stories created" in text

    def test_both_completed_shows_both_checkmarks(self):
        """When both Confluence and Jira completed, both show checkmarks."""
        products = [_PRODUCTS[2]]  # both completed
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = section_blocks[0]["text"]["text"]
        assert text.count(":white_check_mark:") == 2
        assert "Confluence PRD" in text
        assert "Jira Ticketing" in text

    def test_start_jira_skeleton_button_label(self):
        """Not-started Jira should have 'Start Jira Skeleton' button."""
        products = [_PRODUCTS[0]]  # jira_phase=""
        blocks = product_list_blocks(products, _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        jira_btn = next(e for e in elements if "jira_skeleton" in e["action_id"])
        assert "Start" in jira_btn["text"]["text"]

    def test_resume_jira_skeleton_button_label(self):
        """In-progress Jira (skeleton_pending) should have 'Review' button."""
        product = {
            **_PRODUCTS[0],
            "confluence_published": True,
            "jira_phase": "skeleton_pending",
        }
        blocks = product_list_blocks([product], _USER, _PROJECT_NAME, _PROJECT_ID)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        elements = action_blocks[0]["elements"]
        jira_btn = next(e for e in elements if "jira_skeleton" in e["action_id"])
        assert "Review" in jira_btn["text"]["text"]
        assert jira_btn.get("style") == "primary"


# ---------------------------------------------------------------------------
# View details — Confluence URL and Jira ticket counts (issues #1 & #3)
# ---------------------------------------------------------------------------

_WI_REPO = "crewai_productfeature_planner.mongodb.working_ideas.repository"
_PR_MODULE = "crewai_productfeature_planner.mongodb.product_requirements"


class TestViewDetailsConfluenceUrl:
    """Verify view details shows Confluence URL correctly."""

    def test_confluence_url_from_delivery_record(self):
        """When doc has no confluence_url but delivery record does, show link."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {
            "confluence_published": True,
            "confluence_url": "https://wiki.example.com/page/99",
            "jira_tickets": [],
        }
        mock_send_tool = MagicMock()
        with (
            patch(
                f"{_WI_REPO}.find_run_any_status",
                return_value=doc,
            ),
            patch(
                f"{_PR_MODULE}.get_delivery_record",
                return_value=record,
            ),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "wiki.example.com" in text
        assert "Not published" not in text

    def test_confluence_not_published_shown(self):
        """When no confluence URL exists anywhere, show 'Not published'."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {"confluence_published": False, "confluence_url": "", "jira_tickets": []}
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "Not published" in text


class TestViewDetailsJiraTicketCounts:
    """Verify view details shows Jira ticket type counts."""

    def test_shows_type_counts(self):
        """Should show count of Epics, Stories, and Sub-tasks."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {
            "confluence_published": False,
            "jira_tickets": [
                {"key": "PROJ-1", "type": "Epic", "summary": "Auth"},
                {"key": "PROJ-2", "type": "Epic", "summary": "Data"},
                {"key": "PROJ-3", "type": "Story", "summary": "Login"},
                {"key": "PROJ-4", "type": "Story", "summary": "Register"},
                {"key": "PROJ-5", "type": "Story", "summary": "Logout"},
                {"key": "PROJ-6", "type": "Sub-task", "summary": "Unit tests"},
            ],
        }
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "6 total" in text
        assert "2 Epics" in text
        assert "3 Stories" in text
        assert "1 Sub-task" in text

    def test_no_tickets_shows_none(self):
        """When no tickets exist, show 'No tickets created'."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {"confluence_published": False, "jira_tickets": []}
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "No tickets created" in text

    def test_single_epic_uses_singular(self):
        """1 Epic should say '1 Epic' not '1 Epics'."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {
            "confluence_published": False,
            "jira_tickets": [
                {"key": "PROJ-1", "type": "Epic", "summary": "Auth"},
            ],
        }
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "1 Epic" in text
        assert "1 Epics" not in text

    def test_confluence_published_no_url_shows_published(self):
        """When confluence_published=True but URL is empty, say published."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {
            "confluence_published": True,
            "confluence_url": "",
            "jira_tickets": [],
        }
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "Published" in text
        assert "Not published" not in text

    def test_legacy_task_type_normalised_to_subtask(self):
        """Tickets stored as type='Task' should display as Sub-tasks."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {
            "confluence_published": False,
            "jira_tickets": [
                {"key": "PROJ-1", "type": "Epic"},
                {"key": "PROJ-2", "type": "Story"},
                {"key": "PROJ-3", "type": "Task"},
                {"key": "PROJ-4", "type": "Task"},
            ],
        }
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "2 Sub-tasks" in text

    def test_unknown_type_resolved_from_jira(self):
        """Tickets with type='unknown' should be resolved via Jira API."""
        doc = {"run_id": "run-x", "idea": "Test", "status": "completed"}
        record = {
            "confluence_published": False,
            "jira_tickets": [
                {"key": "PROJ-1", "type": "unknown"},
                {"key": "PROJ-2", "type": "unknown"},
                {"key": "PROJ-3", "type": "unknown"},
                {"key": "PROJ-4", "type": "unknown"},
            ],
        }
        jira_issues = [
            {"issue_key": "PROJ-1", "issue_type": "Epic", "summary": "Auth"},
            {"issue_key": "PROJ-2", "issue_type": "Story", "summary": "Login"},
            {"issue_key": "PROJ-3", "issue_type": "Story", "summary": "Register"},
            {"issue_key": "PROJ-4", "issue_type": "Sub-task", "summary": "Unit tests"},
        ]
        mock_send_tool = MagicMock()
        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PR_MODULE}.get_delivery_record", return_value=record),
            patch(
                "crewai_productfeature_planner.tools.jira.search_jira_issues",
                return_value=jira_issues,
            ),
            patch(f"{_PR_MODULE}.upsert_delivery_record"),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_view_details,
            )
            _handle_view_details("run-x", 1, "U1", "C1", "T1", mock_send_tool, None)

        text = mock_send_tool.run.call_args[1]["text"]
        assert "1 Epic" in text
        assert "2 Stories" in text
        assert "1 Sub-task" in text
        assert "unknown" not in text.lower()


# ---------------------------------------------------------------------------
# Jira approval handler
# ---------------------------------------------------------------------------

_JIRA_HANDLER = (
    "crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler"
)


class TestJiraApprovalHandler:
    """Verify skeleton/review approval button handlers."""

    def test_skeleton_approve_persists_phase_and_launches_epics(self):
        """Approving skeleton should persist phase and start Epics & Stories."""
        with (
            patch(f"{_JIRA_HANDLER}._persist_jira_phase") as mock_persist,
            patch(f"{_JIRA_HANDLER}.SlackSendMessageTool"),
            patch(f"{_JIRA_HANDLER}._get_slack_client"),
            patch(f"{_JIRA_HANDLER}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )
            _handle_jira_approval_action(
                "jira_skeleton_approve", "run-x", "U1", "C1", "T1",
            )
        mock_persist.assert_called_once_with("run-x", "skeleton_approved")
        # A background thread must be started for Epics & Stories creation
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    def test_skeleton_reject_resets_phase_and_regenerates(self):
        """Rejecting skeleton should reset phase and regenerate skeleton."""
        with (
            patch(f"{_JIRA_HANDLER}._persist_jira_phase") as mock_persist,
            patch(f"{_JIRA_HANDLER}.SlackSendMessageTool"),
            patch(f"{_JIRA_HANDLER}._get_slack_client"),
            patch(f"{_JIRA_HANDLER}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )
            _handle_jira_approval_action(
                "jira_skeleton_reject", "run-x", "U1", "C1", "T1",
            )
        mock_persist.assert_called_once_with("run-x", "")
        # A background thread must be started for skeleton regeneration
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    def test_review_approve_launches_subtasks(self):
        """Approving Epics & Stories should start sub-task creation."""
        with (
            patch(f"{_JIRA_HANDLER}.SlackSendMessageTool"),
            patch(f"{_JIRA_HANDLER}._get_slack_client"),
            patch(f"{_JIRA_HANDLER}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )
            _handle_jira_approval_action(
                "jira_review_approve", "run-x", "U1", "C1", "T1",
            )
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    def test_review_skip_marks_jira_complete(self):
        """Skipping sub-tasks should mark Jira as complete."""
        with (
            patch(f"{_JIRA_HANDLER}._persist_jira_phase") as mock_phase,
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record",
            ) as mock_upsert,
            patch(f"{_JIRA_HANDLER}.SlackSendMessageTool"),
            patch(f"{_JIRA_HANDLER}._get_slack_client"),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )
            _handle_jira_approval_action(
                "jira_review_skip", "run-x", "U1", "C1", "T1",
            )
        mock_phase.assert_called_once_with("run-x", "subtasks_done")
        mock_upsert.assert_called_once_with("run-x", jira_completed=True)

    def test_subtask_approve_marks_jira_complete(self):
        """Approving sub-tasks should mark Jira as complete."""
        with (
            patch(f"{_JIRA_HANDLER}._persist_jira_phase") as mock_phase,
            patch(
                "crewai_productfeature_planner.mongodb.product_requirements.upsert_delivery_record",
            ) as mock_upsert,
            patch(f"{_JIRA_HANDLER}.SlackSendMessageTool"),
            patch(f"{_JIRA_HANDLER}._get_slack_client"),
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )
            _handle_jira_approval_action(
                "jira_subtask_approve", "run-x", "U1", "C1", "T1",
            )
        mock_phase.assert_called_once_with("run-x", "subtasks_done")
        mock_upsert.assert_called_once_with("run-x", jira_completed=True)

    def test_subtask_reject_regenerates(self):
        """Rejecting sub-tasks should reset phase and regenerate."""
        with (
            patch(f"{_JIRA_HANDLER}._persist_jira_phase") as mock_persist,
            patch(f"{_JIRA_HANDLER}.SlackSendMessageTool"),
            patch(f"{_JIRA_HANDLER}._get_slack_client"),
            patch(f"{_JIRA_HANDLER}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._jira_approval_handler import (
                _handle_jira_approval_action,
            )
            _handle_jira_approval_action(
                "jira_subtask_reject", "run-x", "U1", "C1", "T1",
            )
        mock_persist.assert_called_once_with("run-x", "epics_stories_done")
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()


class TestJiraSubtaskReviewBlocks:
    """Verify jira_subtask_review_blocks Block Kit builder."""

    def test_basic_blocks_structure(self):
        """Should produce header, context, section, divider, actions."""
        from crewai_productfeature_planner.apis.slack.blocks import (
            jira_subtask_review_blocks,
        )
        blocks = jira_subtask_review_blocks("run-123", "Sub-task output text")
        assert len(blocks) == 5
        assert blocks[0]["type"] == "header"
        assert blocks[4]["type"] == "actions"
        buttons = blocks[4]["elements"]
        assert len(buttons) == 2
        assert buttons[0]["action_id"] == "jira_subtask_approve"
        assert buttons[1]["action_id"] == "jira_subtask_reject"
        assert buttons[0]["value"] == "run-123"

    def test_long_output_truncated(self):
        """Output longer than 2800 chars should be truncated."""
        from crewai_productfeature_planner.apis.slack.blocks import (
            jira_subtask_review_blocks,
        )
        long_text = "x" * 3000
        blocks = jira_subtask_review_blocks("run-456", long_text)
        section_text = blocks[2]["text"]["text"]
        assert len(section_text) < 3000
        assert "more chars" in section_text


class TestSubtasksPendingPhaseLabel:
    """Verify subtasks_pending appears in phase labels."""

    def test_subtasks_pending_in_labels(self):
        from crewai_productfeature_planner.apis.slack.blocks._product_list_blocks import (
            _JIRA_PHASE_LABELS,
        )
        assert "subtasks_pending" in _JIRA_PHASE_LABELS
        assert _JIRA_PHASE_LABELS["subtasks_pending"] == "Sub-tasks awaiting approval"


# ---------------------------------------------------------------------------
# _handle_jira_skeleton — resume existing skeleton vs regenerate
# ---------------------------------------------------------------------------

_PLH_MOD = (
    "crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler"
)


class TestHandleJiraSkeletonResume:
    """Verify _handle_jira_skeleton shows existing skeleton when
    jira_phase is 'skeleton_pending' instead of regenerating."""

    def test_skeleton_pending_shows_existing_skeleton(self):
        """When jira_phase=='skeleton_pending' and skeleton exists in
        MongoDB, should show approval blocks without spawning thread."""
        doc = {"run_id": "run-x", "jira_phase": "skeleton_pending"}
        mock_client = MagicMock()
        mock_send = MagicMock()

        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_WI_REPO}.get_jira_skeleton", return_value="## Epic 1: Auth\n- Story: Login"),
            patch("crewai_productfeature_planner.apis.slack.blocks.jira_skeleton_approval_blocks", return_value=[{"type": "section"}]) as mock_blocks,
            patch(f"{_PLH_MOD}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_jira_skeleton,
            )
            _handle_jira_skeleton("run-x", 1, "U1", "C1", "T1", mock_send, mock_client)

        # Should show the existing skeleton
        mock_blocks.assert_called_once_with("run-x", "## Epic 1: Auth\n- Story: Login")
        mock_client.chat_postMessage.assert_called()
        # Should NOT spawn a background thread
        mock_threading.Thread.assert_not_called()

    def test_skeleton_pending_but_empty_skeleton_regenerates(self):
        """When jira_phase=='skeleton_pending' but skeleton is empty in
        MongoDB, should regenerate by spawning a background thread."""
        doc = {"run_id": "run-x", "jira_phase": "skeleton_pending"}
        mock_client = MagicMock()
        mock_send = MagicMock()

        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_WI_REPO}.get_jira_skeleton", return_value=""),
            patch(f"{_PLH_MOD}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_jira_skeleton,
            )
            _handle_jira_skeleton("run-x", 1, "U1", "C1", "T1", mock_send, mock_client)

        # Should spawn a background thread to regenerate
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    def test_no_jira_phase_generates_new_skeleton(self):
        """When jira_phase is empty, should generate a new skeleton."""
        doc = {"run_id": "run-x", "jira_phase": ""}
        mock_client = MagicMock()
        mock_send = MagicMock()

        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=doc),
            patch(f"{_PLH_MOD}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_jira_skeleton,
            )
            _handle_jira_skeleton("run-x", 1, "U1", "C1", "T1", mock_send, mock_client)

        # Should spawn a background thread to generate
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    def test_no_doc_found_generates_new_skeleton(self):
        """When document is not found at all, should try to generate."""
        mock_client = MagicMock()
        mock_send = MagicMock()

        with (
            patch(f"{_WI_REPO}.find_run_any_status", return_value=None),
            patch(f"{_PLH_MOD}.threading") as mock_threading,
        ):
            from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
                _handle_jira_skeleton,
            )
            _handle_jira_skeleton("run-x", 1, "U1", "C1", "T1", mock_send, mock_client)

        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()


# ---------------------------------------------------------------------------
# _run_jira_phase — state reconstruction
# ---------------------------------------------------------------------------

_PLH = (
    "crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler"
)
_SVC = "crewai_productfeature_planner.apis.prd.service"
_WI = "crewai_productfeature_planner.mongodb.working_ideas.repository"
_JIRA = "crewai_productfeature_planner.orchestrator._jira"


class TestRunJiraPhaseStateReconstruction:
    """Verify _run_jira_phase unpacks restore_prd_state correctly."""

    def _make_draft(self):
        """Create a minimal PRDDraft with one approved section."""
        from crewai_productfeature_planner.apis.prd._domain import (
            PRDDraft, PRDSection,
        )
        return PRDDraft(sections=[
            PRDSection(
                key="functional_requirements",
                title="Functional Requirements",
                step=1,
                content="Do the thing",
                iteration=3,
                is_approved=True,
            ),
        ])

    def _make_exec_summary(self, *, with_iterations: bool = True):
        from crewai_productfeature_planner.apis.prd._domain import (
            ExecutiveSummaryDraft, ExecutiveSummaryIteration,
        )
        if with_iterations:
            return ExecutiveSummaryDraft(
                iterations=[
                    ExecutiveSummaryIteration(
                        iteration=1, content="Exec summary v1",
                    ),
                ],
                is_approved=True,
            )
        return ExecutiveSummaryDraft()

    def _mongo_doc(self, **overrides):
        base = {
            "run_id": "run-jira-test",
            "idea": "Test idea",
            "jira_phase": "",
            "confluence_url": "https://wiki.example.com/page/42",
        }
        base.update(overrides)
        return base

    def _import_run_jira_phase(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._product_list_handler import (
            _run_jira_phase,
        )
        return _run_jira_phase

    def test_state_fields_populated_from_restore(self):
        """All state fields should be set via attribute access, not assignment."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary()
        restore_result = (
            "Refined idea text",
            draft,
            exec_summary,
            "Requirements text",
            [{"iteration": 1, "requirements": "r1", "evaluation": "ok"}],
            [{"iteration": 1, "idea": "Better idea", "evaluation": "good"}],
        )

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc()),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", return_value="test skip"),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        # Prerequisites check posted a warning — meaning we got past
        # state reconstruction without crashing.
        send.run.assert_called_once()
        assert "test skip" in send.run.call_args.kwargs.get("text", "")

    def test_state_has_correct_draft(self):
        """The draft should be applied so final_prd is assembled from it."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary()
        restore_result = ("idea", draft, exec_summary, "", [], [])
        captured_flow = {}

        original_check = None

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"  # skip reason to stop early

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc()),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        state = captured_flow["state"]
        assert state.draft is draft
        assert state.final_prd != ""
        assert "Functional Requirements" in state.final_prd
        assert state.iteration == 3

    def test_confluence_url_from_doc(self):
        """confluence_url must come from the MongoDB document."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary()
        restore_result = ("idea", draft, exec_summary, "", [], [])
        captured_flow = {}

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc(
                confluence_url="https://wiki.real.com/page/99",
            )),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        assert captured_flow["state"].confluence_url == "https://wiki.real.com/page/99"

    def test_jira_phase_from_doc(self):
        """jira_phase must come from the MongoDB document."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary()
        restore_result = ("idea", draft, exec_summary, "", [], [])
        captured_flow = {}

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc(
                jira_phase="skeleton_approved",
            )),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        assert captured_flow["state"].jira_phase == "skeleton_approved"

    def test_refinement_history_sets_idea_refined(self):
        """When refinement history exists, idea_refined must be True and
        the latest refined idea replaces the idea field."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary(with_iterations=False)
        restore_result = (
            "Original idea",
            draft,
            exec_summary,
            "",
            [],
            [{"iteration": 1, "idea": "Refined idea v1", "evaluation": "ok"}],
        )
        captured_flow = {}

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc()),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        state = captured_flow["state"]
        assert state.idea_refined is True
        assert state.idea == "Refined idea v1"

    def test_exec_summary_sets_finalized_idea(self):
        """When exec summary has latest_content, finalized_idea must be set."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary()
        restore_result = ("idea", draft, exec_summary, "", [], [])
        captured_flow = {}

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc()),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        assert captured_flow["state"].finalized_idea == "Exec summary v1"

    def test_restore_returns_none_falls_back_to_doc(self):
        """When restore_prd_state returns None, idea from doc is used."""
        captured_flow = {}

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc()),
            patch(f"{_SVC}.restore_prd_state", return_value=None),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        state = captured_flow["state"]
        assert state.idea == "Test idea"
        assert state.run_id == "run-jira-test"

    def test_no_doc_found_sends_error(self):
        """When the MongoDB doc is not found, an error is posted."""
        with patch(f"{_WI}.find_run_any_status", return_value=None):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-missing", "skeleton", "U1", "C1", "T1", send)

        send.run.assert_called_once()
        assert "Could not find" in send.run.call_args.kwargs.get("text", "")

    def test_requirements_breakdown_populated(self):
        """requirements_breakdown and requirements_broken_down must be set."""
        draft = self._make_draft()
        exec_summary = self._make_exec_summary()
        restore_result = (
            "idea", draft, exec_summary,
            "Detailed requirements here", [], [],
        )
        captured_flow = {}

        def capture_flow(flow, **_kw):
            captured_flow["state"] = flow.state
            return "bypass"

        with (
            patch(f"{_WI}.find_run_any_status", return_value=self._mongo_doc()),
            patch(f"{_SVC}.restore_prd_state", return_value=restore_result),
            patch(f"{_JIRA}._check_jira_prerequisites", side_effect=capture_flow),
        ):
            send = MagicMock()
            fn = self._import_run_jira_phase()
            fn("run-jira-test", "skeleton", "U1", "C1", "T1", send)

        state = captured_flow["state"]
        assert state.requirements_breakdown == "Detailed requirements here"
        assert state.requirements_broken_down is True
