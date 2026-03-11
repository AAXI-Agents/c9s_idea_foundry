# CrewAI Framework Reference

> How this project uses CrewAI's core concepts — Agents, Tasks, Crews, Flows, Tools, Knowledge, and Memory.
> Reference: [CrewAI Docs](https://docs.crewai.com/en)

---

## Core Concepts

CrewAI is a multi-agent orchestration framework. The six building blocks are:

| Concept | What it is | How we use it |
|---------|-----------|---------------|
| **Agent** | Autonomous unit with role, goal, backstory, tools, LLM | 5 agents: Idea Refiner, Product Manager, Requirements Breakdown, Orchestrator, Delivery Manager |
| **Task** | Specific assignment for an agent with description, expected output | Each PRD section is a separate task; critique/refine are paired tasks |
| **Crew** | Group of agents + tasks executing together | Post-completion crew (Confluence + Jira delivery), startup delivery crew |
| **Flow** | Event-driven orchestration with state management | `PRDFlow` — the main pipeline: idea → refinement → sections → delivery |
| **Tool** | Capability agents can invoke (file I/O, API calls) | Custom tools: Confluence, Jira, FileRead, DirectoryRead, Slack |
| **Knowledge** | External data sources agents consult during tasks | Text files in `knowledge/` — PRD guidelines, user preferences, project architecture |
| **Memory** | Persistent context across tasks and runs | Crew-level memory with `google-vertex` embedder |

---

## Agents

An Agent is defined by `role`, `goal`, `backstory`, `llm`, `tools`, and optional `knowledge_sources`.

### Key Agent Attributes We Use

| Attribute | Our usage |
|-----------|----------|
| `role` / `goal` / `backstory` | Define agent personality and expertise |
| `llm` | Two tiers — Basic (`GEMINI_MODEL`) for routing, Research (`GEMINI_RESEARCH_MODEL`) for content generation |
| `tools` | Custom `BaseTool` subclasses (see [[Tools Overview]]) |
| `knowledge_sources` | `TextFileKnowledgeSource` pointing to `knowledge/*.txt` |
| `verbose` | Enabled in development for debugging |
| `allow_delegation` | Disabled — agents work independently |
| `respect_context_window` | Enabled to prevent token overflow |
| `max_iter` | Default 20 — agents give best answer if stuck |

### Our Agent Definitions

All agents live in `src/.../agents/`:

| Agent | File | LLM Tier | Purpose |
|-------|------|----------|---------|
| Idea Refiner | `idea_refiner/agent.py` | Research | Iterative idea enrichment (3–10 cycles) |
| Product Manager | `product_manager/agent.py` | Research | PRD section drafting, critique, refinement |
| Requirements Breakdown | `requirements_breakdown/agent.py` | Research | Requirements decomposition (3–10 cycles) |
| Orchestrator | `orchestrator/agent.py` | Research | Confluence publish, Jira ticket creation |
| Delivery Manager | `orchestrator/agent.py` | Research | Startup delivery orchestration |

See [[Agent Roles]] for full configuration details.

---

## Tasks

A Task has `description`, `expected_output`, `agent`, optional `tools`, `context`, `callback`, and `guardrail`.

### Key Task Patterns We Use

- **Sequential execution**: Tasks run in order within a Crew
- **Context passing**: Output of one task feeds into the next via `context=[previous_task]`
- **Output files**: PRD sections saved to `output/prds/` via `output_file`
- **Callbacks**: `callback` functions notify Slack of progress after each task completes
- **Guardrails**: Validation functions ensure task output meets quality criteria before proceeding

### Task Creation Pattern

We create tasks programmatically (not YAML) because task descriptions are dynamic (interpolated with idea text, section titles, approved sections):

```python
task = Task(
    description=f"Draft the '{section_title}' section...",
    expected_output="A complete PRD section...",
    agent=product_manager_agent,
    tools=[file_read_tool],
    context=[previous_section_task],
)
```

---

## Crews

A Crew is a group of agents + tasks with a `process` (sequential or hierarchical).

### Key Crew Attributes We Use

| Attribute | Our usage |
|-----------|----------|
| `process` | `Process.sequential` — all our crews run tasks in order |
| `knowledge_sources` | Crew-level knowledge shared by all agents |
| `embedder` | `{"provider": "google-vertex", "config": {"model_name": "..."}}` |
| `memory` | Enabled for cross-task context retention |
| `verbose` | Enabled in development |
| `max_rpm` | Not set — we use per-agent rate limiting |

### Our Crew Instances

| Crew | Built by | Purpose |
|------|----------|---------|
| Post-completion crew | `_post_completion.py` | Confluence + Jira delivery after PRD is done |
| Startup delivery crew | `_startup_delivery.py` | Resume pending deliveries on server start |
| Idea refinement stage | `_idea_refinement.py` | Enrich raw idea into structured brief |
| Requirements stage | `_requirements.py` | Break idea into functional/non-functional requirements |

---

## Flows

Flows are the top-level orchestration layer — event-driven, with state management via Pydantic models.

### Key Flow Concepts

| Concept | Description |
|---------|-------------|
| `@start()` | Entry point — runs when `flow.kickoff()` is called |
| `@listen(method)` | Triggers when a previous method completes |
| `@router(method)` | Conditional branching based on method output |
| `Flow[StateModel]` | Typed state via Pydantic `BaseModel` |
| `self.state` | Shared state across all flow methods |
| `flow.kickoff()` | Starts execution; returns final method's output |

### Our Flow: `PRDFlow`

The main pipeline in `flows/prd_flow.py` uses structured state management:

```
@start() → idea_refinement
  @listen → requirements_breakdown
    @listen → executive_summary_draft
      @listen → section_loop (iterate over 10 PRD sections)
        Each section: draft → critique → refine (up to MAX_ITERATIONS)
      @listen → assemble_final_prd
        @listen → post_completion (Confluence + Jira delivery)
```

**State model**: `PRDFlowState(BaseModel)` tracks:
- `run_id`, `idea`, `refined_idea`, `requirements`
- `executive_summary`, `approved_sections` dict
- `current_section_key`, `iteration_count`
- `prd_output_path`, `confluence_url`
- Progress callbacks and approval callbacks

**Progress events**: The flow fires events via `_notify_progress()` that are consumed by Slack handlers — see [[PRD Flow]] for the full event table.

**Resume capability**: Flows can be paused (on error or user approval gate) and resumed from the last completed section using `restore_prd_state()` which rebuilds state from MongoDB.

---

## Tools

Tools extend agent capabilities. CrewAI tools subclass `BaseTool` with `name`, `description`, `args_schema`, and `_run()`.

### Our Custom Tools

| Tool | File | Purpose |
|------|------|---------|
| `ConfluencePublishTool` | `tools/confluence/` | Publish PRD to Confluence |
| `JiraCreateIssueTool` | `tools/jira/` | Create Jira Epic/Story/Sub-task |
| `FileReadTool` | `crewai_tools` | Read file contents |
| `DirectoryReadTool` | `crewai_tools` | List directory contents |
| `SlackSendTool` | `tools/slack/` | Post messages to Slack threads |

### Tool Design Patterns

- **Authoritative fields**: Tools like `JiraCreateIssueTool` have `authoritative_run_id` that overrides LLM-hallucinated values
- **Error handling**: Tools return error strings rather than raising — lets the agent retry
- **Caching**: Enabled by default for `FileReadTool` and `DirectoryReadTool`

See [[Tools Overview]] for implementation details.

---

## Knowledge

Knowledge sources provide agents with domain-specific context via RAG (retrieval-augmented generation).

### How We Use Knowledge

Files in `knowledge/` at project root:

| File | Fed to | Content |
|------|--------|---------|
| `prd_guidelines.txt` | Product Manager, Idea Refiner | 10-section PRD template, quality criteria |
| `user_preference.txt` | Idea Refiner | User workflow preferences, PRD style |
| `project_architecture.txt` | All agents | Tech stack, conventions, system design |

### Knowledge Configuration

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

knowledge_source = TextFileKnowledgeSource(file_paths=["prd_guidelines.txt"])

agent = Agent(
    role="Product Manager",
    knowledge_sources=[knowledge_source],
    embedder={"provider": "google-vertex", "config": {"model_name": "..."}},
)
```

### Key Points

- Knowledge sources are loaded at `crew.kickoff()` time, not at agent creation
- Agent-level knowledge is independent; crew-level knowledge is shared by all agents
- Embedder must match between knowledge storage and retrieval (we use `google-vertex`)
- Knowledge files must be kept in sync with code changes (see [[Coding Standards]] §5)

---

## Memory

CrewAI's unified Memory system provides persistent context across tasks and runs.

### How We Use Memory

- **Crew-level memory**: Enabled via `memory=True` on Crew instances
- **Embedder**: `google-vertex` provider (same as knowledge)
- **Persistence**: LanceDB backend stores memories locally
- **Cross-task context**: After each task, facts are extracted and stored; before each task, relevant context is recalled

### Memory in Flows

Flows have built-in memory via `self.remember()`, `self.recall()`, and `self.extract_memories()`:

```python
class PRDFlow(Flow[PRDFlowState]):
    @start()
    def begin(self):
        self.remember(f"Working on idea: {self.state.idea}", scope="/prd")
    
    @listen(begin)
    def next_step(self):
        past = self.recall("idea context", scope="/prd")
```

### Memory vs Knowledge

| Aspect | Knowledge | Memory |
|--------|-----------|--------|
| Source | Static files (txt, pdf, csv) | Dynamic — accumulated during execution |
| When loaded | At crew kickoff | Continuously during flow/crew execution |
| Scope | Agent-level or crew-level | Hierarchical scopes (`/project/alpha`) |
| Persistence | ChromaDB | LanceDB |
| Use case | Domain expertise, guidelines | Task output accumulation, cross-run learning |

---

## CrewAI Design Principles for This Project

### 1. Agents Are Specialists
Each agent has one focused role. We don't use `allow_delegation=True` — agents work independently on assigned tasks.

### 2. Flows Over Crews for Orchestration
The main pipeline uses a Flow (not a Crew) because we need event-driven control, conditional routing, state persistence, and resume capability. Crews are used for contained sub-workflows (delivery, startup).

### 3. Two-Tier LLM Strategy
Basic models for fast routing/classification, Research models for deep content generation. See [[LLM Model Tiers]].

### 4. Knowledge Is Static, Memory Is Dynamic
Knowledge files (`knowledge/*.txt`) provide stable domain expertise. Memory accumulates task outputs and decisions during execution.

### 5. Tools Are Minimal
Agents only get the tools they need. We removed web research tools (v0.13.0) to reduce hallucination. Current toolkit: FileRead + DirectoryRead for content agents, Confluence + Jira for delivery agents.

### 6. Guardrails and Callbacks
Task guardrails validate output quality. Callbacks notify Slack of progress. Both are wired through the Flow's state and callback registry.
