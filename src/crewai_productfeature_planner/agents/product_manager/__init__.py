"""Product Manager agent module.

Provides factory functions for the Product Manager agent:

- ``create_product_manager(provider)`` — full PM agent with tools,
  research-tier LLM, and knowledge sources.  Used for drafting and
  refining PRD content.
- ``create_product_manager_critic(project_id)`` — lightweight critic
  agent with no tools, basic-tier LLM, and cached knowledge sources.
  Used for evaluating/critiquing PRD sections.
- ``create_requirements_breakdown_agent(project_id)`` — PM in architect
  mode for decomposing ideas into implementation-ready requirements.
- ``breakdown_requirements(refined_idea, ...)`` — iterative requirements
  breakdown runner.
"""

from crewai_productfeature_planner.agents.product_manager.agent import (
    DEFAULT_REQUIREMENTS_MAX_ITERATIONS,
    DEFAULT_REQUIREMENTS_MIN_ITERATIONS,
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    breakdown_requirements,
    create_product_manager,
    create_product_manager_critic,
    create_requirements_breakdown_agent,
    get_task_configs,
)

__all__ = [
    "DEFAULT_REQUIREMENTS_MAX_ITERATIONS",
    "DEFAULT_REQUIREMENTS_MIN_ITERATIONS",
    "PROVIDER_GEMINI",
    "PROVIDER_OPENAI",
    "breakdown_requirements",
    "create_product_manager",
    "create_product_manager_critic",
    "create_requirements_breakdown_agent",
    "get_task_configs",
]
