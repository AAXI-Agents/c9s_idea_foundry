# Jira Integration

> Phased Jira ticket creation for completed PRDs.

## Phased Approach (v0.13.2+)

Jira ticketing uses a 3-phase user-approval workflow:

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

## `jira_phase` Values

| Phase | Meaning |
|-------|---------|
| `''` / `None` | Not started |
| `skeleton_pending` | Skeleton generated, awaiting approval |
| `epics_stories_pending` | Epics/Stories being created |
| `epics_stories_done` | Epics/Stories complete |
| `subtasks_pending` | Sub-tasks generated, awaiting approval |
| `subtasks_done` | All phases complete |

## Key Files

| File | Purpose |
|------|---------|
| `tools/jira_tool.py` | REST API shim → `jira/` package |
| `tools/jira/` | Operations, helpers, ADF converter |
| `orchestrator/_jira.py` | Stage builders (skeleton, epics, subtasks) |
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

---

See also: [[Confluence Integration]], [[Slack Integration]], [[Orchestrator Overview]]
