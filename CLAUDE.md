# CLAUDE — AI Agent Developer Guide

> **Purpose**: Lean lookup guide for AI coding agents. Load only what you
> need — detailed documentation lives in `obsidian/`. This file provides
> quick-reference tables and pointers; read the linked Obsidian pages for
> full context.
>
> **Last updated**: 2026-04-12

---

## ⛔ Rule 0: NEVER Assume — Ask Questions First (Required)

**NEVER ASSUME.** When requirements are unclear, ambiguous, or have
multiple valid approaches, the agent **MUST** stop and ask questions
before proceeding. Assuming makes an ASS out of U and ME.

### Workflow

1. **Detect ambiguity** — if any part of the task is unclear, has
   missing context, or could be implemented multiple valid ways, do NOT
   guess. Stop and gather input.

2. **Create a decisions file** — create a markdown file in
   `obsidian/User Feedback/` named `QUESTIONS-<short-name>.md` with:
   - **3 Recommendations** (`Option A`, `Option B`, `Option C`): each
     with a brief rationale explaining the trade-offs.
   - **1 Suggestion** (`Suggested`): a fourth option that combines or
     refines the best parts of the recommendations.
   - Each option **must** be a clickable checkbox (`- [ ]`) so the user
     can simply tick their choice.

3. **Ask the user** — present the options using the ask-questions tool
   (or Slack interactive message). Do **NOT** proceed until the user
   selects an answer.

4. **Record the decision** — update the decisions file with the user's
   choice and mark it `status: resolved` in frontmatter.

5. **One-time only** — the user should never be asked the same question
   twice. Once a decision is recorded, the agent must reference it in
   future sessions. The user should not need to re-input this every time.

### Key Principles

- **When in doubt, ask.** A 30-second question saves hours of rework.
- **Never fill in blanks with guesses** — surface the ambiguity to the
  user with structured options.
- **The user decides, the agent executes** — present recommendations,
  but let the user choose.
- **Proactive, not reactive** — the agent must identify ambiguity and
  ask before the user notices the gap.

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
| **PRD generation flow** | `Flows/PRD Flow.md` (index → 10 flow pages) |
| **Slack integration** | `Integrations/Slack Integration.md` |
| **Confluence publishing** | `Integrations/Confluence Integration.md` |
| **Jira ticketing** | `Integrations/Jira Integration.md` |
| **PRD guidelines** | `Knowledge/PRD Guidelines.md` |
| **User preferences** | `Knowledge/User Preferences.md` |
| **Orchestrator pipelines** | `Orchestrator/Orchestrator Overview.md` |
| **Test patterns & patches** | `Testing/Testing Guide.md` |
| **CrewAI tools** | `Tools/Tools Overview.md` |
| **User feedback / gap tickets** | `User Feedback/` (use `_template.md`) |
| **Session log** | `Sessions/Session Log.md` |

### When to Update Which Page

| Change type | Pages to update |
|------------|----------------|
| New module / file added | `Architecture/Module Map.md` |
| New API endpoint | `APIs/API Overview.md` + affected per-route file in `APIs/<Domain>/` (Health, Projects, Ideas, PRD Flow, Publishing, Slack, SSO Webhooks) |
| Changed API request/response schema | Affected per-route file in `APIs/<Domain>/` — update field tables |
| New agent or model change | `Agents/Agent Roles.md` + affected agent page (`Agents/Idea Refiner.md`, `Agents/Product Manager.md`, `Agents/Requirements Breakdown.md`, `Agents/Orchestrator.md`, `Agents/CEO Reviewer.md`, `Agents/Engineering Manager.md`, `Agents/Staff Engineer.md`, `Agents/QA Lead.md`, `Agents/QA Engineer.md`, `Agents/UX Designer.md`, `Agents/Engagement Manager.md`, `Agents/Idea Agent.md`), `Agents/LLM Model Tiers.md` |
| Changed agent role/goal/backstory/task | Affected `Agents/<Agent>.md` page — update role, goal, backstory, or task sections |
| New Slack intent or action | `Integrations/Slack Integration.md`, affected file in `APIs/Slack/` |
| MongoDB schema change | `Database/MongoDB Schema.md` + affected collection page (`Database/crewJobs Schema.md`, `Database/workingIdeas Schema.md`, `Database/productRequirements Schema.md`, `Database/projectConfig Schema.md`, `Database/projectMemory Schema.md`, `Database/agentInteraction Schema.md`, `Database/userSession Schema.md`, `Database/slackOAuth Schema.md`, `Database/userSuggestions Schema.md`) |
| New MongoDB field or index | Affected `Database/<collection> Schema.md` page — update field tables |
| New env var | `Architecture/Environment Variables.md` |
| Pipeline stage change | `Orchestrator/Orchestrator Overview.md`, `Flows/PRD Flow.md` + affected flow page (`Flows/Idea Refinement Flow.md`, `Flows/Executive Summary Flow.md`, `Flows/Requirements Breakdown Flow.md`, `Flows/CEO Review Flow.md`, `Flows/Engineering Plan Flow.md`, `Flows/Section Drafting Flow.md`, `Flows/Finalization Flow.md`, `Flows/UX Design Flow.md`, `Flows/Confluence Publishing Flow.md`, `Flows/Jira Ticketing Flow.md`) |
| Changed flow step/approval gate/skip condition | Affected `Flows/<Flow>.md` page — update step details, skip conditions, data flow |
| Version bump | `Changelog/Version History.md` |
| Gap / missing feature found | `User Feedback/<gap-name>.md` (copy from `_template.md`) |
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
| New or changed agent | `obsidian/Agents/Agent Roles.md` + affected `obsidian/Agents/<Agent>.md` — update role, goal, backstory, tasks |
| Changed agent role/goal/backstory/task | Affected `obsidian/Agents/<Agent>.md` — update role, goal, backstory, or task sections |
| Pipeline or flow step change | `obsidian/Flows/PRD Flow.md` + affected `obsidian/Flows/<Flow>.md` — update step details, skip conditions, data flow |
| Changed flow approval gate or skip condition | Affected `obsidian/Flows/<Flow>.md` — update approval gates, skip conditions |
| Any code change | Affected Obsidian pages (see "When to Update Which Page" table above) |

