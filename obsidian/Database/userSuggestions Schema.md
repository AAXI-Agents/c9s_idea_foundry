# userSuggestions Schema

> Tracks ambiguous user intents and clarification requests — self-learning data for improving intent classification.

**Collection**: `userSuggestions`
**Primary Key**: `suggestion_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Slack API]] | Events router | Logs suggestion when intent is ambiguous or unknown |
| Analytics | Monitoring | Reviews unrecognized patterns over time |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `suggestion_id` | `string` | **Yes** | *UUID hex* | Unique suggestion identifier. Primary key |
| `user_id` | `string \| null` | No | `null` | Slack user ID who triggered the ambiguous interaction |
| `project_id` | `string \| null` | No | `null` | FK → `projectConfig.project_id`. Project context when the suggestion was logged |
| `channel` | `string \| null` | No | `null` | Slack channel ID where the interaction occurred |
| `thread_ts` | `string \| null` | No | `null` | Slack thread timestamp where the interaction occurred |
| `user_message` | `string` | **Yes** | — | Raw original user message that was ambiguous |
| `agent_interpretation` | `string` | **Yes** | — | How the agent understood/classified the message |
| `suggestion_type` | `string` | **Yes** | — | Type of ambiguity: `"clarification_needed"` (agent asked for more info) or `"unknown_intent"` (could not classify at all) |
| `resolved` | `bool` | **Yes** | `false` | Whether the user subsequently clarified their intent |
| `resolved_intent` | `string \| null` | No | `null` | Final resolved intent after clarification (e.g. `"create_prd"`, `"publish"`) |
| `created_at` | `datetime (UTC)` | **Yes** | *now* | When the suggestion was logged |

---

## Suggestion Types

| Type | Description |
|------|-------------|
| `clarification_needed` | Agent recognized partial intent but needs more info (e.g. "Did you mean X or Y?") |
| `unknown_intent` | Agent could not classify the message into any known intent |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `suggestion_id` | Unique, Ascending | Primary key lookup |
| `(project_id, created_at DESC)` | Compound | Find suggestions for a project, newest first |
| `(user_id, created_at DESC)` | Compound | Find suggestions by user, newest first |

---

## Repository Functions

**Source**: `mongodb/user_suggestions/repository.py`

| Function | Purpose |
|----------|---------|
| `log_suggestion()` | Insert new suggestion document, returns `suggestion_id` |
| `find_suggestions_by_project(project_id, resolved, limit)` | Query suggestions by project, optionally filtered by resolved status |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[projectConfig Schema]] | `project_id` → `projectConfig.project_id` (optional N:1) |

---

See also: [[MongoDB Schema]], [[Slack API]], [[Slack Integration]]


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
