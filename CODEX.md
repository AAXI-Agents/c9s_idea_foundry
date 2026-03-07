# CODEX — AI Agent Developer Guide

> **Purpose**: Reduce token usage when working with AI coding agents
> (Copilot, Codex, Cursor, Claude Code, etc.) by documenting the modular
> layout so agents can load only the files they need.
>
> **Last updated**: 2026-03-02 — session management rules, version-scoped
> chat sessions, compact mode at 75% memory, kill-old-runs on restart.

---

## Quick Reference

| Area | Entry point | Key files |
|------|------------|-----------|
| **Server / CLI** | `src/.../main.py` | FastAPI app, CLI entrypoint |
| **PRD Flow** | `src/.../flows/prd_flow.py` | CrewAI Flow orchestrating the full PRD lifecycle |
| **Orchestrator** | `src/.../orchestrator/` | Pipeline runner + stage factories (see below) |
| **Agents** | `src/.../agents/` | CrewAI agent configs (idea_refiner, requirements_breakdown, etc.) |
| **APIs** | `src/.../apis/` | FastAPI routers (health, prd, slack, publishing) |
| **Slack** | `src/.../apis/slack/` | Slack router, interactive handlers, flow handlers, event routing |
| **MongoDB** | `src/.../mongodb/` | DB client, repositories (working_ideas, crew_jobs, agent_interactions, etc.) |
| **Tools** | `src/.../tools/` | CrewAI tools (confluence, jira, file I/O, search, slack) |
| **Scripts** | `src/.../scripts/` | Logging, preflight checks, retry, ngrok tunnel, slack config |
| **Tests** | `tests/` | Mirror of `src/` layout; pytest (1558+ tests) |

---

## Server Lifecycle (`apis/__init__.py`)

The FastAPI app runs 8 startup steps in `_lifespan()`:

1. Kill stale crew processes
2. `fail_incomplete_jobs_on_startup()` → marks orphaned crewJobs as `failed`
2b. `fail_unfinalized_on_startup()` → marks unfinalized working ideas as `failed`
3. Generate missing markdown outputs for completed ideas
4. Run startup pipeline (review + Confluence publish via orchestrator)
5. Launch autonomous delivery crew (Confluence + Jira) in background thread
6. Start file watcher for `output/prds/` auto-publish
7. Start cron scheduler for periodic delivery scans
8. `_notify_terminated_flows()` → posts Slack notices to threads whose flows
   were terminated on restart; users are told to say "create prd" to start fresh

Shutdown: stops file watcher and scheduler.

---

## PRD Flow Progress Events (`flows/prd_flow.py`)

The flow fires events via `_notify_progress(event_type, details)`:

| Event | When | Key details fields |
|-------|------|-------------------|
| `section_start` | Section begins (draft or resume) | `section_title`, `section_key`, `section_step`, `total_sections` |
| `exec_summary_iteration` | Each exec summary refinement pass | `iteration`, `max_iterations` |
| `executive_summary_complete` | Exec summary finalized | `iterations` |
| `section_iteration` | Each section refinement pass | `section_title`, `section_key`, `section_step`, `total_sections`, `iteration`, `max_iterations` |
| `section_complete` | Section approved | `section_title`, `section_key`, `section_step`, `total_sections`, `iterations` |
| `all_sections_complete` | All sections done | `total_iterations`, `total_sections` |
| `prd_complete` | Final PRD assembled | _(empty)_ |
| `confluence_published` | Published to Confluence | `url` |
| `jira_published` | Jira tickets created | `ticket_count` |

Consumed by `make_progress_poster()` in `_flow_handlers.py` which posts
to Slack and updates `crewJobs.current_section*` fields.

---

## Slack Module Map (`apis/slack/`)

```
apis/slack/
  router.py               /slack/kickoff endpoints, _run_slack_prd_flow()
  events_router.py         /slack/events webhook, message/app_mention routing
  interactive_handlers.py  Interactive (approval buttons, manual refinement)
  _flow_handlers.py        make_progress_poster(), handle_resume_prd(),
                           handle_publish_intent(), kick_off_prd_flow()
  _thread_state.py         Per-thread conversation state
  _intent_classifier.py    Message intent classification
```

### Key functions

| Function | File | Purpose |
|----------|------|---------|
| `make_progress_poster(channel, thread_ts, user, send_tool, *, run_id)` | `_flow_handlers.py` | Returns progress callback for Slack heartbeat + crewJobs tracking |
| `handle_resume_prd(channel, thread_ts, user, send_tool, project_id)` | `_flow_handlers.py` | Finds latest unfinalized run, resumes in background thread |
| `_run_slack_prd_flow(run_id, idea, channel, ...)` | `router.py` | Full flow executor with Slack notifications |
| `run_interactive_slack_flow(run_id, idea, channel, ...)` | `interactive_handlers.py` | Interactive approval flow with buttons |

