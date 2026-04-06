---
tags:
  - user-feedback
  - gap-ticket
  - flow-audit
status: in-progress
priority: medium
domain: flow
created: 2026-04-05
---

# [GAP] Engineering Plan Is Generated Without Technical Context From the User

> The Engineering Manager agent produces architecture diagrams, data flows, and deployment strategy without asking the user about their existing tech stack, infrastructure constraints, or team capabilities.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — engineering plan quality and relevance review
- **Related page(s)**: [[Flows/Engineering Plan Flow]], [[Agents/Engineering Manager]], [[Agents/Staff Engineer]]

---

## Current Behaviour

The Engineering Manager agent receives the Executive Product Summary + Requirements Breakdown and autonomously generates a comprehensive Engineering Plan covering: architecture diagrams, data flows, deployment strategy, and technical approach. It runs in "reasoning mode" with no user input.

The agent makes assumptions about:
- Technology stack (may suggest a stack the team doesn't use)
- Infrastructure (may assume cloud-native when team runs on-premises)
- Team size and capabilities (may suggest microservices for a 3-person team)
- Existing systems (may ignore critical integration points)
- Security/compliance requirements (may miss industry-specific regulations)

These assumptions cascade into Jira tickets — sub-tasks may reference technologies the team has never used.

---

## Expected Behaviour

The Engineering Plan should incorporate the team's actual technical context — their stack, infrastructure, constraints, and preferences. This should be collected once per project (not per PRD) and fed into the Engineering Manager's prompt.

---

## Affected Area

- [x] Agent / Flow (missing step / wrong output)
- [ ] Slack integration (missing intent / button / handler)
- [ ] API endpoint (missing / incomplete / wrong response)
- [x] Database schema (missing field / index / collection)
- [ ] Web app (missing page / component / flow)
- [ ] Documentation (missing / outdated)
- [x] Configuration / Environment

---

## Questions for User

### Q1: How should the system collect technical context from the user?

The agent needs to know the team's technology stack, infrastructure, and constraints to generate relevant engineering plans.

**Recommendation A**: **Technical profile in project config** — Add a "Technical Profile" section to project configuration. Fields: primary languages, frameworks, database(s), cloud provider, CI/CD tools, deployment model (containers/serverless/VMs), team size, and constraints (e.g., "must use PostgreSQL", "no Kubernetes"). Collected once via Slack wizard or web form, persisted in `projectConfig`.

**Recommendation B**: **Pre-engineering questionnaire** — Before the Engineering Plan phase, present 5-7 targeted questions based on the Requirements Breakdown: "The requirements suggest real-time data sync. What's your current approach to real-time? (WebSockets / SSE / Polling / Not implemented yet)". Questions are dynamically generated based on what the plan needs to decide.

**Recommendation C**: **Stack detection from project memory** — If the project has code repositories linked, analyze the codebase to detect the tech stack automatically (read `package.json`, `requirements.txt`, `Dockerfile`, etc.). Present detected stack for user confirmation: "I detected: React, Node.js, PostgreSQL, Docker, AWS. Is this correct?"

**Suggestion**: Recommendation A (technical profile) is the foundation — every project should have this metadata regardless of flow. Add B's dynamic questions on top for PRD-specific technical decisions that the profile doesn't cover.

**Your Answer**: C but Add B's dynamic questions on top for PRD-specific technical decisions that the project memory doesn't cover.

---

### Q2: Should the Engineering Plan go through an interactive review like other sections?

Currently the Engineering Plan is generated autonomously and becomes part of the final PRD without explicit user review.

**Recommendation A**: **Architecture review dialogue** — After the Engineering Plan is generated, the Engineering Manager agent presents the plan and asks 3-5 validation questions: "I proposed a microservices architecture for the payment module. Given your team size of 4, should we simplify to a modular monolith?" User reviews and provides direction. The agent revises the plan accordingly.

**Recommendation B**: **Technical review gate with alternatives** — Generate 2 architecture options (e.g., monolith vs microservices, REST vs GraphQL) with trade-off analysis. Present both to the user: "Option A: Monolith (faster to build, easier to deploy). Option B: Microservices (better scaling, harder to develop). Which approach should I detail?" User picks, agent generates the full plan for the chosen option.

**Recommendation C**: **Section-by-section engineering review** — Break the engineering plan into sub-sections (architecture, data model, API design, deployment, security) and present each for individual review, similar to how PRD sections work. User approves each sub-section.

**Suggestion**: Recommendation B (alternatives with trade-offs) provides the most impactful interaction — the biggest engineering decisions are architectural, and presenting options helps users make informed choices without requiring deep technical expertise.

**Your Answer**: B but start with a list of questions to gauge user technical level. If user does not have a strong technical skill then default to simpler questions to make decision for user such as "what is your current hosting budget?" Agent will provide trade off for user in the initial architecture but scale from it.

---

### Q3: Should the Engineering Plan directly feed into Jira ticket generation with traceability?

Currently the Engineering Plan informs Jira tickets indirectly through the overall PRD context. There's no direct mapping from architecture decisions to implementation tickets.

**Recommendation A**: **Requirements-to-tickets traceability** — Each engineering decision (architecture choice, data model entity, API endpoint) gets a unique ID. Jira tickets reference these IDs. When the engineering plan is revised, the system can identify which tickets need updating. The web app shows a traceability matrix.

**Recommendation B**: **Engineering plan as Jira epic source** — Let the Engineering Plan directly define Jira epic boundaries. Instead of the generic 4-epic structure (Data Persistence, Data Layer, Data Presentation, Security), the agent creates epics based on the actual architecture: "Payment Service Epic", "User Auth Epic", "Notification System Epic". Stories are grouped by architectural component.

**Recommendation C**: **Keep indirect relationship** — The current flow works: PRD context flows to Jira through the full document. Adding traceability increases complexity. Instead, improve the Jira agent's prompt to explicitly reference Engineering Plan decisions when generating tickets.

**Suggestion**: Recommendation B (architecture-driven epics) would dramatically improve Jira ticket quality. Generic epics like "Data Persistence" don't match how teams think about their system. Architecture-specific epics are immediately understandable to engineers.

**Your Answer**: B

---

## Proposed Solution

1. Add a "Technical Profile" section to `projectConfig` with stack, infra, and constraint fields
2. Add a review gate after Engineering Plan generation with architecture alternatives
3. Allow the Engineering Plan to define Jira epic boundaries instead of fixed categories

---

## Acceptance Criteria

- [ ] Technical profile fields available in project configuration
- [ ] Engineering Plan prompt includes project technical context
- [ ] Users can review and choose between architecture alternatives
- [ ] Engineering decisions have traceability to Jira tickets (if B chosen)
- [ ] Auto-approve mode generates plan without review gate

---

## References

- `src/.../agents/engineering_manager/` — Engineering Manager config
- `src/.../flows/prd_flow.py` — engineering plan step
- `src/.../orchestrator/_jira.py` — epic/story generation
- `src/.../mongodb/project_config/` — project configuration
- `obsidian/Flows/Engineering Plan Flow.md`
- `obsidian/Agents/Engineering Manager.md`

---

## Resolution

- **Version**: 0.57.0
- **Date**: 2026-04-06
- **Summary**: `technical_profile` field in `projectConfig` (Q1 partial, v0.56.0) + Engineering Manager agent activity messages (v0.57.0). Architecture detection, dynamic questions, tech-level gauging, and architecture-driven epics are future work. **Q2 follow-up question still unanswered.**

### Implemented in v0.56.0:
1. **Project technical profile** — Added `technical_profile` dict field (languages, frameworks, infra) to `projectConfig` MongoDB schema and `create_project()` function. This enables stack detection from project memory once populated.

### Implemented in v0.57.0:
2. **Agent activity messages** — Before Engineering Manager crew kickoff, an `agent_activity` event fires: "🛠️ *Engineering Manager* is generating engineering plan…" — informing users the agent is working.

### Remaining (future work):
- Stack detection via reference URL analysis (Q1 full)
- Dynamic engineering questions before plan generation (Q1 full)
- Architecture-driven epic generation (Q3/B)
- Tech-level gauging for architecture alternatives (Q2 — **awaiting user answer below**)

### Follow-up Question — Q2 Clarification:

You said the agent should "gauge user technical level" before presenting alternatives. How should this work in practice?

**Suggestion A**: **One-time technical assessment** — During project setup (or first PRD), ask 3 quick questions: "What's your role?" (PM / developer / tech lead / non-technical), "Are you comfortable with architecture diagrams?" (yes/no), "Do you want implementation details or high-level summaries?" (detailed / summary). Save answers in user preferences and adjust all future outputs.

**Suggestion B**: **Adaptive from conversation history** — Analyze the user's past messages in the thread for technical vocabulary. If they use terms like "microservices", "API gateway", "event-driven" — present full architecture details. If their messages are business-focused, present simplified summaries with "expand for technical details" sections.

**Suggestion C**: **Progressive disclosure by default** — Always start with a high-level summary (suitable for any audience) and include expandable "Technical Deep-Dive" sections. No tech-level assessment needed — the user self-selects their depth. In Slack, these would be threaded replies they can click to expand.

**Recommendation**: Suggestion C (progressive disclosure) — it's the most inclusive approach, avoids profiling users incorrectly, and works well in both Slack and web interfaces. No setup friction.
