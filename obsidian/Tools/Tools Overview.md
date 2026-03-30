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
| `gemini_chat.py` | `tools/` | Gemini LLM intent classification + direct chat response (v0.43.3) |
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

## Removed Tools (v0.13.0)

- `SerperDevTool` (Google search) — never invoked during PRD flows
- `ScrapeWebsiteTool` — never invoked
- `WebsiteSearchTool` — never invoked
- `FigmaMakeTool` (v0.22.0–v0.44.0) — Figma Make integration removed in v0.45.0; UX design now produces markdown specifications

---

See also: [[Agent Roles]], [[Slack Integration]]
