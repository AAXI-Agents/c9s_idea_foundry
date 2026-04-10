"""Tests for the idea options block builder."""

from crewai_productfeature_planner.apis.slack.blocks._idea_options_blocks import (
    idea_options_blocks,
)


def test_idea_options_blocks_returns_blocks():
    """Should return valid Block Kit blocks with 3 options."""
    blocks = idea_options_blocks(
        options=["Enterprise approach", "Consumer approach", "API approach"],
        run_id="test_run_123",
        iteration=3,
        trigger="auto_cycles_complete",
    )
    assert isinstance(blocks, list)
    assert len(blocks) > 0


def test_idea_options_blocks_has_header():
    blocks = idea_options_blocks(
        options=["A", "B", "C"], run_id="r1", iteration=3,
        trigger="auto_cycles_complete",
    )
    headers = [b for b in blocks if b["type"] == "header"]
    assert len(headers) == 1
    assert "compass" in headers[0]["text"]["text"].lower() or "Auto" in headers[0]["text"]["text"]


def test_idea_options_blocks_has_3_option_sections():
    blocks = idea_options_blocks(
        options=["A", "B", "C"], run_id="r1", iteration=3,
        trigger="auto_cycles_complete",
    )
    sections = [
        b for b in blocks
        if b["type"] == "section" and "Option" in b["text"]["text"]
    ]
    assert len(sections) == 3


def test_idea_options_blocks_has_action_buttons():
    blocks = idea_options_blocks(
        options=["A", "B", "C"], run_id="r1", iteration=3,
        trigger="low_confidence",
    )
    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    elements = actions[0]["elements"]
    assert len(elements) == 3
    assert elements[0]["action_id"] == "idea_option_1"
    assert elements[1]["action_id"] == "idea_option_2"
    assert elements[2]["action_id"] == "idea_option_3"


def test_idea_options_blocks_button_values():
    blocks = idea_options_blocks(
        options=["A", "B", "C"], run_id="run42", iteration=5,
        trigger="direction_change",
    )
    actions = [b for b in blocks if b["type"] == "actions"]
    for elem in actions[0]["elements"]:
        assert elem["value"] == "run42"


def test_idea_options_blocks_primary_style_on_first():
    blocks = idea_options_blocks(
        options=["A", "B", "C"], run_id="r1", iteration=3,
        trigger="auto_cycles_complete",
    )
    actions = [b for b in blocks if b["type"] == "actions"]
    assert actions[0]["elements"][0].get("style") == "primary"
    assert "style" not in actions[0]["elements"][1]


def test_idea_options_blocks_truncates_long_option():
    long_text = "x" * 5000
    blocks = idea_options_blocks(
        options=[long_text, "B", "C"], run_id="r1", iteration=3,
        trigger="auto_cycles_complete",
    )
    sections = [
        b for b in blocks
        if b["type"] == "section" and "Option 1" in b["text"]["text"]
    ]
    # Section text should be truncated below 3000 chars
    assert len(sections[0]["text"]["text"]) < 3100
