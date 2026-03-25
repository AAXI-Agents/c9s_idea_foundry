---
run_id: ece3992be937
status: completed
created: 2026-03-23T13:54:27.201671+00:00
completed: 2026-03-23T15:48:07.236014+00:00
project: "[[business-compliance-tool]]"
tags: [idea, prd, completed]
---

# an accounting project and task management tool that integrates close checklis...

> Part of [[business-compliance-tool/business-compliance-tool|Business compliance tool]] project

## Original Idea

an accounting project and task management tool that integrates close checklists, reconciliation checklists, approvals, and routing, to support audit needs for sophisticated companies and simpler management for less sophisticated companies. It should provide a bird's eye view for management, clarify tasks for staff, highlight dependencies, offer automatic time tracking for process improvement, provide historical data for new hires, and support AI workers and managers. This tool aims to be the best for accounting/finance teams to manage work for one or many companies, including FP&A work, enabling better, smarter, and more productive work.

## Refined Idea

# Executive Summary

**Product Vision: The Hybrid Human-AI Financial Close & Orchestration Platform**

The proposed product is a specialized financial workflow and orchestration platform designed to manage the end-to-end month-end close, FP&A cycles, and audit preparation. Unlike generic project management tools (e.g., Asana, Monday.com) that lack financial compliance rigour, and legacy close-management incumbents (e.g., BlackLine, FloQast) that are overly rigid and entirely reliant on manual human input, this platform pioneers the "hybrid workforce." It treats AI agents and human accountants as collaborative peers within a unified, strictly governed workspace. By integrating native connections to both QuickBooks Online (QBO) for SMBs and NetSuite for mid-market/enterprise firms, the tool provides a scalable pathway from a company's first external audit through to strict SOX 404 public company compliance.

## The Core Problem

Accounting and finance teams are plagued by the "month-end close chaos." In less sophisticated companies running on QBO, the close is managed via brittle Excel checklists and scattered Slack messages, leading to missed dependencies and tribal knowledge silos that evaporate when a key employee leaves. As these companies mature and migrate to enterprise ERPs like NetSuite, they face a new nightmare: external audits. 

Auditors demand immutable evidence of preparer-reviewer segregation of duties, tie-outs, and variance explanations. Today, capturing this requires heavily manual oversight. Furthermore, highly paid CPAs spend 60% of their time on rote data-gathering and repetitive reconciliations rather than strategic FP&A analysis. Existing tools fail to bridge this gap; they either lack the IT General Controls (ITGC) required by Big 4 auditors, or they are too administratively heavy for a growing mid-market team.

## Competitive Differentiation & The "Hybrid Workforce"

The critical wedge for this product is its native integration of AI workers via the `crewAI` framework. In our system, an AI agent is treated as a distinct "user" with specific, heavily restricted role-based access. 

For example, when the system detects that the NetSuite AP ledger is locked for the period via the REST API, it automatically triggers a `crewAI` agent to perform the preliminary bank reconciliation. The AI fetches the data, performs the VLOOKUPs and matching logic, and attaches the working paper to the task. Crucially, to maintain audit defensibility, **AI agents cannot authorize approvals**. The platform enforces a strict routing rule where an AI's output must be reviewed and signed off by a human credentialed user. This eliminates the risk of AI hallucinations impacting financial statements while saving the human preparer hours of rote work.

## Key Capabilities & Technical Enablers

To translate this vision into a PRD, the product must be architected around several core pillars:

**1. Scalable Compliance ("Strict Audit Mode")**
Built on a Python 3.11/FastAPI backend and utilizing MongoDB Atlas, the platform captures a continuous, immutable, append-only audit log of every action. For simpler companies, the workflow is fluid. For mature companies, administrators can toggle "Strict Audit Mode," which enforces multi-tier approvals, locks workflow steps until predecessor tasks are completed, and requires re-authentication for critical sign-offs.

**2. Frictionless, Passive Time Tracking**
Accountants universally despise manual timesheets, yet controllers need to know where the close process is bottlenecking. Instead of invasive timers, the React + TypeScript frontend and backend engine passively track "time-in-status." By measuring the delta between when a task enters the "Ready for Review" state and when it is "Approved," management gains a bird's-eye view of process bottlenecks—allowing them to reallocate headcount or assign more AI agents to specific workflow streams.

**3. Deep ERP Syncing**
The platform is not a disconnected checklist; it is state-aware. By polling the QBO and NetSuite APIs, tasks dynamically update. A human doesn't need to manually check off "Close AR module"—the system detects the closed state in NetSuite and automatically advances the downstream dependency (e.g., "Run Bad Debt Reserve Calculation"), alerting the responsible staff member or AI worker.

**4. Contextual Continuity for FP&A and New Hires**
Historically, variance explanations live in disparate email threads. Using Google Vertex AI, the platform semantically indexes all historical task comments, variance notes, and reconciliation attachments. When a new hire is assigned a complex deferred revenue reconciliation, the platform automatically surfaces a contextual briefing generated by the LLM, detailing exactly how the task was completed in the prior three periods and highlighting historical pitfalls.

## Success Criteria

For this product to succeed, it must demonstrate a demonstrable reduction in "Days to Close" (target: 30%+ reduction) for its users. Furthermore, success will be measured by a zero-deficiency reliance on the system's generated audit trails by external auditors, and a high adoption rate of the `crewAI` automated task workers for baseline reconciliations. This platform will not just manage the work; it will execute the baseline, orchestrate the flow, and secure the audit, fundamentally elevating the Office of the CFO.

## Executive Summary

# Executive Summary

**Product Vision**
The Hybrid Human-AI Financial Close & Orchestration Platform is a specialized, compliance-driven workflow ecosystem designed to modernize month-end close, FP&A cycles, and external audit preparation. Moving beyond the constraints of generic project management tools (e.g., Asana) and the manual rigidity of legacy close-management incumbents (e.g., BlackLine, FloQast), this platform pioneers the "hybrid workforce" paradigm. By natively integrating AI agents as restricted, collaborative peers alongside human CPAs within a strictly governed environment, the platform provides a seamlessly scalable pathway from an organization's first external audit up to rigorous SOX 404 public company compliance. 

**The Core Problem**
Accounting and finance teams at scaling mid-market enterprises face chronic "month-end close chaos." In earlier stages running on QuickBooks Online (QBO), the close is typically governed by brittle, disconnected Excel checklists and fragmented tribal knowledge. As companies scale, migrate to enterprise ERPs like NetSuite, and undergo rigorous external audits, they encounter exponential compliance burdens. External auditors mandate immutable evidence of preparer-reviewer segregation of duties, comprehensive tie-outs, and thorough variance explanations. To satisfy these requirements using existing technology, highly paid accounting professionals are forced to spend upwards of 60% of their time executing rote data-gathering and repetitive reconciliations rather than strategic FP&A analysis. Existing software either lacks the stringent IT General Controls (ITGC) required by Big 4 auditors or demands suffocating administrative overhead.

**Target Audience & Key Stakeholders**
*   **Controllers & Accounting Managers:** Seeking to eliminate manual bottlenecks, enforce standardized processes, and reduce key-person risk during the month-end close.
*   **CFOs & VP of Finance:** Focused on accelerating the "Days to Close" metric to unlock faster strategic decision-making and reallocating CPA headcount to high-value FP&A tasks.
*   **External Auditors (Big 4 / Regional Firms):** Requiring immutable, structurally sound audit trails, clear ITGC enforcement, and mathematically proven segregation of duties.
*   **System Administrators / IT Teams:** Tasked with provisioning secure, state-aware financial tech stacks that integrate natively via robust APIs without introducing data-integrity risks.

**Proposed Solution & Key Differentiators**
Architected on a high-performance stack (Python 3.11/FastAPI backend, React + TypeScript frontend, and MongoDB Atlas persistence), the platform operates on four primary pillars:

1.  **The Hybrid Workforce via crewAI:** AI agents execute tasks as distinct, heavily restricted "users." For example, upon detecting a locked AP ledger, a crewAI agent autonomously performs preliminary bank reconciliations (matching, VLOOKUPs) and attaches the working paper. To enforce audit defensibility, **AI agents cannot authorize approvals**; their outputs must route to a credentialed human reviewer, completely mitigating hallucination risks while eliminating rote preparation work.
2.  **Scalable Compliance & "Strict Audit Mode":** Capturing a continuous, append-only audit log of every system action. Administrators can enable "Strict Audit Mode" for mature organizations to enforce multi-tier approvals, mandatory predecessor task locking, and re-authentication for critical sign-offs.
3.  **Deep, State-Aware ERP Syncing:** Unlike static checklists, the platform maintains bidirectional state awareness via QBO and NetSuite REST APIs. Systemic ledger changes (e.g., closing an AR module) are automatically detected, instantly advancing downstream dependencies (e.g., Bad Debt Reserve Calculation) without manual human input.
4.  **Contextual Continuity via Vertex AI:** Leveraging Google Vertex AI, the platform semantically indexes all historical task comments, attachments, and variance explanations. It autonomously generates contextual briefings for new hires or staff taking over complex reconciliations, surfacing exactly how tasks were resolved in prior periods and highlighting historical pitfalls.
5.  **Frictionless Passive Time Tracking:** Instead of invasive manual timesheets, the platform calculates "time-in-status" deltas (e.g., from "Ready for Review" to "Approved"), giving management actionable analytics to identify process bottlenecks and optimize hybrid workforce allocation.

**Business Impact & Success Criteria**
The success of this platform is anchored in verifiable operational efficiency and strict compliance readiness. The SMART success criteria are defined as follows:

*   **Speed to Close:** Achieve a demonstrable **30%+ reduction in "Days to Close"** for deployed organizations within the first two full financial quarters of adoption.
*   **Audit Defensibility:** Attain a **zero-deficiency reliance metric** by external auditors on the platform’s generated audit trails, ITGC enforcements, and segregation-of-duties logs during the first annual audit cycle.
*   **AI Adoption & Efficiency:** Achieve >60% adoption of crewAI-automated baseline reconciliations across all eligible workflow templates, validating the trust and efficacy of the hybrid workforce model and measurably shifting CPA hours from data gathering to strategic analysis.

## Executive Product Summary

# Executive Product Summary: The Continuous Close Platform

