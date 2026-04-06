---
tags:
  - database
  - mongodb
---

# MongoDB Schema

> Collections, indexes, and document schemas — each collection has its own detailed page.
> Hosted on **MongoDB Atlas** — connection via `MONGODB_ATLAS_URI` env var.
> Database name controlled by `MONGODB_DB` env var (default: `ideas`).

---

## Collection Pages

Each page documents every field with type, constraints, descriptions, API references, and repository functions.

| Collection | Page | Records | Primary Key |
|-----------|------|---------|-------------|
| `crewJobs` | [[crewJobs Schema]] | Async job tracking for PRD flows | `job_id` |
| `workingIdeas` | [[workingIdeas Schema]] | In-progress PRD persistence (iterations, sections, status) | `run_id` |
| `productRequirements` | [[productRequirements Schema]] | Completed PRD delivery records (Confluence + Jira) | `run_id` |
| `projectConfig` | [[projectConfig Schema]] | Per-project settings (Confluence, Jira, Figma) | `project_id` |
| `projectMemory` | [[projectMemory Schema]] | Project-level memory for agent context | `project_id` |
| `agentInteraction` | [[agentInteraction Schema]] | Slack interaction logging for analytics/fine-tuning | `interaction_id` |
| `userSession` | [[userSession Schema]] | User and channel session management | `session_id` |
| `slackOAuth` | [[slackOAuth Schema]] | Slack workspace OAuth token persistence | `team_id` |
| `userSuggestions` | [[userSuggestions Schema]] | Ambiguous intent tracking for self-learning | `suggestion_id` |

**Total**: 9 collections, created by `ensure_collections()` in `scripts/setup_mongodb.py` on startup.

---

## Collection Relationships

```
crewJobs ─────────── 1:1 ─────────── workingIdeas
                                        │
                                        │ 1:1
                                        ▼
                                  productRequirements
                                        
workingIdeas ────── N:1 ──────── projectConfig
userSession ─────── N:1 ──────── projectConfig
agentInteraction ── N:1 ──────── projectConfig
userSuggestions ─── N:1 ──────── projectConfig
projectMemory ───── 1:1 ──────── projectConfig

slackOAuth (independent — no foreign keys)
```

### Key Relationships

| From | Field | To | Cardinality |
|------|-------|----|-------------|
| `crewJobs.job_id` | = | `workingIdeas.run_id` | 1:1 |
| `workingIdeas.run_id` | = | `productRequirements.run_id` | 1:1 |
| `workingIdeas.project_id` | → | `projectConfig.project_id` | N:1 |
| `projectMemory.project_id` | → | `projectConfig.project_id` | 1:1 |
| `userSession.project_id` | → | `projectConfig.project_id` | N:1 |
| `agentInteraction.project_id` | → | `projectConfig.project_id` | N:1 (optional) |
| `userSuggestions.project_id` | → | `projectConfig.project_id` | N:1 (optional) |

---

## Web App Data Model

The web app interacts with these collections through the REST API:

| Collection | API Page | Web App Purpose |
|-----------|----------|-----------------|
| `projectConfig` | [[Projects/]] | Project CRUD (name, Confluence/Jira/Figma config) |
| `workingIdeas` | [[Ideas/]], [[PRD Flow/]] | Idea lifecycle (progress, sections, iterations) |
| `crewJobs` | [[PRD Flow/]] | Job tracking (status, timing, output) |
| `productRequirements` | [[Publishing/]] | Delivery records (Confluence URLs, Jira tickets) |

---

## Setup

Collections and indexes are created by `scripts/setup_mongodb.py` on server startup:

```bash
# Manual setup
.venv/bin/python -m crewai_productfeature_planner.scripts.setup_mongodb
```

---

See also: [[API Overview]], [[Server Lifecycle]], [[Environment Variables]]


---

## Change Requests

<!-- 
HOW TO USE: Add your change requests below as bullet points.
Codex will implement each request, update this page, bump the
version, and move the completed item to the "Completed" list.

FORMAT:

EXAMPLE:
-->

### Pending

_No pending change requests._

### Completed

_No completed change requests._
