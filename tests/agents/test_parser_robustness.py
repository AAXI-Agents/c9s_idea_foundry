"""Deterministic parser robustness tests — verifies code-level field normalization.

These tests verify the parser handles ALL known LLM output drift WITHOUT
relying on prompt engineering. Each test represents a real-world failure
mode observed in production.
"""

import json

import pytest

from crewai_productfeature_planner.agents.ideation.agent import (
    _extract_json_object,
    _normalize_response_fields,
    _parse_structured_from_text,
)


# ── Real-world LLM output patterns ───────────────────────────


class TestParserHandlesAllDriftPatterns:
    """Every observed LLM drift pattern MUST parse successfully."""

    def test_british_acknowledgement_with_option_field(self):
        """Exact pattern from production: 'acknowledgement' + 'option'."""
        raw = json.dumps({
            "acknowledgement": "Excellent progress!",
            "questions": [
                {
                    "question": f"Q{i}?",
                    "recommendations": [
                        {"option": f"Opt {j}", "pro": "P", "con": "C", "complexity": "Medium"}
                        for j in range(3)
                    ],
                    "recommended_index": 0,
                    "recommended_reason": "Best.",
                }
                for i in range(3)
            ],
            "agent_insight": "Good idea.",
        })
        result = _parse_structured_from_text(raw)
        assert result is not None
        assert result.acknowledgment == "Excellent progress!"
        assert result.questions[0].recommendations[0].label == "Opt 0"
        assert result.questions[0].id == 1
        assert result.questions[0].context == "Best."

    def test_direction_field_no_id_no_context(self):
        """Pattern: 'direction' instead of 'label', missing 'id' and 'context'."""
        raw = json.dumps({
            "acknowledgment": "Great!",
            "questions": [
                {
                    "question": "What vertical?",
                    "recommendations": [
                        {"direction": "Cosmetics", "pro": "P", "con": "C", "complexity": "High"},
                        {"direction": "Fashion", "pro": "P", "con": "C", "complexity": "Low"},
                        {"direction": "Tech", "pro": "P", "con": "C", "complexity": "Medium"},
                    ],
                    "recommended_index": 1,
                    "recommended_reason": "Fastest traction.",
                },
                {
                    "question": "Revenue model?",
                    "recommendations": [
                        {"direction": "Commission", "pro": "P", "con": "C", "complexity": "Medium"},
                        {"direction": "Subscription", "pro": "P", "con": "C", "complexity": "High"},
                        {"direction": "Ads", "pro": "P", "con": "C", "complexity": "Low"},
                    ],
                    "recommended_index": 0,
                    "recommended_reason": "Aligns incentives.",
                },
                {
                    "question": "Distribution?",
                    "recommendations": [
                        {"direction": "Organic", "pro": "P", "con": "C", "complexity": "Low"},
                        {"direction": "Paid", "pro": "P", "con": "C", "complexity": "Medium"},
                        {"direction": "Partnerships", "pro": "P", "con": "C", "complexity": "High"},
                    ],
                    "recommended_index": 2,
                    "recommended_reason": "Scalable.",
                },
            ],
            "agent_insight": "Strong potential.",
        })
        result = _parse_structured_from_text(raw)
        assert result is not None
        assert result.questions[0].recommendations[0].label == "Cosmetics"
        assert result.questions[0].id == 1
        assert result.questions[1].id == 2
        assert result.questions[2].id == 3

    def test_description_field(self):
        """Pattern: 'description' instead of 'label'."""
        raw = json.dumps({
            "acknowledgment": "Noted.",
            "questions": [
                {
                    "id": 1,
                    "question": "Who?",
                    "context": "Important.",
                    "recommendations": [
                        {"description": "SMBs", "pro": "P", "con": "C", "complexity": "Low"},
                        {"description": "Enterprise", "pro": "P", "con": "C", "complexity": "High"},
                        {"description": "Prosumers", "pro": "P", "con": "C", "complexity": "Medium"},
                    ],
                    "recommended_index": 0,
                    "recommended_reason": "Lowest friction.",
                },
            ] * 3,
            "agent_insight": "Focused.",
        })
        result = _parse_structured_from_text(raw)
        assert result is not None
        assert result.questions[0].recommendations[0].label == "SMBs"

    def test_preamble_text_before_json(self):
        """LLM outputs conversational text then JSON (no fences)."""
        payload = json.dumps({
            "acknowledgment": "Good.",
            "questions": [
                {
                    "id": i,
                    "question": f"Q{i}?",
                    "context": "C",
                    "recommendations": [
                        {"label": f"L{j}", "pro": "P", "con": "C", "complexity": "Medium"}
                        for j in range(3)
                    ],
                }
                for i in range(1, 4)
            ],
            "agent_insight": "Nice.",
        })
        raw = f"Welcome! Here are my thoughts:\n\n{payload}\n\nLooking forward!"
        result = _parse_structured_from_text(raw)
        assert result is not None
        assert result.acknowledgment == "Good."

    def test_code_fenced_json_with_preamble(self):
        """LLM outputs text then ```json ... ```."""
        payload = json.dumps({
            "acknowledgment": "Understood.",
            "questions": [
                {
                    "id": i,
                    "question": f"Q{i}?",
                    "context": "C",
                    "recommendations": [
                        {"label": f"L{j}", "pro": "P", "con": "C", "complexity": "Low"}
                        for j in range(3)
                    ],
                }
                for i in range(1, 4)
            ],
            "agent_insight": "Clear.",
        })
        raw = f"Let me analyze this:\n\n```json\n{payload}\n```\n\nHope that helps!"
        result = _parse_structured_from_text(raw)
        assert result is not None

    def test_complexity_normalization(self):
        """LLM outputs various complexity spellings."""
        raw = json.dumps({
            "acknowledgment": "OK.",
            "questions": [
                {
                    "id": 1,
                    "question": "Q?",
                    "context": "C",
                    "recommendations": [
                        {"label": "A", "pro": "P", "con": "C", "complexity": "low"},
                        {"label": "B", "pro": "P", "con": "C", "complexity": "HIGH"},
                        {"label": "C", "pro": "P", "con": "C", "complexity": "medium"},
                    ],
                },
            ] * 3,
            "agent_insight": "I.",
        })
        result = _parse_structured_from_text(raw)
        assert result is not None
        assert result.questions[0].recommendations[0].complexity == "Low"
        assert result.questions[0].recommendations[1].complexity == "High"
        assert result.questions[0].recommendations[2].complexity == "Medium"

    def test_mixed_drift_all_at_once(self):
        """Worst case: British spelling + option + missing id + missing context + preamble."""
        payload = json.dumps({
            "acknowledgement": "Amazing concept!",
            "questions": [
                {
                    "question": "Target market?",
                    "recommendations": [
                        {"option": "Vietnam-first", "pro": "Focus", "con": "Small", "complexity": "low"},
                        {"option": "SEA-wide", "pro": "Scale", "con": "Complex", "complexity": "high"},
                        {"option": "Global", "pro": "Massive", "con": "Impossible", "complexity": "High"},
                    ],
                    "recommended_index": 0,
                    "recommended_reason": "Start focused.",
                },
                {
                    "question": "Revenue?",
                    "recommendations": [
                        {"option": "Commission", "pro": "Aligned", "con": "Slow", "complexity": "Medium"},
                        {"option": "SaaS", "pro": "Recurring", "con": "Barrier", "complexity": "medium"},
                        {"option": "Ads", "pro": "Free", "con": "Intrusive", "complexity": "LOW"},
                    ],
                    "recommended_index": 0,
                    "recommended_reason": "Best alignment.",
                },
                {
                    "question": "Tech stack?",
                    "recommendations": [
                        {"option": "React + Node", "pro": "Popular", "con": "Fragmented", "complexity": "Medium"},
                        {"option": "Flutter + Go", "pro": "Fast", "con": "Hiring", "complexity": "High"},
                        {"option": "Next.js mono", "pro": "Simple", "con": "Limits", "complexity": "Low"},
                    ],
                    "recommended_index": 2,
                    "recommended_reason": "Fastest to MVP.",
                },
            ],
            "agent_insight": "Exciting opportunity!",
        })
        raw = f"Great question! Here's my analysis:\n\n```json\n{payload}\n```"
        result = _parse_structured_from_text(raw)
        assert result is not None
        assert result.acknowledgment == "Amazing concept!"
        assert len(result.questions) == 3
        assert result.questions[0].id == 1
        assert result.questions[0].context == "Start focused."
        assert result.questions[0].recommendations[0].label == "Vietnam-first"
        assert result.questions[0].recommendations[0].complexity == "Low"
        assert result.questions[1].recommendations[2].complexity == "Low"
        assert result.questions[2].recommendations[1].complexity == "High"

    def test_plain_invalid_text_returns_none(self):
        """Non-JSON text must return None, not crash."""
        assert _parse_structured_from_text("Hello, world!") is None
        assert _parse_structured_from_text("") is None
        assert _parse_structured_from_text("{}") is None
        assert _parse_structured_from_text('{"foo": "bar"}') is None


