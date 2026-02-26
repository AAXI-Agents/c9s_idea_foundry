"""Tests for crewai_productfeature_planner.components.document."""

import pytest

from crewai_productfeature_planner.components.document import (
    assemble_prd_from_doc,
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