## The Real Problem 
When finance leaders ask for "better month-end close software," we shouldn't just give them a smarter checklist. We have to ask: *Why is the month-end close still a chaotic, 15-day batch process in the first place?*

The fundamental problem isn't that accountants are disorganized; it's that accounting is still operating on a legacy "batch processing" paradigm. For 29 days, discrepancies pile up, missing invoices accumulate, and tribal knowledge fades. Then, on day 30, highly paid CPAs spend 60% of their time playing forensic archaeologist—hunting down VLOOKUP errors and pinging Slack channels just to figure out what happened three weeks ago. Existing tools like BlackLine or Asana merely digitize this chaos. 

**We are not building a better checklist. We are eliminating the batch process.** 

We are building the "Continuous Close"—a system where the books are effectively reconciled every single day. By deploying restricted AI agents as persistent background workers, we shift the accountant's role from *Data Preparer* to *Exception Handler.* When month-end arrives, it shouldn’t be a scramble; it should be a calm, two-hour formal review of the final 2% of anomalies.

## The 10-Star Vision: The "Hybrid Workforce" & The Continuous Close
The 10-star version of this product is a self-driving ledger with rigorous, Big-4 grade guardrails. It natively pairs Python/FastAPI backend logic, crewAI orchestration, and Vertex AI semantic reasoning to create a "hybrid workforce." 

In this ecosystem, AI agents and human CPAs collaborate in a mathematically proven, strictly governed workspace. 

*   **The AI as Junior Staff:** crewAI agents continuously poll QBO and NetSuite REST APIs. They don't wait for month-end. They ingest data, perform baseline bank reconciliations, execute the matching logic, and draft the working papers in real-time. 
*   **The Human as Editor:** To eliminate hallucination risk and ensure audit defensibility, **AI cannot authorize.** Zero silent failures. The AI’s output is staged as a "Ready for Review" draft. The human CPA simply reviews the AI's math, investigates the flagged exceptions, and signs off.

This delivers 10x the value because we aren't just giving them a dashboard to see their delayed work; we are actually *doing the baseline work for them*, governed by strict IT General Controls (ITGC) and immutable MongoDB Atlas audit trails.

## The Ideal User Experience
Imagine Sarah, a Corporate Controller at a $50M mid-market company. It is Day 1 of the new month—historically the most stressful day of her calendar.

She logs into the platform (React + TypeScript frontend). Instead of a red dashboard of 400 overdue tasks, she sees a clean, calm interface: 
*"Good morning. The Continuous Close engine reconciled 14,203 transactions overnight. Everything ties out. There are exactly 6 exceptions that require your attention."*

She clicks into the first exception: a complex deferred revenue variance. She doesn’t have to dig through old emails to understand it. Vertex AI has already generated a contextual briefing: *"In the past 3 periods, this variance was caused by early renewals from the Enterprise cohort. Here is the historical working paper from last month for reference."* She reviews the AI's suggested adjustment, clicks "Approve," and the system automatically logs the segregation-of-duties evidence to the immutable audit ledger. She goes to get coffee. The close is practically done.

## Delight Opportunities ("Bonus Chunks")
To make users say *"oh nice, they thought of that,"* we will include these low-effort, high-impact features (<30 mins effort each):

1.  **"Explain to Auditor" Button:** A single-click feature on any reconciliation that instantly packages the transaction data, the AI's underlying math, the human approver's identity, and the Vertex AI context summary into a locked, Big-4 formatted PDF memo. 
2.  **Day -3 Proactive Nudges:** Before month-end even hits, the system checks for missing high-value receipts/invoices. It auto-drafts Slack messages or emails to the responsible employees (e.g., *"Hi Dave, it looks like we're missing the invoice for the $5k AWS charge on the 14th"*), staging them for the Controller to send with one click.
3.  **The "Morning Briefing":** Instead of forcing users to log in to see what happened, the platform pushes a 3-bullet daily summary to the team's Slack/Teams channel: *"Overnight, 4 ledgers locked, AP was reconciled, and 2 Bad Debt tasks were advanced to Review."*
4.  **Passive Process Traffic Maps:** Instead of hated manual timesheets, the system passively measures "time-in-status" (e.g., how long a task sat in 'Ready for Review') and generates a visual heatmap showing exactly where the close is bottlenecking. 

## Scope Mapping: The 12-Month Trajectory

*   **Current State (Status Quo):** Companies run on brittle Excel checklists, manual VLOOKUPs, disconnected Slack threads, and "month-end chaos." Audits are a nightmare of missing evidence.
*   **This Plan (Months 1-6): The Exception-Based Close.** We deliver deep bi-directional syncing with QBO/NetSuite. crewAI agents perform baseline rote tasks and stage them for human review. Strict Audit Mode is enforced via immutable MongoDB logs. The close duration drops by 30%.
*   **12-Month Ideal: Predictive Accounting.** The platform shifts from reactive orchestration to predictive anomaly detection. Using historical data and Vertex AI, the system anticipates variances *before* they occur, automatically adjusting intra-month accruals and intelligently redistributing workload among human staff and AI agents based on real-time bottlenecks.

## Business Impact & Competitive Positioning
This is not just operational software; it is a margin-expansion tool for the Office of the CFO. 

*   **The Market Wedge:** Legacy incumbents like BlackLine are incredibly expensive, require months of implementation, and rely 100% on human input. Generic tools like Monday.com fail instantly under the scrutiny of a SOX 404 audit. We own the "Hybrid AI" whitespace for scaling mid-market companies.
*   **Metric 1: Speed to Value:** Achieve a demonstrable **30%+ reduction in "Days to Close"** within the first two financial quarters.
*   **Metric 2: Audit Reliance:** Achieve a **zero-deficiency metric** from external auditors regarding our platform's ITGC, segregation-of-duties logs, and system-generated trails.
*   **Metric 3: CPA Repurposing:** Reach >60% crewAI adoption for baseline reconciliations, definitively shifting highly-paid CPA hours away from data-gathering toward strategic FP&A and growth analysis. 

We are not just selling faster close times. We are selling audit peace of mind, team retention, and the elevation of the accounting department from back-office historians to front-line strategic advisors.

## Engineering Plan

# Engineering Plan: The Continuous Close Platform

## 1. Architecture Overview

To satisfy the stringent SOX 404 compliance constraints, high-volume webhook ingestion, and deterministic AI augmentation, the system is architected around an event-driven, decoupled microservices model. The synchronous serving layer is strictly isolated from the asynchronous AI orchestration layer to ensure UI responsiveness and predictable scaling.

### 1.1 System Component Diagram

```ascii
                                   +-------------------+
                                   |  External Client  | (React + TypeScript SPA)
                                   +--------+----------+
                                            | HTTPS / WSS
                                            v
+-----------------------------------------------------------------------------------+
|                              Cloudflare / API Gateway                             |
+-----------------------------------------------------------------------------------+
             |                                                  |
             | (REST APIs, JWT, MFA)                            | (Webhooks, HMAC)
             v                                                  v
+-----------------------------+                  +----------------------------------+
|   Core API Service (Sync)   |                  |   Ingestion Service (Async)      |
|   (Python 3.11 / FastAPI)   |<-----------------|   (Python 3.11 / FastAPI)        |
| - AuthZ & JWT Middleware    |   Internal RPC   | - Webhook Signature Validation   |
| - DAG Evaluation Engine     |                  | - High-throughput Fast-Ack       |
| - Audit Logging Interceptor |                  +----------------+-----------------+
+-------------+---------------+                                   |
              |                                                   |
              | Publish Task / Sync Events                        | Enqueue Sync Event
              v                                                   v
+-----------------------------------------------------------------------------------+
|                             Message Broker (RabbitMQ)                             |
+-----------------------------------------------------------------------------------+
              |                                                   |
              v                                                   v
+-----------------------------+                  +----------------------------------+
| AI Worker Pool (crewAI)     |                  |  Background Workers (Celery)     |
| - Account Reconciliations   |                  | - DAG Recalculation              |
| - ERP Sync Anomaly Checking |                  | - Time-in-Status Aggregation     |
| - Context Generation (RAG)  |                  | - Email/Slack Notifications      |
+------+---------------+------+                  +----------------+-----------------+
       |               |                                          |
       | API Calls     | API Calls                                |
       v               v                                          v
+--------------+ +-------------+                 +----------------------------------+
|   Vertex AI  | | QBO/NetSuite|                 |    Primary Datastore (MongoDB)   |
| (LLM / RAG)  | |   (ERPs)    |                 |  - AuditLogEntry (Append-Only)   |
+--------------+ +-------------+                 |  - ReconciliationTask            |
                                                 |  - TaskNode (DAG Graph)          |
                                                 +----------------------------------+
```

### 1.2 Technology Stack Decisions
*   **Backend Serving**: `FastAPI` (Python 3.11). *Rationale*: Native async I/O handles concurrent AI polling efficiently. Built-in Pydantic integration enforces strict payload schemas (critical for audit integrity).
*   **Persistence**: `MongoDB Atlas`. *Rationale*: Flexible document schemas for highly variable ERP webhook payloads and embedded metadata. Compound and TTL indexes optimize DAG traversals and passive time-tracking queries.
*   **Message Broker**: `RabbitMQ`. *Rationale*: Guaranteed message delivery and routing keys allow us to strictly separate high-priority user actions from low-priority passive AI tasks.
*   **AI Framework**: `crewAI` + `Vertex AI`. *Rationale*: crewAI enables deterministic, agentic workflows with explicit tool-use. Vertex AI provides enterprise-grade data privacy (no training on user data) and integrated vector search for RAG.
*   **Frontend**: `React + TypeScript`. *Rationale*: Strict typing ensures UI components correctly handle complex API state transitions.

### 1.3 Data Flow: AI Reconciliation Pipeline

```ascii
[Happy Path]
(Human) -> Assigns Task -> (FastAPI) -> Updates State [Pending] -> (RabbitMQ) -> (crewAI Worker)
(crewAI) -> Fetches ERP Data -> Calculates Match -> Generates CSV -> Uploads to Cloud Storage
(crewAI) -> Calls POST /attachments (confidence=0.95) -> (FastAPI) -> Updates State [ReadyForReview] -> Notifies Human
(Human) -> Reviews UI -> Clicks Approve + MFA -> (FastAPI) -> Writes Audit Log -> Updates State [Approved]

[Error Path: AI Low Confidence]
(crewAI) -> Calls POST /attachments (confidence=0.80) -> (FastAPI) intercepts <0.85 threshold
(FastAPI) -> Bypasses [ReadyForReview] -> Transitions to [ReworkRequested] -> Alerts Human of AI failure

[Error Path: AI Authorization Attempt - SEC/SOX Violation]
(crewAI Worker) -> Forges POST /approve with AI JWT -> (FastAPI AuthZ Middleware) 
-> Reads scope:`ai_preparer` -> Rejects 403 Forbidden -> Writes FAILED_APPROVAL to AuditLogEntry
```

