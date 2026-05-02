---
tags:
  - agents
  - crewai
---

# Product Manager

> Drafts, critiques, and refines PRD sections through deep reasoning and iterative review cycles. Also decomposes refined ideas into granular, implementation-ready requirements with entities, state machines, API contracts, and acceptance criteria.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research (drafter & requirements) / Critic (critic variant) |
| **Drafter Model Env Var** | `OPENAI_RESEARCH_MODEL` or `GEMINI_PM_MODEL` → `GEMINI_RESEARCH_MODEL` |
| **Requirements Model Env Var** | `REQUIREMENTS_BREAKDOWN_MODEL` → `GEMINI_RESEARCH_MODEL` → `DEFAULT_GEMINI_RESEARCH_MODEL` |
| **Critic Model Env Var** | `GEMINI_CRITIC_MODEL` |
| **Tools** | FileReadTool, DirectoryReadTool (drafter); None (requirements, critic) |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Provider** | `"openai"` or `"gemini"` (configurable) |
| **Introduced** | v0.1.0 (critic variant v0.8.1) |
| **Source** | `agents/product_manager/`, `agents/requirements_breakdown/` |

---

## Role

> Senior Product Manager & Solutions Architect

## Goal

Transform raw ideas into comprehensive, technically feasible PRDs through deep reasoning and iterative refinement. Decompose refined ideas into granular, implementation-ready requirements with data entities, state machines, API contracts, and AI augmentation points. Leverage advanced reasoning capabilities to uncover hidden requirements, anticipate edge cases, and produce production-ready feature definitions.

## Backstory

You are an expert PM with a background in Agile methodologies and systems thinking. You have 20+ years of experience bridging product vision and technical implementation across FinTech, InsurTech, PropTech, and Developer Tools — all with heavy emphasis on AI-assisted workflows. You excel at spotting "logic gaps" in features and translating user needs into structured requirements. You think in terms of entities, relationships, state transitions, and event-driven architectures.

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

### Requirements Breakdown

- **LLM**: Gemini Research tier (`REQUIREMENTS_BREAKDOWN_MODEL` → `GEMINI_RESEARCH_MODEL`)
- **Tools**: None (pure reasoning, knowledge sources available)
- **Purpose**: Decompose refined ideas into implementation-ready requirements

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

### `breakdown_requirements_task`

Decompose refined idea into product features. For EACH feature, produce:

- Feature Overview
- Data Entities & Attributes (fully-typed)
- State Machine (state-transition notation)
- AI Agent Augmentation Points
- API Contract Sketch
- Acceptance Criteria

**Expected output**: 2000-5000 words with fully-typed attributes and state-transition notation.

### `evaluate_requirements_task`

Evaluate whether requirements breakdown is detailed enough for a data architect to start building without follow-up questions.

---

## Requirements Scoring Criteria

| Criterion | Threshold |
|-----------|-----------|
| Feature completeness | ≥ 4 / 5 |
| Entity granularity | ≥ 4 / 5 |
| State machine rigour | ≥ 4 / 5 |
| AI augmentation depth | ≥ 4 / 5 |
| API contract precision | ≥ 4 / 5 |
| Acceptance criteria coverage | ≥ 4 / 5 |

All six criteria must score ≥ 4 for the requirements to pass.

---

## Tools

| Tool | Purpose |
|------|---------|
| `FileReadTool` | Read knowledge files, existing PRDs, reference docs |
| `DirectoryReadTool` | List `output/prds/` directory |

---

## PRD Flow Phase

**Phase 1** — Receives refined idea from Idea Refiner. Drafts executive summary, then individual sections. Critic variant reviews each section for quality scoring. Requirements Breakdown variant runs after Idea Refiner to produce structured requirements consumed by Engineering Manager and section drafting.

---

## Source Files

- `agents/product_manager/config/agent.yaml` — role, goal, backstory
- `agents/product_manager/config/tasks.yaml` — task definitions
- `agents/product_manager/agent.py` — agent factory functions (Gemini, OpenAI, Critic variants)
- `agents/requirements_breakdown/config/agent.yaml` — requirements role, goal, backstory
- `agents/requirements_breakdown/config/tasks.yaml` — requirements task definitions
- `agents/requirements_breakdown/agent.py` — requirements agent factory function

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]]
