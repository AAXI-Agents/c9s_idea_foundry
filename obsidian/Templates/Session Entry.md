---
tags:
  - templates
---

# Session Entry Template

> Copy this template when starting a new session entry in [[Session Log]].

```markdown
## Session NNN — YYYY-MM-DD

**Scope**: Brief description of the session's focus
**Version**: vX.Y.Z → vX.Y.Z

### Work Done
- Item 1
- Item 2

### Key Decisions
- Decision 1
- Decision 2

### Files Modified
- `path/to/file.py` — description of change

### Obsidian Pages Updated
- [[Page Name]] — what was updated

### Bugs Found & Fixed
- Description of bug and fix (if any)

### Open Issues
- Any remaining issues (if any)
```

## Checklist for Every Session

- [ ] Append entry to [[Session Log]]
- [ ] Update [[Version History]] if version bumped
- [ ] Update affected knowledge pages (e.g., [[Module Map]], [[MongoDB Schema]])
- [ ] Update [[Home]] if vault structure changed
- [ ] Run tests and verify all pass before closing
