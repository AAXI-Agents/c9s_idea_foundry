---
tags:
  - database
  - mongodb
---

# productRequirements Schema

> Completed PRD delivery records — tracks Confluence publishing and Jira ticket creation.

**Collection**: `productRequirements`
**Primary Key**: `run_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Publishing API]] | `GET /publishing/pending` | Queries records with status `new` or `inprogress` |
| [[Publishing API]] | `GET /publishing/status/{run_id}` | Reads full delivery status |
| [[Publishing API]] | `POST /publishing/confluence/{run_id}` | Updates Confluence fields on publish |
| [[Publishing API]] | `POST /publishing/jira/{run_id}` | Appends Jira tickets on creation |
| [[Publishing API]] | `POST /publishing/all` | Batch update Confluence + Jira |
| Orchestrator | Startup delivery | Checks for pending deliveries on server start |
| Orchestrator | Post-completion | Creates record when PRD flow completes |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `run_id` | `string` | **Yes** | — | Links to `workingIdeas.run_id`. Primary key for delivery tracking |
| `confluence_published` | `bool` | No | `false` | `true` once a Confluence page has been successfully published |
| `confluence_url` | `string` | No | `""` | Full URL of the published Confluence page — populated after publishing |
| `confluence_page_id` | `string` | No | `""` | Confluence page ID (numeric string) — used for updates and linking |
| `jira_completed` | `bool` | No | `false` | `true` once Jira tickets have been successfully created |
| `jira_output` | `string` | No | `""` | Agent summary text of created Jira tickets |
| `jira_tickets` | `list[dict]` | No | `[]` | Array of ticket records. Each element: `{ key: str, type: str, summary: str, url: str, reused: bool }` |
| `status` | `string` | No | `"new"` | Delivery workflow status (see Status Values below) |
| `created_at` | `string (ISO-8601)` | No | *now* | When the delivery record was first created |
| `updated_at` | `string (ISO-8601)` | No | *now* | Last update timestamp |
| `error` | `string \| null` | No | `null` | Last error message from a failed publish/ticketing attempt |

---

## Jira Ticket Record

Each element in the `jira_tickets` array:

| Field | Type | Description |
|-------|------|-------------|
| `key` | `string` | Jira issue key (e.g. `"MCR-101"`) |
| `type` | `string` | Issue type: `"Epic"`, `"Story"`, `"Sub-task"` |
| `summary` | `string` | Issue summary/title |
| `url` | `string` | Full URL to the Jira issue |
| `reused` | `bool` | `true` if an existing ticket was reused instead of creating a new one |

---

## Status Values

| Status | Description | Transitions to |
|--------|-------------|----------------|
| `new` | Record created but nothing delivered yet | `inprogress` |
| `inprogress` | Partially delivered (e.g. Confluence done, Jira pending) | `completed` |
| `completed` | Both Confluence and Jira delivery finished | (terminal) |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `run_id` | Unique, Ascending | Primary key lookup |
| `(status, created_at ASC)` | Compound | Find pending deliveries ordered by age |

---

## Repository Functions

**Source**: `mongodb/product_requirements/repository.py`

| Function | Purpose |
|----------|---------|
| `get_delivery_record(run_id)` | Fetch delivery record by run_id |
| `find_pending_delivery()` | Find records with status `new` or `inprogress` |
| `upsert_delivery_record()` | Create or update delivery record (idempotent) |
| `append_jira_ticket()` | Append single ticket to `jira_tickets` array atomically |
| `get_jira_tickets(run_id)` | Return `jira_tickets` array (or empty list) |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[workingIdeas Schema]] | `run_id` = `workingIdeas.run_id` (1:1) |

---

See also: [[MongoDB Schema]], [[Publishing API]], [[Confluence Integration]], [[Jira Integration]]


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
