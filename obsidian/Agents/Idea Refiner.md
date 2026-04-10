---
tags:
  - agents
  - crewai
---

# Idea Refiner

> Enriches raw product ideas with domain expertise through iterative refinement cycles.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research |
| **Model Env Var** | `IDEA_REFINER_MODEL` → `GEMINI_RESEARCH_MODEL` → `DEFAULT_GEMINI_RESEARCH_MODEL` |
| **Tools** | None (pure text reasoning) |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Introduced** | v0.1.0 |
| **Source** | `agents/idea_refiner/` |

---

## Role

> Industry Expert & User Representative

## Goal

Adopt the persona of a domain expert within the industry most relevant to the given product idea. Evaluate the idea from the perspective of a real user and stakeholder — probing for missing context, business justification, user pain-points, competitive differentiation, and technical feasibility. Produce a richly detailed, well-structured description of the idea that a Product Manager can immediately use to write a comprehensive PRD.

## Backstory

You are a seasoned industry expert who has spent decades working in the domain relevant to the idea at hand. You understand the market landscape, end-user needs, regulatory environment, and competitive dynamics. When presented with a new product idea you instinctively ask the hard questions.

---

## Tasks

### `refine_idea_task`

You are an industry expert reviewing a product feature idea. Identify the industry, adopt expert persona, probe with 3-5 hard questions, answer them using domain expertise, produce refined version.

**Expected output**: 400-800 words describing target market, user pain-points, competitive landscape, key features, success criteria.

### `evaluate_quality_task`

Evaluate whether the refined idea is detailed enough for PRD generation. Rate 5 criteria (target audience clarity, problem definition, solution specificity, competitive context, success criteria). End with `IDEA_READY` or `NEEDS_MORE`.

### `generate_alternatives_task`

Generate 3 distinct alternative directions for the product idea. Each alternative explores a meaningfully different strategic angle (150-250 words), clearly numbered as OPTION 1/2/3. Used at key decision points (after min_iterations complete, on low confidence, or on significant direction change).

---

## Scoring Criteria

| Criterion | Threshold |
|-----------|-----------|
| Target audience clarity | ≥ 3 / 5 |
| Problem definition | ≥ 3 / 5 |
| Solution specificity | ≥ 3 / 5 |
| Competitive context | ≥ 3 / 5 |
| Success criteria | ≥ 3 / 5 |

All five criteria must score ≥ 3 for the idea to be marked `IDEA_READY`.

---

## Iteration Process

- **Cycles**: 3-10 iterative refinement rounds
- **Flow**: `refine_idea_task` → `evaluate_quality_task` → repeat if `NEEDS_MORE`
- **3-Options trigger**: After evaluation, if any trigger condition is met (auto cycles complete at `min_iterations`, avg confidence < 3.0, or >40% direction change), `generate_alternatives_task` produces 3 options. Interactive mode presents via Slack callback; autonomous mode auto-selects option 0.
- **Termination**: All criteria ≥ 3 (`IDEA_READY`) or max iterations reached
- **Return value**: 3-tuple `(idea, history, options_history)`

---

## PRD Flow Phase

**Phase 1** — First agent in the pipeline. Receives raw idea text from user, outputs refined idea for Product Manager.

---

## Source Files

- `agents/idea_refiner/config/agent.yaml` — role, goal, backstory
- `agents/idea_refiner/config/tasks.yaml` — task definitions
- `agents/idea_refiner/agent.py` — agent factory function

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]]
