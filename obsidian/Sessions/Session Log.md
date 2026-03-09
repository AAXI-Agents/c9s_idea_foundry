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
