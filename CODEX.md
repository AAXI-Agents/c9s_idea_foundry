# CODEX — AI Agent Developer Guide

> **Purpose**: Reduce token usage when working with AI coding agents
> (Copilot, Codex, Cursor, etc.) by documenting the modular layout so
> agents can load only the files they need.

## Quick Reference

| Area | Entry point | Key files |
|------|------------|-----------|
| **Server / CLI** | `src/.../main.py` | FastAPI app, CLI entrypoint |
| **PRD Flow** | `src/.../flows/prd_flow.py` | CrewAI Flow orchestrating the full PRD lifecycle |
| **Orchestrator** | `src/.../orchestrator/` | Pipeline runner + stage factories (see below) |
| **Agents** | `src/.../agents/` | CrewAI agent configs (idea_refiner, requirements_breakdown, etc.) |
| **APIs** | `src/.../apis/` | FastAPI routers (health, prd) |
| **MongoDB** | `src/.../mongodb/` | DB client, repositories (working_ideas, finalized_ideas, crew_jobs) |
| **Tools** | `src/.../tools/` | CrewAI tools (confluence, jira, file I/O, search) |
| **Scripts** | `src/.../scripts/` | Logging, preflight checks, retry, ngrok tunnel |
| **Tests** | `tests/` | Mirror of `src/` layout; pytest |

---

## Orchestrator Module Map

The orchestrator was split from a single 1,378-line `stages.py` into
focused sub-modules. **Load only the file you need.**

```
src/crewai_productfeature_planner/orchestrator/
  orchestrator.py          AgentOrchestrator, AgentStage, StageResult
  stages.py                Re-export facade (backward compat — all names)

  _helpers.py              _has_gemini_credentials, _has_confluence_credentials,
                           _has_jira_credentials, _print_delivery_status

  _idea_refinement.py      build_idea_refinement_stage(flow)
  _requirements.py         build_requirements_breakdown_stage(flow)
  _confluence.py           build_confluence_publish_stage(flow)
  _jira.py                 _extract_issue_keys, build_jira_ticketing_stage(flow)

  _pipelines.py            build_default_pipeline(flow),
                           build_post_completion_pipeline(flow)

  _post_completion.py      build_post_completion_crew(flow, progress_callback)
  _startup_review.py       _discover_publishable_prds,
                           build_startup_markdown_review_stage,
                           build_startup_pipeline
  _startup_delivery.py     DeliveryItem, _discover_pending_deliveries,
                           build_startup_delivery_crew(item, progress_callback)
```

### When to load which file

| Task | File(s) to read |
|------|----------------|
| Fix credential checks | `_helpers.py` |
| Change idea refinement logic | `_idea_refinement.py` |
| Change requirements breakdown | `_requirements.py` |
| Fix Confluence publishing | `_confluence.py` |
| Fix Jira ticket creation | `_jira.py` |
| Change pipeline composition | `_pipelines.py` |
| Fix post-completion delivery | `_post_completion.py` |
| Fix startup PRD publishing | `_startup_review.py` |
| Fix startup pending deliveries | `_startup_delivery.py` |

---

## Test Module Map

Tests mirror the source modules:

```
tests/orchestrator/
  test_stages.py              Smoke test (facade import check only)
  test_helpers.py             Credential checks, _print_delivery_status
  test_idea_refinement.py     TestIdeaRefinementStage
  test_requirements.py        TestRequirementsBreakdownStage
  test_confluence.py          TestConfluencePublishStage
  test_jira.py                TestExtractIssueKeys, TestJiraTicketingStage
  test_pipelines.py           TestBuildDefaultPipeline, TestBuildPostCompletionPipeline
  test_post_completion.py     TestBuildPostCompletionCrew
  test_startup_review.py      TestDiscoverPublishablePrds, TestStartupMarkdownReviewStage,
                              TestStartupPipeline
  test_startup_delivery.py    TestDiscoverPendingDeliveries, TestBuildStartupDeliveryCrew
```

---

## Patch Target Cheat Sheet

When writing `@patch(...)` in tests, patch the name **where it is
imported**, not where it is defined:

| Function | Patch target |
|----------|-------------|
| `_has_gemini_credentials` in `_post_completion.py` | `...orchestrator._post_completion._has_gemini_credentials` |
| `_has_jira_credentials` in `_startup_delivery.py` | `...orchestrator._startup_delivery._has_jira_credentials` |
| `_has_confluence_credentials` in `_startup_review.py` | `...orchestrator._startup_review._has_confluence_credentials` |
| `_discover_publishable_prds` in `_startup_review.py` | `...orchestrator._startup_review._discover_publishable_prds` |

> **Rule of thumb**: Patch `<module_where_used>.<name>`, not
> `<module_where_defined>.<name>`.

---

## Common Commands

```bash
# Run all tests
.venv/bin/python -m pytest -x -q

# Run just orchestrator tests
.venv/bin/python -m pytest tests/orchestrator/ -x -q

# Run a single test module
.venv/bin/python -m pytest tests/orchestrator/test_jira.py -x -q

# Start the server
./start_server.sh
```

---

## Project Conventions

- **Python 3.11** with type hints throughout
- **CrewAI** framework for multi-agent orchestration
- **Pydantic v2** models for API request/response and flow state
- **MongoDB** for PRD persistence (working ideas, finalized ideas, delivery records)
- Tests use `unittest.mock.patch` + `monkeypatch` for env vars
- All source packages have `__init__.py` with explicit `__all__`
