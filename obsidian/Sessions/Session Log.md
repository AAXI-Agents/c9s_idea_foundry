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