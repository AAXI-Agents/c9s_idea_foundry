"""Content Reviewer agent — analyzes knowledge documents."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from crewai import Agent, LLM

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def _load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_llm() -> LLM:
    model_name = os.environ.get("GEMINI_CONTENT_REVIEWER_MODEL", DEFAULT_GEMINI_MODEL)
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"
    return LLM(model=model_name, timeout=120, max_retries=2)


def create_content_reviewer() -> Agent:
    """Create a Content Reviewer agent instance."""
    agent_config = _load_yaml("agent.yaml")["content_reviewer"]
    return Agent(
        role=agent_config["role"].strip(),
        goal=agent_config["goal"].strip(),
        backstory=agent_config["backstory"].strip(),
        llm=_build_llm(),
        tools=[],
        verbose=False,
        allow_delegation=False,
    )


def get_task_configs() -> dict:
    """Load task configurations for the content reviewer."""
    return _load_yaml("tasks.yaml")
