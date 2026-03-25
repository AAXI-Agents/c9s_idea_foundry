# Version History

> Full changelog from v0.1.0 to current. Updated every session.

## v0.40.0 (2026-03-25)

| Version | Summary |
|---------|--------|
| 0.40.0 | Engagement Manager project knowledge awareness. (1) New _build_project_tools() builds FileReadTool + DirectoryReadTool scoped to project knowledge folder, loads completed-ideas context from MongoDB. (2) create_engagement_manager(project_id) gives agent file-reading tools and appends ideas context to backstory. (3) handle_unknown_intent(project_id) passes {project_knowledge} to task template. (4) engagement_response_task rewritten with A/B/C classification (knowledge question / action intent / steering) and duplication/synergy detection instructions. (5) agent.yaml backstory expanded with Project Knowledge & Idea Awareness section. (6) _message_handler.py passes project_id. 12 new tests, 59 EM tests, 2614 total |

## v0.39.0 (2026-03-24)

| Version | Summary |
|---------|--------|
| 0.39.0 | Engagement Manager PRD Orchestrator — transforms the engagement manager from a simple intent router into a full idea-to-PRD lifecycle orchestrator. (1) agent.yaml rewritten with expanded role, full agent team knowledge, 2-step orchestration strategy (Step 1 sequential, Step 2 parallel), heartbeat protocol, user steering detection, session isolation. (2) 3 new tasks: idea_to_prd_orchestration_task, heartbeat_update_task, user_steering_detection_task. (3) 5 new functions: generate_heartbeat(), make_heartbeat_progress_callback(), detect_user_steering(), _parse_steering_result(), orchestrate_idea_to_prd(). (4) .gitignore updated to ignore entire output/ folder. (5) conftest.py recursion limit fix for crewai 1.9.x. 32 new tests, 47 engagement manager tests total |

## v0.38.0 (2026-03-24)

| Version | Summary |
|---------|--------|
| 0.38.0 | Publication safety overhaul — user-triggered publishing only. (1) Duplicate Confluence fix — publish_to_confluence() accepts page_id; stored confluence_page_id reused for updates instead of creating duplicates. (2) Auto-publish removal — _run_auto_post_completion() no longer calls crews; startup functions discovery-only; file watcher disabled; startup stage always skips. (3) Confluence prerequisite for Jira — all Jira paths check confluence_url first; user guided to publish Confluence with button if not yet published. 23 tests updated, 2571 total |

## v0.37.1 (2026-03-24)

| Version | Summary |
|---------|--------|
| 0.37.1 | Slack thread recovery & flow-aware summaries. (1) Flow thread recovery — thread messages no longer silently dropped after in-memory cache expiry; new find_idea_by_thread() MongoDB fallback queries workingIdeas by slack_channel + slack_thread_ts, re-caches on match. (2) Flow-aware summaries — summary/status/progress requests in flow threads return structured flow status (emoji, sections done/total, idea text, section names) instead of generic help. 16 new tests, 2571 total |

## v0.37.0 (2026-03-23)

| Version | Summary |
|---------|--------|
| 0.37.0 | Server crash-prevention hardening for 99.99% uptime. _safe_handler() wraps all 13 Slack interaction handler dispatches with crash protection + Slack error notification. Global exception handler enhanced with exc_info=True. PRD router MongoDB calls wrapped (list_resumable, list_jobs, get_job, kickoff). OAuth router, SSO webhooks hardened. Jira & Confluence JSON decode protection. 14 new tests, 2560 total |

## v0.36.0 (2026-03-23)

| Version | Summary |
|---------|--------|
| 0.36.0 | Fully automated PRD flow + active-flow config guard. Default mode switched from interactive to automated — all approval gates auto-approve with progress summaries. Enhanced critique summaries in Slack. Auto-resume on server restart via find_resumable_on_startup(). Config guard blocks project configuration during active flows. 29 new tests, 2541 total |

## v0.35.0 (2026-03-22)

