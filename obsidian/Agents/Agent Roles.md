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

See also: [[LLM Model Tiers]], [[PRD Flow]], [[Orchestrator Overview]]
