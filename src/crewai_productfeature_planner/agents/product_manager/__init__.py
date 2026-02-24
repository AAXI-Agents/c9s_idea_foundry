"""Product Manager agent module.

Provides a single factory ``create_product_manager(provider)`` that
supports both OpenAI and Gemini LLM backends.
"""

from crewai_productfeature_planner.agents.product_manager.agent import (
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    create_product_manager,
    get_task_configs,
)

__all__ = [
    "PROVIDER_GEMINI",
    "PROVIDER_OPENAI",
    "create_product_manager",
    "get_task_configs",
]
