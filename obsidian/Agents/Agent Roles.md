# Agent Roles

> All CrewAI agent configurations used in the PRD Planner.

## Idea Refiner

- **LLM**: Gemini (Research tier)
- **Tools**: None
- **Purpose**: Enrich raw ideas with domain expertise and stakeholder perspective
- **Process**: 3-10 iterative cycles
- **Scoring**: audience clarity, problem definition, solution specificity, competitive context, success criteria (1-5 each, all must ≥ 3 for "IDEA_READY")
- **Source**: `agents/idea_refiner/`

## Product Manager — Gemini

- **LLM**: Gemini (Research tier)
- **Tools**: FileReadTool, DirectoryReadTool
- **Purpose**: Draft and critique PRD sections with deep industry knowledge
- **Source**: `agents/product_manager/`

## Product Manager — OpenAI

- **LLM**: OpenAI (Research tier)
- **Tools**: FileReadTool, DirectoryReadTool
- **Purpose**: Secondary PM for multi-agent diversity in critique cycles
- **Source**: `agents/product_manager/`

## Product Manager Critic

- **LLM**: Gemini (Critic/Basic tier)
- **Tools**: None
- **Purpose**: Lightweight section critique (v0.8.1+, separate from research-tier drafter)
- **Source**: `agents/product_manager/`

## Requirements Breakdown Agent

- **LLM**: Gemini (Research tier)
- **Tools**: None
- **Purpose**: Decompose refined ideas into entities, state machines, API contracts, acceptance criteria
- **Scoring**: feature completeness, entity granularity, state machine rigour, AI augmentation depth, API contract precision, acceptance criteria coverage (1-5 each, all must ≥ 4)
- **Source**: `agents/requirements_breakdown/`

## Orchestrator Agent

- **LLM**: Gemini (Research tier)
- **Tools**: Confluence + Jira tools
- **Purpose**: Publish completed PRDs to Confluence, create Jira tracking tickets
- **Source**: `agents/orchestrator/`

## Delivery Manager Agent

- **LLM**: Gemini (Research tier)
- **Tools**: Confluence + Jira tools
- **Purpose**: Startup delivery orchestration (auto-publish pending Confluence/Jira)
- **Source**: `agents/orchestrator/`

## Jira PM / Architect Agents

- **LLM**: Gemini (Research tier)
- **Tools**: Jira tool
- **Purpose**: Epic/Story/Sub-task creation with domain-specific structure
- **Source**: `agents/orchestrator/`

---

## GStack Specialist Agents (v0.18.0)

### CEO Reviewer

- **LLM**: Gemini (Research tier — `GEMINI_CEO_MODEL`)
- **Tools**: None
- **Purpose**: Apply founder-mode thinking to transform the executive summary into an *Executive Product Summary* — a 10-star product vision document
- **Phase**: 1.5a (after executive summary approval)
- **Source**: `agents/ceo_reviewer/`

### Engineering Manager

- **LLM**: Gemini (Research tier — `GEMINI_ENG_MODEL`)
- **Tools**: None
- **Purpose**: Convert the executive product summary and requirements into an *Engineering Plan* — technical architecture, phasing, data model, test strategy, security, deployment
- **Phase**: 1.5b (after CEO review)
- **Source**: `agents/eng_manager/`

### Staff Engineer (v0.19.0)

- **LLM**: Gemini (Research tier — `GEMINI_STAFF_ENG_MODEL`)
- **Tools**: JiraCreateIssueTool
- **Purpose**: Paranoid structural audit — reviews every user story for N+1 queries, race conditions, stale reads, trust boundaries, missing indexes, escaping bugs, broken invariants, bad retry logic. Creates one `[Staff Eng Review]` sub-task per Story.
- **Phase**: Jira Phase 4a (after dev sub-tasks approval)
- **Source**: `agents/staff_engineer/`

### QA Lead (v0.19.0)

