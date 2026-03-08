# Testing Guide

> Test structure, patterns, and common commands.

## Test Structure

Tests mirror the source layout (2033+ tests):

```
tests/
  conftest.py                    Global fixtures
  test_main.py                   CLI entry points
  test_version.py                Version module
  test_preflight.py              Preflight checks
  test_retry.py                  Retry wrapper
  ...
  agents/                        Agent tests
  apis/                          API tests
    health/
    prd/
    publishing/
    slack/                       Slack integration tests
  components/                    CLI components
  flows/                         PRD flow tests
  mongodb/                       Database tests
  orchestrator/                  Pipeline tests
  tools/                         Tool tests
```

## Common Commands

```bash
# Run all tests
.venv/bin/python -m pytest -x -q

# Run just orchestrator tests
.venv/bin/python -m pytest tests/orchestrator/ -x -q

# Run a single test module
.venv/bin/python -m pytest tests/orchestrator/test_jira.py -x -q

# Run with verbose output
.venv/bin/python -m pytest tests/ -v

# Run specific test class
.venv/bin/python -m pytest tests/orchestrator/test_jira.py::TestJiraTicketingStage -x -q
```

## Patch Target Rules

When writing `@patch(...)` in tests, patch the name **where it is imported**, not where it is defined.

| Function | Patch target |
|----------|-------------|
| `_has_gemini_credentials` in `_post_completion.py` | `...orchestrator._post_completion._has_gemini_credentials` |
| `_has_jira_credentials` in `_startup_delivery.py` | `...orchestrator._startup_delivery._has_jira_credentials` |
| `_has_confluence_credentials` in `_startup_review.py` | `...orchestrator._startup_review._has_confluence_credentials` |
| `_discover_publishable_prds` in `_startup_review.py` | `...orchestrator._startup_review._discover_publishable_prds` |

> **Rule of thumb**: Patch `<module_where_used>.<name>`, not `<module_where_defined>.<name>`.

## Key Orchestrator Tests

| Test File | Classes |
|-----------|---------|
| `test_stages.py` | Smoke test (facade import check) |
| `test_helpers.py` | Credential checks, delivery status |
| `test_idea_refinement.py` | TestIdeaRefinementStage |
| `test_requirements.py` | TestRequirementsBreakdownStage |
| `test_confluence.py` | TestConfluencePublishStage |
| `test_jira.py` | TestExtractIssueKeys, TestJiraTicketingStage |
| `test_pipelines.py` | TestBuildDefaultPipeline, TestBuildPostCompletionPipeline |
| `test_post_completion.py` | TestBuildPostCompletionCrew |
| `test_startup_review.py` | TestDiscoverPublishablePrds, TestStartupPipeline |
| `test_startup_delivery.py` | TestDiscoverPendingDeliveries, TestBuildStartupDeliveryCrew |

## Best Practices

- Use `-x` (fail-fast) during development
- Check `logs/crewai.log` for new `WARNING` / `ERROR` entries after changes
- Fix regressions before moving to the next task
- Tests use `unittest.mock.patch` + `monkeypatch` for env vars
- Always verify all tests pass before committing

---

See also: [[Coding Standards]], [[Module Map]]
