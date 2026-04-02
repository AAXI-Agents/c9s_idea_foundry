---
tags:
  - architecture
---

# Project Overview

> Idea Foundry — AI-powered platform that transforms raw product ideas into implementation-ready PRDs using multi-agent orchestration.

## Tech Stack

| Technology | Version / Detail |
|-----------|-----------------|
| Python | 3.11 with type hints |
| CrewAI | 1.9.3 (multi-agent orchestration) |
| Gemini LLM | gemini-3-flash-preview (default) |
| OpenAI | o3 (fallback / secondary PM agent) |
| MongoDB | Working ideas, finalized ideas, crew jobs, projects, users |
| FastAPI | REST API + Slack webhooks |
| Slack | Bot: Events API, Interactions API, OAuth v2, Block Kit |
| Confluence | Post-completion PRD publishing |
| Jira | Phased ticket creation (Epics → Stories → Sub-tasks) |
| Pydantic | v2 — API request/response and flow state |
| Embedder | google-vertex (backed by google-genai SDK) |

## Architecture — Web App + Slack Integration

The backend serves two client interfaces:

| Client | Transport | Auth | Primary Use |
|--------|-----------|------|-------------|
| **Web App** | REST API (JSON) | SSO JWT Bearer token | Project management, idea lifecycle, PRD generation, publishing |
| **Slack Bot** | Webhooks (Events + Interactions) | HMAC-SHA256 signing | Conversational PRD creation, Block Kit approvals |

Both clients share the same backend services (MongoDB, PRD Flow, Publishing).

### API Surface for Web App

| Domain | Endpoints | Purpose |
|--------|-----------|---------|
| Projects | `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}` | Project CRUD with Confluence/Jira config |
| Ideas | `GET /ideas`, `GET /ideas/{run_id}`, `PATCH /ideas/{run_id}/status` | Idea list, progress, archive/pause |
| PRD Flow | `POST /flow/prd/kickoff`, `GET /flow/runs/{run_id}`, `POST /flow/prd/approve`, `/pause`, `/resume` | AI-driven PRD generation lifecycle |
| Publishing | `POST /publishing/confluence/{run_id}`, `POST /publishing/jira/{run_id}`, `GET /publishing/status/{run_id}` | Delivery to Confluence & Jira |
| Health | `GET /health`, `GET /version` | Liveness, version info |

→ Full endpoint reference: [[API Overview]]

## Project Conventions

- All source packages have `__init__.py` with explicit `__all__`
- Logging uses `[Tag]` prefix convention (e.g. `[SlackConfig]`, `[CrewJobs]`)
- No decorative/box-drawing characters in log output — single-line structured messages
- Tests use `unittest.mock.patch` + `monkeypatch` for env vars
- Modular design: one concern per file, small focused functions
- `__init__.py` re-exports so internal layout changes don't break imports

## Versioning (`X.Y.Z`)

Lives in `src/crewai_productfeature_planner/version.py`:

| Segment | Bumped by | When |
|---------|-----------|------|
| **X** (Release) | User | User decides to cut a release |
| **Y** (Major) | Agent | Agent adds a new set of features or code |
| **Z** (Minor) | Agent | Agent iterates on a fix or resolves a bug |

## Key Entry Points

| Entry | File | Purpose |
|-------|------|---------|
| CLI | `src/.../main.py` | Interactive PRD generation |
| API Server | `src/.../apis/__init__.py` | FastAPI app with lifespan hooks, serves web app + Slack |
| PRD Flow | `src/.../flows/prd_flow.py` | CrewAI Flow orchestrating PRD lifecycle |
| OpenAPI Spec | `docs/openapi/openapi.json` | Web app integration reference (schemas, paths, auth) |

## Quick Start

```bash
# One-command setup
./scripts/dev_setup.sh

# Start server
./start_server.sh

# Run all tests
.venv/bin/python -m pytest -x -q
```

---

See also: [[Module Map]], [[Server Lifecycle]], [[Environment Variables]]
