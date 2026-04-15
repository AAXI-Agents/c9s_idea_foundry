---
tags:
  - changelog
  - versions
aliases:
  - Changelog
  - Release Notes
created: 2026-02-14
updated: 2026-04-15
---

# Version History

> Weekly changelog from v0.1.0 to current. Each week groups all version bumps with summaries.

---

## Week of 2026-04-13

| Version | Date | Summary |
|---------|------|---------|
| 0.72.1 | 04-15 | SSO proxy path fix — all upstream SSO server calls now use the correct `/sso/` prefix. Fixed 13 proxy paths in router.py and 2 paths in sso_auth.py that omitted the `/sso` segment, causing 404 errors from the upstream SSO server. 48 SSO tests pass |
| 0.72.0 | 04-15 | Multi-tenancy data isolation Phase 1. New `_tenant.py` module (TenantContext, tenant_filter, tenant_fields). All 9 repositories updated with tenant param. API layer injects TenantContext.from_user(). Slack path resolves tenant from slackOAuth. Tenant indexes on all collections. Migration script for backfill. 15 new regression tests. 3 web UI gap tickets |
| 0.71.2 | 04-13 | CRITICAL FIX Phase 2: Comprehensive dedup fallback. v0.71.1 relied on idea_normalized field (absent on older documents), causing dedup to silently miss existing duplicates. Fix: Two-phase _match_by_idea_text() — fast indexed lookup then in-memory fallback on raw idea field. Self-healing backfill of idea_normalized. Multi-scope search (project then channel). API routes reject duplicates before run_id allocation (HTTP 409). Startup calls fail_unfinalized_on_startup() to clean orphaned flows. One-time scripts/dedup_working_ideas.py for backfill + archival. 5 new fallback tests |
| 0.71.1 | 04-13 | CRITICAL FIX: Duplicate-idea dedup in kick_off_prd_flow. Root cause: zero deduplication at PRD flow entry point — same idea created 5 run_ids with 1000+ Jira tickets. Fix: find_active_duplicate_idea() blocks inprogress/paused duplicates. find_recent_duplicate_idea() now falls back to channel scope when project_id is missing. Dual guard in kick_off_prd_flow + router.py + API route_actions.py. 14 new tests |

## Week of 2026-04-06

