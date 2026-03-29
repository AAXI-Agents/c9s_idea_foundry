# Idea Refinement Flow

> Phase 0 — Iterative idea enrichment with domain expertise (3-10 cycles).

| Field | Value |
|-------|-------|
| **Phase** | 0 (first in pipeline) |
| **Agent** | [[Idea Refiner]] |
| **LLM Tier** | Research (Gemini) |
| **Source** | `orchestrator/_idea_refinement.py` |
| **Stage Factory** | `build_idea_refinement_stage(flow)` |
| **Pipeline** | `build_default_pipeline()` |

---

## Purpose

Enrich a raw user idea into a detailed, well-structured description that a Product Manager can immediately use to draft a comprehensive PRD. The Idea Refiner adopts a domain-expert persona and probes for missing context, business justification, user pain-points, competitive differentiation, and technical feasibility.

---

## Step-by-Step Flow

### Step 1 — Skip Check

```
_should_skip() → bool
```

Skips this phase if:
- `flow.state.idea_refined == True` (already refined in a previous run)
- No Gemini credentials (`GOOGLE_API_KEY` or `GOOGLE_CLOUD_PROJECT` not set)

### Step 2 — Refinement Execution

```
_run() → StageResult
```

- Calls `agents.idea_refiner.refine_idea(idea, run_id, project_id)`
- Runs 3-10 iterative cycles:
  1. **Refine**: `refine_idea_task` — identify industry, adopt expert persona, probe with 3-5 hard questions, produce 400-800 word refined version
  2. **Evaluate**: `evaluate_quality_task` — score 5 criteria, output `IDEA_READY` or `NEEDS_MORE`
  3. **Repeat** if `NEEDS_MORE`
- Returns `StageResult(output=refined_idea, history=list[dict])`

### Step 3 — State Update

```
_apply(result) → None
```

- `flow.state.idea = result.output` (refined idea replaces raw input)
- `flow.state.idea_refined = True`
- `flow.state.refinement_history = result.history`
- `flow.state.original_idea = snapshot` (preserves raw input)

### Step 4 — User Approval Gate

```
_requires_approval() → bool
_get_approval() → bool
```

- Returns `True` only if `idea_approval_callback` is set AND Gemini credentials are absent
- Auto-approves when requirements breakdown stage is configured (normal path)
- Calls `flow.idea_approval_callback(refined_idea, original_idea, run_id, history)`
- If user declines: raises `IdeaFinalized()` — flow stops after idea refinement

---

## Scoring Criteria

| Criterion | Threshold |
|-----------|-----------|
| Target audience clarity | ≥ 3 / 5 |
| Problem definition | ≥ 3 / 5 |
| Solution specificity | ≥ 3 / 5 |
| Competitive context | ≥ 3 / 5 |
| Success criteria | ≥ 3 / 5 |

All five must score ≥ 3 for `IDEA_READY`.

---

## Progress Events

| Event | When |
|-------|------|
| `pipeline_stage_start` | Idea refinement begins |
| `pipeline_stage_complete` | Refinement finished (includes iteration count) |
| `pipeline_stage_skipped` | Skipped (already refined or no credentials) |

---

## Resume Behaviour

On resume, this phase is skipped if `flow.state.idea_refined == True`. The previously refined idea and history are restored from MongoDB.

---

## MongoDB Persistence

- `save_iteration(run_id, step="idea_refinement", ...)` — after each cycle
- Refinement history stored in `working_ideas.refinement_history[]`
- Original idea preserved in `working_ideas.original_idea`

---

## Data Flow

```
Input:  flow.state.idea (raw user text)
Output: flow.state.idea (refined), flow.state.original_idea (preserved)
        flow.state.refinement_history (all iterations)
Next:   → Executive Summary Flow (Phase 1)
```

---

## Source Files

- `orchestrator/_idea_refinement.py` — stage factory and implementation
- `agents/idea_refiner/agent.py` — agent factory
- `agents/idea_refiner/config/agent.yaml` — role, goal, backstory
- `agents/idea_refiner/config/tasks.yaml` — task definitions

---

See also: [[PRD Flow]], [[Idea Refiner]], [[Executive Summary Flow]]
