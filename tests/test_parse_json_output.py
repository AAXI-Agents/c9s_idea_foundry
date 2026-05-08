"""Tests for the improved _parse_json_output function."""

from __future__ import annotations

import pytest

from crewai_productfeature_planner.services.knowledge_aggregator import _parse_json_output


class TestParseJsonOutput:
    def test_plain_json(self):
        raw = '{"summary": "test", "key_bullets": ["a"], "topics": ["b"], "confidence": 0.9}'
        result = _parse_json_output(raw)
        assert result == {"summary": "test", "key_bullets": ["a"], "topics": ["b"], "confidence": 0.9}

    def test_json_with_whitespace(self):
        raw = '  \n  {"summary": "test"}\n  '
        result = _parse_json_output(raw)
        assert result == {"summary": "test"}

    def test_markdown_fenced_json(self):
        raw = '```json\n{"summary": "test"}\n```'
        result = _parse_json_output(raw)
        assert result == {"summary": "test"}

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"summary": "test"}\n```'
        result = _parse_json_output(raw)
        assert result == {"summary": "test"}

    def test_preamble_then_json(self):
        raw = 'Here is the review:\n{"summary": "test", "key_bullets": []}'
        result = _parse_json_output(raw)
        assert result == {"summary": "test", "key_bullets": []}

    def test_preamble_then_fenced_json(self):
        raw = 'Here is the review:\n```json\n{"summary": "test"}\n```\nDone.'
        result = _parse_json_output(raw)
        assert result == {"summary": "test"}

    def test_json_with_postamble(self):
        raw = '{"summary": "test"}\n\nI hope this helps!'
        result = _parse_json_output(raw)
        assert result == {"summary": "test"}

    def test_multiline_json(self):
        raw = '{\n  "summary": "A document about testing",\n  "key_bullets": ["point 1", "point 2"],\n  "topics": ["testing"],\n  "confidence": 0.85\n}'
        result = _parse_json_output(raw)
        assert result["summary"] == "A document about testing"
        assert result["confidence"] == 0.85

    def test_no_json_returns_none(self):
        raw = "I cannot parse this document."
        result = _parse_json_output(raw)
        assert result is None

    def test_invalid_json_returns_none(self):
        raw = "{invalid json here}"
        result = _parse_json_output(raw)
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_json_output("")
        assert result is None

    def test_nested_braces_in_json(self):
        raw = '{"summary": "test", "contradictions": [{"claim_a": "x", "claim_b": "y"}]}'
        result = _parse_json_output(raw)
        assert result["contradictions"][0]["claim_a"] == "x"

    def test_json_with_newlines_inside(self):
        raw = 'Review result:\n```\n{\n"summary": "Line1\\nLine2",\n"key_bullets": ["a"]\n}\n```'
        result = _parse_json_output(raw)
        assert result is not None
        assert result["summary"] == "Line1\nLine2"
