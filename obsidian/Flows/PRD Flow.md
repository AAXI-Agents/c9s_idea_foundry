# PRD Flow

> End-to-end PRD generation pipeline. Each phase has its own detail page with step-by-step flow, data flow diagrams, skip conditions, approval gates, and source file paths.

---

## Pipeline Overview

| Phase | Flow | Agent(s) | Purpose |
|-------|------|----------|---------|
| 0 | [[Idea Refinement Flow]] | [[Idea Refiner]] | 3-10 iterative enrichment cycles |
| 1 | [[Executive Summary Flow]] | [[Product Manager]] | Multi-agent draft→critique→refine loop |
| 1 | [[Requirements Breakdown Flow]] | [[Requirements Breakdown]] | Entities, state machines, API contracts |
| 1.5a | [[CEO Review Flow]] | [[CEO Reviewer]] | 10-star Executive Product Summary |
| 1.5b | [[Engineering Plan Flow]] | [[Engineering Manager]] | Architecture, data model, deployment |
| 2 | [[Section Drafting Flow]] | [[Product Manager]] | 9 sections with critique scoring |
| 3 | [[Finalization Flow]] | — | Assemble PRD, trigger post-completion |
| Post-PRD | [[UX Design Flow]] | [[UX Designer]] | 2-phase design specification |
| Post-Completion | [[Confluence Publishing Flow]] | [[Orchestrator]] | Publish to Confluence |
| Post-Completion | [[Jira Ticketing Flow]] | [[Orchestrator]], [[Staff Engineer]], [[QA Lead]], [[QA Engineer]] | 5-phase Jira ticket creation |

---

## Execution Flow

```
Raw Idea
  │
  ▼
Phase 0: Idea Refinement (3-10 cycles)
  │                                    ← User approval gate
  ▼
Phase 1: Executive Summary (2-10 iterations)
  │                                    ← User feedback gate (each iteration)
  │                                    ← User completion gate
  ├──► Requirements Breakdown
  │
  ▼
Phase 1.5a: CEO Review → Executive Product Summary
  │
  ▼
Phase 1.5b: Engineering Plan
  │                                    ← User decision gate (proceed to sections?)
  ▼
Phase 2: Section Drafting (9 sections × 2-10 iterations)
  │                                    ← User approval gate (each section)
  ▼
Phase 3: Finalization
  │
  ├──► UX Design (Phase 1: Draft → Phase 2: Review)
  │
  ├──► Confluence Publishing
  │
  └──► Jira Ticketing (5 phases)
       Phase 1: Skeleton            ← User approval
       Phase 2: Epics & Stories     ← User review
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
| `figma_design_url` / `figma_design_prompt` | str | UX Design |
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
