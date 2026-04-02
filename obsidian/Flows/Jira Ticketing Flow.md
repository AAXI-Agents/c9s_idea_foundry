---
tags:
  - flows
  - pipeline
---

# Jira Ticketing Flow

> Post-PRD — 5-phase interactive Jira ticket creation with approval gates at each phase.

| Field | Value |
|-------|-------|
| **Phase** | Post-Completion (5 sub-phases) |
| **Agents** | [[Orchestrator]] (Jira PM, Architect), [[Staff Engineer]], [[QA Lead]], [[QA Engineer]] |
| **LLM Tier** | Research (Gemini) |
| **Source** | `orchestrator/_jira.py`, `flows/_finalization.py` |
| **Invariant** | Jira tickets must NEVER be created without explicit user approval |

---

## Purpose

Create structured Jira tickets (Epics, Stories, Sub-tasks, Review tickets, QA test tickets) from the completed PRD through a 5-phase approval workflow. Each phase requires user approval before proceeding. Autonomous paths must always use `confluence_only=True` to prevent unapproved ticket creation.

---

## Phase Routing

```
run_post_completion(flow) → None
```

Routes based on callbacks:
- **Phased** (has `jira_skeleton_approval_callback`): Interactive 5-phase Jira
- **Auto** (no callback): Confluence-only publishing, no Jira

---

## Phase 1 — Skeleton Generation

```
build_jira_skeleton_stage(flow, require_confluence=True) → AgentStage
```

### Step 1 — Skip Check

Skips if:
- No Jira credentials
- No Gemini credentials
- Skeleton already generated
- No PRD content

### Step 2 — Skeleton Generation

- Agent: `create_jira_product_manager_agent(project_id, run_id)`
- Task: `generate_jira_skeleton_task`
- Input:
  - `{page_title}`: `make_page_title(flow.state.idea)`
  - `{executive_summary}`: executive product summary or finalized idea
  - `{functional_requirements}`: from draft section
  - `{additional_prd_context}`: Engineering Plan + UX URL
- Output: structured outline with Epic titles and Story titles (no descriptions)

### Step 3 — State Update

- `flow.state.jira_skeleton = result.output`
- `flow.state.jira_phase = "skeleton_pending"`
- Persists via `save_jira_skeleton()`

### Step 4 — User Approval

```
jira_skeleton_approval_callback(skeleton, run_id) → (action, feedback)
```

- User reviews skeleton outline
- Can approve, provide feedback, or decline
- On approve: `flow.state.jira_phase = "skeleton_approved"`

---

## Phase 2 — Epics & Stories Creation

```
build_jira_epics_stories_stage(flow, require_confluence=True) → AgentStage
```

### Step 1 — Skip Check

Skips if `jira_phase != "skeleton_approved"` or no skeleton

### Step 2 — Epic Creation

- Task: `create_jira_epic_task`
- Creates one Epic per key feature area
- Extracts `epic_key` from output
- Appends to MongoDB via `append_jira_ticket()`

### Step 3 — Stories Creation

- Task: `create_jira_stories_task`
- Input:
  - `{approved_skeleton}`: the approved skeleton
  - `{functional_requirements}`: from PRD
  - `{additional_prd_context}`: Engineering Plan + UX URL
  - `{epic_key}`: from Step 2
- Stories organized per Epic into: Data Persistence, Data Layer, Data Presentation, App & Data Security
- Extracts story keys and appends to MongoDB

### Step 4 — State Update

- `flow.state.jira_epics_stories_output = result.output`
- `flow.state.jira_phase = "epics_stories_done"`
- Persists via `save_jira_epics_stories_output()`

### Step 5 — User Review

```
jira_review_callback(output, run_id) → bool
```

- User reviews created Epics and Stories
- If proceed: `flow.state.jira_phase = "subtasks_ready"`

---

## Phase 3 — Sub-task Creation

```
build_jira_subtasks_stage(flow, require_confluence=True) → AgentStage
```

### Step 1 — Skip Check

Skips if `jira_phase != "subtasks_ready"`

### Step 2 — Sub-task Generation

- Agent: `create_jira_architect_tech_lead_agent(project_id, run_id)`
- Task: `create_jira_tasks_task`
- Input:
  - `{stories_output}`: Epics + Stories from Phase 2
  - `{functional_requirements}`: from PRD
  - `{additional_prd_context}`: Engineering Plan + UX URL
- Creates implementation sub-tasks under each Story
- Extracts subtask keys and appends to MongoDB

### Step 3 — State Update

- `flow.state.jira_output = f"{epics+stories}\nSub-Tasks: {subtasks}"`
- `flow.state.jira_phase = "subtasks_done"`

---

## Phase 4 — Review Sub-tasks (Staff Engineer + QA Lead)

```
build_jira_review_subtasks_stage(flow, require_confluence=True) → AgentStage
```

### Step 1 — Skip Check

Skips if `jira_phase != "subtasks_done"`

