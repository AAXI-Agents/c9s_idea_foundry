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
