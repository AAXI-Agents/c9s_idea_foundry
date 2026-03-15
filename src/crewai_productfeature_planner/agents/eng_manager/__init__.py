"""Eng Manager / Tech Lead reviewer agent — gstack plan-eng-review role.

Takes the product vision and locks in the technical architecture,
data flow, edge cases, test coverage, and engineering plan.
"""

from crewai_productfeature_planner.agents.eng_manager.agent import (
    create_eng_manager,
    get_task_configs,
)

get_eng_task_configs = get_task_configs

__all__ = [
    "create_eng_manager",
    "get_task_configs",
    "get_eng_task_configs",
]