### Step 2 — Parallel Review Agents

Two agents run in parallel:

**Staff Engineer** (`create_staff_engineer(project_id, run_id)`):
- Task: `create_staff_engineer_review_subtasks_task`
- Creates one `[Staff Eng Review]` sub-task per User Story
- Audit: N+1 queries, race conditions, stale reads, trust boundaries, missing indexes, escaping bugs, broken invariants, bad retry logic, schema migration risks
- Category: `"staff-review"`

**QA Lead** (`create_qa_lead(project_id, run_id)`):
- Task: `create_qa_lead_review_subtasks_task`
- Creates one `[QA Lead Review]` sub-task per User Story
- Review: acceptance criteria completeness, test coverage gaps, negative tests, integration tests, regression risk, data integrity, performance criteria
- Category: `"qa-lead-review"`

### Step 3 — State Update

- `flow.state.jira_review_output = result.output`
- `flow.state.jira_phase = "review_done"`

---

## Phase 5 — QA Test Sub-tasks

```
build_jira_qa_test_subtasks_stage(flow, require_confluence=True) → AgentStage
```

### Step 1 — Skip Check

Skips if `jira_phase != "review_done"`

### Step 2 — QA Test Generation

- Agent: `create_qa_engineer(project_id, run_id)`
- Task: `create_qa_engineer_test_subtasks_task`
- Creates one `[QA Test]` counter-ticket per implementation sub-task
- Tests: edge cases (boundary values, concurrent access, state transitions), security (injection, auth bypass, CSRF/SSRF), rendering (empty/loading/error states, responsive, accessibility)
- Category: `"qa-test"`

### Step 3 — State Update

- `flow.state.jira_qa_test_output = result.output`
- `flow.state.jira_phase = "qa_test_done"`

---

## Jira Phase State Machine

```
(none) → skeleton_pending → skeleton_approved → epics_stories_done
  → subtasks_ready → subtasks_done → review_done → qa_test_done
```

---

## Progress Events

| Event | When |
|-------|------|
| `jira_skeleton_start` | Skeleton generation begins |
| `jira_skeleton_ready` | Skeleton ready for user review |
| `jira_skeleton_approved` | User approved skeleton |
| `jira_epics_stories_start` | Epic + Story creation begins |
| `jira_epics_stories_complete` | Epics and Stories created |
| `jira_subtasks_start` | Sub-task creation begins |
| `jira_published` | All implementation tickets created |
| `jira_review_subtasks_start` | Staff Eng + QA Lead reviews begin |
| `jira_review_subtasks_complete` | Review sub-tasks created |
| `jira_qa_test_subtasks_start` | QA test tickets begin |
| `jira_qa_test_subtasks_complete` | QA test tickets created |

---

## Jira Approval Gate Invariant

> Jira tickets must **never** be created without explicit user approval.

Enforced by 23 regression tests in `tests/flows/test_jira_approval_gate.py`.

- **Autonomous paths**: Must pass `confluence_only=True` to crew builders
- **Interactive paths**: Must use 3-phase approval flow (skeleton → Epics/Stories → Sub-tasks)
- **Restart paths**: Must pass `interactive=True` to `kick_off_prd_flow`
- **New delivery paths**: Add a regression test to `test_jira_approval_gate.py`

---

## Resume Behaviour

On resume, each phase checks `jira_phase` state:
- Resumes from the next unfinished phase
- Previously created tickets are not re-created (idempotent)
- Approval gates re-fire for phases not yet approved

---

## MongoDB Persistence

| Operation | When |
|-----------|------|
| `save_jira_skeleton()` | After Phase 1 skeleton generation |
| `save_jira_epics_stories_output()` | After Phase 2 epic + story creation |
| `append_jira_ticket(run_id, key, category)` | After each ticket creation |
| `upsert_delivery_record()` | After Jira completion |

---

## Data Flow

```
Input:  flow.state.final_prd
        flow.state.executive_product_summary
        flow.state.engineering_plan
        flow.state.ux_design_content (context)
        flow.state.confluence_url (link in tickets)
Output: flow.state.jira_skeleton
        flow.state.jira_epics_stories_output
        flow.state.jira_output
        flow.state.jira_review_output
        flow.state.jira_qa_test_output
        flow.state.jira_phase (state machine)
```

---

## Source Files

- `orchestrator/_jira.py` — all 5 stage factories and implementations
- `flows/_finalization.py` — `run_post_completion()`, `_run_phased_post_completion()`
- `agents/orchestrator/agent.py` — Jira PM, Architect agent factories
- `agents/staff_engineer/agent.py` — Staff Engineer agent
- `agents/qa_lead/agent.py` — QA Lead agent
- `agents/qa_engineer/agent.py` — QA Engineer agent

---

See also: [[PRD Flow]], [[Orchestrator]], [[Staff Engineer]], [[QA Lead]], [[QA Engineer]], [[Jira Integration]], [[Finalization Flow|Step 7 — Finalization Flow]]


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
