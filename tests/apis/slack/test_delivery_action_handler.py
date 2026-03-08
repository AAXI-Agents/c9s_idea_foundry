"""Tests for the delivery action handler (Publish / Create Jira buttons)."""

from unittest.mock import MagicMock, patch

_HANDLER_MODULE = (
    "crewai_productfeature_planner.apis.slack.interactions_router"
    "._delivery_action_handler"
)


class TestHandleDeliveryAction:
    """Verify _handle_delivery_action routes correctly."""

    @patch(f"{_HANDLER_MODULE}._do_publish")
    def test_routes_delivery_publish(self, mock_pub):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _handle_delivery_action,
        )

        _handle_delivery_action(
            "delivery_publish", "run-1", "U1", "C1", "T1",
        )
        mock_pub.assert_called_once_with("run-1", "U1", "C1", "T1")

    @patch(f"{_HANDLER_MODULE}._do_create_jira")
    def test_routes_delivery_create_jira(self, mock_jira):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _handle_delivery_action,
        )

        _handle_delivery_action(
            "delivery_create_jira", "run-2", "U2", "C2", "T2",
        )
        mock_jira.assert_called_once_with("run-2", "U2", "C2", "T2")

    def test_unknown_action_logs_warning(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _handle_delivery_action,
        )

        with patch(f"{_HANDLER_MODULE}.logger") as mock_log:
            _handle_delivery_action("unknown_action", "r", "U", "C", "T")
            mock_log.warning.assert_called_once()


class TestDoPublish:
    """Verify _do_publish delegates to handle_publish_intent."""

    @patch(
        "crewai_productfeature_planner.apis.slack._flow_handlers.handle_publish_intent",
    )
    @patch(
        "crewai_productfeature_planner.tools.slack_tools.SlackSendMessageTool",
    )
    def test_calls_handle_publish_intent(self, MockSend, mock_publish):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _do_publish,
        )

        _do_publish("run-1", "U1", "C1", "T1")
        mock_publish.assert_called_once_with("C1", "T1", "U1", MockSend.return_value)


class TestDoCreateJira:
    """Verify _do_create_jira starts a background Jira skeleton thread."""

    @patch(f"{_HANDLER_MODULE}.threading")
    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
        return_value=MagicMock(),
    )
    def test_starts_background_thread(self, mock_client, mock_threading):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _do_create_jira,
        )

        _do_create_jira("run-3", "U3", "C3", "T3")
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    @patch(f"{_HANDLER_MODULE}.threading")
    @patch(
        "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
        return_value=MagicMock(),
    )
    def test_posts_ack_message(self, mock_get_client, mock_threading):
        from crewai_productfeature_planner.apis.slack.interactions_router._delivery_action_handler import (
            _do_create_jira,
        )

        _do_create_jira("run-4", "U4", "C4", "T4")
        client = mock_get_client.return_value
        client.chat_postMessage.assert_called_once()
        call_kw = client.chat_postMessage.call_args[1]
        assert call_kw["channel"] == "C4"
        assert call_kw["thread_ts"] == "T4"
        assert "run-4" in call_kw["text"]


class TestDeliveryActionsInDispatch:
    """Verify _DELIVERY_ACTIONS set is correctly defined for dispatch."""

    def test_delivery_actions_set(self):
        from crewai_productfeature_planner.apis.slack.interactions_router._dispatch import (
            _DELIVERY_ACTIONS,
        )

        assert "delivery_publish" in _DELIVERY_ACTIONS
        assert "delivery_create_jira" in _DELIVERY_ACTIONS
        assert len(_DELIVERY_ACTIONS) == 2
