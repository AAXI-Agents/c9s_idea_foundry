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

# [GAP] No Post-PRD Iteration Loop — Users Can't Evolve Published PRDs

> Once a PRD is finalized and published, there's no structured way to evolve it. Users must restart from scratch or manually edit in Confluence. The system treats PRDs as write-once artifacts.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — PRD lifecycle and iteration review
- **Related page(s)**: [[Flows/PRD Flow]], [[Flows/Confluence Publishing Flow]], [[Integrations/Confluence Integration]]

---

## Current Behaviour

The PRD lifecycle is: Idea → Refine → Draft → Approve → Finalize → Publish → Done. After finalization:
- Users can "restart" a PRD flow, but this wipes all state and starts from scratch
- Users can "iterate" an idea, but this starts a new PRD flow, not a revision of the existing one
- Published Confluence pages can be overwritten on re-publish, but there's no concept of a "v2" or incremental revision
- Jira tickets already created are not updated when the PRD changes
- There's no way to say "Update just the Functional Requirements section based on new user feedback"

In practice, PRDs evolve as products develop. Scope changes, user research reveals new needs, and technical discoveries invalidate assumptions. The system doesn't support this natural evolution.

---

## Expected Behaviour

Users should be able to iteratively improve published PRDs — update individual sections, version the changes, re-publish selectively, and optionally update related Jira tickets to reflect PRD amendments.

---

## Affected Area

- [x] Agent / Flow (missing step / wrong output)
- [x] Slack integration (missing intent / button / handler)
- [x] API endpoint (missing / incomplete / wrong response)
- [x] Database schema (missing field / index / collection)
- [ ] Web app (missing page / component / flow)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Questions for User

### Q1: Should the system support versioned PRD revisions?

Currently PRDs are write-once. When re-published, the old version is overwritten.

**Recommendation A**: **Git-style versioning** — Every finalization creates a new version (v1, v2, v3...). Versions are stored in MongoDB with full content snapshots. Users can diff between versions, revert to previous versions, and publish any version. Confluence pages show version history with "Last updated: v3 — Apr 5, 2026."

**Recommendation B**: **Amendment log** — Instead of full versioning, track amendments as structured entries: "Apr 5: Updated Functional Requirements (FR-007 added, FR-003 modified). Reason: user research revealed offline sync need." Amendments are appended to the PRD. No full snapshots, but a clear audit trail of what changed and why.

**Recommendation C**: **Living document mode** — PRDs are always editable. Changes are tracked with timestamps but there's no explicit versioning. The PRD is a "living document" that evolves continuously. This is simpler but offers less traceability.

**Suggestion**: Recommendation A (git-style versioning) provides the strongest foundation. PRDs are critical documents — teams need to know exactly what was agreed at each point in time. The overhead of storing full snapshots is minimal compared to the value of reliable version history.

**Your Answer**: A

---

### Q2: How should users trigger section-level revisions?

Currently the only option is "restart" (full re-run) or manual Confluence editing. Users need a way to say "Update just this section."

**Recommendation A**: **"Revise Section" command** — A new Slack intent and API endpoint: `revise_section(run_id, section_key, feedback)`. The PM agent re-drafts only the specified section, incorporating the user's feedback and the latest context from other sections. Goes through the same draft → critique → approve loop as initial drafting.

**Recommendation B**: **Conversational revision** — In the ChatGPT-like app, users navigate to any section and start a conversation: "The functional requirements need to include API rate limiting." The agent understands which section to update, makes the change, and presents the revised section for approval. No explicit commands needed.

**Recommendation C**: **Scheduled review cycles** — The system prompts users on a schedule (e.g., biweekly) to review each section: "It's been 2 weeks since you published. Has anything changed for Functional Requirements?" Users mark sections as "still valid" or "needs update." Flagged sections enter a revision loop.

**Suggestion**: Recommendation B (conversational revision) is the most natural for a ChatGPT-like experience. Users should be able to chat about any section and trigger revisions through natural language. Implement A's `revise_section` API under the hood for the backend.

**Your Answer**: B

---

### Q3: Should Jira tickets be updated when the PRD is revised?

Published Jira tickets are currently disconnected from PRD changes. If Functional Requirements change, existing stories may become invalid.

**Recommendation A**: **Impact analysis** — When a section is revised, the system analyzes which Jira tickets reference the changed requirements (via ticket descriptions or linked requirements). Present an impact report: "3 stories and 7 sub-tasks may be affected by this change." User decides which tickets to update, and the agent regenerates their descriptions.

**Recommendation B**: **Automatic sync with approval** — After PRD revision, automatically identify affected Jira tickets and generate updated descriptions. Present the changes for user approval before pushing to Jira. This ensures tickets stay in sync without manual tracking.

**Recommendation C**: **Manual Jira refresh** — Add a "Refresh Jira from PRD" button that regenerates all Jira ticket descriptions from the current PRD state. This is a blunt instrument but simple — user triggers it when they know the PRD has changed significantly enough to warrant a full Jira refresh.

**Suggestion**: Recommendation A (impact analysis) is the safest approach — it surfaces what would change without automatically modifying tickets that might have been manually edited by engineers. Show the impact, let the user decide.

**Your Answer**: A

---

## Proposed Solution

1. Add version tracking to `productRequirements` collection (version number, snapshot, changelog)
2. Create a `revise_section` API endpoint and Slack intent
3. Build a PRD revision conversation flow in the ChatGPT-like app
4. Add Jira impact analysis for PRD sections linked to tickets

---

## Acceptance Criteria

- [ ] PRD revisions create new versions with change tracking
- [ ] Individual sections can be revised without re-running the full flow
- [ ] Revised sections go through draft → critique → approve loop
- [ ] Confluence page is updated to reflect revisions
- [ ] Jira impact analysis identifies affected tickets
- [ ] Version history is viewable and diffable

---

## References

- `src/.../mongodb/product_requirements/` — PRD storage
- `src/.../flows/prd_flow.py` — flow execution
- `src/.../orchestrator/_confluence.py` — Confluence publishing
- `src/.../orchestrator/_jira.py` — Jira orchestration
- `obsidian/Flows/PRD Flow.md`

---

## Resolution

- **Version**: 0.59.0
- **Date**: 2026-04-08
- **Summary**: Backend version tracking infrastructure implemented. Version snapshots, history, and API endpoint in place.

### v0.59.0 — Backend Foundation

- **Version tracking schema**: `save_version_snapshot(run_id, version, sections_snapshot, changelog_entry)` pushes to `version_history` array and sets `current_version` on the `productRequirements` document. `get_version_history(run_id)` returns the full history. `get_current_version(run_id)` returns the current version number. All in `mongodb/product_requirements/repository.py`.
- **Versions API** (`GET /flow/runs/{run_id}/versions`): Returns `VersionHistoryResponse` with `run_id`, `current_version`, and `versions[]` (each with `version`, `changelog`, `sections` snapshot, `created_at`). Implemented in `apis/prd/_route_versions.py`.
- **5 tests** in `tests/mongodb/test_version_tracking.py`.

### Remaining Work
- Wire version snapshots into finalization flow (auto-create v1 on PRD complete)
- Section-level revision via conversational interface (Q2)
- Jira impact analysis showing affected tickets (Q3)
- Diff rendering between versions in frontend

### User Decisions:
- Q1: A (git-style versioning with branches and diffs)
- Q2: B (conversational revision — "update the mobile section")
- Q3: A (impact analysis — show which downstream sections are affected by changes)
