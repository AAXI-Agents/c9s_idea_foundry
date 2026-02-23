# CrewaiProductfeaturePlanner Crew

Welcome to the CrewaiProductfeaturePlanner Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

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

- Modify `src/crewai_productfeature_planner/config/agents.yaml` to define your agents
- Modify `src/crewai_productfeature_planner/config/tasks.yaml` to define your tasks
- Modify `src/crewai_productfeature_planner/crew.py` to add your own logic, tools and specific args
- Modify `src/crewai_productfeature_planner/main.py` to add custom inputs for your agents and tasks

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

Key endpoints:

- `POST /flow/prd/kickoff` — start a PRD flow
- `POST /flow/prd/approve` — approve or continue refinement
- `GET /flow/runs/{run_id}` — check run status

Swagger UI is available at `http://localhost:8000/docs`.

### Start with ngrok

Use the helper script to start the API with an ngrok tunnel:

```bash
$ ./scripts/start_api_ngrok.sh
```

The script calls `uv run start_api --ngrok` and prints the public URL.

## Environment Variables

Copy `.env.example` to `.env` and fill in real values. Required and optional variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes**\* | — | OpenAI API key (required when `DEFAULT_AGENT=openai_pm` or `DEFAULT_MULTI_AGENTS=2`) |
| `OPENAI_MODEL` | No | `o3` | OpenAI model for the Product Manager agent |
| `DEFAULT_AGENT` | No | `openai_pm` | Primary agent for all LLM tasks (`openai_pm`). |
| `DEFAULT_MULTI_AGENTS` | No | `1` | Number of PM agents to run in parallel. |
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
| `NGROK_AUTHTOKEN` | No | — | Required for ngrok remote access |
| `LLM_TIMEOUT` | No | `300` | LLM request timeout in seconds |
| `LLM_MAX_RETRIES` | No | `3` | Retries on transient LLM errors |
| `LLM_RETRY_BASE_DELAY` | No | `5` | Base delay (seconds) for exponential back-off |

## Understanding Your Crew

The crewai_productfeature_planner Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the CrewaiProductfeaturePlanner Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