---

## MongoDB Module Map

```
mongodb/
  client.py                get_db(), connection management
  crew_jobs/
    repository.py          create_job(), update_job_status(), fail_incomplete_jobs_on_startup(),
                           reactivate_job(), find_active_job(), find_job(), list_jobs()
  working_ideas/
    repository.py          save_iteration(), find_unfinalized(), save_slack_context(),
                           save_confluence_url(), mark_completed(), mark_paused(),
                           get_run_documents(), save_output_file(), save_project_ref()
  agent_interactions/      Slack interaction logging (fine-tuning data)
  project_config/          Per-project settings (jira_project_key, etc.)
  project_memory/          Project-level memory store
```

### crewJobs document schema

```
{
  job_id, flow_name, idea, status,
  error,
  slack_channel, slack_thread_ts,           # for auto-resume
  current_section, current_section_key,     # live progress tracking
  current_section_step, total_sections,
  queued_at, started_at, completed_at,
  queue_time_ms, queue_time_human,
  running_time_ms, running_time_human,
  updated_at
}
```

Status values: `queued` → `running` → `completed` | `failed` | `awaiting_approval` | `paused`

---

## Orchestrator Module Map

```
src/crewai_productfeature_planner/orchestrator/
  orchestrator.py          AgentOrchestrator, AgentStage, StageResult
  stages.py                Re-export facade (backward compat — all names)

  _helpers.py              _has_gemini_credentials, _has_confluence_credentials,
                           _has_jira_credentials, _print_delivery_status

  _idea_refinement.py      build_idea_refinement_stage(flow)
  _requirements.py         build_requirements_breakdown_stage(flow)
  _confluence.py           build_confluence_publish_stage(flow)
  _jira.py                 _extract_issue_keys,
                           build_jira_skeleton_stage(flow),
                           build_jira_epics_stories_stage(flow),
                           build_jira_subtasks_stage(flow),
                           build_jira_ticketing_stage(flow)  [legacy auto-approve]

  _pipelines.py            build_default_pipeline(flow),
                           build_post_completion_pipeline(flow)

  _post_completion.py      build_post_completion_crew(flow, progress_callback)
  _startup_review.py       _discover_publishable_prds,
                           build_startup_markdown_review_stage,
                           build_startup_pipeline
  _startup_delivery.py     DeliveryItem, _discover_pending_deliveries,
                           build_startup_delivery_crew(item, progress_callback)
```

### When to load which file

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

---

## PRD Service (`apis/prd/service.py`)

| Function | Purpose |
|----------|---------|
| `run_prd_flow(run_id, idea, auto_approve, progress_callback)` | Execute new PRD flow; pauses on all errors (never fails) |
| `resume_prd_flow(run_id, auto_approve, progress_callback)` | Resume paused/unfinalized flow; calls `reactivate_job()` + `restore_prd_state()` |
| `restore_prd_state(run_id)` | Rebuilds full PRDDraft + ExecutiveSummaryDraft from MongoDB |
| `make_approval_callback(run_id)` | Creates blocking section-approval callback for interactive mode |

---

## Test Module Map

Tests mirror the source modules:

```
tests/orchestrator/
  test_stages.py              Smoke test (facade import check only)
  test_helpers.py             Credential checks, _print_delivery_status
  test_idea_refinement.py     TestIdeaRefinementStage
  test_requirements.py        TestRequirementsBreakdownStage
  test_confluence.py          TestConfluencePublishStage
  test_jira.py                TestExtractIssueKeys, TestJiraTicketingStage
  test_pipelines.py           TestBuildDefaultPipeline, TestBuildPostCompletionPipeline
  test_post_completion.py     TestBuildPostCompletionCrew
  test_startup_review.py      TestDiscoverPublishablePrds, TestStartupMarkdownReviewStage,
                              TestStartupPipeline
  test_startup_delivery.py    TestDiscoverPendingDeliveries, TestBuildStartupDeliveryCrew
```

---

## Patch Target Cheat Sheet

When writing `@patch(...)` in tests, patch the name **where it is
imported**, not where it is defined:

| Function | Patch target |
|----------|-------------|
| `_has_gemini_credentials` in `_post_completion.py` | `...orchestrator._post_completion._has_gemini_credentials` |
| `_has_jira_credentials` in `_startup_delivery.py` | `...orchestrator._startup_delivery._has_jira_credentials` |
| `_has_confluence_credentials` in `_startup_review.py` | `...orchestrator._startup_review._has_confluence_credentials` |
| `_discover_publishable_prds` in `_startup_review.py` | `...orchestrator._startup_review._discover_publishable_prds` |