---

## 2. Component Breakdown

### 2.1 State Machines

**ReconciliationTask State Machine**
```ascii
      +---------+      Manual Config       +---------+
      |  Draft  |------------------------->| Pending |
      +---------+                          +----+----+
                                                |
                                                | Agent Claims Task
                                                v
+-----------------+   Rework (Comment)     +-----------------+
| ReworkRequested |<-----------------------|  AI_Processing  |
+--------+--------+                        +----+----+-------+
         |                                      |    |
         | Agent Re-claims                      |    | Confidence < 0.85
         +--------------------------------------+    | (Auto-Rework)
                                                     v
                                       +------------------+
                                       |  ReadyForReview  |
                                       +---------+--------+
                                                 |
                                                 | Human Approve + MFA
                                                 v
                                           +----------+
                                           | Approved |
                                           +----------+
```

**TaskNode (DAG) State Machine**
```ascii
  +---------+   All Predecessors Closed    +-------+
  | Blocked |----------------------------->| Ready |
  +----+----+                              +---+---+
       ^                                       |
       |                                       | Webhook Received
       | AI Detects Anomalies                  v
       +-----------------------------+------------------+
                                     |  SystemVerified  |
                                     +---------+--------+
                                               |
                                               | AI Passes Verification
                                               v
                                          +--------+
                                          | Closed |
                                          +--------+
```

### 2.2 API Contract Sketches

**1. POST /api/v1/tasks/{taskId}/approve**
*   **Purpose**: Final human sign-off enforcing segregation of duties.
*   **AuthZ**: Requires `scope: human_reviewer`. Blocks `scope: ai_preparer`.
*   **Payload**:
    ```json
    {
      "signatureText": "Approved by J. Doe",
      "mfaToken": "123456" // Validated via regex ^\d{6}$
    }
    ```
*   **Responses**: `200 OK`, `403 Forbidden`, `409 Conflict` (Task not in `ReadyForReview`), `422 Unprocessable Entity`.

**2. POST /api/v1/webhooks/netsuite**
*   **Purpose**: Receive ERP sync events. High throughput, low latency.
*   **AuthZ**: HMAC-SHA256 signature in `X-NetSuite-Signature` header.
*   **Payload**: Arbitrary JSON strictly bounded by 1MB limit.
*   **Responses**: `202 Accepted` (Enqueued to RabbitMQ), `401 Unauthorized`, `429 Too Many Requests`.

---

## 3. Implementation Phases

### Phase 1: Foundation & Data Models (Epic)
**Complexity: M**
*   **Story 1.1**: Bootstrap FastAPI application, MongoDB Beanie/Motor ODM integration, and basic error handling middleware.
*   **Story 1.2**: Implement JWT Authentication and strictly typed role scopes (`SystemAdmin`, `HumanReviewer`, `AIPreparer`).
*   **Story 1.3**: Design and implement `Company`, `User`, and `ClosePeriod` foundational schemas.
*   **Story 1.4**: Establish strictly immutable `AuditLogEntry` collection (block application-level DELETE/UPDATE operations).

### Phase 2: Core Task & DAG Engine (Epic)
**Complexity: L**
*   **Story 2.1**: Implement `ReconciliationTask` CRUD APIs and Pydantic validation for the state machine transitions.
*   **Story 2.2**: Implement `TaskNode` DAG schema and cycle-detection logic upon creation (DFS algorithm).
*   **Story 2.3**: Build the Webhook Ingestion endpoint (HMAC validation, 202 Fast-Ack, RabbitMQ enqueueing).
*   **Story 2.4**: Create Celery worker to consume webhooks, traverse the DAG, and advance `Blocked` -> `Ready` states.

### Phase 3: Hybrid AI Workforce (Epic)
**Complexity: XL**
*   **Story 3.1**: Provision crewAI framework inside dedicated Celery worker queues. Fetch Vault/Secret Manager credentials dynamically.
*   **Story 3.2**: Implement the "Bank Reconciliation Agent" (Fetches NetSuite data, runs deterministic matching logic, generates CSV).
*   **Story 3.3**: Implement the POST `/attachments` endpoint with the `<0.85` confidence score interception routing to `ReworkRequested`.
*   **Story 3.4**: Integrate Vertex AI for `ContextualBriefing`. Implement `Generating` -> `Available` state machine and deterministic fallback logic for timeouts.

### Phase 4: Strict Audit & Observability (Epic)
**Complexity: M**
*   **Story 4.1**: Implement the "Strict Audit Mode" tenant toggle (MFA required, secondary Admin approval).
*   **Story 4.2**: Write FastAPI middleware to calculate and append `SHA256(previousHash + payload)` to the `AuditLogEntry` on every mutating request.
*   **Story 4.3**: Implement `TaskStatusTimeLog` passive event listeners. Update exit timestamps asynchronously when task status changes.
*   **Story 4.4**: Expose GET `/api/v1/analytics/bottlenecks` leveraging simple aggregations (Fall back to basic stats if AI optimizer is down).

---

## 4. Data Model (MongoDB Atlas)

### 4.1 Schema Definitions

**`audit_logs` Collection (Strictly Append-Only)**
*   `_id`: ObjectId
*   `companyId`: ObjectId (Ref: `companies`)
*   `actorId`: String (Human or AI token subject)
*   `actorType`: Enum (`Human`, `System`, `AIAgent`)
*   `action`: String
*   `resourceId`: ObjectId
*   `newState`: Object (dict)
*   `cryptographicHash`: String (Unique)
*   `timestamp`: Date
*   **Indexes**: `{ companyId: 1, timestamp: -1 }`, Unique on `{ cryptographicHash: 1 }`.
*   **Constraint**: Application-layer logic throws hard exceptions on any `collection.update_one` or `delete_one`.

**`reconciliation_tasks` Collection**
*   `_id`: ObjectId
*   `companyId`: ObjectId
*   `periodId`: ObjectId
*   `title`: String (Max 150 chars)
*   `status`: Enum (`Draft`, `Pending`, `AI_Processing`, `ReadyForReview`, `ReworkRequested`, `Approved`)
*   `assignedHumanId`: ObjectId (Nullable)
*   `assignedAgentId`: String (Nullable)
*   `erpSource`: Enum (`QBO`, `NetSuite`)
*   `metadata`: Object (dict)
*   **Indexes**: `{ companyId: 1, periodId: 1, status: 1 }`.

**`task_nodes` Collection (DAG)**
*   `_id`: ObjectId
*   `periodId`: ObjectId
*   `erpModuleId`: String
*   `dependencies`: Array[ObjectId]
*   `graphStatus`: Enum (`Blocked`, `Ready`, `SystemVerified`, `Closed`)
*   **Indexes**: `{ periodId: 1 }`, Multikey index on `{ dependencies: 1 }`.

---

## 5. Error Handling & Failure Modes

| Component / Dependency | Failure Mode | Classification | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **QBO/NetSuite APIs** | Rate Limits (HTTP 429) | Major | crewAI workers implement Exponential Backoff (max 3 retries). Fails state back to `Pending` alerting Controller if persistent. |
| **Vertex AI LLM** | Timeout / Service Unavailable | Minor | Hard 15s timeout on `ContextualBriefing`. Graceful UI degradation via hardcoded deterministic string. Never blocks the close. |
| **RabbitMQ** | Message Broker Down | Critical | API shifts to 503 for Async requests. Synchronous CRUD remains available. Dead-Letter Queues (DLQ) configured for poison messages. |
| **crewAI Agent** | Hallucination / Bad Math | Major | **Architecture limit:** AI acts as preparer only. Low confidence (<0.85) auto-routes to Rework. Human must authorize final output. |
| **MongoDB** | Replica Set Election | Major | PyMongo driver configured with `retryWrites=True`. API requests will automatically stall/retry during the ~2s failover window. |
| **ERP Webhook Flood** | > 100 req/sec (DDoS / Loop) | Major | API Gateway / Cloudflare strict rate limiting. FastAPI returns `429`. |

---

## 6. Test Strategy

### 6.1 Test Pyramid
*   **Unit Tests (Pytest)**:
    *   DAG Traversal/Cycle Detection (Crucial: verify infinite loops are caught).
    *   State Machine guards (Assert invalid transitions throw `ValueError`).
    *   Cryptographic Hash generation (Assert exact SHA-256 replication).
*   **Integration Tests (Testcontainers + MongoDB)**:
    *   Webhook ingestion -> RabbitMQ enqueue -> Worker consumption.
    *   Audit Log immutability enforcement.
*   **E2E Tests (Playwright)**:
    *   Critical Path: Controller configures task -> assigns AI -> AI responds via mock -> Controller approves with MFA.

### 6.2 Edge Case Test Matrix
*   Approval attempted with `mfaToken` as a string of letters instead of `^\d{6}$`.
*   Dependency graph created where `Task A -> Task B -> Task A`.
*   Webhook arrives for an ERP module not present in the current `ClosePeriod`.
*   crewAI attempts to POST a workpaper but passes `confidenceScore: null`.

---

## 7. Security & Trust Boundaries

### 7.1 Authorization Boundaries
*   **Strict Segregation**: The system enforces a hard boundary between `Actor=AI` and `Actor=Human`. Fast API Dependencies (`Depends(get_current_user)`) evaluate the JWT `sub` and `role`. Any endpoint modifying state to `Approved` enforces `role == HumanReviewer` AND validates the provided MFA token against the user's secret.
*   **Tenant Isolation**: All API endpoints enforce a `companyId` header/token match. Data queries strictly include `companyId` in the root filter payload.

### 7.2 Input Validation
*   All inbound data passes through strict Pydantic models.
*   ERP Webhooks use `Request.body()` raw bytes to calculate HMAC-SHA256 against a Vault-stored tenant secret before JSON parsing, preventing deserialization attacks.

