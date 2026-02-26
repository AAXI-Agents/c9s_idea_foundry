"""Tests for the Gemini chat intent classification helper."""

import json
from unittest.mock import patch

import pytest

from crewai_productfeature_planner.tools.gemini_chat import (
    _fallback,
    interpret_message,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)


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
    """Create a mock urlopen context-manager returning a Gemini-style response."""

    class FakeResp:
        def __init__(self):
            self.status = 200

        def read(self):
            payload = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": json.dumps(response_content)}],
                    },
                }],
            }
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    return FakeResp()


def test_interpret_create_prd(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "create_prd", "idea": "fitness app", "reply": "Starting PRD!"}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(gemini_result),
    ):
        result = interpret_message("create a PRD for a fitness app")

    assert result["intent"] == "create_prd"
    assert result["idea"] == "fitness app"


def test_interpret_help(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "help", "idea": None, "reply": "Here's how to use me..."}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(gemini_result),
    ):
        result = interpret_message("what can you do?")

    assert result["intent"] == "help"
    assert result["idea"] is None


def test_interpret_greeting(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "greeting", "idea": None, "reply": "Hey!"}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(gemini_result),
    ):
        result = interpret_message("hello")

    assert result["intent"] == "greeting"


def test_interpret_publish(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "publish", "idea": None, "reply": "Publishing all pending PRDs now!"}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(gemini_result),
    ):
        result = interpret_message("publish all PRDs to confluence")

    assert result["intent"] == "publish"
    assert result["idea"] is None


def test_interpret_check_publish(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "check_publish", "idea": None, "reply": "Checking status now…"}

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_factory(gemini_result),
    ):
        result = interpret_message("what PRDs are pending?")

    assert result["intent"] == "check_publish"
    assert result["idea"] is None


def test_interpret_with_history(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "create_prd", "idea": "chat app", "reply": "ok"}
    history = [
        {"role": "user", "content": "I want to build something"},
        {"role": "assistant", "content": "What did you have in mind?"},
    ]

    captured = {}

    def _capture_urlopen(req, **kwargs):
        body = json.loads(req.data.decode())
        captured["contents"] = body["contents"]
        return _mock_urlopen_factory(gemini_result)

    with patch("urllib.request.urlopen", side_effect=_capture_urlopen):
        result = interpret_message("a chat application", conversation_history=history)

    assert result["intent"] == "create_prd"
    # 2 history turns + 1 user message = 3 content entries
    assert len(captured["contents"]) == 3
    # assistant → model role mapping
    assert captured["contents"][1]["role"] == "model"


def test_interpret_history_role_mapping(monkeypatch):
    """Verify that 'assistant' role is mapped to 'model' for Gemini."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "unknown", "idea": None, "reply": "hmm"}
    history = [
        {"role": "assistant", "content": "I can help!"},
    ]

    captured = {}

    def _capture_urlopen(req, **kwargs):
        body = json.loads(req.data.decode())
        captured["contents"] = body["contents"]
        return _mock_urlopen_factory(gemini_result)

    with patch("urllib.request.urlopen", side_effect=_capture_urlopen):
        interpret_message("test", conversation_history=history)

    assert captured["contents"][0]["role"] == "model"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_interpret_http_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    import io
    import urllib.error

    # HTTPError needs a readable body
    body = io.BytesIO(b"rate limited")
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com", 429,
            "Rate limited", {}, body,
        ),
    ):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_interpret_malformed_json_response(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    class FakeResp:
        def read(self):
            return json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": "not valid json!!"}]},
                }],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_interpret_empty_content(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    class FakeResp:
        def read(self):
            return json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": ""}]},
                }],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_interpret_json_in_markdown_fences(monkeypatch):
    """Gemini sometimes wraps JSON in markdown code fences despite instructions."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    class FakeResp:
        def read(self):
            content = '```json\n{"intent":"create_prd","idea":"app","reply":"ok"}\n```'
            return json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": content}]},
                }],
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


def test_interpret_unexpected_response_structure(monkeypatch):
    """Gemini returning a completely unexpected shape should not crash."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    class FakeResp:
        def read(self):
            return json.dumps({"unexpected": True}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = interpret_message("test")

    assert result["intent"] == "unknown"


def test_system_prompt_sent_as_system_instruction(monkeypatch):
    """Verify the system prompt is sent via systemInstruction, not as a content turn."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    gemini_result = {"intent": "greeting", "idea": None, "reply": "hi"}
    captured = {}

    def _capture_urlopen(req, **kwargs):
        body = json.loads(req.data.decode())
        captured["body"] = body
        return _mock_urlopen_factory(gemini_result)

    with patch("urllib.request.urlopen", side_effect=_capture_urlopen):
        interpret_message("hi")

    assert "systemInstruction" in captured["body"]
    assert "responseMimeType" in captured["body"]["generationConfig"]
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"
