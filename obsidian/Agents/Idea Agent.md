---
tags:
  - agents
  - crewai
---

# Idea Agent

> Context-aware in-thread analyst for active idea iterations — answers questions, provides steering recommendations, and identifies gaps.

| Field | Value |
|-------|-------|
| **LLM Tier** | Basic |
| **Model Env Var** | `IDEA_AGENT_MODEL` → `GEMINI_MODEL` → `DEFAULT_GEMINI_MODEL` |
| **Tools** | None (pure Q&A using provided context) |
| **Timeout** | 120 s |
| **Max Retries** | 3 |
| **Fast Path** | Direct Gemini REST API via `generate_chat_response()` (bypasses CrewAI, ~200-800 ms) |
| **CrewAI Override** | `IDEA_AGENT_USE_CREWAI=true` |
| **Special Params** | `respect_context_window=True` |
| **Introduced** | v0.43.0 |
| **Source** | `agents/idea_agent/` |

---

## Role

> Idea Analyst & Iteration Advisor

## Goal

Help users understand, query, and steer an in-progress product idea iteration. Provide instant, context-rich answers about the current state of the idea — including refined idea text, iteration history, executive summary drafts, requirements breakdown, engineering plan, completed PRD sections, and overall progress. Make actionable recommendations to improve the idea and steer upcoming iterations.

## Backstory

You are a sharp product analyst who works alongside the Idea Refiner, Product Manager, and other specialist agents during a PRD iteration. Your unique value is **real-time situational awareness** — you have full access to the current iteration state and can answer any question about what has been produced so far. You can tell what the current refined idea is, how many iterations ran and what changed, the latest executive summary, requirements breakdown, engineering plan status, which PRD sections are drafted.

---

## Tasks

### `idea_query_task`

Handle user questions and feedback during active idea iteration. Classify intent as:

- **Information request** — what's been produced → answer with specific data from iteration state
- **Steering feedback** — influence next iteration → produce structured `## Steering Recommendation` with target agent, instruction, and impact
- **Gap analysis** — what's missing → identify sections with weak content, inconsistencies, missing personas, weak success metrics

**Expected output**: Clear, structured response with specific data from iteration state. Keep under 2000 characters.

**When steering**: Include `## Steering Recommendation` section with:
- Target agent
- Instruction
- Impact

**When gap analysis**: Include `## Gaps & Recommendations` section.

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `create_idea_agent()` | Agent factory |
| `handle_idea_query()` | Entry point for in-thread queries |
| `extract_steering_feedback()` | Parse and persist steering recommendations to `agentInteraction` |
| `_extract_iteration_context()` | Build structured context from working-idea MongoDB document |

---

## Context Extraction

`_extract_iteration_context()` builds structured context from the working-idea MongoDB document:

- Status
- Refined idea text
- Refinement history (all iterations)
- Executive summary draft
- Requirements breakdown
- Engineering plan
- Completed PRD sections
- Active critiques

---

## Integration

- **Invoked when**: User sends `general_question` or unknown intent in a Slack thread with an active flow (status `inprogress`/`paused`)
- **Replaces**: [[Engagement Manager]] during active iterations (v0.43.0)
- **Steering persistence**: `extract_steering_feedback()` parses recommendations and stores in `agentInteraction` collection for downstream agents
- **Fallback**: If agent fails, falls back to `_build_flow_summary()` for basic status information

---

## Source Files

- `agents/idea_agent/config/agent.yaml` — role, goal, backstory
- `agents/idea_agent/config/tasks.yaml` — task definitions
- `agents/idea_agent/agent.py` — agent factory and handler functions

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[Engagement Manager]], [[PRD Flow]], [[Slack Integration]]
