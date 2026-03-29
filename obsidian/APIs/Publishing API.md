# Publishing API

> Publish completed PRDs to Confluence and create Jira tickets.

**Base path**: `/publishing`
**Auth**: SSO Bearer token (all endpoints)

---

## Endpoints

| Method | Path | Auth | Response | Status | Purpose |
|--------|------|------|----------|--------|---------|
| `GET` | `/publishing/pending` | SSO | `PendingListResponse` | 200 | List PRDs pending delivery |
| `POST` | `/publishing/confluence/all` | SSO | `ConfluenceBatchResult` | 200 | Batch-publish all pending to Confluence |
| `POST` | `/publishing/confluence/{run_id}` | SSO | `ConfluencePublishResult` | 200 | Publish single PRD to Confluence |
| `POST` | `/publishing/jira/all` | SSO | `JiraBatchResult` | 200 | Batch-create Jira tickets for all pending |
| `POST` | `/publishing/jira/{run_id}` | SSO | `JiraCreateResult` | 200 | Create Jira tickets for one PRD |
| `POST` | `/publishing/all` | SSO | `CombinedPublishResult` | 200 | Confluence + Jira for all pending |
| `POST` | `/publishing/all/{run_id}` | SSO | `CombinedPublishResult` | 200 | Confluence + Jira for single PRD |
| `GET` | `/publishing/status/{run_id}` | SSO | `DeliveryStatusResponse` | 200 | Check delivery status for a run |
| `GET` | `/publishing/automation/status` | SSO | `WatcherStatusResponse` | 200 | File watcher & scheduler status |

---

## Response Schemas

### PendingPRDItem