| Version | Summary |
|---------|--------|
| 0.35.0 | Engagement Manager agent — new CrewAI agent handles unknown intents with context-aware conversational responses. Uses GEMINI_MODEL (basic tier). Integrated into Slack message handler with graceful fallback. General questions retain direct LLM reply. 16 new tests, 2512 total |

## v0.28.x (2026-03-20)

| Version | Summary |
|---------|--------|
| 0.28.0 | Confluence/Jira page titles use idea text instead of 'PRD —' prefix. New make_page_title() helper, 12 inline sites replaced across 9 files. 8 new tests, 2328 total |
| 0.28.1 | Fix Confluence 'not configured' false negative. _has_confluence_credentials() no longer requires CONFLUENCE_SPACE_KEY env var — space key resolved per-project from projectConfig at publish time. 2329 tests |
| 0.28.2 | Suppress redundant 'PRD Generation Complete' Slack notification when PRD is fully delivered. Granular progress messages suffice; summary banner and next-step skipped in all 3 flow completion paths. 2329 tests |

## v0.29.x (2026-03-20)

| Version | Summary |
|---------|--------|
| 0.29.0 | Route Slack thread replies to active PRD flow. Queued feedback mechanism so user replies during section drafting are acknowledged and injected into the next section-loop critique instead of falling through to LLM intent classifier. 2329 tests |
| 0.29.1 | Fix bot not responding in Slack session threads after cache expiry or server restart. Added `has_bot_thread_history()` fallback checking MongoDB agentInteraction for prior bot participation. Re-registers thread in memory cache on hit. 6 new tests, 2335 total |
| 0.29.2 | Fix bare 'configure' not recognised as project config intent. Added 'configure' to `_UPDATE_CONFIG_PHRASES` and LLM prompt examples. 5 new tests, 2340 total |

## v0.30.x (2026-03-20)

| Version | Summary |
|---------|---------|
| 0.30.0 | All bot commands clickable — replaced every 'Say *command*' text prompt with interactive Slack Block Kit buttons. New `_command_blocks.py` (11 button constants, 10 composite builders), new `_command_handler.py` (cmd_* dispatch). 18 text prompts replaced across 12 files. Help intent now renders Block Kit with action buttons. 33 new tests, 2373 total |
| 0.30.1 | Complete intent-to-button coverage: added 5 missing cmd_* buttons (publish, create_jira, restart_prd, current_project, create_prd). 16 total button constants. Codified Slack Interaction-First Rule in CODEX.md § Slack Interaction-First Rule and Coding Standards § 9. Unknown-intent fallback now shows New Idea + Help buttons. 7 new tests, 2380 total |
| 0.30.2 | Admin-gated project configuration: non-admin channel users blocked from configure/switch/create project buttons and update_config text intent. Role-aware help_blocks() hides admin-only buttons for non-admins. Admin gate on configure_memory next-step accept. 18 new tests, 2398 total |
| 0.30.3 | Defense-in-depth admin gates in handlers: can_manage_memory checks inside handle_update_config, handle_configure_memory, handle_project_name_reply, handle_project_setup_reply. Blocks non-admins at handler level regardless of caller. |

## v0.31.x (2026-03-21)

| Version | Summary |
|---------|---------|
| 0.31.0 | Interaction-first rule for ALL prompts: replaced every 'type skip', 'say *command*', 'just tell me' text with clickable Block Kit buttons. Setup wizard Skip button, setup-complete/next-step/greeting/idea-list/empty-ideas all use action buttons. _SETUP_ACTIONS dispatch routing. Interaction-First Testing section in CODEX.md. 26 new tests, 2425 total |
| 0.31.1 | Fix 'configure tools' misrouted to project config. Added tools phrases to _CONFIGURE_MEMORY_PHRASES and both LLM prompts. Guarded update_config dispatch so memory/tool phrases prevent update_config catch. 4 new tests, 2429 total |
| 0.31.2 | Slack file-upload fallback for truncated content. When block text exceeds 2800 chars, inline preview truncated and full content uploaded as downloadable text file in thread. All 5 rendered sections: idea approval, manual refinement, requirements breakdown, exec summary feedback, exec summary completion. New _slack_file_helper module. 18 new tests, 2447 total |

