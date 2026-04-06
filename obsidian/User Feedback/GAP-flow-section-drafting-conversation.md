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

# [GAP] Section Drafting Lacks Conversational Feedback Loop

> Users can only approve/reject sections or provide one-shot feedback — there's no back-and-forth dialogue to collaboratively refine a section like in ChatGPT.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — section drafting interactivity review
- **Related page(s)**: [[Flows/Section Drafting Flow]], [[Flows/PRD Flow]], [[Agents/Product Manager]]

---

## Current Behaviour

During section drafting (9 sections), the Product Manager drafts → Critic scores → user gets 4 buttons: Approve / Select Agent / Provide Feedback / Pause. When the user provides feedback, it's collected as a single text input and the section is re-drafted. The user then sees the new draft and repeats. This is a rigid request-response cycle with no dialogue context — each feedback round is treated independently. The agent doesn't ask clarifying questions, explain its choices, or engage in a multi-turn conversation about the section content.

---

## Expected Behaviour

Users should be able to have a natural conversation about each section before approving. The agent should ask "What specifically about the functional requirements concerns you?", offer alternatives, and iterate in a ChatGPT-style dialogue. The conversation context should accumulate so later feedback builds on earlier discussion.

---

## Affected Area

- [x] Agent / Flow (missing step / wrong output)
- [x] Slack integration (missing intent / button / handler)
- [ ] API endpoint (missing / incomplete / wrong response)
- [x] Database schema (missing field / index / collection)
- [ ] Web app (missing page / component / flow)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Questions for User

### Q1: How should the conversational feedback loop work during section drafting?

Currently: Draft → Score → [Approve | Feedback text] → Re-draft. There's no multi-turn dialogue.

**Recommendation A**: **Chat-within-section mode** — After each draft, instead of just a feedback text box, open a "discussion thread" where the user and PM agent converse. The agent explains its draft rationale, asks clarifying questions, and proposes alternatives. Each turn adds to a `section_conversation: list[dict]` in MongoDB. When the user types "approve" or clicks [Approve], the agent generates a final draft incorporating all conversation context.

**Recommendation B**: **Guided revision mode** — After scoring, if any criterion scores below 8, the agent proactively asks a targeted question about the weak area (e.g., "The completeness score is 6/10 — should I add acceptance criteria for the offline sync feature?"). This is less freeform than full conversation but more directed than a blank feedback box.

**Recommendation C**: **Annotated draft review** — Instead of freeform feedback, present the draft with inline annotations. Users click on specific paragraphs to comment (similar to Google Docs suggestions). Each annotation becomes a targeted revision instruction. The agent revises only the annotated areas.

**Suggestion**: Recommendation A (chat-within-section) is the most natural ChatGPT-like experience. Start with A for the core interaction model, then layer B's proactive questions on top — the agent should initiate the conversation when scores are low, not wait for the user to speak first.

**Your Answer**: A

---

### Q2: Should section conversation history carry forward to influence later sections?

Currently, each section is drafted independently. Feedback given on "Functional Requirements" doesn't influence the drafting of "Edge Cases" even though they're closely related.

**Recommendation A**: **Cross-section context accumulation** — Maintain a `prd_conversation_context: list[dict]` that accumulates key decisions across all sections. When drafting Edge Cases, the agent prompt includes relevant decisions from Functional Requirements. This prevents contradictions and reduces redundant feedback.

**Recommendation B**: **Explicit dependency chain** — Define section dependencies (e.g., Edge Cases depends on Functional Requirements; Error Handling depends on Edge Cases). When drafting a dependent section, include the parent section's final approved content AND conversation highlights in the agent prompt.

**Recommendation C**: **Summary notes per section** — After each section is approved, the agent generates a 3-5 bullet "key decisions" summary. These summaries are prepended to all subsequent section prompts. Lighter weight than full conversation history.

**Suggestion**: Recommendation C (summary notes) gives 80% of the benefit at 20% of the token cost. Full conversation history (A) would blow up prompt sizes on later sections.

**Your Answer**: C

---

### Q3: Should the system support comparing multiple agent-generated variants side-by-side?

Currently, users can select a different agent's draft but only see one at a time. For critical sections, comparing variants side-by-side would help users pick the best baseline.

**Recommendation A**: **Parallel variant generation** — For each section, generate 2-3 variants (different agents or different prompts) simultaneously. Present all variants in a comparison view with per-variant scores. User picks the best one as the starting point for conversation.

**Recommendation B**: **On-demand variant** — Keep single-draft as default, but add a [Generate Alternative] button. When clicked, a second agent drafts the same section. Show both side-by-side. Only generates alternatives when requested, saving compute.

**Recommendation C**: **Style selector** — Before drafting, let users choose a "style" (concise / detailed / technical / executive-friendly). The same agent drafts with different prompt parameters. This gives variety without multi-agent overhead.

**Suggestion**: Recommendation B (on-demand variant) best balances UX with cost — users who are happy with the first draft don't pay for extra generation, but those who want options can request them.

**Your Answer**: B

---

## Proposed Solution

Core change: extend the section drafting loop in `prd_flow.py` to support multi-turn conversation mode. Add a `section_conversations` sub-document to the working idea MongoDB record. Modify the Slack approval callback to support a "conversation" state that maintains dialogue context until explicit approval.

---

## Acceptance Criteria

- [ ] Users can have multi-turn conversations about each section
- [ ] Agent proactively explains scoring weaknesses
- [ ] Conversation context persists across turns and is resumable
- [ ] Approved conversation summaries available for downstream sections
- [ ] Auto-approve mode bypasses conversation (backwards compatible)

---

## References

- `src/.../flows/prd_flow.py` — section drafting loop
- `src/.../orchestrator/_pipelines.py` — pipeline composition
- `src/.../apis/slack/interactions_router/` — approval callback handlers
- `obsidian/Flows/Section Drafting Flow.md`

---

## Resolution

- **Version**: 0.59.0
- **Date**: 2026-04-08
- **Summary**: Backend conversation storage schema implemented. Per-section message threading and summary notes in place.

### v0.59.0 — Backend Foundation

- **Section conversation schema**: `save_section_message(run_id, section_key, role, content)` appends messages to `section_conversations.<key>` array. `get_section_conversation(run_id, section_key)` retrieves the message thread. Both in `mongodb/working_ideas/_sections.py`.
- **Summary notes**: `save_section_summary_note(run_id, section_key, summary)` stores per-section summaries. `get_section_summary_notes(run_id)` returns all summaries as a `{section_key: summary}` dict. These carry forward context to downstream sections (Q2/C).
- **Injection guards**: Section keys validated against `$` and `.` characters to prevent MongoDB injection.
- **11 tests** in `tests/mongodb/test_section_conversations.py`.

### Remaining Work
- Wire conversation storage into section drafting flow (save agent/user messages each iteration)
- Slack threaded conversation UI for chat-within-section (Q1)
- Generate Alternative button in Slack Block Kit (Q3)
- Pass summary notes as context to downstream section agents

### User Decisions:
- Q1: A (chat-within-section mode — threaded conversation per section)
- Q2: C (summary notes per section carry forward to subsequent sections)
- Q3: B (on-demand [Generate Alternative] button)
