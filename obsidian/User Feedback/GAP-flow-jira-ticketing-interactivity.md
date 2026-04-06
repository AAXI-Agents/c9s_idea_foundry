---
tags:
  - user-feedback
  - gap-ticket
  - flow-audit
status: in-progress
priority: high
domain: flow
created: 2026-04-05
---

# [GAP] Jira Ticketing Flow Is Rigid — No Conversational Customization

> The 5-phase Jira flow generates tickets based on agent-determined structure. Users can only approve/reject at gate boundaries — they can't customize ticket granularity, adjust priorities, or discuss implementation strategy with the agents.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — Jira ticketing interactivity review
- **Related page(s)**: [[Flows/Jira Ticketing Flow]], [[Integrations/Jira Integration]], [[Agents/Staff Engineer]], [[Agents/QA Lead]]

---

## Current Behaviour

The Jira flow has 5 sequential phases:
1. **Skeleton** → user approves outline
2. **Epics + Stories** → user reviews created tickets
3. **Sub-tasks** → auto-generated implementation tasks (7 required sections each)
4. **Staff Eng + QA Lead reviews** → auto-generated review sub-tasks
5. **QA test counter-tickets** → auto-generated

Users can approve/reject at Phase 1 (skeleton) and Phase 2 (epics/stories), but Phases 3-5 run entirely without user input. The agent decides: how many sub-tasks per story, what the implementation approach is, which test scenarios to cover, and what the staff engineer should audit. There's no way for users to say "This story doesn't need sub-tasks, it's a config change" or "Add a specific test for GDPR compliance."

---

## Expected Behaviour

Users should be able to conversationally customize the Jira output: adjust ticket granularity, modify implementation approach, add/remove sub-tasks, and provide domain-specific testing requirements through dialogue — not just approve/reject gates.

---

## Affected Area

- [x] Agent / Flow (missing step / wrong output)
- [x] Slack integration (missing intent / button / handler)
- [ ] API endpoint (missing / incomplete / wrong response)
- [ ] Database schema (missing field / index / collection)
- [ ] Web app (missing page / component / flow)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Questions for User

### Q1: How much control should users have over Jira ticket granularity and structure?

Currently, the agent decides the structure (Epics → Stories → Sub-tasks). Some teams want flat story lists; others want deeply nested hierarchies. The agent's structure may not match the team's Jira workflow.

**Recommendation A**: **Pre-generation configuration** — Before Jira creation, present a configuration panel: (1) Ticket depth: Epics only / Epics+Stories / Epics+Stories+Sub-tasks, (2) Story sizing: large (fewer, broader stories) / small (many, granular stories), (3) Custom epic categories (override default: Data Persistence, Data Layer, Data Presentation, Security), (4) Sprint mapping: auto-estimate story points and suggest sprint allocation.

**Recommendation B**: **Interactive skeleton builder** — Replace the current text-only skeleton with an interactive tree view. Users can drag/drop stories between epics, merge/split stories, add custom stories, and remove auto-generated ones. The edited skeleton becomes the blueprint for ticket creation.

**Recommendation C**: **Template-based generation** — Offer 3-4 Jira templates: (1) Standard (current structure), (2) Kanban-friendly (flat stories, no sub-tasks), (3) Sprint-ready (stories with point estimates and sprint suggestions), (4) Minimal (epics + high-level stories only). Team picks a template; agent generates accordingly.

**Suggestion**: Recommendation A (pre-generation config) provides the most impact with the least UI complexity. Start here, then build toward B (interactive skeleton) for teams that want full control.

**Your Answer**:A and sturcture for Kanban style only.

---

### Q2: Should users be able to review and edit sub-tasks before they're created in Jira?

Phases 3-5 create sub-tasks, review tasks, and QA tickets without any user gate. Once created, tickets must be edited directly in Jira — there's no in-app editing.

**Recommendation A**: **Sub-task preview and edit gate** — After the agent generates sub-task content (but before Jira API calls), present each sub-task's 7 sections for user review. Users can [Approve] / [Edit] / [Skip] each sub-task. Editing opens a text input for the specific section. Only approved sub-tasks are created in Jira.

**Recommendation B**: **Batch review with exceptions** — Generate all sub-tasks, present a summary table (story → sub-task count → estimated effort), and let users flag specific sub-tasks for review. Unflagged sub-tasks are auto-created; flagged ones open for editing. This avoids reviewing every sub-task while catching problems.

