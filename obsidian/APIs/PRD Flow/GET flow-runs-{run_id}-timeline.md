---
tags:
  - api
  - endpoints
  - prd
  - flow
---

# GET /flow/runs/{run_id}/timeline

> Unified PRD journey timeline — chronological events from idea to delivery.

**Method**: `GET`
**Path**: `/flow/runs/{run_id}/timeline`
**Auth**: SSO Bearer token
**Tags**: Flow Runs

---

## Request

| Param | Type | Location | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `run_id` | `string` | path | — | — | Flow run identifier |
| `limit` | `int` | query | `200` | 1–1000 | Max events to return |

---

## Response — 200

```json
{
  "run_id": "a1b2c3d4e5f6",
  "total_events": 12,
  "events": [
    {
      "timestamp": "2026-04-05T10:00:00",
      "event_type": "idea_submitted",
      "title": "Idea submitted",
      "detail": "Build a fitness tracking app...",
      "agent": "",
      "section_key": "",
      "iteration": 0,
      "score": "",
      "metadata": {}
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `string` | The run this timeline belongs to |
| `total_events` | `int` | Total number of events returned |
| `events` | `TimelineEvent[]` | Events sorted chronologically (oldest first) |

### TimelineEvent

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `string` | ISO-8601 timestamp |
| `event_type` | `string` | Event category (see below) |
| `title` | `string` | Short human-readable title |
| `detail` | `string` | Longer description or content excerpt |
| `agent` | `string` | Agent name involved (if any) |
| `section_key` | `string` | PRD section key (if applicable) |
| `iteration` | `int` | Iteration number (if applicable) |
| `score` | `string` | Quality score excerpt (if applicable) |
| `metadata` | `object` | Extra context |

### Event Types

| Type | Source Collection | Description |
|------|-------------------|-------------|
| `idea_submitted` | `workingIdeas` | Original idea submission |
| `idea_refined` | `workingIdeas` | Finalized/refined idea |
| `exec_summary_iteration` | `workingIdeas` | Executive summary iteration |
| `section_drafted` | `workingIdeas` | Section draft iteration |
| `job_status` | `crewJobs` | Job lifecycle (queued, started, completed) |
| `agent_interaction` | `agentInteraction` | Agent interaction event |
| `confluence_published` | `productRequirements` | Published to Confluence |
| `jira_created` | `productRequirements` | Jira tickets created |

---

## DB Algorithm

1. Query `workingIdeas` via `find_run_any_status(run_id)` — extract idea, refinement, executive summary iterations, section iterations, completion events
2. Query `crewJobs` via `find_job(run_id)` — extract queued/started lifecycle events
3. Query `agentInteraction` via `find_interactions(run_id=run_id, limit=limit)` — extract agent interaction events
4. Query `productRequirements` via `get_delivery_record(run_id)` — extract Confluence/Jira delivery events
5. Merge all events, sort by timestamp ascending, apply limit

---

## Errors

| Code | Description |
|------|-------------|
| 404 | Run not found |
| 500 | Internal server error |
| 503 | Service unavailable |

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
