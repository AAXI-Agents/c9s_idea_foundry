# Agent Roles

> All CrewAI agent configurations used in the PRD Planner.

## Idea Refiner

- **LLM**: Gemini (Research tier)
- **Tools**: None
- **Purpose**: Enrich raw ideas with domain expertise and stakeholder perspective
- **Process**: 3-10 iterative cycles
- **Scoring**: audience clarity, problem definition, solution specificity, competitive context, success criteria (1-5 each, all must ≥ 3 for "IDEA_READY")
- **Source**: `agents/idea_refiner/`

## Product Manager — Gemini

- **LLM**: Gemini (Research tier)
- **Tools**: FileReadTool, DirectoryReadTool
- **Purpose**: Draft and critique PRD sections with deep industry knowledge
- **Source**: `agents/product_manager/`

## Product Manager — OpenAI

- **LLM**: OpenAI (Research tier)
- **Tools**: FileReadTool, DirectoryReadTool
- **Purpose**: Secondary PM for multi-agent diversity in critique cycles
- **Source**: `agents/product_manager/`

## Product Manager Critic

- **LLM**: Gemini (Critic/Basic tier)
- **Tools**: None
- **Purpose**: Lightweight section critique (v0.8.1+, separate from research-tier drafter)
- **Source**: `agents/product_manager/`

## Requirements Breakdown Agent

- **LLM**: Gemini (Research tier)
- **Tools**: None
- **Purpose**: Decompose refined ideas into entities, state machines, API contracts, acceptance criteria
- **Scoring**: feature completeness, entity granularity, state machine rigour, AI augmentation depth, API contract precision, acceptance criteria coverage (1-5 each, all must ≥ 4)
- **Source**: `agents/requirements_breakdown/`

## Orchestrator Agent

- **LLM**: Gemini (Research tier)
- **Tools**: Confluence + Jira tools
- **Purpose**: Publish completed PRDs to Confluence, create Jira tracking tickets
- **Source**: `agents/orchestrator/`

## Delivery Manager Agent

- **LLM**: Gemini (Research tier)
- **Tools**: Confluence + Jira tools
- **Purpose**: Startup delivery orchestration (auto-publish pending Confluence/Jira)
- **Source**: `agents/orchestrator/`

## Jira PM / Architect Agents

- **LLM**: Gemini (Research tier)
- **Tools**: Jira tool
- **Purpose**: Epic/Story/Sub-task creation with domain-specific structure
- **Source**: `agents/orchestrator/`

---

See also: [[LLM Model Tiers]], [[PRD Flow]], [[Orchestrator Overview]]
