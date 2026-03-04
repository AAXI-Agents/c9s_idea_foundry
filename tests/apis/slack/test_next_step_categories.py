"""Tests for _next_step default messages and system prompt."""

from crewai_productfeature_planner.apis.slack._next_step import (
    _DEFAULT_MESSAGES,
    _NEXT_STEP_SYSTEM_PROMPT,
)


class TestNextStepCategories:
    """Verify the create_jira_skeleton category is available."""

    def test_create_jira_skeleton_in_default_messages(self):
        assert "create_jira_skeleton" in _DEFAULT_MESSAGES
        msg = _DEFAULT_MESSAGES["create_jira_skeleton"]
        assert "skeleton" in msg.lower()
        assert "Epics" in msg

    def test_create_jira_skeleton_in_system_prompt(self):
        assert "create_jira_skeleton" in _NEXT_STEP_SYSTEM_PROMPT

    def test_all_categories_have_default_messages(self):
        """Every category in the system prompt should have a fallback message."""
        # Extract categories from prompt
        import re
        m = re.search(r"Categories:\s*(.+)", _NEXT_STEP_SYSTEM_PROMPT)
        assert m, "Categories line not found in system prompt"
        cats_raw = m.group(1).replace("\\", "").replace("\n", " ")
        categories = [c.strip() for c in cats_raw.split("|") if c.strip()]
        # "none" has no message by design
        for cat in categories:
            if cat == "none":
                continue
            assert cat in _DEFAULT_MESSAGES, f"Missing default message for '{cat}'"
