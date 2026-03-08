# PRD Guidelines

> 10-section template, quality criteria, and iteration protocol for PRD generation.

## PRD Section Order (10 Sections)

### Section 1: Executive Summary
- Clear problem statement (1-2 sentences)
- Proposed solution overview
- Target audience identification
- Key business value / ROI justification
- High-level timeline or phasing indication
- **Quality bar**: Concise, compelling, self-contained

### Section 2: Problem Statement
- Current state description
- Pain points with evidence (user research, data, support tickets)
- Impact quantification (lost revenue, wasted time, churn risk)
- Why now? — urgency or market timing
- **Quality bar**: Data-driven, specific

### Section 3: User Personas
- 2-4 distinct personas with names, roles, demographics
- Pain points specific to each persona
- Goals and desired outcomes
- Usage frequency and context
- **Quality bar**: Specific enough to drive design decisions

### Section 4: Functional Requirements
- Numbered (FR-001, FR-002, ...)
- SHALL/SHOULD/MAY priority levels
- Given/When/Then acceptance criteria
- Input validation rules and expected outputs
- API endpoints with method, path, request/response schemas
- **Quality bar**: Developer can implement without clarifying questions

### Section 5: Non-Functional Requirements
- Performance: latency targets (p50, p95, p99), throughput (RPS)
- Scalability: concurrent users, data volume
- Availability: uptime SLA, RTO, RPO
- Security: authentication, authorisation, encryption
- Compliance: GDPR, SOC 2, HIPAA if applicable
- Accessibility: WCAG level target
- **Quality bar**: Measurable, testable targets

### Section 6: Edge Cases
- Boundary conditions (empty inputs, max-length, etc.)
- Concurrent access scenarios
- Network failure handling
- Data inconsistency scenarios
- User behaviour edge cases
- **Quality bar**: Each specifies expected system behaviour

### Section 7: Error Handling
- Error taxonomy with HTTP status codes
- User-facing error messages (clear, actionable)
- System-level handling (retry, circuit breaker, dead-letter)
- Logging and alerting requirements
- Graceful degradation strategy
- **Quality bar**: No silent failures

### Section 8: Success Metrics
- Primary KPI with baseline and target
- Secondary metrics (adoption, NPS, support tickets)
- Instrumentation requirements
- Experiment design (A/B test plan)
- Leading vs. lagging indicators
- **Quality bar**: Specific, measurable, time-bound

### Section 9: Dependencies
- Technical (services, APIs, infrastructure)
- Team (design, backend, data, QA)
- Third-party (vendors, licenses, contracts)
- Risk assessment (likelihood × impact)
- Mitigation strategies
- **Quality bar**: Every dependency has an owner and mitigation

### Section 10: Assumptions
- Business assumptions
- Technical assumptions
- Operational assumptions
- Validation plan for critical assumptions
- **Quality bar**: Explicit and falsifiable

## Quality Criteria (6 Dimensions, scored 1-10)

1. **Completeness** — All required elements addressed?
2. **Specificity** — Concrete and testable?
3. **Consistency** — Aligned with other sections?
4. **Clarity** — Unambiguous and well-organised?
5. **Actionability** — Developer can act without questions?
6. **No Duplication** — No repeated content?

Approved ("SECTION_READY") when ALL scores ≥ 8.

## Iteration Protocol

Min 2, max 10 draft-critique cycles per section:
1. **DRAFT** — Write/revise addressing all critique points
2. **CRITIQUE** — Score on 6 dimensions (1-10 each)
3. **DECIDE** — All ≥ 8 → approve. Otherwise, specific feedback → iterate

## Writing Style

- Active voice, present tense
- Consistent terminology
- Numbered lists for requirements, bullets for descriptions
- Tables for structured data
- Include concrete examples
- Cross-reference other sections by name

## Anti-Patterns

- Vague requirements ("The system should be fast")
- Missing acceptance criteria
- Duplicating content across sections
- Requirements without priority levels
- Metrics without baselines or targets
- Edge cases without specified behaviour
- Dependencies without owners or mitigations
- Assumptions presented as facts
- Placeholder text or TODO markers

---

See also: [[PRD Flow]], [[Agent Roles]]
