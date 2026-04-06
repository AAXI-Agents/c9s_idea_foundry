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

# [GAP] No End-to-End Flow Dashboard or Conversation History View

> Users can't see the full journey of their PRD — from original idea through every agent interaction, approval decision, and revision to final output. There's no unified timeline or conversation history.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — user experience and transparency review
- **Related page(s)**: [[Flows/PRD Flow]], [[Database/agentInteraction Schema]], [[Architecture/Project Overview]]

---

## Current Behaviour

Interaction data is stored across multiple MongoDB collections:
- `workingIdeas` — idea state, sections, flow status
- `crewJobs` — pipeline execution state
- `agentInteraction` — individual agent interactions with timestamps
- `productRequirements` — final PRD output

However, there's no unified view that stitches these together into a coherent timeline. Users in Slack see messages scroll by in threads but can't easily review:
- What the original idea was vs the refined version
- Which sections were revised and why
- What feedback they gave and how it was incorporated
- The Critic's scoring journey per section
- Total time and cost of the generation process

For a ChatGPT-like experience, users expect to scroll back through their "conversation" with the AI and see the full history.

---

## Expected Behaviour

Users should have access to a unified conversation history / timeline view showing every step of the PRD journey — from raw idea to published document — with the ability to revisit and reference past decisions.

---

## Affected Area

- [x] Web app (missing page / component / flow)
- [x] API endpoint (missing / incomplete / wrong response)
- [x] Slack integration (missing intent / button / handler)
- [ ] Agent / Flow (missing step / wrong output)
- [x] Database schema (missing field / index / collection)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Questions for User

### Q1: What should the PRD journey timeline look like?

Users need visibility into the full flow, but the level of detail and presentation format matters.

**Recommendation A**: **ChatGPT-style conversation view** — Present the entire PRD journey as a scrollable conversation thread in the web app. Each agent interaction is a "message" with the agent's avatar, timestamp, and content. User feedback appears as user messages. Collapse long agent outputs with [Expand]. This is the most familiar UX for ChatGPT users.

**Recommendation B**: **Kanban-style phase board** — Show the PRD as a horizontal board with columns for each phase (Idea → Executive Summary → Requirements → CEO Review → Engineering → Sections → Design → Publishing → Jira). Each column shows completion status, scores, and key artifacts. Users click into a phase for details.

