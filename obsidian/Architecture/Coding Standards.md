# Coding Standards

> Development conventions and quality requirements.

## 1. Modular & Component-Based Design

- Split large files into focused sub-modules (one concern per file)
- Keep functions small and single-purpose
- Use `__init__.py` re-exports so internal layout can change without breaking imports
- Goal: smaller context windows for AI agents → less token usage

## 2. Log Scanning After Changes

After every code change — and during partial or full test runs:
- Check `logs/crewai.log` for new `WARNING` / `ERROR` entries
- Fix any regressions before moving on
- Run tests with `-x` (fail-fast) and inspect output for unexpected warnings

## 3. Documentation Updates (Required)

Every code change **must** update the relevant documentation:

| Trigger | Files to update |
|---------|----------------|
| New or changed API endpoint | `docs/openapi/openapi.json`, `docs/openapi/paths/`, Swagger UI at `/docs` |
| New or changed env var | `.env.example`, `obsidian/Architecture/Environment Variables.md` |
| New feature or major change | `README.md` (feature list, usage, examples) |
| New dependency added | `pyproject.toml`, `README.md` (prerequisites section) |
| Schema / model change | `obsidian/Database/MongoDB Schema.md` |
| Any code change | Affected Obsidian pages (see CODEX.md "When to Update Which Page" table) |

### OpenAPI / Swagger
- Maintain OpenAPI/Swagger docs in `docs/openapi/openapi.json`
- Every new or changed endpoint must update the OpenAPI spec
- Verify changes reflected in Swagger UI at `/docs`

### README
- Update `README.md` when adding new APIs, features, or setup steps

### .env.example
- Every new environment variable must be added to `.env.example` with a descriptive comment

## 4. Session Management

### Major vs Minor Changes

- **Major changes** (new features, large refactors): Start a **new chat session**. Gets a `Y` bump.
- **Minor changes** (bug fixes, small tweaks): Keep in **current session**. Gets a `Z` bump.
- Bug fixes related to current work stay in the same session.

### Compact Mode at 75% Memory

When context capacity reaches 75%:
- Summarise completed work
- Drop intermediate search/read results
- Keep only: current task state, file paths, key decisions, todo list

### Obsidian Knowledge Updates

Every new session or iteration must update the Obsidian vault:
- Update [[Version History]] with new codex entries
- Update [[Session Log]] with session summary
- Update relevant knowledge pages for structural changes
- See [[Session Entry]] template for format

## 5. Command Prompt Permissions

All command-line operations are allowed by default — no permission needed.

## 6. Jira Approval Gate Invariant

Jira tickets must **never** be created without explicit user approval.
This rule applies to ALL code paths that can trigger Jira creation:

- **Auto-approve paths** (`_run_auto_post_completion`, startup crews):
  Must use `confluence_only=True` to gate out all Jira tasks.
- **Interactive paths** (`_run_phased_post_completion`): Must use the
  3-phase approval flow (skeleton → Epics/Stories → Sub-tasks) with
  user interaction at each gate.
- **Restart paths** (`execute_restart_prd`): Must use `interactive=True`
  to ensure phased Jira approval.

**Regression tests**: `tests/flows/test_jira_approval_gate.py` contains
23 tests covering every delivery path. Any new delivery path must add
a test to this file.

**Lesson learned** (v0.15.8): A `confluence_only` parameter was added
to `build_post_completion_crew` but was not propagated to all callers
(`_run_auto_post_completion`, `build_startup_delivery_crew`), causing
Jira tickets to be created without user approval. Always verify that
parameter changes are applied to ALL callers, not just the immediate
context.

**Lesson learned** (v0.15.11): Don't just guard against Jira *creation*
— also guard against Jira *state persistence*. `persist_post_completion()`
was autonomously detecting Jira keywords in crew output and setting
`jira_phase=subtasks_done` + `jira_completed=True`, causing the product
list to show Jira as complete when the user never approved it. All
autonomous Jira detection/persistence was removed from
`persist_post_completion()`, `_cli_startup.py`, and `components/startup.py`.
Only the interactive phased flow (`orchestrator/_jira.py`) may set these
fields.

## 7. One-Time Data Fix Scripts

When a bug contaminates MongoDB data (e.g. stale flags, orphaned
records), fix it with a **one-time script** in `scripts/`:

1. **Create** the script (e.g. `scripts/fix_stale_jira_phase.py`)
2. **Query first**: find affected documents and print them before changes
3. **Fix**: apply targeted `update_one` / `update_many` with explicit filters
4. **Verify**: re-query the same documents and print the corrected state
5. **Run** the script
6. **Confirm** output shows expected before/after state
7. **Delete** the script — single-use, don't commit it

