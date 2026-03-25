# LLM Model Tiers

> The application uses three model tiers. Defaults live in `agents/gemini_utils.py`.

## Basic Models (`GEMINI_MODEL` / `OPENAI_MODEL`)

Fast, lightweight models for orchestration and user interactions.

| Consumer | File | Purpose |
|----------|------|---------|
| Gemini intent classifier | `tools/gemini_chat.py` | Classify Slack message intent |
| OpenAI intent classifier | `tools/openai_chat.py` | Classify Slack message intent (fallback) |
| Next-step predictor | `apis/slack/_next_step.py` | Predict next user action |
| Engagement Manager | `agents/engagement_manager/agent.py` | Handle unknown intents, guide user navigation (v0.35.0) |

## Research Models (`GEMINI_RESEARCH_MODEL` / `OPENAI_RESEARCH_MODEL`)

Deep-thinking models for complex, multi-iteration tasks.

| Consumer | File | Purpose |
|----------|------|---------|
| Product Manager agent | `agents/product_manager/agent.py` | PRD section drafting, refinement |
| Idea Refiner agent | `agents/idea_refiner/agent.py` | Iterative idea enrichment (3-10 cycles) |
| Requirements Breakdown | `agents/requirements_breakdown/agent.py` | Requirements decomposition |
| Orchestrator agent | `agents/orchestrator/agent.py` | Confluence publish, Jira creation |
| Delivery Manager | `agents/orchestrator/agent.py` | Startup delivery orchestration |
| Jira PM / Architect | `agents/orchestrator/agent.py` | Epic/Story/Task creation |

## Critic Model (`GEMINI_CRITIC_MODEL`)

Lightweight model for section critique (v0.8.1+). No tools.

| Consumer | File | Purpose |
|----------|------|---------|
| Product Manager Critic | `agents/product_manager/agent.py` | Section quality scoring |

## When Writing New Code

- **User-facing, lightweight, or routing logic** → Basic tier
- **Content generation, iterative refinement, deep reasoning** → Research tier
- **Quality scoring without tools** → Critic tier
- Import defaults from `agents/gemini_utils.py`

---

See also: [[Agent Roles]], [[Environment Variables]]
