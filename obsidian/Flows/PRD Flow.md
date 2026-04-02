---
tags:
  - flows
  - pipeline
---

# PRD Flow

> End-to-end PRD generation pipeline. Each phase has its own detail page with step-by-step flow, data flow diagrams, skip conditions, approval gates, and source file paths.

---

## Flow Connection Map

The system has **4 independent flow entry points** and **7 sub-flows** inside the PRD pipeline. This diagram shows every flow, what triggers it, and how they connect.

### Entry Points

| Flow | Standalone? | Triggers |
|------|-------------|----------|
| **PRD Flow** | Yes | REST API (`POST /flow/prd/kickoff`), Slack (`new_idea`, `restart_prd`), Slack interactive kickoff |
| **UX Design Flow** | Yes | Triggered by PRD Finalization (Step 7) |
| **Confluence Publishing** | Yes | Slack (`publish` intent), server startup auto-publish, PRD Finalization (Step 7) |
| **Jira Ticketing** | Yes | Slack (`create_jira` intent), PRD Finalization (Step 7) |

### Connection Diagram

```
                    ┌──────────────────────────────────────┐
                    │          TRIGGER SOURCES              │
                    ├──────────┬───────────┬────────────────┤
                    │ REST API │   Slack   │ Server Startup │
                    └────┬─────┴─────┬─────┴───────┬────────┘
                         │           │             │
              ┌──────────┘     ┌─────┘             │
              ▼                ▼                   │
     ┌────────────────────────────────┐            │
     │          PRD Flow              │            │
     │  ┌───────────────────────┐     │            │
     │  │ Step 1: Idea Refine   │     │            │
     │  └──────────┬────────────┘     │            │
     │  ┌──────────▼────────────┐     │            │
     │  │ Step 2: Exec Summary  │     │            │
     │  └──────────┬────────────┘     │            │
     │  ┌──────────▼────────────┐     │            │
     │  │ Step 3: Requirements  │     │            │
     │  └──────────┬────────────┘     │            │
     │  ┌──────────▼────────────┐     │            │
     │  │ Step 4: CEO Review    │     │            │
     │  └──────────┬────────────┘     │            │
     │  ┌──────────▼────────────┐     │            │
     │  │ Step 5: Sections (×9) │     │            │
     │  └──────────┬────────────┘     │            │
     │  ┌──────────▼────────────┐     │            │
     │  │ Step 6: Eng Plan      │     │            │
     │  └──────────┬────────────┘     │            │
     │  ┌──────────▼────────────┐     │            │
     │  │ Step 7: Finalization  │─────┼─────┐      │
     │  └───────────────────────┘     │     │      │
     └────────────────────────────────┘     │      │
                                           ▼      │
                               ┌───────────────────────┐
                               │  Post-PRD Triggers    │
                               ├───────────────────────┤
                               │  UX Design Flow       │
                               │  Confluence Publishing │◄─┘
                               │  Jira Ticketing        │  (startup auto-publish)
                               └───────────────────────┘
                                     ▲         ▲
                                     │         │
                            Slack "publish"  Slack "create_jira"
                            (standalone)     (standalone)
```

### Standalone Triggers (Outside PRD Pipeline)

These flows can be triggered independently without running the full PRD pipeline:

| Trigger | Source | Flow | Behaviour |
|---------|--------|------|-----------|
| PRD Finalization (Step 7) | Internal trigger | UX Design Flow | Generates 2-phase design specification from Executive Product Summary |
| PRD Finalization (Step 7) | Internal trigger | Confluence Publishing | Publishes finalized PRD to Confluence |
| PRD Finalization (Step 7) | Internal trigger | Jira Ticketing | Creates Jira tickets (interactive mode only) |
| Slack `publish` intent | User message / button | Confluence Publishing | Discovers all completed PRDs missing a Confluence page and publishes them |
| Slack `create_jira` intent | User message / button | Jira Ticketing | Starts Phase 1 (skeleton) for a completed PRD with approval gates |
| Server startup | `main.py` lifespan | Startup Review → Confluence | Auto-publishes completed PRDs without Confluence pages (`confluence_only=True`) |
| Server startup | `main.py` lifespan | Startup Delivery → Confluence | Delivers pending completed ideas to Confluence |
| Slack `resume_prd` intent | User message / button | PRD Flow (resume) | Restores state from MongoDB, resumes from last checkpoint |
| Slack `restart_prd` intent | User message / button | PRD Flow (fresh) | Starts a new PRD run from an existing working idea |

### Flow Modes

| Mode | Triggered By | Approval Gates | Post-Completion |
|------|-------------|----------------|-----------------|
| **Auto-approve** | REST API (`auto_approve=true`), Slack (default) | None — all sections auto-approved | Confluence only (no Jira) |
| **Interactive** | REST API (`auto_approve=false`), Slack (`interactive=true`) | Per-section approval via callbacks | Phased Jira (5 phases with user approval) + Confluence |

---

## Pipeline Overview

| Step | Flow | Agent(s) | Purpose |
|------|------|----------|---------|
| 1 | [[Idea Refinement Flow\|Step 1 — Idea Refinement Flow]] | [[Idea Refiner]] | 3-10 iterative enrichment cycles |
| 2 | [[Executive Summary Flow\|Step 2 — Executive Summary Flow]] | [[Product Manager]] | Multi-agent draft→critique→refine loop |
| 3 | [[Requirements Breakdown Flow\|Step 3 — Requirements Breakdown Flow]] | [[Requirements Breakdown]] | Entities, state machines, API contracts |
| 4 | [[CEO Review Flow\|Step 4 — CEO Review Flow]] | [[CEO Reviewer]] | 10-star Executive Product Summary |
| 5 | [[Section Drafting Flow\|Step 5 — Section Drafting Flow]] | [[Product Manager]] | 9 sections with critique scoring |
| 6 | [[Engineering Plan Flow\|Step 6 — Engineering Plan Flow]] | [[Engineering Manager]] | Architecture, data model, deployment (requires all sections) |
| 7 | [[Finalization Flow\|Step 7 — Finalization Flow]] | — | Assemble PRD, trigger post-completion |