## v0.32.x (2026-03-21)

| Version | Summary |
|---------|--------|
| 0.32.0 | Bot only responds in threads where it is @mentioned. Fallback conditions (active_session, thread_history) in events_router now require @mention. Active workflow conditions (interactive, pending, conversation) remain unrestricted. 6 new tests, 2453 total |
| 0.32.1 | Fix files:write scope missing from Slack manifest (file uploads failed). Admin cache now has 5-min TTL so role changes detected without restart. exec_summary_completion truncation limit lowered to 2700. 3 new tests, 2456 total |

## v0.33.x (2026-03-22)

| Version | Summary |
|---------|--------|
| 0.33.0 | Output file reorganisation & UX design file fix. UX markdown only generated on successful Figma design (URL available). PRD/UX files now saved under output/{project_id}/product requirement documents/ and output/{project_id}/ux design/. Added ux_output_file MongoDB field. Startup disk scanner covers both legacy and project dirs. Migration script: scripts/migrate_output_dirs.py. 7 new tests, 2463 total |

## v0.34.x (2026-03-22)

| Version | Summary |
|---------|--------|
| 0.34.0 | Project knowledge base — Obsidian-style knowledge folders for agent learning. New scripts/project_knowledge.py generates projects/ folders with overview pages (config, memory, tools, references) and completed idea pages (YAML frontmatter, wikilinks, PRD sections). Hooked into create_project() and finalize(). Integrated load_completed_ideas_context() into enrich_backstory() so agents receive completed idea summaries. 34 new tests, 2496 total |

## v0.27.x (2026-03-17)

| Version | Summary |
|---------|---------|| 0.27.1 | MongoDB database name fully environment-driven. Removed stale legacy vars from .env.example and README. migrate_to_atlas.py imports DEFAULT_DB_NAME. Updated docs for MONGODB_DB switching. 2320 tests || 0.27.0 | SERVER_ENV three-tier public URL resolution. get_server_env(), is_dev(), get_public_url() in ngrok_tunnel.py. DEV→ngrok, UAT→DOMAIN_NAME_UAT, PROD→DOMAIN_NAME_PROD. Rewired main.py and start_server.sh. 11 new tests, 2320 total |

## v0.26.x (2026-03-17)

| Version | Summary |
|---------|---------|
| 0.26.0 | Logging standard & incident-trace instrumentation. CODEX § Logging Standard + Coding Standards § 8. Converted 41 files to get_logger(). Added trace logging (run_id, user_id, channel, team_id) to health, projects, ideas, SSO, publishing, Slack tools, OpenAI/Gemini chat, document assembly. 2303 tests |

## v0.25.x (2026-03-17)

| Version | Summary |
|---------|---------|
| 0.25.0 | SSO-based user_id on all API endpoints. All auth via external SSO portal; no local user accounts in ideas DB. API endpoints receive user_id from SSO JWT sub claim. 2303 tests |

## v0.24.x (2026-03-16)

| Version | Summary |
|---------|---------|
| 0.24.0 | CRUD APIs with pagination for Projects and Ideas — GET/POST/PATCH/DELETE /projects; GET/PATCH /ideas with pagination (10/25/50), project_id & status filters. SSO-protected. 35 new tests, 2307 total |

## v0.23.x (2026-03-16)

| Version | Summary |
|---------|---------|
| 0.23.0 | SSO "Idea Foundry" application whitelisting — sso_auth.py rewritten for RS256 JWT (was HS256); app_id claim enforcement via SSO_EXPECTED_APP_ID; sso_webhooks.py handles all 6 SSO events; X-Webhook-Signature header (was X-SSO-Signature); .env.example SSO block; FastAPI title "Idea Foundry"; SSO bootstrap seeds Idea Foundry as registered OAuth app. 2272 tests |

## v0.22.x (2026-03-16)

