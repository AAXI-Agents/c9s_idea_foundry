# Session Log

> AI agent session tracking. Every new session or iteration appends an entry.

---

## Session — 2026-03-29 (v0.43.8)

**Scope**: MongoDB Schema Obsidian docs breakdown — individual collection pages with field-level schemas
**Version**: v0.43.7 → v0.43.8

### Problem
The monolithic MongoDB Schema page lacked field-level detail and API references. Users could not edit individual collection schemas, and Codex could not efficiently diff and apply changes.

### Changes

Created 9 new Obsidian pages under `obsidian/Database/`:
1. **crewJobs Schema.md** — 16 fields, status flow, timing fields, 11 repository functions
2. **workingIdeas Schema.md** — 25+ fields across 7 categories (core, timestamps, Slack, exec summary, requirements, sections, output, Jira, Figma), 30+ repository functions
3. **productRequirements Schema.md** — 11 fields, Jira ticket record sub-schema, delivery status lifecycle
4. **projectConfig Schema.md** — 14 fields, Figma OAuth fields, Slack file refs sub-schema
5. **projectMemory Schema.md** — 6 fields, memory entry formats for 3 categories (idea_iteration, knowledge, tools)
6. **agentInteraction Schema.md** — 17 fields, predicted next step sub-schema, 8 repository functions
7. **userSession Schema.md** — dual schema (user sessions vs channel sessions), 9 repository functions
8. **slackOAuth Schema.md** — 12 fields, token rotation support, 6 repository functions
9. **userSuggestions Schema.md** — 11 fields, suggestion type enum, 2 repository functions

Updated `obsidian/Database/MongoDB Schema.md`:
- Converted from monolithic reference to index page
- Links to all 9 sub-pages via `[[wikilinks]]`
- Added collection relationship diagram
- Added key relationships table with cardinality

### Tests
- No code changes — documentation only
- 2728 tests passing (unchanged)

---

## Session — 2026-03-29 (v0.43.7)

**Scope**: API Obsidian docs breakdown — individual domain pages with field-level schemas
**Version**: v0.43.6 → v0.43.7

### Problem
The monolithic API Overview page was too large for targeted edits. Users could not edit individual API domain schemas, and Codex could not efficiently diff and apply changes.

### Changes

Created 7 new Obsidian pages under `obsidian/APIs/`:
1. **Health API.md** — 5 endpoints, response schemas for health probe, version, Slack token management
2. **Projects API.md** — 5 CRUD endpoints, `ProjectCreate`/`ProjectUpdate`/`ProjectItem`/`ProjectListResponse` with full field tables (types, constraints, defaults, descriptions)
3. **Ideas API.md** — 3 endpoints, `IdeaItem`/`IdeaListResponse`/`IdeaStatusUpdate`, status lifecycle, PRD sections reference table
4. **PRD Flow API.md** — 9 endpoints, 19 models documented (all request/response/domain/nested schemas), web app integration flow, agent providers, error codes
5. **Publishing API.md** — 9 endpoints, `PendingPRDItem`/`ConfluencePublishResult`/`JiraCreateResult`/`DeliveryStatusResponse`/`WatcherStatusResponse` with field-level docs
6. **Slack API.md** — 5 endpoints, `SlackPRDKickoffRequest`/`SlackPRDKickoffResponse`, events API (dedup, thread state, smart routing), Block Kit interactions (17 command actions, flow control, publishing, session)
7. **SSO Webhooks API.md** — 1 endpoint, HMAC auth, 6 supported event types with data field tables

Updated `obsidian/APIs/API Overview.md`:
- Converted from monolithic reference to index page
- Links to all 7 sub-pages via `[[wikilinks]]`
- Retains auth, CORS, pagination, error handling reference
- Router mounting table now links to sub-pages

### Tests
- No code changes — documentation only
- 2728 tests passing (unchanged)

---

## Session — 2026-03-29 (v0.43.6)

**Scope**: API and Obsidian documentation update for web app integration
**Version**: v0.43.5 → v0.43.6

### Problem
API documentation and Obsidian knowledge base were incomplete for web app frontend integration. Missing: Projects, Ideas, and SSO Webhook path specs in OpenAPI; no web app integration guide; outdated server lifecycle steps; no security scheme definitions; CORS not documented.

### Changes

**OpenAPI spec** (`docs/openapi/openapi.json`):
1. Updated title to "Idea Foundry API" (was "CrewAI Product Feature Planner API")
2. Rewrote description as web app integration guide covering auth, pagination, error handling, CORS, status lifecycle, and typical polling flow
3. Added 7 new path files: `projects/list.json`, `projects/{project_id}.json`, `ideas/list.json`, `ideas/{run_id}.json`, `ideas/{run_id}_status.json`, `sso/webhooks_events.json`
4. Added 10 new component schemas: `ProjectCreate`, `ProjectUpdate`, `ProjectItem`, `ProjectListResponse`, `IdeaItem`, `IdeaListResponse`, `IdeaStatusUpdate`
5. Added security schemes: `ssoAuth` (JWT Bearer), `slackVerification` (HMAC), `ssoWebhook` (HMAC)
6. Added API tags for Swagger UI organization
7. Updated version to 0.43.6

**Obsidian pages**:
1. `APIs/API Overview.md` — Complete rewrite as web app integration reference with auth guide, CORS, pagination, error handling, full endpoint tables with request/response models, status lifecycle diagram, router mounting table
2. `Architecture/Project Overview.md` — Added dual-client architecture table (Web App + Slack Bot), API surface summary for web app
3. `Architecture/Server Lifecycle.md` — Updated to current startup sequence (2a archive stale, 2b resumable partition, 8b auto-resume), added CORS configuration section
4. `Architecture/Environment Variables.md` — Reorganized with web app integration section first (CORS_ALLOWED_ORIGINS, SSO vars), removed duplicate SSO section
5. `Database/MongoDB Schema.md` — Added web app data model mapping table (collection → API endpoints → purpose)

### Result
All API documentation now covers the full endpoint surface (40+ endpoints across 10 routers) with typed schemas, security definitions, and integration guides suitable for a frontend developer building a web app. 2728 tests passing.

---

## Session — 2026-03-28 (v0.43.5)

**Scope**: Fix 47-second server startup regression
**Version**: v0.43.4 → v0.43.5

### Problem
Server startup went from ~3-5s yesterday to ~47-50s today. The entire delay occurred in the `startup_markdown_review` pipeline stage's `_should_skip()` function with zero log output during the 47-second gap.

### Root Causes
1. **Heavy import chain via credential checks**: `_helpers.py`'s `_has_confluence_credentials()` and `_has_jira_credentials()` lazily imported from `tools.confluence_tool` / `tools.jira_tool`. This triggered `tools/__init__.py` which eagerly imports `file_read_tool` → `from crewai_tools import FileReadTool` → full CrewAI framework (~15s).
2. **Full document fetch from Atlas**: `find_completed_without_confluence()` fetched entire documents (avg ~100KB each, containing embedded iterations and sections) for all 11 completed ideas from MongoDB Atlas. 85 docs, 8.4MB total — the full-doc query took ~47s over the network even though only run_id fields were needed for filtering.

### Changes
1. **`orchestrator/_helpers.py`**: Inlined `_has_confluence_credentials()` and `_has_jira_credentials()` as direct env-var checks. Removed lazy imports from `tools` package entirely. Credentials checked: `ATLASSIAN_BASE_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN` (+ `JIRA_PROJECT_KEY` for Jira).
2. **`mongodb/working_ideas/_queries.py`**: Rewrote `find_completed_without_confluence()` as a three-phase query: (1) lightweight projection to get run_ids only (0.05s), (2) filter out already-published IDs, (3) fetch full docs only for unpublished run_ids (0 docs in common case).
3. **Updated tests**: `tests/mongodb/working_ideas/test_repository.py` — adapted `TestFindCompletedWithoutConfluence` mocks for two-phase query pattern.

### Result
Startup pipeline stage: **~47s → ~0.9s** (51x speedup). All 2728 tests passing.

---

## Session — 2026-03-28 (v0.43.4)

**Scope**: Fix thread-history mention gate
**Version**: v0.43.3 → v0.43.4

### Problem
Bot stopped responding to thread follow-ups after server restarts. User sent "list of ideas" in an existing thread without @mentioning the bot → message silently ignored.

### Root Cause
The `has_bot_thread_history()` check in `events_router.py` was gated behind `_bot_mentioned`. After a server restart, the in-memory thread cache was empty, so the only way to recognize the thread was via the MongoDB `agentInteractions` lookup — but that lookup was skipped because the user didn't @mention the bot.

### Solution
Removed the `_bot_mentioned` gate from the `has_thread_history` check. If the bot has already replied in a thread (per MongoDB), the thread is an established conversation — no @mention required. This matches the existing `has_flow_thread` fallback which was already ungated.

### Files Changed
- `src/.../apis/slack/events_router.py` — removed `if _bot_mentioned:` gate from `has_thread_history` check
- `tests/apis/slack/test_dm_and_pending_routing.py` — updated `TestMentionGateThreadHistory` to assert dispatch without @mention

---

## Session — 2026-03-28 (v0.43.3)

**Scope**: Engagement Manager & Idea Agent latency optimization
**Version**: v0.43.2 → v0.43.3

### Problem
Engagement Manager and Idea Agent responses took 3-5 seconds due to CrewAI `Crew.kickoff()` framework overhead (~2-4 s) — even though the underlying Gemini Flash model call only takes ~200-500 ms.

### Root Cause
CrewAI's `Crew.kickoff()` adds overhead for agent construction, task creation, tool registration, and telemetry. The conversational agents (Engagement Manager, Idea Agent) don't need this machinery — they're simple prompt-in/text-out tasks.

### Solution
1. New `generate_chat_response()` in `tools/gemini_chat.py` — direct Gemini REST API call for plain-text responses (same `urllib.request` pattern as `interpret_message()`). `thinkingBudget=0`, 30s timeout, 2 retries.
2. `handle_unknown_intent()` now uses fast path by default. Falls back to CrewAI on failure or when `ENGAGEMENT_MANAGER_USE_CREWAI=true`.
3. `detect_user_steering()` same fast/fallback pattern (also controlled by `ENGAGEMENT_MANAGER_USE_CREWAI`).
4. `handle_idea_query()` same fast/fallback pattern (controlled by `IDEA_AGENT_USE_CREWAI=true`).
5. 21 new tests covering fast path, fallback behavior, and `generate_chat_response()`.
6. 2728 tests passing.

### Files Changed
- `src/.../tools/gemini_chat.py` — added `generate_chat_response()`
- `src/.../agents/engagement_manager/agent.py` — split into fast/crewai paths
- `src/.../agents/idea_agent/agent.py` — split into fast/crewai paths
- `tests/tools/test_gemini_chat.py` — 8 new tests
- `tests/agents/test_engagement_manager.py` — 9 new tests
- `tests/agents/test_idea_agent.py` — 6 new tests

---

## Session — 2026-03-28 (v0.43.2)

**Scope**: Immediate "Thinking…" acknowledgment on all Slack interactions
**Version**: v0.43.1 → v0.43.2

### Problem
When users sent messages or clicked buttons, there was no immediate feedback — the bot was silently processing (LLM classification, handler dispatch) for several seconds before any response appeared.

### Solution
1. New `_post_thinking()` in `_message_handler.py` — posts `:thinking_face: <@user> Thinking…` via best-effort `chat_postMessage`. Never raises.
2. `interpret_and_act()` calls `_post_thinking()` before `_interpret_and_act_inner()` — covers all @mention + thread-reply paths that reach the LLM.
3. `cmd_*` button clicks in `_dispatch.py` now post a "Thinking…" ack via `_post_ack()` (same pattern as project-session button acks).
4. Thread replies routed to pending-state handlers, feedback queues, and setup wizards are unaffected — those respond instantly.

### Files Modified
- `src/.../apis/slack/_message_handler.py` — added `_post_thinking()`, wired into `interpret_and_act()`
- `src/.../apis/slack/interactions_router/_dispatch.py` — added "Thinking…" ack for cmd_* buttons

### Tests
- 2707 tests passing (no new tests needed — defensive `_post_thinking` exits silently in test env)

---

## Session — 2026-03-27 (v0.43.1)

**Scope**: Reduce Slack iteration noise; enhance section/exec-summary completion messages with content summary + file fallback
**Version**: v0.43.0 → v0.43.1

### Problem
During PRD generation, every section iteration and executive summary iteration posted a message to the Slack thread — flooding the thread with per-iteration refinement noise. Completion messages also lacked content summaries and didn't tag the user.

### Solution
1. **Suppressed iteration noise** — `section_iteration` and `exec_summary_iteration` events in `make_progress_poster()` now pass silently (no Slack messages). Only `section_start` and completion events are shown.
2. **Enhanced completion messages** — `section_complete` and `executive_summary_complete` now:
   - Tag the user (`<@user>`) when a user ID is available (interactive flows)
   - Include the full section content as an inline preview
   - If content exceeds Slack's 2800-char block limit, truncate with hint and upload full content as a downloadable `.md` file via `files_upload_v2`
3. **Content in event details** — `prd_flow.py` and `_executive_summary.py` now include `content` in the `section_complete` and `executive_summary_complete` event detail dicts.

### Files Modified
- `src/.../apis/slack/_flow_handlers.py` — suppress iteration events, enhance completion events with tag/summary/file fallback
- `src/.../flows/prd_flow.py` — add `content` to `section_complete` event details (both emission sites)
- `src/.../flows/_executive_summary.py` — add `content` to `executive_summary_complete` event details (both emission sites)
- `tests/.../test_progress_poster.py` — updated suppression test, added 12 new tests
- `tests/.../test_automated_flow.py` — updated 3 tests for suppression behavior

### Tests
- 2707 total tests passing (2696 → 2707, net +11)
- 12 new tests in `test_progress_poster.py` (suppression, user tag, content summary, file fallback)
- 3 updated tests in `test_automated_flow.py` (iteration suppression)

---

## Session — 2026-03-27 (v0.43.0)

**Scope**: New Idea Agent for in-thread iteration queries + v0.42.4 security audit completion
**Version**: v0.42.3 → v0.42.4 → v0.43.0

### Problem
When users asked questions like "what is the current summary?" during an active idea iteration thread, the Engagement Manager responded with generic navigation help instead of specific iteration data. Users couldn't get information about the current state of their idea, refined text, sections, or critiques during active flows.

### Solution — Idea Agent (v0.43.0)
New `agents/idea_agent/` module with:
- **agent.yaml** — "Idea Analyst & Iteration Advisor" role with backstory covering real-time situational awareness
- **tasks.yaml** — `idea_query_task` for information requests, steering feedback, and gap analysis
- **agent.py** — `create_idea_agent()`, `handle_idea_query()`, `extract_steering_feedback()`, `_extract_iteration_context()`
- **_extract_iteration_context()** — builds structured context from working-idea MongoDB document (status, refined idea, refinement history, exec summary, requirements, engineering plan, sections, critiques)
- **Steering** — when users provide direction feedback, the agent produces structured recommendations persisted to `agentInteraction` for downstream agents
- **_handle_idea_agent()** in `_message_handler.py` — posts response and handles steering persistence
- **Engagement Manager disengaged** — during active flows (inprogress/paused), both `general_question` and unknown intents route to the Idea Agent instead of the Engagement Manager

### Security Audit Completion (v0.42.4)
All HIGH and MEDIUM findings from ISO 27001 audit fixed and tested:
- XSS, SSRF, figma_api_key exposure, error detail leakage, input validation, Slack verify warning, path traversal, injection guards, auth on health endpoints, query limit bounds

### Tests
- 21 new Idea Agent tests
- 2696 total tests passing (up from 2675)

### Files Created
- `src/.../agents/idea_agent/__init__.py`
- `src/.../agents/idea_agent/agent.py`
- `src/.../agents/idea_agent/config/agent.yaml`
- `src/.../agents/idea_agent/config/tasks.yaml`
- `tests/agents/test_idea_agent.py`

### Files Modified
- `src/.../apis/slack/_message_handler.py` — added `_handle_idea_agent()`, rewired `general_question` and unknown intent dispatch
- `tests/apis/slack/test_flow_thread_routing.py` — updated summary integration test for Idea Agent routing
- `src/.../version.py` — v0.42.4 + v0.43.0 entries
- `obsidian/Agents/Agent Roles.md` — Idea Agent entry + Engagement Manager disengagement note
- `obsidian/Architecture/Module Map.md` — idea_agent/ entry
- `obsidian/Changelog/Version History.md` — v0.42.4 + v0.43.0
- `obsidian/Sessions/Session Log.md` — this entry

---

## Session — 2026-03-27 (v0.42.3)

**Scope**: Root-cause fix — save_iteration() resurrecting archived ideas
**Version**: v0.42.2 → v0.42.3

### Problem
CrewAI flows kept running for archived ideas even after v0.42.2 cancel mechanism fixes. The flow for `d64725f5e861` was auto-resumed on every server restart despite being "archived".

### Root Cause (the real bug)
`save_iteration()` in `_sections.py` unconditionally set `status: "inprogress"` via `$set` on every section save. This meant:
1. User archives idea → MongoDB status = "archived"
2. Flow thread still running (cancel signal takes time to reach)
3. Next `save_iteration()` call → MongoDB status overwritten to "inprogress"
4. Server restart → `find_resumable_on_startup()` finds it as "inprogress" → auto-resumes
5. Cycle repeats infinitely

### Fixes
1. **`save_iteration()`** — checks current MongoDB status before writing; terminal statuses (archived, completed, failed) are never overwritten
2. **`save_executive_summary_iteration()`** — same guard
3. **`save_pipeline_step()`** — same guard
4. **`resume_prd_flow()`** — queries MongoDB and refuses to resume archived/failed runs
5. **`generate_sections()`** — early `check_cancelled()` before any pipeline work
6. **MongoDB fix** — manually archived `d64725f5e861` (was stuck as inprogress)

### Files Changed
- `src/.../mongodb/working_ideas/_sections.py` — 3 functions guarded against terminal status overwrite
- `src/.../apis/prd/service.py` — archive guard in resume_prd_flow
- `src/.../flows/prd_flow.py` — early cancellation check

### Tests
2675 passing (0 failing, 1 flaky unrelated test)

---

## Session — 2026-03-27 (v0.42.2)

**Scope**: Fix archive cancellation for resumed/auto-resumed flows
**Version**: v0.42.1 → v0.42.2