# ── JSON extraction tests ─────────────────────────────────────


class TestExtractJsonObject:
    def test_clean_json(self):
        assert _extract_json_object('{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self):
        raw = '```json\n{"a": 1}\n```'
        assert _extract_json_object(raw) == {"a": 1}

    def test_json_with_preamble(self):
        raw = 'Here it is:\n{"a": 1}\nDone!'
        assert _extract_json_object(raw) == {"a": 1}

    def test_no_json_returns_none(self):
        assert _extract_json_object("just text") is None

    def test_nested_braces(self):
        raw = '{"a": {"b": 1}, "c": [2, 3]}'
        result = _extract_json_object(raw)
        assert result == {"a": {"b": 1}, "c": [2, 3]}


# ── Normalization unit tests ──────────────────────────────────


class TestNormalizeResponseFields:
    def test_acknowledgement_british(self):
        data = {"acknowledgement": "Hi", "questions": []}
        result = _normalize_response_fields(data)
        assert result["acknowledgment"] == "Hi"
        assert "acknowledgement" not in result

    def test_preserves_correct_acknowledgment(self):
        data = {"acknowledgment": "Hi", "questions": []}
        result = _normalize_response_fields(data)
        assert result["acknowledgment"] == "Hi"

    def test_auto_assigns_id(self):
        data = {"acknowledgment": "Hi", "questions": [
            {"question": "Q?", "context": "C", "recommendations": []},
        ]}
        result = _normalize_response_fields(data)
        assert result["questions"][0]["id"] == 1

    def test_coerces_string_id(self):
        data = {"acknowledgment": "Hi", "questions": [
            {"id": "3", "question": "Q?", "context": "C", "recommendations": []},
        ]}
        result = _normalize_response_fields(data)
        assert result["questions"][0]["id"] == 3

    def test_normalizes_label_from_all_aliases(self):
        aliases = ["direction", "description", "option", "title", "name",
                   "answer", "suggestion", "approach", "strategy"]
        for alias in aliases:
            rec = {alias: "test_value", "pro": "P", "con": "C", "complexity": "Medium"}
            data = {"acknowledgment": "Hi", "questions": [
                {"id": 1, "question": "Q?", "context": "C", "recommendations": [rec]},
            ]}
            result = _normalize_response_fields(data)
            assert result["questions"][0]["recommendations"][0]["label"] == "test_value", \
                f"Failed to normalize alias '{alias}' → 'label'"

    def test_complexity_normalization_variants(self):
        cases = {
            "low": "Low", "LOW": "Low", "l": "Low", "simple": "Low",
            "medium": "Medium", "MEDIUM": "Medium", "moderate": "Medium",
            "high": "High", "HIGH": "High", "h": "High", "complex": "High",
            "very high": "High", "difficult": "High",
        }
        for input_val, expected in cases.items():
            rec = {"label": "X", "pro": "P", "con": "C", "complexity": input_val}
            data = {"acknowledgment": "Hi", "questions": [
                {"id": 1, "question": "Q?", "context": "C", "recommendations": [rec]},
            ]}
            result = _normalize_response_fields(data)
            assert result["questions"][0]["recommendations"][0]["complexity"] == expected, \
                f"complexity '{input_val}' should map to '{expected}'"

    def test_defaults_missing_pro_con(self):
        rec = {"label": "X", "complexity": "Medium"}
        data = {"acknowledgment": "Hi", "questions": [
            {"id": 1, "question": "Q?", "context": "C", "recommendations": [rec]},
        ]}
        result = _normalize_response_fields(data)
        assert result["questions"][0]["recommendations"][0]["pro"] == ""
        assert result["questions"][0]["recommendations"][0]["con"] == ""
