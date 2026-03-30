# Agent Roles

> Index of all CrewAI agent configurations used in the PRD Planner.
> Each agent has its own detail page with full role, goal, backstory, tasks, tools, and source paths.

---

## PRD Pipeline Agents

| Agent | LLM Tier | Phase | Purpose |
|-------|----------|-------|---------|
| [[Idea Refiner]] | Research | 1 | Enrich raw ideas with domain expertise (3-10 iterative cycles) |
| [[Product Manager]] | Research / Critic | 1 | Draft, critique, and refine PRD sections |
| [[Requirements Breakdown]] | Research | 1 | Decompose ideas into entities, state machines, API contracts |
| [[CEO Reviewer]] | Research | 1.5a | 10-star product vision with founder-mode thinking |
| [[Engineering Manager]] | Research | 1.5b | Engineering plan with architecture, data flows, deployment |
| [[Orchestrator]] | Research | Post-PRD | Publish to Confluence, create Jira tickets |

## Jira Review Agents

| Agent | LLM Tier | Phase | Purpose |
|-------|----------|-------|---------|
| [[Staff Engineer]] | Research | Jira 4a | Paranoid structural audit per User Story |
| [[QA Lead]] | Research | Jira 4b | Test methodology and acceptance criteria review |
| [[QA Engineer]] | Research | Jira 5 | Edge case and security test counter-tickets |

## Design Agents

| Agent | LLM Tier | Phase | Purpose |
|-------|----------|-------|---------|
| [[UX Designer]] | Research | Post-PRD | Design specification in markdown (2-phase flow) |

## Conversational Agents

| Agent | LLM Tier | Fast Path | Purpose |
|-------|----------|-----------|---------|
| [[Engagement Manager]] | Basic | Yes | Unknown intents, idea-to-PRD lifecycle orchestration |
| [[Idea Agent]] | Basic | Yes | In-thread Q&A during active iterations |

## Stubs (Future)

| Agent | Source | Status |
|-------|--------|--------|
| Release Engineer | `agents/release_engineer/` | Placeholder |
| Retro Manager | `agents/retro_manager/` | Placeholder |

---

## Agent Execution Order

```
Raw Idea
  │
  ▼
Idea Refiner (3-10 cycles)
  │
  ▼
Product Manager (executive summary)
  │
  ├──► CEO Reviewer (Executive Product Summary)
  ├──► Requirements Breakdown
  │       │
  │       ▼
  │    Engineering Manager (Engineering Plan)
  │
  ├──► UX Designer + Design Partner → Senior Designer
  │
  ▼
Product Manager (section drafting + critique)
  │
  ▼
Orchestrator (Confluence + Jira)
  │
  ├──► Staff Engineer (review sub-tasks)
  ├──► QA Lead (review sub-tasks)
  └──► QA Engineer (test counter-tickets)
```

---

See also: [[LLM Model Tiers]], [[PRD Flow]], [[Orchestrator Overview]]
