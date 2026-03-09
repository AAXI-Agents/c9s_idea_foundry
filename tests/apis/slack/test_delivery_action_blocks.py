"""Tests for delivery action Block Kit builders."""

from crewai_productfeature_planner.apis.slack.blocks._delivery_action_blocks import (
    delivery_next_step_blocks,
    jira_only_blocks,
    publish_only_blocks,
)


class TestDeliveryNextStepBlocks:
    """Verify delivery_next_step_blocks produces correct Block Kit output."""

    def test_both_buttons(self):
        blocks = delivery_next_step_blocks("run-1")
        assert len(blocks) == 3  # divider + section + actions
        actions = blocks[-1]
        assert actions["type"] == "actions"
        ids = [el["action_id"] for el in actions["elements"]]
        assert "delivery_publish" in ids
        assert "delivery_create_jira" in ids
        # All values encode the run_id
        for el in actions["elements"]:
            assert el["value"] == "run-1"

    def test_publish_only(self):
        blocks = delivery_next_step_blocks("r2", show_publish=True, show_jira=False)
        assert len(blocks) == 3
        ids = [el["action_id"] for el in blocks[-1]["elements"]]
        assert ids == ["delivery_publish"]

    def test_jira_only(self):
        blocks = delivery_next_step_blocks("r3", show_publish=False, show_jira=True)
        assert len(blocks) == 3
        ids = [el["action_id"] for el in blocks[-1]["elements"]]
        assert ids == ["delivery_create_jira"]

    def test_neither_returns_empty(self):
        assert delivery_next_step_blocks("r4", show_publish=False, show_jira=False) == []


class TestJiraOnlyBlocks:
    def test_returns_actions_block(self):
        blocks = jira_only_blocks("r5")
        ids = [el["action_id"] for el in blocks[-1]["elements"]]
        assert ids == ["delivery_create_jira"]

    def test_value_is_run_id(self):
        blocks = jira_only_blocks("run-abc")
        assert blocks[-1]["elements"][0]["value"] == "run-abc"

    def test_button_label_says_skeleton(self):
        """The Jira button must say 'Create Jira Skeleton' — not 'Create
        Jira Tickets' — because the action always starts with skeleton
        generation (the first phase of the phased Jira workflow)."""
        blocks = jira_only_blocks("r-label")
        btn = blocks[-1]["elements"][0]
        assert "Skeleton" in btn["text"]["text"]
        assert "Tickets" not in btn["text"]["text"]


class TestPublishOnlyBlocks:
    def test_returns_actions_block(self):
        blocks = publish_only_blocks("r6")
        ids = [el["action_id"] for el in blocks[-1]["elements"]]
        assert ids == ["delivery_publish"]

    def test_value_is_run_id(self):
        blocks = publish_only_blocks("run-xyz")
        assert blocks[-1]["elements"][0]["value"] == "run-xyz"