- **LLM**: Gemini (Research tier — `GEMINI_QA_LEAD_MODEL`)
- **Tools**: JiraCreateIssueTool
- **Purpose**: Test methodology review — checks acceptance criteria completeness, test coverage gaps, negative tests, integration tests, regression risk, data integrity, performance criteria, user flow, error recovery. Creates one `[QA Lead Review]` sub-task per Story.
- **Phase**: Jira Phase 4b (after Staff Engineer review)
- **Source**: `agents/qa_lead/`

### QA Engineer (v0.19.0)

- **LLM**: Gemini (Research tier — `GEMINI_QA_ENG_MODEL`)
- **Tools**: JiraCreateIssueTool
- **Purpose**: Edge case and security testing — creates `[QA Test]` counter-ticket per implementation sub-task covering boundary values, concurrent access, state transitions, injection, auth bypass, CSRF/SSRF, empty/loading/error states, responsive, accessibility.
- **Phase**: Jira Phase 5 (after review sub-tasks)
- **Source**: `agents/qa_engineer/`

### UX Designer (v0.20.0)

- **LLM**: Gemini (Research tier — `GEMINI_UX_DESIGNER_MODEL`)
- **Tools**: FigmaMakeTool
- **Purpose**: Convert the Executive Product Summary into a structured Figma Make prompt covering design system (colours, typography, spacing), user flows (with error/empty/loading states), reusable components (with variants), responsive page layouts, and interactions. Submits to Figma Make via Playwright browser automation when a Figma session is configured (see `login.py`); otherwise stores prompt for manual use.
- **Phase**: 1.5c (after Engineering Plan)
- **Source**: `agents/ux_designer/`

### Release Engineer (stub)
- **Source**: `agents/release_engineer/` — placeholder for future activation

### Retro Manager (stub)
- **Source**: `agents/retro_manager/` — placeholder for future activation

---

## Engagement Manager (v0.35.0, expanded v0.39.0)

- **LLM**: Gemini (Basic tier — `GEMINI_MODEL`, override via `ENGAGEMENT_MANAGER_MODEL`)
- **Tools**: None
- **Purpose**: Handle unknown/ambiguous intents AND orchestrate the full idea-to-PRD lifecycle. Coordinates all specialist agents through a 2-step strategy with continuous heartbeat updates and user steering detection.
- **Integration**: Automatically invoked when the Slack intent classifier returns `unknown`. Also serves as the orchestration entry point via `orchestrate_idea_to_prd()`.
- **Coordination**: Full knowledge of the agent team and execution order. Orchestrates Step 1 (sequential: Idea Refinement → Executive Summary) and Step 2 (parallel/coordinated: CEO Review + Requirements → Engineering + UX → Section Drafting).
- **Heartbeat**: Generates emoji-prefixed status updates at every phase transition (🧠 planning, ⚙️ working, ✅ completed, 💬 waiting, 🔄 steering).
- **User Steering**: Detects and classifies user messages during active flows (STEERING/QUESTION/FEEDBACK/UNRELATED) with LLM-powered analysis.
- **Session Isolation**: Only processes messages from the initiating user — other users are silently ignored.
- **Tasks**: `engagement_response_task` (intent routing), `idea_to_prd_orchestration_task` (lifecycle plan), `heartbeat_update_task` (status messages), `user_steering_detection_task` (message classification).
- **Key Functions**: `create_engagement_manager()`, `handle_unknown_intent()`, `orchestrate_idea_to_prd()`, `detect_user_steering()`, `generate_heartbeat()`, `make_heartbeat_progress_callback()`.
- **Fallback**: If the agent fails (LLM errors), gracefully falls back to a static help message with New Idea + Help buttons. Steering detection defaults to QUESTION on failure.
- **Source**: `agents/engagement_manager/`

---

See also: [[LLM Model Tiers]], [[PRD Flow]], [[Orchestrator Overview]]
