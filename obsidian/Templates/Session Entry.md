---
tags:
  - templates
---

# Session Entry Template

> Append this format to the current week's `Changelog/YYYY-MM-DD.md` file.

```markdown
### Session — MM-DD (vX.Y.Z)

**Focus**: One-line description of session goal

- **Root Cause**: (if fixing a bug — what caused it)
- **Changes**: Bullet summary of what was done
- **Files**: Key files created/modified
- **Tests**: Test counts and pass status
```

## Checklist for Every Session

- [ ] Add version table row to current week's `Changelog/YYYY-MM-DD.md`
- [ ] Add session entry below the week's table
- [ ] Update affected knowledge pages (e.g., [[Module Map]], [[MongoDB Schema]])
- [ ] Update [[Home]] if vault structure changed
- [ ] Run tests and verify all pass before closing