### Post-PRD Flows (Triggered by Step 7 — Finalization)

| Flow | Agent(s) | Purpose |
|------|----------|---------|
| [[UX Design Flow]] | [[UX Designer]] | 2-phase design specification |
| [[Confluence Publishing Flow]] | [[Orchestrator]] | Publish to Confluence |
| [[Jira Ticketing Flow]] | [[Orchestrator]], [[Staff Engineer]], [[QA Lead]], [[QA Engineer]] | 5-phase Jira ticket creation |

---

## Execution Flow

```
Raw Idea
  │
  ▼
Step 1:  Idea Refinement (3-10 cycles)
  │                                     ← User approval gate
  ▼
Step 2:  Executive Summary (2-10 iterations)
  │                                     ← User feedback gate (each iteration)
  │                                     ← User completion gate
  ▼
Step 3:  Requirements Breakdown
  │                                     ← User approval gate
  ▼
Step 4:  CEO Review → Executive Product Summary
  │                                     ← User decision gate (proceed to sections?)
  ▼
Step 5:  Section Drafting (9 sections × 2-10 iterations)
  │                                     ← User approval gate (each section)
  ▼
Step 6:  Engineering Plan (requires all sections complete)
  │
  ▼
Step 7:  Finalization
  │
  ├──► UX Design Flow (Phase 1: Draft → Phase 2: Review)
  ├──► Confluence Publishing
  └──► Jira Ticketing (5 phases, interactive mode only)
       Phase 1: Skeleton              ← User approval
       Phase 2: Epics & Stories       ← User review
       Phase 3: Sub-tasks
       Phase 4: Staff Eng + QA Lead reviews
       Phase 5: QA test counter-tickets
```

---

## PRD State (`PRDState`)

Tracks the full lifecycle:

| Field | Type | Set by |
|-------|------|--------|
| `run_id` | 12-char hex | Service |
| `idea` / `original_idea` | str | Idea Refinement |
| `draft` | PRDDraft (10 sections) | Section Drafting |
| `executive_summary` | ExecutiveSummaryDraft | Executive Summary |
| `requirements_breakdown` | str | Requirements Breakdown |
| `executive_product_summary` | str | CEO Review |
| `engineering_plan` | str | Engineering Plan |
| `ux_design_content` / `ux_design_status` | str | UX Design |
| `confluence_url` | str | Confluence Publishing |
| `jira_skeleton` / `jira_output` / `jira_phase` | str | Jira Ticketing |
| `status` | `"new"` → `"inprogress"` → `"completed"` | Lifecycle |

---

## Progress Events

| Event | When | Key Fields |
|-------|------|-----------|
| `pipeline_stage_start` | Any stage begins | stage name |
| `pipeline_stage_complete` | Stage finished | iteration count |
| `section_start` | Section begins | `section_title`, `section_step`, `total_sections` |
| `section_complete` | Section approved | `section_title`, `iterations` |
| `all_sections_complete` | All sections done | `total_iterations`, `total_sections` |
| `prd_complete` | Final PRD assembled | — |
| `confluence_published` | Published to Confluence | `url` |
| `jira_published` | Jira tickets created | `ticket_count` |

---

## API Entry Points

| Function | File | Purpose |
|----------|------|---------|
| `run_prd_flow(run_id, idea, ...)` | `apis/prd/service.py` | Execute new PRD flow |
| `resume_prd_flow(run_id, ...)` | `apis/prd/service.py` | Resume paused/unfinalized flow |
| `restore_prd_state(run_id)` | `apis/prd/service.py` | Rebuild state from MongoDB |
| `make_approval_callback(run_id)` | `apis/prd/service.py` | Create blocking section-approval callback |

---

## Resume Behaviour

Progress saved to MongoDB on every iteration, enabling pause/resume:
- Phase 0-1: Skip if already completed (flags in state)
- Phase 1.5: Skip if specialist outputs already populated
- Phase 2: Skip approved sections, resume from last unapproved
- Post-completion: Check `jira_phase` state machine, resume from next phase

---

## Degenerate Content Detection

If a draft is excessively short (<5 chars after stripping), off-topic, or contains template placeholders, the content is wiped and the section restarts from scratch.

---

## Draft Files (v0.8.3+)

In-progress saves go to `output/prds/_drafts/`. Only completed PRDs appear in `output/prds/`.

---

See also: [[Agent Roles]], [[Orchestrator Overview]], [[PRD Guidelines]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:
- [ ] <your change request here>

EXAMPLE:
- [ ] Add a new field `priority` (string, optional) to the response
- [ ] Rename endpoint from /v1/old to /v2/new
-->

### Pending

_No pending change requests._

### Completed

- [x] Move Engineering Plan after Section Drafting (now Step 6) so all sections are complete before generating the engineering plan *(completed 2026-03-29)*
- [x] Remove Steps 8, 9, 10 (UX Design, Confluence, Jira) from the pipeline — they are now Post-PRD flows triggered by Finalization *(completed 2026-03-29)*
