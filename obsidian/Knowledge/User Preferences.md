---
tags:
  - knowledge
---

# User Preferences

> User profile and PRD generation preferences.

## Profile

- AI Engineer specialising in AI Agent systems
- Interested in AI Agents, LLM orchestration, multi-agent workflows
- Targets modern cloud-native architectures: containerised services, REST/gRPC APIs, event-driven patterns

## PRD Preferences

- Concise, actionable PRD documents with concrete acceptance criteria
- Iterative refinement: each section should improve through critique cycles
- All requirements must be testable and implementation-ready
- Developer clarity — no room for ambiguity
- Standard 10-section template
- Edge cases and error handling addressed explicitly, not deferred
- Given/When/Then format for acceptance criteria
- Non-functional requirements with quantitative targets (latency, throughput, uptime)

## Platform Preferences

- Slack as primary collaboration platform for PRD generation and review
- Slack interactive mode should mirror CLI experience with Block Kit buttons
- Comprehensive API documentation: OpenAPI/Swagger with typed schemas and examples
- Webhook callbacks with structured JSON payloads for async results
- Hand-maintained OpenAPI specs alongside auto-generated Swagger

## Automation Preferences

- Automated publishing: new PRD markdown files auto-published to Confluence
- Resilient delivery: cron scheduler resumes incomplete Confluence/Jira tasks
- Environment-variable-driven feature toggles for background automation
- All agent interactions logged to MongoDB for LLM fine-tuning
- Non-intrusive tracking: logging must never disrupt the user-facing flow

---

See also: [[PRD Guidelines]], [[Coding Standards]]
