# Step 4 — CEO Review Flow

> Pipeline Step 4 — Transform the executive summary into a 10-star Executive Product Summary.

| Field | Value |
|-------|-------|
| **Phase** | 1.5a (after executive summary approval) |
| **Agent** | [[CEO Reviewer]] |
| **LLM Tier** | Research (Gemini or OpenAI) |
| **Source** | `flows/_ceo_eng_review.py` |
| **Function** | `run_ceo_review(flow)` |
| **Special Params** | `reasoning=True`, `max_reasoning_attempts=3` |

---

## Purpose

Apply founder-mode thinking to rethink the product from the user's perspective. Challenge whether the right problem is being solved, elevate to a 10-star product vision, and produce an Executive Product Summary that replaces the raw executive summary as context for all downstream phases.

---

## Step-by-Step Flow

### Step 1 — Skip Check

Skips if:
- `flow.state.executive_product_summary` is already populated (previous run or resume)
- No Gemini credentials

### Step 2 — Agent Execution

```
run_ceo_review(flow) → str
```

- Creates agent: `create_ceo_reviewer(project_id)`
- Task: `generate_executive_product_summary_task`
- Input parameters:
  - `{executive_summary}`: `flow.state.executive_summary.latest_content`
  - `{idea}`: `flow.state.idea`
- Agent applies reasoning mode with up to 3 attempts

### Step 3 — Output Processing

- `result.raw` → `flow.state.executive_product_summary`
- Populates draft section `"executive_product_summary"` with `is_approved=True`
- No user approval gate — auto-approved as specialist section

### Step 4 — Persistence

- `save_iteration(run_id, step="ceo_review", section_key="executive_product_summary")`
- Content stored in `working_ideas.executive_product_summary`

---

## Challenge Areas

The CEO Reviewer evaluates the product through these lenses:
- **Problem reframing**: Is this the right problem to solve?
- **10-star vision**: What's the version that feels inevitable and delightful?
- **User experience narrative**: What makes users say "exactly what I needed"?
- **Scope mapping**: Current state → planned scope → 12-month ideal
- **Business impact**: Why this matters to the business

---

## Progress Events

| Event | When |
|-------|------|
| `ceo_review_start` | CEO review begins |
| `ceo_review_complete` | Executive Product Summary generated |

---

## Resume Behaviour

On resume, skipped if `flow.state.executive_product_summary` is already set. The saved content is restored from `working_ideas.executive_product_summary`.

---

## Data Flow

```
Input:  flow.state.executive_summary.latest_content
        flow.state.idea
Output: flow.state.executive_product_summary
Next:   → Engineering Plan Flow (Phase 1.5b, primary input)
        → UX Design Flow (Post-PRD, primary input)
        → Section Drafting Flow (Phase 2, replaces raw exec summary as context)
        → Jira Ticketing Flow (context for skeleton generation)
```

---

## Source Files

- `flows/_ceo_eng_review.py` — `run_ceo_review()` implementation
- `agents/ceo_reviewer/agent.py` — agent factory
- `agents/ceo_reviewer/config/agent.yaml` — role, goal, backstory
- `agents/ceo_reviewer/config/tasks.yaml` — task definitions

---

See also: [[PRD Flow]], [[CEO Reviewer]], [[Executive Summary Flow|Step 2 — Executive Summary Flow]], [[Engineering Plan Flow|Step 6 — Engineering Plan Flow]]


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
