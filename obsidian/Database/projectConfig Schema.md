# projectConfig Schema

> Per-project configuration — Confluence, Jira, Figma settings, and reference materials.

**Collection**: `projectConfig`
**Primary Key**: `project_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Projects API]] | `GET /projects` | Lists all projects (paginated) |
| [[Projects API]] | `GET /projects/{project_id}` | Reads single project |
| [[Projects API]] | `POST /projects` | Creates new project |
| [[Projects API]] | `PATCH /projects/{project_id}` | Partial update |
| [[Projects API]] | `DELETE /projects/{project_id}` | Deletes project |
| [[PRD Flow API]] | All flow endpoints | Reads project config for Confluence/Jira keys |
| [[Slack API]] | Session management | Reads project config for active session context |
| [[Publishing API]] | Publishing endpoints | Reads Confluence space key and Jira project key |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_id` | `string` | **Yes** | *UUID hex* | Unique project identifier — generated as UUID hex on creation |
| `name` | `string` | **Yes** | — | Human-readable project display name (1–256 chars) |
| `confluence_space_key` | `string` | No | `""` | Confluence space key for PRD publishing (e.g. `"PROD"`, `"ENG"`) |
| `jira_project_key` | `string` | No | `""` | Jira project key for ticket creation (e.g. `"MCR"`, `"FEAT"`) |
| `confluence_parent_id` | `string` | No | `""` | Confluence parent page ID — PRDs published as child pages under this |
| `figma_api_key` | `string` | No | `""` | Figma personal access token for design integration. **Write-only** — never exposed in API responses (API returns `figma_api_key_set: bool` instead) |
| `figma_team_id` | `string` | No | `""` | Figma team ID — used to list and fetch design files |
| `figma_oauth_token` | `string` | No | `""` | Figma OAuth2 access token (rotating) — managed by OAuth flow |
| `figma_oauth_refresh_token` | `string` | No | `""` | Figma OAuth2 refresh token — used to obtain new access tokens |
| `figma_oauth_expires_at` | `string (ISO-8601)` | No | `""` | When the Figma OAuth token expires — triggers auto-refresh |
| `reference_urls` | `list[string]` | No | `[]` | Public reference URLs for context (specs, design docs, competitor links). Max 20 items |
| `slack_file_refs` | `list[dict]` | No | `[]` | Documents uploaded via Slack. Each element: `{ file_id: str, name: str, url: str, uploaded_at: str }` |
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

See also: [[MongoDB Schema]], [[Projects API]], [[Environment Variables]]


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
