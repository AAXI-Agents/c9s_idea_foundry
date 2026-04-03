---
tags:
  - database
  - mongodb
---

# projectMemory Schema

> Project-level memory store — behavioural guardrails, domain knowledge, and tools for agent context.

**Collection**: `projectMemory`
**Primary Key**: `project_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Slack/]] | `cmd_configure_memory` | Admin configures memory entries via Block Kit |
| CrewAI agents | Agent initialization | Loads memories into agent backstory via `get_memories_for_agent()` |
| Orchestrator | PRD flow | Enriches agent context with project-specific knowledge |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_id` | `string` | **Yes** | — | FK → `projectConfig.project_id`. Primary key — one memory document per project |
| `idea_iteration` | `list[dict]` | No | `[]` | Behavioural guardrails for idea iteration. Instructions telling agents how to refine ideas for this project (e.g. "Focus on mobile-first", "Always consider accessibility") |
| `knowledge` | `list[dict]` | No | `[]` | Domain context for agents — links, documents, and notes. Each entry has a `kind` field for categorization |
| `tools` | `list[dict]` | No | `[]` | Technologies, frameworks, and services used by this project (e.g. "React Native", "PostgreSQL"). Helps agents generate technically appropriate PRDs |
| `created_at` | `string (ISO-8601)` | **Yes** | *now* | When project memory was initialized |
| `updated_at` | `string (ISO-8601)` | **Yes** | *now* | Last update timestamp |

---

## Memory Entry Format

Each element in `idea_iteration`, `knowledge`, and `tools` arrays:

### idea_iteration / tools entry

| Field | Type | Description |
|-------|------|-------------|
| `content` | `string` | The instruction, tool name, or guideline text |
| `added_by` | `string` | Slack user ID who added this entry |
| `added_at` | `string` | ISO-8601 timestamp when entry was added |

### knowledge entry

| Field | Type | Description |
|-------|------|-------------|
| `content` | `string` | The knowledge content (URL, document text, or note) |
| `kind` | `string` | Category: `"link"` (URL reference), `"document"` (uploaded doc text), or `"note"` (free-form note) |
| `added_by` | `string` | Slack user ID who added this entry |
| `added_at` | `string` | ISO-8601 timestamp when entry was added |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `project_id` | Unique, Ascending | Primary key lookup (1:1 with projectConfig) |

---

## Repository Functions

**Source**: `mongodb/project_memory/repository.py`

| Function | Purpose |
|----------|---------|
| `upsert_project_memory()` | Ensure document exists — creates empty scaffold if not |
| `get_project_memory()` | Fetch full project memory document |
| `list_memory_entries(project_id, category)` | Return entries in a specific category |
| `get_memories_for_agent()` | Load memories relevant to an agent role (for backstory enrichment) |
| `add_memory_entry()` | Append entry to a category array |
| `replace_category_entries()` | Replace all entries in a category |
| `clear_category()` | Clear all entries in a category |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[projectConfig Schema]] | `project_id` → `projectConfig.project_id` (1:1) |

---

See also: [[MongoDB Schema]], [[Projects/]], [[Agent Roles]]


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
