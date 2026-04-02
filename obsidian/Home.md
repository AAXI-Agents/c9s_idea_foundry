---
tags:
  - home
  - index
aliases:
  - Home
  - Index
---

# C9 PRD Planner — Obsidian Knowledge Base

> AI-powered Product Requirements Document generation with CrewAI, Gemini, OpenAI, Slack, Confluence, and Jira.

**Current Version**: `0.51.0` (2026-04-02)

---

## Quick Navigation

### Architecture
- [[Project Overview]] — System overview, tech stack, conventions
- [[Module Map]] — Source tree with file purposes
- [[Server Lifecycle]] — FastAPI startup/shutdown sequence
- [[Environment Variables]] — All env vars and their purposes
- [[CrewAI Framework]] — How CrewAI concepts map to this project
- [[Coding Standards]] — Modular design, logging, versioning, testing

### APIs
- [[API Overview]] — All 39 endpoints across 11 routers
- [[APIs/Health/|Health]] — Server probes and token management
- [[APIs/Projects/|Projects]] — CRUD with pagination
- [[APIs/Ideas/|Ideas]] — Idea lifecycle
- [[APIs/PRD Flow/|PRD Flow]] — Kickoff, approve, pause, resume, activity
- [[APIs/Publishing/|Publishing]] — Confluence & Jira delivery
- [[APIs/Integrations/|Integrations]] — Connection status

### Agents & Flows
- [[PRD Flow]] — End-to-end PRD generation pipeline
- [[Agent Roles]] — 12 agent pages (Idea Refiner, Product Manager, etc.)
- [[LLM Model Tiers]] — Basic vs Research models and when to use each

### Integrations
- [[Slack Integration]] — Events API, Block Kit, interactive flows
- [[Confluence Integration]] — Publishing pipeline
- [[Jira Integration]] — Phased ticketing (Skeleton → Epics → Sub-tasks)
- [[MongoDB Schema]] — 9 collection pages with field schemas

### Development
- [[Testing Guide]] — Test structure, patch targets, common commands
- [[Version History]] — Weekly changelog from v0.1.0 to current
- [[Session Log]] — AI agent session tracking

### Knowledge
- [[PRD Guidelines]] — 10-section template, quality criteria, iteration protocol
- [[User Preferences]] — User profile and PRD preferences

---

> [!tip] Making Changes
> Each API endpoint has its own markdown file under `APIs/<Domain>/`. Edit the **Change Requests → Pending** section to request changes — the coding agent will pick them up and implement them.

---

## Vault Structure

```
Home.md                    ← You are here
Architecture/
  Project Overview.md      ← System overview & tech stack
  Module Map.md            ← Source file purposes
  Server Lifecycle.md      ← Startup/shutdown hooks
  Environment Variables.md ← Env var reference
  CrewAI Framework.md      ← CrewAI concepts & project mapping
  Coding Standards.md      ← Development conventions
Agents/
  Agent Roles.md           ← Index → 12 individual agent pages
  LLM Model Tiers.md      ← Model selection guide
APIs/
  API Overview.md          ← Endpoint index (39 endpoints)
  Health/                  ← 5 per-route files
  Projects/                ← 5 per-route files
  Ideas/                   ← 3 per-route files
  PRD Flow/                ← 10 per-route files + [CHANGE] docs
  Publishing/              ← 9 per-route files
  Integrations/            ← 1 per-route file + [CHANGE] docs
  Slack/                   ← 5 per-route files
  SSO Webhooks/            ← 1 per-route file
Changelog/
  Version History.md       ← Weekly changelog
Database/
  MongoDB Schema.md        ← Index → 9 collection schema pages
Flows/
  PRD Flow.md              ← Index → 10 flow step pages
Integrations/
  Slack Integration.md     ← Slack module map
  Confluence Integration.md
  Jira Integration.md
Knowledge/
  PRD Guidelines.md        ← 10-section template
  User Preferences.md      ← User profile
Orchestrator/
  Orchestrator Overview.md ← Pipeline stages
Sessions/
  Session Log.md           ← AI session tracking
Templates/
  Session Entry.md         ← Template for session entries
Testing/
  Testing Guide.md         ← Test patterns & commands
Tools/
  Tools Overview.md        ← CrewAI tool wrappers
```
