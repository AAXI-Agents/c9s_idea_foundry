"""Post-completion delivery action Block Kit builders.

.. deprecated::
    Confluence/Jira publishing removed from Slack in v0.71.0.
    All functions return empty lists for backward compatibility.
"""

from __future__ import annotations


def delivery_next_step_blocks(
    run_id: str,
    *,
    show_publish: bool = True,
    show_jira: bool = True,
) -> list[dict]:
    """No-op — Confluence/Jira publishing removed from Slack."""
    return []


def jira_only_blocks(run_id: str) -> list[dict]:
    """No-op — Jira creation removed from Slack."""
    return []


def publish_only_blocks(run_id: str) -> list[dict]:
    """No-op — Confluence publishing removed from Slack."""
    return []
