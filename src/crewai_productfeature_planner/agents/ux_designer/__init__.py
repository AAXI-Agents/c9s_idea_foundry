"""UX Designer agents — generates design specifications and Figma Make prompts.

Agents:
- **UX Designer**: Converts executive summaries into Figma Make prompts.
- **Design Partner**: Collaborates on initial design draft (gstack methodology).
- **Senior Designer**: Reviews and finalizes design via 7-pass review.
"""

from crewai_productfeature_planner.agents.ux_designer.agent import (
    create_design_partner,
    create_senior_designer,
    create_ux_designer,
    get_task_configs,
    get_ux_design_flow_task_configs,
)

get_ux_task_configs = get_task_configs

__all__ = [
    "create_design_partner",
    "create_senior_designer",
    "create_ux_designer",
    "get_task_configs",
    "get_ux_design_flow_task_configs",
    "get_ux_task_configs",
]
