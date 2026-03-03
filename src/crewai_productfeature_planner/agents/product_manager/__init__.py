"""Product Manager agent module.

Provides factory functions for the Product Manager agent:

- ``create_product_manager(provider)`` — full PM agent with tools,
  research-tier LLM, and knowledge sources.  Used for drafting and
  refining PRD content.
- ``create_product_manager_critic(project_id)`` — lightweight critic
  agent with no tools, basic-tier LLM, and cached knowledge sources.
  Used for evaluating/critiquing PRD sections.
"""

from crewai_productfeature_planner.agents.product_manager.agent import (
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    create_product_manager,
    create_product_manager_critic,
    get_task_configs,
)

__all__ = [
    "PROVIDER_GEMINI",
    "PROVIDER_OPENAI",
    "create_product_manager",
    "create_product_manager_critic",
    "get_task_configs",
]
