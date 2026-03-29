# agentInteraction Schema

> Slack interaction logging — captures every user message, LLM intent classification, and agent response for analytics and fine-tuning.

**Collection**: `agentInteraction`
**Primary Key**: `interaction_id` (unique index)

---

## Used By

| API | Endpoint | Operation |
|-----|----------|-----------|
| [[Slack API]] | Events router (`app_mention`) | Logs interaction after intent classification |
| [[Slack API]] | Events router (`message`) | Logs threaded conversation interactions |
| [[Slack API]] | Interactions router | Logs button click interactions |
| [[Slack API]] | Events router (smart routing) | Checks `has_bot_thread_history()` for thread routing |
| Agent feedback loop | Next-step prediction | Records whether user followed LLM predictions |

---

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `interaction_id` | `string` | **Yes** | *UUID hex* | Unique interaction identifier. Primary key |
| `source` | `string` | **Yes** | — | Origin of the interaction: `"slack"` (mention/message), `"cli"` (command line), or `"slack_interactive"` (button click) |
| `user_message` | `string` | **Yes** | — | Raw text the user sent (message body or button label) |
| `intent` | `string` | **Yes** | — | Classified intent: `"create_prd"`, `"help"`, `"greeting"`, `"publish"`, `"list_ideas"`, `"unknown"`, etc. |
| `agent_response` | `string` | **Yes** | — | Agent's reply/response text sent back to the user |
| `idea` | `string \| null` | No | `null` | Extracted product idea text (if the intent was `create_prd`) |
| `run_id` | `string \| null` | No | `null` | Associated flow run_id (if a PRD flow was started/referenced) |
| `project_id` | `string \| null` | No | `null` | FK → `projectConfig.project_id` (from active session context) |
| `channel` | `string \| null` | No | `null` | Slack channel ID (Slack interactions only) |
| `thread_ts` | `string \| null` | No | `null` | Slack thread timestamp (Slack interactions only) |
| `user_id` | `string \| null` | No | `null` | Slack user ID or `"cli_user"` for CLI interactions |
| `conversation_history` | `list[dict] \| null` | No | `null` | Thread context — array of `{role, content}` messages for LLM fine-tuning data |
| `metadata` | `dict \| null` | No | `null` | Additional context (e.g. `{ "interactive": true }`, `{ "auto_approve": false }`) |
| `predicted_next_step` | `dict \| null` | No | `null` | LLM's prediction of user's next action: `{ next_step: str, message: str, confidence: float, reason: str }` |
| `next_step_accepted` | `bool \| null` | No | `null` | Whether the user followed the predicted next step — `true`/`false`/`null` (not yet recorded) |
| `next_step_feedback_at` | `datetime \| null` | No | `null` | When the feedback on the prediction was recorded |
| `created_at` | `datetime (UTC)` | **Yes** | *now* | When the interaction occurred |

---

## Predicted Next Step Record

The `predicted_next_step` field (when present):

| Field | Type | Description |
|-------|------|-------------|
| `next_step` | `string` | Predicted action (e.g. `"approve_section"`, `"create_prd"`, `"publish"`) |
| `message` | `string` | Suggested message/prompt for the user |
| `confidence` | `float` | Prediction confidence score (0.0–1.0) |
| `reason` | `string` | Reasoning behind the prediction |

---

## Indexes

| Fields | Type | Purpose |
|--------|------|---------|
| `interaction_id` | Unique, Ascending | Primary key lookup |
| `created_at DESC` | Descending | Recent interactions (newest first) |
| `(source, created_at DESC)` | Compound | Filter by source, newest first |
| `(intent, created_at DESC)` | Compound | Filter by intent, newest first |

---

## Repository Functions

**Source**: `mongodb/agent_interactions/repository.py`

| Function | Purpose |
|----------|---------|
| `log_interaction()` | Insert new interaction document |
| `get_interaction(interaction_id)` | Fetch by ID |
| `find_interactions_by_source()` | Filter by source, newest first |
| `find_interactions_by_intent()` | Filter by intent, newest first |
| `find_interactions()` | Flexible query with optional filters (source, intent, user_id, run_id, since) |
| `list_interactions()` | Return most recent interactions |
| `has_bot_thread_history()` | Check if bot has prior interaction in a Slack thread |
| `record_next_step_feedback()` | Record whether user followed LLM's predicted next step |

---

## Related Collections

| Collection | Relationship |
|------------|-------------|
| [[projectConfig Schema]] | `project_id` → `projectConfig.project_id` (optional N:1) |
| [[workingIdeas Schema]] | `run_id` → `workingIdeas.run_id` (optional N:1) |

---

See also: [[MongoDB Schema]], [[Slack API]], [[Slack Integration]]
