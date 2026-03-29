# CODEX — AI Agent Developer Guide

> **Purpose**: Lean lookup guide for AI coding agents. Load only what you
> need — detailed documentation lives in `obsidian/`. This file provides
> quick-reference tables and pointers; read the linked Obsidian pages for
> full context.
>
> **Last updated**: 2026-03-10

---

## Quick Reference

| Area | Entry point | Key files |
|------|------------|-----------|
| **Server / CLI** | `src/.../main.py` | FastAPI app, CLI entrypoint |
| **PRD Flow** | `src/.../flows/prd_flow.py` | CrewAI Flow orchestrating the full PRD lifecycle |
| **Orchestrator** | `src/.../orchestrator/` | Pipeline runner + stage factories |
| **Agents** | `src/.../agents/` | CrewAI agent configs (idea_refiner, requirements_breakdown, etc.) |
| **APIs** | `src/.../apis/` | FastAPI routers (health, prd, slack, publishing) |
| **Slack** | `src/.../apis/slack/` | Slack router, interactive handlers, flow handlers, event routing |
| **MongoDB** | `src/.../mongodb/` | DB client, repositories (working_ideas, crew_jobs, agent_interactions, etc.) |
| **Tools** | `src/.../tools/` | CrewAI tools (confluence, jira, file I/O, search, slack) |
| **Scripts** | `src/.../scripts/` | Logging, preflight checks, retry, ngrok tunnel, slack config, MongoDB setup |
| **Tests** | `tests/` | Mirror of `src/` layout; pytest (2425+ tests) |

→ Full module map: `obsidian/Architecture/Module Map.md`

---

## Obsidian Knowledge Base

All detailed documentation lives in `obsidian/`. Read the relevant page
when you need deep context on a topic.

| Topic | Obsidian page |
|-------|--------------|
| **Architecture & conventions** | `Architecture/Project Overview.md` |
| **CrewAI framework patterns** | `Architecture/CrewAI Framework.md` |
| **Module file map** | `Architecture/Module Map.md` |
| **Server startup/shutdown** | `Architecture/Server Lifecycle.md` |
| **Environment variables** | `Architecture/Environment Variables.md` |
| **Coding standards** | `Architecture/Coding Standards.md` |
| **Agent configs & roles** | `Agents/Agent Roles.md` |
| **LLM model tiers** | `Agents/LLM Model Tiers.md` |
| **API endpoints** | `APIs/API Overview.md` |
| **Version history / changelog** | `Changelog/Version History.md` |
| **MongoDB schemas** | `Database/MongoDB Schema.md` |
| **PRD generation flow** | `Flows/PRD Flow.md` |
| **Slack integration** | `Integrations/Slack Integration.md` |
| **Confluence publishing** | `Integrations/Confluence Integration.md` |
| **Jira ticketing** | `Integrations/Jira Integration.md` |
| **PRD guidelines** | `Knowledge/PRD Guidelines.md` |
| **User preferences** | `Knowledge/User Preferences.md` |
| **Orchestrator pipelines** | `Orchestrator/Orchestrator Overview.md` |
| **Test patterns & patches** | `Testing/Testing Guide.md` |
| **CrewAI tools** | `Tools/Tools Overview.md` |
| **Session log** | `Sessions/Session Log.md` |

### When to Update Which Page

| Change type | Pages to update |
|------------|----------------|
| New module / file added | `Architecture/Module Map.md` |
| New API endpoint | `APIs/API Overview.md` + affected domain page (`APIs/Health API.md`, `APIs/Projects API.md`, `APIs/Ideas API.md`, `APIs/PRD Flow API.md`, `APIs/Publishing API.md`, `APIs/Slack API.md`, `APIs/SSO Webhooks API.md`) |
| Changed API request/response schema | Affected `APIs/<Domain> API.md` page — update field tables |
| New agent or model change | `Agents/Agent Roles.md`, `Agents/LLM Model Tiers.md` |
| New Slack intent or action | `Integrations/Slack Integration.md`, `APIs/Slack API.md` |
| MongoDB schema change | `Database/MongoDB Schema.md` + affected collection page (`Database/crewJobs Schema.md`, `Database/workingIdeas Schema.md`, `Database/productRequirements Schema.md`, `Database/projectConfig Schema.md`, `Database/projectMemory Schema.md`, `Database/agentInteraction Schema.md`, `Database/userSession Schema.md`, `Database/slackOAuth Schema.md`, `Database/userSuggestions Schema.md`) |
| New MongoDB field or index | Affected `Database/<collection> Schema.md` page — update field tables |
| New env var | `Architecture/Environment Variables.md` |
| Pipeline stage change | `Orchestrator/Orchestrator Overview.md` |
| Version bump | `Changelog/Version History.md` |
| Every session | `Sessions/Session Log.md` |

---

## Orchestrator — When to Load Which File

