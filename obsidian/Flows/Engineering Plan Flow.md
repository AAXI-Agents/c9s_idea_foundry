---
tags:
  - flows
  - pipeline
---

# Step 6 — Engineering Plan Flow

> Pipeline Step 6 — Generate a bulletproof engineering plan from the Executive Product Summary, requirements, and all completed PRD sections.

| Field | Value |
|-------|-------|
| **Phase** | 1.5b (after CEO review) |
| **Agent** | [[Engineering Manager]] |
| **LLM Tier** | Research (Gemini or OpenAI) |
| **Source** | `flows/_ceo_eng_review.py` |
| **Function** | `run_eng_plan(flow)` |

---

## Purpose

Convert the Executive Product Summary and requirements breakdown into a comprehensive Engineering Plan covering architecture, system boundaries, data flows, state machines, failure modes, test strategy, security, and deployment.

---

## Step-by-Step Flow

### Step 1 — Skip Check

Skips if:
- `flow.state.engineering_plan` is already populated (previous run or resume)
- No Gemini credentials

### Step 2 — Agent Execution

```
run_eng_plan(flow) → str
```

- Creates agent: `create_eng_manager(project_id)`
- Task: `generate_engineering_plan_task`
- Input parameters:
  - `{executive_product_summary}`: `flow.state.executive_product_summary`
  - `{idea}`: `flow.state.idea`
  - `{requirements_breakdown}`: `flow.state.requirements_breakdown` or `"(Not available)"`

### Step 3 — Output Processing

- `result.raw` → `flow.state.engineering_plan`
- Populates draft section `"engineering_plan"` with `is_approved=True`
- No user approval gate — auto-approved as specialist section

### Step 4 — Persistence

- `save_iteration(run_id, step="eng_plan", section_key="engineering_plan")`
- Content stored in `working_ideas.engineering_plan`

---

## Engineering Plan Coverage

The generated plan uses **progressive disclosure** format: each section
starts with a concise high-level summary (suitable for non-technical
readers), followed by a **Technical Deep-Dive** sub-section with full
engineering detail and ASCII diagrams.

| Section | Content |
|---------|---------|
| Architecture Overview | ASCII diagrams, component layout |
| Component Breakdown | Service boundaries, responsibilities |
| Implementation Phases | Ordered build plan with dependencies |
| Data Model | Entities, relationships, schemas |
| Error Handling & Failure Modes | Happy/nil/empty/error paths |
| Test Strategy | Unit, integration, E2E coverage |
| Security & Trust Boundaries | Auth, authz, data protection |
| Deployment & Rollout | CI/CD, feature flags, rollback |
| Observability | Logging, metrics, alerting |

---

## Progress Events

| Event | When |
|-------|------|
| `eng_plan_start` | Engineering plan generation begins |
| `eng_plan_complete` | Engineering plan generated |

---

## Resume Behaviour

On resume, skipped if `flow.state.engineering_plan` is already set. The saved content is restored from `working_ideas.engineering_plan`.

---

## Data Flow

```
Input:  flow.state.executive_product_summary (from CEO Review)
        flow.state.requirements_breakdown (from Requirements Breakdown)
        flow.state.idea
Output: flow.state.engineering_plan
Next:   → Section Drafting Flow (Phase 2, used as context)
        → Jira Ticketing Flow (context for sub-task creation)
```

---

## User Decision Gate (v0.20.1)

After **both** CEO Review and Engineering Plan complete, a user decision gate fires:

```
executive_summary_callback(content, idea, run_id, ...)
```

- User reviews: requirements, Executive Product Summary, Engineering Plan, UX design
- Decides: proceed to section-by-section drafting, or stop here
- On resume: auto-bypassed when all specialists were skipped (already completed) or Phase 2 sections already have content

---

## Source Files

- `flows/_ceo_eng_review.py` — `run_eng_plan()` implementation
- `agents/eng_manager/agent.py` — agent factory
- `agents/eng_manager/config/agent.yaml` — role, goal, backstory
- `agents/eng_manager/config/tasks.yaml` — task definitions

---

See also: [[PRD Flow]], [[Engineering Manager]], [[CEO Review Flow|Step 4 — CEO Review Flow]], [[Section Drafting Flow|Step 5 — Section Drafting Flow]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:

EXAMPLE:
-->

### Pending

_No pending change requests._

### Completed

_No completed change requests._
