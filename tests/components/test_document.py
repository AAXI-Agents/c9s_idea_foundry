"""Tests for crewai_productfeature_planner.components.document."""

import json

import pytest

from crewai_productfeature_planner.components.document import (
    assemble_prd_from_doc,
    sanitize_section_content,
    strip_iteration_tags,
)


# ── strip_iteration_tags ──────────────────────────────────────


class TestStripIterationTags:
    """Tests for strip_iteration_tags()."""

    @pytest.mark.parametrize(
        "text, expected",
        [
            # Basic cases
            ("Heading (Iteration 3)", "Heading"),
            ("Heading (Iteration 1)", "Heading"),
            ("Heading (Iteration 12)", "Heading"),
            # Case-insensitive
            ("Heading (iteration 3)", "Heading"),
            ("Heading (ITERATION 3)", "Heading"),
            # Multiple occurrences
            (
                "Title (Iteration 2) and body (Iteration 3)",
                "Title and body",
            ),
            # Mid-sentence
            (
                "### The Expert Review: Strategic Probing (Iteration 3)",
                "### The Expert Review: Strategic Probing",
            ),
            # No match — text unchanged
            ("Plain heading", "Plain heading"),
            ("", ""),
            ("Iteration 3 in text", "Iteration 3 in text"),
            # Multiple spaces before parenthesis
            ("Heading  (Iteration 5)", "Heading"),
        ],
    )
    def test_strips_iteration_tags(self, text: str, expected: str) -> None:
        assert strip_iteration_tags(text) == expected


# ── assemble_prd_from_doc — iteration stripping ──────────────


class TestAssemblePrdFromDocIterationStripping:
    """Verify that assembled PRD content has iteration markers removed."""

    def test_strips_iteration_from_executive_summary(self) -> None:
        doc = {
            "executive_summary": [
                {
                    "content": "### Strategic Probing (Iteration 3)\n\nDetails here.",
                    "iteration": 3,
                },
            ],
        }
        result = assemble_prd_from_doc(doc)
        assert "(Iteration 3)" not in result
        assert "### Strategic Probing" in result
        assert "Details here." in result

    def test_strips_iteration_from_section_content(self) -> None:
        doc = {
            "section": {
                "problem_statement": [
                    {
                        "content": "Problem overview (Iteration 2) is clear.",
                        "iteration": 2,
                    },
                ],
            },
        }
        result = assemble_prd_from_doc(doc)
        assert "(Iteration 2)" not in result
        assert "Problem overview is clear." in result


# ── sanitize_section_content ──────────────────────────────────


def _make_doc_dump(
    exec_content: str = "Clean executive summary.",
    section_content: str = "Clean problem statement.",
    section_key: str = "problem_statement",
) -> str:
    """Build a fake JSON document dump resembling a workingIdeas doc."""
    doc = {
        "run_id": "test-run",
        "idea": "Test idea",
        "finalized_idea": "Finalized test idea",
        "executive_summary": [
            {"content": exec_content, "iteration": 1},
        ],
        "section": {
            section_key: [
                {"content": section_content, "iteration": 1},
            ],
        },
        "status": "completed",
    }
    return json.dumps(doc, indent=2)


class TestSanitizeSectionContent:
    """Tests for sanitize_section_content()."""

    def test_passthrough_plain_markdown(self) -> None:
        """Non-JSON content should pass through with only iteration-tag stripping."""
        content = "## Overview (Iteration 3)\n\nDetails here."
        result = sanitize_section_content(content, "problem_statement")
        assert result == "## Overview\n\nDetails here."

    def test_passthrough_empty(self) -> None:
        assert sanitize_section_content("", "x") == ""

    def test_strips_code_fenced_json_exec_summary(self) -> None:
        """Code-fenced JSON dump should extract exec summary content."""
        raw_json = _make_doc_dump(exec_content="The real summary.")
        content = f"```json\n{raw_json}\n```"
        result = sanitize_section_content(content, "executive_summary")
        assert result == "The real summary."

    def test_strips_bare_json_exec_summary(self) -> None:
        """Bare JSON dump (no code fence) should also be extracted."""
        content = _make_doc_dump(exec_content="Bare summary.")
        result = sanitize_section_content(content, "executive_summary")
        assert result == "Bare summary."

    def test_strips_json_dump_for_regular_section(self) -> None:
        """JSON dump should extract a regular section's content."""
        content = _make_doc_dump(section_content="The problem is clear.")
        result = sanitize_section_content(content, "problem_statement")
        assert result == "The problem is clear."

    def test_fallback_finalized_idea_for_exec_summary(self) -> None:
        """When exec summary array is empty, fall back to finalized_idea."""
        doc = {
            "run_id": "r",
            "executive_summary": [],
            "section": {},
            "finalized_idea": "Fallback idea text.",
        }
        content = json.dumps(doc)
        result = sanitize_section_content(content, "executive_summary")
        assert result == "Fallback idea text."

    def test_non_dump_json_passthrough(self) -> None:
        """JSON that is NOT a document dump should pass through."""
        content = '{"key": "value"}'
        result = sanitize_section_content(content, "x")
        assert result == content

    def test_strips_iteration_tags_from_extracted_content(self) -> None:
        """Extracted content should also have iteration tags removed."""
        raw_json = _make_doc_dump(
            exec_content="Summary (Iteration 6) text."
        )
        content = f"```json\n{raw_json}\n```"
        result = sanitize_section_content(content, "executive_summary")
        assert "(Iteration 6)" not in result
        assert "Summary text." in result


class TestAssemblePrdSanitizesJsonDumps:
    """Verify that assemble_prd_from_doc strips JSON dumps from content."""

    def test_exec_summary_json_dump_is_sanitized(self) -> None:
        """If exec summary content is a JSON dump, the real text is extracted."""
        inner_json = _make_doc_dump(exec_content="Actual summary.")
        doc = {
            "executive_summary": [
                {"content": f"```json\n{inner_json}\n```", "iteration": 1},
            ],
        }
        result = assemble_prd_from_doc(doc)
        assert "Actual summary." in result
        assert "run_id" not in result
        assert "```json" not in result

    def test_section_json_dump_is_sanitized(self) -> None:
        """If a regular section's content is a JSON dump, the text is extracted."""
        inner_json = _make_doc_dump(
            section_content="Real problem.",
            section_key="problem_statement",
        )
        doc = {
            "section": {
                "problem_statement": [
                    {"content": inner_json, "iteration": 1},
                ],
            },
        }
        result = assemble_prd_from_doc(doc)
        assert "Real problem." in result
        assert '"run_id"' not in result