| Task | File(s) to read |
|------|----------------|
| Fix credential checks | `_helpers.py` |
| Change idea refinement logic | `_idea_refinement.py` |
| Change requirements breakdown | `_requirements.py` |
| Fix Confluence publishing | `_confluence.py` |
| Fix Jira ticket creation | `_jira.py` |
| Change Jira phasing / approval gates | `_jira.py`, `prd_flow.py` |
| Change pipeline composition | `_pipelines.py` |
| Fix post-completion delivery | `_post_completion.py` |
| Fix startup PRD publishing | `_startup_review.py` |
| Fix startup pending deliveries | `_startup_delivery.py` |

→ Full orchestrator details: `obsidian/Orchestrator/Orchestrator Overview.md`

---

## PRD Service (`apis/prd/service.py`)

| Function | Purpose |
|----------|---------|
| `run_prd_flow(run_id, idea, auto_approve, progress_callback)` | Execute new PRD flow; pauses on all errors (never fails) |
| `resume_prd_flow(run_id, auto_approve, progress_callback)` | Resume paused/unfinalized flow; calls `reactivate_job()` + `restore_prd_state()` |
| `restore_prd_state(run_id)` | Rebuilds full PRDDraft + ExecutiveSummaryDraft from MongoDB |
| `make_approval_callback(run_id)` | Creates blocking section-approval callback for interactive mode |

---

## Quick Start

```bash
# One-command project setup (creates venv, installs deps, copies .env)
./scripts/dev_setup.sh

# Start the server
./start_server.sh

# Run all tests
.venv/bin/python -m pytest -x -q

# Open in VS Code with all project settings
code .
```

---

## Common Commands

```bash
# Run all tests
.venv/bin/python -m pytest -x -q

# Run just orchestrator tests
.venv/bin/python -m pytest tests/orchestrator/ -x -q

# Run a single test module
.venv/bin/python -m pytest tests/orchestrator/test_jira.py -x -q

# Start the server
./start_server.sh

# Bootstrap MongoDB collections and indexes (also runs on server start)
.venv/bin/python -m crewai_productfeature_planner.scripts.setup_mongodb
```

---

## Coding Standards (Summary)

> Full details: `obsidian/Architecture/Coding Standards.md`

### Version Control (`X.Y.Z`)

| Segment | Bumped by | When |
|---------|-----------|------|
| **X** (Release) | User | User decides to cut a release |
| **Y** (Major) | Agent | Agent adds a new set of features or code |
| **Z** (Minor) | Agent | Agent iterates on a fix or resolves a bug |

The canonical version lives in `version.py` `_CODEX` list — append a
new `CodexEntry` for each bump.

### Jira Approval Gate Invariant

Jira tickets must **never** be created without explicit user approval.
Enforced by 23 regression tests in `tests/flows/test_jira_approval_gate.py`.

- **Autonomous paths**: Must pass `confluence_only=True` to crew builders.
- **Interactive paths**: Must use 3-phase approval flow (skeleton → Epics/Stories → Sub-tasks).
- **Restart paths**: Must pass `interactive=True` to `kick_off_prd_flow`.
- **New delivery paths**: Add a regression test to `test_jira_approval_gate.py`.

### Key Rules

- Modular design: one concern per file, small functions, `__init__.py` re-exports
- Log scanning: check `logs/crewai.log` after every change for `WARNING`/`ERROR`
- One-time fix scripts: create in `scripts/`, query→fix→verify→delete

### Slack Interaction-First Rule (Required)

Every Slack intent that a user can trigger **must** have a clickable
Block Kit button — users should never need to type a command.

**Invariants:**

1. **Every new intent** must have a corresponding `BTN_*` constant in
   `blocks/_command_blocks.py` and a `cmd_<intent>` dispatch branch in
   `interactions_router/_command_handler.py`.
2. **No "Say *command*" text** — never instruct the user to type a
   command. Use button blocks from `_command_blocks.py` instead.
3. **Help must show all actions** — the `help_blocks()` builder must
   include every actionable intent as a clickable button.
4. **Naming convention** — button action IDs follow `cmd_<intent>` where
   `<intent>` matches the LLM intent string (e.g. `cmd_publish`,
   `cmd_create_jira`, `cmd_restart_prd`).
5. **Add to CMD_ACTIONS** — register every new `cmd_*` action ID in the
   `CMD_ACTIONS` frozenset in `_command_handler.py`.

| Checklist for new intents | File(s) to update |
|--------------------------|-------------------|
| New `BTN_*` constant | `blocks/_command_blocks.py` |
| New dispatch branch | `interactions_router/_command_handler.py` |
| Register in `CMD_ACTIONS` | `interactions_router/_command_handler.py` |
| Export in `__init__.py` | `blocks/__init__.py` |
| Include in `help_blocks()` | `blocks/_command_blocks.py` |
| Add test | `tests/apis/slack/test_command_handler.py` |

### Interaction-First Testing (Required)

After any change to Slack Block Kit builders or handlers, verify the
**interaction-first rule** is not violated. The canonical regression
tests live in `tests/apis/slack/test_interaction_first_rule.py`.

**How to test Block Kit output:**

1. **Call the builder directly** — block builders are pure functions.
   Call them in tests and inspect the returned `list[dict]`.
