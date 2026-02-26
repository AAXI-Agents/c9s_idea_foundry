# CrewaiProductfeaturePlanner Crew

Welcome to the Crewai Product Feature Planner Crew project, powered by [crewAI](https://crewai.com). This crew project design to take a simple idea and create a detail product requirement documentation and associated engineering tickets for development.

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file.** Optionally set `GOOGLE_API_KEY` (or `GOOGLE_CLOUD_PROJECT` for Vertex AI) to enable Gemini-powered idea refinement and requirements breakdown.

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command runs the PRD flow interactively. You will be prompted to provide a feature idea and approve each iteration until you finalize.

You can also pass the idea directly:

```bash
$ crewai run "Add dark mode to the dashboard"
```

## API Server (FastAPI)

Start the API server locally:

```bash
$ uv run start_api
```

Swagger UI is available at `http://localhost:8000/docs`.
OpenAPI JSON spec is available at `http://localhost:8000/openapi.json`.

A hand-maintained OpenAPI spec with `$ref`-based path splitting is in `docs/openapi/`.

### Start with ngrok

Use the helper script to start the API with an ngrok tunnel:

```bash
$ ./scripts/start_api_ngrok.sh
```

The script calls `uv run start_api --ngrok` and prints the public URL.

### API Endpoints Reference

#### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — returns `{"status": "ok"}` |
| `GET` | `/health/slack-token` | Slack token rotation diagnostics (no secrets exposed) |
| `POST` | `/health/slack-token/exchange` | One-time exchange of a long-lived `xoxb-` token for rotating tokens |
| `POST` | `/health/slack-token/refresh` | Force-refresh the Slack access token |

#### Flow Runs

| Method | Path | Description |
|---|---|---|
| `POST` | `/flow/prd/kickoff` | Start a PRD generation flow (async, 202) |
| `POST` | `/flow/prd/approve` | Approve or continue section refinement |
| `POST` | `/flow/prd/pause` | Pause and save current progress |
| `GET` | `/flow/prd/resumable` | List paused / unfinalized runs |
| `POST` | `/flow/prd/resume` | Resume a paused run |
| `GET` | `/flow/runs/{run_id}` | Get run status, section progress, and draft content |
| `GET` | `/flow/runs` | List all in-memory runs |

#### Jobs

| Method | Path | Description |
|---|---|---|
| `GET` | `/flow/jobs` | List persistent job records from MongoDB |
| `GET` | `/flow/jobs/{job_id}` | Get a single job record |

#### Slack Messenger

| Method | Path | Description |
|---|---|---|
| `POST` | `/slack/kickoff` | Start a Slack-triggered PRD flow (async) |
| `POST` | `/slack/kickoff/sync` | Start a Slack-triggered PRD flow (synchronous; blocks until done) |

#### Slack Webhooks

| Method | Path | Description |
|---|---|---|
| `POST` | `/slack/events` | Slack Events API — handles `url_verification`, `app_mention`, `member_joined_channel`, threaded `message` |
| `POST` | `/slack/interactions` | Slack Interactivity — handles Block Kit button clicks and modal submissions |
| `GET` | `/slack/oauth/callback` | Slack OAuth v2 install/reinstall callback |

#### Publishing & Delivery

| Method | Path | Description |
|---|---|---|
| `GET` | `/publishing/pending` | List PRDs awaiting Confluence publish or Jira ticket creation |
| `POST` | `/publishing/confluence/all` | Batch-publish all pending PRDs to Confluence |
| `POST` | `/publishing/confluence/{run_id}` | Publish a single PRD to Confluence |
| `POST` | `/publishing/jira/all` | Batch-create Jira tickets for all eligible PRDs |
| `POST` | `/publishing/jira/{run_id}` | Create Jira tickets for a single PRD |
| `POST` | `/publishing/all` | Full batch: Confluence publish + Jira tickets for all pending |
| `POST` | `/publishing/all/{run_id}` | Full pipeline (Confluence + Jira) for a single PRD |
| `GET` | `/publishing/status/{run_id}` | Delivery status for a specific run |
| `GET` | `/publishing/automation/status` | File watcher & cron scheduler status |

### Webhook Callback Payload

When a `webhook_url` is provided on `/slack/kickoff` or `/slack/kickoff/sync`, the server POSTs the following JSON on completion or failure:

```json
{
  "run_id": "a1b2c3d4e5f6",
  "status": "completed",
  "result": { "...": "..." },
  "error": null
}
```

## Slack Integration

The bot supports two modes of operation in Slack:

### Standard Mode (default)

Mention the bot with a product idea and it generates a full PRD automatically:

```
@crewai-prd-bot create a PRD for a mobile fitness tracking app
```

The flow runs end-to-end with `auto_approve=true` and posts results back to the channel.

### Interactive Mode

Add keywords like *"interactive"*, *"step by step"*, or *"guided"* to an @mention:

```
@crewai-prd-bot interactive: create a PRD for a mobile fitness tracking app
```

Interactive mode mirrors the CLI experience inside Slack using Block Kit buttons:

1. **Refinement mode choice** — Agent-driven or manual (user types feedback in thread)
2. **Idea approval** — Approve the enriched idea or cancel
3. **Requirements approval** — Approve the structured requirements or cancel
4. **Auto-generation** — PRD sections are generated automatically after approval

### Slack App Setup

1. Create a Slack app from the manifest (`slack_manifest.json`)
2. Set environment variables: `SLACK_SIGNING_SECRET`, `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`
3. Start the server with ngrok: `./scripts/start_api_ngrok.sh`
4. Configure the Request URLs in Slack:
   - **Event Subscriptions** → `https://<ngrok>/slack/events`
   - **Interactivity & Shortcuts** → `https://<ngrok>/slack/interactions`
   - **OAuth Redirect URL** → `https://<ngrok>/slack/oauth/callback`
5. Install the app to your workspace (triggers the OAuth callback)

### Slack Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_SIGNING_SECRET` | **Yes** | HMAC-SHA256 signing secret for request verification |
| `SLACK_CLIENT_ID` | **Yes** | Slack app client ID (for OAuth) |
| `SLACK_CLIENT_SECRET` | **Yes** | Slack app client secret (for OAuth) |
| `SLACK_ACCESS_TOKEN` | No | Bot token — auto-populated after OAuth install |
| `SLACK_REFRESH_TOKEN` | No | Refresh token for rotating tokens (auto-populated after exchange) |
| `SLACK_VERIFICATION_TOKEN` | No | Deprecated fallback for request verification (use `SLACK_SIGNING_SECRET` instead) |
| `SLACK_DEFAULT_CHANNEL` | No | Default channel for posting results (default: `crewai-prd-planner`) |
| `SLACK_TOKEN_STORE` | No | Path to JSON file for persisting rotated tokens (default: `.slack_tokens.json`) |
| `SLACK_BYPASS` | No | Set to `1` or `true` to skip actual Slack API calls (dry-run mode) |

## Environment Variables

Copy `.env.example` to `.env` and fill in real values. Required and optional variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes**\* | — | OpenAI API key (required when `DEFAULT_AGENT=openai` or `DEFAULT_MULTI_AGENTS=2`) |
| `OPENAI_MODEL` | No | `o3` | OpenAI model for the Product Manager agent |
| `DEFAULT_AGENT` | No | `gemini` | Primary LLM provider for the Product Manager agent (`openai` or `gemini`). |
| `DEFAULT_MULTI_AGENTS` | No | `1` | Number of PM agents to run in parallel (one per provider). |
| `GOOGLE_API_KEY` | **Yes**\* | — | Google API key ([get one here](https://aistudio.google.com/apikey)). Required for Gemini-powered idea refinement and requirements breakdown. Either this or `GOOGLE_CLOUD_PROJECT` must be set. |
| `GOOGLE_CLOUD_PROJECT` | **Yes**\* | — | Google Cloud project ID with Vertex AI API enabled. Alternative to `GOOGLE_API_KEY`. Authenticate via `gcloud auth application-default login`. |
| `GOOGLE_CLOUD_LOCATION` | No | `asia-southeast1` | Google Cloud region for Vertex AI ([available regions](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations)) |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Gemini model to use ([available models](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models)) |
| `IDEA_REFINER_MIN_ITERATIONS` | No | `3` | Minimum idea-refinement cycles before the refiner can stop |
| `IDEA_REFINER_MAX_ITERATIONS` | No | `10` | Maximum idea-refinement cycles |
| `IDEA_REFINER_MODEL` | No | `GEMINI_MODEL` | Override the Gemini model used by the Idea Refinement agent |
| `REQUIREMENTS_BREAKDOWN_MIN_ITERATIONS` | No | `3` | Minimum requirements-breakdown cycles before the agent can stop |
| `REQUIREMENTS_BREAKDOWN_MAX_ITERATIONS` | No | `10` | Maximum requirements-breakdown cycles |
| `REQUIREMENTS_BREAKDOWN_MODEL` | No | `GEMINI_MODEL` | Override the Gemini model used by the Requirements Breakdown agent |
| `PRD_SECTION_MIN_ITERATIONS` | No | `2` | Minimum critique→refine iterations per PRD section |
| `PRD_SECTION_MAX_ITERATIONS` | No | `10` | Maximum critique→refine iterations per PRD section |
| `SERPER_API_KEY` | **Yes** | — | Google search via SerperDev for market research |
| `MONGODB_URI` | No | `localhost` | MongoDB host |
| `MONGODB_PORT` | No | `27017` | MongoDB port |
| `MONGODB_DB` | No | `ideas` | MongoDB database name |
| `MONGODB_USERNAME` | No | — | MongoDB auth username |
| `MONGODB_PASSWORD` | No | — | MongoDB auth password |
| `SLACK_SIGNING_SECRET` | **Yes**\* | — | HMAC-SHA256 signing secret for Slack request verification |
| `SLACK_CLIENT_ID` | **Yes**\* | — | Slack app client ID (for OAuth) |
| `SLACK_CLIENT_SECRET` | **Yes**\* | — | Slack app client secret (for OAuth) |
| `SLACK_ACCESS_TOKEN` | No | — | Bot token — auto-populated after OAuth install |
| `SLACK_REFRESH_TOKEN` | No | — | Refresh token for rotating tokens |
| `SLACK_VERIFICATION_TOKEN` | No | — | Deprecated fallback for request verification |
| `SLACK_DEFAULT_CHANNEL` | No | `crewai-prd-planner` | Default Slack channel for posting results |
| `SLACK_TOKEN_STORE` | No | `.slack_tokens.json` | Path to JSON file for persisting rotated tokens |
| `SLACK_BYPASS` | No | `false` | Set to `1`/`true` to skip actual Slack API calls (dry-run) |
| `NGROK_AUTHTOKEN` | No | — | Required for ngrok remote access |
| `LLM_TIMEOUT` | No | `300` | LLM request timeout in seconds |
| `LLM_MAX_RETRIES` | No | `3` | Retries on transient LLM errors |
| `LLM_RETRY_BASE_DELAY` | No | `5` | Base delay (seconds) for exponential back-off |
| `PUBLISH_WATCHER_ENABLED` | No | `1` | Set to `0` or `false` to disable the file watcher that auto-publishes new PRD markdown files |
| `PUBLISH_WATCHER_POLL_SECONDS` | No | `10` | Polling interval (seconds) for the file watcher |
| `PUBLISH_SCHEDULER_ENABLED` | No | `1` | Set to `0` or `false` to disable the cron scheduler that resumes incomplete deliveries |
| `PUBLISH_SCAN_INTERVAL_SECONDS` | No | `300` | How often (seconds) the scheduler scans for incomplete deliveries (minimum 30) |

## Understanding Your Crew

The crewai_productfeature_planner Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.