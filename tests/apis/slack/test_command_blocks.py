"""Tests for _command_blocks.py — Block Kit command button builders."""

from __future__ import annotations

from crewai_productfeature_planner.apis.slack.blocks._command_blocks import (
    BTN_CHECK_PUBLISH,
    BTN_CONFIGURE,
    BTN_CONFIGURE_MEMORY,
    BTN_CREATE_JIRA,
    BTN_CREATE_PROJECT,
    BTN_CURRENT_PROJECT,
    BTN_END_SESSION,
    BTN_HELP,
    BTN_LIST_IDEAS,
    BTN_LIST_PRODUCTS,
    BTN_LIST_PROJECTS,
    BTN_NEW_IDEA,
    BTN_PUBLISH,
    BTN_RESTART_PRD,
    BTN_RESUME_PRD,
    BTN_SWITCH_PROJECT,
    check_publish_buttons,
    help_blocks,
    missing_keys_buttons,
    no_products_buttons,
    post_memory_saved_buttons,
    post_memory_view_buttons,
    product_list_footer_buttons,
    restart_cancelled_buttons,
    resume_prd_button,
    session_action_buttons,
)


# ---------------------------------------------------------------------------
# Button constants
# ---------------------------------------------------------------------------


class TestButtonConstants:
    """Each BTN_* constant should be a well-formed Slack button element."""

    ALL_BUTTONS = [
        BTN_LIST_IDEAS, BTN_LIST_PRODUCTS, BTN_CONFIGURE,
        BTN_CONFIGURE_MEMORY, BTN_SWITCH_PROJECT, BTN_END_SESSION,
        BTN_RESUME_PRD, BTN_CREATE_PROJECT, BTN_LIST_PROJECTS,
        BTN_HELP, BTN_CHECK_PUBLISH, BTN_PUBLISH, BTN_CREATE_JIRA,
        BTN_RESTART_PRD, BTN_CURRENT_PROJECT, BTN_NEW_IDEA,
    ]

    def test_all_are_button_elements(self):
        for btn in self.ALL_BUTTONS:
            assert btn["type"] == "button"
            assert "action_id" in btn
            assert btn["action_id"].startswith("cmd_")
            assert btn["text"]["type"] == "plain_text"

    def test_total_button_count(self):
        assert len(self.ALL_BUTTONS) == 16

    def test_resume_prd_has_primary_style(self):
        assert BTN_RESUME_PRD.get("style") == "primary"

    def test_publish_has_primary_style(self):
        assert BTN_PUBLISH.get("style") == "primary"


# ---------------------------------------------------------------------------
# Composite builders
# ---------------------------------------------------------------------------


class TestHelpBlocks:
    def test_returns_list_of_blocks(self):
        blocks = help_blocks("U123")
        assert isinstance(blocks, list)
        assert len(blocks) >= 4

    def test_first_block_mentions_user(self):
        blocks = help_blocks("U123")
        assert "<@U123>" in blocks[0]["text"]["text"]

    def test_no_project_adds_context(self):
        blocks = help_blocks("U123", has_project=False)
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 1
        assert "project" in context_blocks[0]["elements"][0]["text"].lower()

    def test_has_project_no_context(self):
        blocks = help_blocks("U123", has_project=True)
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 0

    def test_has_action_blocks(self):
        blocks = help_blocks("U123")
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) >= 2

    def test_admin_sees_all_buttons(self):
        blocks = help_blocks("U123", is_admin=True)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        all_ids = {
            e["action_id"]
            for b in action_blocks
            for e in b["elements"]
        }
        # Admin-only buttons should be present
        assert "cmd_configure_project" in all_ids
        assert "cmd_configure_memory" in all_ids
        assert "cmd_switch_project" in all_ids
        assert "cmd_create_project" in all_ids
        assert len(action_blocks) == 4  # 4 action rows for admin

    def test_non_admin_hides_admin_buttons(self):
        blocks = help_blocks("U123", is_admin=False)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        all_ids = {
            e["action_id"]
            for b in action_blocks
            for e in b["elements"]
        }
        # Admin-only buttons should NOT be present
        assert "cmd_configure_project" not in all_ids
        assert "cmd_configure_memory" not in all_ids
        assert "cmd_switch_project" not in all_ids
        assert "cmd_create_project" not in all_ids
        # But non-admin buttons should still be there
        assert "cmd_list_ideas" in all_ids
        assert "cmd_list_products" in all_ids
        assert "cmd_list_projects" in all_ids
        assert "cmd_end_session" in all_ids
        assert len(action_blocks) == 3  # 3 action rows for non-admin

    def test_non_admin_no_project_management_section(self):
        blocks = help_blocks("U123", is_admin=False)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        text = " ".join(b["text"]["text"] for b in section_blocks)
        assert "Project Management" not in text


class TestSessionActionButtons:
    def test_contains_switch_and_end(self):
        blocks = session_action_buttons()
        assert len(blocks) == 1
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_switch_project" in ids
        assert "cmd_end_session" in ids


class TestResumePrdButton:
    def test_returns_button(self):
        btn = resume_prd_button()
        assert btn["action_id"] == "cmd_resume_prd"


class TestPostMemorySavedButtons:
    def test_contains_configure_and_list(self):
        blocks = post_memory_saved_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_configure_memory" in ids
        assert "cmd_list_ideas" in ids


class TestPostMemoryViewButtons:
    def test_contains_configure(self):
        blocks = post_memory_view_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_configure_memory" in ids


class TestNoProductsButtons:
    def test_contains_list_ideas(self):
        blocks = no_products_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_list_ideas" in ids


class TestProductListFooterButtons:
    def test_contains_list_ideas(self):
        blocks = product_list_footer_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_list_ideas" in ids


class TestMissingKeysButtons:
    def test_contains_configure(self):
        blocks = missing_keys_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_configure_project" in ids


class TestCheckPublishButtons:
    def test_contains_check_publish(self):
        blocks = check_publish_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_check_publish" in ids


class TestRestartCancelledButtons:
    def test_contains_resume(self):
        blocks = restart_cancelled_buttons()
        ids = {e["action_id"] for e in blocks[0]["elements"]}
        assert "cmd_resume_prd" in ids
