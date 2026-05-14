---
tags:
  - architecture
---

# Module Map

> Source tree with file-level purpose annotations.

## Root Shell Scripts

| File | Purpose |
|------|---------|
| `start_server.sh` | Launch FastAPI server (optionally with ngrok) |
| `start_server_watchdog.sh` | Auto-restart wrapper for start_server.sh with circuit breaker |
| `scripts/dev_setup.sh` | One-command project bootstrap (venv, deps, .env) |

## Top-Level Source (`src/crewai_productfeature_planner/`)

| File | Purpose |
|------|---------|
| `main.py` | CLI entry points, re-exports from sub-modules |
| `version.py` | Canonical version + changelog (CodexEntry list) |
| `_cli_state.py` | PRD state restoration & assembly from MongoDB |
| `_cli_project.py` | Project selection, creation & memory config |
| `_cli_refinement.py` | Idea input, refinement & approval gates |
| `_cli_startup.py` | Startup process cleanup, delivery & recovery |

## Agents (`agents/`)

| File / Dir | Purpose |
|-----------|---------|
| `gemini_utils.py` | Shared Gemini LLM config, model tier defaults |
| `idea_refiner/` | Idea enrichment agent (Gemini, no tools) |
| `product_manager/` | PM agent (Gemini + OpenAI variants, 2 tools) |
| `requirements_breakdown/` | Requirements decomposition agent |
| `ceo_reviewer/` | CEO/Founder reviewer — generates executive product summary (v0.18.0) |
| `eng_manager/` | Engineering Manager — generates engineering plan (v0.18.0) |
| `staff_engineer/` | Staff engineer agent (stub, v0.18.0) |
| `release_engineer/` | Release engineer agent (stub, v0.18.0) |
| `qa_engineer/` | QA engineer agent (stub, v0.18.0) |
| `qa_lead/` | QA lead agent (stub, v0.18.0) |
| `retro_manager/` | Retro manager agent (stub, v0.18.0) |
| `ux_designer/` | UX Designer + Design Partner + Senior Designer — 2-phase UX design flow (v0.20.0, refactored v0.41.0) |
| `engagement_manager/` | Engagement Manager & PRD Orchestrator — handles unknown intents, orchestrates idea-to-PRD lifecycle with heartbeats, user steering, session isolation. Disengaged during active iterations (v0.35.0, expanded v0.39.0, v0.43.0) |
| `idea_agent/` | Idea Agent — context-aware in-thread analyst for active idea iterations, answers questions about current state and produces steering recommendations (v0.43.0) |
| `orchestrator/` | Atlassian publishing + Jira agents |

## APIs (`apis/`)