### 7.3 Data Classification
*   **High Risk / PII**: Financial ledgers, employee MFA tokens, Audit Cryptographic Hashes. Stored encrypted at rest (AES-256 via MongoDB Atlas).
*   **Transit**: TLS 1.3 enforced at Cloudflare edge.

---

## 8. Deployment & Rollout

### 8.1 Deployment Sequence
1.  **DB Migrations**: Execute index creation and schema validations via automated CI scripts.
2.  **Workers**: Deploy Celery/crewAI background workers.
3.  **API Services**: Rolling update (Blue/Green) of FastAPI pods.
4.  **Frontend**: Push static assets to CDN.

### 8.2 Feature Flags (LaunchDarkly / Config)
*   `ENABLE_STRICT_AUDIT_MODE` (Default: False)
*   `ENABLE_CREW_AI_AGENTS` (Default: True)
*   `ENABLE_VERTEX_RAG` (Default: False - roll out gradually to monitor LLM costs).

### 8.3 Rollback Plan (Step-by-Step)
1.  If API error rate > 1% over 2 minutes, CI/CD pipeline auto-aborts.
2.  Revert FastAPI deployment to previous git tag.
3.  Leave DB indexes intact (backward compatible).
4.  Drain RabbitMQ queues if payload schema changed incompatibly.

---

## 9. Observability

### 9.1 Logging
*   Structured JSON logging (`structlog`) pushed to Datadog/ELK.
*   **Required Context**: Every log entry must include `trace_id`, `company_id`, `actor_id`, and `actor_type`.

### 9.2 Metrics & Alerting
*   `dag.recalculation_duration_ms` (Alert if > 5000ms).
*   `ai_agent.confidence_score` (Histogram: track if agents are consistently under-confident).
*   `api.webhook_ingest.429_count` (Alert if a specific tenant is flooding the system).
*   `audit_log.mfa_failures` (Security Alert if > 5 per minute per user).

### 9.3 Debugging Guide for Common Scenarios
*   **Symptom**: "Task is stuck in `AI_Processing`."
    *   **Action**: Query Datadog logs by `taskId`. Check if the crewAI worker crashed due to NetSuite API timeout. Check RabbitMQ DLQ. If dead-lettered, manually reset task to `Pending` via Admin UI.
*   **Symptom**: "Downstream tasks not unblocking after AP closed."
    *   **Action**: Verify the NetSuite webhook was received (`202 Accepted`). Check `TaskNode` status. If `SystemVerified` but not `Closed`, the AI Auditor flagged an anomaly. Review the `AuditLogEntry` for unposted transaction warnings.

## Problem Statement

The month-end financial close is fundamentally broken, operating on a legacy "batch processing" paradigm that forces finance teams into a reactive, chaotic scramble at the end of every 30-day cycle. Currently, scaling mid-market companies ($10M–$50M ARR) transitioning from QuickBooks Online (QBO) to enterprise ERPs like NetSuite manage their financial orchestration through brittle Excel checklists, disjointed Slack threads, and unwritten tribal knowledge. 

Existing close-management incumbents (e.g., BlackLine, FloQast) and generic project management tools (e.g., Asana, Monday.com) fail to solve the root cause of this chaos. They merely digitize a manual checklist, offering visibility into the delay without actually executing the underlying data work or inherently enforcing the strict compliance required by external auditors.

**Core Pain Points**

*   **The Batch Processing Bottleneck:** For 29 days, transaction discrepancies, unmapped ledger codes, and missing vendor invoices silently accumulate. On day 30, finance teams face a massive, immediate backlog, artificially extending the "Days to Close" metric to 15+ days.
*   **Misallocation of High-Cost Human Capital:** Highly compensated Certified Public Accountants (CPAs) spend up to 60% of their operational bandwidth acting as "forensic archaeologists"—hunting down VLOOKUP errors, manually matching bank feeds, and chasing transaction context across disconnected communication channels. This starves the organization of forward-looking Financial Planning & Analysis (FP&A).
*   **Audit Defensibility and ITGC Failures:** External auditors—particularly during first-year Big 4 audits or SOX 404 compliance checks—mandate immutable, mathematically proven evidence of preparer-reviewer segregation of duties and strict IT General Controls (ITGC). Generic task trackers fail these compliance checks instantly. Legacy financial tools demand suffocating administrative overhead to capture this evidence and rely entirely on human data entry, which is highly susceptible to omission and silent failures.
*   **Key-Person Dependency & Context Erasure:** Variance explanations and reconciliation methodologies typically reside in individual email inboxes or undocumented memory. When a key controller or senior accountant departs, the historical context of complex deferred revenue schedules or custom accruals vanishes, severely disrupting subsequent audit and close cycles.

**Quantifiable Business Impact**

*   **Delayed Strategic Velocity:** A 15-day close cycle dictates that executive leadership makes critical resource allocation and growth decisions based on financial data that is fundamentally two to four weeks out of date.
*   **Margin Erosion via Inefficiency:** Utilizing CPAs (averaging $120k+ annual compensation) to manually execute baseline bank reconciliations and data-gathering represents a massive misallocation of operational expenditure. 
*   **High-Risk Audit Exposure:** The inability to systematically prove segregation of duties, or to produce granular, system-generated tie-outs, directly leads to audit deficiencies, significantly increased external auditor billable hours, and delayed M&A or public-market readiness.

**Why Now?**

As mid-market organizations transition from lax SMB accounting standards to strict enterprise compliance environments, the sheer volume of localized and transactional data exponentially outpaces manual human processing capacity. Concurrently, the permanent shift to distributed, remote finance teams has eliminated the informal "shoulder-tapping" method of resolving ledger discrepancies. This makes the implementation of a continuous, mathematically governed, and structurally secure financial orchestration process an immediate operational necessity, not a future luxury.

## User Personas

### 1. The Human Reviewer (Corporate Controller / Accounting Manager)
**Profile:** A highly experienced, credentialed CPA (e.g., Sarah) operating at a mid-market company ($10M–$50M ARR). She manages a small team of accountants and is ultimately responsible for signing off on the financial statements before they go to the CFO or external auditors. 
**Usage Context:** Daily power user, peaking significantly around days 1-5 of the month-end close cycle.
**Goals & Desired Outcomes:**
*   Achieve a mathematically sound, 100% tied-out month-end close in under 5 days.
*   Eliminate time spent on rote data-gathering (e.g., matching bank feeds) to focus on strategic FP&A and variance analysis.
*   Ensure every reconciliation is "audit-ready" with clear, system-generated segregation-of-duties evidence.
**Pain Points:**
*   Currently spends the majority of the close cycle "playing forensic archaeologist"—hunting down VLOOKUP errors and digging through Slack/email to understand why a variance occurred.
*   Cannot trust generic task trackers because they lack the ITGC guardrails required by her auditors.
**System Interaction & Scope:**
*   **Role Scope:** `scope: human_reviewer`
*   **Capabilities:** Interacts via the React + TypeScript frontend. Can assign tasks, configure DAG dependencies, review AI-generated workpapers, request rework, and critically, execute the POST `/approve` endpoint using MFA to transition tasks to the `Approved` state.

### 2. The AI Preparer (crewAI Agent)
**Profile:** A deterministically constrained, background AI worker tasked with executing repetitive financial reconciliations and data ingestion. It acts as the "Junior Staff" member of the accounting team.
**Usage Context:** Persistent background worker, constantly polling webhooks and executing API calls 24/7 as ERP states change.
**Goals & Desired Outcomes:**
*   Perform baseline reconciliations (e.g., bank feed matching against NetSuite AP ledgers) with high mathematical accuracy.
*   Draft working papers and surface exceptions for human review.
*   Never violate segregation of duties or ITGC protocols.
**Pain Points (System Limitations):**
*   Lacks the contextual judgment of a human CPA.
*   Vulnerable to hallucinations if not strictly bounded by deterministic logic and confidence thresholds.
**System Interaction & Scope:**
*   **Role Scope:** `scope: ai_preparer`
*   **Capabilities:** Operates asynchronously via RabbitMQ and Celery workers. Can transition tasks from `Pending` to `AI_Processing` and POST generated artifacts to `/attachments`.
*   **Hard Boundaries:** Cannot execute approvals. If the agent attempts to hit the `/approve` endpoint, the FastAPI AuthZ middleware instantly rejects it (403 Forbidden) and logs a critical security violation. Outputs scoring < 0.85 confidence bypass the `ReadyForReview` state and force a `ReworkRequested` loop.

### 3. The System Administrator (IT / Finance Systems Manager)
**Profile:** A technical operations manager responsible for provisioning, securing, and maintaining the financial technology stack.
**Usage Context:** Occasional user; heavy usage during initial ERP integration (QBO/NetSuite), followed by periodic monitoring of system health and audit logs.
**Goals & Desired Outcomes:**
*   Ensure seamless, bi-directional state syncing between the Continuous Close Platform and the core ERP (NetSuite/QBO).
*   Enforce enterprise-grade security, including SSO, MFA, and tenant isolation.
*   Provide external auditors with pristine, immutable ITGC logs upon request.
**Pain Points:**
*   Legacy close tools require massive, brittle implementation cycles.
*   Manual provisioning of users and tracking of permissions across disparate tools creates security vulnerabilities.
**System Interaction & Scope:**
*   **Role Scope:** `scope: system_admin`
*   **Capabilities:** Manages HMAC-SHA256 webhook configurations. Can toggle "Strict Audit Mode" (enforcing mandatory MFA and locked DAG dependencies). Has read-only access to the `AuditLogEntry` collection in MongoDB for generating compliance reports.

### 4. The External Auditor (Big 4 / Regional CPA Firm Partner)
**Profile:** An independent compliance professional tasked with verifying the accuracy of the company's financial statements and the efficacy of its internal controls (e.g., SOX 404).
**Usage Context:** Infrequent, but high-stakes usage. Logs in strictly during quarterly reviews and annual audit cycles.
**Goals & Desired Outcomes:**
*   Verify that no single user (human or AI) can both prepare and approve a journal entry (Segregation of Duties).
*   Obtain undeniable proof that the system's audit trails are immutable and mathematically sound.
*   Trace the lifecycle of a financial exception from detection to final human sign-off without needing to interview the staff.
**Pain Points:**
*   Wastes highly billable hours manually tracing emails to prove who approved a specific reconciliation.
*   Deeply skeptical of AI tools due to "black box" hallucination risks.
**System Interaction & Scope:**
*   **Role Scope:** `scope: read_only_auditor`
*   **Capabilities:** Interacts via a locked-down frontend portal. Cannot modify task states. Relies on the "Explain to Auditor" feature (Vertex AI generated, immutable PDFs) and directly reviews the cryptographically hashed `AuditLogEntry` trails to verify compliance.

