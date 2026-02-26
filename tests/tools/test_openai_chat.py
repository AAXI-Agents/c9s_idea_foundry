"""Tests for the OpenAI chat intent classification helper."""

import json
from unittest.mock import patch

import pytest

from crewai_productfeature_planner.tools.openai_chat import (
    _fallback,
    interpret_message,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


# ---------------------------------------------------------------------------
# _fallback
# ---------------------------------------------------------------------------

def test_fallback_returns_unknown():
    result = _fallback()
    assert result["intent"] == "unknown"
    assert result["idea"] is None
    assert "Try" in result["reply"]


# ---------------------------------------------------------------------------
# interpret_message — no API key → fallback
# ---------------------------------------------------------------------------

def test_interpret_no_api_key():
    result = interpret_message("create a PRD for a test")
    assert result["intent"] == "unknown"


# ---------------------------------------------------------------------------
# interpret_message — successful classification
# ---------------------------------------------------------------------------

def _mock_urlopen_factory(response_content: dict):
    """Create a mock urlopen context-manager returning *response_content*."""
    import io

    class FakeResp:
        def __init__(self):
            self.status = 200

        def read(self):
            payload = {
                "choices": [{"message": {"content": json.dumps(response_content)}}],
            }
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    return FakeResp()


def test_interpret_create_prd(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    openai_result = {"intent": "create_prd", "idea": "fitness app", "reply": "Starting PRD!"}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(openai_result),
    ):
        result = interpret_message("create a PRD for a fitness app")

    assert result["intent"] == "create_prd"
    assert result["idea"] == "fitness app"


def test_interpret_help(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    openai_result = {"intent": "help", "idea": None, "reply": "Here's how to use me..."}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(openai_result),
    ):
        result = interpret_message("what can you do?")

    assert result["intent"] == "help"
    assert result["idea"] is None


def test_interpret_greeting(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    openai_result = {"intent": "greeting", "idea": None, "reply": "Hey!"}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(openai_result),
    ):
        result = interpret_message("hello")

    assert result["intent"] == "greeting"


def test_interpret_with_history(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    openai_result = {"intent": "create_prd", "idea": "chat app", "reply": "ok"}
    history = [
        {"role": "user", "content": "I want to build something"},
        {"role": "assistant", "content": "What did you have in mind?"},
    ]

    captured = {}

    def _capture_urlopen(req, **kwargs):
        body = json.loads(req.data.decode())
        captured["messages"] = body["messages"]
        return _mock_urlopen_factory(openai_result)

    with patch("urllib.request.urlopen", side_effect=_capture_urlopen):
        result = interpret_message("a chat application", conversation_history=history)

    assert result["intent"] == "create_prd"
    # System prompt + 2 history items + user message = 4
    assert len(captured["messages"]) == 4


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_interpret_http_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    import urllib.error

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            "https://api.openai.com", 429, "Rate limited", {}, None,
        ),
    ):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_interpret_malformed_json_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class FakeResp:
        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "not valid json!!"}}],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_interpret_empty_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class FakeResp:
        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": ""}}],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_interpret_json_in_markdown_fences(monkeypatch):
    """OpenAI sometimes wraps JSON in markdown code fences despite instructions."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class FakeResp:
        def read(self):
            content = '```json\n{"intent":"create_prd","idea":"app","reply":"ok"}\n```'
            return json.dumps({
                "choices": [{"message": {"content": content}}],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = interpret_message("build an app")

    # Should extract JSON from within fences
    assert result["intent"] == "create_prd"
    assert result["idea"] == "app"
