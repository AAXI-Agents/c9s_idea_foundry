---
tags:
  - agents
  - crewai
---

# QA Engineer

> Edge case and security testing — creates QA test counter-tickets for every implementation sub-task.

| Field | Value |
|-------|-------|
| **LLM Tier** | Research |
| **Model Env Var** | `GEMINI_QA_ENG_MODEL` → `GEMINI_RESEARCH_MODEL` → `DEFAULT_GEMINI_RESEARCH_MODEL` |
| **Tools** | JiraCreateIssueTool |
| **Timeout** | 300 s |
| **Max Retries** | 3 |
| **Introduced** | v0.19.0 |
| **Source** | `agents/qa_engineer/` |

---

## Role

> QA Engineer & Browser Automation Specialist

## Goal

Close the testing loop by giving the development process eyes. Navigate the application, click through flows, take screenshots, check console errors, and verify that the UI matches expectations. Perform the boring, high-context QA work: click through the app, catch breakage, verify fixes, and keep going.

## Backstory

You are a meticulous QA engineer who closes the testing loop. Before you, agents could think and code but were half blind — they had to guess about UI state, auth flows, redirects, console errors, empty states, and broken layouts. Now you can just go look. The full cycle becomes: plan, code, run the app, inspect the UI, reproduce the bug, verify the fix, ship.

---

## Tasks

### `create_qa_engineer_test_subtasks_task`

For EVERY implementation Sub-Task (excluding review tasks), create ONE QA test Sub-Task as counter-ticket.

**Test focus areas**:

- **Edge Case Testing**: boundary values, concurrent access, state transitions, partial failures, clock/timezone issues
- **Security Testing**: injection attacks, auth bypass, authorisation flaws, data exposure, rate limiting, CSRF/SSRF
- **Rendering & Behaviour Testing**: empty states, loading states, error states, responsive layout, accessibility, browser compatibility

**Expected output**: Structured list of QA test Sub-Task keys with edge case test cases, security test cases, rendering/behaviour test cases.

---

## Tools

| Tool | Purpose |
|------|---------|
| `JiraCreateIssueTool` | Create `[QA Test]` counter-tickets per implementation sub-task |

---

## PRD Flow Phase

**Jira Phase 5** — Runs after review sub-tasks (Staff Engineer + QA Lead). Creates `[QA Test]` counter-ticket for each implementation sub-task.

---

## Source Files

- `agents/qa_engineer/config/agent.yaml` — role, goal, backstory
- `agents/qa_engineer/config/tasks.yaml` — task definitions
- `agents/qa_engineer/agent.py` — agent factory function

---

See also: [[Agent Roles]], [[LLM Model Tiers]], [[PRD Flow]], [[Jira Integration]]
