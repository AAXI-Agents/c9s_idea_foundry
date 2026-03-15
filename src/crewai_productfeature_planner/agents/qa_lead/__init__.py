"""QA Lead agent — gstack qa role.

Systematic QA testing with structured reports, health scores,
screenshots, and regression tracking.
"""

from crewai_productfeature_planner.agents.qa_lead.agent import (
    create_qa_lead,
    get_task_configs,
)

__all__ = [
    "create_qa_lead",
    "get_task_configs",
]
