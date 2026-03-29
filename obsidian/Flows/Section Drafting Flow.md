# Step 5 — Section Drafting Flow

> Pipeline Step 5 — Sequential draft→critique→refine loop for each PRD section.

| Field | Value |
|-------|-------|
| **Phase** | 2 |
| **Agents** | [[Product Manager]] (Gemini + OpenAI drafters, Critic) |
| **LLM Tier** | Research (drafters), Critic (reviewer) |
| **Source** | `flows/prd_flow.py` |
| **Min Iterations** | 2 per section |
| **Max Iterations** | 10 per section |

---

## Purpose

Generate the 9 remaining PRD sections sequentially after the executive summary, CEO review, and Engineering Plan are complete. Each section goes through parallel drafting by multiple agents, then iterative critique→refine cycles until quality thresholds are met.

---

## PRD Sections

| # | Section | Key |
|---|---------|-----|
| 1 | Executive Summary | `executive_summary` (Phase 1) |
| 2 | Executive Product Summary | `executive_product_summary` (Phase 1.5a) |
| 3 | Engineering Plan | `engineering_plan` (Phase 1.5b) |
| 4 | Problem Statement | `problem_statement` |
| 5 | User Personas | `user_personas` |
| 6 | Functional Requirements | `functional_requirements` |
| 7 | Non-Functional Requirements | `non_functional_requirements` |
| 8 | Edge Cases | `edge_cases` |
| 9 | Error Handling | `error_handling` |
| 10 | Success Metrics | `success_metrics` |
| 11 | Dependencies | `dependencies` |
| 12 | Assumptions | `assumptions` |

Sections 1-3 are handled by earlier phases. Sections 4-12 are processed in this flow.

---

## Step-by-Step Flow (Per Section)

### Step 1 — Skip Check

- Already-approved sections (`section.is_approved == True`) are skipped
- On resume: sections with content and iteration > 0 may skip directly to approval loop

### Step 2 — Parallel Drafting

```
_run_agents_parallel(agents, task_configs, section_title, ...)
```

- Runs Gemini PM + OpenAI PM in parallel threads
- Each agent executes `draft_section_task` with:
  - `{idea}`: refined idea
  - `{section_title}`: current section name
  - `{executive_summary}`: executive summary content
  - `{executive_product_summary}`: CEO review output (v0.18.0+)
  - `{engineering_plan}`: Eng Manager output (v0.18.0+)
- Returns `(agent_results: {name → draft}, failed_agents: {name → error})`
- Default agent's output becomes initial section content

### Step 3 — Draft Persistence

```
save_iteration(run_id, step=f"draft_{section.key}", ...)
```

- Progress event: `section_start` with `section_title`, `section_key`, `section_step`, `total_sections`

### Step 4 — User Approval Gate

```
approval_callback(iteration, section_key, agent_results, draft)
```

- Via `make_approval_callback(run_id)`:
  1. Updates in-memory FlowRun with latest state
  2. Sets status = `AWAITING_APPROVAL`
  3. Persists status to `crewJobs`
  4. Waits for user action (`/approve` or `/pause` via Slack)
- User can:
  - **Approve** — accept current draft, move to next section
  - **Select agent** — choose a different agent's draft
  - **Provide feedback** — text incorporated in next refinement
  - **Pause** — stop flow (raises `PauseRequested`)

### Step 5 — Critique Scoring

```
critique_prd_task(section_content, idea)
```

- Critic agent scores against 6 criteria:

| Criterion | Threshold |
|-----------|-----------|
| Completeness | ≥ 8 / 10 |
| Specificity | ≥ 8 / 10 |
| Consistency | ≥ 8 / 10 |
| Clarity | ≥ 8 / 10 |
| Actionability | ≥ 8 / 10 |
| No-duplication | ≥ 8 / 10 |

- Outputs `SECTION_READY` (all ≥ 8) or continues refining
- Persisted via `update_section_critique()`

### Step 6 — Refinement Loop

- If not `SECTION_READY` and iteration < max:
  - Incorporates user feedback + critique into next draft prompt
  - Returns to Step 2 with previous draft as context
- If `SECTION_READY` or iteration ≥ max:
  - `section.is_approved = True`
  - Progress event: `section_complete`

### Step 7 — Degenerate Content Detection

If a draft is excessively short (<5 chars after stripping), off-topic, or contains template placeholders, the content is wiped and the section restarts from scratch.

---

## Progress Events

| Event | When | Key Fields |
|-------|------|------------|
| `section_start` | Section begins | `section_title`, `section_key`, `section_step`, `total_sections` |
| `section_iteration` | Each draft→critique pass | `section_title`, `iteration`, `max_iterations` |
| `section_complete` | Section approved | `section_title`, `iterations` |
| `all_sections_complete` | All 9 sections done | `total_iterations`, `total_sections` |

---

## Resume Behaviour

On resume:
- Sections with `is_approved == True` are skipped entirely
- Section with content but not approved: resumes from approval/critique step
- Approval state inferred from: iteration count ≥ min threshold, or `SECTION_READY` in last critique
- Degenerate content is wiped and re-drafted

---

## MongoDB Persistence

- `save_iteration(run_id, step=f"draft_{section_key}", ...)` — after each draft
- `update_section_critique(run_id, section_key, critique)` — after each critique
- Stored in `working_ideas.sections[section_key][]` as iteration arrays

---

## Data Flow

```
Input:  flow.state.idea (refined)
        flow.state.executive_summary.latest_content
        flow.state.executive_product_summary (context)
        flow.state.engineering_plan (context)
Output: flow.state.draft.sections[] (all 9 sections with content + approval)
Next:   → Finalization Flow (Phase 3)
```

---

## Draft Files (v0.8.3+)

In-progress saves go to `output/prds/_drafts/`. Only completed PRDs appear in `output/prds/`.

---

## Source Files

- `flows/prd_flow.py` — `generate_sections()` main loop, `_run_agents_parallel()`, `_section_approval_loop()`
- `agents/product_manager/agent.py` — PM agent factories
- `agents/product_manager/config/tasks.yaml` — `draft_section_task`, `critique_prd_task`
- `apis/prd/service.py` — `make_approval_callback()` for Slack integration

---

See also: [[PRD Flow]], [[Product Manager]], [[Engineering Plan Flow|Step 6 — Engineering Plan Flow]], [[Finalization Flow|Step 7 — Finalization Flow]]


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
