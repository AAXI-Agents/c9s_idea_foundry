"""Tests for the delivery action handler (Publish / Create Jira buttons).

As of v0.71.0, delivery actions (publish, create_jira) were removed from
Slack.  _handle_delivery_action now logs a warning and returns immediately.
"""

from unittest.mock import patch

_HANDLER_MODULE = (
    "crewai_productfeature_planner.apis.slack.interactions_router"
    "._delivery_action_handler"
)


class TestHandleDeliveryAction:
    """Verify _handle_delivery_action is a no-op stub after v0.71.0."""

    def test_any_action_logs_warning(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _handle_delivery_action,
        )

        with patch(f"{_HANDLER_MODULE}.logger") as mock_log:
            _handle_delivery_action("delivery_publish", "r", "U", "C", "T")
            mock_log.warning.assert_called_once()

    def test_does_not_raise_on_unknown_action(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _handle_delivery_action,
        )

        # Should not raise for any action ID
        _handle_delivery_action("unknown_action", "r", "U", "C", "T")


class TestDeliveryActionsInDispatch:
    """Verify _DELIVERY_ACTIONS is empty after v0.71.0."""

    def test_delivery_actions_set_is_empty(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _DELIVERY_ACTIONS,
        )

        assert len(_DELIVERY_ACTIONS) == 0
