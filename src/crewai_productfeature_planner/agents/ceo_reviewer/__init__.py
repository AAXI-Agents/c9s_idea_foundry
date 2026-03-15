"""CEO / Founder reviewer agent — gstack plan-ceo-review role.

Applies founder-mode thinking to product plans: rethinks the problem,
finds the 10-star product hiding inside the request, and pressure-tests
whether the right thing is being built.
"""

from crewai_productfeature_planner.agents.ceo_reviewer.agent import (
    create_ceo_reviewer,
    get_task_configs,
)

get_ceo_task_configs = get_task_configs

__all__ = [
    "create_ceo_reviewer",
    "get_task_configs",
    "get_ceo_task_configs",
]
