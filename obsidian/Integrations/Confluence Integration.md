---
tags:
  - integrations
---

# Confluence Integration

> Publishing PRDs to Atlassian Confluence.

## Overview

Completed PRDs are published as Confluence pages using the REST API. Publishing can happen:
- Automatically during Phase 4 (post-completion pipeline)
- On server startup (discover unpublished completed PRDs)
- On demand via Slack ("publish" intent or delivery button)
- Via file watcher when new `.md` files appear in `output/prds/`
- Via cron scheduler periodic delivery scans

## Key Files

| File | Purpose |
|------|---------|
| `tools/confluence_tool.py` | REST API wrapper for page creation/update |
| `scripts/confluence_xhtml.py` | Markdown → Confluence XHTML converter |
| `orchestrator/_confluence.py` | `build_confluence_publish_stage(flow)` |
| `orchestrator/_startup_review.py` | Startup PRD discovery & publish |
| `apis/publishing/` | Automation endpoints, watcher, scheduler |

## Configuration

| Source | Fields |
|--------|--------|
| Environment | `CONFLUENCE_URL`, `CONFLUENCE_USERNAME`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_PARENT_ID` |
| Project Config (MongoDB) | `confluence_space_key` |

Parent page ID is optional — pages publish at space root when unset (v0.9.3+).

## MongoDB Persistence

Confluence URL and publish status stored in `productRequirements` collection (v0.9.7+):
- `confluence_url` — URL of published page
- `confluence_page_id` — Confluence page ID
- `confluence_published` — boolean flag
- `confluence_published_at` — timestamp

## Hallucinated URL Fix (v0.13.1)

The LLM was inventing fake Confluence URLs in Jira tickets. Fix: Jira tool resolves the authoritative URL from MongoDB, ignoring whatever the LLM passes.

---

See also: [[Jira Integration]], [[Orchestrator Overview]]
