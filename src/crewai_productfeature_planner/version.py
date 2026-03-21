"""Centralised version and changelog (codex) for the application.

Every deployment-worthy change gets an entry in ``_CODEX``.  The latest
entry's version is the canonical application version, surfaced in:

* Startup log lines
* ``GET /health`` and ``GET /version`` API responses
* The FastAPI ``app.version`` metadata / Swagger UI

Versioning scheme: **X.Y.Z**
    X (Release)   – bumped by user when cutting a release
    Y (Major)     – bumped by agent when adding new features or code
    Z (Minor)     – bumped by agent when iterating on a fix or bug
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple


class CodexEntry(NamedTuple):
    """Single codex (changelog) record."""

    version: str
    date: date
    summary: str


# ---------------------------------------------------------------------------
# Codex – append new entries at the **bottom**
# ---------------------------------------------------------------------------

_CODEX: list[CodexEntry] = [
    CodexEntry(
        version="0.1.0",
        date=date(2026, 2, 14),
        summary="Initial release — PRD generation flow, MongoDB persistence, FastAPI server.",
    ),
    CodexEntry(
        version="0.1.1",
        date=date(2026, 2, 25),
        summary=(
            "Slack OAuth refactoring — per-team tokens stored in MongoDB "
            "slackOAuth collection; removed .env token dependency."
        ),
    ),
    CodexEntry(
        version="0.1.2",
        date=date(2026, 2, 28),
        summary=(
            "Intent classification fix — added create_project intent to "
            "Gemini/OpenAI prompts with few-shot examples and text-level "
            "fallback detection so 'create a project' no longer loops to "
            "the project-selection prompt."
        ),
    ),
    CodexEntry(
        version="0.1.3",
        date=date(2026, 2, 28),
        summary=(
            "Version control & codex — centralised version module, "
            "GET /version endpoint, version in health response and "
            "startup logs for deployment traceability."
        ),
    ),
    CodexEntry(
        version="0.1.4",
        date=date(2026, 2, 28),
        summary=(
            "Thread reply awareness — app_mention events with pending "
            "state (e.g. awaiting project name) now route through the "
            "thread handler instead of re-interpreting via LLM. Other "
            "users' replies are ignored while waiting for the initiating "
            "user's input, ensuring session isolation."
        ),
    ),
    CodexEntry(
        version="0.1.5",
        date=date(2026, 2, 28),
        summary=(
            "Intent fix & project setup wizard — 'iterate an idea' no "
            "longer misclassified as create_project when a session is "
            "active.  Project creation now walks through a 3-step setup "
            "wizard (Confluence space key, Jira project key, Confluence "
            "parent page ID) matching the CLI experience."
        ),
    ),
    CodexEntry(
        version="0.1.6",
        date=date(2026, 2, 28),
        summary=(
            "Comprehensive intent audit — added 5 new LLM intents "
            "(list_projects, switch_project, end_session, current_project, "
            "configure_memory) to Gemini/OpenAI prompts.  Replaced brittle "
            "exact-match text commands with broader phrase-matching + LLM "
            "intent routing.  'show me available projects' and other natural "
            "phrasing now works correctly.  Updated help text to list all "
            "available capabilities."
        ),
    ),
    CodexEntry(
        version="0.2.0",
        date=date(2026, 3, 1),
        summary=(
            "Auto-resume & observability — server auto-resumes interrupted "
            "PRD flows on restart with 3-strategy Slack context recovery. "
            "Heartbeat progress posts section_start events to Slack and "
            "tracks current_section in crewJobs. crewJobs persists "
            "slack_channel/slack_thread_ts. Slack manifest token validation. "
            "Migrated embedder from google-generativeai to google-vertex. "
            "Conventional single-line logging (removed box-drawing output). "
            "CODEX.md + VS Code / Claude Code instruction files for AI agents."
        ),
    ),
    CodexEntry(
        version="0.2.1",
        date=date(2026, 3, 1),
        summary=(
            "Post-completion next-step prompts — SlackPostPRDResultTool now "
            "shows deterministic next-step hints (publish / create jira "
            "tickets) when Confluence or Jira delivery wasn't completed. "
            "Added predict_and_post_next_step() to non-interactive Slack "
            "flow and auto-resume completion paths for consistency with "
            "the interactive handler."
        ),
    ),
    CodexEntry(
        version="0.2.2",
        date=date(2026, 3, 1),
        summary=(
            "Fix PostCompletion delivery crew crash — unescaped curly braces "
            "in Prometheus metric example in tasks.yaml "
            "(api_requests_total{method=\"POST\", status=\"201\"}) caused "
            "Python str.format() to raise KeyError during Jira task "
            "construction, preventing Confluence publish and Jira ticket "
            "creation after PRD finalization."
        ),
    ),
    CodexEntry(
        version="0.3.0",
        date=date(2026, 3, 1),
        summary=(
            "PRD output sanitization, Slack file upload, and next-step fix. "
            "(1) Added sanitize_section_content() to detect and strip JSON "
            "document dumps the LLM occasionally wraps executive summaries "
            "in — applied in PRDDraft.assemble(), assemble_prd_from_doc(), "
            "and _iterate_executive_summary(). "
            "(2) SlackPostPRDResultTool now uploads the PRD markdown file "
            "to Slack via files_upload_v2() instead of showing the path. "
            "(3) Fixed predict_and_post_next_step() receiving no "
            "project_config in auto-resume and non-interactive flows, "
            "causing incorrect 'configure_confluence' predictions."
        ),
    ),
    CodexEntry(
        version="0.3.1",
        date=date(2026, 3, 1),
        summary=(
            "Restart PRD flow intent — new restart_prd intent lets users "
            "archive the current PRD run and start a fresh flow with the "
            "same idea. Separated 'restart' from 'resume' in both LLM "
            "intent classification and phrase-based fallback. Confirmation "
            "prompt via Block Kit buttons before archiving. Added "
            "mark_archived() to MongoDB working_ideas repository; "
            "find_unfinalized() now excludes archived runs. Wired "
            "restart_prd_confirm/cancel actions in interactions router."
        ),
    ),
    CodexEntry(
        version="0.4.0",
        date=date(2026, 3, 1),
        summary=(
            "Executive summary interactive feedback loop — new "
            "exec_summary_user_feedback_callback on PRDFlow lets users "
            "provide initial guidance before the first draft and "
            "critique/approve after each iteration via Slack. Pre-draft "
            "prompt posts Block Kit buttons (Skip / Cancel) and accepts "
            "thread replies as initial guidance. Post-iteration prompt "
            "shows the current summary with Approve / Cancel buttons; "
            "thread replies trigger another refine iteration with user "
            "feedback injected alongside the AI critique. Wired into "
            "run_interactive_slack_flow() with new Block Kit builders "
            "(exec_summary_pre_feedback_blocks, "
            "exec_summary_feedback_blocks) and action IDs "
            "(exec_summary_approve, exec_summary_skip). Events router "
            "extended to route thread replies during exec summary "
            "feedback sessions."
        ),
    ),
    CodexEntry(
        "0.4.1",
        date(2026, 3, 1),
        (
            "Slack bot interaction fixes — three issues resolved: "
            "(1) Added list_ideas intent so 'list of ideas' queries "
            "the project's working ideas instead of prompting project "
            "selection; channel-level project set by admin is used "
            "automatically for any user. "
            "(2) New find_ideas_by_project() MongoDB query returns "
            "ideas in all statuses (in-progress, paused, completed) "
            "for the current project. "
            "(3) Reworded all user-facing messages from 'generate a "
            "PRD' to 'iterate on an idea' language throughout Slack "
            "handlers, system prompts, help text, intro message, and "
            "next-step suggestions."
        ),
    ),
    CodexEntry(
        "0.4.2",
        date(2026, 3, 1),
        (
            "Interactive idea list — 'list ideas' now posts Block Kit "
            "messages with per-idea Resume and Restart buttons instead of "
            "asking users to type 'resume idea #N'. Added "
            "idea_list_blocks() builder, idea_resume_<N>/idea_restart_<N> "
            "action IDs, and _handle_idea_list_action() in the "
            "interactions router. Resume dispatches to handle_resume_prd; "
            "Restart shows the existing confirmation prompt."
        ),
    ),
    CodexEntry(
        "0.4.3",
        date(2026, 3, 1),
        (
            "Refactor blocks.py (1232 lines) into a blocks/ package with "
            "7 focused sub-modules: _flow_blocks, _session_blocks, "
            "_memory_blocks, _next_step_blocks, _exec_summary_blocks, "
            "_jira_blocks, _idea_list_blocks. The __init__.py re-exports "
            "all public names for full backward compatibility — zero "
            "import changes required in consumers."
        ),
    ),
    CodexEntry(
        "0.4.4",
        date(2026, 3, 1),
        (
            "Refactor interactions_router.py (985 lines) into an "
            "interactions_router/ package with 6 sub-modules: _dispatch, "
            "_project_handler, _memory_handler, _next_step_handler, "
            "_restart_handler, _idea_list_handler. Refactor "
            "interactive_handlers.py (942 lines) into an "
            "interactive_handlers/ package with 5 sub-modules: _run_state, "
            "_decisions, _slack_helpers, _callbacks, _flow_runner. Both "
            "packages re-export all public names via __init__.py facades."
        ),
    ),
    CodexEntry(
        "0.4.5",
        date(2026, 3, 2),
        (
            "Fix rescan/restart of completed ideas — execute_restart_prd "
            "now uses find_run_any_status() which includes completed runs "
            "instead of find_unfinalized()+get_run_documents() which both "
            "excluded them. Fix resume of completed ideas — "
            "handle_resume_prd now detects completed status and suggests "
            "Rescan instead of failing silently."
        ),
    ),
    CodexEntry(
        "0.4.6",
        date(2026, 3, 2),
        (
            "Ignore messages directed at other users — thread messages "
            "starting with @another_user (not the bot) are silently "
            "dropped instead of processed as follow-ups. "
            "Add general_question intent — informational questions like "
            "'What is a PRD?' now receive a conversational answer from "
            "the LLM instead of the static help menu."
        ),
    ),
    CodexEntry(
        "0.4.7",
        date(2026, 3, 2),
        (
            "Non-interactive exec summary feedback gate — the Slack "
            "PRD flow now pauses after generating the executive summary "
            "and posts an approve/iterate prompt with Block Kit buttons. "
            "Users can approve to proceed or reply with critique to "
            "trigger another iteration. Thread replies and button clicks "
            "are routed through resolve_exec_feedback(). Auto-approves "
            "after 600 s timeout."
        ),
    ),    CodexEntry(
        "0.5.0",
        date(2026, 3, 2),
        (
            "Flow-paused retry button \u2014 when a PRD flow pauses due to "
            "LLM / billing / internal errors, the Slack notification now "
            "includes a Retry button (action_id: flow_retry) that triggers "
            "handle_resume_prd. Replaces the old text-only message in all "
            "four pause paths (router, interactive runner, flow_handlers "
            "resume, auto-resume). "
            "Crash-prevention hardening \u2014 all background thread targets "
            "and run_prd_flow / resume_prd_flow now catch BaseException "
            "(SystemExit, KeyboardInterrupt) to prevent a CrewAI subprocess "
            "crash from taking down the server. A global threading.excepthook "
            "is installed during server lifespan as a final safety net."
        ),
    ),
    CodexEntry(
        "0.6.0",
        date(2026, 3, 2),
        (
            "Kill old runs on restart \u2014 replaced auto-resume with clean "
            "termination of all unfinalized PRD flows on server restart. "
            "New fail_unfinalized_on_startup() marks paused/in-progress "
            "working ideas as failed so new code changes take effect. "
            "Slack threads receive a termination notice instead of being "
            "auto-resumed with stale code. Users can say 'create prd' to "
            "start a fresh run."
        ),
    ),
    CodexEntry(
        "0.6.1",
        date(2026, 3, 2),
        (
            "Fix empty idea title in listing \u2014 save_slack_context no "
            "longer creates orphan workingIdeas documents via upsert, "
            "preventing $setOnInsert from being skipped for the idea field. "
            "find_ideas_by_project now falls back to finalized_idea when the "
            "idea field is empty. handle_list_ideas uses Block Kit "
            "idea_list_blocks with interactive Resume/Restart buttons "
            "instead of plain text. Added crew-job backfill for legacy "
            "documents missing idea text."
        ),
    ),
    CodexEntry(
        "0.6.2",
        date(2026, 3, 2),
        (
            "Fix Slack invalid_blocks error on restart — truncate idea text "
            "to 500 chars in restart confirmation blocks and resume/archive "
            "messages to stay within the Slack 3000-char section block limit."
        ),
    ),
    CodexEntry(
        "0.6.3",
        date(2026, 3, 2),
        (
            "Fix '(unknown idea)' on restart — execute_restart_prd, "
            "handle_restart_prd, and handle_resume_prd now fall back to "
            "finalized_idea when the idea field is empty. find_unfinalized "
            "also applies the same fallback. Fixed stale test patches that "
            "targeted find_unfinalized instead of find_run_any_status."
        ),
    ),
    CodexEntry(
        "0.6.4",
        date(2026, 3, 2),
        (
            "Fix premature 'Suggested next step' on create_prd — removed "
            "create_prd from _SUGGEST_AFTER_INTENTS so the next-step "
            "prediction only fires after completed actions (publish, "
            "check_publish), not when the PRD flow is just starting. "
            "The prediction is already posted after flow completion in "
            "router._run_slack_prd_flow."
        ),
    ),
    CodexEntry(
        "0.6.5",
        date(2026, 3, 2),
        (
            "Exec summary completion gate + JSON bloat fix — (1) Added "
            "executive_summary_callback phase gate between Phase 1 (exec "
            "summary) and Phase 2 (section drafting). Slack users now see "
            "the finalized exec summary with Continue / Stop buttons before "
            "section drafting begins. New completion blocks, resolve_exec_completion, "
            "make_exec_summary_completion_gate in _flow_handlers, wired through "
            "service.run_prd_flow and router._run_slack_prd_flow. New action IDs: "
            "exec_summary_continue, exec_summary_stop. (2) Rewrote draft_prd_task "
            "and critique_prd_task expected_output in tasks.yaml to request "
            "markdown content only — removed full MongoDB JSON document schema "
            "that caused LLM responses to include bloated JSON objects."
        ),
    ),
    CodexEntry(
        "0.7.0",
        date(2026, 3, 2),
        (
            "Large-file modular refactoring — Split 10 files exceeding 550 "
            "lines into focused sub-modules with backward-compatible facades. "
            "prd_flow.py (2103→530L, 5 sub-modules), main.py (1676→454L, 4), "
            "_flow_handlers.py (1124→package, 4), working_ideas/repository.py "
            "(1086→85L, 4), jira_tool.py (859→12L shim, jira/ package with 5), "
            "_message_handler.py (734→370L, 3), models.py (694→81L, 7), "
            "_session_handlers.py (692→50L, 4), router.py (631→225L, 1 sub-router), "
            "events_router.py (605→375L, 1 _event_handlers with sys.modules "
            "call-through for test patchability). All 1504 tests pass."
        ),
    ),
    CodexEntry(
        "0.7.1",
        date(2026, 3, 3),
        (
            "Fix in-progress ideas invisible to 'list ideas' — "
            "save_project_ref and save_slack_context now run before the "
            "PRD flow starts (with upsert=True) so in-progress working "
            "ideas have project_id set immediately. Previously these "
            "functions were called only after flow completion, causing "
            "find_ideas_by_project to miss running/paused ideas. Both "
            "router._run_slack_prd_flow and interactive _flow_runner "
            "updated. New tests for upsert behavior added."
        ),
    ),
    CodexEntry(
        "0.7.2",
        date(2026, 3, 3),
        (
            "Backfill orphaned working ideas — Added _backfill_orphaned_ideas() "
            "to rescue workingIdeas documents missing project_id by cross-referencing "
            "crewJobs channel. find_ideas_by_project() now accepts optional channel "
            "kwarg to trigger backfill. Callers (_session_ideas, _flow_handlers) pass "
            "channel. Also fixed find_unfinalized() missing 'status' in return dict, "
            "extracted _doc_to_idea_dict() helper to reduce duplication, and removed "
            "duplicate return statement. 7 new tests for backfill scenarios."
        ),
    ),
    CodexEntry(
        "0.7.3",
        date(2026, 3, 3),
        (
            "Resume flow exec-summary user gates — resume_prd_flow() now "
            "accepts exec_summary_user_feedback_callback and "
            "executive_summary_callback parameters. handle_resume_prd() "
            "creates and wires both Slack gates (per-iteration feedback "
            "and Phase 1→2 completion review) so resumed flows show "
            "executive summary results for user review, matching the "
            "initial-run behavior."
        ),
    ),
    CodexEntry(
        "0.7.4",
        date(2026, 3, 4),
        (
            "Rescan exec-summary review gate & failed-idea titles — "
            "(1) skip_phase1 branch now invokes executive_summary_callback "
            "so users can review the existing exec summary before Phase 2 "
            "on resume/rescan. (2) Fixed create_job() callers in Slack "
            "router and interactive flow runner using positional args that "
            "put the idea text into flow_name instead of idea. (3) Moved "
            "idea from $setOnInsert to $set in save_iteration() so working-"
            "idea documents always have the title. (4) Enhanced backfill "
            "to recover titles from flow_name field in legacy crew-job docs."
        ),
    ),
    CodexEntry(
        "0.8.0",
        date(2026, 3, 4),
        (
            "Manual archive interaction for idea list — Added an Archive "
            "button to each idea in the idea list (alongside Resume and "
            "Rescan). Clicking Archive shows a confirmation prompt; on "
            "confirm, both the working-idea document and crew job are "
            "marked as archived and removed from the active list. New "
            "files: _archive_handler.py (confirmation button handler). "
            "New functions: handle_archive_idea() and "
            "execute_archive_idea() in _flow_handlers.py. Updated "
            "_dispatch.py with _ARCHIVE_ACTIONS routing."
        ),
    ),
    CodexEntry(
        "0.8.1",
        date(2026, 3, 4),
        (
            "PRD critique performance optimisation — (1) Dedicated "
            "lightweight critic agent using basic/flash model tier "
            "(GEMINI_CRITIC_MODEL) with no tools, separate from the "
            "research-tier PM drafter. (2) Critique and refine Crews "
            "now use separate agent lists so the critic never loads "
            "heavy tools. (3) Knowledge sources cached at module level "
            "to avoid redundant embedding API calls on every agent "
            "creation (clear_knowledge_cache() to reset). New env vars: "
            "GEMINI_CRITIC_MODEL, CRITIC_LLM_TIMEOUT."
        ),
    ),
    CodexEntry(
        "0.8.2",
        date(2026, 3, 4),
        (
            "Interactive exec summary completion gate — The interactive "
            "Slack flow now pauses after executive summary iteration to "
            "let the user review and choose Continue/Stop before section "
            "drafting begins. Added make_slack_exec_summary_completion_callback "
            "to interactive_handlers/_callbacks.py. Wired "
            "executive_summary_callback in _flow_runner.py. Added "
            "ExecutiveSummaryCompleted handler so stopping after exec "
            "summary marks the flow as completed (not failed)."
        ),
    ),
    CodexEntry(
        "0.8.3",
        date(2026, 3, 4),
        (
            "Prevent incomplete PRDs from polluting output/prds/ — "
            "(1) save_progress() now writes to output/prds/_drafts/ "
            "instead of output/prds/ so partial/paused progress saves "
            "are structurally separated from completed PRDs. "
            "(2) _discover_publishable_prds() disk scan now skips files "
            "inside _drafts/ and files with '(In Progress)' header to "
            "prevent incomplete documents from being published to "
            "Confluence on startup. "
            "(3) Removed PRDFileWriteTool from the Product Manager agent "
            "toolkit (5 tools instead of 6) — file writing is handled "
            "programmatically by finalize() and save_progress() to "
            "prevent LLM-autonomous uncontrolled file creation."
        ),
    ),
    CodexEntry(
        "0.8.4",
        date(2026, 3, 4),
        (
            "Fix original idea not persisted in workingIdeas — "
            "save_slack_context() and save_project_ref() now accept "
            "an optional idea= keyword argument and write the original "
            "idea text on both $set and $setOnInsert. All callers "
            "(Slack router, interactive flow runner, CLI, resume "
            "handler) updated to pass the idea. This ensures the "
            "'idea' field is populated from the very first upsert, "
            "fixing listing showing 'Untitled' and rescan losing the "
            "original idea text."
        ),
    ),
    CodexEntry(
        "0.8.5",
        date(2026, 3, 4),
        (
            "Requirements approval gate for auto-approve Slack flows — "
            "the requirements breakdown stage now pauses for user "
            "approval in non-interactive (auto-approve) flows, matching "
            "the existing behaviour in interactive mode. Added "
            "make_requirements_approval_gate() and "
            "resolve_requirements_approval() in _flow_handlers.py, "
            "wired into run_prd_flow(), resume_prd_flow(), "
            "_run_slack_prd_flow(), and handle_resume_prd(). The "
            "interactions router dispatches requirements_approve and "
            "requirements_cancel button clicks to the non-interactive "
            "gate before falling through to the interactive handler. "
            "Reuses existing requirements_approval_blocks from "
            "_flow_blocks.py. Gate waits 10 minutes for user response "
            "then auto-approves on timeout."
        ),
    ),
    CodexEntry(
        "0.8.6",
        date(2026, 3, 4),
        (
            "Fix exec summary callbacks lost by CrewAI asyncio.to_thread — "
            "added module-level _callback_registry in prd_flow.py as a "
            "safety net for callbacks that CrewAI's Flow.kickoff() loses "
            "when running @start() methods in thread pool workers. "
            "PRDFlow._resolve_callback() checks the instance attribute "
            "first, then falls back to the registry. run_prd_flow() and "
            "resume_prd_flow() now call register_callbacks() before "
            "kickoff and cleanup_callbacks() in finally blocks. "
            "Diagnostic logging added at flow start, service callback "
            "assignment, and registry recovery events."
        ),
    ),
    CodexEntry(
        "0.8.7",
        date(2026, 3, 4),
        (
            "Fix in-progress ideas invisible to 'list ideas' (3rd fix) — "
            "Root cause: find_ideas_by_project() required exact project_id "
            "match; if save_project_ref() failed silently or was skipped, "
            "the idea became invisible. Fix: (1) find_ideas_by_project() "
            "now uses a single $or MongoDB query that matches ideas by "
            "project_id OR by slack_channel (for orphans without "
            "project_id), eliminating the dependency on the fragile "
            "crew-jobs cross-collection lookup. Channel-matched orphans "
            "get project_id backfilled inline. (2) _backfill_orphaned_ideas "
            "enhanced to check the document's own slack_channel before "
            "falling back to crew_jobs lookup. Extracted _do_backfill() "
            "helper. (3) run_interactive_slack_flow now calls "
            "save_slack_context() early (was missing) so slack_channel is "
            "always available for channel-based queries. 7 new regression "
            "tests covering all 'invisible idea' scenarios."
        ),
    ),
    CodexEntry(
        "0.8.8",
        date(2026, 3, 4),
        (
            "Fix MongoDB upsert conflict in save_slack_context() and "
            "save_project_ref() — When the 'idea' parameter was provided, "
            "the field was placed in both $set and $setOnInsert operators, "
            "causing MongoDB to reject the upsert with 'Updating the path "
            "'idea' would create a conflict at 'idea''. This prevented "
            "the workingIdeas document from being created on the first "
            "save call, leaving newly created ideas invisible. Fix: "
            "idea is now only in $set (which applies to both insert and "
            "update operations)."
        ),
    ),
    CodexEntry(
        "0.9.0",
        date(2026, 3, 4),
        (
            "Interactive mode by default + orchestrator progress "
            "notifications. (1) Create PRD flows now default to "
            "interactive/step-by-step mode with approval gates at "
            "each stage (idea refinement, requirements breakdown, "
            "executive summary). Users must explicitly say 'auto', "
            "'fast', or 'quick' to run without approval checkpoints. "
            "(2) AgentOrchestrator now accepts a progress_callback "
            "and fires pipeline_stage_start, pipeline_stage_complete, "
            "and pipeline_stage_skipped events during the pre-PRD "
            "pipeline (idea refinement → requirements breakdown). "
            "build_default_pipeline() wires the flow's progress "
            "callback so Slack users see heartbeat messages like "
            "'Starting Idea Refinement...', 'Idea Refinement complete "
            "(3 iterations)' during stages that were previously "
            "silent. 24 new tests covering both features."
        ),
    ),
    CodexEntry(
        "0.9.1",
        date(2026, 3, 4),
        (
            "Idea refinement now saves as 'refine_idea' pipeline key. "
            "Changed idea_refiner agent, CLI manual refinement, and "
            "components CLI to use save_pipeline_step with "
            "pipeline_key='refine_idea' instead of save_executive_summary. "
            "Updated restore logic in _cli_state, components/resume, and "
            "apis/prd/service to read from the refine_idea array in MongoDB. "
            "Separates idea refinement data from executive summary data."
        ),
    ),
    CodexEntry(
        "0.9.2",
        date(2026, 3, 4),
        (
            "503 model-busy errors now pause immediately instead of "
            "retrying with backoff. Added ModelBusyError (subclass of "
            "LLMError) raised on 503 / model-overloaded / service-unavailable "
            "patterns. The flow pauses at once so the 5-minute periodic "
            "auto-resume scheduler can retry when load subsides, avoiding "
            "wasted resources on busy-wait retries."
        ),
    ),
    CodexEntry(
        "0.9.3",
        date(2026, 3, 5),
        (
            "Confluence parent page ID removed from project setup wizard. "
            "The 3-step setup (space key, Jira key, parent ID) is now 2 "
            "steps. Parent ID is still used if available in project config "
            "or CONFLUENCE_PARENT_ID env var — pages are simply created at "
            "the space root when unset."
        ),
    ),
    CodexEntry(
        "0.9.4",
        date(2026, 3, 5),
        (
            "Confluence parent page ID removed from all LLM-facing surfaces. "
            "Intent classification prompts (Gemini/OpenAI) no longer mention "
            "confluence_parent_id as a response field or update_config entity. "
            "Next-step prediction context no longer includes has_confluence_parent "
            "or confluence_parent_id. The Slack orchestrator will no longer ask "
            "users to provide a parent page ID before publishing."
        ),
    ),
    CodexEntry(
        "0.9.5",
        date(2026, 3, 5),
        (
            "Jira skeleton next-step hint after publishing. "
            "handle_publish_intent now suggests 'create jira tickets' "
            "when Confluence was published but no Jira tickets were "
            "created, guiding users to the phased Jira skeleton flow "
            "(Epics & User Stories review/approval). PRD result tool "
            "updated with improved Jira hint wording. Next-step "
            "prediction adds create_jira_skeleton category."
        ),
    ),
    CodexEntry(
        "0.9.6",
        date(2026, 3, 5),
        (
            "Fix KeyError 'approved_skeleton' in startup delivery. "
            "build_startup_delivery_crew was missing the approved_skeleton "
            "format parameter when interpolating the create_jira_stories_task "
            "description, causing Jira ticket creation to fail on server "
            "restart for pending deliveries. Now passes a fallback instruction "
            "for the agent to derive the structure from functional requirements."
        ),
    ),
    CodexEntry(
        "0.9.7",
        date(2026, 3, 5),
        (
            "Fix Confluence data persisted to wrong collection. "
            "save_confluence_url was writing confluence_url, "
            "confluence_page_id, and confluence_published_at to "
            "workingIdeas instead of productRequirements. Removed "
            "save_confluence_url entirely; all call sites now use "
            "upsert_delivery_record in the productRequirements "
            "collection. Refactored find_completed_without_confluence "
            "to cross-reference productRequirements.confluence_published "
            "instead of checking workingIdeas.confluence_url. Added "
            "migration script scripts/migrate_confluence_to_product_"
            "requirements.py to move existing data."
        ),
    ),
    CodexEntry(
        "0.9.8",
        date(2026, 3, 5),
        (
            "Standardise productRequirements status values. "
            "Replaced pending/partial/completed with new/inprogress/"
            "completed. 'new' = first created, 'inprogress' = being "
            "updated (Confluence published or Jira in progress), "
            "'completed' = all Jira tickets including sub-tasks done. "
            "Updated _compute_status, find_pending_delivery query, "
            "API models, OpenAPI docs, and migrated existing DB records."
        ),
    ),
    CodexEntry(
        "0.9.9",
        date(2026, 3, 4),
        (
            "Fix 503 retry resume — ModelBusyError (503) now propagates "
            "from section critique/refine and executive summary loops "
            "instead of being swallowed by the generic except-Exception "
            "handler that force-approves sections. This allows the flow "
            "to pause cleanly on 503 and resume at the exact section "
            "and iteration where it left off, rather than force-approving "
            "with incomplete content. Updated _section_loop.py and "
            "_executive_summary.py to catch (BillingError, ModelBusyError) "
            "before the generic Exception handler."
        ),
    ),
    CodexEntry(
        "0.9.10",
        date(2026, 3, 5),
        (
            "Fix idea list: exclude completed/archived ideas and fix "
            "sections_done count — find_ideas_by_project now uses $nin "
            "to exclude both 'archived' and 'completed' statuses so "
            "only actionable ideas are shown. _doc_to_idea_dict now "
            "counts the top-level executive_summary as a section "
            "(was previously only counting keys under the section "
            "object, giving 9/10 for fully drafted ideas) and forces "
            "sections_done=total_sections when status is 'completed'."
        ),
    ),
    CodexEntry(
        "0.9.11",
        date(2026, 3, 5),
        (
            "Fix autonomous Jira creation bypassing user approval — "
            "the startup delivery scheduler was creating Jira tickets "
            "(Epics, Stories, Sub-tasks) without approval when the "
            "interactive phased flow owned the Jira lifecycle. Added "
            "save_jira_phase() to MongoDB working_ideas to persist the "
            "jira_phase field across server restarts. All phase "
            "transitions in _jira.py and _finalization.py now persist "
            "jira_phase. _discover_pending_deliveries() now checks "
            "jira_phase and skips items managed by the interactive "
            "flow, preventing the scheduler from creating duplicate "
            "or unapproved Jira tickets."
        ),
    ),
    CodexEntry(
        "0.9.12",
        date(2026, 3, 5),
        (
            "Add 'list products' intent — new Slack intent to list all "
            "completed (non-archived) ideas with delivery manager "
            "interaction buttons. Users can resume Confluence publish, "
            "review Jira skeleton, publish Jira epics & stories, and "
            "publish Jira sub-tasks directly from the product list. "
            "Includes new MongoDB query find_completed_ideas_by_project, "
            "Block Kit builder with contextual delivery buttons, "
            "interactive button dispatch handler, dual-layer intent "
            "classification (LLM + phrase fallback), and full event "
            "routing wiring."
        ),
    ),
    CodexEntry(
        "0.9.13",
        date(2026, 3, 5),
        (
            "Fix 3 product list issues — (1) Confluence URL in view "
            "details now falls back to the productRequirements delivery "
            "record when the workingIdeas doc lacks the URL. "
            "(2) Jira Ticketing status uses differentiated icons: "
            ":arrow_forward: for not started, :arrows_counterclockwise: "
            "for in-progress phases, :white_check_mark: only when "
            "completed; label changed from 'Jira' to 'Jira Ticketing'. "
            "(3) View details now shows ticket type counts "
            "(e.g. '2 Epics, 3 Stories, 1 Sub-task') instead of "
            "listing individual ticket keys."
        ),
    ),
    CodexEntry(
        "0.9.14",
        date(2026, 3, 5),
        (
            "Product list: only completed delivery steps show static "
            ":white_check_mark: status text; incomplete steps appear "
            "solely as interactive buttons (Start/Resume). Confluence "
            "and Jira status removed from section text when not yet "
            "completed — users click the button to take action instead "
            "of seeing a misleading status indicator."
        ),
    ),    CodexEntry(
        "0.9.15",
        date(2026, 3, 5),
        (
            "Fix 3 product list display issues \u2014 (1) View details now "
            "checks confluence_published flag when URL is missing, showing "
            "'Published (URL not available)' instead of 'Not published'. "
            "(2) Jira sub-task creation now stores type as 'Sub-task' "
            "instead of 'Task'. (3) View details normalises legacy ticket "
            "types: 'Task'\u2192'Sub-task', 'unknown'\u2192'Sub-task', ensuring "
            "correct breakdown counts."
        ),
    ),
    CodexEntry(
        "0.9.16",
        date(2026, 3, 5),
        (
            "Fix Confluence URL display with native Slack URL button "
            "(always clickable regardless of mrkdwn rendering). Fix Jira "
            "ticket type resolution: replace blind 'unknown'\u2192'Sub-task' "
            "normalisation with live Jira API lookup via "
            "search_jira_issues, persisting corrected types back to "
            "MongoDB for future queries."
        ),
    ),
    CodexEntry(
        "0.10.0",
        date(2026, 3, 5),
        (
            "Jira phased-approval overhaul: (1) Skeleton reject regenerates "
            "instead of skipping Jira. (2) Skeleton approve immediately "
            "creates Epics & Stories instead of requiring another button. "
            "(3) New sub-task review step — after sub-tasks are generated, "
            "user reviews and can approve or regenerate before finalising. "
            "New action IDs: jira_subtask_approve, jira_subtask_reject. "
            "New jira_phase value: subtasks_pending. "
            "(4) Fixed jira_phase=None from MongoDB hiding skeleton button."
        ),
    ),
    CodexEntry(
        "0.10.1",
        date(2026, 3, 5),
        (
            "Fix missing Jira skeleton button in product list: "
            "smart jira_completed check — don't trust jira_completed=True "
            "when jira_tickets is empty and jira_phase != subtasks_done "
            "(scheduler race condition). Fallback button for unrecognised "
            "jira_phase values shows Restart Jira Skeleton."
        ),
    ),
    CodexEntry(
        "0.10.2",
        date(2026, 3, 5),
        (
            "Migrate Jira REST API from deprecated v2 to v3: search uses "
            "/rest/api/3/search/jql (fixes 410 Gone that broke duplicate "
            "detection, causing massive ticket duplication on every server "
            "restart). Issue creation and linking also migrated to v3. "
            "Fix empty response body crash in _jira_request for link "
            "creation 201 responses (return {} instead of JSON parse error)."
        ),
    ),
    CodexEntry(
        "0.11.0",
        date(2026, 3, 5),
        (
            "Fix autonomous Jira delivery re-creating tickets from scratch "
            "on every server restart: after successful autonomous Jira "
            "completion, set jira_phase='subtasks_done' on workingIdeas "
            "document so _discover_pending_deliveries skips the run on "
            "next restart. Applied to components/startup.py, _cli_startup.py, "
            "and flows/_finalization.py. Also auto-populate Jira ticket URL "
            "(ATLASSIAN_BASE_URL/browse/KEY) in append_jira_ticket when not "
            "explicitly provided — all callers now store full browse URLs "
            "in the productRequirements.jira_tickets array."
        ),
    ),
    CodexEntry(
        "0.11.1",
        date(2026, 3, 5),
        (
            "Fix 'update knowledge' intent misclassification — added "
            "'knowledge' synonyms to _CONFIGURE_MEMORY_PHRASES in "
            "_intent_phrases.py and to LLM system prompts in "
            "gemini_chat.py / openai_chat.py so that phrases like "
            "'update knowledge', 'project knowledge', 'configure "
            "knowledge', etc. are correctly classified as "
            "configure_memory intent (same as 'update memory')."
        ),
    ),
    CodexEntry(
        "0.11.2",
        date(2026, 3, 5),
        (
            "Fix PRD section generation pausing prematurely on 429 "
            "RESOURCE_EXHAUSTED rate-limit errors. Separated "
            "_RATE_LIMIT_PATTERNS from _MODEL_BUSY_PATTERNS in retry.py "
            "so that rate-limit errors get 5 retries with 30s-base "
            "exponential backoff (30s, 60s, 120s, 240s, 480s) before "
            "pausing the flow, instead of pausing immediately. Also "
            "refactored retry loop from for-loop to while-loop so "
            "rate-limit retries don't consume the normal retry budget. "
            "Updated preflight.py Jira health check from v2 to v3 API."
        ),
    ),
    CodexEntry(
        "0.12.0",
        date(2026, 3, 5),
        (
            "Fix Jira API v3 400 errors — ticket descriptions now use "
            "Atlassian Document Format (ADF) instead of plain wiki "
            "markup strings. Added _markdown_to_adf() converter in "
            "_helpers.py that transforms Markdown to ADF with support "
            "for headings, bold, inline code, fenced code blocks, "
            "bullet/ordered lists, links, horizontal rules, and "
            "multi-line paragraphs. Updated create_jira_issue() in "
            "_operations.py to emit ADF for the description field. "
            "Also fixed a pre-existing flaky retry test caused by "
            "background thread time.sleep() interception."
        ),
    ),
    CodexEntry(
        "0.12.1",
        date(2026, 3, 5),
        (
            "Fix Jira ticket persistence to productRequirements. "
            "Root cause: JiraCreateIssueTool._run() created tickets via "
            "REST API but never persisted them to MongoDB — all "
            "persistence relied on fragile regex parsing of crew output "
            "text. Additionally, the phased Jira path never called "
            "upsert_delivery_record(jira_completed=True) after all "
            "phases completed, leaving the delivery status incomplete. "
            "Fix: (1) Tool now calls append_jira_ticket() immediately "
            "after successful Jira API creation when run_id is provided. "
            "(2) _run_phased_post_completion() now calls "
            "upsert_delivery_record(jira_completed=True) after all 3 "
            "phases complete. (3) Replaced silent except:pass in "
            "_jira.py stage persistence with proper logger.warning() "
            "calls for observability."
        ),
    ),
    CodexEntry(
        "0.12.2",
        date(2026, 3, 6),
        (
            "Fix interactive agent-mode flow skipping executive summary "
            "review gate. Root cause: run_interactive_slack_flow() set "
            "callbacks directly on the PRDFlow instance but never called "
            "register_callbacks() — CrewAI's asyncio.to_thread lost the "
            "instance attributes, so _resolve_callback() returned None "
            "and the flow auto-continued without pausing. Fix: (1) "
            "Register all callbacks in the module-level registry in "
            "_flow_runner.py so they survive asyncio.to_thread. (2) "
            "Clean up registered callbacks in the finally block. (3) "
            "Use _resolve_callback() for Jira callbacks in "
            "_finalization.py (same bug pattern — direct attribute "
            "access subject to asyncio.to_thread loss)."
        ),
    ),
    CodexEntry(
        version="0.12.3",
        date=date(2026, 3, 5),
        summary=(
            "Fix flow ordering: requirements breakdown now runs after "
            "executive summary approval. Removed requirements_breakdown "
            "from build_default_pipeline() — pipeline now only contains "
            "idea_refinement. Added requirements breakdown as a direct "
            "stage call inside generate_sections() after the exec "
            "summary approval gate. Removed stale exec-summary-iterations "
            "auto-skip from _requires_approval() in _requirements.py."
        ),
    ),
    CodexEntry(
        version="0.12.4",
        date=date(2026, 3, 6),
        summary=(
            "Acknowledge user feedback on executive summary. When a "
            "user replies to the exec summary with feedback in Slack, "
            "the bot now posts a confirmation message before starting "
            "the next iteration. Applied to both interactive-mode "
            "callback (_callbacks.py) and auto-mode gate "
            "(_flow_handlers.py)."
        ),
    ),
    CodexEntry(
        version="0.12.5",
        date=date(2026, 3, 7),
        summary=(
            "Fix thread_broadcast messages being silently dropped. "
            "Slack sends subtype=thread_broadcast when a user replies "
            "to a thread and also posts to the channel. The blanket "
            "subtype filter in events_router.py and "
            "_event_handlers.py dropped these messages, causing "
            "commands like 'list of ideas' to produce no response "
            "when sent as a broadcast reply. Fix: allow "
            "thread_broadcast through while still filtering other "
            "subtypes (message_changed, bot_message, etc.)."
        ),
    ),
    CodexEntry(
        version="0.13.0",
        date=date(2026, 3, 7),
        summary=(
            "Remove unused web research tools from Product Manager agent. "
            "SerperDevTool (Google search), ScrapeWebsiteTool, and "
            "WebsiteSearchTool were never invoked during PRD flows — the "
            "LLM generates content from the user's idea and knowledge "
            "sources without internet search. Removed: tool factory "
            "modules (search_tool.py, scrape_tool.py, "
            "website_search_tool.py), SERPER_API_KEY preflight check, "
            "and .env entry. Agent toolkit reduced from 5 to 2 tools "
            "(FileReadTool + DirectoryReadTool), saving LLM context tokens."
        ),
    ),
    CodexEntry(
        version="0.13.1",
        date=date(2026, 3, 7),
        summary=(
            "Fix hallucinated Confluence URLs in Jira tickets. The LLM "
            "frequently invents fake URLs like "
            "'https://confluence.internal/pages/...' or "
            "'https://confluence.example.com/display/...' instead of "
            "using the real Confluence URL provided in the task "
            "description. Fix: the JiraCreateIssueTool now resolves the "
            "authoritative Confluence URL from MongoDB (set by the "
            "actual Confluence publish step) before creating tickets, "
            "ignoring whatever the LLM passes. Added "
            "_resolve_confluence_url() helper with 7 tests."
        ),
    ),
    CodexEntry(
        version="0.13.2",
        date=date(2026, 3, 8),
        summary=(
            "Fix TokenManager and CrewJobs resume bugs from log review. "
            "(1) Static xoxb- tokens (no refresh_token) were wrongly "
            "treated as expired on every call, causing 61 unnecessary "
            "MongoDB round-trips and warning log entries per session. "
            "Fix: detect non-rotating tokens and cache with 24h TTL. "
            "(2) Fallback cache TTL was immediately stale because "
            "time.time()+300 minus _REFRESH_BUFFER_SECONDS(300) = now, "
            "so _needs_refresh always returned True. Fix: add buffer to "
            "the TTL so entries survive the subtraction. "
            "(3) resume_prd_flow silently failed to track jobs when no "
            "crewJobs document existed — reactivate_job returned False "
            "and update_job_started also failed. Fix: fall back to "
            "create_job when reactivate_job returns False."
        ),
    ),
    CodexEntry(
        version="0.14.0",
        date=date(2026, 3, 8),
        summary=(
            "Delivery action buttons & create_jira intent. "
            "(1) Replaced text-based 'Say *publish*' / 'Say *create jira "
            "tickets*' prompts with interactive Slack Block Kit buttons "
            "(delivery_publish, delivery_create_jira) at PRD completion, "
            "resume completion, post-publish, and check-publish status. "
            "New module: blocks/_delivery_action_blocks.py with "
            "delivery_next_step_blocks(), jira_only_blocks(), "
            "publish_only_blocks(). New handler: interactions_router/"
            "_delivery_action_handler.py for button click dispatch. "
            "(2) Added dedicated 'create_jira' intent to both Gemini "
            "and OpenAI LLM classifiers so 'create jira' is no longer "
            "misclassified as 'publish'. Narrowed publish intent to "
            "Confluence-only. Added _CREATE_JIRA_PHRASES phrase fallback, "
            "handle_create_jira_intent() handler, handler proxy, "
            "events_router alias, message handler dispatch, and "
            "_next_step_handler support for create_jira_skeleton. "
            "20 new tests (1996 total)."
        ),
    ),
    CodexEntry(
        version="0.14.1",
        date=date(2026, 3, 7),
        summary=(
            "Fix Jira skeleton generation failing for completed PRDs. "
            "restore_prd_state() only searched find_unfinalized() which "
            "excludes status='completed' documents. When a user clicked "
            "'Create Jira Tickets' on a completed PRD the function raised "
            "ValueError('Run … not found in unfinalized working ideas'). "
            "Fix: fall back to find_run_any_status() so completed runs "
            "are also loadable. Added test_restore_prd_state_completed_run "
            "(1997 tests total)."
        ),
    ),
    CodexEntry(
        version="0.14.2",
        date=date(2026, 3, 8),
        summary=(
            "Fix Flow.state read-only property crash in _run_jira_phase(). "
            "The v0.14.1 fix unblocked restore_prd_state() for completed runs "
            "but exposed a second bug: 'flow.state = state' fails because "
            "CrewAI Flow.state is a read-only property (no setter) and "
            "restore_prd_state() returns a 6-tuple, not a PRDState. "
            "Fix: unpack the tuple and apply fields individually via attribute "
            "access (matching resume_prd_flow pattern). Also populate "
            "final_prd via draft.assemble() and confluence_url from the "
            "MongoDB document so _check_jira_prerequisites() passes. "
            "Added disk-file fallback: when MongoDB sections are empty "
            "(older completed runs), read PRD from the on-disk output file. "
            "Made Confluence URL optional for interactive Jira flows — "
            "added require_confluence parameter to all Jira stage builders. "
            "Added 9 tests in TestRunJiraPhaseStateReconstruction. "
            "One-time retry script: scripts/retry_jira_skeleton.py."
        ),
    ),
    CodexEntry(
        version="0.14.3",
        date=date(2026, 3, 8),
        summary=(
            "Fix 'list ideas' showing 'No ideas found' when completed "
            "products exist. Root cause: handle_list_ideas() only called "
            "find_ideas_by_project() which excludes status=completed. "
            "Users with completed PRDs needing Jira delivery saw nothing. "
            "Fix: handle_list_ideas() now also calls "
            "find_completed_ideas_by_project() and renders product blocks "
            "with delivery action buttons (Confluence/Jira) alongside "
            "in-progress idea blocks. Shows a unified view so users can "
            "resume where they left off from a single 'list ideas' command."
        ),
    ),
    CodexEntry(
        version="0.14.4",
        date=date(2026, 3, 8),
        summary=(
            "Fix product list showing 'Jira Ticketing complete' when the "
            "interactive Jira flow is still in progress. Root cause: "
            "_doc_to_product_dict() only checked for empty jira_tickets "
            "but the delivery record had 45 stale tickets from a prior "
            "auto-delivery run while jira_phase was 'skeleton_pending'. "
            "Fix: jira_phase on the working-idea document is now the "
            "authoritative source — any active phase (not 'subtasks_done') "
            "overrides the delivery record's jira_completed flag. "
            "Product list blocks now display the current Jira phase as "
            "a status indicator (e.g. ':hourglass: Jira: Skeleton "
            "awaiting approval') so users see exactly where to resume."
        ),
    ),
    CodexEntry(
        version="0.14.5",
        date=date(2026, 3, 8),
        summary=(
            "Persist Jira skeleton to MongoDB and show existing skeleton "
            "when user resumes. Root cause: the skeleton was only stored "
            "in-memory on flow.state.jira_skeleton and lost after the "
            "background thread ended. When the user clicked 'Resume Jira "
            "Skeleton' on a skeleton_pending product, the system "
            "regenerated from scratch instead of showing the existing one. "
            "Fix: (1) New save_jira_skeleton()/get_jira_skeleton() in "
            "MongoDB _status.py persist the skeleton text alongside "
            "jira_phase. (2) build_jira_skeleton_stage._apply() now "
            "calls save_jira_skeleton() on generation. (3) "
            "_handle_jira_skeleton() checks jira_phase first — when "
            "'skeleton_pending', loads and shows the existing skeleton "
            "with Approve/Regenerate buttons without re-running the LLM."
        ),
    ),
    CodexEntry(
        version="0.14.6",
        date=date(2026, 3, 8),
        summary=(
            "Fix product list UX for skeleton_pending phase. "
            "(1) Button label changed from 'Resume Jira Skeleton' to "
            "'Review Jira Skeleton' with primary style when jira_phase "
            "is skeleton_pending — clearly indicates skeleton exists and "
            "needs approval rather than regeneration. "
            "(2) Split the jira_phase '' and 'skeleton_pending' branches "
            "in _product_list_blocks.py — '' shows 'Start Jira Skeleton' "
            "while 'skeleton_pending' shows 'Review Jira Skeleton'. "
            "(3) Added warning log when skeleton_pending but no skeleton "
            "in MongoDB — explains why regeneration occurred for data "
            "created before v0.14.5 persistence was added."
        ),
    ),
    CodexEntry(
        "0.15.0",
        date(2026, 3, 8),
        (
            "MongoDB collection & index bootstrap on startup. "
            "New ensure_collections() in scripts/setup_mongodb.py creates "
            "all 8 collections (agentInteraction, crewJobs, workingIdeas, "
            "productRequirements, projectConfig, projectMemory, userSession, "
            "slackOAuth) and their indexes on server startup (step 0 in "
            "_lifespan). Indexes cover primary keys (unique), common query "
            "patterns, and sort fields. Fix pre-existing NameError on "
            "shutdown — threading.excepthook safety net now installed and "
            "restored correctly. Developer setup script (scripts/dev_setup.sh) "
            "for one-command project bootstrap. 9 new tests."
        ),
    ),
    CodexEntry(
        "0.15.1",
        date(2026, 3, 8),
        (
            "Fix Slack bot not responding — env var token fallback. "
            "get_valid_token() now falls back to SLACK_BOT_TOKEN / "
            "SLACK_ACCESS_TOKEN env vars when no OAuth records exist in "
            "the slackOAuth MongoDB collection. This enables dev setups "
            "without completing the full OAuth install flow. Added startup "
            "Slack token validation check (step 0b in _lifespan) that logs "
            "a clear warning when no token is available. Updated .env.example "
            "with SLACK_BOT_TOKEN documentation. 6 new tests."
        ),
    ),
    CodexEntry(
        "0.15.2",
        date(2026, 3, 8),
        (
            "Fix 'configure memory' intent not recognised — phrase override. "
            "When the user typed 'configure memory' in Slack, the LLM "
            "misclassified it as list_ideas. The list_ideas dispatch handler "
            "matched first, bypassing the configure_memory handler. Added "
            "configure_memory and update_config to the phrase-override "
            "section in _message_handler.py so keyword detection corrects "
            "LLM misclassification before any dispatch check runs. "
            "6 new tests."
        ),
    ),
    CodexEntry(
        "0.15.3",
        date(2026, 3, 8),
        (
            "Fix 'create idea' not recognised as idea iteration intent. "
            "The user typed 'create idea' in Slack but the LLM misclassified "
            "it as configure_memory, because 'create idea' was missing from "
            "_IDEA_PHRASES. Added 'create idea', 'create an idea', "
            "'create new idea', and 'create a new idea' to the phrase list. "
            "2 new tests."
        ),
    ),
    CodexEntry(
        "0.15.4",
        date(2026, 3, 8),
        (
            "Fix thread-reply intent regression — pending_memory state "
            "consumed user commands (e.g. 'create idea') as memory entries "
            "instead of routing to intent classification. Three fixes: "
            "(1) removed configure_memory/update_config from top-level "
            "phrase overrides — LLM is the primary classifier for those "
            "ambiguous intents; (2) added guard on list_ideas dispatch so "
            "LLM misclassification doesn't catch memory-phrase text; "
            "(3) added phrase-based command detection in pending_memory "
            "handler — cancels memory mode when user types a recognised "
            "command. 6 new regression tests."
        ),
    ),
    CodexEntry(
        "0.15.5",
        date(2026, 3, 8),
        (
            "Improve LLM error handling for HTTP 500 and transient errors. "
            "(1) retry.py: added _SERVER_ERROR_PATTERNS for explicit 500/"
            "502/504 classification — these now get clear log messages and "
            "proper retry with exponential backoff instead of falling "
            "through to the generic catch-all. "
            "(2) gemini_chat.py: increased retries from 2 to 3, added "
            "exponential backoff delay (1s, 2s, 4s) between attempts, "
            "non-retryable HTTP status codes (4xx except 429) now fail "
            "immediately instead of wasting a retry. "
            "(3) openai_chat.py: added retry logic (was zero retries), "
            "3 attempts with backoff, retryable status codes (429, 500, "
            "502, 503, 504), error response body now logged for "
            "diagnostics. 11 new tests."
        ),
    ),
    CodexEntry(
        "0.15.6",
        date(2026, 3, 9),
        (
            "Fix shutdown error handling — 'cannot schedule new futures "
            "after shutdown' no longer wastes 60+ seconds on futile "
            "retries. (1) retry.py: added ShutdownError class and "
            "_SHUTDOWN_PATTERNS — detected immediately with zero retries. "
            "(2) _section_loop.py: ShutdownError re-raises instead of "
            "force-approving sections with incomplete content. "
            "(3) service.py: ShutdownError caught in both run_prd_flow "
            "and resume_prd_flow — pauses flow for auto-resume on next "
            "server start. (4) apis/__init__.py: global handler returns "
            "HTTP 503 for ShutdownError. 5 new tests."
        ),
    ),
    CodexEntry(
        "0.15.8",
        date(2026, 3, 9),
        (
            "Critical Jira approval gate fix — 5 autonomous code paths "
            "could create Jira tickets without user approval. "
            "(1) _finalization.py: _run_auto_post_completion now uses "
            "confluence_only=True. (2) _startup_delivery.py: added "
            "confluence_only parameter, gating jira_needed. "
            "(3) _cli_startup.py & components/startup.py: callers pass "
            "confluence_only=True. (4) _flow_handlers.py: "
            "execute_restart_prd passes interactive=True to "
            "kick_off_prd_flow. (5) 23 regression tests in "
            "tests/flows/test_jira_approval_gate.py covering every "
            "delivery path. CODEX.md and Obsidian updated with "
            "Jira approval gate invariant documentation."
        ),
    ),
    CodexEntry(
        "0.15.9",
        date(2026, 3, 9),
        (
            "Fix Confluence publish notification and Jira next-step flow. "
            "(1) _product_list_handler._handle_confluence_publish now "
            "passes a progress_callback to build_post_completion_crew so "
            "users see heartbeat updates during the 2-4 min crew run. "
            "(2) After Confluence publish completes, the handler now "
            "offers a 'Create Jira Skeleton' button when Jira "
            "credentials are configured. "
            "(3) Button label corrected from 'Create Jira Tickets' to "
            "'Create Jira Skeleton' across _delivery_action_blocks.py, "
            "_dispatch.py, _flow_handlers.py, and "
            "_product_list_handler.py — the action always triggers "
            "skeleton generation (Phase 1 of phased Jira workflow). "
            "4 regression tests added."
        ),
    ),
    CodexEntry(
        "0.15.10",
        date(2026, 3, 9),
        (
            "Fix delivery state reset: PublishScheduler scan was "
            "overwriting confluence_published with False on every sweep. "
            "Root cause: _discover_pending_deliveries() read "
            "confluence_url from the workingIdeas doc (empty after "
            "save_confluence_url migration) and used it to set "
            "confluence_published — resetting the delivery record. "
            "(1) subtasks_done branch now only sets jira_completed, "
            "preserving existing confluence state. "
            "(2) 'fully done' branch reads confluence_url from the "
            "delivery record first, falling back to workingIdeas. "
            "(3) Item dict confluence_url sourced from delivery record. "
            "3 regression tests added (2105 total)."
        ),
    ),
    CodexEntry(
        "0.15.11",
        date(2026, 3, 9),
        (
            "Remove autonomous Jira detection from all delivery paths. "
            "persist_post_completion(), _cli_startup, and components/startup "
            "no longer detect Jira keywords or set jira_phase / "
            "jira_completed — these fields are now exclusively managed by "
            "the interactive phased flow (orchestrator/_jira.py), enforcing "
            "the approval gate invariant (v0.15.8). "
            "Fixed stale jira_phase='subtasks_done' data from pre-approval "
            "autonomous runs via one-time fix script. "
            "8 tests rewritten to assert Jira state is never set on "
            "autonomous paths."
        ),
    ),
    CodexEntry(
        "0.15.12",
        date(2026, 3, 10),
        (
            "Persist Jira Epics & Stories output to MongoDB for crash "
            "resilience. Root cause: jira_epics_stories_output was only "
            "stored in-memory on flow.state and lost on server restart. "
            "When resuming from epics_stories_done phase, the Sub-tasks "
            "stage skipped because the output was empty. "
            "Fix: (1) New save_jira_epics_stories_output() / "
            "get_jira_epics_stories_output() in MongoDB _status.py. "
            "(2) build_jira_epics_stories_stage._apply() now persists "
            "the crew output alongside jira_phase. "
            "(3) _run_jira_phase() restores jira_skeleton and "
            "jira_epics_stories_output from the MongoDB document so "
            "all 3 Jira phases can resume after crash. "
            "14 new tests (2122 total)."
        ),
    ),
    CodexEntry(
        "0.15.13",
        date(2026, 3, 10),
        (
            "Eliminate 'unknown' Jira ticket types. Root cause: the "
            "JiraCreateIssueTool persisted the raw issue_type from the "
            "LLM agent before the orchestrator could write the correct "
            "hardcoded type — and since append_jira_ticket() deduplicates "
            "by key, the first (wrong) write won. "
            "Fix: _normalise_issue_type() in _tool.py maps all LLM "
            "variants ('task', 'Sub-Task', 'subtask', '', 'unknown') to "
            "canonical Jira types ('Epic', 'Story', 'Sub-task', 'Bug'). "
            "Context-aware: when parent_key is set, unrecognised types "
            "default to 'Sub-task' instead of 'Story'. "
            "18 new tests (2140 total)."
        ),
    ),
    CodexEntry(
        "0.15.14",
        date(2026, 3, 10),
        (
            "Add archive button to the product list. Completed ideas "
            "now show a ':file_folder: Archive' button alongside delivery "
            "actions (Confluence / Jira). Clicking it posts a confirmation "
            "prompt — on confirm the product is marked status='archived' and "
            "excluded from future 'list products' lookups. Wired in the "
            "dispatch router (product_archive_ prefix), product list handler "
            "(_handle_product_archive), and Block Kit builder. Reuses the "
            "existing archive_idea_confirm/cancel confirmation flow. "
            "11 new tests (2151 total)."
        ),
    ),
    CodexEntry(
        "0.15.15",
        date(2026, 3, 10),
        (
            "Fix progress heartbeat not firing during interactive PRD "
            "flows. Root cause: run_interactive_slack_flow() in "
            "_flow_runner.py never created a make_progress_poster() "
            "callback or set flow.progress_callback — unlike the "
            "non-interactive and resume paths which both wired it. "
            "Added progress_cb creation and registration in the "
            "callback registry so section-by-section Slack updates "
            "now fire correctly. 3 new tests (2154 total)."
        ),
    ),
    CodexEntry(
        "0.16.0",
        date(2026, 3, 10),
        (
            "Optimise PRD section generation performance. Three changes "
            "reduce wall-clock runtime by ~40%% for later sections: "
            "(1) Condensed prior-section context for refine tasks — "
            "new approved_context_condensed() sends only titles + first "
            "500 chars instead of full text, cutting the research-model "
            "prompt size from ~30K+ to ~5K for section 9. "
            "(2) Exclude executive_summary from approved_sections in "
            "critique/refine tasks since it is already passed as a "
            "separate template parameter (eliminates double-counting). "
            "(3) Remove knowledge_sources and embedder from the critic "
            "agent — pure evaluation does not need RAG retrieval. "
            "4 new tests (2158 total)."
        ),
    ),
    CodexEntry(
        "0.16.1",
        date(2026, 3, 10),
        (
            "Fix post-completion flow not prompting user after resume. "
            "handle_resume_prd() called resume_prd_flow(auto_approve=True) "
            "without Jira callbacks, so _finalization fell to auto-publish "
            "instead of the interactive phased flow. Added "
            "jira_skeleton_approval_callback and jira_review_callback params "
            "to resume_prd_flow(), wired them to the flow instance and "
            "callback registry. handle_resume_prd() now registers the "
            "interactive run and builds Jira callbacks before resuming. "
            "5 new tests (2150 total)."
        ),
    ),
    CodexEntry(
        "0.16.2",
        date(2026, 3, 10),
        (
            "Server crash resilience and log-driven bug fixes. "
            "(1) Created start_server_watchdog.sh — auto-restart wrapper "
            "with signal handling (clean shutdown on SIGINT/SIGTERM, no "
            "restart), circuit breaker (5 restarts in 120s → stop), and "
            "logging to logs/watchdog.log. "
            "(2) Fixed LLM run_id hallucination in Jira tickets — added "
            "authoritative_run_id field to JiraCreateIssueTool that "
            "overrides whatever the LLM provides (same pattern as "
            "Confluence URL override). Wired through agent factories and "
            "orchestrator stages with flow.state.run_id. "
            "(3) Fixed ShutdownError swallowed in run_post_completion() — "
            "the generic except Exception was catching ShutdownError, "
            "BillingError, and ModelBusyError, preventing the service "
            "layer from properly pausing the flow. Added explicit re-raise "
            "before the generic catch. "
            "(4) Fixed 7 pre-existing flaky retry tests caused by "
            "background thread time.sleep() interception — changed strict "
            "assert_called_once_with/assert_not_called to resilient "
            "assert_any_call and filtered call list checks. "
            "12 new tests (2175 total)."
        ),
    ),
    CodexEntry(
        "0.17.0",
        date(2026, 3, 13),
        (
            "MongoDB Atlas migration — replaced localhost MongoDB with "
            "cloud-hosted MongoDB Atlas. Refactored mongodb.client to use "
            "MONGODB_ATLAS_URI (mongodb+srv://) as the sole connection "
            "method; removed MONGODB_URI, MONGODB_PORT, MONGODB_USERNAME, "
            "MONGODB_PASSWORD env vars. Updated preflight check to "
            "validate Atlas connectivity. Created one-time migration "
            "script (scripts/migrate_to_atlas.py) to export all "
            "collections and indexes from localhost to Atlas with "
            "dry-run support and duplicate-key resilience."
        ),
    ),
    CodexEntry(
        "0.17.1",
        date(2026, 3, 13),
        (
            "Fix intent misclassification: idea text containing 'jira "
            "tickets' or 'jira epics' as body content was being "
            "reclassified from create_prd to create_jira by the phrase "
            "override chain in _message_handler.py. Reordered phrase "
            "overrides so has_idea_phrase is checked before "
            "has_create_jira_phrase, and added guard so the jira phrase "
            "override does not fire when the LLM already classified the "
            "intent as create_prd. Added 3 regression tests."
        ),
    ),
    CodexEntry(
        "0.18.0",
        date(2026, 3, 13),
        (
            "GStack agent integration — added 7 gstack-inspired agent "
            "roles (CEO Reviewer, Eng Manager, Staff Engineer, Release "
            "Engineer, QA Engineer, QA Lead, Retro Manager). Introduced "
            "Phase 1.5: after executive summary approval, the CEO "
            "Reviewer generates an 'executive_product_summary' (10-star "
            "product vision) and the Eng Manager produces an "
            "'engineering_plan' (technical architecture basis for Jira "
            "tickets). Both artefacts are auto-approved specialist "
            "sections. Phase 2 section drafting now uses both artefacts "
            "as context instead of the raw executive summary. Jira "
            "ticket creation uses the engineering plan as additional "
            "context. SECTION_ORDER expanded from 10 to 12 sections. "
            "Added SPECIALIST_SECTION_KEYS constant. Resume support "
            "restores specialist fields from MongoDB. 12 new tests in "
            "test_ceo_eng_review.py; 2162 total tests passing."
        ),
    ),
    CodexEntry(
        "0.19.0",
        date(2026, 3, 13),
        (
            "Jira Review & QA Test sub-tasks — extended the 3-phase Jira "
            "pipeline to 5 phases. Phase 4: Staff Engineer + QA Lead "
            "review every user story, creating '[Staff Eng Review]' and "
            "'[QA Lead Review]' sub-tasks per Story (structural audit + "
            "test methodology review). Phase 5: QA Engineer creates "
            "'[QA Test]' counter-tickets per implementation sub-task "
            "covering edge cases, security, and rendering. Activated 3 "
            "stub agents (staff_engineer, qa_lead, qa_engineer) with "
            "full factories, task YAML configs, and JiraCreateIssueTool. "
            "Extended jira_phase state machine through review_ready → "
            "review_done → qa_test_ready → qa_test_done. Added Slack "
            "approval buttons and handlers for phases 4 and 5. Updated "
            "finalization pipeline, product list blocks, and approval "
            "handler dispatch. 2162 tests passing."
        ),
    ),
    CodexEntry(
        "0.20.0",
        date(2026, 3, 13),
        (
            "UX Designer agent & Figma Make integration — new UX Designer "
            "agent (Phase 1.5c) converts the Executive Product Summary into "
            "a structured Figma Make prompt and submits it to the Figma Make "
            "API to generate clickable prototypes. Figma tool package "
            "(tools/figma/) with HTTP client, submit/poll lifecycle, and "
            "CrewAI BaseTool wrapper. Graceful fallback: when "
            "FIGMA_ACCESS_TOKEN is not set, stores the generated prompt for "
            "manual use (status 'prompt_ready'). Figma design URL and "
            "status persisted to MongoDB workingIdeas. Product list shows "
            "Figma status (✅ link, ⏳ in-progress, ✏️ prompt ready) with "
            "Start/Retry/View buttons. UX design context (Figma URL and/or "
            "prompt) fed into all Jira ticket generation stages so Stories "
            "and Sub-tasks reference the visual design. New env vars: "
            "FIGMA_ACCESS_TOKEN, FIGMA_TEAM_ID, GEMINI_UX_DESIGNER_MODEL. "
            "55 new tests (2217 total)."
        ),
    ),
    CodexEntry(
        "0.20.1",
        date(2026, 3, 15),
        (
            "Resume gate bypass fix — resumed PRD flows no longer get "
            "stuck at the requirements approval gate or the 'proceed to "
            "sections?' gate when specialist agents (CEO, Eng, UX) already "
            "ran in a prior attempt. _requires_approval() now checks "
            "flow.state.executive_product_summary, engineering_plan, and "
            "figma_design_status to auto-approve. User decision gate "
            "skipped when all specialist agents were skipped (resume) or "
            "Phase 2 sections already have content. Fixed "
            "test_callback_false_raises_completed to mock Gemini "
            "credentials and specialist agents."
        ),
    ),
    CodexEntry(
        "0.20.2",
        date(2026, 3, 16),
        (
            "Retry UX Design dispatch fix + test performance — "
            "Added 'product_ux_design_' to _PRODUCT_PREFIXES in "
            "_dispatch.py so the Retry UX Design button click is "
            "routed to _handle_ux_design(). Added regression test. "
            "Fixed 6 slow tests (28s each → <1s) that were hitting the "
            "live Gemini API via unmocked _run_ux_design(). Full test "
            "suite: 199s → 32s. 2205 tests."
        ),
    ),
    CodexEntry(
        "0.21.0",
        date(2026, 3, 16),
        (
            "Figma Make — Playwright browser automation — "
            "Replaced non-existent /v1/ai/make REST API with Playwright "
            "headless Chromium automation against the Figma Make web UI "
            "(figma.com/make/new). New _client.py drives headless browser: "
            "navigate → enter prompt → wait for URL change → return file URL. "
            "New _config.py with FIGMA_SESSION_DIR, FIGMA_MAKE_TIMEOUT, "
            "FIGMA_HEADLESS env vars. New login.py interactive session helper "
            "for one-time Figma auth. Removed FIGMA_ACCESS_TOKEN / "
            "FIGMA_TEAM_ID / FIGMA_API_BASE. Added playwright>=1.40 to deps. "
            "32 Figma tests rewritten. 2221 tests."
        ),
    ),
    CodexEntry(
        "0.21.1",
        date(2026, 3, 16),
        (
            "Fix 12/10 section count in idea list — "
            "total_sections was hardcoded to 10 in _queries.py and "
            "fallback defaults in _flow_handlers.py and "
            "_idea_list_blocks.py, but SECTION_ORDER grew to 12 in "
            "v0.18.0 when specialist sections were added. sections_done "
            "counted all 12 keys from MongoDB, producing '12/10'. "
            "Added _TOTAL_SECTIONS = 12 in _queries.py, updated all "
            "fallback defaults to 12, added TOTAL_SECTIONS constant "
            "to _sections.py. 2221 tests."
        ),
    ),
    CodexEntry(
        "0.22.0",
        date(2026, 3, 16),
        (
            "Figma project config + OAuth + REST API — "
            "Added figma_api_key, figma_team_id, figma_oauth_token, "
            "figma_oauth_refresh_token, figma_oauth_expires_at to "
            "projectConfig schema. New _api.py REST client "
            "(get_team_projects, get_project_files, get_file_info, "
            "refresh_oauth_token, exchange_oauth_code). Updated "
            "_config.py with project-level credential resolution "
            "(API key → OAuth → session file). Updated _client.py "
            "with _build_context() OAuth cookie injection. Rewritten "
            "login.py with dual mode (--oauth flag for OAuth2 flow, "
            "default session login). Setup wizard expanded from 2 to "
            "4 steps (added figma_api_key, figma_team_id). Wired "
            "project_config through agent/flow pipeline. 2253 tests."
        ),
    ),
    CodexEntry(
        "0.22.1",
        date(2026, 3, 16),
        (
            "Project config wizard + Config button — "
            "Expanded update_config intent with broad config phrases "
            "(project config, configure project, reconfigure, project "
            "settings, etc.). Rewrote handle_update_config to launch "
            "the 5-step setup wizard (project name, Confluence key, "
            "Jira key, Figma API key, Figma team ID) for existing "
            "projects with current values shown. Added `:gear: Config` "
            "button to product list header. New mark_pending_reconfig() "
            "in session_manager. Dispatch routes product_config to "
            "_handle_product_config. 2260 tests."
        ),
    ),
    CodexEntry(
        "0.22.2",
        date(2026, 3, 16),
        (
            "LLM token optimisation — critique task now uses "
            "approved_context_condensed(char_limit=300) instead of "
            "full approved_context; new condensed_text() helper "
            "truncates EPS and engineering plan to 1500 chars for "
            "critique calls; removed redundant critique_section_content "
            "from refine expected_output format. Manual UX Design "
            "button — product list shows :page_facing_up: Manual UX "
            "Design alongside API retry; dispatches to "
            "_handle_manual_ux_design which uploads a markdown file "
            "with executive_product_summary + ux_design section for "
            "copy-paste into Figma Make. 2271 tests."
        ),
    ),
    CodexEntry(
        "0.22.3",
        date(2026, 3, 16),
        (
            "Fix UX Design task producing no user-visible output. "
            "(1) Task YAML now mandates agent ALWAYS outputs "
            "FIGMA_PROMPT: with the full design spec regardless of "
            "tool success/error/skip — previously agent only relayed "
            "FIGMA_ERROR on API 404 (74 chars, no design content). "
            "(2) _ux_design.py error path recovers design content "
            "from agent output even when FIGMA_ERROR is present — "
            "strips error markers and stores remainder as prompt when "
            ">100 chars. (3) UX design prompt now appended as "
            "'Appendix: UX Design' in both finalized PRD and "
            "save_progress drafts. (4) Standalone ux_design_*.md "
            "file written alongside PRD. (5) Slack ux_design_complete "
            "notification includes prompt preview and tells user "
            "where to find the full spec. 2272 tests."
        ),
    ),
    CodexEntry(
        "0.23.0",
        date(2026, 3, 16),
        (
            "SSO integration — 'Idea Foundry' application whitelisting. "
            "(1) sso_auth.py rewritten for RS256 JWT validation using "
            "the SSO public key (was HS256). Tokens verified locally "
            "via SSO_JWT_PUBLIC_KEY_PATH or remotely via /sso/oauth/introspect. "
            "(2) app_id claim enforcement: when SSO_EXPECTED_APP_ID is set, "
            "only tokens issued for the Idea Foundry OAuth app are accepted. "
            "(3) sso_webhooks.py updated to match actual SSO event types "
            "(user.created/updated/deleted, login.success/failed, "
            "token.revoked) with X-Webhook-Signature header (was X-SSO-Signature). "
            "(4) FastAPI app title set to 'Idea Foundry'. "
            "(5) .env.example includes full SSO configuration block. "
            "(6) SSO bootstrap seeds 'Idea Foundry' as registered OAuth "
            "application on startup. 2272 tests."
        ),
    ),
    CodexEntry(
        "0.23.1",
        date(2026, 3, 16),
        (
            "Fix 'No Executive Product Summary found' on Manual UX Design "
            "for completed/published products. _handle_manual_ux_design() "
            "only checked section.executive_product_summary (populated by "
            "CEO Review in newer runs). Older completed products store the "
            "EPS in the top-level executive_summary array. Fix adds "
            "fallback: when section.executive_product_summary is empty, "
            "reads from doc.executive_summary[-1].content. 2272 tests."
        ),
    ),
    CodexEntry(
        "0.24.0",
        date(2026, 3, 16),
        (
            "CRUD APIs with pagination for Projects and Ideas. "
            "GET /projects (paginated 10/25/50), GET /projects/{id}, "
            "POST /projects, PATCH /projects/{id}, DELETE /projects/{id}. "
            "GET /ideas (paginated 10/25/50, filter by project_id & status), "
            "GET /ideas/{run_id}, PATCH /ideas/{run_id}/status (archive/pause). "
            "Both routers SSO-protected. 35 new tests, 2307 total."
        ),
    ),
    CodexEntry(
        "0.25.0",
        date(2026, 3, 17),
        (
            "SSO-based user_id on all API endpoints. "
            "All login and registration handled by the external SSO portal; "
            "users are redirected back to Idea Foundry after successful auth. "
            "No local user accounts stored in the ideas database. "
            "(1) `require_sso_user` returns `user_id` from the SSO JWT `sub` "
            "claim directly — no local DB provisioning. "
            "(2) All API endpoints (Ideas, Projects, PRD, Publishing) receive "
            "`user: dict = Depends(require_sso_user)` parameter with the "
            "authenticated SSO `user_id`. "
            "(3) Removed local `users` collection, `user_provisioning` module, "
            "and Slack auto-provisioning calls. "
            "2307 tests."
        ),
    ),
    CodexEntry(
        "0.26.0",
        date(2026, 3, 17),
        (
            "Logging standard & incident-trace instrumentation. "
            "(1) New CODEX § Logging Standard + Coding Standards § 8 require "
            "all business logic modules to use `get_logger(__name__)`, log at "
            "boundaries with trace identifiers (run_id, user_id, channel, "
            "team_id, project_id), and `exc_info=True` on errors. "
            "(2) Converted 41 files from bare `import logging` / "
            "`logging.getLogger(__name__)` to unified `get_logger()` pattern. "
            "(3) Added incident-trace logging to health router (token status, "
            "exchange, refresh), projects CRUD (5 endpoints), ideas CRUD "
            "(get, status update), SSO auth (auth boundary, token validation), "
            "publishing service (list pending, publish+tickets, delivery status), "
            "Slack tools (send/read/post/interpret with channel/run_id), "
            "OpenAI chat (entry/exit with intent + model), "
            "Gemini chat (entry/exit with intent + model), "
            "document assembly (run_id context). "
            "2303 tests."
        ),
    ),
    CodexEntry(
        "0.27.0",
        date(2026, 3, 17),
        (
            "SERVER_ENV three-tier public URL resolution. "
            "Added get_server_env(), is_dev(), get_public_url() to "
            "ngrok_tunnel.py. SERVER_ENV (DEV/UAT/PROD) now controls "
            "how the public-facing URL is resolved: DEV starts an ngrok "
            "tunnel, UAT uses DOMAIN_NAME_UAT, PROD uses DOMAIN_NAME_PROD. "
            "Rewired main.py start_api() and start_server.sh to use "
            "SERVER_ENV instead of NGROK_AUTHTOKEN presence check. "
            "--ngrok flag kept as override. Updated .env.example and "
            "slack_config.py docstring. 11 new tests, 2320 total."
        ),
    ),
    CodexEntry(
        "0.27.1",
        date(2026, 3, 18),
        (
            "MongoDB database name fully environment-driven. "
            "Removed stale legacy vars (MONGODB_URI, MONGODB_PORT, "
            "MONGODB_USERNAME, MONGODB_PASSWORD) from .env.example and "
            "README — only MONGODB_ATLAS_URI and MONGODB_DB remain. "
            "migrate_to_atlas.py now imports DEFAULT_DB_NAME from "
            "client.py instead of duplicating the fallback. "
            "Updated .env.example, README, and obsidian docs "
            "(Environment Variables, MongoDB Schema) to document "
            "MONGODB_DB as the way to switch databases "
            "(e.g. ideas_dev, ideas_uat, ideas_prod). 2320 tests."
        ),
    ),
    CodexEntry(
        "0.28.0",
        date(2026, 3, 20),
        (
            "Confluence page titles use idea text instead of 'PRD' prefix. "
            "New make_page_title() helper in orchestrator/_helpers.py "
            "generates short-form titles from the raw idea text (truncated "
            "to 80 chars with ellipsis). Replaced 12 inline 'PRD — {idea}' "
            "title constructions across 8 files: _confluence.py, "
            "_post_completion.py, _startup_delivery.py, _startup_review.py, "
            "_jira.py, _cli_startup.py, publishing/service.py, "
            "publishing/watcher.py, and components/startup.py. "
            "8 new make_page_title tests, 2328 total."
        ),
    ),
    CodexEntry(
        "0.28.1",
        date(2026, 3, 20),
        (
            "Fix Confluence 'not configured' false negative. "
            "_has_confluence_credentials() no longer requires "
            "CONFLUENCE_SPACE_KEY env var — space key is a per-project "
            "routing parameter resolved from projectConfig at publish "
            "time. Only the three connection credentials "
            "(ATLASSIAN_BASE_URL, ATLASSIAN_USERNAME, ATLASSIAN_API_TOKEN) "
            "are checked. 2329 tests."
        ),
    ),
    CodexEntry(
        "0.28.2",
        date(2026, 3, 20),
        (
            "Suppress redundant 'PRD Generation Complete' Slack notification "
            "when PRD is fully delivered (Confluence + Jira already done). "
            "User already receives granular progress messages for each "
            "delivery step; the summary banner and next-step suggestion "
            "are now skipped in the fully-delivered case across all 3 "
            "Slack flow completion paths (_flow_runner.py, "
            "_flow_handlers.py, router.py). 2329 tests."
        ),
    ),
    CodexEntry(
        "0.29.0",
        date(2026, 3, 20),
        (
            "Route Slack thread replies to active PRD flow instead of LLM "
            "intent classifier. When a user sends feedback during section "
            "drafting (no explicit approval gate), the message is now "
            "queued, acknowledged in Slack, and injected into the next "
            "section-loop critique. New _queued_feedback store in "
            "_run_state.py, drain_queued_feedback() consumed in "
            "_section_loop.py. Added _safe_ack_reply helper and "
            "conftest.py for slack test isolation. 2329 tests."
        ),
    ),
    CodexEntry(
        "0.29.1",
        date(2026, 3, 20),
        (
            "Fix bot not responding in Slack session threads after cache "
            "expiry or server restart. Root cause: the should_process gate "
            "in events_router.py silently dropped thread messages when the "
            "in-memory thread cache expired (10-min TTL) and no project "
            "was selected yet (e.g. user wants to START configuring). All "
            "4 conditions were False: has_conversation, has_interactive, "
            "has_pending, has_active_session. Fix: added a 5th fallback — "
            "has_bot_thread_history() checks MongoDB agentInteraction for "
            "prior bot participation in the thread. When found, the thread "
            "is re-registered in the in-memory cache to avoid repeated DB "
            "lookups. New has_bot_thread_history() in agent_interactions "
            "repository. 6 new tests, 2335 total."
        ),
    ),
    CodexEntry(
        "0.29.2",
        date(2026, 3, 20),
        (
            "Fix bare 'configure' not recognised as project config intent. "
            "Root cause: _UPDATE_CONFIG_PHRASES required at least two words "
            "(e.g. 'configure project', 'project config') so the single "
            "word 'configure' failed both phrase matching and LLM "
            "classification. Added 'configure' to _UPDATE_CONFIG_PHRASES "
            "and 'configure' → update_config examples in Gemini/OpenAI LLM "
            "prompt files. Dispatch guards (not has_memory_phrase) ensure "
            "'configure memory' still routes correctly. "
            "5 new tests, 2340 total."
        ),
    ),
    CodexEntry(
        "0.30.0",
        date(2026, 3, 20),
        (
            "All bot commands now clickable — replace every 'Say *command*' "
            "text prompt with interactive Slack Block Kit buttons. "
            "New _command_blocks.py module with 11 button constants and "
            "10 composite block builders. New _command_handler.py with "
            "cmd_* action dispatch wired into _dispatch.py. Replaced 18 "
            "text-based command prompts across 12 files (session, memory, "
            "retry, product list, flow handlers, message handler, restart, "
            "router). Help intent now renders as Block Kit with action "
            "buttons instead of plain text bullet list. "
            "33 new tests, 2373 total."
        ),
    ),
    CodexEntry(
        "0.30.1",
        date(2026, 3, 21),
        (
            "Complete intent-to-button coverage: added 5 missing cmd_* "
            "buttons (publish, create_jira, restart_prd, current_project, "
            "create_prd). All 16 LLM-recognised actionable intents now "
            "have clickable Block Kit buttons. Updated help_blocks() with "
            "4 action rows covering all intents. Added Slack "
            "Interaction-First Rule to CODEX.md and Coding Standards — "
            "every future intent must have a button. Replaced fallback "
            "unknown-intent text with buttons. "
            "7 new tests, 2380 total."
        ),
    ),
    CodexEntry(
        "0.30.2",
        date(2026, 3, 21),
        (
            "Admin-gated project configuration: non-admin channel users "
            "blocked from configure/switch/create project buttons and "
            "update_config text intent. Role-aware help_blocks() hides "
            "admin-only buttons for non-admins. Added admin gate to "
            "configure_memory next-step accept path. "
            "18 new tests, 2398 total."
        ),
    ),
    CodexEntry(
        "0.30.3",
        date(2026, 3, 21),
        (
            "Defense-in-depth admin gates: added can_manage_memory checks "
            "directly in handle_update_config, handle_configure_memory, "
            "handle_project_name_reply, and handle_project_setup_reply. "
            "Non-admins in channels are blocked at the handler level "
            "regardless of which caller invokes them. Fixes bypass where "
            "'configure' text was consumed as a project name by a stale "
            "pending_create state from the pre-gated setup wizard."
        ),
    ),
    CodexEntry(
        "0.31.0",
        date(2026, 3, 21),
        (
            "Interaction-first rule for ALL prompts: replaced every "
            "'type skip', 'say *command*', 'just tell me' text with "
            "clickable Block Kit buttons across the entire Slack UX. "
            "Setup wizard steps now have a Skip button (setup_skip "
            "action). Setup completion, next-step handler, greeting, "
            "idea list footer, and empty-ideas state all post action "
            "buttons. Added _SETUP_ACTIONS dispatch routing. "
            "26 new interaction-first regression tests. "
            "Added Interaction-First Testing section to CODEX.md. "
            "2425 total tests."
        ),
    ),
    CodexEntry(
        "0.31.1",
        date(2026, 3, 21),
        (
            "Fix 'configure tools' misrouted to project config. Added "
            "tools phrases (configure tools, add tools, manage tools, "
            "etc.) to _CONFIGURE_MEMORY_PHRASES and both LLM prompts. "
            "Guarded update_config dispatch so has_memory_phrase prevents "
            "LLM-classified update_config from catching memory/tool "
            "phrases. 4 new tests, 2429 total."
        ),
    ),
    CodexEntry(
        "0.31.2",
        date(2026, 3, 21),
        (
            "Slack file-upload fallback for truncated content. When "
            "block text exceeds 2800 chars, the inline preview is "
            "truncated and the full content is uploaded as a "
            "downloadable text file in the thread. Applies to all "
            "5 rendered sections: idea approval, manual refinement, "
            "requirements breakdown, exec summary feedback, and "
            "exec summary completion. New _slack_file_helper module "
            "with truncate_with_file_hint() and upload_content_file(). "
            "18 new tests, 2447 total."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

#: Current application version (derived from the latest codex entry).
__version__: str = _CODEX[-1].version


def get_version() -> str:
    """Return the current application version string."""
    return __version__


def get_codex() -> list[dict]:
    """Return the full codex as a list of dicts (JSON-serialisable)."""
    return [
        {
            "version": entry.version,
            "date": entry.date.isoformat(),
            "summary": entry.summary,
        }
        for entry in _CODEX
    ]


def get_latest_codex_entry() -> dict:
    """Return only the most recent codex entry as a dict."""
    entry = _CODEX[-1]
    return {
        "version": entry.version,
        "date": entry.date.isoformat(),
        "summary": entry.summary,
    }