| Version | Date | Summary |
|---------|------|---------|
| 0.59.4 | 04-07 | Fix SSO token refresh 401 — missing client_id. Token refresh proxy did not include SSO_CLIENT_ID in the payload, causing the SSO server to reject requests with 401 Unauthorized. Now injects client_id matching the direct login endpoint pattern |
| 0.59.5 | 04-07 | Fix GET /flow/runs/{run_id} 404 after server restart. Endpoint only checked in-memory `runs` dict (lost on restart). Now falls back to MongoDB (crewJobs + workingIdeas) via restore_prd_state(). GET /flow/runs list also includes persistent MongoDB jobs |
| 0.60.0 | 04-07 | User Feedback gap ticket resolution — wired backend infrastructure to flow execution. Version snapshots auto-saved on finalization + Confluence publish. Section conversation messages persisted during draft-critique-refine loop. Cross-section summary notes on approval. Timeline API emits section_approved annotations. 4 fully-answered gaps resolved, 4 follow-up clarity gaps created |
| 0.61.0 | 04-07 | Gap ticket resolution — 4 user-answered follow-up tickets processed. Engineering Plan task prompt updated to progressive disclosure format (high-level summary + Technical Deep-Dive sections). Added board_style field to projectConfig schema (scrum/kanban). Webapp monorepo decision recorded (keep separate). Created codex task files for complex flow changes: idea refinement 3-options at key decision points, Jira kanban flat-task generation |
| 0.61.1 | 04-08 | Test suite optimization — full regression from 480s to 45s (90% faster). Session-scoped Agent warmup fixture. Mock LLM builders for UX/PM/Critic agents. Flows conftest. Fixed flaky retry + dm_pending tests. Session manager state cleanup in Slack conftest. All 2819 tests under 1.5s |
| 0.62.0 | 04-09 | Idea Refinement 3-Options — generate 3 alternative directions at key decision points (after 3 auto cycles, low confidence, or direction change). Kanban Board Style — flat-task Jira ticketing (2-phase skeleton→tasks) for kanban projects. Fixed low_confidence threshold (6.0→3.0 for 1-5 scale). 30 new tests (19 kanban + 11 options) |
| 0.62.1 | 04-10 | Log error investigation & performance fixes — Jira issue-link 404s fixed (split comma-separated keys). Slack file upload retry (2 attempts + backoff). API latency middleware (X-Process-Time header, slow request warnings >2s). SSO introspection optimised (reuse httpx client). All 2862 tests pass |
| 0.62.2 | 04-10 | API latency fix — GET /projects and GET /ideas 10s→<300ms. MongoDB exclusion projection for ideas (removes 80%+ document size). run_in_executor for async-safe DB calls. estimated_document_count for unfiltered projects. New created_at DESC indexes on projectConfig + workingIdeas. VALID_PAGE_SIZES expanded to {5,6,10,25,50}. All 2862 tests pass |
| 0.63.0 | 04-10 | Performance recommendations implemented. Motor async MongoDB driver for GET /ideas and GET /projects (replaces run_in_executor). Response cache with 5s TTL for paginated list endpoints. Index coverage analysis script (explain_queries.py). User chose Option B (keep exclusion projection). New dependencies: motor>=3.3. 2872 tests pass |
| 0.63.1 | 04-10 | SSO userinfo 401 loop fix — _introspect_remotely missing SSO_CLIENT_ID in body (RFC 7662). Public key LRU cache auto-clears on InvalidSignatureError. Improved introspection error logging (response body). 2874 tests pass |
| 0.63.2 | 04-10 | SSO OAuth deep fix — 3-phase token validation with automatic key rotation recovery. Introspection sends Authorization: Bearer header. New _fetch_and_save_public_key() auto-downloads RSA key from SSO server. require_sso_user, /userinfo, /status all use 3-phase flow (local decode → key fetch retry → remote introspect). 5 new SSO tests. 2877 tests pass |
| 0.63.3 | 04-10 | SSO auth aligned with SSO server OpenAPI spec (v0.4.0). 3 bugs fixed: introspect sends client_secret in body (not Authorization header), public key field name corrected to public_key_pem, JWKS support added (GET /.well-known/jwks.json with JWK→PEM conversion). 2878 tests pass |
| 0.64.0 | 04-10 | SSO validation strategy + background key scheduler (GAP ticket resolved). Remote-first validation: introspect first, local decode fallback. Background key refresh daemon (6h interval + startup). 2881 tests pass |
| 0.64.1 | 04-10 | Fix GET /ideas and GET /projects 400 errors. Web app page_size not in strict allowlist. Replaced with range check (1-100). Dashboard polling fixed. 2881 tests pass |
| 0.65.0 | 04-10 | Web-app API gap closure (A1–A3). New GET /dashboard/stats (MongoDB aggregation), POST /flow/ux/kickoff (body-based), GET /flow/ux/status/{run_id} (UXDesignStatusResponse). Fixed GET /flow/runs/{run_id} DB fallback to include ux_design_status/content. 19 new tests. 2900 tests pass |
| 0.66.0 | 04-11 | WebSocket real-time agent activity (Gap A6). WS /flow/runs/{run_id}/ws — bidirectional WebSocket with status_update, agent_activity, progress events. Supports ping/pong and get_status. Gap A4 already resolved (PATCH /user/profile exists). Gap A5 is frontend-only. 10 new tests. 2910 tests pass |
| 0.67.0 | 04-11 | Fix critical bug: project_id validation on PRD kickoff. POST /flow/prd/kickoff returns 422 for non-existent project_id. Slack kickoff validates and clears invalid project_id. save_project_ref() defence-in-depth rejects phantom projects. Prevents orphaned ideas (proj-1 had 67). GAP ticket for stale data cleanup. 4 new tests |
| 0.68.0 | 04-11 | Stale project cleanup + duplicate-idea protection. R1+R2+R3: cleanup_orphan_projects.py CLI (archive/delete orphaned project refs). S1A: 24h duplicate-idea cooldown (409 on API, warning in Slack). idea_normalized field for text comparison. find_recent_duplicate_idea query. 17 new tests |
| 0.68.1 | 04-11 | Fix IdeaItem ux_design_status crash. idea_fields() returned None when both ux_design_status and figma_design_status were null in MongoDB, causing Pydantic ValidationError on GET /ideas/. Added trailing `or ""` fallback. 6 regression tests |
| 0.69.0 | 04-12 | Deprecate legacy API endpoints (/generate, /publish, /confluence/*). Preflight checks validate credentials on startup. 4 endpoints deprecated with 410 Gone responses |
| 0.70.0 | 04-12 | GCP auto-scale statelessness audit. (1) File-based output → GCS adapter + MongoDB fallback. (2) PRDFlow singleton → per-request instances. (3) Scheduler → sharded leader election. (4) Rotating Slack tokens → encrypted storage via KMS. (5) New env vars: GCS_OUTPUT_BUCKET, GCS_OUTPUT_PREFIX |
| 0.70.1 | 04-12 | CRITICAL FIX: Stop runaway Jira ticket creation. _create_pending_jira() replaced with no-op stub. _discover_pending_deliveries() re-evaluation removed. Jira tickets ONLY via interactive Slack flow or manual API |
| 0.63.1 | 04-10 | SSO userinfo 401 loop fix. Remote introspection missing client_id (RFC 7662). Public key LRU cache auto-clears on InvalidSignatureError (SSO key rotation). Improved introspect error logging with response body. 2 new SSO tests |

## Week of 2026-03-31

| Version | Date | Summary |
|---------|------|---------|
| 0.59.3 | 04-06 | SSO bootstrap fix — multi-environment redirect_uris. App was registered but client_secret/app_id not saved. Script now registers with ALL redirect_uris (DEV+UAT+PROD) in one registration. Added SSO_JWT_PUBLIC_KEY_PATH auto-update, webhook subscription registration, smart existing-app detection. UAT/PROD deployment no longer requires script re-run |
| 0.59.2 | 04-04 | SSO bootstrap & deployment validation. Configured .env with SSO vars, downloaded RSA public key. Created sso_bootstrap.sh for admin login, app approval, credential save. Added SSO checks to dev_setup.sh for UAT/PROD. Fixed _introspect_remotely async (event-loop blocking). Root cause: app submitted but never approved (AUTH_2009) |
| 0.59.1 | 04-08 | SSO proxy async refactor — fix 502 login errors. Converted all 15 synchronous httpx.post calls to async httpx.AsyncClient via _sso_proxy_post helper. ConnectError → 502, TimeoutException → 504. Updated 29 SSO tests |\n| 0.59.0 | 04-08 | Gap ticket backend features. Timeline API (GET /flow/runs/{run_id}/timeline): unified PRD journey view. PRD version tracking (save/get version snapshots + GET /flow/runs/{run_id}/versions). Confluence preview (GET /publishing/confluence/{run_id}/preview). Section conversation schema (per-section message threading + summary notes). 30 new tests |
| 0.58.0 | 04-07 | UX Design review gate + flow control panel. Summary review gate after Phase 2 (Approve/Skip). Persistent control panel with [Pause Flow] / [Cancel] buttons. CEO + UX design gates added to cancel unblock. Fixed version.py date bug. Updated gap tickets |
| 0.57.0 | 04-06 | Agent activity messages + requirements transparency. `agent_activity` progress events for all 6 agents (PM, Critic, CEO, Eng Manager, UX Designer, Senior Designer) with agent-specific emojis in Slack. `requirements_assumptions` event shows AI evaluation after breakdown. `ux_design_draft_complete` and `ux_design_review_start` events handled in Slack. Deleted 9 resolved gap tickets. 4 gap tickets updated with v0.57.0 implementation |
| 0.56.0 | 04-05 | Flow audit gap implementation. CEO Review approval gate (callback + Block Kit + dispatch + auto/blocking factories). Transparent critique (Critic reasoning posted to Slack). Pipeline step counter ([1/3] in progress messages). Project config: `design_preferences`, `review_checklists`, `technical_profile` fields. All 10 audit gap tickets updated with user decisions + 3 follow-up questions |
| 0.55.0 | 04-04 | Resolved 8 gap tickets + 1 in-progress. New `GET/PATCH /user/profile` with `userPreferences` collection, `POST /flow/ux-design/{run_id}` endpoint, `iterate_idea` distinct Slack flow. DESIGN.md 8 decisions resolved, README 20-intent list + 15-version history, 22 boilerplate CRs cleaned. Web app screen gap analysis |
| 0.54.2 | 04-03 | Full codebase audit — 9 gap tickets created (5 needing user input, 4 quick-win doc fixes) |
| 0.54.1 | 04-03 | User Feedback gap ticket system. Created `User Feedback/_template.md` with structured template. Updated CODEX.md with Gap Ticket Workflow section |
| 0.54.0 | 04-03 | Obsidian API docs cleanup. Deleted 7 redundant domain summary files, migrated unique content (schemas, tables, reference data) to per-route files, fixed 50+ stale wiki links across Database pages, updated CODEX.md references |
| 0.53.0 | 04-03 | API per-route restructuring. Split monolithic router files into individual route modules: Health (5 files), Ideas (3 + models), Projects (5 + models), SSO Webhooks (moved to package). Each route file has docstring with request/response/DB algorithm. 1115 API tests passing |
| 0.52.0 | 04-02 | SSO authentication router — full C9S SSO integration. 18 `/auth/sso/*` endpoints: OAuth2 login, direct login, 2FA, Google Sign-In, registration, password reset, token refresh, re-auth, logout. All proxy to SSO server via httpx. 29 new tests |
| 0.51.0 | 04-02 | Obsidian vault restructure (docs-only). Weekly changelog, YAML frontmatter on 103 files, 6 API docs completed (DB algorithms for Slack/Publishing), 7 old API files deprecated, Home.md updated with API nav |
| 0.50.0 | 04-01 | Activity Log & Integration Status APIs + obsidian restructure. `GET /flow/runs/{run_id}/activity` — agent interaction events. `GET /integrations/status` — Confluence/Jira connection check. 32 per-route API docs. 9 new tests. 2746 passing |
| 0.49.0 | 04-01 | Web app gap analysis API updates. `title` + `project_id` on kickoff; `description` on projects; `title` on ideas. [CHANGE] markers for 4 low-confidence APIs |
| 0.48.2 | 03-31 | Model defaults & test perf fixes. Reverted DEFAULT_* to string fallbacks; fast-path mocks. 2738 passing |
| 0.48.1 | 03-31 | Per-section LLM model tier optimisation. Complex sections use research model; structured use basic (~44% fewer research calls). 2738 passing |
| 0.48.0 | 03-31 | Fix CrewAI event-bus shutdown corruption (`cannot schedule new futures after shutdown`). New `crewai_bus_fix.py`. 2724 passing |

---

## Week of 2026-03-24

| Version | Date | Summary |
|---------|------|---------|
| 0.47.2 | 03-30 | Thread session isolation — reject non-owner replies in Slack threads. 2715 passing |
| 0.47.1 | 03-30 | Fix Confluence published checkmarks — delivery record as sole authority. 2703 passing |
| 0.47.0 | 03-30 | Background Slack token refresh scheduler — prevents token rotation death spiral. 2699 passing |
| 0.46.1 | 03-30 | Engagement Manager delivery failure detection + startup token validation. 2681 passing |
| 0.46.0 | 03-30 | Enhanced knowledge base — 5 new knowledge files for agents |
| 0.45.1 | 03-30 | Fix test suite latency — 596s to 79s (7.6x speedup). 2653 passing |
| 0.45.0 | 03-29 | Complete Figma removal — UX design markdown-only. Removed `tools/figma/` |
| 0.44.0 | 03-29 | PRD Flow obsidian docs breakdown — 10 individual flow step pages |
| 0.43.9 | 03-29 | Agent Roles obsidian docs breakdown — 12 individual agent pages |
| 0.43.8 | 03-29 | MongoDB Schema obsidian docs breakdown — 9 individual collection pages |
| 0.43.7 | 03-29 | API Obsidian docs breakdown — 7 domain pages with field-level schemas |
| 0.43.6 | 03-29 | Comprehensive API + Obsidian docs for web app integration |
| 0.43.5 | 03-28 | Fix 47-second server startup regression — lazy imports + two-phase query |
| 0.43.4 | 03-28 | Fix thread-history mention gate — bot responds to follow-ups |
| 0.43.3 | 03-28 | EM & Idea Agent latency — direct Gemini REST (~200-800ms vs ~2-4s) |
| 0.43.2 | 03-28 | Immediate 'Thinking...' acknowledgment on all Slack interactions |
| 0.43.1 | 03-27 | Reduce Slack iteration noise; completion summaries with content preview |
| 0.43.0 | 03-27 | New Idea Agent — context-aware in-thread analyst for active flows |
| 0.42.4 | 03-27 | ISO 27001 security audit — all HIGH/MEDIUM findings remediated |
| 0.42.3 | 03-27 | Root-cause fix: `save_iteration()` resurrecting archived ideas |
| 0.42.2 | 03-27 | Fix archive cancellation for resumed/auto-resumed flows |
| 0.42.1 | 03-27 | Archive stops active flows + `FlowCancelled` exception system |
| 0.42.0 | 03-26 | Summarize ideas intent, userSuggestions collection, admin config guard |
| 0.41.0 | 03-26 | UX Design flow refactor — standalone 2-phase post-PRD flow |
| 0.40.0 | 03-25 | Engagement Manager project knowledge awareness |
| 0.39.0 | 03-24 | Engagement Manager PRD Orchestrator — full idea-to-PRD lifecycle |
| 0.38.0 | 03-24 | Publication safety overhaul — user-triggered publishing only |

---

## Week of 2026-03-17

| Version | Date | Summary |
|---------|------|---------|
| 0.37.1 | 03-24 | Slack thread recovery & flow-aware summaries |
| 0.37.0 | 03-23 | Server crash-prevention hardening — `_safe_handler()` wraps 13 dispatches |
| 0.36.0 | 03-23 | Fully automated PRD flow + active-flow config guard |
| 0.35.0 | 03-22 | Engagement Manager agent — context-aware conversational responses |
| 0.34.0 | 03-22 | Project knowledge base — Obsidian-style folders for agent learning |
| 0.33.0 | 03-22 | Output file reorganisation — project-scoped dirs |
| 0.32.1 | 03-21 | Fix files:write Slack scope; admin cache TTL; truncation limit |
| 0.32.0 | 03-21 | Bot only responds in threads where @mentioned |
| 0.31.2 | 03-21 | Slack file-upload fallback for truncated content |
| 0.31.1 | 03-21 | Fix 'configure tools' misrouted to project config |
| 0.31.0 | 03-21 | Interaction-first rule for ALL prompts — Block Kit only |
| 0.30.3 | 03-20 | Defense-in-depth admin gates in handlers |
| 0.30.2 | 03-20 | Admin-gated project configuration |
| 0.30.1 | 03-20 | Complete intent-to-button coverage (16 button constants) |
| 0.30.0 | 03-20 | All bot commands clickable — Block Kit buttons replace text |
| 0.29.2 | 03-20 | Fix bare 'configure' not recognised |
| 0.29.1 | 03-20 | Fix bot not responding after cache expiry |
| 0.29.0 | 03-20 | Route Slack thread replies to active PRD flow |
| 0.28.2 | 03-20 | Suppress redundant 'PRD Generation Complete' notification |
| 0.28.1 | 03-20 | Fix Confluence 'not configured' false negative |
| 0.28.0 | 03-20 | Confluence/Jira titles use idea text |
| 0.27.1 | 03-17 | MongoDB database name fully environment-driven |
| 0.27.0 | 03-17 | SERVER_ENV three-tier public URL resolution |
| 0.26.0 | 03-17 | Logging standard & incident-trace instrumentation |
| 0.25.0 | 03-17 | SSO-based user_id on all API endpoints |

---

## Week of 2026-03-10

| Version | Date | Summary |
|---------|------|---------|
| 0.24.0 | 03-16 | CRUD APIs with pagination for Projects and Ideas |
| 0.23.0 | 03-16 | SSO "Idea Foundry" whitelisting — RS256 JWT |
| 0.22.3 | 03-16 | Fix UX Design task producing no output |
| 0.22.2 | 03-16 | LLM token optimisation; Manual UX Design button |
| 0.22.1 | 03-16 | Project config wizard + Config button |
| 0.22.0 | 03-16 | Figma project config + OAuth + REST API |
| 0.21.1 | 03-16 | Fix 12/10 section count in idea list |
| 0.21.0 | 03-16 | Figma Make — Playwright browser automation |
| 0.20.2 | 03-13 | Retry UX Design dispatch fix + test performance |
| 0.20.1 | 03-13 | Resume gate bypass fix |
| 0.20.0 | 03-13 | UX Designer agent & Figma Make integration |
| 0.19.0 | 03-13 | Jira Review & QA Test sub-tasks (5-phase pipeline) |
| 0.18.0 | 03-13 | GStack agent integration — 7 new roles, Phase 1.5 |
| 0.17.1 | 03-13 | Fix intent misclassification (jira in idea text) |
| 0.17.0 | 03-13 | MongoDB Atlas migration |
| 0.16.2 | 03-10 | Server crash resilience — watchdog, run_id fix, error handling |
| 0.16.1 | 03-10 | Fix post-completion flow not prompting user |
| 0.16.0 | 03-10 | PRD section generation performance — condensed context |

---

## Week of 2026-03-03

| Version | Date | Summary |
|---------|------|---------|
| 0.15.15 | 03-10 | Fix progress heartbeat in interactive flows |
| 0.15.14 | 03-10 | Archive button on product list |
| 0.15.13 | 03-10 | Eliminate 'unknown' Jira ticket types |
| 0.15.12 | 03-08 | Persist Jira Epics & Stories for crash resilience |
| 0.15.11 | 03-08 | Remove autonomous Jira detection |
| 0.15.10 | 03-08 | Fix delivery state reset by scheduler |
| 0.15.9 | 03-08 | Fix Confluence publish notification |
| 0.15.8 | 03-08 | Critical fix: Jira approval gate — 23 regression tests |
| 0.15.6 | 03-08 | Fix shutdown error handling |
| 0.15.5 | 03-08 | Improve LLM error handling for HTTP 500 |
| 0.15.4 | 03-07 | Fix thread-reply intent regression |
| 0.15.3 | 03-07 | Fix 'create idea' not recognised |
| 0.15.2 | 03-07 | Fix 'configure memory' intent |
| 0.15.1 | 03-07 | Fix Slack bot not responding — env var fallback |
| 0.15.0 | 03-07 | MongoDB bootstrap on startup; dev_setup.sh |
| 0.14.6 | 03-07 | Fix product list UX for skeleton_pending |
| 0.14.5 | 03-07 | Persist Jira skeleton to MongoDB |
| 0.14.4 | 03-07 | Fix product list 'Jira complete' in progress |
| 0.14.3 | 03-07 | Fix 'list ideas' showing 'No ideas found' |
| 0.14.2 | 03-07 | Fix Flow.state read-only crash |
| 0.14.1 | 03-07 | Fix Jira skeleton for completed PRDs |
| 0.14.0 | 03-07 | Delivery action buttons & create_jira intent |
| 0.13.2 | 03-07 | Fix TokenManager/CrewJobs resume bugs |
| 0.13.1 | 03-07 | Fix hallucinated Confluence URLs in Jira |
| 0.13.0 | 03-07 | Remove unused web research tools |
| 0.12.5 | 03-05 | Fix thread_broadcast dropped messages |
| 0.12.4 | 03-05 | Acknowledge user feedback on exec summary |
| 0.12.3 | 03-05 | Fix flow ordering — requirements after exec summary |
| 0.12.2 | 03-05 | Fix interactive flow skipping exec summary gate |
| 0.12.1 | 03-05 | Fix Jira ticket persistence |
| 0.12.0 | 03-05 | Fix Jira API v3 400 errors — ADF format |
| 0.11.2 | 03-05 | Fix PRD section pausing on 429 rate-limit |
| 0.11.1 | 03-05 | Fix 'update knowledge' misclassification |
| 0.11.0 | 03-05 | Fix autonomous Jira re-creating tickets |
| 0.10.2 | 03-05 | Migrate Jira API v2 to v3 |
| 0.10.1 | 03-05 | Fix missing Jira skeleton button |
| 0.10.0 | 03-05 | Jira phased-approval overhaul |
| 0.9.16 | 03-04 | Confluence URL as native Slack button |
| 0.9.15 | 03-04 | Fix product list: confluence_published |
| 0.9.14 | 03-04 | Product list: incomplete steps as buttons |
| 0.9.13 | 03-04 | Fix product list: URL fallback, status icons |
| 0.9.12 | 03-04 | 'list products' intent with delivery buttons |
| 0.9.11 | 03-04 | Fix autonomous Jira bypassing approval |
| 0.9.10 | 03-04 | Fix idea list: exclude completed/archived |
| 0.9.9 | 03-04 | Fix 503 retry resume |
| 0.9.8 | 03-04 | Standardise productRequirements status |
| 0.9.7 | 03-04 | Fix Confluence data to wrong collection |
| 0.9.6 | 03-04 | Fix KeyError 'approved_skeleton' |
| 0.9.5 | 03-04 | Jira skeleton next-step hint |
| 0.9.4 | 03-04 | Remove parent page ID from LLM surfaces |
| 0.9.3 | 03-04 | Remove parent page ID from setup wizard |
| 0.9.2 | 03-04 | 503 model-busy pauses immediately |
| 0.9.1 | 03-04 | Idea refinement saves as 'refine_idea' |
| 0.9.0 | 03-04 | Interactive mode + orchestrator progress |
| 0.8.8 | 03-04 | Fix MongoDB upsert conflict |
| 0.8.7 | 03-04 | Fix in-progress ideas invisible (3rd fix) |
| 0.8.6 | 03-04 | Fix exec summary callbacks lost by asyncio |
| 0.8.5 | 03-04 | Requirements approval gate for auto-approve |
| 0.8.4 | 03-04 | Fix original idea not persisted |
| 0.8.3 | 03-04 | Prevent incomplete PRDs in output/prds/ |
| 0.8.2 | 03-04 | Interactive exec summary completion gate |
| 0.8.1 | 03-04 | PRD critique performance — dedicated critic agent |
| 0.8.0 | 03-04 | Manual archive interaction for idea list |

---

## Week of 2026-02-24

| Version | Date | Summary |
|---------|------|---------|
| 0.7.4 | 03-02 | Rescan exec-summary review gate & failed-idea titles |
| 0.7.3 | 03-02 | Resume flow exec-summary user gates |
| 0.7.2 | 03-02 | Backfill orphaned working ideas |
| 0.7.1 | 03-02 | Fix in-progress ideas invisible to 'list ideas' |
| 0.7.0 | 03-02 | Large-file modular refactoring (10 files split) |
| 0.6.5 | 03-02 | Exec summary completion gate + JSON bloat fix |
| 0.6.4 | 03-02 | Fix premature 'Suggested next step' |
| 0.6.3 | 03-02 | Fix '(unknown idea)' on restart |
| 0.6.2 | 03-02 | Fix Slack invalid_blocks — truncate idea text |
| 0.6.1 | 03-02 | Fix empty idea title in listing |
| 0.6.0 | 03-02 | Kill old runs on restart |
| 0.5.0 | 03-02 | Flow-paused retry button + crash hardening |
| 0.4.7 | 03-02 | Non-interactive exec summary feedback gate |
| 0.4.6 | 03-01 | Ignore messages at other users; general_question intent |
| 0.4.5 | 03-01 | Fix rescan/restart of completed ideas |
| 0.4.4 | 03-01 | Refactor interactions_router + interactive_handlers |
| 0.4.3 | 03-01 | Refactor blocks.py into blocks/ package |
| 0.4.2 | 03-01 | Interactive idea list with Resume/Restart buttons |
| 0.4.1 | 03-01 | list_ideas intent; 'iterate on an idea' phrasing |
| 0.4.0 | 03-01 | Executive summary interactive feedback loop |
| 0.3.1 | 03-01 | Restart PRD flow intent |
| 0.3.0 | 03-01 | PRD output sanitization, Slack file upload, next-step fix |
| 0.2.2 | 03-01 | Fix PostCompletion delivery crew crash |
| 0.2.1 | 03-01 | Post-completion next-step prompts |
| 0.2.0 | 03-01 | Auto-resume & observability; heartbeat; CODEX.md |

---

## Week of 2026-02-10

| Version | Date | Summary |
|---------|------|---------|
| 0.1.6 | 02-28 | Comprehensive intent audit — 5 new LLM intents |
| 0.1.5 | 02-28 | Intent fix & project setup wizard |
| 0.1.4 | 02-28 | Thread reply awareness |
| 0.1.3 | 02-28 | Version control & codex module |
| 0.1.2 | 02-28 | Intent classification fix for create_project |
| 0.1.1 | 02-25 | Slack OAuth refactoring — per-team tokens in MongoDB |
| 0.1.0 | 02-14 | Initial release — PRD generation, MongoDB, FastAPI |

---

> [!info] Version Scheme
> **X.Y.Z** — X = release (user), Y = major feature (agent), Z = bug fix (agent).
> Version source: `version.py` `_CODEX` list.

See also: [[Session Log]], [[Coding Standards]]