**Recommendation C**: **Timeline with milestones** — A vertical timeline (like GitHub's PR timeline) showing key milestones: idea refined (score: 8.2/10), exec summary approved (iteration 3), CEO vision completed, 9 sections drafted (avg score: 8.5/10), published to Confluence, 32 Jira tickets created. Expand any milestone for full details.

**Suggestion**: Recommendation A (conversation view) is the most aligned with the "ChatGPT-like app" vision. The conversation metaphor naturally represents the back-and-forth between users and agents. Add a compact timeline sidebar (inspired by C) for quick navigation.

**Your Answer**: A

---

### Q2: Should the system track and display quality metrics across the PRD journey?

Agent interactions generate scoring data (Critic scores, iteration counts, agent response quality) that could give users insight into PRD quality.

**Recommendation A**: **Quality dashboard** — A dedicated "PRD Quality" view showing: average section scores, number of iterations per section, sections that needed the most revision, total agent interactions, estimated time saved vs manual PRD writing. Presented as cards/charts at the top of the conversation view.

**Recommendation B**: **Inline quality badges** — Add small quality badges to each section in the conversation view: (✅ 9.2/10, 2 iterations) or (⚠️ 7.5/10, 5 iterations). Users can quickly scan which sections are strong and which may need attention. Click badge for full score breakdown.

**Recommendation C**: **Comparative analytics** — Track quality metrics across PRDs within a project. Show trends: "Your PRDs have improved — average first-draft scores increased from 6.8 to 8.1 over 5 PRDs." This helps teams see if their idea submissions are getting better.

**Suggestion**: Recommendation B (inline quality badges) gives immediate, actionable quality insight with minimal UI complexity. Add A (quality dashboard) as a premium feature for teams that want deeper analytics.

**Your Answer**: B

---

### Q3: How should decision audit trails be presented?

Users make many decisions during a PRD flow (approve section, provide feedback, choose agent variant, approve Jira skeleton). Currently these decisions aren't recorded in a reviewable format.

**Recommendation A**: **Decision log** — A dedicated "Decisions" tab in the PRD view listing every user decision with timestamp, context, and outcome. Format: "Apr 5, 10:32am — Approved Functional Requirements (score 8.7/10, iteration 2, feedback: 'Add API rate limiting requirements')". Exportable as CSV for stakeholder review.

**Recommendation B**: **Decision annotations in context** — Embed decision markers directly in the conversation view. When the user approved a section, show a highlighted "Decision Point" card: "You approved this version. Previous version scored 7.2/10." Users see decisions in the context where they occurred.

**Recommendation C**: **Summary email/report** — After PRD completion, auto-generate a "PRD Journey Report" summarizing all decisions, sent via email or posted in Slack. Includes: decisions made, alternative paths not taken, total iterations, and time invested. Useful for stakeholder communication.

**Suggestion**: Recommendation B (in-context annotations) is the most natural for a chat-style interface. Decision points become first-class elements in the conversation, making it easy to understand why the PRD evolved the way it did. Add C (summary report) as a post-completion deliverable.

**Your Answer**: B
---

## Proposed Solution

1. Create a `GET /flow/{run_id}/timeline` API endpoint that stitches data from `workingIdeas`, `crewJobs`, and `agentInteraction` into a unified timeline
2. Build a conversation-style view in the web app
3. Add quality badges derived from Critic scores
4. Record user decisions as first-class `agentInteraction` entries with `type: "user_decision"`

---

## Acceptance Criteria

- [ ] Users can view the full PRD journey as a conversation timeline
- [ ] Quality scores are visible per section
- [ ] User decisions are recorded and displayable
- [ ] Timeline is accessible from both web app and Slack (via link)
- [ ] API endpoint supports pagination for long flows
- [ ] Historical PRDs are viewable (not just active flows)

---

## References

- `src/.../mongodb/agent_interactions/` — interaction storage
- `src/.../mongodb/working_ideas/` — idea state storage
- `src/.../mongodb/crew_jobs/` — job execution state
- `src/.../apis/prd/` — PRD API endpoints
- `obsidian/Database/agentInteraction Schema.md`
- `obsidian/Database/workingIdeas Schema.md`

---

## Resolution

- **Version**: 0.59.0
- **Date**: 2026-04-08
- **Summary**: Backend API implemented. Timeline endpoint stitches all data sources into a unified chronological view.

### v0.59.0 — Backend Foundation

- **Timeline API** (`GET /flow/runs/{run_id}/timeline`): Unified PRD journey endpoint that stitches `workingIdeas`, `crewJobs`, `agentInteraction`, and `productRequirements` into a chronological `TimelineEvent` list. Events include: `idea_submitted`, `idea_refined`, `exec_summary_iteration`, `section_drafted`, `section_approved`, `agent_interaction`, `job_status`, `confluence_published`, `jira_created`. Implemented in `apis/prd/_route_timeline.py`.
- **Response model**: `TimelineResponse` with `run_id`, `total_events`, and `events[]` (each with `timestamp`, `event_type`, `title`, `detail`, `agent`, `section_key`, `iteration`, `score`, `metadata`).
- **Pagination**: `limit` query parameter (default 200, max 1000).
- **9 tests** in `tests/apis/prd/test_timeline.py`.

### Remaining Work
- ChatGPT-style conversation view frontend (Q1)
- Inline quality badges rendering (Q2)
- Decision annotation display (Q3)

### User Decisions:
- Q1: A (ChatGPT-style conversation view)
- Q2: B (inline quality badges — show critique scores in context)
- Q3: B (decision annotations in context — show what was changed and why)
