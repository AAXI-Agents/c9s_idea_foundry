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

# [GAP] Idea Refinement Phase Lacks Real-Time User Collaboration

> The Idea Refiner runs 3-10 autonomous cycles with no mid-cycle user input, producing a refined idea the user may not agree with.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — idea-to-delivery interactivity review
- **Related page(s)**: [[Flows/Idea Refinement Flow]], [[Agents/Idea Refiner]], [[Knowledge/User Preferences]]

---

## Current Behaviour

The Idea Refiner agent runs autonomously for 3-10 scoring cycles. It enriches the raw idea across 5 criteria (target audience clarity, problem definition, solution specificity, competitive context, success criteria). The user only sees the final refined idea and can approve or reject — there is no opportunity to steer the refinement mid-cycle. If the agent makes wrong assumptions in early cycles, all subsequent cycles compound those errors.

---

## Expected Behaviour

Users should have the option to participate in the refinement process interactively, steering the agent toward the correct product direction before it locks in assumptions that cascade through the entire PRD.

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

### Q1: Should the Idea Refiner pause after each scoring cycle for user feedback?

Currently the refiner runs 3-10 cycles without stopping. Adding mid-cycle checkpoints would let users correct course early but would make the process slower and more hands-on.

**Recommendation A**: **Pause every 3 cycles** — Run 3 autonomous cycles, then present the current refined idea with scores and ask "Continue refining, adjust direction, or approve?" This balances speed with control. The user gets a natural checkpoint without being overwhelmed by per-cycle decisions.

**Recommendation B**: **Configurable pause interval** — Let users set a "refinement checkpoint interval" (e.g., every 1, 3, or 5 cycles) in project config. Power users skip checkpoints; cautious users review every cycle.

**Recommendation C**: **Smart pause on low-confidence** — Only pause when the agent's self-scoring drops below a threshold (e.g., any criterion < 6/10). High-confidence refinements proceed automatically; uncertain ones ask for user direction.

**Suggestion**: Combine A + C — pause every 3 cycles AND pause immediately if any criterion drops below 6. This respects the user's time while catching risky assumptions early.

**Your Answer**: A + C

---

### Q2: Should users be able to lock specific aspects of their idea during refinement?

The Idea Refiner may change parts of the idea the user considers non-negotiable (e.g., target audience, technical approach). There's currently no way to mark parts as "do not modify."

**Recommendation A**: **Aspect locking via structured input** — Before refinement starts, ask users to tag parts of their idea as "fixed" vs "refine." The agent's prompt includes locked aspects as constraints. Implementation: add a `locked_aspects: list[str]` field to the working idea document.

**Recommendation B**: **Post-refinement diff view** — After refinement, show a side-by-side diff of original vs refined idea. Users can accept/reject individual changes. This doesn't prevent changes but gives granular control over what sticks.

**Recommendation C**: **Guardrail keywords** — Users prefix non-negotiable statements with `[FIXED]` in their idea text. The refiner agent prompt instructs it to preserve `[FIXED]` sections verbatim.

**Suggestion**: Start with Recommendation B (diff view) because it requires no user training, then add aspect locking (A) as a power-user feature later.

**Your Answer**: B

---

### Q3: Should the system support collaborative idea building where the user and agent take turns?

Currently the flow is: user submits → agent refines → user approves. A ChatGPT-style back-and-forth could produce better ideas through dialogue.

**Recommendation A**: **Conversational refinement mode** — Replace the batch refinement with a turn-by-turn dialogue. Agent asks clarifying questions ("Who is the primary user?", "What's the core metric?"), user answers, agent incorporates answers into the next draft. Cap at 10 turns. Store conversation in `agentInteraction` for context.

**Recommendation B**: **Hybrid mode** — Agent does 3 autonomous cycles first, then switches to conversational mode for the remaining cycles. The autonomous cycles establish a baseline; the conversation fine-tunes it.

**Recommendation C**: **Guided questionnaire** — Instead of freeform conversation, present a structured questionnaire (5-8 targeted questions based on low-scoring criteria). After answers, agent does one final refinement pass.

**Suggestion**: Recommendation B (hybrid) is the strongest path for a ChatGPT-like experience — the agent does the heavy lifting first, then the user refines in conversation. This avoids overwhelming users who just want a quick PRD while giving detailed users the depth they need.

**Your Answer**: B + C. Start with B as hybrid but alwasy present 3 options to user with one recommended by agent and why. User can always give feedback if he does not like any of the 3 options.

---

## Proposed Solution

Implementation depends on user answers above. The core architectural change is adding an `idea_refinement_mode` to project config (`autonomous` | `checkpointed` | `conversational` | `hybrid`) and modifying the Idea Refiner's loop in `_idea_refinement.py` to check for pause conditions and collect feedback via the existing Slack approval callback pattern.

---

## Acceptance Criteria

- [ ] Users can interact with the idea refinement process mid-cycle
- [ ] Refinement mode is configurable per project
- [ ] Existing autonomous mode continues to work unchanged
- [ ] Conversation history is persisted for resume capability
- [ ] Slack Block Kit buttons support the chosen interaction pattern

---

## References

- `src/.../orchestrator/_idea_refinement.py` — current auto-refinement loop
- `src/.../agents/idea_refiner/` — agent config
- `obsidian/Flows/Idea Refinement Flow.md`

---

## Resolution

- **Version**: 0.56.0 (partial)
- **Date**: 2026-04-05
- **Summary**: User answers recorded. Implementation is future work — all 3 questions involve new interactive flow patterns (pause checkpoints, diff view, guided options).

### User Decisions:
- Q1: A+C (pause every 3 cycles AND on low-confidence <6)
- Q2: B (diff view of original vs refined idea)
- Q3: B+C (hybrid — 3 auto cycles then guided, always present 3 options)

### Follow-up Question — Q3 Clarification:

You said "always present 3 options" — should the 3 options appear at every single refinement turn, or only at key decision points?

**Suggestion A**: **Every turn** — After every refinement cycle (each of the 3 auto cycles + each guided cycle), present 3 alternative directions. This gives maximum control but may feel repetitive for simple ideas that don't need much steering.

**Suggestion B**: **Key decision points only** — Present 3 options only when: (a) after the 3 auto cycles complete (transition to guided mode), (b) when the agent detects a significant direction change, or (c) when confidence drops below 6. During steady refinement, just show the refined idea with approve/continue.

**Suggestion C**: **Progressive frequency** — Show 3 options at the start (after cycle 1) and at the end (guided mode entry), but skip them during middle iterations if the idea is converging well. If the idea diverges or confidence drops, re-introduce options.

**Recommendation**: Suggestion B (key decision points) — presenting 3 options every single turn would be overwhelming for a 10-cycle refinement. Save the options for moments where user steering actually matters.
