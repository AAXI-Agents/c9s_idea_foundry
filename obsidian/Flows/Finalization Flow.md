---
tags:
  - flows
  - pipeline
---

# Step 7 — Finalization Flow

> Pipeline Step 7 — Assemble all sections into the final PRD, trigger UX design and post-completion delivery.

| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Source** | `flows/_finalization.py` |
| **Function** | `finalize(flow)` |
| **Triggers** | UX Design Flow, Confluence Publishing Flow, Jira Ticketing Flow |

---

## Purpose

Assemble all approved PRD sections into a complete markdown document, write the final file, mark the working idea as completed, and trigger all post-completion workflows (UX design, Confluence publishing, Jira ticketing).

---

## Step-by-Step Flow

### Step 1 — Assemble PRD

```
flow.state.final_prd = flow.state.draft.assemble()
```

- Concatenates all 12 sections (executive summary through assumptions) into a single markdown document
- Includes section headers and content

### Step 2 — Append UX Design Appendix

- If UX design content is available, appends it as an appendix to the assembled PRD

### Step 3 — Write PRD File

```
writer = PRDFileWriteTool(output_dir=prd_dir)
save_result = writer._run(content=final_prd, filename="", version=iteration)
```

- Saves to `output/{project_id}/product requirement documents/`
- Returns the file path as `save_result`

### Step 4 — Persist Output Path

```
persist_output_path(flow, save_result)
```

- Stores the file path in MongoDB `working_ideas.output_path`

### Step 5 — Convert to Confluence XHTML

```
confluence_xhtml = md_to_confluence_xhtml(flow.state.final_prd)
```

- Pre-renders the markdown to Confluence-compatible XHTML for later publishing

### Step 6 — Mark Completed

```
mark_completed(flow.state.run_id)
```

- Updates `working_ideas.status` to `"completed"`
- Sets `completed_at` timestamp

### Step 7 — Generate Project Knowledge

```
sync_completed_idea(flow.state.run_id)
```

- Creates/updates the project knowledge page for the completed idea
- Available to future agent runs as context

### Step 8 — Set State Flags

```python
flow.state.is_ready = True
flow.state.status = "completed"
flow.state.completed_at = datetime.now(timezone.utc).isoformat()
```

### Step 9 — Trigger UX Design Flow

```
_trigger_ux_design_flow(flow)
```

- Calls the standalone UX Design Flow (see [[UX Design Flow]])
- Requires: executive product summary present, UX not already completed
- Skip guards: no EPS → skip, status already `completed` or `prompt_ready` → skip
- Errors: `BillingError`/`ModelBusyError`/`ShutdownError` propagate; other errors caught (PRD saved regardless)

### Step 10 — Trigger Post-Completion

```
run_post_completion(flow)
```

- Routes to phased or auto mode based on callbacks:
  - **Phased** (has `jira_skeleton_approval_callback`): Interactive 5-phase Jira → see [[Jira Ticketing Flow]]
  - **Auto** (no callback): Confluence-only publishing → see [[Confluence Publishing Flow]]

---

## Progress Events

| Event | When |
|-------|------|
| `prd_complete` | Final PRD assembled and written |
| `prd_ready_for_publish` | Ready for Confluence/Jira |

---

## Resume Behaviour

Finalization does not have explicit resume logic — it runs once when all sections are approved. If the flow was paused during post-completion, the resume path re-runs `run_post_completion()` which checks each phase's completion state.

---

## MongoDB Persistence

- `mark_completed(run_id)` — status → `"completed"`, sets `completed_at`
- `persist_output_path(flow, path)` — output file location
- `sync_completed_idea(run_id)` — project knowledge sync

---

## Data Flow

```
Input:  flow.state.draft.sections[] (all 12 sections approved)
Output: flow.state.final_prd (assembled markdown)
        flow.state.is_ready = True
        flow.state.status = "completed"
        File: output/{project_id}/product requirement documents/
Triggers: → UX Design Flow (Post-PRD)
           → Confluence Publishing Flow (Post-Completion)
           → Jira Ticketing Flow (Post-Completion)
```

---

## Source Files

- `flows/_finalization.py` — `finalize()`, `_trigger_ux_design_flow()`, `run_post_completion()`
- `tools/prd_file_write_tool.py` — PRD file writer
- `tools/confluence_xhtml.py` — markdown to XHTML converter

---

See also: [[PRD Flow]], [[Section Drafting Flow|Step 5 — Section Drafting Flow]], [[UX Design Flow]], [[Confluence Publishing Flow]], [[Jira Ticketing Flow]]


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

_No completed change requests._
