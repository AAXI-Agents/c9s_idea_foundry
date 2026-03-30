# Engagement Manager

> Handles unknown/ambiguous intents and orchestrates the full idea-to-PRD lifecycle with continuous heartbeat updates and user steering detection.

| Field | Value |
|-------|-------|
| **LLM Tier** | Basic |
| **Model Env Var** | `ENGAGEMENT_MANAGER_MODEL` → `GEMINI_MODEL` → `DEFAULT_GEMINI_MODEL` |
| **Tools** | FileReadTool, DirectoryReadTool |
| **Timeout** | 120 s |
| **Max Retries** | 3 |
| **Fast Path** | Direct Gemini REST API via `generate_chat_response()` (bypasses CrewAI, ~200-800 ms) |
| **CrewAI Override** | `ENGAGEMENT_MANAGER_USE_CREWAI=true` |
| **Introduced** | v0.35.0 (expanded v0.39.0) |
| **Source** | `agents/engagement_manager/` |

---

## Role

> Engagement Manager, PRD Orchestrator & Navigation Guide

## Goal

Manage end-to-end "idea to PRD" lifecycle by orchestrating all specialist agents through a structured flow. Guide users from raw idea capture through refinement, executive summary, requirements breakdown, CEO review, engineering plan, UX design, and section drafting — all the way to a PRD ready for Confluence and Jira publication. Provide continuous heartbeat updates so the user always knows what agents are thinking, planning, working on, completing.

## Backstory

You are a seasoned engagement manager and PRD orchestrator who knows every capability of the product feature planning system. You coordinate a team of specialist agents. Your orchestration strategy: Step 1 (Sequential): Idea Refinement → Executive Summary (must complete in order). Step 2 (Parallel/Coordinated): After Step 1, coordinate remaining agents — CEO Review + Eng Plan + UX Design can start together, section drafting needs requirements, etc. You actively listen for user feedback and incorporate it into current iteration step. You only engage with initiating user. You have access to completed idea markdown files in project's ideas/ folder and can read full content using file tools.

---

## Tasks

### `engagement_response_task`

Handle messages that don't match any known system intent. Classify as:

- **Knowledge question** — about existing ideas, summaries, status → provide well-structured summary with actual project data
- **Action intent** — do something specific → recommend specific action button
- **Idea feedback/steering** — provide feedback on in-progress iteration
- **Clarification needed** — start with `[CLARIFICATION]`, explain what understood, ask clarifying question, suggest 2-3 likely actions

### `idea_to_prd_orchestration_task`

Orchestrate full idea-to-PRD lifecycle:

- **Step 1 — Sequential**: Idea Refinement → Executive Summary
- **Step 2 — Coordinated Parallel**: CEO Review + Requirements → Engineering + UX → Section Drafting

Before starting each phase, tell user what you're doing and why. While working, provide thinking/planning updates. When completed, summarize what was produced and what's next.

### `heartbeat_update_task`

Generate emoji-prefixed status updates at every phase transition:

| Emoji | Phase |
|-------|-------|
| 🧠 | Planning |
| ⚙️ | Working |
| ✅ | Completed |
| 💬 | Waiting for user |
| 🔄 | Incorporating steering feedback |

### `user_steering_detection_task`

Detect and classify user messages during active flows:

- `STEERING` — user wants to change direction
- `QUESTION` — user asking about progress/status
- `FEEDBACK` — user providing input to incorporate
- `UNRELATED` — message not related to current flow

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `create_engagement_manager()` | Agent factory |
| `handle_unknown_intent()` | Entry point for unknown Slack intents |
| `orchestrate_idea_to_prd()` | Lifecycle orchestration entry point |
| `detect_user_steering()` | LLM-powered message classification |
| `generate_heartbeat()` | Phase transition status messages |
| `make_heartbeat_progress_callback()` | Progress callback factory |

---

## Integration

- **Invoked when**: Slack intent classifier returns `unknown`
- **Session isolation**: Only processes messages from the initiating user — others silently ignored
- **Disengaged during iterations**: When active idea has status `inprogress`/`paused`, all user questions route to [[Idea Agent]] instead (v0.43.0)
- **Fallback**: If agent fails (LLM errors), gracefully falls back to static help message with New Idea + Help buttons
- **Steering detection fallback**: Defaults to `QUESTION` on failure

---

## Source Files

- `agents/engagement_manager/config/agent.yaml` — role, goal, backstory
- `agents/engagement_manager/config/tasks.yaml` — task definitions
- `agents/engagement_manager/agent.py` — agent factory and handler functions

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[Idea Agent]], [[PRD Flow]], [[Slack Integration]]