> **Rule**: Always delete the script after use. It documents the fix in
> git history if committed before deletion, but must not remain in the
> tree as a runnable artifact.

## 8. Logging Standard (Required)

Every module with business logic **must** include structured logging for
incident tracking, troubleshooting, and trace-ability.

### 8.1 Logger Import — Always Use `get_logger`

```python
from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)
```

**Never** use bare `import logging` + `logging.getLogger(__name__)`.
The project logger (`get_logger`) ensures all messages flow through the
centralised root logger with daily file rotation, correct format, and
consistent namespace prefix.

### 8.2 What to Log

| Event | Level | Example |
|-------|-------|---------|
| Request received (API endpoint) | `INFO` | `logger.info("GET /health called")` |
| Task/operation started | `INFO` | `logger.info("[PRD] Starting flow run_id=%s", run_id)` |
| Task/operation completed | `INFO` | `logger.info("[PRD] Flow completed run_id=%s", run_id)` |
| External call sent/received | `INFO` | `logger.info("[Jira] Creating epic project=%s", key)` |
| State transition (DB update) | `INFO` | `logger.info("[MongoDB] Job %s → %s", job_id, status)` |
| Recoverable issue | `WARNING` | `logger.warning("[Slack] Retry posting to %s", channel)` |
| Missing optional config | `WARNING` | `logger.warning("FIGMA_API_KEY not set — skipping UX")` |
| Caught exception / failure | `ERROR` | `logger.error("[SSO] Token validation failed", exc_info=True)` |
| Internal variable state | `DEBUG` | `logger.debug("Payload: %s", payload)` |

### 8.3 Trace Context — Always Include Identifiers

Every log message must include the relevant business identifiers so
that logs can be correlated across modules during incident investigation:

- **PRD flows**: `run_id`, `job_id`
- **Slack events**: `channel`, `thread_ts`, `user` (Slack user ID), `team_id`
- **API requests**: `user_id` (from SSO), endpoint path
- **MongoDB operations**: collection name, document `_id` / `run_id`
- **External integrations**: `project_key` (Jira), `space_key` (Confluence), `page_id`

Example:
```python
logger.info(
    "[Slack] app_mention channel=%s thread=%s user=%s",
    channel, thread_ts, user,
)
```

### 8.4 Error Logging — Always Include Stack Trace

When catching exceptions, always use `exc_info=True` so the full
stack trace is written to `logs/crewai.log`:

```python
try:
    result = external_api_call()
except Exception:
    logger.error("External call failed for run_id=%s", run_id, exc_info=True)
    raise
```

### 8.5 Security — No Sensitive Data

Never log:
- Passwords, password hashes, or API keys/secrets
- Full JWT tokens (log only the `sub` claim or token prefix)
- OAuth refresh tokens or client secrets
- Personal data beyond user IDs and emails

### 8.6 Modules Exempt From Logging

The following file types do **not** require logging:
- `__init__.py` re-export files (no business logic)
- Pydantic model files (`models.py`, `_domain.py`, `_requests.py`, `_responses.py`)
- Slack block builder files (`blocks/*.py`) — pure data construction
- Constant/config files (`_constants.py`) — unless they run init logic

---

## 9. Slack Interaction-First Rule (Required)

Every Slack intent that a user can trigger **must** have a clickable
Block Kit button. Users should never need to type a command — all
navigation must be available as button interactions.

### 9.1 Required for Every New Intent

| Artifact | Location |
|----------|----------|
| `BTN_*` constant | `blocks/_command_blocks.py` |
| `cmd_<intent>` dispatch | `interactions_router/_command_handler.py` |
| Register in `CMD_ACTIONS` | `interactions_router/_command_handler.py` |
| Export in `__init__.py` | `blocks/__init__.py` |
| Include in `help_blocks()` | `blocks/_command_blocks.py` |
| Test dispatch | `tests/apis/slack/test_command_handler.py` |

### 9.2 Naming Convention

- Action IDs: `cmd_<intent>` where `<intent>` matches the LLM intent
  string (e.g. `cmd_publish`, `cmd_create_jira`).
- Button constants: `BTN_<UPPER_INTENT>` (e.g. `BTN_PUBLISH`,
  `BTN_CREATE_JIRA`).

### 9.3 Forbidden Patterns

- Never use "Say *command*" or "Type *command*" in any Slack message.
- Never instruct users to type text when a button can do the same.
- All fallback / error messages should include relevant action buttons.

---

See also: [[Testing Guide]], [[Project Overview]]