| Version | Summary |
|---------|---------|
| 0.22.3 | Fix UX Design task producing no user-visible output — task YAML mandates FIGMA_PROMPT always; error recovery; PRD appendix; standalone file; Slack preview. 2272 tests |
| 0.22.2 | LLM token optimisation — critique task uses `approved_context_condensed(char_limit=300)` instead of full `approved_context()`; new `condensed_text()` truncates EPS/eng plan to 1500 chars for critique; removed redundant `critique_section_content` from refine expected_output. Manual UX Design button — product list offers `:page_facing_up: Manual UX Design` alongside API retry; uploads markdown file with EPS + ux_design section for Figma Make copy-paste. 2271 tests |
| 0.22.1 | Project config wizard + Config button — expanded `_UPDATE_CONFIG_PHRASES` (12→21) with project config/configure/reconfigure/settings phrases; rewrote `handle_update_config` to launch 5-step setup wizard with pre-populated current values; added `:gear: Config` button to product list header; new `mark_pending_reconfig()` in session_manager; `product_config` dispatch → `_handle_product_config`; `project_name` as step 1 (skipped for new projects). 2260 tests |
| 0.22.0 | Figma project config + OAuth + REST API — 5 Figma fields in `projectConfig` schema; `_api.py` REST client; project-level credential resolution (API key → OAuth → session); OAuth cookie injection in `_client.py`; dual-mode `login.py` (--oauth flag); setup wizard 2→4 steps; agent/flow pipeline wiring. 2253 tests |

## v0.21.x (2026-03-16)

| Version | Summary |
|---------|---------|
| 0.21.1 | Fix 12/10 section count in idea list — `total_sections` hardcoded to 10 since v0.18.0 added 2 specialist sections; updated `_queries.py`, `_flow_handlers.py`, `_idea_list_blocks.py` to use 12. 2221 tests |
| 0.21.0 | Figma Make — Playwright browser automation — replaced non-existent `/v1/ai/make` REST API with headless Chromium automation against `figma.com/make/new`. New `_client.py` (Playwright), `_config.py` (session-based auth), `login.py` (one-time interactive login). Removed `FIGMA_ACCESS_TOKEN`/`FIGMA_TEAM_ID`/`FIGMA_API_BASE`; added `FIGMA_SESSION_DIR`/`FIGMA_MAKE_TIMEOUT`/`FIGMA_HEADLESS`. 32 Figma tests rewritten. 2221 tests |

## v0.20.x (2026-03-13)

| Version | Summary |
|---------|---------|
| 0.20.2 | Retry UX Design dispatch fix + test performance — added `product_ux_design_` to `_PRODUCT_PREFIXES`; mocked `_run_ux_design` in 6 slow tests (199s → 32s total). 2205 tests |
| 0.20.1 | Resume gate bypass fix — requirements approval gate and user decision gate no longer block on resume when specialist agents already ran. `_requires_approval()` checks specialist state; user decision gate skipped when all specialists were skipped or Phase 2 started |
| 0.20.0 | UX Designer agent & Figma Make integration — Phase 1.5c converts Executive Product Summary into Figma Make prompt; Figma tool package (submit/poll/BaseTool); graceful fallback when FIGMA_ACCESS_TOKEN absent; Figma URL/status in MongoDB + product list; UX design feeds into all Jira stages. 55 new tests (2217 total) |

## v0.19.x (2026-03-13)

| Version | Summary |
|---------|---------|
| 0.19.0 | Jira Review & QA Test sub-tasks — extended 3-phase Jira pipeline to 5 phases. Phase 4: Staff Eng + QA Lead review sub-tasks per Story. Phase 5: QA Engineer test counter-tickets per dev sub-task (edge cases, security, rendering). 3 stub agents activated. Slack approval buttons for phases 4–5. 2162 tests |

## v0.18.x (2026-03-13)

| Version | Summary |
|---------|---------|
| 0.18.0 | GStack agent integration — 7 new agent roles (CEO Reviewer, Eng Manager + 5 stubs). Phase 1.5: CEO Reviewer → `executive_product_summary`, Eng Manager → `engineering_plan`. Both auto-approved specialist sections feed Phase 2 drafting + Jira context. SECTION_ORDER 10→12. 12 new tests; 2162 total |

