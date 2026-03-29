# Orchestrator

> Coordinates end-to-end delivery pipeline — publishes PRDs to Confluence and creates Jira tickets for every actionable requirement.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research |
| **Model Env Var** | `ORCHESTRATOR_MODEL` → `GEMINI_RESEARCH_MODEL` → `DEFAULT_GEMINI_RESEARCH_MODEL` |
| **Tools** | ConfluencePublishTool, JiraCreateIssueTool |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Introduced** | v0.1.0 |
| **Source** | `agents/orchestrator/` |

---

## Role

> Orchestrator & Delivery Coordinator

## Goal

Coordinate end-to-end delivery pipeline after PRD is generated. Detect completed PRD artefacts, publish them to Atlassian Confluence, and create Jira tickets for every actionable requirement or task identified in the PRD. Ensure no completed work product is left unpublished or untracked.

## Backstory

You are a seasoned delivery coordinator who bridges product planning and engineering execution. You monitor the output pipeline, ensuring every finalized PRD is published to Confluence for stakeholder visibility and that corresponding Jira tickets are created.

---

## Agent Variants

### Orchestrator Agent

- **Purpose**: Publish completed PRDs to Confluence, create Jira tracking tickets
- **Tools**: ConfluencePublishTool, JiraCreateIssueTool

### Delivery Manager Agent

- **Purpose**: Startup delivery orchestration — auto-publish pending Confluence/Jira on server restart
- **Tools**: ConfluencePublishTool, JiraCreateIssueTool

### Jira PM / Architect Agents

- **Purpose**: Epic/Story/Sub-task creation with domain-specific structure
- **Tools**: JiraCreateIssueTool

---

## Tasks

### `publish_to_confluence_task`

Publish completed PRD markdown document to Atlassian Confluence using the confluence publisher tool. Use provided page title; update existing page or create new.

**Expected output**: Confirmation with page ID and URL, or error details.

### `generate_jira_skeleton_task`

Generate skeleton outline of Jira Epics and User Stories WITHOUT creating tickets yet. Analyse PRD and structure with Epics (one per key feature) and User Stories per Epic organized into:

- Data Persistence
- Data Layer
- Data Presentation
- App & Data Security

**Expected output**: Structured outline with Epic titles and story titles (no descriptions yet).

---

## Tools

| Tool | Purpose |
|------|---------|
| `ConfluencePublishTool` | Publish/update PRD pages on Confluence |
| `JiraCreateIssueTool` | Create Epics, Stories, Sub-tasks in Jira |

---

## PRD Flow Phase

**Confluence**: Post-completion — triggered after all PRD sections are approved.

**Jira**: Multi-phase approval workflow:
- Phase 1: Skeleton generation (Epics + Stories outline)
- Phase 2: Epic & Story creation (after user approval)
- Phase 3: Sub-task creation (after user approval)
- Phase 4a/4b: Staff Engineer + QA Lead review sub-tasks
- Phase 5: QA Engineer test counter-tickets

---

## Source Files

- `agents/orchestrator/config/agent.yaml` — role, goal, backstory
- `agents/orchestrator/config/tasks.yaml` — task definitions
- `agents/orchestrator/agent.py` — agent factory functions (orchestrator, delivery manager, Jira PM/architect)

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]], [[Confluence Integration]], [[Jira Integration]], [[Orchestrator Overview]]
