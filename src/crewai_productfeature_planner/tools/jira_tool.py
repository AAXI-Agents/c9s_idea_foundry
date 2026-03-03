"""Backward-compatibility shim — re-exports everything from ``tools.jira``.

All names that were previously defined here are now in the ``jira/``
sub-package.  This module re-exports them so that every existing
``from crewai_productfeature_planner.tools.jira_tool import …`` and
every ``@patch("…tools.jira_tool.…")`` continues to work without
changes.
"""

from crewai_productfeature_planner.tools.jira import *  # noqa: F401,F403
from crewai_productfeature_planner.tools.jira import __all__  # noqa: F401
