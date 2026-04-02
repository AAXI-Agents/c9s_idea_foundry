---
tags:
  - api
  - endpoints
  - integrations
---

# GET /integrations/status

> Check Confluence and Jira integration configuration status.

**Method**: `GET`
**Path**: `/integrations/status`
**Auth**: SSO Bearer token
**Tags**: Integrations

---

## Request

No parameters.

---

## Response — 200

```json
{
  "confluence": {
    "configured": true,
    "base_url": "https://mycompany.atlassian.net",
    "project_key": ""
  },
  "jira": {
    "configured": true,
    "base_url": "https://mycompany.atlassian.net",
    "project_key": "MCR"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `confluence.configured` | `bool` | Whether `ATLASSIAN_BASE_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN` are all set |
| `confluence.base_url` | `string` | Masked base URL (scheme + hostname only) — empty if not configured |
| `jira.configured` | `bool` | Whether all Confluence vars + `JIRA_PROJECT_KEY` are set |
| `jira.base_url` | `string` | Masked base URL — empty if not configured |
| `jira.project_key` | `string` | Jira project key — empty if not configured |

---

## Database Algorithm

No database access. Reads environment variables:
1. Check `ATLASSIAN_BASE_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN` → Confluence status
2. Check same + `JIRA_PROJECT_KEY` → Jira status
3. Mask `ATLASSIAN_BASE_URL` to show only scheme + hostname (security)
4. Return `IntegrationStatusResponse`

---

## Source

- **Router**: `apis/integrations/router.py`
- **Env vars**: `ATLASSIAN_BASE_URL`, `ATLASSIAN_USERNAME`, `ATLASSIAN_API_TOKEN`, `JIRA_PROJECT_KEY`

---

## Change Requests

### Pending

_No pending change requests._

### Completed

_No completed change requests._
