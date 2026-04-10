"""Tests for the Motor async client module."""

from unittest.mock import MagicMock, patch

from crewai_productfeature_planner.mongodb import async_client


class TestAsyncClient:
    def test_get_async_client_caches(self):
        """Second call re-uses the existing Motor client."""
        mock_motor = MagicMock()
        original = async_client._async_client
        async_client._async_client = mock_motor
        try:
            client = async_client.get_async_client()
            assert client is mock_motor
        finally:
            async_client._async_client = original

    def test_reset_async_client_clears_singleton(self):
        """reset_async_client closes and clears the singleton."""
        mock_motor = MagicMock()
        async_client._async_client = mock_motor
        async_client.reset_async_client()
        assert async_client._async_client is None
        mock_motor.close.assert_called_once()

    def test_reset_noop_when_none(self):
        """reset_async_client is a no-op when no client exists."""
        async_client._async_client = None
        async_client.reset_async_client()  # should not raise
        assert async_client._async_client is None