## v0.17.x (2026-03-13)

| Version | Summary |
|---------|---------|
| 0.17.1 | Fix intent misclassification — idea text containing "jira tickets" or "jira epics" in the body was reclassified from `create_prd` to `create_jira` by the phrase override chain. Reordered phrase overrides (`has_idea_phrase` before `has_create_jira_phrase`) and added LLM trust guard; 3 new regression tests (605 Slack tests total) |
| 0.17.0 | MongoDB Atlas migration — replaced localhost MongoDB with cloud-hosted Atlas; refactored `mongodb.client` to use `MONGODB_ATLAS_URI`; removed old connection env vars; created one-time migration script with dry-run support |

## v0.16.x (2026-03-10)

| Version | Summary |
|---------|---------|
| 0.16.2 | Server crash resilience and log-driven bug fixes — (1) `start_server_watchdog.sh` auto-restart with circuit breaker; (2) fix LLM run_id hallucination via `authoritative_run_id` on JiraCreateIssueTool; (3) fix ShutdownError/BillingError/ModelBusyError swallowed in `run_post_completion()`; (4) fix 7 pre-existing flaky retry tests; 12 new tests (2175 total) |
| 0.16.1 | Fix post-completion flow not prompting user after resume — `handle_resume_prd()` was missing Jira callbacks, causing auto-publish instead of interactive phased flow; added `jira_skeleton_approval_callback` and `jira_review_callback` to `resume_prd_flow()`; 5 new tests (2150 total) |
| 0.16.0 | Optimise PRD section generation performance — condensed prior-section context for refine tasks (titles+500 chars vs full text), exclude exec summary from approved_sections (dedup), remove knowledge_sources from critic agent; 4 new tests (2158 total) |

## v0.15.x (2026-03-08 – 2026-03-10)

| Version | Summary |
|---------|---------|
| 0.15.15 | Fix progress heartbeat not firing during interactive PRD flows — `run_interactive_slack_flow()` was missing `make_progress_poster()` callback; wired progress_cb to flow and callback registry; 3 new tests (2154 total) |
| 0.15.14 | Add archive button to product list — completed ideas show `:file_folder: Archive` button; confirmation prompt reuses existing archive flow; wired in dispatch, handler, and Block Kit builder; 11 new tests (2151 total) |
| 0.15.13 | Eliminate 'unknown' Jira ticket types — `_normalise_issue_type()` in `_tool.py` maps LLM variants ('task', 'Sub-Task', 'unknown') to canonical types; context-aware default (parent_key → Sub-task); 18 new tests (2140 total) |
| 0.15.12 | Persist Jira Epics & Stories output to MongoDB for crash resilience — Sub-tasks stage can now resume after server restart; restores jira_skeleton and jira_epics_stories_output in _run_jira_phase(); 14 new tests (2122 total) |
| 0.15.11 | Remove autonomous Jira detection — `persist_post_completion()`, `_cli_startup.py`, `components/startup.py` no longer set `jira_phase` / `jira_completed`; fixed stale data via one-time script; added data fix pattern to Coding Standards |
| 0.15.10 | Fix delivery state reset — scheduler scan was overwriting `confluence_published` with False on every sweep |
| 0.15.9 | Fix Confluence publish notification — heartbeat progress, Jira skeleton next-step button, button label corrected to "Create Jira Skeleton" |
| 0.15.8 | Critical fix: Jira approval gate — 5 autonomous Jira paths blocked, 23 regression tests, `confluence_only` propagated to all callers |
| 0.15.6 | Fix shutdown error handling — ShutdownError stops retries immediately, pauses flow for auto-resume |
| 0.15.5 | Improve LLM error handling for HTTP 500 and transient errors |
| 0.15.4 | Fix thread-reply intent regression — pending_memory state consumed commands; phrase-based command detection in pending_memory handler |
| 0.15.3 | Fix 'create idea' not recognised — added to phrase list |
| 0.15.2 | Fix 'configure memory' intent — phrase override before LLM dispatch |
| 0.15.1 | Fix Slack bot not responding — env var token fallback for dev setups |
| 0.15.0 | MongoDB collection & index bootstrap on startup; dev_setup.sh script |

