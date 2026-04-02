---
tags:
  - flows
  - pipeline
---

# Confluence Publishing Flow

> Post-PRD — Publish the finalized PRD to Atlassian Confluence.

| Field | Value |
|-------|-------|
| **Phase** | Post-Completion |
| **Agent** | [[Orchestrator]] |
| **LLM Tier** | Research (Gemini) |
| **Source** | `orchestrator/_confluence.py` |
| **Stage Factory** | `build_confluence_publish_stage(flow)` |

---

## Purpose

Publish the finalized PRD markdown document to an Atlassian Confluence space. Supports both creating new pages and updating existing ones. Uses project-level Confluence configuration for space key and parent page.

---

## Step-by-Step Flow

### Step 1 — Skip Check

```
_should_skip() → bool
```

Skips this phase if:
- No Confluence credentials (`CONFLUENCE_URL`, `CONFLUENCE_USERNAME`, `CONFLUENCE_API_TOKEN` not set)
- No Gemini credentials
- Already published (`confluence_url` is set)
- No final PRD content

### Step 2 — Resolve Confluence Config

- Reads project-level configuration for:
  - `space_key` — Confluence space
  - `parent_id` — parent page ID (for nesting)
- Checks for existing delivery record with `page_id` (update vs. create)

### Step 3 — Publish

```
publish_to_confluence(title, markdown_content, run_id, page_id=None)
```

- `title`: generated via `make_page_title(flow.state.idea)`
- `markdown_content`: `flow.state.final_prd`
- `page_id`: existing page ID for updates, or `None` for new page
- Returns `StageResult(output=f"{action}|{page_id}|{url}")`

### Step 4 — State Update

```
_apply(result) → None
```

- Extracts `page_id` and `url` from output string
- `flow.state.confluence_url = page_url`

### Step 5 — Delivery Record

```
upsert_delivery_record(run_id, confluence_published=True, confluence_url=url, confluence_page_id=page_id)
```

- Creates or updates the delivery record in `productRequirements` collection
- Tracks publish status for startup recovery

---

## Progress Events

| Event | When |
|-------|------|
| `confluence_published` | Page published/updated | `url` |
| `pipeline_stage_skipped` | Skipped (no credentials or already published) |

---

## Resume Behaviour

On resume:
- Skipped if `flow.state.confluence_url` is already set
- On server startup: `_startup_review.py` scans for completed ideas without Confluence pages and auto-publishes

---

## Startup Auto-Publish

The `_startup_review.py` module discovers completed PRDs without Confluence pages on server start:

```
_discover_publishable_prds() → list[WorkingIdea]
```

- Uses two-phase query: projection first (fast), then full docs only for unpublished
- Auto-publishes each via `build_startup_delivery_crew(item, confluence_only=True)`
- Always `confluence_only=True` — no Jira on autonomous paths

---

## MongoDB Persistence

- `upsert_delivery_record()` — creates/updates `productRequirements` with Confluence status
- Fields: `confluence_published`, `confluence_url`, `confluence_page_id`

---

## Data Flow

```
Input:  flow.state.final_prd (assembled markdown)
        flow.state.idea (for page title)
        Project config (space_key, parent_id)
Output: flow.state.confluence_url
        Delivery record in productRequirements
```

---

## Source Files

- `orchestrator/_confluence.py` — stage factory and implementation
- `orchestrator/_startup_review.py` — startup auto-publish logic
- `orchestrator/_startup_delivery.py` — startup delivery crew builder
- `tools/confluence_tool.py` — Confluence API client

---

See also: [[PRD Flow]], [[Orchestrator]], [[Confluence Integration]], [[Finalization Flow|Step 7 — Finalization Flow]]


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
