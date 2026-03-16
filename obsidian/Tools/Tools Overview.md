# Tools Overview

> CrewAI tool wrappers used by agents.

## Active Tools (v0.13.0+)

| Tool | File | Used By | Purpose |
|------|------|---------|---------|
| `FileReadTool` | `tools/file_read_tool.py` | Product Manager | Read files |
| `DirectoryReadTool` | `tools/directory_read_tool.py` | Product Manager | List directories |
| `ConfluenceTool` | `tools/confluence_tool.py` | Orchestrator | Confluence REST API |
| `JiraCreateIssueTool` | `tools/jira_tool.py` → `jira/` | Orchestrator | Jira REST API |
| `SlackSendMessageTool` | `tools/slack_tools.py` | Flow handlers | Post to Slack |
| `SlackReadMessagesTool` | `tools/slack_tools.py` | Flow handlers | Read Slack messages |
| `SlackPostPRDResultTool` | `tools/slack_tools.py` | Flow handlers | Post PRD summary + file upload |
| `SlackInterpretMessageTool` | `tools/slack_tools.py` | Event handlers | Intent classification |
| `PRDFileWriteTool` | `tools/file_write_tool.py` | Finalization | Write PRD files |

## Chat/Intent Tools

| Tool | File | Purpose |
|------|------|---------|
| `gemini_chat.py` | `tools/` | Gemini LLM intent classification |
| `openai_chat.py` | `tools/` | OpenAI LLM intent classification (fallback) |

## Token Management

| Tool | File | Purpose |
|------|------|---------|
| `slack_token_manager.py` | `tools/` | Token rotation, exchange, persistence |

## Jira Package (`tools/jira/`)

| File | Purpose |
|------|---------|
| `_operations.py` | Core Jira API operations (create, search, link) |
| `_helpers.py` | ADF converter, URL resolution, helpers |
| Others | Specialised Jira operations |

## Figma Make Package (`tools/figma/`) — v0.22.0

| File | Purpose |
|------|---------|
| `_config.py` | Configuration + credential resolution (API key → OAuth → session) |
| `_api.py` | Figma REST API client (`get_team_projects`, `get_project_files`, `get_file_info`, `refresh_oauth_token`, `exchange_oauth_code`) |
| `_client.py` | Playwright browser automation — `run_figma_make(prompt, project_config=...)` with OAuth cookie injection |
| `figma_make_tool.py` | CrewAI `BaseTool` wrapper (`FigmaMakeTool`) with `_project_config` injection |
| `login.py` | Dual-mode login: default session login or `--oauth` for OAuth2 flow |

> Auth priority: project API key → OAuth token (not expired) → Playwright session file. Project credentials stored in `projectConfig` collection. Uses Playwright headless Chromium to drive `figma.com/make/new`.

## Removed Tools (v0.13.0)

- `SerperDevTool` (Google search) — never invoked during PRD flows
- `ScrapeWebsiteTool` — never invoked
- `WebsiteSearchTool` — never invoked

---

See also: [[Agent Roles]], [[Slack Integration]]