### Problem
Server was still running CrewAI flows for archived ideas. The v0.42.1 cancel mechanism only worked for flows started via `kick_off_prd_flow()` (Slack interactive start). Resumed flows (auto-resume on startup, manual resume) and the REST API archive path were missing critical cancel plumbing.

### Root Causes
1. `resume_prd_flow()` did not register a `cancel_event` — `request_cancel()` found nothing to set
2. `resume_prd_flow()` did not catch `FlowCancelled` — cancelled flows got paused instead of archived
3. `_run_slack_resume_flow()` (startup auto-resume) never registered cancel events
4. REST API `PATCH /ideas/{run_id}/status` archive path only called `mark_archived()` — no cancel signal, no gate unblocking, no crew job archival
5. `request_cancel()` silently did nothing when no event existed for the run_id

### Fixes
1. `resume_prd_flow()` — registers `cancel_events[run_id]`, catches `FlowCancelled`, cleans up in finally
2. `_run_slack_resume_flow()` — registers cancel event before calling resume
3. `request_cancel()` — creates + sets event if missing (defensive, archive always works)
4. REST API archive — calls `request_cancel()`, `_unblock_gates_for_cancel()`, `update_job_status("archived")`
5. `_resume_flow_background()` — checks MongoDB status before resuming, skips archived ideas
6. Fixed `completed_at` None validation error crashing GET /ideas

### Files Changed
- `src/.../apis/prd/service.py` — FlowCancelled handling + cancel_events registration in resume_prd_flow
- `src/.../apis/shared.py` — request_cancel creates event if missing
- `src/.../apis/slack/router.py` — cancel event registration in _run_slack_resume_flow
- `src/.../apis/ideas/router.py` — archive path now cancels flows + completed_at fix
- `src/.../apis/__init__.py` — _resume_flow_background checks archived status
- `tests/.../test_archive_cancel.py` — updated tests for new request_cancel behavior

### Tests
2675 passing (0 failing)

---

## Session — 2026-03-27 (v0.42.1)

**Scope**: Archive stops active flows — cooperative cancellation + scan cleanup
**Version**: v0.42.0 → v0.42.1

### Work Done
1. **FlowCancelled exception + cancel registry** — Added `FlowCancelled` exception and `cancel_events: dict[str, threading.Event]` registry to `shared.py`. Helper functions: `request_cancel()`, `is_cancelled()`, `check_cancelled()`.

2. **kick_off_prd_flow cancel event** — Creates `threading.Event()` and stores in `cancel_events[run_id]` before starting the daemon thread.

3. **execute_archive_idea signals cancel** — Calls `request_cancel(run_id)` and `_unblock_gates_for_cancel(run_id)` before archiving DB records.

4. **_unblock_gates_for_cancel** — New helper that sets all pending gate events for a run_id: exec_feedback, exec_completion, requirements_approval, and approval_events (interactive mode). Unblocked threads flow through to the next `check_cancelled()` checkpoint.

5. **PRDFlow cancellation checkpoints** — Added `check_cancelled(run_id)` at 6 strategic points in `generate_sections()`: after pipeline, before exec summary, before requirements, before CEO review, before eng plan, before each Phase 2 section.

6. **run_prd_flow FlowCancelled handler** — Catches `FlowCancelled`, sets `FAILED` status with "CANCELLED" error, job status "archived". Cleanup in finally block pops `cancel_events`.

7. **Interactive flow runner + router** — `_flow_runner.py` catches `FlowCancelled` with same status handling. Router suppresses error message for cancelled flows.

8. **get_run_documents() archived filter** — Changed from `$ne "completed"` to `$nin ["completed", "archived"]` so archived docs are not returned by resume/restart lookups.

9. **archive_stale_jobs_on_startup()** — New startup step in crew_jobs/repository.py. Cross-references non-final crew jobs against workingIdeas collection; archives jobs whose ideas have `status: "archived"`. Called in `apis/__init__.py` lifespan step 2a.

10. **Stale flow cleanup** — Cleaned up `d64725f5e861` ("new idea") which was stuck `inprogress` and auto-resumed every server restart (command-phrase guard issue from v0.42.0).

### Tests
- 17 new tests in `test_archive_cancel.py`
- 8 test classes: TestCancelRegistry, TestUnblockGates, TestArchiveSignalsCancel, TestRunPrdFlowCancelled, TestKickOffRegistersCancel, TestArchiveCancelsWaitingFlow, TestGetRunDocumentsArchived, TestArchiveStaleJobsOnStartup
- Updated `test_repository.py` assertion for `get_run_documents` query change
- Integration test verifies a flow thread waiting on a gate is unblocked and receives FlowCancelled

---

## Session — 2026-03-26 (v0.42.0)

**Scope**: Summarize ideas, user suggestions, admin config guard, archive knowledge file
**Version**: v0.41.0 → v0.42.0

### Work Done
1. **Summarize ideas intent** — New `summarize_ideas` intent with `_SUMMARIZE_IDEAS_PHRASES` added before `list_ideas` in priority order. `_handle_summarize_ideas()` uses Engagement Manager for AI-powered narrative summary. `BTN_SUMMARIZE_IDEAS` + `cmd_summarize_ideas` dispatch.

2. **User suggestions collection** — New `userSuggestions` MongoDB collection with `log_suggestion()` and `find_suggestions_by_project()`. Tracks `clarification_needed` (when Engagement Manager prefixes response with `[CLARIFICATION]`) and `unknown_intent` (when agent fails entirely).

3. **Engagement Manager category D** — `tasks.yaml` updated with category D "clarification needed" for ambiguous intents. Agent asked to prefix with `[CLARIFICATION]` so system can track.

4. **Admin-only config button** — `product_list_blocks()` now accepts `is_admin` kwarg; Config button hidden for non-admin users. `_handle_product_config()` adds `can_manage_memory()` guard. Callers in `_session_ideas.py` and `_session_products.py` pass admin status.

5. **Command-phrase idea guard** — New `_is_command_phrase_idea()` in `_message_handler.py` prevents auto-starting PRD flow when LLM extracts command phrases ("new idea", "add new idea", "create a prd") as the idea text. Prompts user for real idea instead.

6. **Archive moves knowledge file** — `archive_idea_knowledge()` in `project_knowledge.py` moves `projects/{name}/ideas/{title}.md` → `projects/{name}/archives/{YYYY}/{MM}/{DD}/{title}.md`. Called from `execute_archive_idea()`. Project overview page refreshed after move.

### Tests
- 22 new tests in `test_v042_fixes.py`
- Existing test updated: `test_product_list.py` (is_admin=True), `test_command_handler.py` (CMD_ACTIONS count 17), `test_setup_mongodb.py` (userSuggestions in EXPECTED)

---

## Session — 2026-03-26 (v0.41.0)

**Scope**: UX Design Flow Refactor — Standalone 2-Phase Post-PRD Flow
**Version**: v0.40.0 → v0.41.0

### Work Done
1. **Phase 1.5c removed from PRD flow** — `_run_ux_design` method deleted from PRDFlow; UX design import and Phase 1.5c block removed from `generate_sections()`. UX design is now a standalone post-PRD flow.

2. **_ux_design.py fully rewritten** — New 2-phase architecture:
   - `run_ux_design_draft()` — Phase 1: UX Designer + Design Partner collaborate on initial design spec
   - `run_ux_design_review()` — Phase 2: Senior Designer applies 7-pass review and produces final spec
   - `run_ux_design_flow()` — Orchestrates both phases
   - `_write_design_file()` — Fixed-name file writer (overwrites existing, no timestamp proliferation)
   - `_resolve_output_dir()` — Project-aware output directory resolution
   - `run_ux_design()` — Legacy backward-compat entry point

3. **File proliferation fix** — Changed from timestamped filenames (`ux_design_YYYYMMDD_HHMMSS.md`, 30+ files) to 2 fixed files: `ux_design_draft.md` and `ux_design_final.md`

4. **3 new YAML configs** — `design_partner.yaml` (gstack design-consultation, AI slop blacklist), `senior_designer.yaml` (gstack plan-design-review, 7-pass scoring), `ux_design_flow_tasks.yaml` (2 task definitions with 12-section spec + review criteria)

5. **3 new agent factories** — `create_design_partner()`, `create_senior_designer()`, `get_ux_design_flow_task_configs()` in `agent.py`, all with proper credential checks

6. **Standalone flow entry point** — `ux_design_flow.py` with `kick_off_ux_design_flow()`

7. **Finalization trigger** — `_trigger_ux_design_flow()` in `_finalization.py` with skip guards (no EPS, already completed/prompt_ready) and error propagation (BillingError/ModelBusyError/ShutdownError)

8. **Test suite rewritten** — 37 tests across 13 classes in `test_ux_design.py`; 3 test_prd_flow.py patches updated to remove `_run_ux_design` references

### Files Created
- `agents/ux_designer/config/design_partner.yaml`
- `agents/ux_designer/config/senior_designer.yaml`
- `agents/ux_designer/config/ux_design_flow_tasks.yaml`
- `flows/ux_design_flow.py`

### Files Modified
- `agents/ux_designer/agent.py` — 3 new factories + credential checks
- `agents/ux_designer/__init__.py` — exports updated
- `flows/_ux_design.py` — full rewrite (2-phase architecture)
- `flows/_finalization.py` — _trigger_ux_design_flow() added
- `flows/prd_flow.py` — Phase 1.5c removed
- `flows/__init__.py` — kick_off_ux_design_flow export
- `tests/flows/test_ux_design.py` — rewritten (37 tests)
- `tests/flows/test_prd_flow.py` — _mock_ux patches removed
- `version.py` — v0.41.0 CodexEntry

### Tests
- 37 UX design tests (13 classes)
- 2636 total tests passing

---

## Session — 2026-03-25 (v0.40.0)

**Scope**: Engagement Manager Project Knowledge Awareness
**Version**: v0.39.0 → v0.40.0

### Work Done
1. **_build_project_tools()** — New function in agent.py builds FileReadTool + DirectoryReadTool scoped to a project's knowledge folder (`src/projects/{name}/`). Loads completed-ideas context from MongoDB via `load_completed_ideas_context()`. Returns `(tools, ideas_context)` tuple; graceful fallback on DB/filesystem errors.

2. **create_engagement_manager(project_id)** — Now accepts optional `project_id`. When provided, agent receives file-reading tools and ideas context is appended to backstory, enabling holistic project knowledge queries.

3. **handle_unknown_intent(project_id)** — Now accepts optional `project_id`, builds `{project_knowledge}` template variable from completed ideas, passes to task description.

4. **engagement_response_task rewrite** — Task now classifies user messages into: (A) Knowledge question — summarize/compare ideas, detect duplication/synergies using file tools; (B) Action intent — recommend button clicks; (C) Idea feedback/steering. New `{project_knowledge}` template variable.

5. **agent.yaml backstory update** — Added "Project Knowledge & Idea Awareness" section describing file-reading capabilities, idea comparison, and duplication detection.

6. **_message_handler.py** — `handle_unknown_intent()` call now passes `project_id=session_project_id`.

### Files Modified
- `src/.../agents/engagement_manager/agent.py` — new `_build_project_tools()`, updated `create_engagement_manager()` + `handle_unknown_intent()`
- `src/.../agents/engagement_manager/config/tasks.yaml` — engagement_response_task rewritten
- `src/.../agents/engagement_manager/config/agent.yaml` — backstory expanded
- `src/.../apis/slack/_message_handler.py` — project_id passthrough
- `src/.../version.py` — v0.40.0 CodexEntry
- `tests/agents/test_engagement_manager.py` — 12 new tests (59 total)
- `obsidian/Sessions/Session Log.md` — v0.40.0 entry
- `obsidian/Changelog/Version History.md` — v0.40.0 entry

### Tests
- 59 engagement manager tests passing (12 new: 4 _build_project_tools, 3 create with project, 4 handle_unknown_intent with project, 1 YAML placeholder)
- 2614 total tests passing

---

## Session — 2026-03-24 (v0.39.0)

**Scope**: Engagement Manager PRD Orchestrator — Heartbeats, Steering, Session Isolation
**Version**: v0.38.0 → v0.39.0

### Work Done
1. **agent.yaml rewrite** — Expanded role to "Engagement Manager, PRD Orchestrator & Navigation Guide". Full backstory with agent team knowledge, 2-step orchestration strategy (Step 1 sequential: Idea Refinement → Exec Summary; Step 2 parallel/coordinated: remaining agents), heartbeat protocol, user steering detection, session isolation.

2. **3 new tasks in tasks.yaml** — `idea_to_prd_orchestration_task` (full lifecycle orchestration plan with template variables for idea, user, run, phase, history, steering), `heartbeat_update_task` (emoji-prefixed status updates), `user_steering_detection_task` (IGNORE/STEERING/QUESTION/FEEDBACK/UNRELATED classification with session isolation fast-path).

3. **5 new functions in agent.py** — `generate_heartbeat()` (template-based instant heartbeats, no LLM), `make_heartbeat_progress_callback()` (wraps PRD flow progress events into user-friendly messages via _PROGRESS_EVENT_MAP), `detect_user_steering()` (LLM-powered classification with fast-path session isolation for non-initiator messages), `_parse_steering_result()` (JSON/keyword parser), `orchestrate_idea_to_prd()` (wraps run_prd_flow with heartbeat callbacks and session isolation).

4. **.gitignore** — Changed `output/prds/` to `output/` to ignore entire output folder.

5. **conftest.py fix** — Raised recursion limit to 5000 for crewai 1.9.x + starlette/pydantic compatibility (model_rebuild exceeds default 1000 limit).

### Files Modified
- `.gitignore` — output/ folder fully ignored
- `src/.../agents/engagement_manager/config/agent.yaml` — complete rewrite
- `src/.../agents/engagement_manager/config/tasks.yaml` — 3 new tasks added
- `src/.../agents/engagement_manager/agent.py` — 5 new functions, expanded imports
- `src/.../agents/engagement_manager/__init__.py` — 4 new exports
- `src/.../version.py` — v0.39.0 CodexEntry
- `tests/conftest.py` — recursion limit fix
- `tests/agents/test_engagement_manager.py` — 32 new tests (47 total)
- `obsidian/Changelog/Version History.md` — v0.39.0 entry
- `obsidian/Agents/Agent Roles.md` — expanded Engagement Manager section
- `obsidian/Architecture/Module Map.md` — updated engagement_manager description

### Tests
- 47 engagement manager tests passing (32 new: 3 YAML config, 7 heartbeat, 4 progress callback, 3 steering detection, 4 steering parser, 6 orchestration, 2 progress event map + 15 existing)

---

## Session — 2026-03-24 (v0.38.0)

**Scope**: Publication Safety Overhaul — User-Triggered Publishing Only
**Version**: v0.37.1 → v0.38.0

### Work Done
1. **Duplicate Confluence fix** — `publish_to_confluence()` now accepts `page_id` parameter; when stored `confluence_page_id` exists in delivery record, page is updated by ID instead of creating duplicates. Added `_get_page_by_id()` to `confluence_tool.py`. Orchestrator `_confluence.py` and publishing service pass stored page_id.

2. **Auto-publish removal** — `_run_auto_post_completion()` gutted to log + notify only (no crew kickoff). `_run_phased_post_completion()` requires Confluence already published before starting Jira. Startup functions (`_cli_startup`, `components/startup`) now discovery-only. File watcher disabled. `build_startup_markdown_review_stage()` always skips.

3. **Confluence prerequisite for Jira** — All Jira creation paths (`_delivery_action_handler`, `_product_list_handler`, `_flow_handlers`) check for `confluence_url` before allowing Jira. User guided to publish Confluence first with interactive button. Removed `require_confluence=False` overrides.

### Files Modified
- `src/.../tools/confluence_tool.py` — added `_get_page_by_id()`, `page_id` param to `publish_to_confluence()`
- `src/.../orchestrator/_confluence.py` — pass stored page_id for updates
- `src/.../apis/publishing/service.py` — pass stored page_id in `publish_confluence_single/all()`
- `src/.../flows/_finalization.py` — gutted auto-publish, Confluence prerequisite in phased
- `src/.../orchestrator/_startup_review.py` — always-skip discovery-only
- `src/.../components/startup.py` — discovery-only
- `src/.../_cli_startup.py` — discovery-only
- `src/.../apis/publishing/watcher.py` — disabled
- `src/.../apis/slack/_flow_handlers.py` — Confluence-only publish, Jira button after
- `src/.../apis/slack/interactions_router/_delivery_action_handler.py` — Confluence prerequisite check
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — Confluence prerequisite check
- `tests/` — 23 tests updated across 5 test files

### Test Results
- 2571 passed, 0 failed

---

## Session 001 — 2026-03-08

**Scope**: Obsidian Knowledge Base Setup
**Version**: v0.15.4 → (no version change — documentation only)

### Work Done
- Created Obsidian vault at `c9-prd-planner/C9 Product Ideas Planner`
- Populated 18 knowledge pages covering:
  - Architecture (Project Overview, Module Map, Server Lifecycle, Environment Variables, Coding Standards)
  - Agents (Agent Roles, LLM Model Tiers)
  - APIs (API Overview)
  - Changelog (Version History — full v0.1.0 to v0.15.4)
  - Database (MongoDB Schema)
  - Flows (PRD Flow)
  - Integrations (Slack, Confluence, Jira)
  - Knowledge (PRD Guidelines, User Preferences)
  - Orchestrator (Orchestrator Overview)
  - Testing (Testing Guide)
  - Tools (Tools Overview)
- Updated CODEX.md with Obsidian Knowledge Management section
- Added session/iteration update requirements to coding standards

### Key Decisions
- Vault path: `/Users/c9admin/Library/Mobile Documents/iCloud~md~obsidian/Documents/c9-prd-planner/C9 Product Ideas Planner`
- Used Obsidian `[[wikilinks]]` for inter-note navigation
- Session entries stored in `Sessions/Session Log.md`
- Template provided at `Templates/Session Entry.md`

### Files Modified
- `CODEX.md` — Added Obsidian Knowledge Management section
- 18 new Obsidian vault files created

---

<!-- Append new sessions below this line -->

## Session 002 — 2026-03-08

**Scope**: LLM 500 Error Handling + CODEX Knowledge Update
**Version**: v0.15.4 → v0.15.5