## v0.14.x (2026-03-07 – 2026-03-08)

| Version | Summary |
|---------|---------|
| 0.14.6 | Fix product list UX for skeleton_pending — 'Review Jira Skeleton' button |
| 0.14.5 | Persist Jira skeleton to MongoDB; show existing skeleton on resume |
| 0.14.4 | Fix product list showing 'Jira complete' when interactive flow in progress |
| 0.14.3 | Fix 'list ideas' showing 'No ideas found' when completed products exist |
| 0.14.2 | Fix Flow.state read-only property crash in _run_jira_phase() |
| 0.14.1 | Fix Jira skeleton failing for completed PRDs — fall back to find_run_any_status() |
| 0.14.0 | Delivery action buttons & create_jira intent; Block Kit delivery buttons |

## v0.13.x (2026-03-07 – 2026-03-08)

| Version | Summary |
|---------|---------|
| 0.13.2 | Fix TokenManager/CrewJobs resume bugs from log review |
| 0.13.1 | Fix hallucinated Confluence URLs in Jira tickets — resolve from MongoDB |
| 0.13.0 | Remove unused web research tools (SerperDev, Scrape, WebsiteSearch) |

## v0.12.x (2026-03-05 – 2026-03-07)

| Version | Summary |
|---------|---------|
| 0.12.5 | Fix thread_broadcast messages being silently dropped |
| 0.12.4 | Acknowledge user feedback on executive summary |
| 0.12.3 | Fix flow ordering — requirements after exec summary approval |
| 0.12.2 | Fix interactive agent-mode flow skipping exec summary review gate |
| 0.12.1 | Fix Jira ticket persistence to productRequirements |
| 0.12.0 | Fix Jira API v3 400 errors — Atlassian Document Format (ADF) |

## v0.11.x (2026-03-05)

| Version | Summary |
|---------|---------|
| 0.11.2 | Fix PRD section pausing prematurely on 429 rate-limit errors |
| 0.11.1 | Fix 'update knowledge' intent misclassification |
| 0.11.0 | Fix autonomous Jira re-creating tickets on restart; auto-populate ticket URLs |

## v0.10.x (2026-03-05)

| Version | Summary |
|---------|---------|
| 0.10.2 | Migrate Jira API from v2 to v3 (fix 410 Gone) |
| 0.10.1 | Fix missing Jira skeleton button — smart jira_completed check |
| 0.10.0 | Jira phased-approval overhaul: reject/regenerate, immediate epics, sub-task review |

## v0.9.x (2026-03-04 – 2026-03-05)

| Version | Summary |
|---------|---------|
| 0.9.16 | Confluence URL as native Slack button; Jira type resolution via API |
| 0.9.15 | Fix product list display: confluence_published check, Sub-task type |
| 0.9.14 | Product list: incomplete steps as buttons only |
| 0.9.13 | Fix 3 product list issues: URL fallback, status icons, ticket counts |
| 0.9.12 | Add 'list products' intent with delivery manager buttons |
| 0.9.11 | Fix autonomous Jira bypassing user approval; persist jira_phase |
| 0.9.10 | Fix idea list: exclude completed/archived; fix sections_done count |
| 0.9.9 | Fix 503 retry resume — ModelBusyError propagation |
| 0.9.8 | Standardise productRequirements status (new/inprogress/completed) |
| 0.9.7 | Fix Confluence data persisted to wrong collection |
| 0.9.6 | Fix KeyError 'approved_skeleton' in startup delivery |
| 0.9.5 | Jira skeleton next-step hint after Confluence publish |
| 0.9.4 | Remove Confluence parent page ID from LLM-facing surfaces |
| 0.9.3 | Remove parent page ID from project setup wizard (3→2 steps) |
| 0.9.2 | 503 model-busy errors pause immediately instead of retrying |
| 0.9.1 | Idea refinement saves as 'refine_idea' pipeline key |
| 0.9.0 | Interactive mode by default + orchestrator progress notifications |

