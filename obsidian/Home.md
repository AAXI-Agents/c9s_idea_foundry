# C9 PRD Planner — Obsidian Knowledge Base

> AI-powered Product Requirements Document generation with CrewAI, Gemini, OpenAI, Slack, Confluence, and Jira.

**Current Version**: `0.16.2` (2026-03-10)

---

## Quick Navigation

### Architecture
- [[Project Overview]] — System overview, tech stack, conventions
- [[Module Map]] — Source tree with file purposes
- [[Server Lifecycle]] — FastAPI startup/shutdown sequence
- [[Environment Variables]] — All env vars and their purposes
- [[CrewAI Framework]] — How CrewAI concepts map to this project
- [[Coding Standards]] — Modular design, logging, versioning, testing

### Agents & Flows
- [[PRD Flow]] — End-to-end PRD generation pipeline
- [[Agent Roles]] — Idea Refiner, Product Manager, Requirements, Orchestrator
- [[LLM Model Tiers]] — Basic vs Research models and when to use each

### Integrations
- [[Slack Integration]] — Events API, Block Kit, interactive flows
- [[Confluence Integration]] — Publishing pipeline
- [[Jira Integration]] — Phased ticketing (Skeleton → Epics → Sub-tasks)
- [[MongoDB Schema]] — Collections, indexes, document schemas

### Development
- [[Coding Standards]] — Modular design, logging, versioning, testing
- [[Testing Guide]] — Test structure, patch targets, common commands
- [[Version History]] — Full changelog from v0.1.0 to current
- [[Session Log]] — AI agent session tracking

### Knowledge
- [[PRD Guidelines]] — 10-section template, quality criteria, iteration protocol
- [[User Preferences]] — User profile and PRD preferences

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
  Agent Roles.md           ← All agent configs
  LLM Model Tiers.md      ← Model selection guide
APIs/
  API Overview.md          ← Endpoint summary
Changelog/
  Version History.md       ← Full codex changelog
Database/
  MongoDB Schema.md        ← Collections & document schemas
Flows/
  PRD Flow.md              ← Generation pipeline
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
