"""QA Engineer agent — gstack browse role.

Creates counter-tickets to development sub-tasks for edge case
and security testing beyond unit tests.
"""

from crewai_productfeature_planner.agents.qa_engineer.agent import (
    create_qa_engineer,
    get_task_configs,
)

__all__ = [
    "create_qa_engineer",
    "get_task_configs",
]
