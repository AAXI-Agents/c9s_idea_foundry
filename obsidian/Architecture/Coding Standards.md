# Coding Standards

> Development conventions and quality requirements.

## 1. Modular & Component-Based Design

- Split large files into focused sub-modules (one concern per file)
- Keep functions small and single-purpose
- Use `__init__.py` re-exports so internal layout can change without breaking imports
- Goal: smaller context windows for AI agents → less token usage

## 2. Log Scanning After Changes

After every code change — and during partial or full test runs:
- Check `logs/crewai.log` for new `WARNING` / `ERROR` entries
- Fix any regressions before moving on
- Run tests with `-x` (fail-fast) and inspect output for unexpected warnings

## 3. API Documentation

- Maintain OpenAPI/Swagger docs in `docs/openapi/openapi.json`
- Every new or changed endpoint must update the OpenAPI spec
- Update `README.md` when adding new APIs, features, or setup steps
- Verify changes reflected in Swagger UI at `/docs`

## 4. Session Management

### Major vs Minor Changes

- **Major changes** (new features, large refactors): Start a **new chat session**. Gets a `Y` bump.
- **Minor changes** (bug fixes, small tweaks): Keep in **current session**. Gets a `Z` bump.
- Bug fixes related to current work stay in the same session.

### Compact Mode at 75% Memory

When context capacity reaches 75%:
- Summarise completed work
- Drop intermediate search/read results
- Keep only: current task state, file paths, key decisions, todo list

### Obsidian Knowledge Updates

Every new session or iteration must update the Obsidian vault:
- Update [[Version History]] with new codex entries
- Update [[Session Log]] with session summary
- Update relevant knowledge pages for structural changes
- See [[Session Entry]] template for format

## 5. Command Prompt Permissions

All command-line operations are allowed by default — no permission needed.

## 6. Jira Approval Gate Invariant

Jira tickets must **never** be created without explicit user approval.
This rule applies to ALL code paths that can trigger Jira creation:

- **Auto-approve paths** (`_run_auto_post_completion`, startup crews):
  Must use `confluence_only=True` to gate out all Jira tasks.
- **Interactive paths** (`_run_phased_post_completion`): Must use the
  3-phase approval flow (skeleton → Epics/Stories → Sub-tasks) with
  user interaction at each gate.
- **Restart paths** (`execute_restart_prd`): Must use `interactive=True`
  to ensure phased Jira approval.

**Regression tests**: `tests/flows/test_jira_approval_gate.py` contains
23 tests covering every delivery path. Any new delivery path must add
a test to this file.

**Lesson learned** (v0.15.8): A `confluence_only` parameter was added
to `build_post_completion_crew` but was not propagated to all callers
(`_run_auto_post_completion`, `build_startup_delivery_crew`), causing
Jira tickets to be created without user approval. Always verify that
parameter changes are applied to ALL callers, not just the immediate
context.

**Lesson learned** (v0.15.11): Don't just guard against Jira *creation*
— also guard against Jira *state persistence*. `persist_post_completion()`
was autonomously detecting Jira keywords in crew output and setting
`jira_phase=subtasks_done` + `jira_completed=True`, causing the product
list to show Jira as complete when the user never approved it. All
autonomous Jira detection/persistence was removed from
`persist_post_completion()`, `_cli_startup.py`, and `components/startup.py`.
Only the interactive phased flow (`orchestrator/_jira.py`) may set these
fields.

## 7. One-Time Data Fix Scripts

When a bug contaminates MongoDB data (e.g. stale flags, orphaned
records), fix it with a **one-time script** in `scripts/`:

1. **Create** the script (e.g. `scripts/fix_stale_jira_phase.py`)
2. **Query first**: find affected documents and print them before changes
3. **Fix**: apply targeted `update_one` / `update_many` with explicit filters
4. **Verify**: re-query the same documents and print the corrected state
5. **Run** the script
6. **Confirm** output shows expected before/after state
7. **Delete** the script — single-use, don't commit it

> **Rule**: Always delete the script after use. It documents the fix in
> git history if committed before deletion, but must not remain in the
> tree as a runnable artifact.

---

See also: [[Testing Guide]], [[Project Overview]]
