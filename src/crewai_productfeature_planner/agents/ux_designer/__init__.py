"""UX Designer agent — generates Figma Make prompts from executive summaries.

Transforms the executive product summary into a structured, Figma Make-ready
design prompt and submits it to generate a clickable prototype.
"""

from crewai_productfeature_planner.agents.ux_designer.agent import (
    create_ux_designer,
    get_task_configs,
)

get_ux_task_configs = get_task_configs

__all__ = [
    "create_ux_designer",
    "get_task_configs",
    "get_ux_task_configs",
]
