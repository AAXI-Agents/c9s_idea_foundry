---
tags:
  - agents
  - crewai
---

# Product Manager

> Drafts, critiques, and refines PRD sections through deep reasoning and iterative review cycles.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research (drafter) / Critic (critic variant) |
| **Drafter Model Env Var** | `OPENAI_RESEARCH_MODEL` or `GEMINI_PM_MODEL` → `GEMINI_RESEARCH_MODEL` |
| **Critic Model Env Var** | `GEMINI_CRITIC_MODEL` |
| **Tools** | FileReadTool, DirectoryReadTool |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Provider** | `"openai"` or `"gemini"` (configurable) |
| **Introduced** | v0.1.0 (critic variant v0.8.1) |
| **Source** | `agents/product_manager/` |

---

## Role

> Senior Product Manager

## Goal

Transform raw ideas into comprehensive, technically feasible PRDs through deep reasoning and iterative refinement. Leverage advanced reasoning capabilities to uncover hidden requirements, anticipate edge cases, and produce production-ready feature definitions.

## Backstory

You are an expert PM with a background in Agile methodologies and systems thinking. You excel at spotting "logic gaps" in features and translating user needs into structured requirements. You approach every feature with rigorous analytical reasoning.

---

## Agent Variants

### Product Manager — Gemini

- **LLM**: Gemini Research tier (`GEMINI_PM_MODEL` → `GEMINI_RESEARCH_MODEL`)
- **Purpose**: Primary PRD section drafter

### Product Manager — OpenAI

- **LLM**: OpenAI Research tier (`OPENAI_RESEARCH_MODEL`)
- **Purpose**: Secondary PM for multi-agent diversity in critique cycles

### Product Manager Critic

- **LLM**: Gemini Critic tier (`GEMINI_CRITIC_MODEL`)
- **Tools**: None
- **Purpose**: Lightweight section critique (v0.8.1+, separate from research-tier drafter)

---

## Tasks

### `draft_prd_task`

Create a comprehensive Product Requirements Document including researching competitors and technical standards. Write a compelling executive summary.

### `critique_prd_task`

Critically review the PRD executive summary draft against DoD checklist (7 criteria). Rate readiness 1-10; mark `READY_FOR_DEV` or `NEEDS_REFINEMENT`.

### `draft_section_task`

Draft individual PRD sections:

- Problem Statement
- User Personas
- Functional Requirements
- Non-Functional Requirements
- Edge Cases
- Error Handling
- Success Metrics
- Dependencies
- Assumptions

---

## Tools

| Tool | Purpose |
|------|---------|
| `FileReadTool` | Read knowledge files, existing PRDs, reference docs |
| `DirectoryReadTool` | List `output/prds/` directory |

---

## PRD Flow Phase

**Phase 1** — Receives refined idea from Idea Refiner. Drafts executive summary, then individual sections. Critic variant reviews each section for quality scoring.

---

## Source Files

- `agents/product_manager/config/agent.yaml` — role, goal, backstory
- `agents/product_manager/config/tasks.yaml` — task definitions
- `agents/product_manager/agent.py` — agent factory functions (Gemini, OpenAI, Critic variants)

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]]