| File / Dir | Purpose |
|-----------|---------|
| `__init__.py` | FastAPI app factory, router registration, lifespan hooks |
| `_response_cache.py` | TTL-based in-memory cache for paginated list endpoints |
| `shared.py` | FlowRun, FlowStatus, FlowCancelled, approval state, cancel_events |
| `health/router.py` | Assembles health route modules |
| `health/get_health.py` | GET /health — liveness probe |
| `health/get_version.py` | GET /version — version + codex |
| `health/get_slack_token.py` | GET /health/slack-token — token diagnostics |
| `health/post_slack_token_exchange.py` | POST /health/slack-token/exchange — rotate tokens |
| `health/post_slack_token_refresh.py` | POST /health/slack-token/refresh — force refresh |
| `ideas/router.py` | Assembles ideas route modules |
| `ideas/models.py` | IdeaItem, IdeaListResponse, IdeaStatusUpdate, idea_fields() |
| `ideas/get_ideas.py` | GET /ideas — paginated list with filters |
| `ideas/get_idea.py` | GET /ideas/{run_id} — single idea |
| `ideas/patch_idea_status.py` | PATCH /ideas/{run_id}/status — archive/pause |
| `ideas/delete_idea.py` | DELETE /ideas/{run_id} — soft-delete with cascade |
| `projects/router.py` | Assembles projects route modules |
| `projects/models.py` | ProjectCreate, ProjectUpdate, ProjectItem, project_fields() |
| `projects/get_projects.py` | GET /projects — paginated list |
| `projects/get_project.py` | GET /projects/{project_id} — single project |
| `projects/post_project.py` | POST /projects — create project |
| `projects/patch_project.py` | PATCH /projects/{project_id} — update project |
| `projects/delete_project.py` | DELETE /projects/{project_id} — delete project |
| `projects/get_backlog.py` | GET /projects/{project_id}/backlog — kanban-style backlog with blocked_by |
| `approvals/__init__.py` | Approvals module init + router re-export |
| `approvals/router.py` | GET /approvals/pending — cross-project pending approvals queue |
| `approvals/models.py` | ApprovalItem, ApprovalAction, ApprovalListResponse || admin/__init__.py | Admin module init |
| admin/router.py | 5 enterprise admin endpoints (orgs, projects, cascade-preview, reassign, audit-log) |
| admin/models.py | Admin Pydantic models (OrganizationListResponse, CascadePreviewResponse, etc.) |
| admin_deps.py | require_role() dependency factory for flexible per-endpoint RBAC |
| company/__init__.py | Company module init + router re-export |
| company/router.py | Assembles company route modules (org-chart, agents, budget, activity) |
| company/get_org_chart.py | GET /company/org-chart — agent org chart |
| company/get_agents.py | GET /company/agents — list all agents |
| company/get_agent.py | GET /company/agents/{agent_id} — agent detail |
| company/get_budget.py | GET /company/budget — company budget summary |
| company/patch_agent_budget.py | PATCH /company/agents/{agent_id}/budget — update agent budget |
| company/get_activity.py | GET /company/activity — company activity events |
| company/models.py | Company Pydantic models (OrgChartResponse, AgentDetail, BudgetSummaryResponse, etc.) |
| user_profile/__init__.py | User profile module init |
| user_profile/router.py | GET/PATCH /user/profile — merged SSO identity + local preferences |
| user_profile/models.py | UserProfileResponse, UserProfileUpdate |
| dashboard/__init__.py | Dashboard module init |
| dashboard/router.py | GET /dashboard/stats — aggregate idea counts |
| dashboard/models.py | DashboardStats Pydantic model || `prd/router.py` | `/flow/prd/*` — kickoff, approve, pause, resume, runs, jobs |
| `prd/models.py` | Pydantic request/response schemas |
| `prd/service.py` | Flow execution helpers (run, resume, restore state) |
| `prd/_route_timeline.py` | `GET /flow/runs/{run_id}/timeline` — unified PRD journey timeline |
| `prd/_route_versions.py` | `GET /flow/runs/{run_id}/versions` — PRD version history |
| `prd/_route_websocket.py` | `WS /flow/runs/{run_id}/ws` — real-time WebSocket for agent activity |
| `ideation/__init__.py` | Re-exports: broadcast, broadcast_sync, ideation_ws_router, ideation_router |
| `ideation/router.py` | 11 REST endpoints for interactive ideation flow (incl. iteration history) |
| `ideation/models.py` | Pydantic models: ProcessingPhase enum, StructuredIdeationResponse, request/response shapes |
| `ideation/service.py` | Business logic: start, respond, iterate, advance, rollback + processing_status events |
| `ideation/_streaming.py` | LLM token streaming — CrewAI event bus hook, thread-local session context, `agent_token` WS events |
| `ideation/_route_websocket.py` | `WS /ws/ideation/{session_id}` — real-time streaming with JWT auth |
| `project_ideas/__init__.py` | Re-exports: router |
| `project_ideas/router.py` | Assembles sub-routers under `/projects/{project_id}/ideas` |
| `project_ideas/models.py` | Pydantic models for idea CRUD requests/responses |
| `project_ideas/_route_crud.py` | POST, GET list, GET detail, PATCH metadata, PATCH status, DELETE |
| `project_ideas/_route_features.py` | PATCH features endpoint |
| `publishing/` | Publishing automation (router, service, watcher, scheduler) |
| `slack/` | OAuth-only Slack integration (see [[Slack Integration]]) |
| `slack/oauth_router.py` | OAuth v2 callback |
| `slack/verify.py` | HMAC-SHA256 request verification |
| `dashboard/` | Dashboard aggregate statistics (`GET /dashboard/stats`) |
| `integrations/` | Integration status endpoint (Confluence/Jira connection check) |
| `sso/` | SSO auth router — 18 endpoints (login, register, 2FA, logout, etc.) |
| `sso_auth.py` | SSO JWT validation + require_sso_user dependency || rbac.py | Role enum (SYS_ADMIN/ENT_ADMIN/USER), resolve_role() from JWT claims || `sso_webhooks/router.py` | Assembles SSO webhook route modules |
| `sso_webhooks/post_events.py` | POST /sso/webhooks/events — lifecycle events |
| `agentic_team/__init__.py` | Package init + re-export `agentic_team_router` |
| `agentic_team/_config.py` | Env var config: AGENTIC_TEAM_ENABLED, BASE_URL, WEBHOOK_SECRET |
| `agentic_team/_webhook.py` | POST /webhooks/agentic-team — inbound task/epic completion webhook |
| `agentic_team/_service.py` | Outbound API client (features, task status, pipeline dashboard, kickoff) |
| `agentic_team/router.py` | Router composition — includes webhook_router |
| `agent_worker/__init__.py` | Package init + re-export `aw_credentials_router`, `aw_proxy_router` |
| `agent_worker/_config.py` | Env var config: AGENT_WORKER_ENABLED, AGENT_WORKER_BASE_URL |
| `agent_worker/_client.py` | HTTP client with SSO service-token auth, 401 retry, user-token pass-through |
| `agent_worker/_models.py` | Pydantic models for credential proxy endpoints (field normalization) |
| `agent_worker/_route_credentials.py` | POST/DELETE /aw/atlassian/credentials — store-and-forward proxy |
| `agent_worker/_route_proxy.py` | Catch-all /aw/{path} proxy — user-token forwarding, graceful GET degradation |
| `settings/__init__.py` | Package init + re-export `settings_router` |
| `settings/router.py` | GET/PATCH /settings — enterprise configuration (model tier, concurrency, agent labels) |
| `webhook_management/__init__.py` | Package init + re-export all 3 sub-routers |
| `webhook_management/_config.py` | GET /webhook-config — credential status per provider |
| `webhook_management/_subscriptions.py` | 9 endpoints under /webhook-subscriptions (Jira/GitHub CRUD, secret management) |
| `webhook_management/_events.py` | 4 endpoints under /webhook-events (list, detail, replay, backfill) |

