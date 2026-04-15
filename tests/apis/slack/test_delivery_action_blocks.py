"""Tests for delivery action Block Kit builders.

As of v0.71.0, all delivery action builders return empty lists — Confluence
and Jira publishing was removed from Slack.
"""

from crewai_productfeature_planner.apis.slack.blocks._delivery_action_blocks import (
    delivery_next_step_blocks,
    jira_only_blocks,
    publish_only_blocks,
)


class TestDeliveryNextStepBlocks:
    """delivery_next_step_blocks returns [] after v0.71.0."""

    def test_returns_empty(self):
        assert delivery_next_step_blocks("run-1") == []

    def test_returns_empty_with_flags(self):
        assert delivery_next_step_blocks("r2", show_publish=True, show_jira=True) == []


class TestJiraOnlyBlocks:
    def test_returns_empty(self):
        assert jira_only_blocks("r5") == []


class TestPublishOnlyBlocks:
    def test_returns_empty(self):
        assert publish_only_blocks("r6") == []