### Work Done
- Reviewed `crewai.log` for LLM errors — no actual HTTP 500s found, but discovered inadequate error handling
- `retry.py`: Added `_SERVER_ERROR_PATTERNS` for 500/502/504 classification with proper retry + backoff
- `gemini_chat.py`: Increased retries 2→3, added exponential backoff, non-retryable 4xx fail immediately
- `openai_chat.py`: Added retry logic (was zero retries), 3 attempts with backoff, retryable status codes
- Added 11 new tests across `test_retry.py`, `test_gemini_chat.py`, `test_openai_chat.py`
- Updated CODEX.md session-end checklist to require CrewAI knowledge source updates

### Files Modified
- `src/.../scripts/retry.py` — Server error patterns, retry classification
- `src/.../tools/gemini_chat.py` — Retry with backoff
- `src/.../tools/openai_chat.py` — Retry from scratch
- `tests/test_retry.py` — 5 server error tests
- `tests/tools/test_gemini_chat.py` — 3 retry tests
- `tests/tools/test_openai_chat.py` — 3 retry tests
- `CODEX.md` — Knowledge update requirement

---

## Session 003 — 2026-03-09

**Scope**: Fix Shutdown Error Handling
**Version**: v0.15.5 → v0.15.6

### Work Done
- Reviewed `crewai.log` — found "cannot schedule new futures after shutdown" errors causing 60+ seconds of wasted retries after server shutdown
- `retry.py`: Added `ShutdownError` class and `_SHUTDOWN_PATTERNS` — detected immediately with zero retries
- `_section_loop.py`: `ShutdownError` now re-raises instead of force-approving sections with incomplete content
- `service.py`: `ShutdownError` caught in both `run_prd_flow` and `resume_prd_flow` — pauses flow for auto-resume
- `apis/__init__.py`: Global exception handler returns HTTP 503 for `ShutdownError`
- Added 5 new tests to `tests/test_retry.py`

### Key Decisions
- Shutdown detection placed BEFORE model-busy check in retry loop to catch it earliest
- ShutdownError is a subclass of LLMError (same hierarchy as BillingError, ModelBusyError)
- Flows pause on shutdown rather than fail — enables auto-resume on next server start

### Files Modified
- `src/.../scripts/retry.py` — ShutdownError, _SHUTDOWN_PATTERNS
- `src/.../flows/_section_loop.py` — Re-raise ShutdownError
- `src/.../apis/prd/service.py` — Catch ShutdownError in both flow functions
- `src/.../apis/__init__.py` — Global 503 handler for ShutdownError
- `tests/test_retry.py` — 5 shutdown tests
- `src/.../version.py` — v0.15.6

---

## Session 004 — 2026-03-09

**Scope**: Critical Jira Approval Gate Regression Fix
**Version**: v0.15.7 → v0.15.8

### Problem
A prior fix (v0.15.7, Confluence slowness) added `confluence_only` param
to `build_post_completion_crew()` but failed to propagate it to ALL
callers. Five distinct code paths could create Jira tickets without user
approval:
1. `_run_auto_post_completion()` — called `build_post_completion_crew(flow)` without `confluence_only=True`
2. `build_startup_delivery_crew()` — had no `confluence_only` parameter at all
3. CLI startup (`_cli_startup.py`) — called startup crew without `confluence_only`
4. Server startup (`components/startup.py`) — called startup crew without `confluence_only`
5. `execute_restart_prd()` — called `kick_off_prd_flow()` without `interactive=True`, falling to auto-approve path

### Fixes Applied
1. `_finalization.py`: `_run_auto_post_completion()` → `confluence_only=True`
2. `_startup_delivery.py`: Added `confluence_only: bool = False` parameter, gated `jira_needed` behind it
3. `_cli_startup.py`: Caller passes `confluence_only=True`
4. `components/startup.py`: Caller passes `confluence_only=True`
5. `_flow_handlers.py`: `execute_restart_prd()` → `interactive=True`
6. Created 23 regression tests in `tests/flows/test_jira_approval_gate.py`

### Lesson Learned
Adding a safety gate parameter is not enough — it must be verified at
EVERY call site. When adding parameters that control security-critical
behavior, trace every caller chain end-to-end and add tests for each.

### Files Modified
- `src/.../flows/_finalization.py` — `confluence_only=True` in auto path
- `src/.../orchestrator/_startup_delivery.py` — `confluence_only` param
- `src/.../apis/slack/_flow_handlers.py` — `interactive=True` in restart
- `src/.../_cli_startup.py` — `confluence_only=True` propagation
- `src/.../components/startup.py` — `confluence_only=True` propagation
- `tests/flows/test_jira_approval_gate.py` — 23 regression tests (NEW)
- `tests/flows/test_prd_flow.py` — Updated 2 existing tests for new API
- `CODEX.md` — Jira Approval Gate invariant documented
- `obsidian/Architecture/Coding Standards.md` — §6 Jira approval gate
- `obsidian/Testing/Testing Guide.md` — Regression test documentation
- `obsidian/Orchestrator/Orchestrator Overview.md` — confluence_only docs
- `src/.../version.py` — v0.15.8

---

## Session 004 — 2026-03-09

**Scope**: Fix Confluence publish notification and Jira next-step flow
**Version**: v0.15.9

### Bugs Found (from production logs)
1. **No heartbeat during Confluence publish** — When user clicked "Publish to Confluence" from product list, `_handle_confluence_publish()` called `build_post_completion_crew()` without a `progress_callback`. Users saw a 2-4 minute silent gap.
2. **No Jira next-step notification** — After Confluence publish succeeded, the handler posted a success message but never offered the next step to create the Jira skeleton.
3. **Incorrect button label** — The `delivery_create_jira` button displayed "Create Jira Tickets" but the action always triggers skeleton generation (Phase 1 of the phased Jira workflow). Label should say "Create Jira Skeleton".

### Fixes Applied
- Added heartbeat `progress_callback` to `_handle_confluence_publish()` — posts crew step updates to Slack thread in real-time
- Added Jira next-step button after Confluence publish completes (only when Jira credentials configured)
- Changed button label from "Create Jira Tickets" to "Create Jira Skeleton" across all touchpoints:
  - `_delivery_action_blocks.py` — button text
  - `_dispatch.py` — ack message
  - `_flow_handlers.py` — fallback text
  - `_product_list_handler.py` — fallback text
  - `_delivery_action_handler.py` — docstring

### Key Lesson
The `delivery_create_jira` action_id always routes to `_do_create_jira()` → `_run_jira_phase(run_id, "skeleton", ...)`. The user-facing label must match the actual first phase of the phased workflow (skeleton), not the overarching capability (tickets).

### Tests Added/Modified
- `test_product_list.py` — 3 new tests in `TestHandleConfluencePublishHeartbeatAndNextStep`:
  - `test_progress_callback_posted_to_slack`
  - `test_jira_next_step_button_offered`
  - `test_no_jira_button_without_credentials`
- `test_delivery_action_blocks.py` — 1 new regression test: `test_button_label_says_skeleton`
- Updated existing tests to match new "Create Jira Skeleton" text

### Files Modified
- `src/.../apis/slack/blocks/_delivery_action_blocks.py` — Button label → "Create Jira Skeleton"
- `src/.../apis/slack/interactions_router/_dispatch.py` — Ack message → "Creating Jira skeleton"
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — Added heartbeat + next-step button
- `src/.../apis/slack/interactions_router/_delivery_action_handler.py` — Updated docstring
- `src/.../apis/slack/_flow_handlers.py` — Fallback text → "Create Jira Skeleton"
- `tests/apis/slack/test_product_list.py` — 3 new tests + 2 assertion updates
- `tests/apis/slack/test_delivery_action_blocks.py` — 1 new regression test
- `obsidian/Integrations/Slack Integration.md` — Delivery action button description
- `obsidian/Integrations/Jira Integration.md` — Post-Confluence next step section

---

## Session 005 — 2026-03-09

**Scope**: Fix delivery state reset — scheduler overwrites confluence_published
**Version**: v0.15.9 → v0.15.10

### Bug Found (from production logs)
After Confluence publish succeeded, re-listing products showed "Publish to Confluence" again instead of "Start Jira Skeleton". The product list builder correctly checks `confluence_published`, but the field was being overwritten on every PublishScheduler sweep.

### Root Cause
`_discover_pending_deliveries()` in `_startup_delivery.py` had a data source mismatch. When `jira_phase == "subtasks_done"`, it called `upsert_delivery_record()` with:
```python
confluence_published=bool(doc.get("confluence_url"))  # from workingIdeas
```
But `save_confluence_url()` was removed from the codebase — the Confluence URL is only stored in the `productRequirements` delivery record, not `workingIdeas`. So `doc.get("confluence_url")` returned `None`, overwriting `confluence_published` from `True` to `False` on every scan.

The log evidence showed a repeating cycle:
1. `persist_post_completion()` saves `confluence_published=True` ✓
2. 5 min later: scheduler scan → `_discover_pending_deliveries()` → overwrites with `False` ✗
3. Next scan: `_discover_publishable_prds()` finds 1 without Confluence → RE-PUBLISHES

### Fixes Applied
1. **subtasks_done branch** — Only pass `jira_completed=True` to `upsert_delivery_record()`. No confluence fields, so existing state is preserved.
2. **Fully-done branch** — Read `confluence_url` from delivery record first, falling back to workingIdeas doc.
3. **Items dict** — Source `confluence_url` from delivery record instead of workingIdeas doc.

### Tests Added
- `test_marks_jira_completed_when_subtasks_done` — Updated to verify only `jira_completed` is passed
- `test_subtasks_done_preserves_confluence_state` — Regression: delivery record has `confluence_published=True` but workingIdeas has no URL → must NOT reset
- `test_fully_done_reads_confluence_url_from_delivery_record` — Regression: URL only in delivery record, not workingIdeas → must be sourced correctly
- `test_item_confluence_url_from_delivery_record` — Item dict inherits URL from delivery record

### Files Modified
- `src/.../orchestrator/_startup_delivery.py` — 3 fixes for data source mismatch
- `tests/orchestrator/test_startup_delivery.py` — 3 new regression tests + 1 updated test
- `src/.../version.py` — v0.15.10
- `obsidian/Changelog/Version History.md` — v0.15.10 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 006 — 2026-03-09

**Scope**: Remove autonomous Jira detection; fix stale jira_phase data
**Version**: v0.15.10 → v0.15.11

### Bug Found (from production QA)
Product list showed ":white_check_mark: Jira Ticketing" for a product where Jira skeleton hadn't been started. User never approved any Jira creation.

### Root Cause
Bad data from autonomous Jira runs before the approval gate (v0.15.8). `persist_post_completion()` was detecting Jira keywords in crew output and autonomously setting `jira_phase=subtasks_done` + `jira_completed=True`, even for `confluence_only` crews. This violated the approval gate invariant.

