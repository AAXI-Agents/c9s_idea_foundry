# Environment Variables

> Key environment variables for the CrewAI PRD Planner.

## LLM Providers

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google Gemini LLM access |
| `GEMINI_MODEL` | **Basic** model — intent classification, next-step prediction |
| `GEMINI_RESEARCH_MODEL` | **Research** model — idea refinement, PRD drafting, Jira |
| `GEMINI_CRITIC_MODEL` | **Critic** model — lightweight section critique |
| `OPENAI_MODEL` | **Basic** OpenAI model — intent classification |
| `OPENAI_RESEARCH_MODEL` | **Research** OpenAI model — PRD section drafting & critique |
| `CRITIC_LLM_TIMEOUT` | Timeout for critic agent calls |

## Slack

| Variable | Purpose |
|----------|---------|
| `SLACK_BOT_TOKEN` | Slack bot API token (`xoxb-`) |
| `SLACK_SIGNING_SECRET` | Request HMAC-SHA256 verification |
| `SLACK_APP_ID` | For manifest auto-update |
| `SLACK_APP_CONFIGURATION_TOKEN` | Manifest API token (must be `xoxe.xoxp-` prefix) |
| `SLACK_ACCESS_TOKEN` | Alternative token env var |

## Networking

| Variable | Purpose |
|----------|---------|
| `NGROK_DOMAIN` | Stable ngrok domain (avoids manifest updates) |
| `NGROK_AUTHTOKEN` | ngrok authentication |

## Database

| Variable | Purpose |
|----------|---------|
| `MONGODB_ATLAS_URI` | MongoDB Atlas connection string (`mongodb+srv://...`) — **required** |
| `MONGODB_DB` | Database name (default: `ideas`) |

## Atlassian

| Variable | Purpose |
|----------|---------|
| `CONFLUENCE_URL` | Confluence instance base URL |
| `CONFLUENCE_USERNAME` | Confluence API username |
| `CONFLUENCE_API_TOKEN` | Confluence API token |
| `CONFLUENCE_PARENT_ID` | Optional parent page ID (pages at space root if unset) |
| `JIRA_URL` / `ATLASSIAN_BASE_URL` | Jira instance URL |
| `JIRA_USERNAME` | Jira API username |
| `JIRA_API_TOKEN` | Jira API token |

## Flow Configuration

| Variable | Purpose |
|----------|---------|
| `PRD_SECTION_MIN_ITERATIONS` | Min section refinement cycles |
| `PRD_SECTION_MAX_ITERATIONS` | Max section refinement cycles |
| `DEFAULT_MULTI_AGENTS` | Number of parallel agents (default: 1) |

---

See also: [[Project Overview]], [[LLM Model Tiers]]
