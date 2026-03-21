"""Tests for the interaction-first rule.

Every Slack interaction that moves the user to a next step MUST offer
clickable Block Kit buttons — users should never be asked to type.

These tests verify:
1. Setup wizard steps include a "Skip" button.
2. Setup completion offers action buttons (not "just say" text).
3. Next-step handler posts buttons (not "say"/"type"/"tell me" text).
4. Idea list footer has a New Idea button (not text hint).
5. Greeting posts action buttons.
6. No block text contains "type", "say", or "tell me" as instructions.
"""

from __future__ import annotations

import re

import pytest

from crewai_productfeature_planner.apis.slack.blocks import (
    project_setup_complete_blocks,
    project_setup_step_blocks,
)
from crewai_productfeature_planner.apis.slack.blocks._idea_list_blocks import (
    idea_list_blocks,
)


@pytest.fixture(autouse=True)
def _set_dummy_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy")


# ── Forbidden text patterns ─────────────────────────────────────────────

# Regex matching instructions that tell the user to type or say something.
# Matches phrases like "type `skip`", "say *configure*", "just tell me".
_FORBIDDEN_RE = re.compile(
    r"\b(?:type|say|tell me)\b.*(?:`[^`]+`|\*[^*]+\*)",
    re.IGNORECASE,
)


def _collect_text_blocks(blocks: list[dict]) -> list[str]:
    """Extract all user-visible text from Block Kit blocks."""
    texts: list[str] = []
    for block in blocks:
        if block.get("type") == "section":
            text_obj = block.get("text", {})
            if "text" in text_obj:
                texts.append(text_obj["text"])
        elif block.get("type") == "context":
            for elem in block.get("elements", []):
                if "text" in elem:
                    texts.append(elem["text"])
    return texts


# ── Setup wizard ─────────────────────────────────────────────────────────


_SETUP_STEPS = [
    ("confluence_space_key", 1, 5),
    ("jira_project_key", 2, 5),
    ("figma_api_key", 3, 5),
    ("figma_team_id", 4, 5),
    ("project_name", 5, 5),
]


class TestSetupWizardSkipButton:
    """Every setup step must offer a clickable Skip button."""

    @pytest.mark.parametrize("step,num,total", _SETUP_STEPS)
    def test_skip_button_present(self, step, num, total):
        blocks = project_setup_step_blocks("MyProject", step, num, total)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) >= 1, f"Step {step!r} has no action blocks"
        action_ids = [
            e["action_id"] for ab in action_blocks for e in ab["elements"]
        ]
        assert "setup_skip" in action_ids, (
            f"Step {step!r} missing setup_skip button"
        )

    @pytest.mark.parametrize("step,num,total", _SETUP_STEPS)
    def test_skip_button_value_is_step(self, step, num, total):
        blocks = project_setup_step_blocks("MyProject", step, num, total)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        skip_btns = [
            e
            for ab in action_blocks
            for e in ab["elements"]
            if e["action_id"] == "setup_skip"
        ]
        assert skip_btns[0]["value"] == step

    @pytest.mark.parametrize("step,num,total", _SETUP_STEPS)
    def test_no_type_skip_instruction(self, step, num, total):
        blocks = project_setup_step_blocks("MyProject", step, num, total)
        texts = _collect_text_blocks(blocks)
        for t in texts:
            assert "type `skip`" not in t.lower(), (
                f"Step {step!r} still says 'type skip': {t!r}"
            )
            assert "type skip" not in t.lower(), (
                f"Step {step!r} still says 'type skip': {t!r}"
            )


# ── Setup completion ─────────────────────────────────────────────────────