2. **Count action blocks** — filter for `b["type"] == "actions"` and
   assert the expected count. Every UI response should have ≥ 1 actions
   block (no text-only outputs).
3. **Assert action IDs** — extract `e["action_id"]` from action block
   elements and verify the expected button IDs are present.
4. **No forbidden text** — scan all text blocks for phrases like
   "type `…`", "say *…*", "just tell me" using the `_FORBIDDEN_RE`
   pattern in `test_interaction_first_rule.py`.
5. **Test footer blocks** — when adding a footer button to an existing
   builder, update all tests that count action blocks (`+1` for the new
   footer) and any tests that assert on `blocks[-1]`.

**Quick checklist after UI changes:**

| Check | Command |
|-------|---------|
| Interaction-first tests | `pytest tests/apis/slack/test_interaction_first_rule.py -x -q` |
| Idea list tests | `pytest tests/apis/slack/test_idea_list.py -x -q` |
| Session block tests | `pytest tests/apis/slack/test_session_blocks.py -x -q` |
| Command handler tests | `pytest tests/apis/slack/test_command_handler.py -x -q` |
| Full Slack tests | `pytest tests/apis/slack/ -x -q` |

### Logging Standard (Required)

Every module with business logic **must** use structured logging for
incident tracking and troubleshooting. See full details in
`obsidian/Architecture/Coding Standards.md` § 8.

**Quick rules:**

1. **Use `get_logger`** — always `from ...scripts.logging_config import get_logger`,
   never bare `import logging` / `logging.getLogger(__name__)`.
2. **Log at boundaries** — entry/exit of API endpoints, background tasks,
   external calls (MongoDB, Slack, SSO, Confluence, Jira, Figma).
3. **Include trace context** — every log message must include the relevant
   identifiers: `run_id`, `job_id`, `user_id`, `channel`, `thread_ts`,
   `team_id`, `project_id`, `action_id`, etc.
4. **Log levels**:
   - `DEBUG` — internal state, variable dumps (only visible when `CREWAI_DEBUG=true`)
   - `INFO`  — normal operations (request received, task started/completed, record saved)
   - `WARNING` — recoverable issues (missing optional config, retry, fallback used)
   - `ERROR` — failures that affect the user (exceptions, API errors, bad responses)
5. **Error logging** — always log `exc_info=True` on caught exceptions:
   `logger.error("...", exc_info=True)`.
6. **No sensitive data** — never log passwords, tokens, API keys, or PII
   beyond user/slack IDs.

### Documentation Updates (Required)

Every code change **must** update the relevant documentation artifacts:

| Trigger | Files to update |
|---------|----------------|
| New or changed API endpoint | `docs/openapi/openapi.json`, `docs/openapi/paths/`, affected `obsidian/APIs/<Domain> API.md` |
| Changed API request/response model | Affected `obsidian/APIs/<Domain> API.md` — update field tables, types, constraints |
| New or changed env var | `.env.example`, `obsidian/Architecture/Environment Variables.md` |
| New feature or major change | `README.md` (feature list, usage, examples) |
| New dependency added | `pyproject.toml`, `README.md` (prerequisites section) |
| Schema / model change | Affected `obsidian/Database/<collection> Schema.md` — update field tables, indexes, repository functions |
| New MongoDB field or index | Affected `obsidian/Database/<collection> Schema.md` |
| New repository function | Affected `obsidian/Database/<collection> Schema.md` — add to repository functions table |
| Any code change | Affected Obsidian pages (see "When to Update Which Page" table above) |

---

## Session Management (Summary)

> Full details: `obsidian/Architecture/Coding Standards.md`

- **Major changes** (new features, refactors) → new chat session (`Y` bump)
- **Minor changes** (bug fixes, tweaks) → current session (`Z` bump)
- **Compact mode** at 75% context capacity — summarise and continue
- **All terminal commands allowed by default** — no need to ask permission

### Obsidian Knowledge Updates (Required)

The vault **must** be updated immediately after each code change:

1. **Session start**: Read `Sessions/Session Log.md` for recent context
2. **After each code change**: Update affected Obsidian pages (see table above)
3. **Session end**: Append summary to `Sessions/Session Log.md`
4. **Knowledge sources**: Update `knowledge/*.txt` files when preferences,
   architecture, or PRD guidelines change — these feed CrewAI agents directly

---

## Patch Target Cheat Sheet

Patch the name **where it is imported**, not where it is defined:

| Function | Patch target |
|----------|-------------|
| `_has_gemini_credentials` in `_post_completion.py` | `...orchestrator._post_completion._has_gemini_credentials` |
| `_has_jira_credentials` in `_startup_delivery.py` | `...orchestrator._startup_delivery._has_jira_credentials` |
| `_has_confluence_credentials` in `_startup_review.py` | `...orchestrator._startup_review._has_confluence_credentials` |
| `_discover_publishable_prds` in `_startup_review.py` | `...orchestrator._startup_review._discover_publishable_prds` |

→ Full test patterns: `obsidian/Testing/Testing Guide.md`
