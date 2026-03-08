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

---

See also: [[Testing Guide]], [[Project Overview]]
