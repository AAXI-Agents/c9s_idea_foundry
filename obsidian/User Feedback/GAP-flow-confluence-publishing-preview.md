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

# [GAP] Confluence Publishing Is Fire-and-Forget — No Preview, Edit, or Versioning

> PRDs are published to Confluence as a one-shot dump. Users can't preview the formatted page, edit before publishing, track version history, or incrementally update published pages.

---

## Context

- **Discovered by**: Agent (flow audit)
- **Discovered during**: Full PRD pipeline audit — publishing workflow review
- **Related page(s)**: [[Flows/Confluence Publishing Flow]], [[Integrations/Confluence Integration]]

---

## Current Behaviour

Confluence publishing:
- Converts markdown to XHTML via `confluence_xhtml.py`
- Creates/updates a Confluence page via REST API v3
- Stores URL and page ID in MongoDB
- Auto-publishes on server startup if credentials present
- No preview of formatted content before publishing
- No version tracking of published content
- No ability to publish partial PRDs (draft sections only)
- No collaborative editing — content is overwritten on each publish

When users publish, they trust that the markdown-to-XHTML conversion produces a readable page. Formatting issues, broken links, or missing sections are only discovered after visiting Confluence.

---

## Expected Behaviour

Users should be able to preview the Confluence-formatted content before publishing, choose which sections to publish, track changes between versions, and selectively update sections without overwriting the entire page.

---

## Affected Area

- [x] Agent / Flow (missing step / wrong output)
- [x] Slack integration (missing intent / button / handler)
- [x] API endpoint (missing / incomplete / wrong response)
- [ ] Database schema (missing field / index / collection)
- [ ] Web app (missing page / component / flow)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Questions for User

### Q1: Should users see a preview of the Confluence-formatted content before publishing?

Currently, publishing is a blind operation — users see the markdown source but not how it will look in Confluence.

**Recommendation A**: **In-app formatted preview** — Generate the XHTML output and render a preview in the ChatGPT-like web app (or as an uploaded HTML file in Slack). Users review the formatted version and click [Publish] or [Edit]. This catches formatting issues before they hit Confluence.

**Recommendation B**: **Draft page in Confluence** — Publish as a Confluence "draft" (unpublished state) first. Send the user a link to preview in Confluence natively. User clicks [Publish Live] in Slack/app to change the page from draft to published. This uses Confluence's own rendering as the preview.

**Recommendation C**: **Diff preview** — For updates to already-published pages, show a diff of what changed since the last publish. Highlight new/modified/removed sections. User approves the diff before the update is pushed. First-time publishes show the full content.

**Suggestion**: Recommendation B (draft page in Confluence) is the most reliable — it uses Confluence's own renderer, avoiding any discrepancies between preview and final. For the web app, add A as the native preview since users shouldn't have to leave the app.

**Your Answer**: A

---

### Q2: Should users be able to selectively publish or update individual sections?

Currently, the entire PRD is published as one page. Updating any section overwrites everything.

**Recommendation A**: **Section-level publishing** — Publish each PRD section as a child page under a parent PRD page in Confluence. Users can update individual sections without touching others. The parent page has a table of contents linking to child pages. This maps naturally to Confluence's page hierarchy.

**Recommendation B**: **Selective section update** — Keep the single-page format but track which sections changed since last publish. Present a checklist: [x] Executive Summary (modified), [ ] User Personas (unchanged), [x] Functional Requirements (new). User selects which sections to update; others retain their published content.

**Recommendation C**: **Append-only changelog** — Instead of overwriting, append a "Changes" section at the bottom of the Confluence page with a timestamp and diff summary for each update. The main content updates in place, but the changelog provides an audit trail.

**Suggestion**: Recommendation B (selective update with change tracking) provides the most practical workflow for teams reviewing PRDs in Confluence. Section-level child pages (A) can get unwieldy; selective updates on a single page are cleaner.

**Your Answer**: B

---

### Q3: Should published PRDs support collaborative annotation and feedback from Confluence readers?

Once published, the PRD is static. Stakeholders reading in Confluence can use Confluence comments, but these comments don't flow back to the PRD system. There's no closed-loop feedback.

**Recommendation A**: **Confluence comment sync** — Periodically poll the Confluence page for new inline comments. Surface them in Slack/web app as feedback items. Users can discuss comments in threads and either update the PRD section or resolve the Confluence comment — two-way sync.

**Recommendation B**: **Feedback collection link** — Append a "Provide Feedback" section to each published PRD with a deep link back to the ChatGPT-like app. Stakeholders click the link, land in a feedback form, and their input is stored as `userSuggestions` in MongoDB. The PRD owner reviews suggestions in Slack.

**Recommendation C**: **Scheduled review reminders** — After publishing, schedule a reminder (configurable: 1 week, 2 weeks, 1 month) that prompts the PRD owner: "Your PRD has been published for 1 week. Would you like to review stakeholder feedback and update?" Pull any Confluence comments at that point for review.

**Suggestion**: Recommendation B (feedback collection link) is the simplest closed-loop mechanism. It doesn't require complex Confluence API polling and gives stakeholders a direct path to provide structured feedback.

**Your Answer**: B

---

## Proposed Solution

1. Add a preview step before Confluence publishing (draft page or in-app render)
2. Track section-level change status for selective updates
3. Append a feedback link to published PRDs pointing back to the app

---

## Acceptance Criteria

- [ ] Users can preview formatted content before publishing
- [ ] Published content can be selectively updated per section
- [ ] Stakeholder feedback has a path back to the PRD system
- [ ] Publishing audit trail maintained in MongoDB
- [ ] Auto-publish on startup still works (skips preview for autonomous mode)

---

## References

- `src/.../orchestrator/_confluence.py` — Confluence orchestration
- `src/.../scripts/confluence_xhtml.py` — markdown-to-XHTML converter
- `src/.../tools/confluence_tools/` — Confluence API tools
- `obsidian/Flows/Confluence Publishing Flow.md`
- `obsidian/Integrations/Confluence Integration.md`

---

## Resolution

- **Version**: 0.59.0
- **Date**: 2026-04-08
- **Summary**: Backend foundation implemented. Preview endpoint, version tracking, and change detection in place.

### v0.59.0 — Backend Foundation

- **Preview endpoint** (`GET /publishing/confluence/{run_id}/preview`): Renders PRD as Confluence XHTML without publishing. Returns `run_id`, `title`, `markdown`, `xhtml`, and `sections_changed` (sections that differ from the last version snapshot). Implemented in `apis/publishing/service.py::preview_confluence_content()` and `apis/publishing/router.py`.
- **Version tracking**: `save_version_snapshot()`, `get_version_history()`, `get_current_version()` added to `mongodb/product_requirements/repository.py`. Stores version snapshots with section content for diff comparison.
- **Change detection**: Preview identifies changed sections by comparing current content against last version snapshot. All new sections flagged on first preview.
- **5 tests** in `tests/apis/publishing/test_confluence_preview.py`.

### Remaining Work
- Selective section publishing (Q2) — frontend + API for partial updates
- Feedback collection link (Q3) — append link to published pages
- Wire version snapshots into publish flow (auto-snapshot on publish)

### User Decisions:
- Q1: A (in-app preview before publishing)
- Q2: B (selective section update — publish changed sections only)
- Q3: B (feedback collection link in published Confluence page)
