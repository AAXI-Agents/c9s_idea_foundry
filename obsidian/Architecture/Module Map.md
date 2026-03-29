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
| `shared.py` | FlowRun, FlowStatus, FlowCancelled, approval state, cancel_events |
| `health/router.py` | `/health`, token management endpoints |
| `prd/router.py` | `/flow/prd/*` — kickoff, approve, pause, resume, runs, jobs |
| `prd/models.py` | Pydantic request/response schemas |
| `prd/service.py` | Flow execution helpers (run, resume, restore state) |
| `publishing/` | Publishing automation (router, service, watcher, scheduler) |
| `projects/` | Projects CRUD router (list/get/create/update/delete with pagination) |
| `ideas/` | Ideas CRUD router (paginated list, get, archive/pause with filters) |
| `slack/` | Full Slack integration (see [[Slack Integration]]) |
| `slack/_slack_file_helper.py` | Truncation + file upload for long Slack content (v0.31.2) |
| `sso_auth.py` | SSO JWT validation + require_sso_user dependency |
| `sso_webhooks.py` | SSO webhook receiver for user lifecycle events |

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
| `_jira.py` | Phased Jira stages (skeleton, epics, subtasks) |
| `_pipelines.py` | `build_default_pipeline()`, `build_post_completion_pipeline()` |
| `_post_completion.py` | Post-completion crew (Confluence + Jira) |
| `_startup_review.py` | Startup PRD discovery and publishing |
| `_startup_delivery.py` | Startup pending delivery execution |

## MongoDB (`mongodb/`)

| File / Dir | Purpose |
|-----------|---------|
| `client.py` | `get_db()`, connection management |
| `crew_jobs/` | Async job tracking (create, update, fail, reactivate) |
| `working_ideas/` | In-progress PRD persistence (4 sub-modules) |
| `product_requirements/` | Completed PRD + delivery records |
| `agent_interactions/` | Slack interaction logging (fine-tuning data) |
| `project_config/` | Per-project settings (Jira key, Confluence space) |
| `project_memory/` | Project-level memory store |
| `slack_oauth/` | Slack OAuth token persistence |
| `user_session/` | User session management |
| `user_suggestions/` | Ambiguous intent tracking for self-learning |
| `users/` | Application user accounts (SSO + Slack provisioned) |

## Tools (`tools/`)

| File | Purpose |
|------|---------|
| `confluence_tool.py` | Confluence REST API publishing |
| `jira_tool.py` | Jira REST API shim → `jira/` package |
| `jira/` | Jira operations, helpers, ADF converter |
| `slack_tools.py` | Send/read/post/interpret Slack messages |
| `slack_token_manager.py` | Token rotation, exchange, persistence |
| `file_write_tool.py` | PRD file writer |
| `file_read_tool.py` | File reader |
| `directory_read_tool.py` | Directory listing |
| `gemini_chat.py` | Gemini LLM intent classification |
| `openai_chat.py` | OpenAI LLM intent classification |
| `figma/` | Figma Make integration — Playwright + REST API + OAuth. `_config.py`, `_api.py`, `_client.py`, `figma_make_tool.py`, `login.py` (v0.22.0) |

## Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `logging_config.py` | Structured logging setup |
| `preflight.py` | Startup environment checks |
| `retry.py` | Crew kickoff retry wrapper + error classification |
| `setup_mongodb.py` | Collection & index bootstrap |
| `ngrok_tunnel.py` | ngrok tunnel management |
| `slack_config.py` | Slack manifest validation |
| `memory_loader.py` | Project memory resolution |
| `confluence_xhtml.py` | Markdown → Confluence XHTML converter |
| `knowledge_sources.py` | Knowledge file loading and caching |
| `project_knowledge.py` | Obsidian-style project knowledge base builder (project pages, completed idea pages, agent context) |
| `migrate_output_dirs.py` | One-time script: migrate output files to project-based directories (delete after use) |

## Components (`components/`)

| File | Purpose |
|------|---------|
| `cli.py` | Interactive CLI flow runner |
| `startup.py` | Server startup recovery tasks |
| `resume.py` | Resume paused runs |
| `document.py` | Document formatting utilities |

---

See also: [[Project Overview]], [[Orchestrator Overview]]
