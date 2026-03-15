"""Staff Engineer / Paranoid Reviewer agent — gstack review role.

Performs structural audit to find bugs that pass CI but blow up in
production. Not a style nitpick pass.
"""

from crewai_productfeature_planner.agents.staff_engineer.agent import (
    create_staff_engineer,
    get_task_configs,
)

__all__ = [
    "create_staff_engineer",
    "get_task_configs",
]
