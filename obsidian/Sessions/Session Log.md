# Session Log

> AI agent session tracking. Every new session or iteration appends an entry.

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