### Gap Ticket Workflow (User Feedback)

When a gap is discovered — missing API endpoint, incomplete feature,
broken flow, missing UI component — create a ticket in `obsidian/User Feedback/`.

**Creating a gap ticket:**

1. Copy `obsidian/User Feedback/_template.md` to a new file:
   `obsidian/User Feedback/GAP-<short-name>.md`
2. Fill in the frontmatter: `status`, `priority`, `domain`, `created`.
3. Describe current vs expected behaviour, affected area, and acceptance
   criteria.

**Ask-Questions-First Rule (Required):**

When a gap ticket or task requires user decisions before implementation,
the agent **MUST** proactively ask questions — the user should never need
to manually fill in a questionnaire. See **Rule 0** above for the full
workflow. The agent must:

1. Identify ambiguity and stop before proceeding.
2. Create `QUESTIONS-<short-name>.md` with 3 recommendations + 1 suggestion.
3. Ask the user and wait for a selection.
4. Record the decision and never re-ask.

**Agent workflow (when processing gap tickets):**

1. Scan `User Feedback/` for files with `status: open` in frontmatter.
2. For each open gap:
   a. If the gap has unresolved questions, follow the
      **Ask-Questions-First Rule** above before implementing.
   b. Implement the fix or new feature.
   c. Update the `## Resolution` section with version, date, and summary.
   d. Change frontmatter `status: open` → `status: resolved`.
3. Bump version in `version.py` and update `Changelog/Version History.md`.

**Archive completed tickets (Required):**

Once a gap ticket reaches `status: resolved` or `status: wont-fix`,
the agent **MUST** move the file from `obsidian/User Feedback/` to
`obsidian/User Feedback Archive/`.

1. Move the resolved/won't-fix file:
   `obsidian/User Feedback/GAP-<name>.md` →
   `obsidian/User Feedback Archive/GAP-<name>.md`
2. Also move any related `QUESTIONS-<name>.md` file to the archive.
3. Never delete archived files — they form an audit trail.
4. The `User Feedback/` folder should only contain `_template.md` and
   active (`open` / `in-progress`) tickets.
5. **End of session cleanup** — scan for any resolved/wont-fix files
   still in `User Feedback/` and move them to the archive.

**Naming convention:** `GAP-<domain>-<short-description>.md`
(e.g. `GAP-api-missing-pagination-on-jobs.md`, `GAP-slack-no-error-feedback.md`)

**Priority values:** `critical`, `high`, `medium`, `low`

**Status values:** `open`, `in-progress`, `resolved`, `wont-fix`

---

### Change Request Workflow (APIs, Database, Flows)

Every page in `obsidian/APIs/`, `obsidian/Database/`, and `obsidian/Flows/`
has a **## Change Requests** section at the bottom with **Pending** and
**Completed** sub-headings.

**User workflow:**

1. Open the relevant Obsidian page (e.g. `APIs/Slack/POST slack-kickoff.md`).
2. Under `### Pending`, add a checkbox item:
   ```
   - [ ] Add a new query param `limit` to GET /slack/channels
   ```
3. Ask the agent to process change requests.

**Agent workflow (when processing CRs):**

1. Scan all pages in `APIs/`, `Database/`, `Flows/` for unchecked `- [ ]`
   items under `### Pending`.
2. For each pending CR:
   a. Implement the requested code change.
   b. Update the Obsidian page content to reflect the change.
   c. Move the item from `### Pending` to `### Completed` as `- [x]`
      with the date: `- [x] <request> *(completed YYYY-MM-DD)*`
   d. Remove the `_No pending change requests._` placeholder if items exist.
3. Bump version in `version.py` (`Y` for new features, `Z` for fixes).
4. Update `obsidian/Changelog/Version History.md`.

**Rules:**

- Never delete a completed CR — they form an audit trail.
- If a CR is unclear, add a comment below it: `  - ⚠️ Clarification needed: …`
  and skip it until the user responds.
- Replace `_No pending change requests._` when adding the first item;
  restore it when the last pending item is completed.

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