## Flows (`flows/`)

| File | Purpose |
|------|---------|
| `prd_flow.py` | Core PRDFlow + re-exports from sub-modules |
| `_constants.py` | Constants, utility functions, exceptions, state model |
| `_agents.py` | Agent creation, parallel execution, decision parsing |
| `_executive_summary.py` | Phase 1 executive summary iteration |
| `_ceo_eng_review.py` | Phase 1.5 CEO review + Engineering plan |
| `_ux_design.py` | UX design engine — 2-phase draft + review, fixed filenames (v0.20.0, refactored v0.41.0) |
| `ux_design_flow.py` | Standalone UX design flow entry point — kick_off_ux_design_flow() (v0.41.0) |
| `_section_loop.py` | Phase 2 section critique→refine loop |
| `_finalization.py` | Save, finalize, post-completion delivery |

## Orchestrator (`orchestrator/`)

| File | Purpose |
|------|---------|
| `orchestrator.py` | AgentOrchestrator, AgentStage, StageResult |
| `stages.py` | Re-export facade (backward compat) |
| `_helpers.py` | Credential checks, delivery status |
| `_idea_refinement.py` | `build_idea_refinement_stage(flow)` |
| `_requirements.py` | `build_requirements_breakdown_stage(flow)` |
| `_confluence.py` | `build_confluence_publish_stage(flow)` |
| `_jira.py` | Phased Jira stages (skeleton, epics, subtasks, kanban tasks) |
| `_pipelines.py` | `build_default_pipeline()`, `build_post_completion_pipeline()` |
| `_post_completion.py` | Post-completion crew (Confluence + Jira) |
| `_startup_review.py` | Startup PRD discovery and publishing |
| `_startup_delivery.py` | Startup pending delivery execution |

## MongoDB (`mongodb/`)

