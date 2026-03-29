# Environment Variables

> Key environment variables for Idea Foundry (CrewAI PRD Planner).

## Web App Integration

| Variable | Purpose |
|----------|---------|
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins for web app (default: `http://localhost:3000`). Comma-separated for multiple origins |
| `SSO_ENABLED` | Enable SSO auth enforcement (`true`/`false`, default `false`). Set `false` for local dev (anonymous bypass) |
| `SSO_BASE_URL` | SSO service base URL for remote token introspection (default `http://localhost:8100`) |
| `SSO_JWT_PUBLIC_KEY_PATH` | Path to RS256 public key PEM (for fast local JWT verification) |
| `SSO_ISSUER` | Expected JWT issuer claim (default `c9s-sso`) |
| `SSO_EXPECTED_APP_ID` | When set, only accept tokens with this `app_id` (Idea Foundry) |
| `SSO_WEBHOOK_SECRET` | HMAC-SHA256 secret for verifying SSO webhook payloads |

> **Application name**: "Idea Foundry" — registered as an OAuth client in the SSO service. When `SSO_EXPECTED_APP_ID` is set, tokens must be issued through the OAuth authorization-code flow for that specific application.

## LLM Providers

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google Gemini LLM access |
| `GEMINI_MODEL` | **Basic** model — intent classification, next-step prediction |
| `GEMINI_RESEARCH_MODEL` | **Research** model — idea refinement, PRD drafting, Jira |
| `GEMINI_CRITIC_MODEL` | **Critic** model — lightweight section critique |
| `ENGAGEMENT_MANAGER_MODEL` | Override Gemini model for Engagement Manager (defaults to `GEMINI_MODEL`) |
| `ENGAGEMENT_MANAGER_USE_CREWAI` | Set `true` to force CrewAI path instead of fast direct REST API (v0.43.3) |
| `IDEA_AGENT_MODEL` | Override Gemini model for Idea Agent (defaults to `GEMINI_MODEL`) |
| `IDEA_AGENT_USE_CREWAI` | Set `true` to force CrewAI path instead of fast direct REST API (v0.43.3) |
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
| `SERVER_ENV` | Deployment tier — `DEV` (ngrok tunnel), `UAT` (static domain), `PROD` (static domain). Default `DEV` |
| `DOMAIN_NAME_UAT` | Public domain for UAT (e.g. `prd-planner-uat.cloudninesoftware.vn`). Required when `SERVER_ENV=UAT` |
| `DOMAIN_NAME_PROD` | Public domain for PROD (e.g. `prd-planner.cloudninesoftware.vn`). Required when `SERVER_ENV=PROD` |
| `NGROK_DOMAIN` | Stable ngrok domain (avoids manifest updates) |
| `NGROK_AUTHTOKEN` | ngrok authentication (required for DEV mode) |

## Database

| Variable | Purpose |
|----------|---------|
| `MONGODB_ATLAS_URI` | MongoDB Atlas connection string (`mongodb+srv://...`) — **required** |
| `MONGODB_DB` | Database name (default: `ideas`). Change to target a different DB (e.g. `ideas_dev`, `ideas_uat`, `ideas_prod`) |

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

## Figma (v0.22.0 — Playwright + OAuth + REST API)

| Variable | Purpose |
|----------|---------|
| `FIGMA_SESSION_DIR` | Directory for Playwright session state (default `~/.figma_session`) |
| `FIGMA_MAKE_TIMEOUT` | Timeout in seconds for design generation (default `300`) |
| `FIGMA_HEADLESS` | Run browser in headless mode — `"true"` (default) or `"false"` |
| `FIGMA_CLIENT_ID` | OAuth2 app client ID (for token exchange) |
| `FIGMA_CLIENT_SECRET` | OAuth2 app client secret |

> **Auth priority**: Project API key → OAuth token (not expired) → Playwright session file.
>
> **Project-level config** (stored in `projectConfig` collection): `figma_api_key`, `figma_team_id`, `figma_oauth_token`, `figma_oauth_refresh_token`, `figma_oauth_expires_at`.
>
> **Setup**: Run `python -m crewai_productfeature_planner.tools.figma.login` for session login, or `--oauth` flag for OAuth2 flow.

## Agent Model Overrides

| Variable | Purpose |
|----------|---------|
| `GEMINI_CEO_MODEL` | Override LLM for CEO Reviewer agent |
| `GEMINI_ENG_MODEL` | Override LLM for Eng Manager agent |
| `GEMINI_STAFF_ENG_MODEL` | Override LLM for Staff Engineer agent |
| `GEMINI_QA_LEAD_MODEL` | Override LLM for QA Lead agent |
| `GEMINI_QA_ENG_MODEL` | Override LLM for QA Engineer agent |
| `GEMINI_UX_DESIGNER_MODEL` | Override LLM for UX Designer agent |

## Flow Configuration

| Variable | Purpose |
|----------|---------|
| `PRD_SECTION_MIN_ITERATIONS` | Min section refinement cycles |
| `PRD_SECTION_MAX_ITERATIONS` | Max section refinement cycles |
| `DEFAULT_MULTI_AGENTS` | Number of parallel agents (default: 1) |

---

See also: [[Project Overview]], [[LLM Model Tiers]], [[API Overview]]