## Functional Requirements

### Key Terminology
*   **ReconciliationTask:** A discrete unit of financial work (e.g., matching a bank feed to a ledger) that can be assigned to either a human or an AI agent. It holds a specific state (e.g., `Draft`, `Pending`, `AI_Processing`, `ReadyForReview`, `Approved`).
*   **ClosePeriod:** The overarching time-bound container (usually a month) that holds all associated `ReconciliationTasks` required to finalize the books.
*   **AuditLogEntry:** A strictly append-only, cryptographically hashed database record tracking every state change, actor, and payload within the system.

### 1. System Setup & Administration

**FR-001: User Account & SSO Management**
*   **Priority:** SHALL
*   **Description:** The system must allow administrators to manage human user access and integrate with enterprise identity providers.
*   **Acceptance Criteria:**
    *   *Given* a user with `system_admin` scope accesses the settings module,
    *   *When* they attempt to create, modify, or deactivate a user account,
    *   *Then* the system updates the user record in MongoDB and writes an `AuditLogEntry`.
    *   *Given* an enterprise tenant,
    *   *When* users attempt to log in,
    *   *Then* the system must support authentication via SAML/OAuth2 enterprise SSO providers (e.g., Okta, Azure AD).

**FR-002: Role & Scope Assignment**
*   **Priority:** SHALL
*   **Description:** Administrators must be able to securely assign functional roles that dictate the JWT scopes of human users.
*   **Acceptance Criteria:**
    *   *Given* a user with `system_admin` scope,
    *   *When* they modify a user profile,
    *   *Then* they can strictly assign either `human_reviewer`, `system_admin`, or `read_only_auditor` roles.

**FR-003: ERP Connection Management**
*   **Priority:** SHALL
*   **Description:** The system must securely store credentials required to bi-directionally sync with supported ERPs.
*   **Acceptance Criteria:**
    *   *Given* a `system_admin` configuring a tenant,
    *   *When* they connect to QuickBooks Online or NetSuite,
    *   *Then* the system initiates an OAuth2 flow or accepts securely vaulted API credentials.
    *   *Then* all generated access tokens or secrets are stored encrypted at rest.

**FR-004: ERP Data Mapping Configuration**
*   **Priority:** SHALL
*   **Description:** Administrators must be able to map specific ERP ledgers to system workflows.
*   **Acceptance Criteria:**
    *   *Given* a successfully connected ERP integration,
    *   *When* a `system_admin` accesses the mapping UI,
    *   *Then* they can link specific ERP Module IDs (e.g., "NetSuite AP Ledger") to internal platform prerequisites, allowing webhooks to trigger downstream DAG updates.

### 2. Core Workflow & Dependency Graph (DAG)

**FR-005: ReconciliationTask Definition Management**
*   **Priority:** SHALL
*   **Description:** Authorized users must be able to define the rules and parameters for individual close tasks.
*   **Acceptance Criteria:**
    *   *Given* a user with `human_reviewer` or `system_admin` scope,
    *   *When* they create or edit a `ReconciliationTask` template,
    *   *Then* they can define the task title, ERP data sources, and assign a specific AI agent or human owner.

**FR-006: System Verified DAG Creation**
*   **Priority:** SHALL
*   **Description:** The system must allow users to define a month-end close cycle consisting of tasks linked as a Directed Acyclic Graph (DAG).
*   **Acceptance Criteria:**
    *   *Given* a user is configuring a `ClosePeriod`,
    *   *When* they add a dependency (`Task A` -> `Task B`),
    *   *Then* the system executes a DFS cycle-detection algorithm.
    *   *Then* if a cycle is detected (e.g., A -> B -> A), the system rejects the input with an HTTP 422 error and a clear user-facing message.

**FR-007: Webhook-Driven Task Advancement**
*   **Priority:** SHALL
*   **Description:** The platform must ingest ERP webhooks via a high-throughput `/api/v1/webhooks/netsuite` endpoint and asynchronously update the graph state.
*   **Acceptance Criteria:**
    *   *Given* Task A is in a `Blocked` state waiting on the NetSuite AP ledger to close,
    *   *When* a valid HMAC-SHA256 signed webhook payload is received,
    *   *Then* the system responds with `202 Accepted` within 500ms and a Celery worker transitions Task A to `Ready`.
    *   *When* the webhook payload contains malformed JSON,
    *   *Then* the system responds with `400 Bad Request`.
    *   *When* the webhook lacks a valid HMAC-SHA256 signature,
    *   *Then* the system responds with `401 Unauthorized` and logs a security alert.

### 3. AI Agent Pipeline & Execution

**FR-008: Deterministic AI Task Execution**
*   **Priority:** SHALL
*   **Description:** When an AI Agent claims a task, it must fetch data, perform matching, and generate an artifact. *(Note: Specific ERP data field mappings and mathematical matching algorithms for the agent are delegated to the separate 'AI Agent Task Definition' technical specification).*
*   **Acceptance Criteria:**
    *   *Given* a task assigned to an AI agent transitions to `AI_Processing`,
    *   *When* the agent completes its logic via `crewAI`,
    *   *Then* the agent submits the artifact to the POST `/attachments` endpoint alongside a calculated `confidenceScore`.

**FR-009: AI Confidence Score Routing**
*   **Priority:** SHALL
*   **Description:** The system must intercept AI outputs and route them based on a strict confidence threshold.
*   **Acceptance Criteria:**
    *   *Given* an AI agent submits an attachment,
    *   *When* the `confidenceScore` is ≥ 0.85,
    *   *Then* the task transitions to `ReadyForReview` and the assigned human is notified.
    *   *When* the `confidenceScore` is < 0.85,
    *   *Then* the task bypasses `ReadyForReview`, transitions immediately to `ReworkRequested`, and alerts the human reviewer of an AI failure.

### 4. Human Review & Strict Audit Enforcement

**FR-010: Segregation of Duties Enforcement**
*   **Priority:** SHALL
*   **Description:** The system must strictly block AI agents from authorizing approvals.
*   **Acceptance Criteria:**
    *   *Given* an active session,
    *   *When* an entity attempts to hit the POST `/api/v1/tasks/{taskId}/approve` endpoint,
    *   *Then* the AuthZ middleware must verify the JWT scope.
    *   *Then* if the scope is `ai_preparer`, the request is rejected with `403 Forbidden` and a `FAILED_APPROVAL` security event is written to the audit log.

**FR-011: Multi-Factor Human Approval**
*   **Priority:** SHALL
*   **Description:** Human reviewers must authorize task completion using MFA.
*   **Acceptance Criteria:**
    *   *Given* a task is in `ReadyForReview`,
    *   *When* a user with `human_reviewer` scope submits the approval payload with a valid `mfaToken` (matching regex `^\d{6}$`),
    *   *Then* the task transitions to `Approved` and the `AuditLogEntry` is updated.

**FR-012: Immutable Audit Logging**
*   **Priority:** SHALL
*   **Description:** Every state change must be written to an append-only MongoDB collection.
*   **Acceptance Criteria:**
    *   *Given* any mutating API request,
    *   *When* the database transaction commits,
    *   *Then* an `AuditLogEntry` is generated containing `actorId`, `actorType`, `newState`, and a cryptographic hash calculated as `SHA256(previousHash + payload)`.
    *   *Then* any application-level attempt to UPDATE or DELETE an `AuditLogEntry` document throws a hard exception.

**FR-013: Strict Audit Mode Toggle**
*   **Priority:** SHOULD
*   **Description:** Administrators must be able to enforce elevated compliance constraints at the tenant level.
*   **Acceptance Criteria:**
    *   *Given* a user with `system_admin` scope,
    *   *When* they toggle `ENABLE_STRICT_AUDIT_MODE` to true,
    *   *Then* the system mandates secondary admin approval for DAG dependency changes and enforces MFA re-authentication on every individual task approval.

### 5. Contextual Intelligence & Notifications

**FR-014: Contextual Variance Briefings (Vertex AI RAG)**
*   **Priority:** SHOULD
*   **Description:** The system must provide AI-generated historical context for complex exceptions by querying past task data.
*   **Acceptance Criteria:**
    *   *Given* a task transitions to `ReadyForReview` with a logged variance,
    *   *When* the human user opens the task UI,
    *   *Then* the system queries Vertex AI to retrieve historical comments with a semantic similarity score > 0.7.
    *   *Then* the system generates a summary briefing of how those similar variances were resolved in the past 3 periods.

**FR-015: "Explain to Auditor" Artifact Generation**
*   **Priority:** MAY
*   **Description:** Users must be able to generate a locked compliance artifact with a single click.
*   **Acceptance Criteria:**
    *   *Given* a task is in the `Approved` state,
    *   *When* the user clicks "Explain to Auditor",
    *   *Then* the system packages the transaction data, AI math, human approver identity, and Vertex AI context into a locked PDF memo.

**FR-016: Day -3 Proactive Missing Data Nudges**
*   **Priority:** MAY
*   **Description:** The system must detect missing prerequisite data before the close period begins and stage communications.
*   **Acceptance Criteria:**
    *   *Given* the system date is 3 days prior to the start of a `ClosePeriod`,
    *   *When* the system detects missing high-value invoices identified in the DAG,
    *   *Then* it auto-drafts a Slack message to the responsible party and stages it in the UI for Controller approval.

**FR-017: The Daily Morning Briefing Push**
*   **Priority:** MAY
*   **Description:** The platform must summarize overnight automated activity and push it to collaboration tools.
*   **Acceptance Criteria:**
    *   *Given* it is 8:00 AM local tenant time,
    *   *When* overnight tasks have been processed by the `AIPreparer`,
    *   *Then* the system pushes a summary message (e.g., ledgers locked, tasks advanced) to the configured Slack/Teams webhook.

### 6. Passive Process Analytics

