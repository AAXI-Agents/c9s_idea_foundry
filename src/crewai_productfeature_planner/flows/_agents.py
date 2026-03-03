"""Agent management helpers for the PRD flow.

Handles agent creation, parallel draft execution, and decision parsing.
Extracted from ``prd_flow.py`` for modularity.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from crewai import Agent, Crew, Process, Task

from crewai_productfeature_planner.apis.prd.models import (
    AGENT_GEMINI,
    AGENT_OPENAI,
    get_default_agent,
)
from crewai_productfeature_planner.agents.product_manager import (
    create_product_manager,
)
from crewai_productfeature_planner.flows._constants import (
    DEFAULT_MULTI_AGENTS,
    ApprovalDecision,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger, is_verbose
from crewai_productfeature_planner.scripts.retry import crew_kickoff_with_retry

logger = get_logger(__name__)


def get_available_agents(
    project_id: str | None = None,
) -> dict[str, Agent]:
    """Return a dict of agent-name → Agent for all available LLMs.

    The *default* agent (``DEFAULT_AGENT`` env var, falls back to
    ``openai``) is always created first and is required.

    ``DEFAULT_MULTI_AGENTS`` controls how many PM agents run in
    parallel:

    * **1** (default) — only the default agent is used.
    * **2** — the default agent plus one optional agent whose API
      key is present.

    Args:
        project_id: Optional project identifier for memory enrichment.
    """
    default = get_default_agent()
    max_agents = int(
        os.environ.get("DEFAULT_MULTI_AGENTS", str(DEFAULT_MULTI_AGENTS)),
    )
    max_agents = max(1, max_agents)  # at least the default

    agents: dict[str, Agent] = {}

    # --- factories keyed by agent identifier ---
    def _openai() -> Agent:
        return create_product_manager(
            provider=AGENT_OPENAI, project_id=project_id,
        )

    def _gemini() -> Agent:
        return create_product_manager(
            provider=AGENT_GEMINI, project_id=project_id,
        )

    factories: dict[str, tuple[callable, str | list[str] | None]] = {
        AGENT_OPENAI: (_openai, "OPENAI_API_KEY"),
        AGENT_GEMINI: (_gemini, ["GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT"]),
    }

    # 1) Create the default agent (required)
    factory_fn, _ = factories[default]
    agents[default] = factory_fn()
    logger.info("[Agents] Default agent: %s", default)

    # 2) Create optional secondary agents (if multi-agent is enabled)
    if len(agents) < max_agents:
        for name, (factory_fn, env_key) in factories.items():
            if name == default:
                continue  # already created
            if len(agents) >= max_agents:
                break
            # env_key may be a single string or a list of alternatives
            if env_key:
                keys = [env_key] if isinstance(env_key, str) else env_key
                if not any(os.environ.get(k) for k in keys):
                    logger.info("[Agents] None of %s set — skipping %s",
                                keys, name)
                    continue
            try:
                agents[name] = factory_fn()
                logger.info("[Agents] Optional agent enabled: %s", name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[Agents] Failed to create %s: %s — continuing without it",
                    name, exc,
                )
    else:
        logger.info(
            "[Agents] DEFAULT_MULTI_AGENTS=%d — using default agent only",
            max_agents,
        )

    return agents


def run_agents_parallel(
    agents: dict[str, Agent],
    task_configs: dict,
    section_title: str,
    idea: str,
    section_content: str,
    executive_summary: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Execute draft tasks across *agents* in parallel.

    Returns a tuple of:
        - ``{agent_name: raw_output}`` dict with successful results.
        - ``{agent_name: error_message}`` dict for agents that failed.

    If one agent fails the others still succeed; the error is logged
    and that agent is omitted from the result dict.
    """
    def _draft(agent_name: str, agent: Agent) -> tuple[str, str]:
        draft_task = Task(
            description=task_configs["draft_section_task"]["description"].format(
                section_title=section_title,
                idea=idea,
                section_content=section_content or "(Initial draft)",
                executive_summary=executive_summary or "(Not yet available)",
            ),
            expected_output=task_configs["draft_section_task"]["expected_output"].format(
                section_title=section_title,
            ),
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[draft_task],
            process=Process.sequential,
            verbose=is_verbose(),
        )
        result = crew_kickoff_with_retry(crew, step_label=f"draft_{agent_name}")
        return agent_name, result.raw

    results: dict[str, str] = {}
    failed: dict[str, str] = {}
    if len(agents) == 1:
        # Fast path — no thread overhead for single agent
        name, agent = next(iter(agents.items()))
        _, raw = _draft(name, agent)
        results[name] = raw
    else:
        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            futures = {
                pool.submit(_draft, name, agent): name
                for name, agent in agents.items()
            }
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    _, raw = future.result()
                    results[agent_name] = raw
                except Exception as exc:  # noqa: BLE001
                    error_msg = f"{type(exc).__name__}: {exc}"
                    logger.error(
                        "[Draft] Agent '%s' failed: %s — skipping", agent_name, error_msg,
                    )
                    failed[agent_name] = error_msg

    if not results:
        raise RuntimeError("All agents failed during parallel drafting")

    # Reorder so default agent appears first in the dict.
    # as_completed returns results in finishing order which is
    # non-deterministic; callers rely on iteration order to pick
    # the initial selected agent.
    default = get_default_agent()
    if default in results and next(iter(results)) != default:
        results = {default: results[default], **{k: v for k, v in results.items() if k != default}}

    return results, failed


def parse_decision(
    decision: ApprovalDecision,
    available_agents: list[str],
) -> tuple[str, bool | str]:
    """Normalise an *ApprovalDecision* into ``(agent_name, action)``.

    *action* is ``True`` (approve), ``False`` (self-critique + refine)
    or a ``str`` (user-feedback → refine).
    """
    if isinstance(decision, tuple):
        agent_name, action = decision
        return str(agent_name), action

    # Legacy single-value return — prefer the DEFAULT_AGENT;
    # fall back to the first available agent if it is not in the list.
    default = get_default_agent()
    default_agent = default if default in available_agents else available_agents[0]
    return default_agent, decision


__all__ = [
    "get_available_agents",
    "run_agents_parallel",
    "parse_decision",
]
