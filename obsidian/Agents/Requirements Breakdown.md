# Requirements Breakdown

> Decomposes refined product ideas into granular, implementation-ready requirements with entities, state machines, API contracts, and acceptance criteria.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research |
| **Model Env Var** | `REQUIREMENTS_BREAKDOWN_MODEL` → `GEMINI_RESEARCH_MODEL` → `DEFAULT_GEMINI_RESEARCH_MODEL` |
| **Tools** | None (pure reasoning, knowledge sources available) |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Introduced** | v0.1.0 |
| **Source** | `agents/requirements_breakdown/` |

---

## Role

> Senior Solutions Architect & AI Product Requirements Specialist

## Goal

Decompose a refined product idea into granular, implementation-ready product requirements with a focus on AI agent capabilities that augment industry users. Each feature must include data entities, attributes, state machines, API contracts, and AI augmentation points.

## Backstory

You have 20+ years of experience bridging product vision and technical implementation. You have architected enterprise platforms in FinTech, InsurTech, PropTech, and Developer Tools — all with heavy emphasis on AI-assisted workflows. You think in terms of entities, relationships, state transitions, and event-driven architectures.

---

## Tasks

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

## Scoring Criteria

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

## PRD Flow Phase

**Phase 1** — Runs after Idea Refiner produces the refined idea. Outputs structured requirements consumed by Engineering Manager and section drafting.

---

## Source Files

- `agents/requirements_breakdown/config/agent.yaml` — role, goal, backstory
- `agents/requirements_breakdown/config/tasks.yaml` — task definitions
- `agents/requirements_breakdown/agent.py` — agent factory function

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]]