**FR-018: Passive Time-in-Status Tracking**
*   **Priority:** SHALL
*   **Description:** The system must calculate task duration metrics automatically without user-triggered timers.
*   **Acceptance Criteria:**
    *   *Given* a task changes state (e.g., `ReadyForReview` to `Approved`),
    *   *When* the `TaskStatusTimeLog` event listener triggers,
    *   *Then* the system asynchronously updates the exit timestamp for the previous state and begins the entry timestamp for the new state.

**FR-019: Bottleneck Heatmap Generation**
*   **Priority:** SHOULD
*   **Description:** The system must expose an endpoint for the UI to render process bottlenecks based on time-in-status data.
*   **Acceptance Criteria:**
    *   *Given* an authorized user accesses the analytics dashboard,
    *   *When* the UI calls GET `/api/v1/analytics/bottlenecks`,
    *   *Then* the API returns an aggregation of tasks grouped by DAG module, sorted descending by total time spent in the `ReadyForReview` state.

## Non-Functional Requirements

### 1. Security & Compliance (SOX 404 & ITGC)

**NFR-001: Cryptographic Immutability of Audit Logs**
*   **Priority:** SHALL
*   **Description:** To satisfy Big 4 external audit reliance, the `AuditLogEntry` collection must guarantee append-only behavior.
*   **Target:** 
    *   The system must calculate a `SHA256` hash for every log entry based on `previousHash + payload`.
    *   The system must enforce application-level blocks on any `UPDATE` or `DELETE` operations against the `audit_logs` MongoDB collection.
    *   Any detected mutation attempt must trigger a `P1` security alert and return a `403 Forbidden` response.

**NFR-002: Segregation of Duties (SoD) Authorization Boundaries**
*   **Priority:** SHALL
*   **Description:** The system must cryptographically enforce the boundary between preparers and approvers to prevent self-authorization.
*   **Target:** 
    *   JWT payloads must explicitly carry `sub` and `role` claims.
    *   FastAPI authorization middleware must evaluate every POST/PUT request against the required scope. The `ai_preparer` scope must be globally blocked from accessing any `/approve` endpoint.

**NFR-003: Multi-Factor Authentication (MFA) Integrity**
*   **Priority:** SHALL
*   **Description:** Human authorization actions in "Strict Audit Mode" must be explicitly verified.
*   **Target:** The system must validate the user-provided `mfaToken` (regex `^\d{6}$`) against the securely stored user secret within 500ms before committing any state change to `Approved`.

**NFR-004: Data Encryption**
*   **Priority:** SHALL
*   **Description:** Financial ledgers, working papers, and user credentials must be protected from unauthorized access.
*   **Target:** 
    *   Data at rest must be encrypted using AES-256 via MongoDB Atlas default encryption.
    *   Data in transit must enforce TLS 1.3 across the Cloudflare edge and internal API Gateway.
    *   ERP webhook payloads must be verified against an HMAC-SHA256 signature using Vault-stored tenant secrets before deserialization.

### 2. Performance & Scalability

**NFR-005: Webhook Ingestion Throughput**
*   **Priority:** SHALL
*   **Description:** The system must handle high-volume, concurrent ledger updates from connected ERPs during peak month-end close hours without dropping data.
*   **Target:** 
    *   The `POST /api/v1/webhooks/netsuite` endpoint must support a throughput of 1,000 requests per second (RPS).
    *   The endpoint must return a `202 Accepted` (Fast-Ack) response in < 50ms (p95).
    *   Payload size is strictly bounded to a maximum of 1MB per webhook request.

**NFR-006: DAG Recalculation Latency**
*   **Priority:** SHOULD
*   **Description:** State changes must propagate through the Dependency Graph rapidly to prevent UI staleness and AI idle time.
*   **Target:** The Celery background worker must complete a full DFS DAG traversal and update all downstream `Blocked` to `Ready` task statuses in < 5,000ms (p99) per tenant.

**NFR-007: AI & LLM Service Timeouts**
*   **Priority:** SHALL
*   **Description:** Third-party AI dependencies must not bottleneck the synchronous user experience.
*   **Target:** 
    *   Calls to Google Vertex AI for contextual RAG summaries must enforce a hard 15-second timeout.
    *   If the timeout is breached, the system must gracefully degrade by rendering a static fallback string in the UI without throwing an unhandled exception.

### 3. Reliability & Availability

**NFR-008: System Uptime**
*   **Priority:** SHALL
*   **Description:** The platform must be highly available, particularly during the critical day 1-5 month-end close window.
*   **Target:** The synchronous Core API service must guarantee a 99.9% uptime SLA (allowing for ~43 minutes of downtime per month).

**NFR-009: Message Broker Resilience**
*   **Priority:** SHALL
*   **Description:** The system must not lose asynchronous tasks if the AI worker pool or processing layer fails.
*   **Target:** 
    *   RabbitMQ must be configured with guaranteed message delivery and explicit acknowledgment (ACK) only *after* the worker successfully commits the output to the database.
    *   Messages failing processing 3 times must be routed to a Dead-Letter Queue (DLQ) for manual administrative review.

**NFR-010: Database Failover Resiliency**
*   **Priority:** SHOULD
*   **Description:** Transient database elections must not cause user-facing errors.
*   **Target:** The MongoDB PyMongo driver must be configured with `retryWrites=True`, allowing the API to automatically stall and retry requests during the ~2-second replica set failover window without dropping the connection.

### 4. Observability & Maintainability

**NFR-011: Distributed Tracing & Structured Logging**
*   **Priority:** SHALL
*   **Description:** The system must provide deep visibility into the hybrid workforce's actions to facilitate rapid debugging.
*   **Target:** 
    *   All system logs must be output in structured JSON (`structlog`).
    *   Every log entry must contain `trace_id`, `company_id`, `actor_id`, and `actor_type` (`Human`, `System`, `AIAgent`).

**NFR-012: Alerting Thresholds**
*   **Priority:** SHALL
*   **Description:** The system must proactively alert engineering to anomalous behavior before it impacts the financial close.
*   **Target:**
    *   Trigger an alert if `dag.recalculation_duration_ms` > 5000ms for 3 consecutive events.
    *   Trigger a security alert if `audit_log.mfa_failures` > 5 per minute for a single user.
    *   Trigger an alert if `api.webhook_ingest.429_count` exceeds 100 per minute for a specific tenant, indicating a potential runaway ERP loop.

## Edge Cases

### 1. AI/Human Boundary & Trust Conflicts

**EC-001: High-Confidence AI Mathematical Failure**
*   **Scenario:** The crewAI agent executes a bank reconciliation and calculates a perfect match, scoring its output with a 0.98 `confidenceScore`. The task transitions to `ReadyForReview`. However, the human reviewer spots a fundamental flaw in the AI's logic (e.g., matching a debit to the wrong vendor account despite identical amounts).
*   **Business Impact:** If the human reviewer hastily clicks "Approve," an incorrect journal entry is logged, threatening data integrity.
*   **System Behavior / Mitigation:** 
    *   The UI must enforce a mandatory "diff view" or summary checklist that the human user must interact with (e.g., scroll to the bottom or check a box) *before* the POST `/approve` endpoint is enabled. 
    *   The human reviewer clicks "Request Rework", which transitions the state from `ReadyForReview` to `ReworkRequested`, logging the human's explicit reason as context for the AI's next iteration.

**EC-002: Context Poisoning in Vertex AI (RAG)**
*   **Scenario:** The Vertex AI LLM generates a `ContextualBriefing` for a complex deferred revenue task based on historical data. However, the retrieved historical data from 3 periods ago was actually restated later due to fraud or an accounting error. 
*   **Business Impact:** The AI surfaces incorrect, historically dangerous context to a new hire, leading them to replicate an audited mistake.
*   **System Behavior / Mitigation:** 
    *   The RAG indexing pipeline must cross-reference `AuditLogEntry` metadata. Any historical task or comment associated with a period that was subsequently marked as "Restated" or "Audit Adjusted" in the ERP must be explicitly excluded from the Vertex AI vector search index, or flagged with a high-visibility warning in the UI: *"Warning: This context references a Restated Close Period."*

### 2. Compliance & Segregation of Duties (SoD) Anomalies

**EC-003: The "Last Accountant Standing" (Self-Review Risk)**
*   **Scenario:** A company is operating in "Strict Audit Mode". The Controller is out sick, and the only active `human_reviewer` assigns a task to themselves, completes the preparation manually (bypassing the AI), and then attempts to approve their own work.
*   **Business Impact:** Immediate SOX 404 ITGC violation due to a failure in Segregation of Duties (a single human acting as both preparer and reviewer).
*   **System Behavior / Mitigation:** 
    *   When the POST `/approve` request is received, the FastAPI AuthZ middleware must compare the `sub` claim of the approver's JWT against the `assignedHumanId` (if the task was manually prepared) or the `creatorId` of the task attachment.
    *   If `approver_id == preparer_id`, the system must reject the request with `409 Conflict` (SoD Violation), preventing the state from transitioning to `Approved`, and requiring a secondary credentialed user to sign off.

**EC-004: Mid-Close "Strict Audit Mode" Toggle**
*   **Scenario:** A `system_admin` toggles `ENABLE_STRICT_AUDIT_MODE` from `False` to `True` while an active `ClosePeriod` is currently 50% complete (tasks are in a mix of `Pending`, `ReadyForReview`, and `Approved` states).
*   **Business Impact:** Tasks previously approved without MFA or secondary sign-offs might be viewed as non-compliant, creating a mixed-state audit trail that auditors cannot rely upon.
*   **System Behavior / Mitigation:** 
    *   The system must block the toggling of `ENABLE_STRICT_AUDIT_MODE` if there is an active (non-Closed) `ClosePeriod`. 
    *   The toggle can only take effect for the *next* generated `ClosePeriod`. If an emergency toggle is forced, the system must trigger a global state reset for the current period, moving all `ReadyForReview` and `Approved` tasks back to `Pending` to enforce the new compliance rules uniformly.

### 3. ERP Integration & State Machine Race Conditions

