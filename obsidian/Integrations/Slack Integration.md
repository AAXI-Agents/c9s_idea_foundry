# Slack Integration

> Full Slack module map and interactive flow details (`apis/slack/`).

## Module Structure

```
apis/slack/
  router.py               /slack/kickoff endpoints, _run_slack_prd_flow()
  events_router.py        /slack/events webhook, message/app_mention routing
  interactions_router/     Block Kit button click handlers (package)
    _dispatch.py           Action routing
    _project_handler.py    Project selection
    _memory_handler.py     Memory configuration
    _next_step_handler.py  Next-step suggestions
    _restart_handler.py    Restart/archive flows
    _idea_list_handler.py  Idea list buttons
    _delivery_action_handler.py  Publish/Jira buttons
    _archive_handler.py    Archive confirmation
    _command_handler.py    cmd_* button dispatch (clickable shortcuts)
  interactive_handlers/    Interactive flow state (package)
    _run_state.py          Per-run state tracking
    _decisions.py          Decision resolution
    _slack_helpers.py      Slack messaging helpers
    _callbacks.py          Approval callback factories
    _flow_runner.py        Interactive flow execution
  _flow_handlers.py        Progress poster, resume, publish intent
  _thread_state.py         Per-thread conversation state
  _intent_classifier.py    Message intent classification
  _intent_phrases.py       Phrase-based intent fallback
  _message_handler.py      Message routing logic
  _session_handlers.py     Session management (package)
  _next_step.py            Next-step prediction
  blocks/                  Block Kit message builders (package)
    _flow_blocks.py        Flow status blocks
    _session_blocks.py     Session management blocks
    _memory_blocks.py      Memory config blocks
    _next_step_blocks.py   Next-step suggestion blocks
    _exec_summary_blocks.py  Executive summary blocks
    _jira_blocks.py        Jira approval blocks
    _idea_list_blocks.py   Idea list with buttons
    _delivery_action_blocks.py  Delivery action buttons
    _product_list_blocks.py    Product list with delivery status
    _command_blocks.py         Clickable command buttons (cmd_* shortcuts)
  oauth_router.py          /slack/oauth/callback (OAuth v2)
  verify.py                HMAC-SHA256 request verification
```

## Slack Webhooks

| Endpoint | Purpose |
|----------|---------|
| `POST /slack/events` | Events API (url_verification, app_mention, messages) |
| `POST /slack/interactions` | Block Kit button clicks |
| `GET /slack/oauth/callback` | OAuth v2 install/reinstall |
| `POST /slack/kickoff` | Start PRD flow from API |

## Interactive Flow Phases

1. **Refinement Mode Choice** — "Agent" (auto 3-10 cycles) or "Manual" (thread-based)
2. **Idea Approval** — Approve refined idea or Cancel
3. **Requirements Approval** — Approve structured requirements or Cancel
4. **Executive Summary Feedback** — Iterate with user feedback or Approve (v0.4.0+)
5. **Executive Summary Completion** — Continue to sections or Stop (v0.6.5+)
6. **Auto-Generation** — Sections draft/critique/refine with auto_approve

## Interactive State Management

- `_interactive_runs[run_id]` tracks per-run state with `threading.Event`
- 30-minute TTL for stale entries
- 10-minute timeout per decision
- Thread conversations: 10-minute TTL, 20-message rolling window

### Thread Message Dispatch (`should_process` gate)

Channel thread messages are processed when **any** of these conditions
is true (checked in order, short-circuiting):

1. **has_conversation** — in-memory thread cache (10-min TTL)
2. **has_interactive** — active PRD flow in `_interactive_runs`
3. **has_pending** — pending create/setup wizard
4. **has_active_session** — MongoDB channel session with project_id
5. **has_thread_history** — MongoDB `agentInteraction` with matching
   `channel` + `thread_ts` (v0.29.1) — survives server restarts and
   TTL expiry; re-registers thread in memory cache on hit

## Key Action IDs

| Action ID | Purpose |
|-----------|---------|
| `refinement_agent` / `refinement_manual` | Refinement mode choice |
| `idea_approve` / `idea_cancel` | Idea approval gate |
| `requirements_approve` / `requirements_cancel` | Requirements gate |
| `exec_summary_approve` / `exec_summary_skip` | Exec summary feedback |
| `exec_summary_continue` / `exec_summary_stop` | Exec summary completion |
| `flow_retry` | Retry paused flow |
| `flow_cancel` | Cancel at any point |
| `jira_skeleton_approve` / `jira_skeleton_reject` | Skeleton approval |
| `jira_subtask_approve` / `jira_subtask_reject` | Sub-task review |
| `delivery_publish` / `delivery_create_jira` | Delivery action buttons (Publish to Confluence / Create Jira Skeleton) |

## Intents

Classified via LLM + phrase-based fallback:
`create_prd`, `iterate_idea`, `publish`, `create_jira`, `check_publish`, `resume_prd`, `restart_prd`, `list_ideas`, `summarize_ideas`, `list_products`, `list_projects`, `switch_project`, `create_project`, `configure_memory`, `end_session`, `current_project`, `general_question`, `help`, `greeting`, `unknown`

## Token Management

- Supports both static (`xoxb-`) and rotating (`xoxe.`) bot tokens
- Automatic refresh when near expiry
- Persists to `.slack_tokens.json` + MongoDB
- Health endpoints: `GET /health/slack-token`, `POST /exchange`, `POST /refresh`

## Content Truncation & File Upload (v0.31.2)

Slack Block Kit has a 3000-char limit per section text field. When rendered
content (idea, exec summary, requirements) exceeds 2800 chars:

1. Inline preview is truncated at 2800 chars with a hint: "see attached file"
2. Full content is uploaded as a downloadable `.md` file in the thread
3. Applies to all 5 block builders: `idea_approval_blocks`,
   `manual_refinement_prompt_blocks`, `requirements_approval_blocks`,
   `exec_summary_feedback_blocks`, `exec_summary_completion_blocks`
4. Helper module: `_slack_file_helper.py` — `truncate_with_file_hint()`,
   `upload_content_file()`

## Thread Mention Gating (v0.32.0)

The bot only responds to channel thread messages when @mentioned, **unless**
an active workflow is in progress (interactive PRD flow, pending user input,
or cached conversation). This prevents the bot from jumping into threads
where it was not tagged.

| Condition | Mention required? | Reason |
|-----------|:-:|---|
| `has_interactive` | No | User is answering PRD flow prompts |
| `has_pending` | No | User is replying to setup/config wizard |
| `has_conversation` | No | Bot is in active recent conversation (10-min TTL) |
| `has_active_session` | **Yes** | Channel has project but no active workflow |
| `has_thread_history` | **Yes** | Bot was in thread before but no active workflow |

---

See also: [[Jira Integration]], [[Confluence Integration]], [[PRD Flow]]
