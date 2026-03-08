# PRD Flow

> End-to-end PRD generation pipeline defined in `flows/prd_flow.py`.

## Pipeline Phases

### Phase 0 — Pre-Completion Pipeline (AgentOrchestrator)

**Stage 1: Idea Refinement** (Gemini, 3-10 cycles)
- Evaluates: audience clarity, problem definition, solution specificity, competitive context, success criteria (scored 1-5)
- Continues until all scores ≥ 3 ("IDEA_READY")

**Stage 2: Requirements Breakdown** (Gemini, iterative)
- Decomposes: entities, state machines, API contracts, acceptance criteria
- Evaluates: feature completeness, entity granularity, state machine rigour, AI augmentation depth, API contract precision, acceptance criteria coverage (scored 1-5, all must ≥ 4)
- Runs after executive summary approval (v0.12.3+)

### Phase 1 — Executive Summary Iteration

- Draft → Critique → Refine loop (min 2, max 10 cycles)
- Multi-agent: Gemini PM + OpenAI PM
- Critique scores: problem clarity, personas, functional reqs, non-functional reqs, edge cases, analytics, dependencies (rated 1-10)
- Approved when all scores ≥ 8 ("READY_FOR_DEV")
- User feedback gate: Slack users can provide critique or approve (v0.4.0+)
- Completion gate: Continue/Stop before section drafting (v0.6.5+)

### Phase 2 — Section-by-Section Generation

- 9 remaining sections processed sequentially
- Each: Draft → Critique → Refine (min 2, max 10 cycles)
- Critique scores: completeness, specificity, consistency, clarity, actionability, no-duplication (1-10, all must ≥ 8)
- Approved when "SECTION_READY"

### Phase 3 — Finalization

- Assemble all 10 sections into markdown
- Write PRD file to `output/prds/`
- Mark run as completed in MongoDB

### Phase 4 — Post-Completion Pipeline

- **Confluence Publish**: Push final PRD to Confluence space
- **Jira Ticketing**: Phased approach (see [[Jira Integration]])

## Progress Events

| Event | When | Key fields |
|-------|------|-----------|
| `section_start` | Section begins | `section_title`, `section_key`, `section_step`, `total_sections` |
| `exec_summary_iteration` | Each exec summary pass | `iteration`, `max_iterations` |
| `executive_summary_complete` | Exec summary finalized | `iterations` |
| `section_iteration` | Each section pass | `section_title`, `iteration`, `max_iterations` |
| `section_complete` | Section approved | `section_title`, `iterations` |
| `all_sections_complete` | All sections done | `total_iterations`, `total_sections` |
| `prd_complete` | Final PRD assembled | _(empty)_ |
| `confluence_published` | Published to Confluence | `url` |
| `jira_published` | Jira tickets created | `ticket_count` |

## PRD State (`PRDState`)

Tracks the full lifecycle:
- `run_id` — unique 12-char hex identifier
- `idea` / `original_idea` — feature idea (before/after refinement)
- `draft` — PRDDraft containing 10 PRDSection objects
- `executive_summary` — iterative draft with version history
- `requirements_breakdown` — structured requirements text
- `status` — "new" → "inprogress" → "completed"
- `confluence_url`, `jira_output`, `jira_skeleton`, `jira_phase`

Progress saved to MongoDB on every iteration, enabling pause/resume.

## Degenerate Content Detection

If a draft is excessively short, off-topic, or contains template placeholders, the content is wiped and the section restarts from scratch.

## Draft Files (v0.8.3+)

In-progress saves go to `output/prds/_drafts/` — only completed PRDs are in `output/prds/`.

---

See also: [[Agent Roles]], [[Orchestrator Overview]], [[PRD Guidelines]]
