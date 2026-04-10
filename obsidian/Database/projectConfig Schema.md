---
tags:
  - database
  - mongodb
---

# projectConfig Schema

> Per-project configuration — Confluence, Jira settings, and reference materials.

**Collection**: `projectConfig`
**Primary Key**: `project_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Projects/]] | `GET /projects` | Lists all projects (paginated) |
| [[Projects/]] | `GET /projects/{project_id}` | Reads single project |
| [[Projects/]] | `POST /projects` | Creates new project |
| [[Projects/]] | `PATCH /projects/{project_id}` | Partial update |
| [[Projects/]] | `DELETE /projects/{project_id}` | Deletes project |
| [[PRD Flow/]] | All flow endpoints | Reads project config for Confluence/Jira keys |
| [[Slack/]] | Session management | Reads project config for active session context |
| [[Publishing/]] | Publishing endpoints | Reads Confluence space key and Jira project key |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_id` | `string` | **Yes** | *UUID hex* | Unique project identifier — generated as UUID hex on creation |
| `name` | `string` | **Yes** | — | Human-readable project display name (1–256 chars) |
| `description` | `string` | No | `""` | Project description text — shown on project cards and detail pages (max 2,000 chars) |
| `confluence_space_key` | `string` | No | `""` | Confluence space key for PRD publishing (e.g. `"PROD"`, `"ENG"`) |
| `jira_project_key` | `string` | No | `""` | Jira project key for ticket creation (e.g. `"MCR"`, `"FEAT"`) |
| `confluence_parent_id` | `string` | No | `""` | Confluence parent page ID — PRDs published as child pages under this |
| `reference_urls` | `list[string]` | No | `[]` | Public reference URLs for context (specs, design docs, competitor links). Max 20 items |
| `slack_file_refs` | `list[dict]` | No | `[]` | Documents uploaded via Slack. Each element: `{ file_id: str, name: str, url: str, uploaded_at: str }` |
| `design_preferences` | `dict` | No | `{}` | UX/UI design style preferences: `{ style: str, brand_colors: [str], typography: str }` |
| `review_checklists` | `list[dict]` | No | `[]` | Custom review checklists: `{ name: str, items: [str] }` |
| `technical_profile` | `dict` | No | `{}` | Tech stack profile: `{ languages: [str], frameworks: [str], infra: [str] }` |
| `board_style` | `string` | No | `"scrum"` | Jira board style: `"scrum"` (Epic/Story/Sub-task hierarchy) or `"kanban"` (flat Tasks with priority labels) |
| `created_at` | `string (ISO-8601)` | **Yes** | *now* | When the project was created |
| `updated_at` | `string (ISO-8601)` | **Yes** | *now* | Last modification timestamp |

---

## Slack File Reference

Each element in the `slack_file_refs` array:

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | `string` | Slack file ID |
| `name` | `string` | Original filename |
| `url` | `string` | Slack file URL |
| `uploaded_at` | `string` | ISO-8601 upload timestamp |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `project_id` | Unique, Ascending | Primary key lookup |
| `name` | Ascending | Lookup by project name |
| `created_at DESC` | Single | Paginated list sorted by newest first (GET /projects) |

---

## Repository Functions

**Source**: `mongodb/project_config/repository.py`

| Function | Purpose |
|----------|---------|
| `create_project()` | Create new project configuration |
| `get_project(project_id)` | Fetch project by ID |
| `get_project_by_name(name)` | Fetch project by name |
| `list_projects(limit)` | List all projects, newest first |
| `get_project_for_run(run_id)` | Look up project for a PRD run (via workingIdeas) |
| `update_project()` | Update project fields (partial update) |
| `add_reference_url()` | Append reference URL (no duplicates) |
| `add_slack_file_ref()` | Append Slack file reference |
| `remove_slack_file_ref()` | Remove Slack file from list |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[workingIdeas Schema]] | Referenced by `workingIdeas.project_id` (1:N) |
| [[projectMemory Schema]] | Referenced by `projectMemory.project_id` (1:1) |
| [[userSession Schema]] | Referenced by `userSession.project_id` (N:1) |
| [[agentInteraction Schema]] | Referenced by `agentInteraction.project_id` (N:1) |
| [[userSuggestions Schema]] | Referenced by `userSuggestions.project_id` (N:1) |

---

See also: [[MongoDB Schema]], [[Projects/]], [[Environment Variables]]


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