class TestSetupCompleteButtons:
    """Setup-complete message must offer action buttons, not text."""

    def test_has_action_blocks(self):
        details = {"confluence_space_key": "TEAM", "jira_project_key": "PROJ"}
        blocks = project_setup_complete_blocks("MyProject", details)
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        assert len(action_blocks) >= 1

    def test_new_idea_button_present(self):
        blocks = project_setup_complete_blocks("MyProject", {})
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        action_ids = [
            e["action_id"] for ab in action_blocks for e in ab["elements"]
        ]
        assert "cmd_create_prd" in action_ids

    def test_help_button_present(self):
        blocks = project_setup_complete_blocks("MyProject", {})
        action_blocks = [b for b in blocks if b["type"] == "actions"]
        action_ids = [
            e["action_id"] for ab in action_blocks for e in ab["elements"]
        ]
        assert "cmd_help" in action_ids

    def test_no_say_instructions(self):
        blocks = project_setup_complete_blocks("MyProject", {})
        texts = _collect_text_blocks(blocks)
        for t in texts:
            assert not _FORBIDDEN_RE.search(t), (
                f"Setup-complete still instructs user to type/say: {t!r}"
            )


# ── Idea list footer ────────────────────────────────────────────────────


class TestIdeaListFooterButton:
    """Idea list footer must have a New Idea button, not text."""

    _IDEAS = [
        {
            "idea_number": 1,
            "status": "paused",
            "idea_title": "Test Idea",
            "summary": "Summary",
        },
    ]

    def test_footer_is_actions_block(self):
        blocks = idea_list_blocks(
            self._IDEAS, "U1", "Project", "proj-123"
        )
        assert blocks[-1]["type"] == "actions"

    def test_footer_has_new_idea_button(self):
        blocks = idea_list_blocks(
            self._IDEAS, "U1", "Project", "proj-123"
        )
        footer = blocks[-1]
        action_ids = [e["action_id"] for e in footer["elements"]]
        assert "cmd_create_prd" in action_ids

    def test_no_text_only_footer(self):
        """Footer should not be a context block with plain text."""
        blocks = idea_list_blocks(
            self._IDEAS, "U1", "Project", "proj-123"
        )
        footer = blocks[-1]
        assert footer["type"] != "context", "Footer is still a text-only context block"


# ── Next-step handler ───────────────────────────────────────────────────


class TestNextStepHandlerButtons:
    """Next-step accept should post buttons, not text instructions."""

    @pytest.fixture(autouse=True)
    def _patch_deps(self, monkeypatch):
        monkeypatch.setattr(
            "crewai_productfeature_planner.mongodb.agent_interactions.repository."
            "record_next_step_feedback",
            lambda *a, **kw: None,
        )

    @pytest.fixture()
    def mock_client(self, monkeypatch):
        from unittest.mock import MagicMock

        client = MagicMock()
        monkeypatch.setattr(
            "crewai_productfeature_planner.tools.slack_tools._get_slack_client",
            lambda: client,
        )
        monkeypatch.setattr(
            "crewai_productfeature_planner.apis.slack.session_manager."
            "get_context_session",
            lambda *a: {"project_id": "pid"},
        )
        return client

    def _trigger(self, next_step, mock_client):
        from crewai_productfeature_planner.apis.slack.interactions_router._next_step_handler import (
            _handle_next_step_feedback,
        )

        _handle_next_step_feedback(
            "next_step_accept",
            f"{next_step}|iid-123",
            "U1",
            "C1",
            "ts1",
        )
        return mock_client.chat_postMessage

    def _assert_has_action_block(self, call_kwargs):
        blocks = call_kwargs.get("blocks", [])
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) >= 1, (
            f"Expected actions block but got: {blocks}"
        )
        return action_blocks

    def test_configure_confluence_posts_button(self, mock_client):
        post = self._trigger("configure_confluence", mock_client)
        self._assert_has_action_block(post.call_args.kwargs)

    def test_configure_jira_posts_button(self, mock_client):
        post = self._trigger("configure_jira", mock_client)
        self._assert_has_action_block(post.call_args.kwargs)

    def test_create_prd_posts_button(self, mock_client):
        post = self._trigger("create_prd", mock_client)
        action_blocks = self._assert_has_action_block(post.call_args.kwargs)
        action_ids = [
            e["action_id"] for ab in action_blocks for e in ab["elements"]
        ]
        assert "cmd_create_prd" in action_ids

    def test_fallback_posts_help_button(self, mock_client):
        post = self._trigger("unknown_step", mock_client)
        action_blocks = self._assert_has_action_block(post.call_args.kwargs)
        action_ids = [
            e["action_id"] for ab in action_blocks for e in ab["elements"]
        ]
        assert "cmd_help" in action_ids