**EC-005: Out-of-Order ERP Webhook Ingestion**
*   **Scenario:** Due to network jitter or NetSuite API delays, the platform receives a webhook indicating "AR Ledger Closed" *before* it receives the queued webhook indicating "AR Invoices Posted". 
*   **Business Impact:** The DAG Evaluation Engine prematurely advances the downstream "Bad Debt Reserve" task to `Ready`, causing the crewAI agent to process incomplete ledger data.
*   **System Behavior / Mitigation:** 
    *   The Ingestion Service must parse the ERP timestamp embedded in the webhook payload, not the system receipt time.
    *   The DAG engine must implement a deterministic hold (e.g., a 60-second buffer or an explicit reconciliation check against the ERP API) before transitioning a `TaskNode` from `Blocked` to `Ready` to ensure ledger completeness.

**EC-006: Post-Approval ERP Ledger Mutation**
*   **Scenario:** A task is completed, reviewed by a human, and transitioned to `Approved`. Five minutes later, an accountant bypasses the platform, logs directly into NetSuite, and posts a backdated journal entry to the exact ledger that was just reconciled.
*   **Business Impact:** The Continuous Close Platform shows a 100% tied-out, approved state, but the underlying ERP reality has shifted. The audit trail is now factually incorrect.
*   **System Behavior / Mitigation:** 
    *   The system must continue to subscribe to ERP webhooks for ledgers associated with `Approved` tasks until the entire `ClosePeriod` is locked.
    *   If a webhook detects a mutation on an `Approved` ledger, the system must forcefully revert the `ReconciliationTask` status to `ReworkRequested`, generate a critical alert to the Controller, and append a specific "Post-Approval Discrepancy" event to the `AuditLogEntry`.

### 4. User Behavior & Concurrency

**EC-007: Concurrent Human and AI Task Claiming**
*   **Scenario:** A task transitions to `Pending`. A `crewAI` worker picks up the task from RabbitMQ and begins processing. Simultaneously, an impatient human user logs in and manually clicks "Start Task" on the UI.
*   **Business Impact:** Wasted compute resources, duplicated effort, and a potential race condition when both actors attempt to POST attachments to the same task.
*   **System Behavior / Mitigation:** 
    *   The system must employ Optimistic Concurrency Control (OCC) using a version number on the `ReconciliationTask` MongoDB document.
    *   When the human clicks "Start Task", the UI issues a PUT request. If the document version has already been incremented by the `crewAI` worker claiming it (transitioning to `AI_Processing`), the human's request is rejected with a `409 Conflict`, and the UI updates to show "Currently being processed by AI Agent."

## Error Handling

### 1. Error Taxonomy & System Responses

The system categorizes errors into four distinct domains to ensure appropriate severity tagging, user communication, and system-level recovery strategies.

| Error Category | Source | HTTP Status | Mitigation Strategy | Alerting Level |
| :--- | :--- | :--- | :--- | :--- |
| **Integration Failure** | NetSuite / QBO API | `429` (Rate Limit), `503` (Unavailable), `504` (Timeout) | Exponential Backoff; graceful task suspension. | P3 (Warn) -> P1 (Critical) if persistent > 1hr. |
| **Agent / AI Failure** | crewAI / Vertex AI | `422` (Unprocessable Entity), `<0.85` Confidence Score | Transition task to `ReworkRequested`; static UI fallback. | P2 (High) if failure rate > 5% within 10 mins. |
| **Workflow Conflict** | State Machine / OCC | `409` (Conflict) | Reject action; force client state refresh. | P4 (Info) - Standard business logic. |
| **Security Violation** | AuthZ Middleware | `401` (Unauthorized), `403` (Forbidden) | Hard block; write FAILED_APPROVAL to `AuditLogEntry`. | P1 (Critical) |

### 2. Integration & Network Errors (ERP APIs)

**EH-001: ERP API Rate Limiting (HTTP 429)**
*   **Scenario:** A `crewAI` worker attempts to fetch thousands of ledger lines from NetSuite, hitting the API rate limit.
*   **System Action:** The Celery worker must intercept the `429` response and implement an Exponential Backoff strategy (e.g., retry after 5s, 15s, 45s).
*   **Fallback:** If the request fails after 3 retries, the system must transition the `ReconciliationTask` state from `AI_Processing` back to `Pending` and route the task to a Dead-Letter Queue (DLQ).
*   **User Communication:** The UI displays a warning badge on the task: *"Task delayed: ERP system is currently rate-limiting data requests. Retrying automatically."*

**EH-002: ERP Webhook Payload Malformation**
*   **Scenario:** A NetSuite webhook arrives with a valid HMAC-SHA256 signature but contains a malformed JSON body or is missing required routing keys.
*   **System Action:** The FastAPI ingestion endpoint must immediately return a `400 Bad Request` to the sender to prevent poisoning the RabbitMQ queue.
*   **Fallback:** The raw payload and headers must be dumped to Datadog for engineering analysis. The DAG remains blocked until a valid webhook is received.

### 3. Agent & AI Processing Errors

**EH-003: Vertex AI LLM Timeout**
*   **Scenario:** A human user opens a `ReadyForReview` task, triggering a real-time request to Vertex AI for a `ContextualBriefing` (RAG). The Vertex AI service hangs or exceeds the hard 15-second timeout.
*   **System Action:** The backend must catch the timeout exception. The system must **never** block the rendering of the core reconciliation data (CSV attachments, math) due to an LLM failure.
*   **User Communication:** The frontend gracefully degrades the "Contextual Intelligence" panel, displaying: *"Historical context is currently unavailable due to high AI latency. Standard review workflows remain active."*

**EH-004: Agent Hallucination / Schema Violation**
*   **Scenario:** The `crewAI` worker generates a CSV artifact, but fails to calculate a required output field, or returns a confidence score of `null` or a value `< 0.85`.
*   **System Action:** The POST `/attachments` endpoint must perform strict Pydantic validation. If the confidence score is missing or below the threshold, the system rejects the output.
*   **Fallback:** The task bypasses `ReadyForReview` and transitions directly to `ReworkRequested`.
*   **User Communication:** The assigned human reviewer receives a notification: *"AI Preparer encountered an anomaly matching the AP ledger. Manual review and rework required."*

### 4. Workflow & State Machine Errors

**EH-005: Optimistic Concurrency Control (OCC) Collision**
*   **Scenario:** A human clicks "Approve" at the exact millisecond the `system_admin` forces a global "Strict Audit Mode" reset, which attempts to revert the task to `Pending`.
*   **System Action:** MongoDB throws a `WriteConflict` exception because the document `__v` (version) integer no longer matches the human's payload. 
*   **User Communication:** The FastAPI endpoint returns `409 Conflict`. The UI displays a non-technical error: *"The state of this task has changed since you opened it. Please refresh to see the latest updates."* The user's approval action is safely discarded.

### 5. Security & Authentication Errors

**EH-006: Unauthorized Agent Action (Segregation of Duties Violation)**
*   **Scenario:** A compromised or misconfigured `crewAI` worker attempts to submit a payload to the POST `/api/v1/tasks/{taskId}/approve` endpoint using its `ai_preparer` JWT token.
*   **System Action:** The AuthZ middleware must intercept and reject the request instantly with a `403 Forbidden` status. 
*   **Audit Requirement:** The system must generate a high-severity `AuditLogEntry` indicating `FAILED_APPROVAL_ATTEMPT` with the `actorId` of the AI agent, and trigger a P1 Datadog alert to the SecOps team.

**EH-007: MFA Validation Failure in Strict Audit Mode**
*   **Scenario:** A human reviewer submits the approval payload with an incorrect or expired 6-digit `mfaToken`.
*   **System Action:** The system rejects the request with a `401 Unauthorized` status. The task remains in `ReadyForReview`.
*   **User Communication:** The UI displays: *"Invalid MFA code. Please check your authenticator app and try again."*
*   **Audit Requirement:** If a single `actorId` generates more than 5 consecutive `401` MFA failures within a 60-second window, the system must temporarily lock the user session and log a `Brute_Force_Attempt` event.

## Success Metrics

### 1. Primary Business Outcomes (North Star Metrics)

**SM-001: Speed to Close (Days to Close)**
*   **Definition:** The total calendar days required to finalize all `ReconciliationTasks` within a given `ClosePeriod`, measured from the last day of the month to the timestamp of the final task transitioning to `Approved`.
*   **Baseline:** 15 days (Industry average for mid-market batch processing).
*   **Target:** A 30%+ reduction (≤ 10.5 days) within the first two full financial quarters of platform adoption.
*   **Measurement:** Calculated natively via the `TaskStatusTimeLog` aggregations across the entire DAG.

**SM-002: Audit Defensibility (Zero-Deficiency Reliance)**
*   **Definition:** The ability for external auditors (Big 4 / Regional firms) to rely entirely on the system's generated ITGC and Segregation of Duties (SoD) logs without finding compliance failures.
*   **Baseline:** High volume of manual email/spreadsheet tracing required during external audits.
*   **Target:** 0 deficiency findings related to SoD, unauthorized approvals, or audit trail immutability during the customer's first annual audit cycle post-implementation.
*   **Measurement:** Qualitative confirmation from external audit partners; Quantitative measurement of 0 manual rollbacks or overrides required on the `AuditLogEntry` collection.

### 2. AI Efficacy & Workflow Adoption

**SM-003: AI Automation Adoption Rate**
*   **Definition:** The percentage of baseline, rote `ReconciliationTasks` (e.g., bank feed matching) that are assigned to and completed by `crewAI` agents rather than human preparers.
*   **Baseline:** 0% (Current state is entirely manual).
*   **Target:** >60% of all eligible data-gathering and preliminary reconciliation tasks handled by AI within 90 days of launch.
*   **Measurement:** Count of tasks where `actorType = AIAgent` transitioning from `AI_Processing` to `ReadyForReview` divided by the total number of tasks in the `ClosePeriod`.

**SM-004: AI First-Pass Acceptance Rate (FPAR)**
*   **Definition:** The percentage of AI-prepared tasks that are approved by a human reviewer without requiring a transition to `ReworkRequested`.
*   **Baseline:** N/A (New feature).
*   **Target:** >85% FPAR for AI-generated working papers.
*   **Measurement:** Tracked via state transitions in MongoDB. `count(AI_Processing -> ReadyForReview -> Approved) / count(Total tasks assigned to AI)`. A low FPAR indicates the `confidenceScore` threshold needs tuning or the underlying agent logic requires refinement.

