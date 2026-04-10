---
tags:
  - orchestrator
---

# Orchestrator Overview

> Pipeline runner and stage factories in `orchestrator/`.

## Architecture

The `AgentOrchestrator` executes a pipeline of `AgentStage` objects sequentially. Each stage has:
- A name
- An `_apply()` function that does the work
- A `StageResult` return (success/skip/fail + output)

## Stage Factories

| Factory | File | Purpose |
|---------|------|---------|
| `build_idea_refinement_stage(flow)` | `_idea_refinement.py` | Iterative idea enrichment |
| `build_requirements_breakdown_stage(flow)` | `_requirements.py` | Requirements decomposition |
| `build_confluence_publish_stage(flow)` | `_confluence.py` | Confluence page creation |
| `build_jira_skeleton_stage(flow)` | `_jira.py` | Jira skeleton outline |
| `build_jira_epics_stories_stage(flow)` | `_jira.py` | Epics + Stories creation |
| `build_jira_subtasks_stage(flow)` | `_jira.py` | Sub-tasks with dependencies |
| `build_jira_kanban_tasks_stage(flow)` | `_jira.py` | Flat kanban Tasks (no hierarchy) |
| `build_jira_ticketing_stage(flow)` | `_jira.py` | Legacy auto-approve Jira (scrum or kanban) |

## Pipelines

| Pipeline | File | Stages |
|----------|------|--------|
| `build_default_pipeline(flow)` | `_pipelines.py` | Idea refinement only (v0.12.3+) |
| `build_post_completion_pipeline(flow)` | `_pipelines.py` | Confluence + Jira |

## Progress Callback (v0.9.0+)

The orchestrator fires events during pipeline execution:
- `pipeline_stage_start` — stage beginning
- `pipeline_stage_complete` — stage finished with iteration count
- `pipeline_stage_skipped` — stage skipped (e.g., missing credentials)

## Crew Factories

| Factory | File | Key params |
|---------|------|------------|
| `build_post_completion_crew(flow, *, confluence_only=False)` | `_post_completion.py` | `confluence_only=True` gates out all Jira tasks |
| `build_startup_delivery_crew(item, *, confluence_only=False)` | `_startup_delivery.py` | `confluence_only=True` gates out all Jira tasks |

### `confluence_only` Invariant

The `confluence_only` parameter **must** be `True` in all autonomous
paths (no user interaction). Jira ticket creation requires the phased
approval flow. See [[Coding Standards]] §6 and
`tests/flows/test_jira_approval_gate.py`.

## When to Load Which File

| Task | File(s) |
|------|---------|
| Fix credential checks | `_helpers.py` |
| Change idea refinement | `_idea_refinement.py` |
| Change requirements | `_requirements.py` |
| Fix Confluence publishing | `_confluence.py` |
| Fix Jira ticket creation | `_jira.py` |
| Change pipeline composition | `_pipelines.py` |
| Fix post-completion delivery | `_post_completion.py` |
| Fix startup PRD publishing | `_startup_review.py` |
| Fix startup deliveries | `_startup_delivery.py` |

---

See also: [[PRD Flow]], [[Agent Roles]], [[Confluence Integration]], [[Jira Integration]]