```json
{
  "run_id": "a1b2c3d4e5f6",
  "title": "Dark Mode Dashboard Feature",
  "source": "mongodb",
  "output_file": "/output/a1b2c3d4e5f6/product requirement documents/prd.md",
  "confluence_published": false,
  "confluence_url": "",
  "jira_completed": false,
  "jira_tickets": [],
  "status": "new"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Unique flow run identifier |
| `title` | `string` | — | Page title derived from the PRD (e.g. `"Dark Mode Dashboard Feature"`) |
| `source` | `string` | `"mongodb"` | Discovery source: `"mongodb"` (from database) or `"disk"` (from filesystem scan) |
| `output_file` | `string` | `""` | Absolute path to the PRD markdown file on disk |
| `confluence_published` | `bool` | `false` | Whether a Confluence page has been published |
| `confluence_url` | `string` | `""` | URL of the Confluence page — empty if unpublished |
| `jira_completed` | `bool` | `false` | Whether Jira tickets have been created from this PRD |
| `jira_tickets` | `dict[]` | `[]` | List of Jira ticket objects (key, summary, type, url) |
| `status` | `string` | `"new"` | Delivery status: `"new"` (not yet delivered), `"inprogress"` (delivery underway), `"completed"` (fully delivered) |

### PendingListResponse

`GET /publishing/pending`

```json
{
  "count": 3,
  "items": [ /* PendingPRDItem[] */ ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Total number of pending items |
| `items` | `PendingPRDItem[]` | Array of pending PRD items |

---

### ConfluencePublishResult

`POST /publishing/confluence/{run_id}`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "title": "Dark Mode Dashboard Feature",
  "url": "https://wiki.example.com/pages/12345",
  "page_id": "12345",
  "action": "created"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Run identifier |
| `title` | `string` | `""` | Confluence page title |
| `url` | `string` | `""` | Full URL of the Confluence page |
| `page_id` | `string` | `""` | Confluence page ID (numeric string) |
| `action` | `string` | `"created"` | `"created"` for new pages, `"updated"` for existing page updates |

### ConfluenceBatchResult

`POST /publishing/confluence/all`

```json
{
  "published": 3,
  "failed": 1,
  "results": [ /* ConfluencePublishResult[] */ ],
  "errors": [ { "run_id": "...", "error": "..." } ],
  "message": "Published 3 of 4 PRDs to Confluence"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `published` | `int` | `0` | Number of PRDs successfully published |
| `failed` | `int` | `0` | Number that failed to publish |
| `results` | `ConfluencePublishResult[]` | `[]` | Per-item success results |
| `errors` | `dict[]` | `[]` | Per-item error details (run_id + error message) |
| `message` | `string` | `""` | Summary message |

---

### JiraCreateResult

`POST /publishing/jira/{run_id}`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "jira_completed": true,
  "ticket_keys": ["MCR-101", "MCR-102", "MCR-103"],
  "progress": ["Created Epic MCR-101", "Created Story MCR-102", "Created Sub-task MCR-103"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Run identifier |
| `jira_completed` | `bool` | `true` | Whether Jira ticket creation succeeded |
| `ticket_keys` | `string[]` | `[]` | Created Jira issue keys (e.g. `["MCR-101", "MCR-102"]`) |
| `progress` | `string[]` | `[]` | Step-by-step progress messages from the Jira crew |

### JiraBatchResult

`POST /publishing/jira/all`

```json
{
  "completed": 3,
  "failed": 0,
  "results": [ /* JiraCreateResult[] */ ],
  "errors": [],
  "message": "Created Jira tickets for 3 PRDs"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `completed` | `int` | `0` | Number successfully completed |
| `failed` | `int` | `0` | Number that failed |
| `results` | `JiraCreateResult[]` | `[]` | Per-item success results |
| `errors` | `dict[]` | `[]` | Per-item error details |
| `message` | `string` | `""` | Summary message |

---

### CombinedPublishResult

`POST /publishing/all` or `POST /publishing/all/{run_id}`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "confluence": {
    "run_id": "a1b2c3d4e5f6",
    "title": "Dark Mode Dashboard Feature",
    "url": "https://wiki.example.com/pages/12345",
    "page_id": "12345",
    "action": "created"
  },
  "jira": {
    "run_id": "a1b2c3d4e5f6",
    "jira_completed": true,
    "ticket_keys": ["MCR-101"]
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | `""` | Run identifier (single-run) — empty for batch operations |
| `confluence` | `dict` | `{}` | Confluence publish result (same shape as `ConfluencePublishResult` or `ConfluenceBatchResult`) |
| `jira` | `dict` | `{}` | Jira creation result (same shape as `JiraCreateResult` or `JiraBatchResult`) |

---

### DeliveryStatusResponse

`GET /publishing/status/{run_id}`

```json
{
  "run_id": "a1b2c3d4e5f6",
  "confluence_published": true,
  "confluence_url": "https://wiki.example.com/pages/12345",
  "confluence_page_id": "12345",
  "jira_completed": true,
  "jira_tickets": [
    { "key": "MCR-101", "summary": "Epic: Dark Mode", "type": "Epic" }
  ],
  "status": "completed",
  "error": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `run_id` | `string` | — | Run identifier |
| `confluence_published` | `bool` | `false` | Whether Confluence page exists |
| `confluence_url` | `string` | `""` | Confluence page URL |
| `confluence_page_id` | `string` | `""` | Confluence page ID |
| `jira_completed` | `bool` | `false` | Whether Jira tickets have been created |
| `jira_tickets` | `dict[]` | `[]` | Array of created Jira tickets with key, summary, type |
| `status` | `string` | `"new"` | Delivery status: `"new"`, `"inprogress"`, or `"completed"` |
| `error` | `string \| null` | `null` | Last error message — `null` if no errors |

---

### WatcherStatusResponse

`GET /publishing/automation/status`

```json
{
  "watcher_running": true,
  "watcher_directory": "/output",
  "scheduler_running": true,
  "scheduler_interval_seconds": 300
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watcher_running` | `bool` | `false` | Whether the filesystem watcher is actively monitoring for new PRD files |
| `watcher_directory` | `string` | `""` | Directory being watched for new PRD output files |
| `scheduler_running` | `bool` | `false` | Whether the cron scheduler is active for periodic publishing checks |
| `scheduler_interval_seconds` | `int` | `0` | Scan interval in seconds (e.g. 300 = every 5 minutes) |

---

## Error Responses

| Status | Condition | Body |
|--------|-----------|------|
| 404 | `run_id` not found | `PublishingErrorResponse` |
| 503 | Confluence/Jira credentials not configured | `PublishingErrorResponse` |
| 500 | Unexpected server error | `PublishingErrorResponse` |

### PublishingErrorResponse

```json
{
  "error_code": "CONFLUENCE_NOT_CONFIGURED",
  "message": "Confluence credentials are not configured",
  "detail": "Set CONFLUENCE_URL, CONFLUENCE_USERNAME, and CONFLUENCE_API_TOKEN"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error_code` | `string` | Machine-readable error code |
| `message` | `string` | Human-readable error message |
| `detail` | `string` | Additional diagnostic information |

---

See also: [[API Overview]], [[PRD Flow API]], [[Confluence Integration]], [[Jira Integration]]
