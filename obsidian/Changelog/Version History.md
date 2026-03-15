# Version History

> Full changelog from v0.1.0 to current. Updated every session.

## v0.20.x (2026-03-13)

| Version | Summary |
|---------|---------|
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
