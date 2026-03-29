# Step 2 — Executive Summary Flow

> Pipeline Step 2 — Multi-agent draft→critique→refine loop for the PRD executive summary.

| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Agents** | [[Product Manager]] (Gemini + OpenAI variants, Critic) |
| **LLM Tier** | Research (drafters), Critic (reviewer) |
| **Source** | `flows/prd_flow.py`, `flows/_executive_summary.py` |
| **Min Iterations** | 2 |
| **Max Iterations** | 10 |

---

## Purpose

Generate a comprehensive executive summary through iterative drafting, critique, and refinement. Uses parallel Gemini and OpenAI Product Manager agents for diversity, with a Critic agent scoring quality. Users can provide feedback between iterations.

---

## Step-by-Step Flow

### Step 1 — Pre-Draft User Gate

```
exec_summary_user_feedback_callback(content="", idea, run_id, iteration=0)
```

- Fires before the first draft if callback is set
- User can: `"skip"` (proceed to auto-draft), `"approve"` (skip entirely), or provide `"feedback"` text
- Returns `(action, feedback_text | None)`

### Step 2 — Parallel Drafting

```
_run_agents_parallel(agents, task_configs, section_title="Executive Summary", ...)
```

- Runs Gemini PM + OpenAI PM in parallel threads
- Each agent executes `draft_prd_task` with:
  - `{idea}`: refined idea text
  - `{section_title}`: "Executive Summary"
  - Context from knowledge sources
- Returns `(agent_results: {name → draft}, failed_agents: {name → error})`
- Default agent's output becomes the initial draft content

### Step 3 — Critique Scoring

```
critique_prd_task(executive_summary_draft, idea)
```

- Critic agent evaluates the draft against 7 criteria:

| Criterion | Scale |
|-----------|-------|
| Problem clarity | 1-10 |
| Personas | 1-10 |
| Functional requirements | 1-10 |
| Non-functional requirements | 1-10 |
| Edge cases | 1-10 |
| Analytics | 1-10 |
| Dependencies | 1-10 |

- Outputs `READY_FOR_DEV` (all ≥ 8) or `NEEDS_REFINEMENT`
- Persisted via `update_executive_summary_critique()`

### Step 4 — User Feedback Gate

```
exec_summary_user_feedback_callback(content, idea, run_id, iteration)
```

- Fires after each critique iteration (iteration ≥ 1)
- User can:
  - `"approve"` — accept current draft, stop iterating
  - `"feedback"` — provide text to incorporate in next refinement
  - `"skip"` — let auto-critique continue
- Slack integration: user sees draft + critique scores + approve/feedback buttons

### Step 5 — Refinement

- If `NEEDS_REFINEMENT` and iteration < max:
  - Incorporates user feedback (if provided) into next draft prompt
  - Runs parallel agents again with previous draft + critique as context
  - Returns to Step 3
- If `READY_FOR_DEV` or iteration ≥ max:
  - Marks executive summary as approved

### Step 6 — Completion Gate

```
executive_summary_callback(content, idea, run_id, iterations_history)
```

- Fires after executive summary is approved
- User decides: continue to specialist reviews + section drafting, or stop here
- Returns `True` (continue) or `False` (stop → raises `ExecutiveSummaryCompleted`)

---

## Progress Events

| Event | When | Key Fields |
|-------|------|------------|
| `exec_summary_iteration` | Each draft→critique pass | `iteration`, `max_iterations` |
| `executive_summary_complete` | Summary finalized | `iterations` |

---

## Resume Behaviour

On resume:
- Skips if executive summary already has ≥ `PRD_EXEC_RESUME_THRESHOLD` iterations
- Restores iteration history from `working_ideas.executive_summary[]`
- Restores approval state from critique keywords in last iteration

---

## MongoDB Persistence

- `save_iteration(run_id, step="executive_summary", ...)` — after each cycle
- `update_executive_summary_critique(run_id, critique)` — after critique scoring
- Stored in `working_ideas.executive_summary[]` as iteration array

---

## Data Flow

```
Input:  flow.state.idea (refined)
        flow.state.original_idea
Output: flow.state.executive_summary.latest_content
        flow.state.executive_summary.is_approved
        flow.state.executive_summary.iterations[]
Next:   → Requirements Breakdown Flow + CEO Review Flow (Phase 1 / 1.5a)
```

---

## Source Files

- `flows/prd_flow.py` — `_iterate_executive_summary()` orchestration
- `flows/_executive_summary.py` — executive summary iteration logic
- `agents/product_manager/agent.py` — PM agent factories (Gemini, OpenAI, Critic)
- `agents/product_manager/config/tasks.yaml` — draft_prd_task, critique_prd_task

---

See also: [[PRD Flow]], [[Product Manager]], [[Idea Refinement Flow|Step 1 — Idea Refinement Flow]], [[Requirements Breakdown Flow|Step 3 — Requirements Breakdown Flow]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:
- [ ] <your change request here>

EXAMPLE:
- [ ] Add a new field `priority` (string, optional) to the response
- [ ] Rename endpoint from /v1/old to /v2/new
-->

### Pending

_No pending change requests._

### Completed

_No completed change requests._