## v0.8.x (2026-03-04)

| Version | Summary |
|---------|---------|
| 0.8.8 | Fix MongoDB upsert conflict in save_slack_context/save_project_ref |
| 0.8.7 | Fix in-progress ideas invisible to 'list ideas' (3rd fix) |
| 0.8.6 | Fix exec summary callbacks lost by CrewAI asyncio.to_thread |
| 0.8.5 | Requirements approval gate for auto-approve Slack flows |
| 0.8.4 | Fix original idea not persisted in workingIdeas |
| 0.8.3 | Prevent incomplete PRDs from polluting output/prds/ |
| 0.8.2 | Interactive exec summary completion gate |
| 0.8.1 | PRD critique performance optimisation — dedicated critic agent |
| 0.8.0 | Manual archive interaction for idea list |

## v0.7.x (2026-03-02 – 2026-03-04)

| Version | Summary |
|---------|---------|
| 0.7.4 | Rescan exec-summary review gate & failed-idea titles |
| 0.7.3 | Resume flow exec-summary user gates |
| 0.7.2 | Backfill orphaned working ideas |
| 0.7.1 | Fix in-progress ideas invisible to 'list ideas' |
| 0.7.0 | Large-file modular refactoring (10 files split into sub-modules) |

## v0.6.x (2026-03-02)

| Version | Summary |
|---------|---------|
| 0.6.5 | Exec summary completion gate + JSON bloat fix |
| 0.6.4 | Fix premature 'Suggested next step' on create_prd |
| 0.6.3 | Fix '(unknown idea)' on restart |
| 0.6.2 | Fix Slack invalid_blocks on restart — truncate idea text |
| 0.6.1 | Fix empty idea title in listing |
| 0.6.0 | Kill old runs on restart (replaced auto-resume) |

## v0.5.0 (2026-03-02)

Flow-paused retry button + crash-prevention hardening.

## v0.4.x (2026-03-01 – 2026-03-02)

| Version | Summary |
|---------|---------|
| 0.4.7 | Non-interactive exec summary feedback gate |
| 0.4.6 | Ignore messages at other users; general_question intent |
| 0.4.5 | Fix rescan/restart of completed ideas |
| 0.4.4 | Refactor interactions_router + interactive_handlers into packages |
| 0.4.3 | Refactor blocks.py into blocks/ package |
| 0.4.2 | Interactive idea list with Resume/Restart buttons |
| 0.4.1 | list_ideas intent; find_ideas_by_project; 'iterate on an idea' language |
| 0.4.0 | Executive summary interactive feedback loop |

## v0.3.x (2026-03-01)

| Version | Summary |
|---------|---------|
| 0.3.1 | Restart PRD flow intent |
| 0.3.0 | PRD output sanitization, Slack file upload, next-step fix |

## v0.2.x (2026-03-01)

| Version | Summary |
|---------|---------|
| 0.2.2 | Fix PostCompletion delivery crew crash (unescaped curly braces) |
| 0.2.1 | Post-completion next-step prompts |
| 0.2.0 | Auto-resume & observability; heartbeat tracking; CODEX.md |

## v0.1.x (2026-02-14 – 2026-02-28)

| Version | Summary |
|---------|---------|
| 0.1.6 | Comprehensive intent audit — 5 new LLM intents |
| 0.1.5 | Intent fix & project setup wizard |
| 0.1.4 | Thread reply awareness |
| 0.1.3 | Version control & codex module |
| 0.1.2 | Intent classification fix for create_project |
| 0.1.1 | Slack OAuth refactoring — per-team tokens in MongoDB |
| 0.1.0 | Initial release — PRD generation, MongoDB, FastAPI |

---

See also: [[Session Log]], [[Coding Standards]]