### Data Fix
Created one-time script `scripts/fix_stale_jira_phase.py`:
1. Found docs with `jira_phase=subtasks_done` but no `jira_skeleton` (proving they weren't from interactive flow)
2. Reset `jira_phase=""` and `jira_completed=False`
3. Verified fix
4. Deleted script after use

### Code Fixes
Removed all autonomous Jira detection/persistence from 3 files:
- **`flows/_finalization.py`** — `persist_post_completion()` now only handles Confluence; no `jira_completed`, no `append_jira_ticket`, no `save_jira_phase`
- **`_cli_startup.py`** — Removed Jira detection block, ticket persistence, `save_jira_phase()` calls
- **`components/startup.py`** — Same cleanup as `_cli_startup.py`

### Tests Rewritten
- `test_prd_flow.py`: Replaced 3 old tests with 4 new tests verifying Jira is NOT detected/persisted
- `test_main.py`: Replaced `test_sets_jira_phase_subtasks_done_after_jira_completion` with `test_does_not_set_jira_phase_on_autonomous_path`
- `test_main.py`: Replaced `test_jira_output_not_written_to_working_ideas` with `test_no_jira_data_in_delivery_record_on_autonomous_path`
- `test_main.py`: Replaced `test_persists_ticket_type_from_jira_lookup` + `test_falls_back_to_unknown_when_search_fails` with `test_does_not_search_or_persist_jira_tickets`

### Documentation
- CODEX.md: Added "One-Time Data Fix Scripts" pattern (section 6) + v0.15.11 lesson learned to Jira Approval Gate
- Obsidian Coding Standards: Added section 7 (data fix scripts) + v0.15.11 lesson learned
- Obsidian Version History: v0.15.11 entry

### Files Modified
- `src/.../flows/_finalization.py` — Removed Jira detection from `persist_post_completion()`
- `src/.../\_cli_startup.py` — Removed Jira detection, ticket persistence, `save_jira_phase()`
- `src/.../components/startup.py` — Same cleanup
- `tests/flows/test_prd_flow.py` — 4 new approval-gate regression tests
- `tests/test_main.py` — 3 tests rewritten to assert Jira NOT persisted
- `tests/test_version.py` — Updated version assertion
- `src/.../version.py` — v0.15.11
- `CODEX.md` — Data fix pattern, recent changes, lesson learned
- `obsidian/Architecture/Coding Standards.md` — Data fix pattern + lesson learned
- `obsidian/Changelog/Version History.md` — v0.15.11 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 007 — 2026-03-10

**Scope**: Jira Epics & Stories Output Persistence for Crash Resilience
**Version**: v0.15.11 → v0.15.12

### Problem
`jira_epics_stories_output` was only stored in-memory on `flow.state` and never persisted to MongoDB. If the server crashed after Phase 2 (Epics & Stories) but before Phase 3 (Sub-tasks), the Sub-tasks stage would skip because `flow.state.jira_epics_stories_output` was empty after resume. Additionally, `_run_jira_phase()` did not restore `jira_skeleton` or `jira_epics_stories_output` from MongoDB when reconstructing flow state.

### Fix
1. **New MongoDB functions** — `save_jira_epics_stories_output()` / `get_jira_epics_stories_output()` in `_status.py`, matching the skeleton persistence pattern
2. **Persist on creation** — `build_jira_epics_stories_stage._apply()` now calls `save_jira_epics_stories_output()` alongside `_persist_jira_phase()`
3. **Restore on resume** — `_run_jira_phase()` now restores `jira_skeleton` and `jira_epics_stories_output` from the MongoDB document during state reconstruction

### Tests Added (14 new, 2122 total)
- `TestSaveJiraEpicsStoriesOutput` (8 tests) — MongoDB save/get, error handling
- `TestEpicsStoriesStageApplyPersistence` (2 tests) — _apply persists output, survives save failure
- `TestSubtasksStageResume` (2 tests) — subtasks skips without output, does not skip with restored output
- `TestRunJiraPhaseStateReconstruction` (3 tests) — jira_skeleton restored, epics_stories_output restored, missing fields default to empty

### Files Modified
- `src/.../mongodb/working_ideas/_status.py` — Added save/get for jira_epics_stories_output
- `src/.../mongodb/working_ideas/repository.py` — Re-exported new functions
- `src/.../orchestrator/_jira.py` — Persist output in epics_stories _apply()
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — Restore jira_skeleton + jira_epics_stories_output
- `tests/orchestrator/test_jira.py` — 4 new tests
- `tests/mongodb/working_ideas/test_repository.py` — 8 new tests
- `tests/apis/slack/test_product_list.py` — 3 new tests (state reconstruction)
- `src/.../version.py` — v0.15.12

---

## Session 007b — 2026-03-10

**Scope**: Eliminate 'unknown' Jira Ticket Types
**Version**: v0.15.12 → v0.15.13

### Problem
`JiraCreateIssueTool` persisted the raw LLM-provided `issue_type` to MongoDB before the orchestrator could write the correct hardcoded type. Since `append_jira_ticket()` deduplicates by key, the first (wrong) write won — resulting in "unknown", "Task", "Sub-Task", etc. in the database.

### Root Cause
Two code paths write tickets to MongoDB:
1. **JiraCreateIssueTool._run()** — writes during crew execution with whatever `issue_type` the LLM provides (first write wins)
2. **Orchestrator _jira.py** — writes after crew completes with hardcoded correct types, but dedup silently skips since key already exists

### Fix
Added `_normalise_issue_type()` in `_tool.py` that maps all LLM variants to canonical types before persistence:
- `"task"`, `"Task"` → `"Sub-task"`
- `"subtask"`, `"Sub-Task"` → `"Sub-task"`
- `"story"` → `"Story"`, `"epic"` → `"Epic"`
- `""`, `"unknown"`, unrecognised → `"Story"` (or `"Sub-task"` when `parent_key` is set)

### Tests Added (18 new, 2140 total)
- `TestNormaliseIssueType` (14 tests) — all variants and edge cases
- `TestToolNormalisesTypeBeforePersist` (4 tests) — end-to-end tool → MongoDB verification

### Files Modified
- `src/.../tools/jira/_tool.py` — Added `_normalise_issue_type()`, called in `_run()` before API call and persistence
- `tests/tools/test_jira_tool.py` — 18 new tests
- `src/.../version.py` — v0.15.13
- `tests/test_version.py` — Updated version assertion

---

## Session 007c — 2026-03-10

**Scope**: Add Archive Button to Product List
**Version**: v0.15.13 → v0.15.14

### Problem
The product list (completed ideas) had no way for users to archive an idea. Archive was only available in the idea list (in-progress ideas). Users could not remove completed products from future "list products" lookups.

### Fix
Added a `:file_folder: Archive #N` button to every product in the product list Block Kit builder. The button triggers a confirmation prompt (reusing the existing `archive_idea_confirm` / `archive_idea_cancel` flow). On confirmation, the working idea is marked `status="archived"` and excluded from future queries (which filter on `status="completed"`).

Changes:
1. **Block Kit builder** — Added archive button as the last element in every product's action row
2. **Dispatch router** — Added `product_archive_` to `_PRODUCT_PREFIXES` and ack label
3. **Product list handler** — Added `_handle_product_archive()` that looks up the product, posts confirmation blocks with the run_id, and reuses the existing archive confirmation flow

### Tests Added (11 new, 2151 total)
- `TestProductArchiveButton` (6 tests) — button presence, value format, ordering
- `TestProductArchiveAckLabel` (1 test) — dispatch ack label
- `TestProductArchiveHandler` (3 tests) — confirmation posting, error cases
- `TestProductArchiveDispatchRouting` (1 test) — prefix recognition

### Files Modified
- `src/.../apis/slack/blocks/_product_list_blocks.py` — Archive button added
- `src/.../apis/slack/interactions_router/_dispatch.py` — product_archive_ prefix + ack label
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — _handle_product_archive()
- `tests/apis/slack/test_product_list.py` — 11 new tests
- `src/.../version.py` — v0.15.14
- `tests/test_version.py` — Updated version assertion

---

## Session 008 — 2026-03-10

**Scope**: Fix Progress Heartbeat Not Firing During Interactive PRD Flows
**Version**: v0.15.14 → v0.15.15

### Problem
During long-running PRD generation flows initiated via the interactive Slack path, users received no section-by-section progress updates. The heartbeat system (which posts messages like ":writing_hand: Drafting section 3/10: User Personas") was originally implemented but had stopped working for the interactive flow path.

### Root Cause
`run_interactive_slack_flow()` in `_flow_runner.py` never called `make_progress_poster()` to create a progress callback, and never set `flow.progress_callback`. The non-interactive path (`router.py` line 169) and resume path (`_flow_handlers.py` line 1031) both correctly created and wired the progress callback — only the interactive path was broken. Log evidence: `[Callbacks] progress=False` for interactive runs.

### Fix
Added to `_flow_runner.py`:
1. Import `make_progress_poster` from `_flow_handlers`
2. Create `progress_cb = make_progress_poster(channel, thread_ts, user, send_tool, run_id=run_id)`
3. Set `flow.progress_callback = progress_cb`
4. Include `"progress_callback": progress_cb` in the `_cb_kwargs` registry dict

### Tests Added (3 new, 2154 total)
- `test_progress_callback_set_on_flow` — verifies flow.progress_callback is set
- `test_progress_callback_registered_in_registry` — verifies register_callbacks includes progress_callback
- `test_make_progress_poster_called_with_correct_args` — verifies correct channel/thread/user/run_id passed

### Files Modified
- `src/.../apis/slack/interactive_handlers/_flow_runner.py` — Added progress_cb creation + registry wiring
- `tests/apis/slack/test_interactive_exec_completion.py` — 3 new tests
- `src/.../version.py` — v0.15.15
- `tests/test_version.py` — Updated version assertion

---

## Session 009 — 2026-03-10

**Scope**: Optimise PRD Section Generation Performance
**Version**: v0.15.15 → v0.16.0

### Problem
Log analysis of run 67aca7dc0697 showed section generation times growing dramatically:
- Problem Statement: 5 min (3 iterations)
- Non-Functional Requirements: 10 min (3 iterations)
- Edge Cases: 15 min (5 iterations)
- Error Handling: 21 min (3 iterations, draft alone 9 min)

### Root Causes
1. **Context bloat**: `approved_context()` sent full text of ALL prior approved sections to both critique and refine tasks. By section 7, prompts included ~30K+ chars of prior context.
2. **Executive summary double-counted**: Included in both `{executive_summary}` param AND in `{approved_sections}` (since it's the first approved section).
3. **Critic agent had knowledge_sources/embedder**: Unnecessary RAG overhead for a pure evaluation agent.

### Optimizations
1. **Condensed prior-section context for refine tasks** — New `approved_context_condensed()` method on PRDDraft sends only section titles + first 500 chars instead of full text. Applied only to refine tasks (research model = bottleneck). Critique tasks keep full context (flash model, needs duplication checking).
2. **Exclude executive_summary from approved_sections** — Both critique and refine tasks now pass `exclude_keys={"executive_summary", section.key}` since exec summary is already a separate template parameter.
3. **Remove knowledge_sources/embedder from critic** — Pure evaluation agent doesn't need RAG retrieval.

### Tests Added (4 new, 2158 total)
- `test_prd_draft_approved_context_exclude_keys` — multiple exclusion keys
- `test_prd_draft_approved_context_condensed` — truncation behavior
- `test_prd_draft_approved_context_condensed_exclude_keys` — condensed + exclusion
- `test_critic_no_knowledge_sources` — critic agent purity

### Files Modified
- `src/.../apis/prd/_domain.py` — Added `approved_context_condensed()`, updated `approved_context()` with `exclude_keys` param
- `src/.../flows/_section_loop.py` — Use condensed context for refine, exclude exec summary from both
- `src/.../agents/product_manager/agent.py` — Removed knowledge_sources/embedder from critic
- `tests/flows/test_prd_flow.py` — 3 new tests
- `tests/agents/test_product_manager.py` — 1 new test
- `src/.../version.py` — v0.16.0
- `tests/test_version.py` — Updated version assertion

---

## Session 010 — 2026-03-10

**Scope**: Fix Post-Completion Flow Not Prompting User After Resume
**Version**: v0.16.0 → v0.16.1

### Problem
After PRD sections completed via resume, Confluence and Jira tickets were created automatically without prompting the user. The `auto_approve=True` flag (intended only for section auto-acceptance) was causing the entire post-completion delivery to bypass approval gates.

### Root Cause
`handle_resume_prd()` in `_flow_handlers.py` called `resume_prd_flow(auto_approve=True)` without Jira callbacks. `resume_prd_flow()` in `service.py` didn't even accept Jira callback parameters. When `_finalization.py`'s `run_post_completion()` found no `jira_skeleton_approval_callback`, it fell to `_run_auto_post_completion()` which auto-published Confluence without user interaction.

### Fix
1. **service.py**: Added `jira_skeleton_approval_callback` and `jira_review_callback` params to `resume_prd_flow()`, wired to flow instance and callback registry
2. **_flow_handlers.py**: `handle_resume_prd()` now calls `register_interactive_run()`, builds Jira callbacks via factory functions, passes them to `resume_prd_flow()`, and cleans up via `cleanup_interactive_run()` in finally block

### Tests Added (5 new, 2150 total)
- `test_resume_builds_jira_callbacks` — handler builds factory callbacks with correct run_id
- `test_resume_registers_interactive_run` — handler stores channel/thread_ts for Slack callbacks
- `test_resume_jira_callbacks_wired_to_flow` — service wires callbacks to flow instance
- `test_resume_jira_callbacks_registered_in_registry` — service registers callbacks (spy before cleanup)
- `test_resume_without_jira_callbacks_omits_from_registry` — service omits absent callbacks

### Files Modified
- `src/.../apis/prd/service.py` — Added Jira callback params to `resume_prd_flow()`
- `src/.../apis/slack/_flow_handlers.py` — Wired interactive run + Jira callbacks in `handle_resume_prd()`
- `tests/flows/test_jira_approval_gate.py` — 2 new handler-level tests
- `tests/apis/prd/test_prd.py` — 3 new service-level tests
- `src/.../version.py` — v0.16.1

---

## Session 011 — 2026-03-10

**Scope**: Server Crash Resilience & Log-Driven Bug Fixes
**Version**: v0.16.1 → v0.16.2

### Problem
Server crashed during Jira ticket creation ("cannot schedule new futures after shutdown") and repeatedly restarted. Log analysis revealed three issues: (1) no auto-restart mechanism, (2) LLM hallucinated `run_id=RUN-12345` in Jira tickets, (3) `ShutdownError` swallowed in `_finalization.py`.

### Root Causes
1. **No auto-restart**: `start_server.sh` exits on crash with no recovery mechanism.
2. **LLM run_id hallucination**: The `run_id` was passed to the LLM in task description text. The LLM hallucinated "RUN-12345" when calling the Jira tool instead of using the actual value from the description.
3. **ShutdownError swallowed**: `run_post_completion()` in `_finalization.py` caught ALL exceptions including `ShutdownError`, `BillingError`, and `ModelBusyError` in a generic `except Exception` block, preventing the service layer from properly pausing the flow.

### Fixes
1. **start_server_watchdog.sh** (new): Auto-restart wrapper with signal handling (SIGINT/SIGTERM → clean shutdown, no restart), circuit breaker (5 restarts in 120s → stop), logging to `logs/watchdog.log`.
2. **authoritative_run_id on JiraCreateIssueTool**: Added `authoritative_run_id` field set at construction time. When set, it overrides whatever `run_id` the LLM provides — same pattern as `_resolve_confluence_url`. Wired through `create_jira_product_manager_agent(run_id=)` and `create_jira_architect_tech_lead_agent(run_id=)`, called from `_jira.py` stages with `flow.state.run_id`.
3. **Re-raise critical errors**: Added `except (BillingError, ModelBusyError, ShutdownError): raise` before the generic `except Exception` in `run_post_completion()`.
4. **Fixed 7 flaky retry tests**: Pre-existing test pollution from background threads calling `time.sleep()`. Changed `assert_called_once_with` → `assert_any_call` and `assert_not_called` → filtered call list checks.

### Tests Added (12 new, 2175 total)
- `TestAuthoritativeRunId` (5 tests): override LLM run_id, use LLM when empty, authoritative when LLM empty, default empty, construction
- `TestRunPostCompletion` (3 tests): shutdown_error_propagates, billing_error_propagates, model_busy_error_propagates
- `TestJiraAgentRunId` (4 tests): PM/Architect agent pass run_id to tool, default empty

### Files Modified
- `start_server_watchdog.sh` — NEW: auto-restart wrapper
- `src/.../tools/jira/_tool.py` — Added `authoritative_run_id` field + override logic
- `src/.../agents/orchestrator/agent.py` — Added `run_id` param to Jira agent factories
- `src/.../orchestrator/_jira.py` — Pass `flow.state.run_id` to agent factories
- `src/.../flows/_finalization.py` — Re-raise ShutdownError/BillingError/ModelBusyError
- `tests/tools/test_jira_tool.py` — 5 new tests (TestAuthoritativeRunId)
- `tests/flows/test_prd_flow.py` — 3 new tests (error propagation)
- `tests/agents/test_orchestrator.py` — 4 new tests (TestJiraAgentRunId)
- `tests/test_retry.py` — Fixed flaky assertion
- `tests/tools/test_gemini_chat.py` — Fixed 3 flaky assertions
- `tests/tools/test_openai_chat.py` — Fixed 3 flaky assertions
- `src/.../version.py` — v0.16.2

---

## Session 012 — 2026-03-10

**Scope**: CODEX.md Optimization & Obsidian Knowledge Base Restructuring
**Version**: v0.16.2 (no version change — documentation only)

### Work Done
1. **Created `obsidian/Architecture/CrewAI Framework.md`** — Comprehensive page mapping CrewAI core concepts (Agents, Tasks, Crews, Flows, Tools, Knowledge, Memory) to project implementation. Includes concept table, agent definitions, task patterns, crew instances, PRDFlow architecture, custom tools, knowledge files, memory usage, and 6 design principles. Sourced from official docs at docs.crewai.com.
2. **Optimized CODEX.md** — Reduced from ~750 lines to ~210 lines by removing all content duplicated in Obsidian:
   - Removed: Server Lifecycle details, PRD Flow Progress Events, Slack Module Map, MongoDB Module Map, Orchestrator Module Map, Test Module Map, full Coding Standards, full Session Management, Obsidian vault structure listing, Project Conventions, LLM Model Tiers, Environment Variables
   - Removed: Entire "Recent Changes" changelog (~120 lines) — kept only in `Changelog/Version History.md`
   - Kept: Quick Reference table, Obsidian lookup table, "When to load which file" table, PRD Service table, Quick Start, Common Commands, Coding Standards summary, Session Management summary, Patch Target Cheat Sheet
   - Added: Obsidian Knowledge Base section with topic-to-page lookup table and "When to Update Which Page" reference
3. **Updated `obsidian/Home.md`** — Version 0.15.4 → 0.16.2, added `[[CrewAI Framework]]` and `[[Coding Standards]]` links, updated vault structure listing
4. **Updated `obsidian/Testing/Testing Guide.md`** — Test count 2033+ → 2175+

### Key Decisions
- CODEX.md is now a lean lookup guide: quick-reference tables + Obsidian pointers
- All detailed documentation lives exclusively in Obsidian
- Changelog removed from CODEX.md entirely — single source of truth in `Version History.md`
- CrewAI Framework page serves as the bridge between official CrewAI docs and our implementation

### Files Modified
- `CODEX.md` — Rewritten from ~750 to ~210 lines
- `obsidian/Architecture/CrewAI Framework.md` — NEW
- `obsidian/Home.md` — Version + links + vault structure updated
- `obsidian/Testing/Testing Guide.md` — Test count updated
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 005 — 2026-03-13

**Scope**: MongoDB Atlas Migration
**Version**: v0.16.2 → v0.17.0

### Work Done
1. **Refactored `mongodb/client.py`** — Replaced localhost-based URI building (`MONGODB_URI`, `MONGODB_PORT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`) with single `MONGODB_ATLAS_URI` env var. `_build_uri()` now returns the Atlas connection string directly; raises `RuntimeError` if not set.
2. **Updated `mongodb/__init__.py`** — Removed `DEFAULT_HOST` and `DEFAULT_PORT` exports (no longer exist).
3. **Updated `scripts/preflight.py`** — `check_mongodb()` now validates `MONGODB_ATLAS_URI` instead of `MONGODB_URI`.
4. **Updated `.env`** — Removed old `MONGODB_URI`, `MONGODB_PORT`, `MONGODB_USERNAME`, `MONGODB_PASSWORD` vars. `MONGODB_ATLAS_URI` is the sole connection config.
5. **Created `scripts/migrate_to_atlas.py`** — One-time migration script that exports all collections (with indexes) from localhost MongoDB to Atlas. Supports `--dry-run`, `--source` customization, batch insert with duplicate-key resilience.
6. **Rewrote `tests/mongodb/test_client.py`** — 9 new tests covering Atlas URI validation, whitespace stripping, missing/empty URI errors, and `_get_db_name` behaviour.
7. **Updated Obsidian docs** — Environment Variables (Atlas URI), MongoDB Schema (Atlas hosted note).

### Key Decisions
- `MONGODB_ATLAS_URI` is required — no fallback to localhost. This ensures the application cannot accidentally connect to a local database in production.
- Migration script preserves `_id` values for data consistency across environments.
- `MONGODB_DB` still defaults to `ideas` for database name flexibility.

### Files Modified
- `src/crewai_productfeature_planner/mongodb/client.py`
- `src/crewai_productfeature_planner/mongodb/__init__.py`
- `src/crewai_productfeature_planner/scripts/preflight.py`
- `src/crewai_productfeature_planner/version.py`
- `.env`
- `scripts/migrate_to_atlas.py` — NEW
- `tests/mongodb/test_client.py`
- `obsidian/Architecture/Environment Variables.md`
- `obsidian/Database/MongoDB Schema.md`
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 008 — 2026-03-13

**Scope**: Fix Intent Misclassification (idea → create_jira)
**Version**: v0.17.0 → v0.17.1

### Problem
When a user submitted a long idea via Slack that contained phrases like "jira tickets" or "jira epics" in the idea body, the phrase override chain in `_message_handler.py` reclassified the intent from `create_prd` (correctly identified by the LLM) to `create_jira`. This caused the system to skip the entire PRD generation pipeline and jump straight to Jira ticket creation.

### Root Cause
In the phrase override chain (`_message_handler.py` ~line 196), `has_create_jira_phrase` was checked **before** `has_idea_phrase`. Since `_CREATE_JIRA_PHRASES` includes substrings like `"jira tickets"` and `"jira epics"`, long idea text containing those words as part of the description (not as a command) triggered the override, replacing the correct LLM classification.

### Fix
1. Reordered the phrase override chain: `has_idea_phrase` now checked before `has_create_jira_phrase`
2. Added guard: `has_create_jira_phrase and intent != "create_prd"` — when the LLM correctly classifies as `create_prd`, the jira phrase override is suppressed

### Files Modified
- `src/crewai_productfeature_planner/apis/slack/_message_handler.py` — phrase override reorder + LLM trust guard
- `tests/apis/slack/test_create_jira_intent.py` — 3 new regression tests
- `src/crewai_productfeature_planner/version.py` — 0.17.1 codex entry
- `obsidian/Sessions/Session Log.md` — This entry

### Tests
- 605 Slack tests passed (602 existing + 3 new regression tests)
- 25 Jira approval gate tests passed

---

## Session 009 — 2026-03-13

**Scope**: GStack Agent Integration
**Version**: v0.17.1 → v0.18.0

### Summary
Integrated 7 gstack-inspired agent roles into CrewAI. Introduced Phase 1.5 (CEO Reviewer → `executive_product_summary`, Eng Manager → `engineering_plan`). Both artefacts feed Phase 2 section drafting and Jira context. SECTION_ORDER expanded from 10 to 12 sections. 5 stub agents created for future activation.

### Tests
- 12 new tests in `test_ceo_eng_review.py`
- 2162 total tests passing

---

## Session 010 — 2026-03-13

**Scope**: Jira Review & QA Test Sub-tasks
**Version**: v0.18.0 → v0.19.0

### Summary
Extended the 3-phase Jira pipeline to 5 phases. Activated 3 stub agents (Staff Engineer, QA Lead, QA Engineer) with full factories, task YAML configs, and JiraCreateIssueTool.

### Changes
1. **Phase 4: Review Sub-tasks** — Staff Engineer + QA Lead review every user story as sub-tasks. Staff Eng performs structural audit (N+1 queries, race conditions, trust boundaries, missing indexes). QA Lead performs test methodology review (acceptance criteria, coverage gaps, negative tests, regression risk).
2. **Phase 5: QA Test Sub-tasks** — QA Engineer creates `[QA Test]` counter-tickets per implementation sub-task covering edge cases, security (injection, auth bypass, CSRF/SSRF), and rendering (empty/loading/error states, responsive, accessibility).
3. **Jira Phase State Machine** — Extended: `subtasks_done → review_ready → review_done → qa_test_ready → qa_test_done`
4. **Slack Integration** — 6 new phase labels, 5 new button blocks, 4 new approval handlers

### Files Created
- `agents/staff_engineer/agent.py` — Full factory with `create_staff_engineer()`
- `agents/staff_engineer/config/tasks.yaml` — Structural audit task template
- `agents/qa_lead/agent.py` — Full factory with `create_qa_lead()`
- `agents/qa_lead/config/tasks.yaml` — Test methodology review task template
- `agents/qa_engineer/agent.py` — Full factory with `create_qa_engineer()`
- `agents/qa_engineer/config/tasks.yaml` — Edge case/security test task template

### Files Modified
- `orchestrator/_jira.py` — Phase 4 + 5 stage builders, updated auto-approve chain
- `flows/_constants.py` — `jira_review_output`, `jira_qa_test_output` fields
- `flows/_finalization.py` — Phase 4 + 5 execution blocks
- `apis/slack/blocks/_product_list_blocks.py` — Phase labels + buttons
- `apis/slack/interactions_router/_product_list_handler.py` — Reviews/QA tests branches
- `apis/slack/interactions_router/_jira_approval_handler.py` — 4 new handlers, dispatch
- `orchestrator/stages.py`, `orchestrator/__init__.py` — Re-exports

### Tests
- 2162 tests passing (3 tests updated for new 5-phase behavior)

---

## Session 009 — 2026-03-13

**Scope**: GStack Agent Integration (CEO Reviewer + Eng Manager + Phase 1.5)
**Version**: v0.17.1 → v0.18.0

### Summary
Integrated 7 gstack-inspired agent roles into the CrewAI project and added a new Phase 1.5 to the PRD flow. After the executive summary is approved, the CEO Reviewer agent generates an `executive_product_summary` (10-star product vision), and the Eng Manager agent produces an `engineering_plan` (technical architecture). Both artefacts feed into Phase 2 section drafting and Jira ticket creation.

### New Agent Directories
- `agents/ceo_reviewer/` — Full agent (YAML + factory + tasks)
- `agents/eng_manager/` — Full agent (YAML + factory + tasks)
- `agents/staff_engineer/` — Stub
- `agents/release_engineer/` — Stub
- `agents/qa_engineer/` — Stub
- `agents/qa_lead/` — Stub
- `agents/retro_manager/` — Stub

### New Files
- `flows/_ceo_eng_review.py` — `run_ceo_review()` and `run_eng_plan()` for Phase 1.5
- `tests/flows/test_ceo_eng_review.py` — 12 tests covering both functions

### Files Modified
- `apis/prd/_sections.py` — SECTION_ORDER expanded (10→12), added SPECIALIST_SECTION_KEYS
- `flows/_constants.py` — PRDState fields: `executive_product_summary`, `engineering_plan`
- `flows/prd_flow.py` — Phase 1.5a/1.5b insertion, parallel drafting context
- `flows/_agents.py` — `run_agents_parallel()` signature + format calls
- `flows/_section_loop.py` — critique/refine template vars, _excl set
- `agents/product_manager/config/tasks.yaml` — section tasks use new template vars
- `orchestrator/_jira.py` — `_build_jira_context()` helper, engineering plan injection
- `components/resume.py` — specialist section restoration
- `apis/prd/service.py` — specialist fields in resume_prd_flow
- `tests/flows/test_prd_flow.py` — 57 format string replacements, section index fixes, CEO/Eng mocks
- `tests/apis/prd/test_prd.py` — sections_total 10→12, next_section assertions
- `version.py` — 0.18.0 codex entry

### Tests
- 2162 total tests passing (12 new in test_ceo_eng_review.py)

---

## Session 011 — 2026-03-13

**Scope**: UX Designer Agent & Figma Make Integration (Phase 1.5c)
**Version**: v0.19.0 → v0.20.0

### Summary
Created a UX Designer agent that runs after the Executive Product Summary (Phase 1.5c). The agent converts the summary into a structured Figma Make prompt and submits it to the Figma Make API to generate clickable prototypes. When Figma credentials are unavailable, the generated prompt is stored for manual use. The Figma design URL and status are persisted to MongoDB and shown in the Slack product list with status indicators and action buttons. Both the UX design and engineering plan now feed into all Jira ticket generation stages.

### New Files
- `tools/figma/__init__.py` — Package exports (FigmaMakeTool)
- `tools/figma/_config.py` — Env helpers: FIGMA_ACCESS_TOKEN, FIGMA_TEAM_ID, has_figma_credentials()
- `tools/figma/_client.py` — HTTP client: submit_figma_make(), poll_figma_make(), FigmaMakeError
- `tools/figma/figma_make_tool.py` — CrewAI BaseTool wrapper with FIGMA_URL/SKIPPED/ERROR output
- `agents/ux_designer/__init__.py` — Package exports
- `agents/ux_designer/agent.py` — Factory with _build_llm() (research tier), create_ux_designer()
- `agents/ux_designer/config/agent.yaml` — Senior UX Designer role/goal/backstory
- `agents/ux_designer/config/tasks.yaml` — 6-step Figma Make prompt generation task
- `flows/_ux_design.py` — run_ux_design() with output parsing and MongoDB persistence
- `tests/tools/test_figma_tool.py` — 29 tests for Figma config, client, and tool
- `tests/flows/test_ux_design.py` — 10 tests for UX design flow

### Files Modified
- `flows/_constants.py` — 3 new PRDState fields: figma_design_url, figma_design_prompt, figma_design_status
- `flows/prd_flow.py` — Phase 1.5c insertion after Eng Plan (1.5b)
- `mongodb/working_ideas/_status.py` — save_figma_design() function
- `mongodb/working_ideas/repository.py` — Re-export save_figma_design
- `mongodb/working_ideas/_queries.py` — figma fields in _doc_to_product_dict()
- `apis/slack/blocks/_product_list_blocks.py` — Figma status indicators + buttons
- `apis/slack/interactions_router/_product_list_handler.py` — _handle_ux_design() + figma field restoration in _run_jira_phase()
- `apis/slack/interactions_router/_dispatch.py` — product_ux_design_ ack label
- `orchestrator/_jira.py` — _build_jira_context() includes UX design blocks
- `tests/flows/test_ceo_eng_review.py` — 5 new Jira context UX tests
- `tests/apis/slack/test_product_list.py` — 11 new Figma block, handler, and state tests
- `version.py` — 0.20.0 codex entry

### New Environment Variables
- `FIGMA_ACCESS_TOKEN` — Figma API personal access token
- `FIGMA_TEAM_ID` — Figma team ID for design file creation
- `GEMINI_UX_DESIGNER_MODEL` — Optional LLM model override for UX Designer

### Tests
- 2217 total tests passing (55 new)

---

## Session 017 — 2026-03-15

**Scope**: Resume Gate Bypass Fix
**Version**: v0.20.0 → v0.20.1

### Problem
Resumed PRD flows got stuck at two approval gates:
1. **Requirements approval gate** — `_requires_approval()` only checked `any(s.content for s in draft.sections)`, which returned False when specialist sections (CEO, Eng, UX) had content but regular sections hadn't started yet.
2. **"Proceed to sections?" gate** — always fired on resume even when all specialist agents had already run, causing a 10-minute timeout before continuing.

Combined, these two gates consumed 20 minutes of timeout on every resume, often causing the server to restart before Phase 2 could begin.

### Root Cause
- `_requires_approval()` in `_requirements.py` didn't account for specialist agent state (`executive_product_summary`, `engineering_plan`, `figma_design_status`)
- The user decision gate in `prd_flow.py` had no skip logic for resumed runs where specialists already completed

### Work Done
- **`orchestrator/_requirements.py`**: Added specialist state checks to `_requires_approval()` — auto-approves when `executive_product_summary`, `engineering_plan`, or `figma_design_status` are set
- **`flows/prd_flow.py`**: Added `specialists_all_skipped` flag tracking whether all three specialist steps were skipped (resume case). User decision gate now bypassed when `specialists_all_skipped` or `has_section_content` is true
- **`tests/flows/test_prd_flow.py`**: Fixed `test_callback_false_raises_completed` — added `_has_gemini_credentials` mock and `monkeypatch.delenv` for Gemini API keys so specialist agents don't hit live API. Removed pre-populated specialist state from `test_requirements_approval_callback_continue_proceeds` to match new gate behavior
- **`version.py`**: v0.20.1 codex entry

### Files Modified
- `src/crewai_productfeature_planner/orchestrator/_requirements.py`
- `src/crewai_productfeature_planner/flows/prd_flow.py`
- `tests/flows/test_prd_flow.py`
- `src/crewai_productfeature_planner/version.py`

### Tests
- All existing tests passing (163 flow + 162 orchestrator + 81 API + 277 agent tests verified)

---

## Session 018 — 2026-03-16

**Scope**: Retry UX Design dispatch fix + test performance
**Version**: v0.20.1 → v0.20.2

### Problem 1 — Retry UX Design button click ignored
The "Retry UX Design" button in the Slack product list did nothing when clicked. The button was correctly rendered with `action_id=product_ux_design_<N>`, and the handler `_handle_ux_design()` was fully implemented, but the dispatcher's `_PRODUCT_PREFIXES` tuple was missing `"product_ux_design_"` — so the click was silently dropped.

### Problem 2 — Test suite taking 199s (6 tests at 25-28s each)
Six end-to-end `generate_sections()` tests in `test_prd_flow.py` were calling the live Gemini API via the unmocked `_run_ux_design()` method. Each test waited ~25s for the real UX Designer agent to generate a Figma Make prompt.

### Work Done
- **`_dispatch.py`**: Added `"product_ux_design_"` to `_PRODUCT_PREFIXES`
- **`test_product_list.py`**: Added `test_ux_design_prefix_in_product_prefixes` regression test
- **`test_prd_flow.py`**: Added `_run_ux_design` mock to 3 tests and `figma_design_status = "prompt_ready"` to 3 tests

### Files Modified
- `src/crewai_productfeature_planner/apis/slack/interactions_router/_dispatch.py`
- `tests/apis/slack/test_product_list.py`
- `tests/flows/test_prd_flow.py`
- `src/crewai_productfeature_planner/version.py`

### Tests
- 2205 passed, full suite: 199s → 32s (84% faster)

---

## Session 019 — 2026-03-16

**Scope**: Figma Make — Playwright browser automation
**Version**: v0.20.2 → v0.21.0

### Problem
The `_client.py` used `POST /v1/ai/make` against the Figma REST API, but this endpoint **does not exist** — confirmed by fetching the Figma OpenAPI spec. The `/v1/ai/make` endpoint was fabricated by the LLM that originally wrote the tool.

### Solution
Replaced the urllib-based HTTP client with **Playwright headless Chromium** automation that drives the Figma Make web UI at `figma.com/make/new`.

### Work Done
- **`_config.py`**: Complete rewrite — removed `FIGMA_API_BASE`, `DEFAULT_POLL_INTERVAL`, `DEFAULT_POLL_TIMEOUT`, `get_figma_access_token()`, `get_figma_team_id()`. Added `FIGMA_MAKE_URL`, `DEFAULT_MAKE_TIMEOUT`, `DEFAULT_SESSION_DIR`, `get_figma_session_dir()`, `get_figma_session_path()`, `get_figma_make_timeout()`, `get_figma_headless()`. Updated `has_figma_credentials()` to check for Playwright session state file.
- **`_client.py`**: Complete rewrite — removed `_request()`, `submit_figma_make()`, `poll_figma_make()`. Added `run_figma_make(prompt)` using Playwright: launch Chromium → load session state → navigate to `/make/new` → detect login redirect → find chat input → fill prompt → press Enter/click Send → wait for URL change → wait for networkidle → return file URL. Helper functions: `_find_chat_input()`, `_send_prompt()`, `_wait_for_generation()`.
- **`figma_make_tool.py`**: Updated imports from `submit_figma_make`/`poll_figma_make` to `run_figma_make`. Simplified `_run()` to single function call. Updated skip message.
- **`__init__.py`**: Updated docstring for Playwright approach and new env vars.
- **`login.py`**: New interactive login script — opens visible Chromium for manual Figma login, saves Playwright `storage_state()` to session dir.
- **`_product_list_handler.py`**: Updated "FIGMA_ACCESS_TOKEN" message to login script instructions.
- **`pyproject.toml`**: Added `playwright>=1.40` dependency.
- **`test_figma_tool.py`**: Complete rewrite — 32 tests covering config, client helpers, `run_figma_make`, and `FigmaMakeTool` with Playwright mocks.

### Env Var Changes
| Removed | Added |
|---------|-------|
| `FIGMA_ACCESS_TOKEN` | `FIGMA_SESSION_DIR` (default `~/.figma_session`) |
| `FIGMA_TEAM_ID` | `FIGMA_MAKE_TIMEOUT` (default 300) |
| `FIGMA_API_BASE` | `FIGMA_HEADLESS` (default `"true"`) |

### Auth Approach
Playwright `storage_state()` JSON file saved from one-time interactive login session via `login.py`. Reused automatically for headless automation.

### Files Modified
- `src/.../tools/figma/_config.py` (rewritten)
- `src/.../tools/figma/_client.py` (rewritten)
- `src/.../tools/figma/figma_make_tool.py` (updated)
- `src/.../tools/figma/__init__.py` (updated)
- `src/.../tools/figma/login.py` (new)
- `src/.../apis/slack/interactions_router/_product_list_handler.py` (updated)
- `pyproject.toml` (updated)
- `tests/tools/test_figma_tool.py` (rewritten)
- `src/.../version.py` (bumped to 0.21.0)

### Tests
- 2221 passed in 37s (net +16 from test rewrite)

---

## Session 019 — 2026-03-16

**Scope**: Figma Project Config + OAuth + REST API
**Version**: v0.21.1 → v0.22.0

### Work Done
- Added 5 Figma fields to `projectConfig` MongoDB schema: `figma_api_key`, `figma_team_id`, `figma_oauth_token`, `figma_oauth_refresh_token`, `figma_oauth_expires_at`
- Created `_api.py` — Figma REST API client (`get_team_projects`, `get_project_files`, `get_file_info`, `refresh_oauth_token`, `exchange_oauth_code`)
- Updated `_config.py` — project-level credential resolution chain (API key → OAuth token → Playwright session). New: `get_figma_credentials()`, `has_figma_credentials(project_config)`, `_oauth_expired()`, `get_figma_client_id()`, `get_figma_client_secret()`, `FIGMA_OAUTH_URL`, `OAUTH_REDIRECT_URI`
- Updated `_client.py` — OAuth token cookie injection via `_build_context()`. `run_figma_make()` now accepts `project_config` kwarg.
- Rewritten `login.py` — dual mode: `--oauth` flag for OAuth2 flow (local HTTP server + Playwright consent), default session login unchanged
- Setup wizard expanded from 2 to 4 steps: added `figma_api_key` and `figma_team_id`
- Wired `project_config` through agent → tool pipeline: `_ux_design.py` → `create_ux_designer(project_config=...)` → `FigmaMakeTool._project_config`
- Expanded tests from 32 to 64 for Figma module, updated setup wizard tests

### New Env Vars
| Variable | Purpose |
|----------|---------|
| `FIGMA_CLIENT_ID` | OAuth2 app client ID |
| `FIGMA_CLIENT_SECRET` | OAuth2 app client secret |

### Files Modified
- `src/.../mongodb/project_config/repository.py` (schema + create_project)
- `src/.../tools/figma/_api.py` (new)
- `src/.../tools/figma/_config.py` (rewritten)
- `src/.../tools/figma/_client.py` (rewritten)
- `src/.../tools/figma/login.py` (rewritten)
- `src/.../tools/figma/figma_make_tool.py` (updated)
- `src/.../tools/figma/__init__.py` (updated)
- `src/.../apis/slack/session_manager.py` (4 setup steps)
- `src/.../apis/slack/blocks/_session_blocks.py` (Figma step labels + summary)
- `src/.../apis/slack/_session_project.py` (persist Figma keys)
- `src/.../agents/ux_designer/agent.py` (project_config injection)
- `src/.../flows/_ux_design.py` (load project config)
- `tests/tools/test_figma_tool.py` (expanded)
- `tests/apis/slack/test_interaction_tracking.py` (updated for 4 steps)
- `src/.../version.py` (bumped to 0.22.0)

### Tests
- 2253 passed in 38s (net +32 from new Figma tests)

---

## Session 020 — 2026-03-16

**Scope**: Project Config Reconfiguration Wizard + Config Button
**Version**: v0.22.0 → v0.22.1

### Work Done
- Expanded `_UPDATE_CONFIG_PHRASES` from 12 to 21 phrases — added "project config", "project configuration", "configure project", "edit config", "edit project config", "change config", "reconfigure", "reconfigure project", "update project config", "project settings", "edit settings"
- Rewrote `handle_update_config()` from inline field updater to full 5-step setup wizard launcher with pre-populated current values
- Expanded `_SETUP_STEPS` from 4 to 5: added `project_name` as first step
- New `_NEW_PROJECT_START_STEP = "confluence_space_key"` — new project creation skips project_name step
- New `mark_pending_reconfig()` in `session_manager.py` — starts wizard at step 0 (project_name) with existing config pre-populated
- Added `current_value` parameter to `project_setup_step_blocks()` — shows "Current value: `X`" hint during reconfiguration
- Added `:gear: Config` button to product list header (action_id `product_config`, block_id `product_project_actions_{project_id}`)
- Added `product_config` action routing in `_dispatch.py` → `_handle_product_config()` in `_product_list_handler.py`
- `handle_project_setup_reply()` now handles `project_name` step; skip preserves existing name

### Files Modified
- `src/.../apis/slack/_intent_phrases.py` — 9 new config phrases
- `src/.../apis/slack/session_manager.py` — 5-step tuple, `_NEW_PROJECT_START_STEP`, `mark_pending_reconfig()`
- `src/.../apis/slack/blocks/_session_blocks.py` — `project_name` label, `current_value` param
- `src/.../apis/slack/_session_project.py` — project_name handling, skip preservation, name persistence
- `src/.../apis/slack/_session_memory.py` — `handle_update_config()` rewritten as wizard launcher
- `src/.../apis/slack/blocks/_product_list_blocks.py` — Config button at project level
- `src/.../apis/slack/interactions_router/_dispatch.py` — `product_config` action routing
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — `_handle_product_config()`
- `tests/apis/slack/test_interaction_tracking.py` — 4 new reconfig tests, assertion fix
- `tests/apis/slack/test_product_list.py` — `_product_action_blocks()` helper, Config button test
- `tests/apis/slack/test_configure_memory_intent.py` — phrase override + fallback tests
- `src/.../version.py` — bumped to 0.22.1

### Tests
- 2260 passed in 41s (net +7 new tests)

---

## Session 021 — 2026-03-16

**Scope**: LLM Token Optimisation + Manual UX Design
**Version**: v0.22.1 → v0.22.2

### Work Done

#### LLM Token Reduction
- **Critique task**: Switched from `approved_context()` (full verbatim text of all approved sections) to `approved_context_condensed(char_limit=300)` — saves ~5,000–30,000 chars/call on later sections
- **EPS/Eng Plan in critique**: New `condensed_text()` helper in `_domain.py` truncates to 1500 chars for critique calls (critic evaluates quality, doesn't write content — full text unnecessary)
- **Refine expected_output**: Removed unused `critique_section_content` kwarg from `.format()` call — YAML template only uses `{section_title}`
- **Estimated savings**: ~50-70% token reduction per critique call on later sections; ~20-30% overall LLM cost reduction across full PRD generation

#### Manual UX Design
- Added `:page_facing_up: Manual UX Design` button alongside existing UX design button in product list
- Button appears whenever API UX design button appears (start or retry state)
- New `_handle_manual_ux_design()` handler loads EPS + ux_design section from MongoDB, builds formatted markdown, uploads as Slack file snippet
- Fallback to plain text if file upload fails

### Files Modified
- `src/.../apis/prd/_domain.py` — Added `condensed_text()` helper
- `src/.../flows/_section_loop.py` — Critique uses condensed context, condensed EPS/eng plan; refine drops unused kwarg
- `src/.../apis/slack/blocks/_product_list_blocks.py` — Manual UX Design button
- `src/.../apis/slack/interactions_router/_dispatch.py` — `product_manual_ux_` prefix + ack label
- `src/.../apis/slack/interactions_router/_product_list_handler.py` — `_handle_manual_ux_design()`
- `src/.../agents/product_manager/config/tasks.yaml` — No changes (templates already clean)
- `tests/flows/test_prd_flow.py` — 5 `condensed_text` tests; 21 test task_configs updated (removed `{critique_section_content}` from expected_output)
- `tests/apis/slack/test_product_list.py` — Manual UX button tests, dispatch tests, handler tests
- `src/.../version.py` — bumped to 0.22.2

### Tests
- 2271 passed in 37s (net +11 new tests)

---

## Session 014 — 2026-03-16

**Scope**: Fix UX Design task generating no user-visible output
**Version**: v0.22.2 → v0.22.3

### Root Cause
Two issues caused the UX Design Phase 1.5c to produce no value:

1. **Agent didn't always output the prompt** — Task YAML only instructed agent to output `FIGMA_PROMPT:` when tool returned `FIGMA_SKIPPED`. When Figma API returned HTTP 404 (`FIGMA_ERROR`), the agent relayed only the 74-char error with zero design content (22:02 run on 2026-03-15). Status → `skipped`, nothing useful stored.
2. **Even when prompt was generated, it was never delivered** — The first run (15:31) DID generate a 5096-char prompt stored as `prompt_ready`, but: SECTION_ORDER doesn't include `ux_design` → `assemble()` never includes it; Slack message just said "Figma prompt generated" without sharing content; no standalone file written; buried in MongoDB.

### Fixes Applied
1. **Task YAML** (`agents/ux_designer/config/tasks.yaml`) — Agent now MUST ALWAYS output `FIGMA_PROMPT:` with full design spec regardless of tool success/error/skip. The prompt is described as valuable UX spec included in the PRD.
2. **Error recovery** (`flows/_ux_design.py`) — When `FIGMA_ERROR` is present but no `FIGMA_PROMPT`, strips error markers and stores remainder as prompt if >100 chars of design content exists. Previously marked as `skipped` and discarded everything.
3. **PRD appendix** (`flows/_finalization.py`) — `finalize()` appends "Appendix: UX Design" section to assembled PRD with Figma URL (if any) and full prompt. `save_progress()` also includes it in draft files.
4. **Standalone file** (`flows/_ux_design.py`) — New `_save_ux_design_file()` writes `ux_design_*.md` alongside PRDs in `output/prds/YYYY/MM/` when prompt is generated.
5. **Slack notification** (`apis/slack/_flow_handlers.py`) — `ux_design_complete` handler now includes prompt preview (300 chars) and tells user the spec is in the PRD appendix and saved as standalone file. Progress event payload now includes `prompt_preview`.

### Files Modified
- `src/.../agents/ux_designer/config/tasks.yaml` — Mandatory FIGMA_PROMPT output
- `src/.../flows/_ux_design.py` — Error recovery, standalone file write, prompt_preview in event
- `src/.../flows/_finalization.py` — UX Design appendix in finalize() and save_progress()
- `src/.../apis/slack/_flow_handlers.py` — Richer ux_design_complete notification
- `tests/flows/test_ux_design.py` — Updated assertions for new payload, added error recovery test
- `src/.../version.py` — Bumped to 0.22.3

### Tests
- 2272 passed (net +1 new test: `test_error_with_long_content_recovers_prompt`)

---

## Session 015 — SSO "Idea Foundry" Application Whitelisting
**Date**: 2026-03-16 | **Version**: 0.22.3 → 0.23.0

### Goal
Register "Idea Foundry" as the application name in the SSO platform and update the PRD planner to validate tokens were issued for this application. Both sides must acknowledge the whitelisted application.

### Changes

#### SSO side (`c9s_singlesignon`)
1. **`applications_repo.py`** — Added `find_app_by_name()` for case-insensitive app lookup by name.
2. **`bootstrap.py`** — Seeds "Idea Foundry" as a registered OAuth application on startup with redirect URIs and OpenID scopes. Client ID/secret generated automatically and logged once.
3. **`version.py`** — Bumped to 0.1.1.

#### PRD Planner side (`crewai_productfeature_planner`)
1. **`sso_auth.py`** — Full rewrite:
   - RS256 JWT validation (was HS256) via `SSO_JWT_PUBLIC_KEY_PATH` or remote `/sso/oauth/introspect`.
   - `APP_NAME = "Idea Foundry"` constant; `app_id` claim enforcement when `SSO_EXPECTED_APP_ID` is set.
   - Webhook signature header changed to `X-Webhook-Signature` (was `X-SSO-Signature`) to match SSO service.
   - Returns enriched user dict with `app_id`, `app_name`, `enterprise_id`, `organization_id`.
2. **`sso_webhooks.py`** — Updated to handle all 6 SSO event types: `user.created`, `user.updated`, `user.deleted`, `login.success`, `login.failed`, `token.revoked`. Uses dispatch table pattern.
3. **`apis/__init__.py`** — FastAPI app title set to "Idea Foundry — CrewAI Product Feature Planner API". SSO webhook tag description updated.
4. **`.env.example`** — Full SSO configuration block: `SSO_ENABLED`, `SSO_BASE_URL`, `SSO_JWT_PUBLIC_KEY_PATH`, `SSO_ISSUER`, `SSO_EXPECTED_APP_ID`, `SSO_WEBHOOK_SECRET`.
5. **`version.py`** — Bumped to 0.23.0.
6. **`obsidian/Architecture/Environment Variables.md`** — Added SSO section.

### Tests
- 2272 passed (no regressions)

---

## Session 016 — CRUD APIs for Projects & Ideas
**Date**: 2026-03-16 | **Version**: 0.23.1 → 0.24.0

### Goal
Create REST CRUD and paginated list APIs for Projects and Ideas.

### Changes

1. **`apis/projects/router.py`** (new) — Full CRUD: `GET /projects` (paginated 10/25/50), `GET /projects/{id}`, `POST /projects`, `PATCH /projects/{id}`, `DELETE /projects/{id}`. SSO-protected. Pydantic request/response models.
2. **`apis/projects/__init__.py`** (new) — Package init with router re-export.
3. **`apis/ideas/router.py`** (new) — `GET /ideas` (paginated 10/25/50, filter by `project_id` & `status`), `GET /ideas/{run_id}`, `PATCH /ideas/{run_id}/status` (archive/pause). SSO-protected.
4. **`apis/ideas/__init__.py`** (new) — Package init with router re-export.
5. **`apis/__init__.py`** — Wired projects_router and ideas_router. Added OpenAPI tags.
6. **`version.py`** — Bumped to 0.24.0.
7. **`obsidian/APIs/API Overview.md`** — Added Projects and Ideas endpoint tables.
8. **`obsidian/Architecture/Module Map.md`** — Added projects/ and ideas/ entries.

### Tests
- 35 new tests (`tests/apis/projects/test_router.py`, `tests/apis/ideas/test_router.py`)
- 2307 total passed (no regressions)

---

## Session 017 — User Provisioning & user_id on All APIs
**Date**: 2026-03-17 | **Version**: 0.24.0 → 0.25.0

### Goal
Add user_id to all API endpoints for logged-in users. Auto-create user accounts from Slack profile when no existing account is found, leaving password empty for first web login.

### Changes

1. **mongodb/users/__init__.py** (new) — users MongoDB collection repository with CRUD operations.
2. **apis/user_provisioning.py** (new) — ensure_user_from_sso() and ensure_user_from_slack() for auto-provisioning.
3. **apis/sso_auth.py** — require_sso_user now calls ensure_user_from_sso(); returns DB user_id.
4. **apis/ideas/router.py** — All endpoints receive user dependency parameter.
5. **apis/projects/router.py** — All endpoints receive user dependency parameter.
6. **apis/prd/router.py** — All endpoints receive user dependency parameter.
7. **apis/prd/_route_actions.py** — All action endpoints receive user dependency.
8. **apis/publishing/router.py** — All endpoints receive user dependency parameter.
9. **apis/slack/_event_handlers.py** — app_mention and thread_message call ensure_user_from_slack().
10. **apis/slack/interactions_router/_dispatch.py** — Interactive handler calls ensure_user_from_slack().
11. **scripts/setup_mongodb.py** — Registered users collection with indexes.
12. **mongodb/__init__.py** — Re-exports all users repository symbols.
13. **tests/conftest.py** — Added users repo to mock DB patch targets.
14. **tests/apis/slack/conftest.py** (new) — Patches ensure_user_from_slack for Slack tests.
15. **tests/test_setup_mongodb.py** — Added users to expected collections set.
16. **version.py** — Bumped to 0.25.0.

### Tests
- 2307 passed (no regressions)

---

## Session 018 — Revert Local User Storage (SSO-Only Auth)
**Date**: 2026-03-17 | **Version**: 0.25.0 (corrected)

### Goal
User information must NOT be stored in the "ideas" database. All login/registration is handled by the external SSO portal. Users are redirected back to Idea Foundry after successful SSO auth. Reverted Session 017's local user provisioning system.

### Changes

1. **mongodb/users/__init__.py** (deleted) — Removed local users collection repository.
2. **apis/user_provisioning.py** (deleted) — Removed auto-provisioning module.
3. **tests/apis/slack/conftest.py** (deleted) — Removed provisioning mock fixture.
4. **apis/sso_auth.py** — Reverted to use SSO JWT `sub` claim directly as `user_id`. No local DB calls.
5. **apis/slack/_event_handlers.py** — Removed `ensure_user_from_slack` imports and calls from `_handle_app_mention` and `_handle_thread_message`.
6. **apis/slack/interactions_router/_dispatch.py** — Removed user provisioning block from interactive handler.
7. **mongodb/__init__.py** — Removed users imports, `USERS_COLLECTION`, and 8 user symbols from `__all__`.
8. **scripts/setup_mongodb.py** — Removed `USERS_COLLECTION` import and index definitions.
9. **tests/conftest.py** — Removed `_users_repo` import and patch target.
10. **tests/test_setup_mongodb.py** — Removed `"users"` from expected collections set.
11. **version.py** — Updated 0.25.0 codex entry to reflect SSO-only approach.
12. **obsidian/Database/MongoDB Schema.md** — Removed `users` collection (back to 8 collections).
13. **obsidian/Architecture/Module Map.md** — Removed `user_provisioning.py` entry.

### Architecture Clarification
- The "ideas" MongoDB database stores only application data (ideas, projects, sessions, jobs, etc.)
- User accounts, authentication, passwords, and registration belong exclusively to the SSO service
- API endpoints keep `user: dict = Depends(require_sso_user)` — identity comes from SSO JWT claims
- Slack users are identified by their Slack user ID (already tracked in `userSession` and `agentInteraction`)

### Tests
- 2303 passed (4 deselected: pre-existing `test_billing_error_not_retried` retry test issue)

---

## Session 019 — Logging Standard & Incident-Trace Instrumentation
**Date**: 2026-03-17 | **Version**: 0.25.0 → 0.26.0

### Goal
Establish a mandatory logging standard in the CODEX and implement it across all codebase modules, ensuring every business-logic file uses `get_logger(__name__)` and logs with trace identifiers for incident investigation.

### Changes

**Standards & Documentation:**
1. **CODEX.md** — Added § Logging Standard (Required): must use `get_logger`, log at boundaries, include trace context, use proper levels, `exc_info=True` on errors, no sensitive data.
2. **obsidian/Architecture/Coding Standards.md** — Added § 8 Logging Standard with 6 sub-sections: import pattern, what to log (table), trace context, error logging, security, exempt modules.

**Logger Import Standardization (41 files):**
3. Bulk-converted all `import logging` + `logging.getLogger(__name__)` to `from ...scripts.logging_config import get_logger` / `get_logger(__name__)` across: APIs (sso_auth, sso_webhooks, health, slack/*, publishing/*, ideas, projects), tools (slack_tools, slack_token_manager, openai_chat, gemini_chat), components (document), and all Slack interactive/session/interaction handlers.
4. Removed stale `import logging` from `apis/slack/router.py`.

**Incident-Trace Logging Added:**
5. **apis/health/router.py** — Added logger + trace logging to slack_token_status (team_id), slack_token_exchange (team_id + error), slack_token_refresh (team_id + success/fail).
6. **apis/projects/router.py** — Added logging to all 5 CRUD endpoints: get (project_id), create (name + project_id), update (project_id + fields), delete (project_id), with user_id on all.
7. **apis/ideas/router.py** — Added logging to get_idea (run_id) and update_idea_status (run_id + new_status + user_id).
8. **apis/sso_auth.py** — Added logging at auth boundary: bypass path, missing Bearer token, invalid/expired token, successful authentication (user_id + path).
9. **apis/publishing/service.py** — Added logging to list_pending_prds (count), publish_and_create_tickets (run_id), publish_all_and_create_tickets, get_delivery_status (run_id + not-found).
10. **tools/slack_tools.py** — Added channel/team_id/run_id to: token retrieval warning, token error refresh, send failure, read failure, post PRD result failure, file upload, interpret message entry/exit with intent.
11. **tools/openai_chat.py** — Added entry log (msg_len), exit log (intent + model), prefix all warnings/errors with `[OpenAI]`.
12. **tools/gemini_chat.py** — Added entry log (msg_len), exit log (intent + model), prefix all warnings/errors with `[Gemini]`.
13. **components/document.py** — Added debug log to assemble_prd_from_doc (run_id).

### Tests
- 2303 passed (4 deselected: pre-existing retry test)

---

## Session 020 — SERVER_ENV Three-Tier Public URL Resolution
**Date**: 2026-03-17 | **Version**: 0.26.0 → 0.27.0

### Goal
Wire `SERVER_ENV` (DEV/UAT/PROD) to control public URL resolution. Previously `.env` documented these variables but no Python code read them.

### Changes

**New Functions in `scripts/ngrok_tunnel.py`:**
1. `get_server_env()` — reads and validates `SERVER_ENV` (default DEV).
2. `is_dev()` — returns True when SERVER_ENV=DEV.
3. `get_public_url(port)` — DEV→start_tunnel, UAT→`https://{DOMAIN_NAME_UAT}`, PROD→`https://{DOMAIN_NAME_PROD}`. Auto-prepends https:// if scheme missing.

**main.py `start_api()` Rewired:**
4. Imports and uses `get_server_env`, `is_dev`, `get_public_url`, `start_tunnel`.
5. `--ngrok` flag kept as override. Logs SERVER_ENV on startup. Calls `update_slack_app_urls` for all environments.

**start_server.sh Rewired:**
6. Reads `ENV="${SERVER_ENV:-DEV}"`, only kills ngrok in DEV mode. Single command — no `--ngrok` flag needed.

**Documentation:**
7. `.env.example` — added SERVER_ENV, DOMAIN_NAME_UAT, DOMAIN_NAME_PROD with docs.
8. `slack_config.py` — docstring updated with SERVER_ENV info.
9. `obsidian/Architecture/Environment Variables.md` — added 3 new vars.
10. `obsidian/Changelog/Version History.md` — added v0.27.0.

### Tests
- 11 new tests in `test_ngrok_tunnel.py`: get_server_env (default, reads env, rejects invalid), is_dev (DEV/UAT/PROD), get_public_url (DEV tunnel, UAT domain, PROD domain, missing domain errors, https prepend, existing scheme).
- 2320 passed

---

## Session 021 — MongoDB Database Name Cleanup
**Date**: 2026-03-18 | **Version**: 0.27.0 → 0.27.1

### Goal
Make the MongoDB database name fully environment-driven and remove stale legacy vars.

### Changes
1. **migrate_to_atlas.py** — replaced inline `"ideas"` fallback with import of `DEFAULT_DB_NAME` from `client.py`.
2. **.env.example** — replaced stale MongoDB section (MONGODB_URI, MONGODB_PORT, MONGODB_USERNAME, MONGODB_PASSWORD) with `MONGODB_ATLAS_URI` + `MONGODB_DB` and docs for switching databases.
3. **README.md** — replaced 5 stale MongoDB env var rows with 2 correct ones (`MONGODB_ATLAS_URI`, `MONGODB_DB`).
4. **obsidian/Architecture/Environment Variables.md** — added guidance for switching DBs.
5. **obsidian/Database/MongoDB Schema.md** — added `MONGODB_DB` reference to header.
6. **obsidian/Changelog/Version History.md** — added v0.27.1.

### Security Hardening (Session 020b)
- Expanded .gitignore (4→40+ patterns: secrets, certs, Python artifacts, .bak, output/prds, obsidian/.obsidian, IDE).
- Untracked 40 files from git index (9 .bak, 27 output/prds, 4 obsidian config).
- Full secrets audit confirmed no real keys ever committed to git history.

### Tests
- 2320 passed

---

## Session 022 — Confluence Title Cleanup
**Date**: 2026-03-20 | **Version**: 0.27.1 → 0.28.0

### Goal
Replace `"PRD — {idea}"` Confluence/Jira page titles with the short-form idea text.

### Changes
1. **orchestrator/_helpers.py** — new `make_page_title(idea, fallback)` helper: strips, truncates to 80 chars with `…`, falls back to "Product Requirements".
2. **12 inline title sites replaced** across 9 files: `_confluence.py`, `_post_completion.py` (×2), `_startup_delivery.py`, `_startup_review.py` (×2), `_jira.py` (×2), `_cli_startup.py`, `publishing/service.py`, `publishing/watcher.py`, `components/startup.py`.
3. **publishing/models.py** — updated Field description example.
4. **17 test assertions updated** across 5 test files to match new title format.
5. **8 new tests** for `make_page_title` in `test_helpers.py`.

### Tests
- 2328 passed

---

## Session 023 — Confluence "Not Configured" Bug Fix
**Date**: 2026-03-20 | **Version**: 0.28.0 → 0.28.1

### Goal
Fix false-negative "Confluence credentials are not configured" error when
publishing from Slack, even when the channel's `projectConfig` has a valid
`confluence_space_key`.

### Root Cause
`_has_confluence_credentials()` called `_get_confluence_env()` with no args,
requiring all four env vars including `CONFLUENCE_SPACE_KEY`.  But space key
is a per-project routing parameter stored in MongoDB `projectConfig` and
resolved at publish time via `confluence_project_context` — not a global
env var.  The credential check ran **before** project config was loaded,
so it always failed when `CONFLUENCE_SPACE_KEY` wasn't in `.env`.

### Changes
1. **tools/confluence_tool.py** — rewrote `_has_confluence_credentials()` to
   only check the three Atlassian connection env vars (`ATLASSIAN_BASE_URL`,
   `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN`).  `CONFLUENCE_SPACE_KEY` is
   no longer required at the credential-check gate.
2. **tests/orchestrator/test_helpers.py** — updated
   `TestHasConfluenceCredentials`: removed `CONFLUENCE_SPACE_KEY` from
   `test_all_set`, added `test_true_without_space_key` case.

### Tests
- 2329 passed

---

## Session 024 — Suppress Redundant Delivery Notification
**Date**: 2026-03-20 | **Version**: 0.28.1 → 0.28.2

### Goal
Fix unwanted "PRD Generation Complete" Slack notification when PRD is
fully delivered in the backend (Confluence + Jira both done).

### Root Cause
After the PRD flow finishes (including post-completion Confluence publish
and all Jira phases), `SlackPostPRDResultTool` posts a "PRD Generation
Complete" banner with ":white_check_mark: PRD has been generated
successfully!" — redundant because the user already received granular
progress messages for each delivery step (Confluence published, Jira
phase messages). The `predict_and_post_next_step("prd_completed")`
call fires immediately after, adding further noise.

### Changes
1. **interactive_handlers/_flow_runner.py** — skip `SlackPostPRDResultTool`
   and `predict_and_post_next_step` when `confluence_url` AND `jira_output`
   are both set (fully delivered).
2. **_flow_handlers.py** — same guard on the resume path.
3. **router.py** — same guard on the non-interactive flow path.

### Tests
- 2329 passed

---

## Session 025 — Route Feedback to Active PRD Flow
**Date**: 2026-03-20 | **Version**: 0.28.2 → 0.29.0

### Goal
Fix no response from orchestrator when user gives feedback during an
active PRD flow (e.g. "remove the avatar video references and focus
only on the compliances").

### Root Cause
`_handle_thread_message_inner` only routed thread replies to the active
flow when `pending_action` was in `_THREAD_REPLY_ACTIONS` (manual_refinement,
exec_summary_pre_feedback, exec_summary_feedback). During section
drafting, `pending_action` is `None` — so user feedback fell through to
`_interpret_and_act` (LLM intent classifier), which treated it as a new
command and responded with unrelated help text or silence.

### Changes
1. **interactive_handlers/_run_state.py** — new `_queued_feedback` dict,
   `queue_feedback(run_id, text)` and `drain_queued_feedback(run_id)`.
2. **_event_handlers.py** — restructured thread-reply matching: first
   checks if `pending_action` is in `_THREAD_REPLY_ACTIONS` (gate mode),
   then falls back to `queue_feedback` for any active run with
   `pending_action=None` (section drafting). Acknowledges with
   ":memo: Got it! I'll incorporate your feedback…".
3. **_event_handlers.py** — new `_safe_ack_reply` helper.
4. **flows/_section_loop.py** — at the top of each iteration, drains
   queued feedback and uses it as `user_feedback` (replaces AI critique).
5. **interactive_handlers/__init__.py** — exports `_queued_feedback`,
   `queue_feedback`, `drain_queued_feedback`.
6. **tests/apis/slack/conftest.py** — new autouse fixture to clear
   `_interactive_runs`, `_manual_refinement_text`, `_queued_feedback`
   between tests.

### Tests
- 2329 passed

---

## Session 026 — Fix Bot Not Engaging in Session Threads
**Date**: 2026-03-20 | **Version**: 0.29.0 → 0.29.1

### Goal
Fix bot not responding when user talks in a Slack session thread.
Expected outcome: bot should understand intent to start configuring
the project even after in-memory thread cache expires.

### Root Cause
The `should_process` gate in `events_router.py` silently dropped
thread messages when ALL 4 conditions were False:
1. `has_conversation` — in-memory thread cache expired after 10-min TTL
   or server restart
2. `has_interactive` — no active PRD flow in `_interactive_runs`
3. `has_pending` — no pending create/setup wizard
4. `has_active_session` — no project selected yet
   (`get_channel_project_id` returns None)

This meant any thread where the user hadn't selected a project yet
(wants to START configuring) became completely unresponsive after the
10-minute thread cache TTL.

### Changes
1. **mongodb/agent_interactions/repository.py** — new
   `has_bot_thread_history(channel, thread_ts)` checks
   `agentInteraction` collection for prior bot participation via
   `find_one({channel, thread_ts})`.
2. **mongodb/agent_interactions/__init__.py** — re-exports
   `has_bot_thread_history`.
3. **apis/slack/events_router.py** — added 5th fallback condition
   `has_thread_history` in `should_process` gate. Only checked when
   all other 4 conditions are False. When True, also re-registers
   the thread in the in-memory cache via `touch_thread()` to avoid
   repeated DB lookups.
4. **tests/apis/slack/test_dm_and_pending_routing.py** — 3 new tests
   in `TestThreadHistoryFallback`: dispatches when history exists,
   ignored when no history, re-registers in memory cache.
5. **tests/mongodb/agent_interactions/test_repository.py** — 3 new
   tests for `has_bot_thread_history`: found, not found, DB error.

### Tests
- 2335 passed

---

## Session 027 — Fix Bare 'configure' Intent Not Recognised
**Date**: 2026-03-20 | **Version**: 0.29.1 → 0.29.2

### Goal
Fix bare "configure" not being recognised as project configuration
intent. Admin types "configure" and expects the bot to start
project configuration.

### Root Cause
`_UPDATE_CONFIG_PHRASES` required at least two words (e.g. "configure
project", "project config"). The single word "configure" didn't match
any phrase in either `_UPDATE_CONFIG_PHRASES` or
`_CONFIGURE_MEMORY_PHRASES`, so it fell through to the LLM classifier
which also didn't map it to `update_config`.

### Changes
1. **_intent_phrases.py** — added "configure" to `_UPDATE_CONFIG_PHRASES`
2. **gemini_chat.py** — added `"configure" → update_config` example
3. **openai_chat.py** — added `"configure" → update_config` example
4. **tests/apis/slack/test_update_config_intent.py** — new test file
   with 5 tests: phrase fallback for bare "configure", phrase fallback
   for config phrases, "configure memory" still routes to
   configure_memory, bare "configure" dispatches to update_config
   handler, LLM update_config dispatches correctly.

### Tests
- 2340 passed

---

## Session 028 — 2026-03-20

**Scope**: All Commands Clickable — Interactive Buttons
**Date**: 2026-03-20 | **Version**: 0.29.2 → 0.30.0

### Goal
Replace all text-based "Say *command*" prompts with clickable Slack
Block Kit buttons so users never need to type command text.

### Changes
1. **blocks/_command_blocks.py** (NEW) — 11 button constants
   (BTN_LIST_IDEAS, BTN_LIST_PRODUCTS, BTN_CONFIGURE, etc.) and
   10 composite block builders (help_blocks, session_action_buttons,
   resume_prd_button, post_memory_saved_buttons, etc.)
2. **interactions_router/_command_handler.py** (NEW) — CMD_ACTIONS
   frozenset, _handle_command_action dispatcher routing cmd_* clicks
   to existing session/flow handlers, _handle_help with Block Kit.
3. **interactions_router/_dispatch.py** — Added _CMD_PREFIX and cmd_*
   dispatch block between session and memory actions.
4. **blocks/__init__.py** — Exported all new command block builders.
5. **interactions_router/__init__.py** — Exported CMD_ACTIONS and
   _handle_command_action.
6. **18 text replacements across 12 files**:
   - _session_blocks.py → session_action_buttons()
   - _memory_blocks.py → post_memory_saved_buttons(), post_memory_view_buttons()
   - _retry_blocks.py → removed "say resume prd flow" text
   - _product_list_blocks.py → product_list_footer_buttons()
   - _session_products.py → no_products_buttons()
   - _flow_handlers.py → BTN_LIST_IDEAS button, plain text fallback updated
   - _message_handler.py → help_blocks() with Block Kit
   - _next_step_handler.py → missing_keys_buttons(), check_publish_buttons()
   - _restart_handler.py → restart_cancelled_buttons()
   - _retry_handler.py → "Click Resume PRD" text
   - router.py → "Click Resume PRD" fallback text
   - _session_reply.py → INTRO_MESSAGE updated
   - apis/__init__.py → startup notification updated
7. **Test updates**: Fixed 3 existing tests for new block structure.
8. **33 new tests**: test_command_blocks.py (17), test_command_handler.py (16).

### Tests
- 2373 passed

---

## Session 029 — 2026-03-21

**Scope**: Complete Intent Button Coverage & Interaction-First Rule
**Date**: 2026-03-21 | **Version**: 0.30.0 → 0.30.1

### Goal
Audit all Slack intents and ensure every actionable one has a `cmd_*`
button. Codify the Interaction-First Rule so all future intents must
have clickable buttons.

### Audit Results
- 19 total LLM-recognised intents
- 11 already had buttons (from session 028)
- 5 actionable intents were missing buttons: `publish`, `create_jira`,
  `restart_prd`, `current_project`, `create_prd`
- 3 non-actionable intents (`greeting`, `general_question`, `unknown`)
  correctly excluded

### Changes
1. **blocks/_command_blocks.py** — Added 5 new button constants:
   BTN_PUBLISH, BTN_CREATE_JIRA, BTN_RESTART_PRD, BTN_CURRENT_PROJECT,
   BTN_NEW_IDEA. Updated help_blocks() from 2 to 4 action rows.
2. **interactions_router/_command_handler.py** — Added 5 new dispatch
   branches + updated CMD_ACTIONS (11 → 16).
3. **blocks/__init__.py** — Exported 5 new BTN_* constants.
4. **_message_handler.py** — Replaced fallback unknown-intent text
   ("type help for options") with New Idea + Help buttons.
5. **CODEX.md** — Added "Slack Interaction-First Rule" section with
   invariants, naming conventions, and checklist table.
6. **obsidian/Architecture/Coding Standards.md** — Added § 9 "Slack
   Interaction-First Rule" with required artifacts, naming convention,
   and forbidden patterns.

### Tests
- 2380 passed (7 new)

---

## Session 030 — 2026-03-21

**Scope**: Admin-Gated Project Configuration & Role-Aware Buttons
**Date**: 2026-03-21 | **Version**: 0.30.1 → 0.30.2

### Goal
Non-admin channel users should not be able to configure project settings,
switch projects, create projects, or configure knowledge/memory. Admin-only
buttons should be hidden from non-admin users in the help menu.

### Changes
1. **interactions_router/_command_handler.py** — Added `_ADMIN_ACTIONS`
   frozenset (cmd_configure_project, cmd_configure_memory,
   cmd_switch_project, cmd_create_project). Admin gate at top of
   `_handle_command_action()`. `_deny_non_admin()` helper.
   `_handle_help()` passes `is_admin` to `help_blocks()`.
2. **blocks/_command_blocks.py** — `help_blocks()` now accepts
   `is_admin` parameter. Admin-only buttons hidden for non-admins
   (4 action rows for admin, 3 for non-admin).
3. **_message_handler.py** — Added `can_manage_memory` gate before
   `update_config` intent handler. Help intent passes `is_admin`.
4. **interactions_router/_next_step_handler.py** — Added admin gate
   for `configure_memory` next-step accept path.

### Tests
- 2398 passed (18 new: 12 admin gate, 4 help blocks role, 2 next-step)

---

## Session 031 — 2026-03-21

**Scope**: Defense-in-Depth Admin Gates
**Date**: 2026-03-21 | **Version**: 0.30.2 → 0.30.3

### Goal
Add handler-level admin gates so non-admins are blocked regardless of
which caller invokes the handler (not just at the button dispatch level).

### Changes
- Added `can_manage_memory()` checks directly inside
  `handle_update_config`, `handle_configure_memory`,
  `handle_project_name_reply`, and `handle_project_setup_reply`.

### Tests
- 2398 passed

---

## Session 032 — 2026-03-21

**Scope**: Interaction-First Rule for ALL Slack Prompts
**Date**: 2026-03-21 | **Version**: 0.30.3 → 0.31.0

### Goal
Replace every instance where the bot tells users to "type", "say", or
"tell me" something with clickable Block Kit buttons. No user should
ever need to type to navigate the bot.

### Changes
1. **blocks/_session_blocks.py** — Setup wizard: added Skip button
   (`setup_skip` action) on all 5 steps. Setup-complete: replaced
   "just say" text with BTN_NEW_IDEA + BTN_CONFIGURE_MEMORY + BTN_HELP.
   Removed misleading "Type project name to search" text.
2. **blocks/_idea_list_blocks.py** — Footer: replaced context text
   "describe a new idea" with BTN_NEW_IDEA actions block.
3. **_session_ideas.py** — Empty ideas: replaced plain text with Block
   Kit message containing BTN_NEW_IDEA.
4. **interactions_router/_next_step_handler.py** — Added `_post_blocks()`
   helper. All accepted next-step suggestions now post action buttons
   (BTN_CONFIGURE, BTN_NEW_IDEA, BTN_HELP) instead of text.
5. **_message_handler.py** — Greeting posts Block Kit with BTN_NEW_IDEA +
   BTN_HELP instead of plain text.
6. **interactions_router/_dispatch.py** — Added `_SETUP_ACTIONS` frozenset
   with `setup_skip` routing to `handle_project_setup_reply`.
7. **CODEX.md** — Added "Interaction-First Testing" section with Block Kit
   testing methodology, checklist, and quick-check commands.

### Tests
- 26 new tests in `test_interaction_first_rule.py`
- Updated `test_idea_list.py` action block count assertions (+1 for footer)
- 2425 total tests

---

## Session 033 — 2026-03-21

**Scope**: Fix "configure tools" Misrouted to Project Config
**Date**: 2026-03-21 | **Version**: 0.31.0 → 0.31.1

### Problem
User typed "configure tools" expecting to manage the tools category in
project memory. Gemini correctly classified as `configure_memory`, but
the message handler's `update_config` condition caught it first because:
1. "configure" (bare) was in `_UPDATE_CONFIG_PHRASES` → `has_config_phrase` = True
2. No "tools" phrases existed in `_CONFIGURE_MEMORY_PHRASES` → `has_memory_phrase` = False
3. The `update_config` check `intent == "update_config" or (... and has_config_phrase)` fired first

### Changes
1. **`_intent_phrases.py`** — Added 15 "tools" phrases to
   `_CONFIGURE_MEMORY_PHRASES` (configure tools, add tools, manage tools,
   show tools, edit tools, etc.)
2. **`gemini_chat.py`** — Added 8 "tools" → configure_memory examples
   and added "tools" to the configure_memory description keywords
3. **`openai_chat.py`** — Same additions for parity
4. **`_message_handler.py`** — Changed update_config guard from
   `intent == "update_config" or (... and not has_memory_phrase ...)`
   to `not has_memory_phrase and (intent == "update_config" or ...)`
   so memory/tool phrases always override update_config, even when the
   LLM explicitly returns update_config

### Tests
- 4 new tests in `test_configure_memory_intent.py`
  (phrase fallback, correct dispatch, LLM override, negative check)
- 2429 total tests

---

## Session 034 — 2026-03-21

**Scope**: Slack File Upload Fallback for Truncated Content
**Date**: 2026-03-21 | **Version**: 0.31.1 → 0.31.2

### Problem
Slack Block Kit has a 3000-char limit per section text field. Long content
(idea refinements, exec summaries, requirements breakdowns) was silently
truncated at 2800 chars with only a "… (N more chars)" hint. Users could
not read the full output.

### Changes
1. **NEW `_slack_file_helper.py`** — shared utility module:
   - `truncate_with_file_hint(content, limit)` → `(preview, was_truncated)`
   - `upload_content_file(channel, thread_ts, content, filename, title)` → bool
2. **5 block builders** return `tuple[list[dict], bool]` instead of `list[dict]`:
   - `idea_approval_blocks`, `manual_refinement_prompt_blocks`,
     `requirements_approval_blocks`, `exec_summary_feedback_blocks`,
     `exec_summary_completion_blocks`
3. **8 caller sites** updated in `_flow_handlers.py` (3) and `_callbacks.py` (5)
   to unpack tuple and call `upload_content_file()` when truncated
4. **All test files** updated for tuple unpacking

### Tests
- 18 new tests in `test_slack_file_helper.py`
  (truncation helper, upload helper, was_truncated flag for all 5 builders)
- 2447 total tests

---

## Session 035 — 2026-03-21

**Scope**: Bot Only Responds When @Mentioned in Threads
**Date**: 2026-03-21 | **Version**: 0.31.2 → 0.32.0

### Problem
Bot was responding to all messages in threads where it had an active
session or thread history, even when the user did not @mention the bot.
Log showed user `U0AK24AU0F3` typing "configure" in a thread without
tagging the bot, and the bot classified it as `update_config` and
responded with the project setup wizard.

### Root Cause
The `events_router.py` thread follow-up logic had 5 conditions for
processing a message. The fallback conditions (`has_active_session` and
`has_thread_history`) were too permissive — they didn't require an
@mention. `has_active_session` is channel-level, not thread-level.

### Fix
Added `_bot_mentioned` check in events_router: fallback conditions
(`has_active_session`, `has_thread_history`) now require the bot to be
@mentioned in the message text. Active workflow conditions
(`has_interactive`, `has_pending`, `has_conversation`) remain
unrestricted since the user is replying to bot prompts.

When `bot_id` is unknown (e.g. no Slack client), the mention gate is
skipped to avoid breaking functionality.

### Tests
- 6 new tests in `test_dm_and_pending_routing.py`:
  - `TestMentionGateActiveSession` (no mention → ignored, with mention → dispatched)
  - `TestMentionGateThreadHistory` (no mention → ignored, with mention → dispatched)
  - `TestNoMentionGateForActiveWorkflows` (interactive + pending → dispatched without mention)
- 2453 total tests

---

## Session 036 — 2026-03-22

**Scope**: Fix File Upload Scope + Admin Cache TTL
**Date**: 2026-03-22 | **Version**: 0.32.0 → 0.32.1

### Problems
1. **File upload failing**: `files:write` scope missing from Slack manifest.
   Log showed: `missing_scope, needed: files:write`. The v0.31.2
   truncation+upload feature couldn't work in production.
2. **Admin status stale**: `_admin_cache` had no TTL (process-lifetime).
   User promoted from member to workspace admin was still blocked from
   configure actions. Log showed: `Admin check user=U0AK24AU0F3 → False`.
3. **Truncation overflow**: `exec_summary_completion_blocks` wraps preview
   in ~85-char prefix but used 2800 limit, risking overflow past 3000.

### Changes
1. **`slack_manifest.json`** — Added `files:write`, `files:read`,
   `pins:read`, `assistant:write`, `calls:read`, `calls:write` scopes
   (matching what the Slack app already has installed).
2. **`session_manager.py`** — Admin cache changed from `dict[str, bool]`
   to `dict[str, tuple[bool, float]]` with 5-minute TTL. Expired entries
   trigger a fresh Slack API call. `import time` added inside function.
3. **`_exec_summary_blocks.py`** — `exec_summary_completion_blocks` uses
   `truncate_with_file_hint(content, 2700)` instead of default 2800.

### Tests
- 3 new tests in `test_session_context.py`:
  - Cache TTL expired → re-checks Slack API
  - Cache TTL not expired → uses cached value
  - Role upgrade detected after TTL expires
- 1 updated assertion in `test_exec_summary_completion_gate.py`:
  combined section text <= 3000
- 2456 total tests

---

## Session 031 — 2026-03-22

**Scope**: Output file reorganisation & UX design file fix
**Version**: v0.32.1 → v0.33.0

### Problem
1. UX design markdown files were generated on every `run_ux_design()` call regardless of whether Figma actually produced a design — causing duplicate files.
2. All PRD and UX output files were stored in a flat `output/prds/YYYY/MM/` structure with no separation by project.

### Work Done
1. **UX file gating** (`flows/_ux_design.py`):
   - `_save_ux_design_file()` is now only called when `figma_url` is non-empty (Figma design successful).
   - Previously called unconditionally for every prompt/error/fallback output.

2. **Project-based output directories** (`flows/_finalization.py`, `flows/_ux_design.py`):
   - `finalize()` now saves PRDs to `output/{project_id}/product requirement documents/`
   - `save_progress()` uses `output/{project_id}/product requirement documents/_drafts/`
   - `_save_ux_design_file()` saves to `output/{project_id}/ux design/`
   - Falls back to legacy `output/prds/` when `project_id` is unavailable.

3. **`ux_output_file` MongoDB field** (`mongodb/working_ideas/_status.py`):
   - Added `get_ux_output_file()` and `save_ux_output_file()` functions.
   - UX file path is persisted with cleanup-on-replace logic (old file deleted when new one saved).
   - Exported via `repository.py` and `mongodb/__init__.py`.

4. **Startup disk scanner** (`orchestrator/_startup_review.py`):
   - `_discover_publishable_prds()` now scans both legacy `output/prds/` and `output/{project_id}/product requirement documents/` directories.

5. **Migration script** (`scripts/migrate_output_dirs.py`):
   - Queries workingIdeas documents with `output_file` or `ux_output_file` and `project_id`.
   - Moves files on disk and updates MongoDB references.
   - Supports `--dry-run` mode for preview.
   - Delete after running per project convention.

### Tests
- 7 new tests:
  - `test_file_saved_when_figma_url_present` — confirms file saved on successful Figma
  - `test_file_not_saved_when_prompt_only` — confirms no file for prompt-only
  - `test_file_not_saved_when_error_skipped` — confirms no file on skip/error
  - `test_file_uses_project_dir_when_available` — project_id passed to save function
  - `test_finalize_uses_project_dir_when_project_id_available` — PRD uses project dir
  - `test_save_progress_uses_project_dir_when_project_id_available` — drafts use project dir
  - (7th implicit: existing tests all updated with `resolve_project_id` patch)
- All existing tests updated to patch `resolve_project_id` in finalization module.
- 2463 total tests, all passing.

### Files Modified
- `src/.../flows/_ux_design.py` — Gate file generation, project-aware paths
- `src/.../flows/_finalization.py` — Project-aware output directories
- `src/.../mongodb/working_ideas/_status.py` — `get_ux_output_file`, `save_ux_output_file`
- `src/.../mongodb/working_ideas/repository.py` — Export new functions
- `src/.../mongodb/__init__.py` — Export new functions
- `src/.../orchestrator/_startup_review.py` — Scan project-based dirs
- `src/.../version.py` — v0.33.0
- `scripts/migrate_output_dirs.py` — NEW one-time migration script
- `tests/flows/test_ux_design.py` — 4 new tests
- `tests/flows/test_prd_flow.py` — 2 new tests + 7 updated tests
- `obsidian/Database/MongoDB Schema.md` — Added new fields
- `obsidian/Architecture/Module Map.md` — Added migration script
- `obsidian/Changelog/Version History.md` — v0.33.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-03-22

**Scope**: Project Knowledge Base — Obsidian-style knowledge folders for agent learning
**Version**: v0.33.0 → v0.34.0

### Changes

1. **New module** (`scripts/project_knowledge.py`):
   - Generates `projects/{name}/{name}.md` overview pages with config, memory, tools, reference URLs, and wikilinks to completed ideas.
   - Generates `projects/{name}/ideas/{idea}.md` pages from workingIdeas docs with YAML frontmatter, full PRD sections in Obsidian format.
   - `load_completed_ideas_context()` queries MongoDB for completed ideas and formats summaries for agent backstory enrichment.
   - `sync_project_knowledge()` and `sync_completed_idea()` orchestrate page generation.

2. **Hooked into project creation** (`mongodb/project_config/repository.py`):
   - `create_project()` now calls `sync_project_knowledge()` after successful insert to bootstrap the project knowledge folder.

3. **Hooked into finalization** (`flows/_finalization.py`):
   - `finalize()` calls `sync_completed_idea()` after `mark_completed()` to generate the idea page and refresh the project overview.

4. **Integrated with memory loader** (`scripts/memory_loader.py`):
   - `enrich_backstory()` now also calls `load_completed_ideas_context()` so agents receive completed idea summaries in their backstory, avoiding duplication and creating synergy.

### Tests Added (34 new, 2496 total)
- `tests/test_project_knowledge.py` — 34 tests covering:
  - `_safe_dirname`, `_safe_filename`, `_truncate`, `_idea_title_from_doc` helpers
  - `generate_project_page` (basic, memory, URLs, ideas subdir, wikilinks)
  - `generate_idea_page` (basic, sections, Figma, delivery, original vs refined)
  - `load_completed_ideas_context` (with docs, no docs, empty ID, DB error)
  - `sync_project_knowledge` (creates page, no config)
  - `sync_completed_idea` (creates page, no doc, no project_id)
  - `enrich_backstory` integration (includes ideas, no ideas)

### Files Modified
- `src/.../scripts/project_knowledge.py` — NEW: Obsidian knowledge base builder
- `src/.../mongodb/project_config/repository.py` — Hook sync_project_knowledge into create_project
- `src/.../flows/_finalization.py` — Hook sync_completed_idea into finalize
- `src/.../scripts/memory_loader.py` — Integrate completed ideas into enrich_backstory
- `src/.../version.py` — v0.34.0
- `tests/test_project_knowledge.py` — NEW: 34 tests
- `obsidian/Architecture/Module Map.md` — Added project_knowledge.py
- `obsidian/Changelog/Version History.md` — v0.34.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 055 — 2026-03-22

**Scope**: Engagement Manager Agent
**Version**: v0.34.0 → v0.35.0

### Work Done
- Created new CrewAI agent: **Engagement Manager** (`agents/engagement_manager/`)
  - YAML config: role, goal, backstory defining a navigation guide for unknown intents
  - Task config: engagement_response_task with template variables for user message, conversation history, active context, and available system actions
  - Python factory: `create_engagement_manager()` + `handle_unknown_intent()` runner
  - Uses `GEMINI_MODEL` (basic tier) — lightweight conversational routing, not deep reasoning
  - Override via `ENGAGEMENT_MANAGER_MODEL` env var
- Integrated into Slack message handler:
  - `unknown` intents now routed through the engagement manager agent instead of static fallback
  - Agent receives user message, conversation history, and active project context
  - Produces context-aware response with relevant action button suggestions
  - Graceful fallback to static help message if agent fails
  - `general_question` intents still use the LLM reply directly (kept separate)
  - Context-aware buttons: shows New Idea + Help (no project) or New Idea + List Ideas + Resume PRD + Help (with project)
- Added autouse mock fixture in `tests/apis/slack/conftest.py` to prevent real LLM calls in Slack tests
- Updated agents `conftest.py` to mock engagement manager LLM builder

### Tests Added (16 new, 2512 total)
- `tests/agents/test_engagement_manager.py`:
  - Factory: credentials required, accepts API key, accepts project, role content, no tools, no delegation, respects context window
  - LLM config: default model, ENGAGEMENT_MANAGER_MODEL override, GEMINI_MODEL fallback
  - YAML: agent.yaml loads with expected keys, tasks.yaml loads with template placeholders
  - Runner: returns response, passes history, includes context, propagates exceptions

### Files Modified
- `src/.../agents/engagement_manager/` — NEW: agent.py, __init__.py, config/agent.yaml, config/tasks.yaml
- `src/.../apis/slack/_message_handler.py` — Added `_handle_engagement_manager()`, `general_question` handler, replaced static fallback
- `src/.../version.py` — v0.35.0
- `tests/agents/test_engagement_manager.py` — NEW: 16 tests
- `tests/agents/conftest.py` — Added engagement manager LLM mock
- `tests/apis/slack/conftest.py` — Added engagement manager autouse mock
- `obsidian/Agents/Agent Roles.md` — Engagement Manager section
- `obsidian/Agents/LLM Model Tiers.md` — Added to Basic tier table
- `obsidian/Architecture/Module Map.md` — Added engagement_manager/ entry
- `obsidian/Architecture/Environment Variables.md` — Added ENGAGEMENT_MANAGER_MODEL
- `obsidian/Changelog/Version History.md` — v0.35.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 056 — 2026-03-23

**Scope**: Fully Automated PRD Flow + Active-Flow Config Guard
**Version**: v0.35.0 → v0.36.0

### Work Done

**Feature 1 — Active-Flow Config Guard:**
- New `has_active_idea_flow(project_id)` MongoDB query in `_queries.py` — checks if any working idea with status "inprogress" exists for the project
- Guard in `_message_handler.py` — blocks `update_config` and `configure_memory` intents when an idea flow is active
- Guard in `_command_handler.py` — blocks `cmd_configure_project` and `cmd_configure_memory` button clicks during active flows
- Both guards post a denial message explaining the restriction with a View Ideas button

**Feature 2 — Fully Automated Flow:**
- Default mode switched from interactive to automated — keywords "interactive", "step-by-step", "manual", "walk me through" opt-in to interactive mode
- Three auto-mode gate factories in `_flow_handlers.py`:
  - `make_auto_exec_summary_gate()` — drains queued feedback, auto-approves
  - `make_auto_exec_completion_gate()` — posts note, returns True (continue)
  - `make_auto_requirements_gate()` — posts note, returns False (approved)
- Router branches on `auto_approve` to wire auto vs blocking gates
- Enhanced progress summaries — `section_iteration` and `exec_summary_iteration` events include `critique_summary` showing what the agent is working on
- Progress poster renders critique summaries as "What I'm working on:" blocks with feedback invitation

**Feature 3 — Auto-Resume on Server Restart:**
- New `find_resumable_on_startup()` in `_queries.py` — partitions unfinalized ideas into resumable (has Slack context) vs failed (no context)
- Startup lifespan in `apis/__init__.py` replaced `fail_unfinalized_on_startup()` with `find_resumable_on_startup()` + `_auto_resume_flows()`
- New `_run_slack_resume_flow()` in `router.py` — builds auto-mode callbacks, calls `resume_prd_flow`, posts completion/pause/error to original Slack thread

### Tests Added (29 new, 2541 total)
- `tests/apis/slack/test_active_flow_guard.py` — 13 tests
- `tests/apis/slack/test_automated_flow.py` — 16 tests
- Updated `test_exec_summary_completion_gate.py` — fixed regression + added auto-mode test
- Updated `test_interactive_default.py` — inverted defaults to match new automated-first behavior

### Files Modified
- `src/.../mongodb/working_ideas/_queries.py` — `has_active_idea_flow()`, `find_resumable_on_startup()`
- `src/.../mongodb/working_ideas/repository.py` — Exported new functions
- `src/.../apis/slack/_message_handler.py` — Flow guard, default mode switch
- `src/.../apis/slack/interactions_router/_command_handler.py` — Flow guard for config actions
- `src/.../apis/slack/_flow_handlers.py` — Auto-mode gate factories, enhanced progress
- `src/.../apis/slack/router.py` — Auto vs blocking gate branching, `_run_slack_resume_flow()`
- `src/.../flows/_executive_summary.py` — critique_summary in progress notification
- `src/.../flows/_section_loop.py` — critique_summary in progress notification
- `src/.../apis/__init__.py` — Auto-resume startup logic
- `src/.../version.py` — v0.36.0
- `tests/apis/slack/test_active_flow_guard.py` — NEW: 13 tests
- `tests/apis/slack/test_automated_flow.py` — NEW: 16 tests
- `tests/apis/slack/test_exec_summary_completion_gate.py` — Updated + 1 new test
- `tests/apis/slack/test_interactive_default.py` — Inverted default behavior tests
- `obsidian/Changelog/Version History.md` — v0.36.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session 057 — 2026-03-23

**Scope**: Server Crash-Prevention Hardening
**Version**: v0.36.0 → v0.37.0

### Work Done

**Comprehensive Reliability Audit:**
- Three sub-agent audits identified 26+ crash vectors across APIs, webhooks, tools
- Handler-level audit found 7/11 interaction handlers with no top-level protection

**_safe_handler() Wrapper (core pattern):**
- New `_safe_handler()` in `_dispatch.py` — wraps handler with team-id injection + try/except
- On exception: logs ERROR with `exc_info=True`, posts `:x: Something went wrong` to Slack channel/thread
- Swallows exception to keep thread pool healthy
- Replaced all 13 interaction handler dispatch calls from `_with_team` to `_safe_handler`

**Endpoint Protection:**
- Global exception handler enhanced with `exc_info=True` for full tracebacks
- PRD router: `list_resumable_runs`, `list_all_jobs`, `get_job` wrapped → HTTPException(500)
- PRD kickoff: `find_active_job()` wrapped → HTTPException(500)
- OAuth router: `_exchange_code` and `_apply_tokens` wrapped with catch-all handlers
- SSO webhooks: handler dispatch wrapped in try/except with traceback logging

**Tool-Level Fixes:**
- Jira `_http.py`: `json.JSONDecodeError` caught → `RuntimeError("Jira API returned invalid JSON")`
- Confluence `confluence_tool.py`: same pattern for invalid JSON responses

### Tests Added (14 new, 2560 total)
- `tests/apis/test_crash_prevention.py` — NEW: 14 tests covering _safe_handler, global exception handler, Jira/Confluence JSON decode, PRD router MongoDB failures

### Files Modified
- `src/.../apis/__init__.py` — `exc_info=True` in global exception handler
- `src/.../apis/slack/interactions_router/_dispatch.py` — `_safe_handler()` + 13 dispatch replacements
- `src/.../apis/sso_webhooks.py` — Handler dispatch wrapped
- `src/.../apis/slack/oauth_router.py` — _exchange_code and _apply_tokens hardened
- `src/.../apis/prd/router.py` — 3 MongoDB query endpoints protected
- `src/.../apis/prd/_route_actions.py` — kickoff find_active_job wrapped
- `src/.../tools/jira/_http.py` — JSONDecodeError catch
- `src/.../tools/confluence_tool.py` — JSONDecodeError catch
- `src/.../version.py` — v0.37.0
- `tests/apis/test_crash_prevention.py` — NEW: 14 tests
- `obsidian/Changelog/Version History.md` — v0.37.0 entry
- `obsidian/Sessions/Session Log.md` — This entry

---

## Session — 2026-03-24

**Scope**: Slack thread recovery & flow-aware summaries
**Version**: v0.37.0 → v0.37.1

### Bugs Fixed

**Issue #1 — Thread messages silently dropped after cache expiry**
- Auto-mode flows (default since v0.36.0) don't register in `_interactive_runs`
- After the 30-min in-memory cache TTL expires, thread messages were silently
  dropped at events_router.py line 404
- **Fix**: Added `find_idea_by_thread()` MongoDB query as a final fallback before
  dropping the message. Queries `workingIdeas` by `slack_channel` +
  `slack_thread_ts`. On match, re-registers the thread in cache via `touch_thread()`.

**Issue #2 — "Give me a summary" gets generic help instead of flow status**
- LLM classifier doesn't know about flow context, so "Give me a summary of the
  refined idea" → `general_question` → generic help text
- **Fix**: Added `_is_summary_request()` phrase detector (14 phrases) and
  `_build_flow_summary()` builder. When `general_question` + summary phrase +
  flow doc found → posts structured flow status with emoji, sections done/total,
  idea text, and section names.

### Files Modified
- `src/.../mongodb/working_ideas/_queries.py` — `find_idea_by_thread()` function
- `src/.../mongodb/working_ideas/repository.py` — export `find_idea_by_thread`
- `src/.../apis/slack/events_router.py` — `has_flow_thread` fallback check
- `src/.../apis/slack/_message_handler.py` — `_SUMMARY_PHRASES`, `_is_summary_request()`,
  `_build_flow_summary()`, flow-aware `general_question` handler
- `tests/apis/slack/test_flow_thread_routing.py` — NEW: 16 tests
- `src/.../version.py` — v0.37.1

### Tests
- 16 new tests (4 thread recovery, 2 phrase detection, 4 summary builder,
  3 integration, 3 MongoDB query)
- 2571 total (all passing, 0 failures)

---

---