**Recommendation C**: **Post-creation sync** — Create all sub-tasks in Jira immediately (current behavior), but add a "Review in App" step that pulls created tickets back, lets users mark changes in the ChatGPT-like interface, and syncs edits back to Jira via API. This treats Jira as the source of truth while still enabling in-app review.

**Suggestion**: Recommendation B (batch review with exceptions) is the sweet spot — teams generating 30+ sub-tasks don't want to review each one, but they do want to catch the 2-3 that are wrong. Flag-and-review is efficient.

**Your Answer**: B

---

### Q3: Should the Staff Engineer and QA Lead reviews be interactive with the user?

Phases 4a/4b create review tickets autonomously. The Staff Engineer audits for N+1 queries, race conditions, etc. The QA Lead checks test methodology. These reviews are valuable but may miss domain-specific concerns.

**Recommendation A**: **Review augmentation** — After auto-generation, present the Staff Engineer's findings and ask: "Are there additional technical risks specific to your system?" User can add custom audit points (e.g., "Check for HIPAA compliance in data storage", "Verify backward compatibility with API v2"). These become additional review sub-tasks.

**Recommendation B**: **Custom review checklists** — Let teams define persistent review checklists in project config (e.g., "Always check: rate limiting, audit logging, data retention policies"). The Staff Engineer and QA Lead incorporate these checklist items into every review they generate, ensuring team-specific concerns are always covered.

**Recommendation C**: **Review priority voting** — Present the Staff Engineer's audit findings as a ranked list. User votes on which findings are most critical (thumbs up/down). Top-voted findings become "Priority 1" sub-tasks; low-voted ones become "nice-to-have" comments on the parent story instead of separate tickets.

**Suggestion**: Recommendation B (custom review checklists) is the most scalable — teams configure once, and every Jira run automatically includes their specific concerns. This reduces per-run interaction while increasing quality.

**Your Answer**: B

---

## Proposed Solution

1. Add a Jira pre-configuration step with depth, sizing, and template options
2. Add a batch sub-task review gate between generation and Jira API creation
3. Store custom review checklists in project config for Staff Eng/QA Lead agents

---

## Acceptance Criteria

- [ ] Users can configure Jira ticket structure before generation
- [ ] Sub-tasks can be reviewed/edited before creation in Jira
- [ ] Custom review checklist items are incorporated into agent reviews
- [ ] Jira approval gate invariant is maintained (no tickets without approval)
- [ ] Auto-approve mode continues to enforce `confluence_only=True`

---

## References

- `src/.../orchestrator/_jira.py` — Jira orchestration
- `src/.../flows/prd_flow.py` — Jira phase integration
- `src/.../agents/staff_engineer/` — Staff Engineer config
- `src/.../agents/qa_lead/` — QA Lead config
- `obsidian/Flows/Jira Ticketing Flow.md`
- `tests/flows/test_jira_approval_gate.py` — 23 regression tests

---

## Resolution

- **Version**: 0.56.0 (partial)
- **Date**: 2026-04-05
- **Summary**: User answers recorded. `review_checklists` field added to `projectConfig` schema (Q3/B). Kanban structure (Q1) and batch review (Q2) are future work.

### Implemented in v0.56.0:
1. **Custom review checklists** — Added `review_checklists` list field to `projectConfig` MongoDB schema, allowing project-specific review checklists for Jira ticket quality gates.

### User Decisions:
- Q1: A + Kanban only (pre-generation config, Kanban board structure)
- Q2: B (batch review with exceptions)
- Q3: B (custom review checklists stored in project config)

### Follow-up Question — Q1 Clarification:

You said "Kanban style only." Does this mean:

**Suggestion A**: **Remove Epic/Story/Sub-task hierarchy entirely** — Replace the current 3-phase Jira flow with a flat Kanban board structure: Backlog → In Progress → Done. All items are flat "Tasks" with labels/tags instead of parent-child relationships. This would be a major simplification.

**Suggestion B**: **Keep hierarchy but present as Kanban** — Keep the Epic → Story → Sub-task structure internally (for project tracking), but present them to the user in a Kanban-style visual layout during review. The Jira board view would be Kanban, but the data model stays hierarchical.

**Suggestion C**: **Offer as project-level template** — Add a "board style" setting to project config (Kanban vs Scrum). Kanban projects generate flat tasks with priority labels. Scrum projects keep the current Epic/Story/Sub-task hierarchy. Users choose during project setup.

**Recommendation**: Suggestion C (template option) — some teams genuinely need hierarchical tickets (enterprise, multi-sprint projects) while others just want a simple Kanban board. Making it a project-level setting gives flexibility without removing existing capability.
