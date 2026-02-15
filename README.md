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

**Add your `OPENAI_API_KEY` into the `.env` file**

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

Ensure you set the required variables in `.env`:

- `OPENAI_API_KEY`
- `MODEL` and optional `PM_MODEL`
- `MONGODB_URI` (default `mongodb://localhost:27017`)
- `MONGODB_USERNAME` / `MONGODB_PASSWORD` (optional)
- `NGROK_AUTHTOKEN` (required for ngrok)

## Understanding Your Crew

The crewai_productfeature_planner Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the CrewaiProductfeaturePlanner Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