**SM-005: Contextual Briefing Utilization**
*   **Definition:** The frequency with which human reviewers engage with the Vertex AI generated historical context during complex exception reviews.
*   **Baseline:** 0%
*   **Target:** >40% engagement (clicks to expand or view) on the "Explain Context" RAG component for tasks flagged with variances.
*   **Measurement:** Frontend UI events tracked (e.g., Mixpanel/Amplitude) when a user clicks to view the Vertex AI contextual summary.

### 3. Operational & System Efficiency

**SM-006: CPA Time Reallocation (Time-in-Status Reduction)**
*   **Definition:** The reduction in human hours spent in the `Pending` or data-gathering phase, representing the shift from rote preparation to exception handling.
*   **Baseline:** 60% of CPA bandwidth spent on data gathering.
*   **Target:** 50% reduction in average human "Time-in-Status" for data preparation phases.
*   **Measurement:** Passive time tracking delta. Measure the duration tasks sit in `Pending` or `Draft` before moving to `ReadyForReview`.

**SM-007: DAG Workflow Bottleneck Identification**
*   **Definition:** The system's ability to accurately surface process bottlenecks to management.
*   **Baseline:** Controllers rely on anecdotal feedback or manual timesheets.
*   **Target:** 100% of tenant admin dashboards display real-time, accurate bottleneck heatmaps generated from the GET `/api/v1/analytics/bottlenecks` endpoint.
*   **Measurement:** System health metric; ensuring the aggregation endpoint consistently returns accurate, sub-second (p95) payload data for UI rendering.

## Dependencies

### 1. Third-Party APIs & Services

**DEP-001: NetSuite REST API**
*   **Description:** The platform relies heavily on NetSuite’s REST API to ingest financial ledger states, fetch transaction data for reconciliations, and receive webhook notifications.
*   **Impact of Failure:** If NetSuite's API is unresponsive, rate-limited, or deprecates required endpoints, the `crewAI` agents cannot fetch data to perform baseline reconciliations, and the DAG state machine cannot advance automatically.
*   **Mitigation:** Implement strict exponential backoff, circuit breakers, and fallback to manual human task advancement. Maintain close alignment with NetSuite API release notes.

**DEP-002: QuickBooks Online (QBO) API**
*   **Description:** Similar to NetSuite, QBO APIs are required for the SMB segment to ingest trial balances, journal entries, and bank feed data.
*   **Impact of Failure:** Disrupts the core value proposition for SMB customers transitioning to enterprise practices.
*   **Mitigation:** Utilize Intuit's officially supported SDKs and monitor their developer portal for breaking changes.

**DEP-003: Google Vertex AI**
*   **Description:** The system relies on Vertex AI for generating contextual briefings and "Explain to Auditor" summaries using Retrieval-Augmented Generation (RAG) over historical task comments.
*   **Impact of Failure:** If the LLM service times out or is degraded, the contextual continuity features fail, forcing accountants back to manual email/Slack searches.
*   **Mitigation:** Enforce a hard 15-second timeout on all LLM calls. If Vertex AI fails, the UI must gracefully degrade to a standard manual view without blocking the core close workflow.

**DEP-004: crewAI Framework**
*   **Description:** The core orchestration engine used to manage, restrict, and execute the AI agent workflows within Celery workers.
*   **Impact of Failure:** Bugs or incompatible updates in the `crewAI` framework could break the deterministic matching logic or cause agent execution crashes.
*   **Mitigation:** Pin the specific stable version of the `crewAI` package (e.g., `1.9.x`) in the Python environment. Comprehensive E2E testing must gate any framework version upgrades.

### 2. Infrastructure & Frameworks

**DEP-005: MongoDB Atlas (Document & Search)**
*   **Description:** The primary datastore for `ReconciliationTasks`, the DAG (`TaskNode`), and the strictly immutable `AuditLogEntry` collection.
*   **Impact of Failure:** A database outage completely halts the platform. Inability to write to the `AuditLogEntry` collection violates SOX 404 compliance immediately.
*   **Mitigation:** Utilize a multi-AZ replica set with `retryWrites=True` for seamless failover handling. Implement daily automated backups with distinct geographic disaster recovery rules.

**DEP-006: RabbitMQ & Celery**
*   **Description:** The message broker and background task execution environment responsible for handling high-volume webhooks and scheduling asynchronous AI tasks.
*   **Impact of Failure:** A broker failure prevents state changes from being processed, causing tasks to appear permanently "stuck" in `Blocked` or `Pending` states.
*   **Mitigation:** Deploy RabbitMQ in a highly available cluster. Configure Dead-Letter Queues (DLQs) for unprocessable messages to prevent silent failures.

### 3. External Stakeholders & Regulatory Bodies

**DEP-007: External Auditors (Big 4 / Regional Firms)**
*   **Description:** The product's success metrics are directly tied to the "zero-deficiency reliance" metric by external auditors on the platform's system-generated ITGC logs.
*   **Impact of Failure:** If a major audit firm refuses to accept the platform's `AuditLogEntry` or questions the segregation of duties boundary between the AI and humans, the product loses its enterprise value proposition.
*   **Mitigation:** Conduct early-stage reviews of the system architecture and `AuditLogEntry` schema with certified IT Audit partners (e.g., during beta) to ensure the outputs explicitly satisfy AICPA and SOX 404 standards.

### 4. Internal Cross-Functional Teams

**DEP-008: Information Security (InfoSec) Team**
*   **Description:** Required to validate the AuthZ middleware, the strict human-AI access boundaries, and the cryptographic hashing algorithm (`SHA256`) used for the audit logs.
*   **Impact of Failure:** Delayed security sign-off will block the release of "Strict Audit Mode," preventing deployment to mid-market enterprise clients.
*   **Mitigation:** Engage InfoSec during the architecture design phase. Provide the Engineering Plan and PRD upfront for proactive threat modeling.

## Assumptions

### 1. Business & Organizational Assumptions
*   **Willingness to Delegate to AI:** We assume that >70% of target Corporate Controllers and CFOs in the mid-market segment will be willing to delegate over 50% of eligible rote data-gathering and baseline reconciliation tasks to an AI agent (`crewAI`), provided there is a mathematically proven, immutable audit trail and a mandatory human approval step. 
    *   *Validation Strategy:* Monitor SM-003 (AI Automation Adoption Rate) during beta and post-launch. Conduct qualitative user interviews to understand perceived trust and behavioral barriers to delegation.
*   **Process Maturity:** We assume that target users, despite current 'month-end chaos,' possess sufficient understanding of their financial processes to define a coherent and logical Directed Acyclic Graph (DAG) for at least 80% of their close process tasks during onboarding, with an average of <10% rework rate for initial DAG configurations.
    *   *Validation Strategy:* Track the time-to-onboard and the frequency of DAG dependency edits (`system_admin` actions in the `AuditLogEntry`) during the first 30 days of a new tenant's deployment.

### 2. Technical & Ecosystem Assumptions
*   **ERP Standardization:** We assume that the target customer base utilizes QuickBooks Online (QBO) and NetSuite ledger configurations that adhere to generally accepted accounting principles (GAAP) and do not include highly customized, non-standard fields or business logic that would prevent automated, deterministic matching by AI agents.
    *   *Validation Strategy:* Conduct rigorous integration testing with anonymized customer data sets across various industries prior to general availability to ensure the baseline AI agent logic handles 90%+ of standard ledger mappings out-of-the-box.
*   **API Rate Limits & Polling:** We assume that the API rate limits provided by standard QBO and NetSuite enterprise tiers are sufficient to support continuous polling and high-throughput webhook ingestion without throttling the core `crewAI` background workers during peak close days (Days 1-5).
    *   *Validation Strategy:* Monitor API `429 Too Many Requests` frequency (EH-001) in Datadog. Implement load testing simulating peak month-end traffic against sandbox ERP environments.
*   **LLM Determinism for RAG:** It is assumed that Google Vertex AI can consistently return semantically relevant historical task contexts within a 15-second timeout window, and that the vector search index can reliably filter out restated or anomalous historical data.
    *   *Validation Strategy:* Track latency and error rates of the Vertex AI RAG endpoints. Monitor user engagement metrics (SM-005) to ensure the provided context is actually deemed useful by human reviewers.
*   **AI Model Longevity & Evolution:** We assume that the underlying AI models (e.g., Vertex AI LLM, crewAI framework logic) will remain stable, evolve predictably, and provide consistent performance without significant model drift or abrupt API changes that would necessitate complete re-training or re-engineering of core agent logic.
    *   *Validation Strategy:* Establish a regular automated testing suite (e.g., weekly) that runs standard financial reconciliation prompts against the LLM/crewAI framework to detect regressions or drift in output accuracy.

### 3. Operational Assumptions
*   **Talent Availability:** We assume that sufficient specialized talent (e.g., AI/ML engineers, accounting automation specialists) will be available, either internally or via partners, to develop, train, and maintain the complex AI agents and integration workflows over the product's lifecycle.
    *   *Validation Strategy:* Monitor hiring pipelines and assess the velocity of resolving complex edge-case bugs related to agent hallucination or matching logic failures.
*   **MFA Adoption:** We assume that client organizations either already utilize enterprise SSO (e.g., Okta, Azure AD) or are willing to enforce Multi-Factor Authentication (MFA) at the application level to satisfy the "Strict Audit Mode" requirements.
    *   *Validation Strategy:* Track the adoption rate of "Strict Audit Mode" (FR-013) vs. standard fluid workflows across the customer base.

### 4. Regulatory & Audit Assumptions
*   **Audit Defensibility:** It is assumed that Big 4 and regional external auditors will recognize and accept a cryptographically hashed, append-only MongoDB `AuditLogEntry` as sufficient and immutable evidence for Segregation of Duties (SoD) and IT General Controls (ITGC) compliance under SOX 404 standards.
    *   *Validation Strategy:* Partner with independent IT Audit consultants during the beta phase to conduct a mock SOX 404 audit specifically targeting the platform's system-generated trails and "Explain to Auditor" artifacts.
*   **AI as a "Preparer":** We assume that regulatory bodies and audit partners will legally and procedurally accept an AI agent acting as a "Preparer" of financial data, provided a credentialed human explicitly acts as the "Reviewer" and assumes ultimate fiduciary responsibility for the approval.
    *   *Validation Strategy:* Solicit formal legal and compliance opinions from industry experts and track evolving AICPA guidelines regarding AI-assisted accounting workflows.