| File / Dir | Purpose |
|-----------|---------|
| `client.py` | `get_db()`, synchronous pymongo connection management |
| `async_client.py` | `get_async_db()`, Motor async client for API endpoints |
| `_tenant.py` | `TenantContext`, `tenant_filter()`, `tenant_fields()` — multi-tenancy query scoping |
| `crew_jobs/` | Async job tracking (create, update, fail, reactivate) |
| `ideas/` | Idea entities CRUD (create, get, list, update, status, features, completion, design_url, delete) |
| `working_ideas/` | In-progress PRD persistence (4 sub-modules) |
| `product_requirements/` | Completed PRD + delivery records |
| `agent_interactions/` | Slack interaction logging (fine-tuning data) |
| `project_config/` | Per-project settings (Jira key, Confluence space) |
| `project_memory/` | Project-level memory store |
| `slack_oauth/` | Slack OAuth token persistence |
| `user_session/` | User session management |
| `user_suggestions/` | Ambiguous intent tracking for self-learning |
| `users/` | Application user accounts (SSO + Slack provisioned) |
| `ideation_sessions/` | Interactive ideation session CRUD (step_to_name, count, paginate, metadata) |
| `knowledge_documents/` | Knowledge document metadata CRUD (uploads + URL ingestions, review results) |
| `knowledge_summaries/` | Aggregated knowledge summaries per project (unified bullets, topics, contradictions) |
| `code_repos/` | Registered GitHub repos per project (OAuth tokens, analysis results) |
| `integration_credentials/` | Per-tenant integration credential storage with Fernet encryption |
| `enterprise_settings/` | Per-enterprise settings (model tier, concurrency, log level, agent labels) |
| `webhook_subscriptions/` | Webhook subscription CRUD (Jira/GitHub), secret hashing, repo management |

## Services (`services/`)

| File | Purpose |
|------|---------|
| `gcs_paths.py` | Unified GCS bucket name resolution (`{SERVER_ENV}-idea-foundry`) and multi-tenant path builders |
| `knowledge_storage.py` | GCS upload/download/delete for knowledge document files |
| `knowledge_aggregator.py` | Orchestrates Content Reviewer agent + summary aggregation |
| `github_service.py` | GitHub OAuth flow, shallow clone, Coding Agent orchestration |

## Tools (`tools/`)

| File | Purpose |
|------|---------|
| `confluence_tool.py` | Confluence REST API publishing |
| `jira_tool.py` | Jira REST API shim → `jira/` package |
| `jira/` | Jira operations, helpers, ADF converter |
| `slack_tools.py` | Send/read Slack messages (OAuth retained) |
| `slack_token_manager.py` | Token rotation, exchange, persistence |
| `token_refresh_scheduler.py` | Background token refresh daemon (proactive rotation) |
| `file_write_tool.py` | PRD file writer |
| `file_read_tool.py` | File reader |
| `directory_read_tool.py` | Directory listing |
| `gemini_chat.py` | Gemini LLM intent classification |
| `openai_chat.py` | OpenAI LLM intent classification |

## Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `logging_config.py` | Structured logging setup |
| `preflight.py` | Startup environment checks |
| `retry.py` | Crew kickoff retry wrapper + error classification |
| `crewai_bus_fix.py` | CrewAI event-bus recovery — detects/repairs dead `crewai_event_bus` singleton |
| `setup_mongodb.py` | Collection & index bootstrap |
| `ngrok_tunnel.py` | ngrok tunnel management |
| `slack_config.py` | Slack manifest validation |
| `memory_loader.py` | Project memory resolution |
| `confluence_xhtml.py` | Markdown → Confluence XHTML converter |

## Agents (new modules)

| Folder | Purpose |
|--------|---------||
| `agents/content_reviewer/` | CrewAI agent — reviews documents (summary, key_bullets, topics, confidence) |
| `agents/coding_agent/` | CrewAI agent — analyzes repos (architecture, tech_stack, apis, schemas, dependencies) |
| `knowledge_sources.py` | Knowledge file loading, caching, and builder factories (8 knowledge files: user_preference, project_architecture, prd_guidelines, idea_refinement, review_criteria, engineering_standards, ux_design_standards, agent_roles_and_workflow) |
| `project_knowledge.py` | Obsidian-style project knowledge base builder (project pages, completed idea pages, agent context) |
| `migrate_output_dirs.py` | One-time script: migrate output files to project-based directories (delete after use) |
| `sso_bootstrap.sh` | One-time SSO app bootstrap: admin login, app approval, credential save, public key download |
| `cleanup_orphan_projects.py` | One-time CLI: find/archive/delete orphaned project_id refs in workingIdeas |

## Components (`components/`)

| File | Purpose |
|------|---------|
| `cli.py` | Interactive CLI flow runner |
| `startup.py` | Server startup recovery tasks |
| `resume.py` | Resume paused runs |
| `document.py` | Document formatting utilities |

---

See also: [[Project Overview]], [[Orchestrator Overview]]