> **Rule of thumb**: Patch `<module_where_used>.<name>`, not
> `<module_where_defined>.<name>`.

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
```

---

## Coding Standards

### 1. Modular & Component-Based Design

All new code must be modular and component-oriented:
- Split large files into focused sub-modules (one concern per file)
- Keep functions small and single-purpose
- Use `__init__.py` re-exports so internal layout can change without breaking imports
- Goal: smaller context windows for AI agents → less token usage

### 2. Log Scanning After Changes

After every code change — and during partial or full test runs — scan
logs for warnings or errors that need fixing:
- Check `logs/crewai.log` for new `WARNING` / `ERROR` entries
- Fix any regressions before moving on to the next task
- Run tests with `-x` (fail-fast) and inspect output for unexpected warnings

### 3. API Documentation

- Maintain OpenAPI/Swagger docs in `docs/openapi/openapi.json`
- Every new or changed endpoint must update the OpenAPI spec
- Update `README.md` when adding new APIs, features, or setup steps
- FastAPI auto-generates Swagger UI at `/docs` — verify it reflects changes

### 4. Version Control (`X.Y.Z`)

Versioning follows `X.Y.Z` in `src/.../version.py`:

| Segment | Bumped by | When |
|---------|-----------|------|
| **X** (Release) | User | User decides to cut a release |
| **Y** (Major) | Agent | Agent adds a new set of features or code |
| **Z** (Minor) | Agent | Agent iterates on a fix or resolves a bug |

Example: `0.2.0` → agent adds heartbeat feature → `0.3.0` → agent
fixes a bug → `0.3.1` → user cuts release → `1.0.0`.

The canonical version lives in `version.py` `_CODEX` list — append a
new `CodexEntry` for each bump.

---

## Session Management

### 1. Major vs Minor Changes — Chat Session Scope

- **Major changes** (new features, large refactors, new integrations):
  Start a **new chat session** before working on the idea. Each major
  change gets its own session to keep context clean and version bumps
  isolated (`Y` bump).
- **Minor changes** (bug fixes, small tweaks related to the current work):
  Keep in the **current session**. These get a `Z` bump.

> **Rule of thumb**: If it bumps `Y`, open a new session. If it bumps
> `Z` and is related to the current session's work, stay.

### 2. Bug Fixes in Current Session

If a bug is discovered during the current session **and** is related to
the work being done, fix it in the same session. Do not defer to a new
session — context is already loaded.

### 3. Compact Mode at 75% Memory

When the current memory/context capacity reaches **75%**, switch to
**compact mode**:
- Summarise completed work so far
- Drop intermediate search/read results from context
- Keep only: current task state, file paths, key decisions, and todo list
- Continue working from the compacted state

This prevents context overflow and keeps the agent productive.

### 4. Command Prompt Permissions

All command-line operations are **allowed by default** in any new session.
No need to ask for permission before running terminal commands — the agent
should proceed directly with builds, tests, installs, and any other
commands needed to complete the task.

---

## Project Conventions

- **Python 3.11** with type hints throughout
- **CrewAI** framework for multi-agent orchestration
- **Pydantic v2** models for API request/response and flow state
- **MongoDB** for PRD persistence (working ideas, finalized ideas, delivery records)
- **Embedder provider**: `google-vertex` (backed by `google-genai` SDK)
- Tests use `unittest.mock.patch` + `monkeypatch` for env vars
- All source packages have `__init__.py` with explicit `__all__`
- Logging uses `[Tag]` prefix convention (e.g. `[SlackConfig]`, `[CrewJobs]`, `[Phase 2]`)
- No decorative/box-drawing characters in log output — single-line structured messages only

---

## LLM Model Tiers

The application uses two model tiers for both Gemini and OpenAI providers.
All model defaults live in `agents/gemini_utils.py`.

### Basic Models (`GEMINI_MODEL` / `OPENAI_MODEL`)

Fast, lightweight models for orchestration and user interactions:

| Consumer | File | Purpose |
|----------|------|--------|
| Gemini intent classifier | `tools/gemini_chat.py` | Classify Slack message intent |
| OpenAI intent classifier | `tools/openai_chat.py` | Classify Slack message intent (fallback) |
| Next-step predictor | `apis/slack/_next_step.py` | Predict next user action |

### Research Models (`GEMINI_RESEARCH_MODEL` / `OPENAI_RESEARCH_MODEL`)

Deep-thinking models for complex, multi-iteration tasks:

| Consumer | File | Purpose |
|----------|------|--------|
| Product Manager agent | `agents/product_manager/agent.py` | PRD section drafting, critique, refinement |
| Idea Refiner agent | `agents/idea_refiner/agent.py` | Iterative idea enrichment (3-10 cycles) |
| Requirements Breakdown agent | `agents/requirements_breakdown/agent.py` | Requirements decomposition (3-10 cycles) |
| Orchestrator agent | `agents/orchestrator/agent.py` | Confluence publish, Jira ticket creation |
| Delivery Manager agent | `agents/orchestrator/agent.py` | Startup delivery orchestration |
| Jira PM / Architect agents | `agents/orchestrator/agent.py` | Jira Epic/Story/Task creation |

### When writing new code

- **User-facing, lightweight, or routing logic** → use `GEMINI_MODEL` / `OPENAI_MODEL`
- **Content generation, iterative refinement, or deep reasoning** → use `GEMINI_RESEARCH_MODEL` / `OPENAI_RESEARCH_MODEL`
- Import defaults from `agents/gemini_utils.py` (`DEFAULT_GEMINI_MODEL`, `DEFAULT_GEMINI_RESEARCH_MODEL`, etc.)

---

## Environment Variables (key ones)

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google Gemini LLM access || `GEMINI_MODEL` | **Basic** Gemini model — intent classification, next-step prediction, orchestration |
| `GEMINI_RESEARCH_MODEL` | **Research** Gemini model — idea refinement, requirements, PRD drafting, Confluence, Jira |
| `OPENAI_MODEL` | **Basic** OpenAI model — intent classification, lightweight interactions |
| `OPENAI_RESEARCH_MODEL` | **Research** OpenAI model — PRD section drafting & critique || `SLACK_BOT_TOKEN` | Slack bot API token (`xoxb-`) |
| `SLACK_SIGNING_SECRET` | Slack request verification |
| `SLACK_APP_ID` | For manifest auto-update |
| `SLACK_APP_CONFIGURATION_TOKEN` | Manifest API token (must be `xoxe.xoxp-` prefix) |
| `NGROK_DOMAIN` | Stable ngrok domain (avoids manifest updates) |
| `NGROK_AUTHTOKEN` | ngrok authentication |
| `MONGODB_URI` | MongoDB connection string |
| `CONFLUENCE_*` | Confluence publishing credentials |
| `JIRA_*` | Jira ticketing credentials |
| `PRD_SECTION_MIN_ITERATIONS` / `PRD_SECTION_MAX_ITERATIONS` | Section refinement bounds |
| `DEFAULT_MULTI_AGENTS` | Number of parallel agents (default: 1) |

---

## Recent Changes (2026-03-07)

- **Removed unused web research tools** (v0.13.0): Removed SerperDevTool,
  ScrapeWebsiteTool, and WebsiteSearchTool from the Product Manager agent —
  never invoked during PRD flows. Deleted tool factory modules, SERPER_API_KEY
  preflight check, and .env entry. Agent toolkit reduced from 5 to 2 tools.
- **Fix hallucinated Confluence URLs in Jira tickets** (v0.13.1): The LLM
  frequently invented fake Confluence URLs (e.g. `confluence.internal`,
  `confluence.example.com`) instead of using the real URL. The Jira tool now
  resolves the authoritative URL from MongoDB before creating tickets.
- **Phased Jira ticketing**: Replaced single-step Jira creation with a
  3-phase approach: (1) Skeleton outline for user approval, (2) Epics with
  inter-Epic dependencies + Stories categorised as Data Persistence / Data
  Layer / Data Presentation / App & Data Security, (3) Sub-tasks with 7
  required sections (Reasoning, Instructions, Sample Data, Guard Rails,
  Definition of Done, Test Cases for QE, Unit Test Cases) and dependency
  chains. New PRDState fields: `jira_skeleton`, `jira_epics_stories_output`,
  `jira_phase`. New Slack interactive callbacks for skeleton approval and
  Epics/Stories review.
- **Auto-resume on restart**: Server automatically resumes interrupted PRD flows
  with 3-strategy Slack context recovery and background threads
- **Heartbeat section tracking**: `section_start` events post to Slack and update
  `crewJobs.current_section*` fields for live progress queryability
- **crewJobs stores Slack context**: `create_job()` persists `slack_channel`/`slack_thread_ts`
- **Slack manifest validation**: Rejects non-`xoxe.` tokens with actionable guidance
- **google-genai migration**: Switched embedder from `google-generativeai` to `google-vertex`
- **Conventional logging**: Removed decorative box-drawing log output
