# Jira Integration

> Phased Jira ticket creation for completed PRDs.

## Phased Approach (v0.19.0, expanded from v0.13.2)

Jira ticketing uses a 5-phase user-approval workflow:

### Phase 1: Skeleton Outline
- Agent generates a skeletal structure from functional requirements
- User reviews and approves or requests regeneration
- Stored in MongoDB via `save_jira_skeleton()`
- `jira_phase`: `''` → `skeleton_pending`

### Phase 2: Epics & Stories
- Creates Jira Epics with inter-Epic dependencies
- Stories categorised as:
  - Data Persistence
  - Data Layer
  - Data Presentation
  - App & Data Security
- `jira_phase`: `epics_stories_pending` → `epics_stories_done`

### Phase 3: Sub-tasks
- Sub-tasks with 7 required sections:
  1. Reasoning
  2. Instructions
  3. Sample Data
  4. Guard Rails
  5. Definition of Done
  6. Test Cases for QE
  7. Unit Test Cases
- Dependency chains between sub-tasks
- User reviews before finalising
- `jira_phase`: `subtasks_pending` → `subtasks_done`

### Phase 4: Review Sub-tasks (v0.19.0)
- **Staff Engineer** creates one `[Staff Eng Review]` sub-task per Story — structural audit (N+1 queries, race conditions, trust boundaries, missing indexes, etc.)
- **QA Lead** creates one `[QA Lead Review]` sub-task per Story — test methodology review (acceptance criteria, coverage gaps, negative tests, regression risk, etc.)
- Both run sequentially; each review sub-task is blocked by the last implementation sub-task
- `jira_phase`: `review_ready` → `review_done`

### Phase 5: QA Test Sub-tasks (v0.19.0)
- **QA Engineer** creates one `[QA Test]` counter-ticket per implementation sub-task (skipping review/unit test sub-tasks)
- Covers edge cases (boundary values, concurrent access, partial failures), security (injection, auth bypass, CSRF/SSRF), and rendering (empty/loading/error states, responsive, accessibility)
- Each QA test sub-task is blocked by the corresponding implementation sub-task
- `jira_phase`: `qa_test_ready` → `qa_test_done`

## `jira_phase` Values

| Phase | Meaning |
|-------|---------|
| `''` / `None` | Not started |
| `skeleton_pending` | Skeleton generated, awaiting approval |
| `epics_stories_pending` | Epics/Stories being created |
| `epics_stories_done` | Epics/Stories complete |
| `subtasks_pending` | Sub-tasks generated, awaiting approval |
| `subtasks_done` | Dev sub-tasks complete |
| `review_ready` | Ready for Staff Eng + QA Lead review sub-tasks |
| `review_pending` | Review sub-tasks being created |
| `review_done` | Review sub-tasks complete |
| `qa_test_ready` | Ready for QA Engineer test sub-tasks |
| `qa_test_pending` | QA test sub-tasks being created |
| `qa_test_done` | All 5 phases complete |

## Key Files

| File | Purpose |
|------|---------|
| `tools/jira_tool.py` | REST API shim → `jira/` package |
| `tools/jira/` | Operations, helpers, ADF converter |
| `orchestrator/_jira.py` | Stage builders (skeleton, epics, subtasks, reviews, QA tests) |
| `agents/staff_engineer/` | Staff Engineer agent (review sub-tasks) |
| `agents/qa_lead/` | QA Lead agent (review sub-tasks) |
| `agents/qa_engineer/` | QA Engineer agent (QA test sub-tasks) |
| `flows/_finalization.py` | Phased post-completion Jira execution |

## Jira API

- Uses REST API **v3** (migrated from v2 in v0.10.2 to fix 410 Gone errors)
- Descriptions use **Atlassian Document Format (ADF)** (v0.12.0)
- `_markdown_to_adf()` converter handles headings, bold, code, lists, links, horizontal rules

## MongoDB Persistence

- Tickets stored in `productRequirements.jira_tickets[]` with type, key, URL
- `jira_completed` flag in delivery record
- `jira_phase` persisted on `workingIdeas` document
- Skeleton text persisted via `save_jira_skeleton()` / `get_jira_skeleton()`

## Autonomous Delivery Protection (v0.9.11+)

The startup delivery scheduler checks `jira_phase` and skips items managed by the interactive flow, preventing duplicate ticket creation.

## Post-Confluence Next Step (v0.15.9)

After Confluence publish completes (via product list button or publish intent), the system offers a "Create Jira Skeleton" button as the next step. This button:
- Uses action_id `delivery_create_jira` but routes to skeleton generation (Phase 1)
- Only appears when Jira credentials are configured
- Includes heartbeat progress messages during the Confluence crew execution
- The button label explicitly says "Create Jira Skeleton" (not "Create Jira Tickets") to match the phased workflow

---

See also: [[Confluence Integration]], [[Slack Integration]], [[Orchestrator Overview]]
