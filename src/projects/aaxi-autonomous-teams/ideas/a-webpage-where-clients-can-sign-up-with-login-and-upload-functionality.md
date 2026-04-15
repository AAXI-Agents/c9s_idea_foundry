---
run_id: f828842fef13
status: completed
created: 2026-04-13T06:45:57.941157+00:00
completed: 2026-04-13T07:31:14.529364+00:00
project: "[[aaxi-autonomous-teams]]"
tags: [idea, prd, completed]
---

# a webpage where clients can sign up with login and upload functionality

> Part of [[aaxi-autonomous-teams/aaxi-autonomous-teams|AAXI Autonomous Teams]] project

## Original Idea

a webpage where clients can sign up with login and upload functionality

## Refined Idea

Headless M&A Data Structuring API**
*Theme: Platform/API approach*

Instead of forcing clients to adopt a new, standalone Document Ingestion Gateway, this alternative builds a "headless" API and webhook architecture that integrates directly with the tools clients and advisors already use (e.g., Box, SharePoint, Google Workspace) or legacy VDRs (Datasite, Intralinks). As a seller drops a messy file like "Scan_0045_Final.pdf" into a standard shared folder, our middleware automatically intercepts it, performs the OCR and AI auto-classification, renames the file in place, and silently pushes the structured metadata to our downstream AI agents.

**Key Trade-off vs. Current Direction:** 
We lose control of the end-to-end user experience and cannot easily enforce the visual, interactive "Checklist" UI to actively prompt clients for missing files. However, this dramatically reduces onboarding friction. Sell-side founders and CFOs won't have to learn a new software interface, adopt new workflows, or manage new login credentials; they simply use their existing enterprise cloud storage while we provide the invisible intelligence layer.

**

## Executive Summary

## Executive Summary

**Problem Statement**  
Sell-side founders, CFOs, and M&A advisors suffer from severe "tool fatigue" and adoption friction when forced to migrate due diligence workflows into new, standalone Document Ingestion Gateways. Beyond user frustration, these standalone platforms create severe security vulnerabilities via shadow IT, introduce hidden licensing costs, and isolate documents in disconnected data silos. This friction leads to chaotic, unstructured data dumps (e.g., "Scan_0045_Final.pdf") in legacy systems, which heavily delays time-to-value, consumes upwards of 40% of advisor bandwidth, and starves downstream AI qualification workflows of the deterministic metadata they require to function. 

**Target Audience & Key Stakeholders**  
*   **Sell-Side Founders & CFOs (End Users):** Require zero-friction workflows using their existing enterprise tools (e.g., Box, SharePoint, legacy VDRs) without the burden of learning new software or managing new credentials.  
*   **M&A Advisors (Beneficiaries):** Need instantly structured, accurately categorized, and validated document repositories to accelerate due diligence without constantly prompting clients for corrected files.  
*   **Internal AI / Engineering Teams:** Depend on a deterministic, high-quality, normalized stream of metadata to successfully trigger and fuel the downstream "M&A crewAI agentic solution."  

**Proposed Solution & Functional Scope**  
The Headless M&A Data Structuring API is a middleware intelligence layer that integrates natively into the tools clients already use. Rather than forcing users into a proprietary UI, the system utilizes OAuth 2.0 authorized native webhooks and API polling to silently monitor standard shared folders (e.g., Box, SharePoint). 
*   **Ingestion & Processing:** When a raw document is uploaded, the API automatically intercepts it, executes OCR, and runs AI auto-classification.
*   **Renaming & Taxonomy:** The system executes non-destructive, in-place renaming of files according to strict M&A taxonomy standards (e.g., `[Phase]_[Category]_[Counterparty]_[Date]_[Version].pdf`), utilizing platform-native versioning to preserve the original file as a historical artifact.
*   **Metadata Handoff:** It generates a structured JSON metadata payload (including `DocumentType`, `TransactionPhase`, `Counterparty`, `ConfidenceScore`, and `Entities`) and pushes it to our downstream AI agents.
*   **Asynchronous Prompting:** To bridge the UX gap of a missing frontend checklist, downstream crewAI agents continually audit the metadata payload against a required due diligence JSON schema. If an expected document type for a specific transaction phase is missing, the agent asynchronously triggers a localized Slack or Email notification to the advisor or client specifying the exact gap.

**Non-Functional Requirements**  
*   **Security & Compliance:** Must be SOC 2 Type II compliant, enforce strict Role-Based Access Control (RBAC) mirroring the host platform's permissions, and utilize AES-256 encryption for data at rest and TLS 1.3 in transit.
*   **Scalability & Reliability:** The API layer must support a volume of up to 10,000 documents per day per client and maintain a 99.9% uptime SLA.
*   **Performance Targets:** Aggregate batch processing (ingestion, classification, renaming) must complete in < 5 minutes. Sub-processes like OCR and AI classification must execute in < 60 seconds at p95 latency.
*   **Data Retention:** Processed documents and metadata caches must strictly conform to client-defined retention policies, defaulting to a 30-day post-deal deletion protocol.

**Edge Cases & Error Handling**  
*   **File Anomalies:** Unsupported file types (e.g., audio, proprietary extensions) or corrupted/unreadable files will bypass processing and be automatically routed to a designated "Quarantine" sub-folder with an automated alert to the advisor.
*   **Naming Collisions:** Handled by appending a unique UUID or incrementing version integers to the M&A taxonomy filename.
*   **AI Misclassification:** If AI classification confidence scores fall below 85%, the system triggers a "Human-in-the-Loop" fallback, moving the document to an 'Unsorted' folder for manual advisor review.
*   **System Failures:** External API rate limits or integration outages are mitigated via an exponential backoff and retry queue, ensuring zero data loss during transient network failures. Document updates or deletions in the source folder trigger corresponding lifecycle webhooks to keep the metadata state in sync.

**Expected Business Impact, Analytics & Success Criteria**  
*   **Frictionless Adoption:** 0 net-new login credentials or UI onboarding sessions required for sell-side users.
*   **Processing Velocity:** Reduce end-to-end document processing time from hours to < 5 minutes. 
*   **Data Accuracy & Monitoring:** Achieve > 95% AI classification accuracy in V1. Operational health will be continuously monitored via tracking API error rates (target < 1%), AI confidence score percentiles, and latency per component.
*   **Bandwidth Reduction:** Reduce overall advisor onboarding bandwidth consumption by at least 30%, measured quantitatively via bi-weekly advisor time-tracking surveys and a logged reduction in automated system follow-up requests.
*   **Auditability:** 100% of critical system actions (ingestion, renaming, classification, metadata generation) must be captured in immutable audit logs.

**Dependencies & Risk Mitigation**  
*   **Dependencies:** External enterprise APIs (Box, SharePoint, Datasite), internal `crewAI` orchestration layer for async prompting, and third-party OCR/LLM service providers.
*   **Integration Risk:** Breaking changes or rate limits in external APIs. *Mitigation:* Implement an abstracted integration adapter layer, daily automated API health checks, and graceful degradation (fallback to manual upload alerts).
*   **AI Drift & Hallucination Risk:** Model drift leading to incorrect metadata extraction. *Mitigation:* Strict JSON schema enforcement, continuous evaluation pipelines on a gold-standard dataset, and the < 85% confidence human-in-the-loop fallback.
*   **Adoption Risk:** Users bypassing the monitored shared folders entirely. *Mitigation:* Provide clear, standardized onboarding communication templates for advisors and implement automated gentle-reminder webhooks if complete inactivity is detected within the first 48 hours of phase kickoff.

## Executive Product Summary

# Executive Product Summary: The Invisible Deal Quarterback

## 1. The Real Problem: Time Kills All Deals
If you ask an M&A advisor or a sell-side founder what their biggest pain point is, they will say "document ingestion," "tool fatigue," or "shadow IT." 

They are wrong. Those are symptoms. **The actual problem is that due diligence destroys deal momentum and founders' sanity.** 

The transition from running a company to selling a company introduces a massive, soul-crushing administrative tax. Founders and CFOs are forced to pause their actual jobs to become full-time file clerks, dumping poorly named files (like `Scan_0045_Final.pdf`) into proprietary Virtual Data Rooms (VDRs) they don't know how to use. Advisors then burn 40% of their bandwidth nagging clients, sorting these files, and fixing metadata so downstream systems can work. Friction spikes, tempers flare, and deals stall. 

We don't need to build a better portal. We need to completely eliminate the concept of "uploading to a portal." 

## 2. The 10-Star Product Vision: Invisible Intelligence
The 10-star version of this product is not a "Headless M&A Data Structuring API." It is an **Invisible Deal Quarterback**. 

We are going to scrap the idea that users need to change their behavior to fit our software. Instead, our software will seamlessly wrap around their existing behavior. If a CFO uses Box, we live in Box. If they use SharePoint, we live in SharePoint. 

The vision: A founder drops a chaotic, 500-file ZIP dump into their standard company shared folder and goes to get a coffee. By the time they sit back down, the folder has magically structured itself. Every file is perfectly renamed to Wall Street M&A standards, categorized into clean sub-folders, and natively version-controlled. Furthermore, the downstream AI has already analyzed the contents and sent a polite Slack message celebrating the progress and highlighting exactly what is still missing. 

No logins. No new passwords. No user manuals. Just instant, magical order out of chaos. 

We will bridge the gap between human messiness and AI precision, delivering 10x the value by making the product completely invisible.

## 3. The Ideal User Experience: "This is exactly what I needed."
Imagine Sarah, the CFO of a mid-market SaaS company preparing for acquisition. It’s 4:30 PM on a Friday. The M&A advisor just requested "all vendor contracts and Q3 financials."

**The Old Way:** Sarah groans, spends three hours renaming files, zips them, logs into a clunky VDR she forgot the password to, waits for the upload, and prays she didn't miss anything.

**The New Way:** Sarah selects 80 messy, randomly named PDFs on her desktop and drags them straight into her existing `Company/Legal_Diligence` folder on Google Drive. She closes her laptop. 
*   *Instantly & invisibly*, our intelligence layer intercepts the files. 
*   It reads, classifies, and non-destructively renames them (e.g., `Phase1_VendorContract_AWS_Oct2023_v1.pdf`).
*   Five minutes later, Sarah gets a direct Slack ping on her phone: *"Hey Sarah! Great news—all 80 vendor contracts were successfully processed and categorized for the buyer. We noticed the Q3 Profit & Loss statement wasn't in that batch. Drop it in the folder whenever you have a second, and you’re fully done for the week! Have a great weekend."*

Sarah doesn't think about APIs, OCR, or JSON payloads. She thinks: *"This is exactly what I needed. They actually respect my time."*

## 4. Delight Opportunities (High-Impact "Bonus Chunks")
To make this feel truly magical, we will implement these sub-30-minute additions that prove we deeply understand our users:

*   **The Living "Readme" Checklist:** Instead of forcing users to log into a dashboard to see what's missing, our API automatically generates and drops a beautifully formatted, auto-updating `00_Diligence_Progress.pdf` (or HTML file) directly into the root of their shared folder. Every time they open the folder, their checklist is right there, already updated.
*   **The Auto-Redaction "Safe" Clone:** When our AI classifies a highly sensitive document (e.g., Cap Table or Employee Comp), it automatically generates a duplicate file named `[Filename]_REDACTED.pdf` using basic PII masking. The advisor thinks, *"Oh nice, they thought of that before I even had to ask."*
*   **Zero Silent Failures via the `_Needs_Human_Eyes` Folder:** If a file is hopelessly corrupted or password-protected, we do not just log an API error. We automatically move it into a brightly colored folder named `_Needs_Human_Eyes` and drop a tiny `.txt` file next to it explaining *exactly* why (e.g., "Needs_Password.txt"). The failure mode becomes a clear, actionable UI.
*   **Momentum High-Fives (Slack/Email):** Program the downstream crewAI agents to not just nag about missing files, but to actively celebrate milestones (e.g., *"Financial Diligence is now 100% complete! Great work."*). M&A is stressful; be the tool that provides dopamine, not just demands.

## 5. Scope Mapping: The 12-Month Trajectory

*   **Current State (The Baseline):** Siloed, legacy Document Ingestion Gateways. Shadow IT risks, messy data dumps, manual renaming, and advisors acting as overpaid file clerks. Downstream AI starves because the metadata is garbage.
*   **This Plan (Months 1-6): The Invisible Intelligence Layer.** 
    *   Native OAuth webhooks into Box/SharePoint/Drive. 
    *   Sub-5-minute batch processing (OCR + LLM Classification). 
    *   In-place, non-destructive file renaming and perfect JSON metadata generation. 
    *   Async Slack/Email prompting via crewAI. 
    *   Zero new user interfaces.
*   **12-Month Ideal (Months 6-12): Direct System Extraction.** 
    *   If the user experience is "uploading files is annoying," the ultimate solution is *eliminating the files*. 
    *   We evolve the API to integrate directly into the source of truth: QuickBooks (Financials), Gusto (HR), and Salesforce (Revenue). 
    *   We bypass the shared folder entirely for 80% of diligence, automatically generating the required PDFs and structuring them into the VDR without human intervention. We move from "organizing what you give us" to "getting it for you."

## 6. Business Impact & Success Criteria
This isn't just a quality-of-life feature; it is a fundamental competitive wedge. By removing the friction of document ingestion, we render traditional VDR onboarding obsolete. Advisors will demand this product because it increases their effective hourly rate by 40%. Founders will demand it because it gives them their time back. 

**Measurable Success Criteria:**
1.  **Frictionless Adoption:** Exactly 0 net-new login credentials or UI onboarding sessions required for sell-side users.
2.  **Processing Velocity:** Time from user dropping a raw file to the AI having structured, deterministic metadata drops from an industry average of 48 hours to < 5 minutes.
3.  **Accuracy & Health:** >95% AI classification accuracy in V1. 100% visibility into failures (Zero silent failures). 
4.  **Adviser Bandwidth:** Quantifiable 30% reduction in advisor time spent on document administration and client follow-up, freeing them to focus purely on deal strategy and buyer negotiation. 

We are not building a better file sorter. We are building the engine that keeps deals alive. Let's get to work.

## Engineering Plan

## 1. Architecture Overview
The Headless M&A Data Structuring API is an event-driven, distributed middleware platform. It eliminates manual Virtual Data Room (VDR) onboarding by intercepting files dragged into standard cloud storage (Box, Google Drive, SharePoint), processing them via an asynchronous AI pipeline, and non-destructively mutating them in place. The architecture relies on webhook ingress, distributed message queues for decoupling, worker pools for compute-heavy Optical Character Recognition (OCR) and Vision-Language Model (VLM) tasks, and a secure egress gateway to push structured metadata to downstream broker systems.

### Technical Deep-Dive

**Technology Stack & Rationale:**
*   **Compute:** Python 3.11 + FastAPI. *Rationale: Python dominates the AI/ML ecosystem, making VLM/LLM library integration seamless. FastAPI provides high-throughput async I/O suitable for webhook ingress/egress.*
*   **Message Broker:** Apache Kafka. *Rationale: Strictly ordered processing per deal context, natively supports backpressure, and allows replayability.*
*   **Database:** PostgreSQL 16. *Rationale: ACID guarantees are non-negotiable for state machine tracking and optimistic concurrency control. JSONB columns perfectly handle dynamic extracted metadata.*
*   **Caching/Rate-Limiting:** Redis. *Rationale: Sliding window rate limits and ephemeral anomaly-detection aggregations.*
*   **Storage:** Ephemeral S3/Blob storage. *Rationale: Files must be cached temporarily for processing and securely wiped post-mutation.*

**System Component Boundaries:**

```text
                     TRUST BOUNDARY (External vs. Internal)
=====================================================================================
[External Storage]      |                               |       [Downstream Systems]
(Box, SharePoint)       |                               |         (CRM, CrewAI)
      |                 |                               |               ^
   1. Webhook           |                               |            6. Egress
      v                 |                               |               |
+------------+          |  +-------------------------+  |        +-------------+
|  Ingress   |--2. Event-->| Kafka (mna.ingress.v1)  |--|------->|   Egress    |
|  Gateway   |          |  +-------------------------+  |        |   Gateway   |
+------------+          |             |                 |        +-------------+
      ^                 |             v 3. Job          |               ^
      |                 |  +-------------------------+  |               | 5. Event
      |                 |  |   AI Document Engine    |  |               |
      |                 |  |  (OCR + VLM + FinOps)   |  |               |
      |                 |  +-------------------------+  |               |
      |                 |             |                 |  +-------------------------+
      |                 |             v 4. Job          |  | Kafka (mna.egress.v1)   |
      |                 |  +-------------------------+  |  +-------------------------+
   7. Mutate API        |  | Storage Mutation & Sync |  |               ^
      +--------------------|      (Rename/Move)      |--|---------------+
                        |  +-------------------------+  |
=====================================================================================
```

**Data Flow Definitions:**
*   **Happy Path:** File uploaded -> Webhook intercepted -> Passed Idempotency/Auth -> Queued to Kafka -> AI downloads file -> VLM classifies & extracts JSON -> Mutation worker generates standard name -> External API renames file (ETag matches) -> Egress sends structured JSON via HMAC webhook -> CrewAI agent sends Slack "High Five".
*   **Nil/Empty Path:** User creates an empty folder or 0-byte file -> Webhook triggers -> Ingress Gateway detects 0 bytes -> Status `DROPPED` -> 202 Accepted returned to provider. No downstream processing.
*   **Error Path (Corrupted/Password):** File uploaded -> Webhook accepted -> AI Engine attempts download/OCR -> Fails due to password -> Engine transitions to `FAILED` -> Triggers Storage Mutation -> Mutation moves file to `_Needs_Human_Eyes` folder & writes `[filename]_Needs_Password.txt` -> Egress notifies downstream of failure.

---

## 2. Component Breakdown
The system is divided into four highly decoupled, horizontally scalable domain services. State is maintained strictly within PostgreSQL, utilizing explicit state machines to prevent invalid transitions (e.g., re-processing a completed job).

### Technical Deep-Dive

#### A. Ingress Gateway
*   **Purpose:** Front door for provider webhooks. Validates HMAC signatures, enforces tenant RPM limits, normalizes payloads, and runs the "Anomaly Watchdog" AI to prevent processing junk dumps (e.g., `node_modules/`).
*   **Dependencies:** Redis (Rate Limiting/Sliding Window), PostgreSQL, Kafka.
*   **IngressEvent State Machine:**
```text
           [RECEIVED]
               | (Validation)
               v
          [NORMALIZED]
           /    |    \
 (Invalid)v     v     v (Burst/Junk detected)
    [DROPPED] [QUEUED] [QUARANTINED] -> (Admin Override) -> [QUEUED]
```

#### B. AI Document Processing Engine
*   **Purpose:** Pulls normalized events from Kafka. Downloads the file into ephemeral storage. Uses OCR / VLM to extract classification, specific metadata, and detect PII. Calculates FinOps (LLM tokens).
*   **Dependencies:** S3 (Ephemeral Storage), External LLM APIs (OpenAI/Anthropic), OCR Service.
*   **DocumentProcessingJob State Machine:**
```text
          [QUEUED]
             |
        [DOWNLOADING]
             |
         [PROCESSING]
         /     |    \
   (Error)     |     (Low Confidence / < 0.85)
      v        v        v
  [FAILED] [COMPLETED] [REQUIRES_REVIEW]
                       / (Human overrides)
                      v
                 [COMPLETED]
```

#### C. Storage Mutation & Sync Service
*   **Purpose:** Executes the "Invisible" part of the product. Generates standard nomenclature using an LLM agent, executes the rename operation in the source storage using Optimistic Concurrency (ETags), and creates Redacted clones if PII was flagged.
*   **Dependencies:** External Storage APIs (Box/SharePoint), LLM APIs.
*   **StorageMutationOperation State Machine:**
```text
          [PENDING]
             |
        [EXECUTING]
        /    |    \
(4xx/5xx)    |    (412 ETag Mismatch)
     v       v       v
 [FAILED] [VERIFIED] [REVERTED]
```

#### D. Structured Data Egress API
*   **Purpose:** Pushes completed deal metadata to downstream systems via signed webhooks. Utilizes an AI summarization agent to append a 2-sentence executive summary. Includes a Dead Letter Queue (DLQ).
*   **Dependencies:** Kafka, Target URL endpoints.
*   **EgressDeliveryLog State Machine:**
```text
          [PENDING]
             |
        [DELIVERING] <----------+
        /    |     \            |
(2xx)  v     v      v (Timeout) |
[DELIVERED] [RETRYING] ---------+
             |
             v (Max attempts)
       [DEAD_LETTER]
```

---

## 3. Implementation Phases
The project will be built in four chronological phases. This progressive layering ensures infrastructure is verified before expensive cognitive abstractions are introduced.

### Technical Deep-Dive

#### Epic 1: Foundation & Ingress (Weeks 1-3)
Establish the architecture, database schemas, Kafka topics, and the Ingress Gateway.
*   **Story 1.1 [M]:** Provision PostgreSQL, Redis, Kafka, and baseline FastAPI structure.
*   **Story 1.2 [L]:** Implement `StorageIntegration` CRUD APIs and credential vault storage.
*   **Story 1.3 [L]:** Build Webhook Ingress endpoints (Box/Google Drive), validating HMAC signatures.
*   **Story 1.4 [M]:** Implement Redis sliding-window rate limiting (tenant RPM) and Idempotency key checks.
*   **Story 1.5 [S]:** Build `IngressEvent` state machine and Kafka publisher (`mna.ingress.events.v1`).

#### Epic 2: Cognitive Engine & FinOps (Weeks 4-7)
Build the AI Processing Engine, OCR pipelines, and strict metadata extraction schemas.
*   **Story 2.1 [M]:** Build Kafka consumer worker and ephemeral file download/cleanup mechanics.
*   **Story 2.2 [L]:** Integrate VLM/LLM provider. Construct the prompt chain for 5 standard M&A taxonomies.
*   **Story 2.3 [L]:** Implement JSON Schema strict output parsing and auto-retry prompt correction loop.
*   **Story 2.4 [M]:** Implement PII detection logic and `contains_pii` boolean flag.
*   **Story 2.5 [S]:** Implement token logging and FinOps attribution per `deal_id`.
*   **Story 2.6 [M]:** Build Human-in-the-Loop review API for `REQUIRES_REVIEW` states.

#### Epic 3: Storage Mutation & Egress (Weeks 8-10)
Close the loop by modifying the source storage and alerting downstream consumers.
*   **Story 3.1 [M]:** Build Nomenclature Generation Agent (Fast LLM, regex sanitation).
*   **Story 3.2 [XL]:** Implement Storage Mutation worker with Optimistic Concurrency Control (If-Match ETags).
*   **Story 3.3 [L]:** Build the Egress webhooks system with HMAC payload signing and key rotation.
*   **Story 3.4 [M]:** Implement Exponential Backoff Retry and Dead Letter Queue (DLQ) for Egress deliveries.

#### Epic 4: "Invisible Quarterback" Polish (Weeks 11-12)
Implement the high-impact delight features outlined in the Executive Summary.
*   **Story 4.1 [M]:** `_Needs_Human_Eyes` folder logic: Automatically move `FAILED` processing jobs and write `.txt` explanation.
*   **Story 4.2 [L]:** Auto-Redaction clone logic: If `contains_pii` is true, generate `[filename]_REDACTED.pdf` during mutation.
*   **Story 4.3 [M]:** Build Egress Context Summarizer Agent (append 2-sentence summary to egress payload).
*   **Story 4.4 [M]:** Implement CrewAI integration layer for Slack "Momentum High-Fives" based on egress events.

---

## 4. Data Model
The database is designed around event sourcing principles, utilizing PostgreSQL as the source of truth. Each component manages its own specific table, tied together primarily via `event_id` and `job_id` foreign keys.

### Technical Deep-Dive

**Entity Relationship Overview:**
*   `StorageIntegration` (1) : (N) `IngressEvent`
*   `IngressEvent` (1) : (1) `DocumentProcessingJob`
*   `DocumentProcessingJob` (1) : (1) `StorageMutationOperation`
*   `StorageMutationOperation` (1) : (N) `EgressDeliveryLog`

**Key Schema Definitions:**

```sql
-- Core Integrations
CREATE TABLE storage_integrations (
    integration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL,
    provider VARCHAR(50) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    rate_limit_rpm INT DEFAULT 600,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ingress Events
CREATE TABLE ingress_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID REFERENCES storage_integrations(integration_id),
    idempotency_key VARCHAR(255) NOT NULL,
    file_name VARCHAR(1024) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    status VARCHAR(50) DEFAULT 'RECEIVED',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_ingress_idempotency ON ingress_events(integration_id, idempotency_key);

-- Processing Jobs (JSONB utilized for flexible schema extraction)
CREATE TABLE document_processing_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID UNIQUE REFERENCES ingress_events(event_id),
    ai_classification VARCHAR(100),
    ai_confidence NUMERIC(3, 2),
    contains_pii BOOLEAN DEFAULT false,
    extracted_metadata JSONB DEFAULT '{}',
    llm_prompt_tokens INT DEFAULT 0,
    llm_completion_tokens INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'QUEUED',
    error_log TEXT,
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_doc_status_confidence ON document_processing_jobs(status, ai_confidence);

-- Mutations
CREATE TABLE storage_mutation_operations (
    mutation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID UNIQUE REFERENCES document_processing_jobs(job_id),
    original_file_id VARCHAR(255) NOT NULL,
    provider_etag VARCHAR(255) NOT NULL,
    target_file_name VARCHAR(1024) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    mutation_audit_log JSONB DEFAULT '[]'
);
```
**Migration Strategy:** Alembic (Python) will manage schema changes. Tables must be append-only or use non-destructive column additions to support zero-downtime blue/green deployments.

---

## 5. Error Handling & Failure Modes
In a headless, highly-integrated distributed system, partial failures are the norm. We rely heavily on explicit timeouts, DLQs, and Optimistic Concurrency Control to ensure data is never corrupted or silently dropped.

### Technical Deep-Dive

**Component-Specific Failure Matrix:**

| Component | Failure Mode | Mitigation Strategy | Severity |
| :--- | :--- | :--- | :--- |
| **Ingress Gateway** | Client bot uploads 5,000 files in 1 minute. | Redis sliding-window rejects at RPM limit (HTTP 429). AI Anomaly Watchdog flags burst as `QUARANTINED` to save LLM costs. | Minor |
| **AI Processing** | LLM Hallucinates invalid JSON structure. | Worker uses `instructor` or constrained generation. Fails validation -> Triggers auto-correction prompt (max 2 retries) -> `REQUIRES_REVIEW`. | Major |
| **AI Processing** | File is heavily encrypted or corrupted. | Catch generic OCR/Read exception. Log error. Transition to `FAILED`. Trigger mutation to `_Needs_Human_Eyes` folder. | Minor |
| **Mutation Sync** | ETag collision (User renames file while AI processes). | API returns HTTP 412. Operation transitions to `REVERTED`. Abort auto-rename so user changes are respected. | Major |
| **Mutation Sync** | Target storage provider API goes down. | Exponential backoff (Retry 3x). If terminal, move to `FAILED` state and flag Admin console. | Critical |
| **Egress Gateway** | Downstream CRM server is offline (HTTP 503). | Worker catches 5xx, transitions to `RETRYING`. Max 5 attempts (1m, 5m, 15m, 1h, 6h). Falls to `DEAD_LETTER`. | Major |

**Circuit Breakers:** Implemented around external LLM APIs and Storage Provider APIs. If >50% of requests to Box fail within 30 seconds, the circuit opens, halting Kafka consumers to prevent queue churning, automatically retrying after 60 seconds.

---

## 6. Test Strategy
Testing will focus heavily on validating state transitions, mocking external vendor APIs, and ensuring strict JSON schema adherence. Manual testing is insufficient for distributed async architectures.

### Technical Deep-Dive

*   **Unit Tests (60%):**
    *   State Machine validity (e.g., Asserting `FAILED -> PROCESSING` throws an exception).
    *   Nomenclature AI regex sanitization (e.g., stripping `<>:/\|?*`).
    *   HMAC Signature validation algorithms.
*   **Integration Tests (30%):**
    *   Kafka publisher/consumer pipeline (using `Testcontainers` for ephemeral Kafka/Postgres).
    *   API contract tests for webhook ingress (testing boundary parsing).
    *   VCR Cassettes for LLM calls: Record and replay OpenAI/Anthropic responses to test JSON parsing without incurring API costs or latency during CI runs.
*   **End-to-End (E2E) Tests (10%):**
    *   "Mock Box" environment. Simulating a file upload, passing it entirely through the pipeline, and verifying the egress webhook is received by a dummy endpoint.
*   **Load & Performance Testing:**
    *   Locust script simulating 10,000 webhook events/minute to validate Redis rate limiter performance and Kafka partitioning logic.

---

## 7. Security & Trust Boundaries
This system processes highly sensitive, strictly confidential Mergers & Acquisitions data. Trust boundaries between tenants, external storage, and downstream brokers must be hermetically sealed.

### Technical Deep-Dive

**Attack Vectors & Mitigations:**
1.  **Webhook Spoofing:** Malicious actors sending fake `file.uploaded` events.
    *   *Mitigation:* All ingress must pass HMAC-SHA256 signature validation against the configured `auth_credentials`. Unsigned or invalid requests return `401 Unauthorized`.
2.  **Directory Traversal via File Name:** Uploading a file named `../../../etc/passwd`.
    *   *Mitigation:* AI Nomenclature regex rigorously strips file paths. Files are stored in flat ephemeral buckets keyed exclusively by UUID (`s3://temp-ocr/{event_id}.ext`), entirely divorced from user-provided file names.
3.  **Cross-Tenant Data Bleed:** Kafka workers accidentally mutating a file in Deal A using credentials from Deal B.
    *   *Mitigation:* Kafka messages are partitioned by `deal_id`. Storage connection factories utilize strict context-managers that scope provider tokens specifically to the `integration_id` fetched directly inside the worker loop.
4.  **PII / Data Retention:** Sensitive Cap Tables left in the database.
    *   *Mitigation:* Ephemeral OCR text (`extracted_text_ref`) and S3 caches are hard-deleted upon job completion. The database only retains the `extracted_metadata` JSON, which is schema-constrained to prevent capturing raw text blocks.

---

## 8. Deployment & Rollout
Deployments must guarantee zero-downtime and zero dropped webhooks. We will utilize a Blue/Green deployment strategy combined with Kafka consumer pausing during migrations.

### Technical Deep-Dive

**Deployment Sequence:**
1.  **Phase 1: DB Migrations.** Alembic runs against the database. Backwards-incompatible schema changes are banned; all additions must be nullable or have defaults.
2.  **Phase 2: Blue/Green Spin Up.** New instances of Webhook Ingress and Worker nodes spin up (Green).
3.  **Phase 3: Traffic Switch.** Load balancer cuts over webhook traffic to Green ingress nodes.
4.  **Phase 4: Consumer Drain.** Blue worker nodes finish processing their current Kafka messages. Once queue is drained, Blue nodes are destroyed.

**Rollback Plan:**
If error rates spike >2% on Green nodes:
1.  Revert Load Balancer traffic back to Blue Ingress.
2.  Halt Green Kafka consumers.
3.  Do *not* rollback DB schema (to avoid data loss on newly written columns).
4.  Investigate logs; patch and re-deploy.

**Feature Flags:** Egress APIs and Mutate APIs will be gated by LaunchDarkly feature flags (`deal_id` specific) to allow internal "dogfooding" on test deals before rolling out to client M&A environments.

---

## 9. Observability
Because the application is "invisible" to the end user (no UI dashboard), observability is the only way we know if the product is functioning. Logs must be highly structured and traceable across microservices.

### Technical Deep-Dive

*   **Distributed Tracing:** 
    *   OpenTelemetry will inject an `x-correlation-id` at the Ingress Gateway.
    *   This ID is passed through Kafka headers, into the AI worker, to the external Storage Mutation request, and finally out to the Egress payload. This allows querying a single UUID in Datadog to see the entire lifecycle of one file.
*   **Structured Logging (JSON):**
    *   All logs output as JSON containing: `timestamp`, `level`, `correlation_id`, `deal_id`, `component`, `message`.
*   **Metrics & Alerts (Prometheus/Grafana):**
    *   *SLI 1:* Ingress Webhook 5xx Error Rate (Alert if > 1% over 5m).
    *   *SLI 2:* Processing Latency (Alert if Time-in-Queue > 5 minutes).
    *   *SLI 3:* AI Confidence Scores (Alert if daily average confidence drops below 85% — indicates prompt drift).
    *   *FinOps:* Sum of `llm_prompt_tokens` grouped by `deal_id` exported daily to billing systems.
*   **Debugging Guide:**
    *   *Symptom:* Missing files downstream.
    *   *Action:* Query logs for `file_name`. Check `ingress_events` for `status = DROPPED` (usually invalid extension or idempotency lock). Check `document_processing_jobs` for `status = FAILED` (usually password protection). Check `mutation_operations` for `status = REVERTED` (ETag concurrency conflict).

## Problem Statement

The transition from running a company to selling a company introduces a massive, momentum-killing administrative tax. Due diligence requires meticulously structured data, yet human operators—specifically sell-side founders and CFOs—naturally produce unstructured, chaotic data (e.g., `Scan_0045_Final_v2.pdf`). The industry's current approach is to force these executives to migrate their workflows into standalone Document Ingestion Gateways or legacy Virtual Data Rooms (VDRs). This fundamentally flawed model assumes busy executives have the bandwidth and willingness to learn proprietary interfaces, manage new login credentials, and manually categorize hundreds of complex documents. In reality, they do not.

This forced behavior change creates severe "tool fatigue" and overwhelming adoption friction. Rather than meticulously organizing files within a new portal, overwhelmed founders frequently resort to shadow IT—emailing highly sensitive zip files or dumping chaotic folders into local drives just to bypass the VDR entirely. Consequently, M&A advisors are forced to step in as overpaid file clerks. Current operational data indicates that advisors burn upwards of 40% of their highly billable bandwidth chasing clients for missing documents, manually renaming files to meet strict Wall Street M&A taxonomy standards, and fixing broken metadata. 

The cascading business impact of this friction is severe and measurable:
* **Stalled Deal Momentum:** Time kills all M&A deals. The administrative bottleneck of manual ingestion extends the time from a raw file's creation to its availability as usable, structured data to an industry average of 48 hours. 
* **Silent Failures & Security Risks:** Manual data handling introduces blind spots. Corrupted files, password-protected PDFs, or missing pages often go unnoticed until a buyer requests them, halting diligence without clear, actionable alerts. Furthermore, bypassing secure portals via email introduces significant data compliance vulnerabilities.
* **Starving Downstream AI:** Our advanced downstream automation (e.g., the `crewAI` agentic qualification workflows) absolutely requires deterministic, high-quality, normalized JSON metadata to function. When the top of the funnel is polluted with unstructured, manually entered garbage, the entire automated diligence ecosystem breaks down.

We cannot solve this ingestion crisis by building a marginally better UI or a new portal. As M&A timelines compress and our reliance on downstream AI orchestration grows, the friction of manual document ingestion has become an existential blocker to scaling deal capacity. There is an immediate, critical need to completely eliminate the concept of "uploading to a portal" and intercept diligence documents seamlessly at the source—where users already naturally work—to instantly bridge the gap between human messiness and AI precision.

## User Personas

### 1. Sarah — The Sell-Side CFO (Primary Data Provider)
**Profile:** CFO or Founder of a mid-market company undergoing due diligence for acquisition. Highly competent, fiercely protective of her time, and under immense pressure to maintain day-to-day business operations while managing the deal.
*   **Current Pain Points:** Despises the administrative "tax" of M&A. She does not know Wall Street naming conventions, routinely forgets VDR passwords, and resents the advisor constantly nagging her for updated files. She currently dumps poorly named files (`Financials_vFinal_v2.xlsx`) into a messy ZIP file just to get them off her desk.
*   **Goals & Outcomes:** Wants to fulfill diligence requests as quickly as possible without altering her daily workflows. She wants confirmation that her files were received without having to log into a separate portal to check.
*   **Interaction Model (Passive / Invisible):** Sarah never logs into our software. Her only interaction is dragging and dropping unformatted files into a standard `Company/Legal_Diligence` folder within her existing Google Drive, Box, or SharePoint environment. She receives asynchronous validation (a "Momentum High-Five") and missing-file prompts via direct Slack messages or email. 

### 2. David — The M&A Advisor (The Deal Manager)
**Profile:** Managing Director or Senior Associate at an investment bank or advisory firm. Responsible for orchestrating the deal, structuring the data room for buyers, and keeping the sell-side client motivated. 
*   **Current Pain Points:** Burns up to 40% of his billable hours acting as an overpaid file clerk. He spends late nights downloading Sarah's messy ZIP files, painstakingly renaming them to standard M&A taxonomy, checking for missing pages, and manually re-uploading them to the VDR. If downstream AI is used, he has to manually tag the metadata.
*   **Goals & Outcomes:** Wants a perfectly structured, categorized, and taxonomy-compliant document repository ready for buyer presentation immediately. He wants to eliminate the friction of nagging his clients, protecting their relationship.
*   **Interaction Model (Passive / Consumptive):** David also bypasses manual ingestion. He opens the shared cloud folder and instantly sees cleanly structured, renamed files alongside an auto-generated, living `00_Diligence_Progress.pdf` checklist. He relies on the system to automatically move password-protected or corrupted files into a `_Needs_Human_Eyes` folder, turning silent failures into an actionable, localized task list.

### 3. Marcus — The IT / Security Administrator (The Enabler)
**Profile:** Head of IT or Security at either the advisory firm or the sell-side company. Highly paranoid about shadow IT, data leakage, and unauthorized access to sensitive M&A documents (e.g., Cap Tables).
*   **Current Pain Points:** Dislikes bespoke SaaS portals because they require separate security reviews, duplicate RBAC (Role-Based Access Control) configuration, and introduce new attack vectors. He constantly battles employees who bypass secure VDRs via email because the VDRs are too difficult to use.
*   **Goals & Outcomes:** Wants to leverage existing, heavily vetted enterprise security infrastructure. Requires strict data retention policies, audit logs, and SOC 2 Type II compliance.
*   **Interaction Model (Active / Configuration):** Marcus interacts with the Headless API once during the initial deal setup phase. He authenticates the OAuth 2.0 connection, approves the webhook payloads for the designated shared folder, and defines the automated data retention/deletion rules.

### 4. Downstream Systems — The AI Agents & CRMs (The Consumers)
**Profile:** Non-human actors; specifically, the `crewAI` agentic qualification workflows and deal management CRMs that drive the next phase of the M&A lifecycle.
*   **Current Pain Points:** Starved of clean data. Without perfectly structured JSON metadata, the AI cannot accurately assess deal readiness or trigger automated buyer matching.
*   **Goals & Outcomes:** Requires deterministic, schema-validated metadata (e.g., `DocumentType`, `TransactionPhase`, `Counterparty`, `ConfidenceScore`, and `Entities`) pushed reliably within milliseconds of file classification. 
*   **Interaction Model (System-to-System):** Receives signed, secure webhook POST requests from the Headless API's Egress Gateway containing structured JSON payloads and AI confidence scores.

## Functional Requirements

### 1. Initial Configuration & Deal Setup

**FR-001: M&A Advisor Deal Linkage Configuration**
*   **Priority:** SHALL
*   **Description:** The system must provide an internal configuration API that allows an authorized M&A Advisor or IT Administrator to link an external storage webhook integration to a specific `deal_id`.
*   **Acceptance Criteria:**
    *   **Given** an authorized user possesses a valid internal JWT,
    *   **When** they send a POST request mapping a `provider` and `tenant_id` to a `deal_id`,
    *   **Then** the system creates a record in the `storage_integrations` table and returns an `integration_id`.

**FR-002: Integration Deactivation & Data Purge**
*   **Priority:** SHALL
*   **Description:** The system must support the deactivation of a storage integration upon deal completion, resulting in the cessation of webhook processing and the secure hard-deletion of all associated ephemeral data and cached metadata.
*   **Acceptance Criteria:**
    *   **Given** an authorized user issues a DELETE request to the configuration API for an `integration_id`,
    *   **When** the system receives the request,
    *   **Then** it updates the integration status to `INACTIVE`, rejects all subsequent webhooks with HTTP 403, and immediately triggers an asynchronous hard-delete of all associated `document_processing_jobs` records and S3 cache objects.

### 2. Ingress Gateway & Provider Integration

**FR-003: Webhook Ingress Reception & Tenant Resolution**
*   **Priority:** SHALL
*   **Description:** The system receives `file.uploaded` and `file.updated` webhooks. It validates the payload signature using the stored HMAC credential, resolving the `tenant_id` and `deal_id` by executing a database lookup against the `storage_integrations` table using the `{integration_id}` provided in the path parameter.
*   **Acceptance Criteria:**
    *   **Given** a webhook payload is received at `/api/v1/ingress/webhook/{provider}/{integration_id}`,
    *   **When** the Gateway successfully queries the database using the `{integration_id}` and validates the HMAC signature,
    *   **Then** the system returns a HTTP 202 Accepted and transitions the `IngressEvent` state to `NORMALIZED`.

**FR-004: Idempotency & Duplicate Rejection**
*   **Priority:** SHALL
*   **Description:** The system prevents processing duplicate webhook events utilizing the provider's unique event ID.
*   **Acceptance Criteria:**
    *   **Given** a webhook event is received,
    *   **When** the event ID matches an `idempotency_key` already present in the `ingress_events` table for that `integration_id`,
    *   **Then** the system returns a HTTP 202 Accepted to the provider (acknowledging receipt) but transitions the new event to `DROPPED` without queuing a downstream job.

**FR-005: File Update / Versioning Handling**
*   **Priority:** SHALL
*   **Description:** The system must fully re-process files if a user uploads a new version of an already processed document, ensuring downstream metadata reflects the latest content.
*   **Acceptance Criteria:**
    *   **Given** a `file.updated` webhook is received for an existing `original_file_id`,
    *   **When** the event is normalized,
    *   **Then** the system queues a new `DocumentProcessingJob`. Upon completion, the Mutation Sync increments the target filename version integer (e.g., from `_v1.pdf` to `_v2.pdf`).

**FR-006: External API Resilience (Rate Limits & Server Errors)**
*   **Priority:** SHALL
*   **Description:** The system must gracefully handle transient failures and rate limits (`429 Too Many Requests`, `5xx` Server Errors) when interacting with external APIs (Box, SharePoint, Anthropic/OpenAI) using exponential backoff.
*   **Acceptance Criteria:**
    *   **Given** a worker attempts an external API call,
    *   **When** the provider returns a 429 or 5xx HTTP status code,
    *   **Then** the worker does not fail the job immediately; instead, it pauses the specific Kafka partition for that `deal_id` and schedules a retry using an exponential backoff algorithm (e.g., 1s, 2s, 4s, up to a max of 5 attempts). If all attempts fail, the job transitions to `FAILED`.

### 3. AI Document Processing Engine

**FR-007: File Download, Timeouts, & Ephemeral Caching**
*   **Priority:** SHALL
*   **Description:** The worker node downloads the physical file to ephemeral S3 storage. To protect system resources from excessively large or complex files, a strict processing timeout must be enforced.
*   **Acceptance Criteria:**
    *   **Given** a `DocumentProcessingJob` is `PROCESSING`,
    *   **When** the combined file download and VLM extraction time exceeds 300 seconds,
    *   **Then** the system abruptly terminates the worker thread, logs a "ERR_TIMEOUT_EXCEEDED", and transitions the job to `FAILED`.

**FR-008: Ephemeral Storage Cleanup**
*   **Priority:** SHALL
*   **Description:** The system must strictly enforce data privacy by deleting raw document files from the ephemeral S3 cache immediately upon job completion or terminal failure.
*   **Acceptance Criteria:**
    *   **Given** a `DocumentProcessingJob` transitions to `COMPLETED` or `FAILED`,
    *   **When** the terminal state is committed to PostgreSQL,
    *   **Then** the system immediately issues a hard-delete command to S3 for `s3://temp-ocr/{event_id}.ext`.

**FR-009: AI Metadata Extraction & Strict JSON Output**
*   **Priority:** SHALL
*   **Description:** The system executes OCR and passes the text to a VLM strictly configured to return an exact, predefined JSON schema. All dates must be normalized to ISO-8601 `YYYY-MM-DD`.
*   **Acceptance Criteria:**
    *   **Given** the file text is successfully extracted,
    *   **When** the VLM returns the payload,
    *   **Then** the `extracted_metadata` JSONB column must strictly conform to the following schema contract:
      ```json
      {
        "DocumentCategory": "enum(Financial, Legal, HR, Commercial, Technology, Unknown)",
        "TransactionPhase": "enum(1_Preparation, 2_Marketing, 3_Diligence, 4_Closing)",
        "DocumentType": "string",
        "CounterpartyEntity": "string | null",
        "EffectiveDate_ISO8601": "string(YYYY-MM-DD) | null",
        "IsExecuted": "boolean",
        "ConfidenceScore": "number(0.00-1.00)"
      }
      ```

**FR-010: FinOps Token Tracking & Alerting**
*   **Priority:** SHALL
*   **Description:** The system captures LLM token usage for billing and triggers an internal alert if a single deal exceeds a predefined usage threshold.
*   **Acceptance Criteria:**
    *   **Given** a VLM classification call completes,
    *   **When** the provider API returns the token usage,
    *   **Then** the system records `llm_prompt_tokens` and `llm_completion_tokens`. If the aggregate token sum for the `deal_id` exceeds 5,000,000 tokens within a 30-day window, the system dispatches a warning event to the internal monitoring queue.

### 4. Storage Mutation & Sync Service

**FR-011: Nomenclature Generation & Versioning logic**
*   **Priority:** SHALL
*   **Description:** The system utilizes the extracted metadata to generate a target filename strictly adhering to Wall Street M&A taxonomy. Initial ingestion defaults to `v1`.
*   **Acceptance Criteria:**
    *   **Given** a `DocumentProcessingJob` transitions to `COMPLETED`,
    *   **When** the Storage Mutation Service executes,
    *   **Then** it generates `target_file_name` matching the regex: `^(Phase[1-4])_(Financial|Legal|HR|Commercial|Technology|Unknown)_([a-zA-Z0-9\-]+_)?(\d{4}-\d{2}-\d{2}_)?v([1-9][0-9]*)\.[a-zA-Z0-9]+$`. All illegal path characters (`<>:"/\|?*`) are stripped.

**FR-012: In-Place File Renaming (Optimistic Concurrency)**
*   **Priority:** SHALL
*   **Description:** The system renames the file directly within the external storage provider using the native API, providing the `provider_etag` to ensure the file has not been manually altered since ingestion.
*   **Acceptance Criteria:**
    *   **Given** a valid `target_file_name` and matching `provider_etag`,
    *   **When** the API rename request is successful,
    *   **Then** the system transitions the `StorageMutationOperation` to `VERIFIED` and logs the new file ID.

**FR-013: Precise PII Detection & Auto-Redacted Clone Generation**
*   **Priority:** SHALL
*   **Description:** The system must detect highly sensitive PII during classification via strict heuristics/regex and automatically generate a visually masked clone.
*   **Acceptance Criteria:**
    *   **Given** the VLM processing detects data matching predefined strict heuristics (e.g., Regex for US Social Security Numbers `\b\d{3}-\d{2}-\d{4}\b`, explicit keywords like "base salary," "stock option grant," or "cap table ownership %"),
    *   **When** the original file is renamed,
    *   **Then** the system generates a flattened PDF with a visual black-box mask over the exact text coordinates of the detected PII, saves the clone as `[target_file_name]_REDACTED.pdf`, and uploads it alongside the original.

**FR-014: Human-Eyes Quarantine Routing**
*   **Priority:** SHALL
*   **Description:** If AI processing fails (e.g., password protection, timeout, OCR failure), the system moves the source file out of the main directory and into a dedicated review folder without leaking sensitive metadata.
*   **Acceptance Criteria:**
    *   **Given** a `DocumentProcessingJob` transitions to `FAILED`,
    *   **When** the Storage Mutation Service executes,
    *   **Then** it moves the file to the `_Needs_Human_Eyes` sub-folder and writes a localized file named `[original_file_name]_Error.txt` containing only the timestamp and the generic system error code (e.g., `ERR_PASSWORD_REQUIRED`, `ERR_TIMEOUT_EXCEEDED`), explicitly omitting any file content.

### 5. Structured Data Egress & "Delight" Features

**FR-015: Egress Webhook Dispatch**
*   **Priority:** SHALL
*   **Description:** Upon successful mutation, the system POSTs the structured `extracted_metadata` JSON payload to the configured downstream system.
*   **Acceptance Criteria:**
    *   **Given** the `StorageMutationOperation` is `VERIFIED`,
    *   **When** the Egress Gateway dispatches the payload,
    *   **Then** the payload includes an HMAC-SHA256 signature in the headers and requires a 2xx HTTP response from the downstream target to transition to `DELIVERED`.

**FR-016: Living "Readme" Checklist Generation**
*   **Priority:** SHOULD
*   **Description:** The system generates and continuously overwrites a visual checklist file in the root of the user's shared folder indicating diligence progress.
*   **Acceptance Criteria:**
    *   **Given** an egress payload is successfully delivered,
    *   **When** the system detects a state change indicating a required document category (e.g., "Financial") has transitioned from "Missing" to "Present",
    *   **Then** it immediately triggers a regeneration of the `00_Diligence_Progress.pdf` file, overwriting the previous version in the provider's root directory.

### 6. Internal API Endpoint Contracts

**FR-017: Manual Review & Quarantine Re-processing Endpoint**
*   **Priority:** SHALL
*   **Method:** `POST`
*   **Path:** `/api/v1/jobs/{job_id}/override`
*   **Description:** Allows an authorized M&A Advisor to manually correct AI misclassifications or instruct the system to re-process a file that was previously sent to quarantine.
*   **Request Schema (Headers):** `Authorization: Bearer <Internal_JWT>`
*   **Request Schema (Body):** 
```json
{
  "action": "enum(OVERRIDE_METADATA, REPROCESS_QUARANTINED)",
  "override_metadata": { 
    "DocumentCategory": "string", 
    "TransactionPhase": "string" 
  } // Only required if action is OVERRIDE_METADATA
}
```
*   **Response Schema:** `200 OK` (Returns updated `DocumentProcessingJob` object and transitions state to `PROCESSING` if action was `REPROCESS_QUARANTINED`).

## Non-Functional Requirements

### 1. Performance & Latency
*   **Ingress Processing Time:** The Ingress Gateway MUST process the webhook, validate the HMAC signature, execute the Redis rate-limit check, and successfully publish the `IngressEvent` to Kafka in `< 250ms` (p95) to ensure external provider webhooks do not time out.
*   **End-to-End Processing Velocity:** As defined in the Executive Summary, the total elapsed time from the receipt of the webhook to the delivery of the Egress JSON payload MUST be `< 5 minutes` (p95) for document batches up to 50 files, assuming individual file sizes are `< 50MB`.
*   **VLM/OCR Timeout:** Individual document processing tasks within the AI Engine MUST have a hard execution timeout of `300 seconds`. Jobs exceeding this limit MUST be terminated and gracefully routed to the `_Needs_Human_Eyes` queue.
*   **Advisor Notification Latency:** Asynchronous Slack or Email notifications generated by downstream agents (e.g., "Momentum High-Fives" or missing file alerts) MUST be delivered to the M&A Advisor within `< 60 seconds` of the triggering job transitioning to a terminal state.

### 2. Scalability & Throughput
*   **Tenant Throughput Limits:** The system MUST support configurable, sliding-window rate limits via Redis per `tenant_id`, defaulting to `600 requests per minute` (RPM) to absorb "chaotic ZIP dump" unzipping events without degrading core system performance.
*   **Daily Volume Capacity:** The architecture (Kafka partitions and horizontally scaled Python/FastAPI workers) MUST support the processing of up to `10,000 documents per day per active deal` without exceeding the 5-minute end-to-end latency target.
*   **Concurrency Handling:** The Storage Mutation Service MUST utilize Optimistic Concurrency Control (via ETags) to handle simultaneous file mutations. The system MUST successfully process a minimum of `50 concurrent file uploads` to the exact same provider folder without data corruption or lost metadata payloads.

### 3. Security, Data Privacy, & Residency
*   **Data Residency:** To comply with international M&A regulations (e.g., GDPR), all client data, database records, and ephemeral storage for deals flagged as "European" MUST reside and be processed exclusively within EU-based cloud data centers.
*   **SOC 2 Type II Compliance:** All infrastructure, data storage, and processing pipelines MUST adhere to SOC 2 Type II standards, specifically regarding Data Security and Confidentiality.
*   **Encryption Standard:** All data at rest (PostgreSQL, Ephemeral S3) MUST be encrypted using `AES-256`. All data in transit (Webhook Ingress, External API calls, Egress payloads) MUST utilize `TLS 1.3`.
*   **Ephemeral Data Retention SLA:** The raw document files downloaded to the S3 bucket for OCR/VLM processing MUST be hard-deleted within `< 5 seconds` of the `DocumentProcessingJob` transitioning to a terminal state (`COMPLETED` or `FAILED`).
*   **Webhook Payload Security:** The Egress Gateway MUST sign all outbound JSON metadata payloads utilizing an `HMAC-SHA256` signature using a securely vaulted, tenant-specific secret key to prevent spoofing of downstream systems.
*   **Data Purge on Deactivation:** Upon receiving a deactivation command for an `integration_id`, the system MUST execute a cascading hard-delete of all associated `document_processing_jobs` metadata records and S3 cache objects within `< 24 hours`.

### 4. Availability, Reliability, & Disaster Recovery
*   **Uptime SLA:** The Headless API, specifically the Ingress Gateway, MUST maintain a `99.9% uptime` SLA to prevent missing critical `file.uploaded` events from external storage providers.
*   **Zero-Downtime Deployments:** The system MUST support blue/green deployments. Database schema migrations (via Alembic) MUST be backward-compatible and non-blocking. Deployments MUST ensure no more than `0.01%` of webhooks are dropped during the deployment window.
*   **Disaster Recovery (RPO/RTO):** In the event of a catastrophic regional failure or database corruption, the system MUST support a Recovery Point Objective (RPO) of `< 1 hour` (maximum data loss) and a Recovery Time Objective (RTO) of `< 4 hours` (system fully restored and processing queued Kafka messages).
*   **External API Fault Tolerance:** The system MUST NOT drop data due to external provider (Box, SharePoint, LLM) outages. As detailed in the Functional Requirements, failures MUST trigger a Kafka partition pause and exponential backoff retry mechanism. Unrecoverable events that exhaust all retries MUST be gracefully routed to a Dead Letter Queue (DLQ) for engineering review.

### 5. Observability, Maintainability, & Auditability
*   **Distributed Tracing:** Every webhook event MUST be assigned an `x-correlation-id` at the Ingress Gateway. This ID MUST be propagated through Kafka headers, the Postgres DB logs, and included in the final Egress webhook payload to allow end-to-end tracing of a specific file's lifecycle.
*   **Immutable Audit Logs:** 100% of state transitions (e.g., `QUEUED` -> `PROCESSING` -> `COMPLETED`) and storage mutations (e.g., file renamed from X to Y) MUST be logged immutably in the PostgreSQL database with a timestamp and the associated `correlation_id`.
*   **Maintainability Standards:** All internal API endpoints MUST conform to OpenAPI v3.0 standards. All application logs MUST be structured as JSON to facilitate automated parsing by centralized log aggregation tools (e.g., Datadog, ELK).
*   **Zero Silent Failures & Alerting Priority:** All unhandled exceptions or VLM processing failures MUST be explicitly caught and logged. Critical system failures (e.g., Kafka cluster down, Database unreachable) MUST trigger immediate `P1` alerts to the L1 Operations/On-Call team via PagerDuty.

### 6. FinOps & Cost Constraints
*   **Anomaly Watchdog:** The system MUST run a pre-processing anomaly check at the Ingress Gateway to identify and quarantine non-document junk data (e.g., `node_modules/`, `.git/` directories) to prevent incurring unnecessary, high-volume LLM API costs.
*   **Token Threshold Alerts:** The system MUST calculate and record `llm_prompt_tokens` and `llm_completion_tokens` for every VLM request. The system MUST trigger an internal warning alert if the aggregate token usage for a single `deal_id` exceeds `5,000,000` tokens within a rolling 30-day window.

## Edge Cases

### 1. File & Storage Concurrency

*   **Target Nomenclature Collision (Exact Name Exists):**
    *   *Scenario:* The AI finishes processing and attempts to rename `Scan_01.pdf` to `Phase1_Financials_v1.pdf`. However, a file with that exact name already exists in the target folder due to a previous run or user action.
    *   *System Behavior:* The Storage Mutation Service catches the 409/412 error from the provider API. It auto-increments the version suffix (e.g., `_v2.pdf`) and retries up to 5 times. If it fails on the 5th attempt, the job transitions to `FAILED` and the original file is routed to the `_Needs_Human_Eyes` folder with an `ERR_RENAME_COLLISION.txt` note.
*   **"Phantom Files" (Deleted During Processing):**
    *   *Scenario:* A user uploads a file, triggering the webhook, but deletes it from the shared folder before the AI finishes downloading or classifying it.
    *   *System Behavior:* The worker node receives a 404 Not Found when attempting to download or mutate the file. The `DocumentProcessingJob` is transitioned to a `DROPPED` state (not `FAILED`, as this does not require human intervention), and no egress webhook or Slack notification is fired.
*   **Rapid Save / Active Editing Loops:**
    *   *Scenario:* A user opens an Excel file directly from the synced SharePoint folder and hits "Save" 15 times in 10 minutes, firing 15 sequential `file.updated` webhooks.
    *   *System Behavior:* The Ingress Gateway utilizes the Redis sliding-window cache to debounce rapid updates. If multiple `file.updated` webhooks for the same `original_file_id` are received within a 60-second window, the system delays processing for 60 seconds from the *last* received event. After this delay, only one Kafka job is triggered using the metadata from that final event; interim events are dropped.

### 2. User Behavior & Input

*   **Archive "Zip Bomb" Uploads:**
    *   *Scenario:* A user uploads a 50GB `.zip` file containing thousands of deeply nested folders and files, potentially overwhelming the worker node's ephemeral storage or memory.
    *   *System Behavior:* The Ingress Gateway intercepts `.zip`/`.rar` extensions. A dedicated extraction worker streams the archive, flattens the file hierarchy, drops non-document artifacts (`.exe`, `.DS_Store`), and publishes individual `file.uploaded` webhooks back to Kafka for each valid document, subject to a hard cap of 1,000 files per archive.
*   **Unprocessable File Content (Encrypted / Corrupted):**
    *   *Scenario:* A user uploads a file with a valid MIME type (e.g., PDF), but it is password-protected, DRM-locked, or deeply corrupted, preventing OCR from extracting text.
    *   *System Behavior:* If the OCR service throws an encryption or corruption exception, the file bypasses the VLM. The job transitions to `FAILED` and the file is moved to the `_Needs_Human_Eyes` folder alongside a specific error file (e.g., `ERR_PASSWORD_REQUIRED.txt`).
*   **Zero-Context Documents:**
    *   *Scenario:* A user scans a completely blank page, or a document containing only an unreadable logo, yielding zero semantic content from the OCR pipeline.
    *   *System Behavior:* If OCR returns fewer than 10 meaningful alphanumeric tokens, the VLM step is skipped to save FinOps tokens. The job transitions to `REQUIRES_REVIEW` and is routed to the `_Needs_Human_Eyes` folder.
*   **User Remediation of Quarantined Files:**
    *   *Scenario:* A user sees a file in the `_Needs_Human_Eyes` folder, removes the password protection locally, and drags the fixed file back into the main monitored folder.
    *   *System Behavior:* The system treats this re-upload as a net-new `file.uploaded` event. It processes the new file normally. The old, failed `DocumentProcessingJob` record remains in the database for audit logging, but the new processing job operates independently.

### 3. AI & Logic

*   **Conflicting PII & Redaction Boundaries:**
    *   *Scenario:* The AI identifies a document as a generic "Vendor Contract" but also detects highly sensitive PII (e.g., an SSN in an appendix).
    *   *System Behavior:* The system prioritizes strict security. If `contains_pii` is triggered, it generates the `_REDACTED.pdf` clone. Crucially, it moves the unredacted original into a system-controlled, permission-restricted `_Original_Unredacted` sub-folder. The Egress payload explicitly configures the downstream CRM to link *only* to the redacted version for standard users.
*   **VLM Hallucination on Required Fields:**
    *   *Scenario:* The LLM returns a successfully parsed JSON object, but hallucinates an enum value that violates the strict schema (e.g., `"TransactionPhase": "5_Post_Close"`).
    *   *System Behavior:* The Pydantic validation layer catches the enum violation and triggers an automatic prompt retry (max 2 attempts). If it fails on the final attempt, it transitions to `REQUIRES_REVIEW`, leaving the file un-renamed in the `_Needs_Human_Eyes` folder until an Advisor uses the Manual Override API.

### 4. System & Integration Failures

*   **External Storage Provider Access Revocation:**
    *   *Scenario:* During an active deal, the IT administrator accidentally revokes the system's OAuth token, or the specific shared folder permissions are altered, resulting in 401/403 errors when attempting to download or rename files.
    *   *System Behavior:* The worker catches the terminal authentication error, immediately halts processing for that specific `integration_id`, logs a `P1` alert, and sends an automated Slack/Email notification to the configured M&A Advisor detailing the access loss. Kafka messages for that deal remain paused until an administrator re-authenticates via the configuration API.
*   **VLM Processing Resource Exhaustion (Internal Crash):**
    *   *Scenario:* The Vision-Language Model process crashes or runs out of memory mid-extraction due to an unexpected container fault, failing to return a response or a standard timeout.
    *   *System Behavior:* A global exception handler wraps the VLM execution thread. If the process dies unexpectedly, the handler catches the fault, logs the stack trace, transitions the `DocumentProcessingJob` to `FAILED` with `ERR_INTERNAL_AI_CRASH`, and routes the file to the `_Needs_Human_Eyes` folder, ensuring the file does not remain stuck in an infinite `PROCESSING` state.
*   **Downstream System Ingestion Failure:**
    *   *Scenario:* The Egress Gateway successfully POSTs the metadata payload (receiving a 200 OK), but the downstream CRM subsequently fails to ingest the data due to its own internal validation errors or database locks.
    *   *System Behavior:* Because the Egress delivery was technically successful, the API assumes completion. To handle downstream ingestion failures, the downstream system MUST be responsible for firing an asynchronous failure alert back to the M&A Advisor via Slack/Email, as the Headless API's state machine terminates at the successful egress delivery.

## Error Handling

The Headless M&A Data Structuring API is built on the principle of "invisible intelligence," where errors are never silent but are handled gracefully and actionably, minimizing disruption for the end-user (sell-side founders/CFOs) while providing clear resolution paths for M&A advisors. The system prioritizes non-destructive operations, ensuring original files are never compromised by processing failures.

### Error Taxonomy and Categorization

Errors within the system are broadly categorized to facilitate targeted handling and recovery:

*   **Input & Content Errors (Type: `INGRESS_CONTENT_ERROR`):** Occur when the incoming file or its attributes prevent processing.
    *   *Examples:* Corrupted files, password-protected documents, zero-byte files, invalid file types (e.g., executables).
*   **Validation & Rate Limit Errors (Type: `INGRESS_VALIDATION_ERROR`):** Failures during initial ingestion, including authentication, authorization, rate limiting, or anomaly detection.
    *   *Examples:* Invalid HMAC signatures, exceeding tenant-specific requests per minute (RPM) limits, AI Anomaly Watchdog flagging a burst of junk files as `QUARANTINED`.
*   **AI Processing & Classification Errors (Type: `PROCESSING_AI_ERROR`):** Issues encountered during OCR, Vision-Language Model (VLM) classification, or metadata extraction.
    *   *Examples:* LLM hallucinating an invalid JSON structure, VLM failing to classify a document with sufficient confidence (`REQUIRES_REVIEW`), OCR failing on a heavily distorted image.
*   **Storage Integration Errors (Type: `MUTATION_API_ERROR`):** Failures when interacting with external cloud storage providers (Box, Google Drive, SharePoint).
    *   *Examples:* Storage provider API downtime (HTTP 5xx), ETag collision during a rename operation (HTTP 412), permission denied.
*   **Egress & Downstream Integration Errors (Type: `EGRESS_DELIVERY_ERROR`):** Issues during the delivery of structured metadata to downstream systems.
    *   *Examples:* Downstream CRM server offline (HTTP 503), invalid target URL, HMAC signature generation failure for egress webhook.
*   **System & Infrastructure Errors (Type: `SYSTEM_INTERNAL_ERROR`):** Core platform failures unrelated to specific file processing, but impacting overall system availability.
    *   *Examples:* Kafka broker unavailability, database connection issues, unexpected service restarts.

### Advisor-Facing Error Handling

While the system is "headless" for the end-user, M&A advisors require clear, actionable insights when human intervention is needed or when a file cannot be fully processed automatically.

*   **`_Needs_Human_Eyes` Folder:** For `INGRESS_CONTENT_ERROR` (e.g., password-protected, corrupted) and terminal `PROCESSING_AI_ERROR` (unclassifiable), the Storage Mutation & Sync Service will automatically move the problematic file to a dedicated sub-folder named `_Needs_Human_Eyes` within the original shared directory. An accompanying `.txt` file (e.g., `[filename]_Needs_Password.txt`) will be created next to it, providing a concise, non-technical explanation of the issue and a suggested next step.
*   **Actionable Notifications:** The Egress API will communicate processing outcomes, including failures, to downstream CrewAI agents. These agents are responsible for sending targeted Slack messages or emails to advisors, informing them of specific file issues (e.g., "File 'Q3_Balance_Sheet.pdf' could not be processed due to password protection. Please remove the password and re-upload."). This transforms a technical error into an actionable item for the advisor.
*   **Low Confidence Review (`REQUIRES_REVIEW`):** If the AI Document Processing Engine classifies a document with low confidence (below an 85% threshold), the job transitions to `REQUIRES_REVIEW`. This triggers an egress event to the CrewAI agents, prompting an advisor to manually validate or correct the classification, preventing the propagation of potentially inaccurate metadata.
*   **Quarantined Files:** Files deemed "junk" or part of an anomalous bulk upload by the Ingress Gateway's Anomaly Watchdog will be `QUARANTINED`. While not immediately user-facing, this state allows an administrator to review and, if appropriate, manually override the quarantine and re-queue for processing.

### System-Level Error Handling & Recovery

The distributed nature of the architecture necessitates robust, automated error handling mechanisms to ensure data integrity and system resilience.

*   **Idempotency:** The Ingress Gateway utilizes idempotency keys to ensure that duplicate webhook events from external storage providers (e.g., retries due to network issues) are processed exactly once, preventing redundant work and potential data inconsistencies.
*   **Rate Limiting:** Tenant-specific API call rate limits are enforced via Redis sliding-window counters at the Ingress Gateway. Requests exceeding the defined RPM return an HTTP 429 status, preventing system overload.
*   **Retries with Exponential Backoff:**
    *   **LLM Auto-Correction:** For `PROCESSING_AI_ERROR` where the LLM produces an invalid JSON structure, the AI Document Processing Engine will automatically attempt to correct the prompt and retry the generation up to 2 times before transitioning to a `REQUIRES_REVIEW` or `FAILED` state.
    *   **External API Calls:** When interacting with external Storage Provider APIs or downstream Egress targets, transient network or service errors will trigger retries with exponential backoff.
        *   `Mutation Sync` failures due to temporary API downtime will retry 3 times. If still unsuccessful, the operation transitions to `FAILED`, and an alert is raised to the Admin console.
        *   `Egress Delivery Log` failures will retry up to 5 times (at 1m, 5m, 15m, 1h, 6h intervals) before being moved to a Dead Letter Queue.
*   **Dead Letter Queues (DLQ):** Kafka topics are configured with DLQs for `EgressDeliveryLog` events that have exhausted their retry attempts. This ensures no data is silently dropped and provides a mechanism for manual inspection and reprocessing of persistently failing egress messages.
*   **Circuit Breakers:** Implemented around external third-party integrations (LLM APIs, Box/SharePoint/Google Drive APIs). If a configured error rate threshold (e.g., >50% of requests failing within 30 seconds) is exceeded, the circuit opens, temporarily halting Kafka consumers for that integration. This prevents cascading failures and allows the external service to recover, with automatic retries after a defined cooldown period (e.g., 60 seconds).
*   **Optimistic Concurrency Control:** The Storage Mutation & Sync Service uses HTTP `If-Match` headers with ETags for file renaming operations in external storage. If a user concurrently modifies a file being processed by the system, an `HTTP 412 Precondition Failed` response is received. In this scenario, the system transitions the `StorageMutationOperation` to `REVERTED`, aborting its rename attempt and respecting the user's changes to avoid data loss or undesired overwrites.
*   **Component State Machines:** Each core service (Ingress Gateway, AI Document Processing Engine, Storage Mutation & Sync Service, Structured Data Egress API) maintains explicit state machines. These ensure valid transitions between processing states (`RECEIVED`, `QUEUED`, `PROCESSING`, `FAILED`, `COMPLETED`, `RETRYING`, `DEAD_LETTER`), preventing inconsistent states and providing a clear audit trail of each file's lifecycle within the system.

### Logging and Alerting

Comprehensive observability is paramount for an "invisible" system, ensuring that all errors are detected, diagnosed, and resolved swiftly.

*   **Distributed Tracing:** Every incoming webhook event is assigned an `x-correlation-id` at the Ingress Gateway. This ID is propagated across all subsequent microservices via Kafka message headers and ultimately included in Egress payloads. This enables end-to-end tracing of a single file's journey through the system in tools like Datadog, allowing for rapid root cause analysis of failures.
*   **Structured Logging (JSON):** All application logs are emitted in JSON format, including essential fields such as `timestamp`, `level`, `correlation_id`, `deal_id`, `component`, and a detailed `message`. This structured approach facilitates efficient querying, filtering, and aggregation of logs in centralized logging platforms.
*   **Metrics & Alerts (Prometheus/Grafana):** Key performance indicators and error rates are continuously monitored:
    *   **Ingress Webhook Error Rate:** Alert if the 5xx error rate for incoming webhooks exceeds 1% over a 5-minute window.
    *   **Processing Latency:** Alert if the average time a file spends in a Kafka queue (Time-in-Queue) before processing exceeds 5 minutes.
    *   **AI Confidence Score Drift:** Alert if the daily average AI classification confidence score drops below 85%, indicating potential prompt drift or issues with the underlying VLM.
    *   **FinOps Metrics:** Track `llm_prompt_tokens` and `llm_completion_tokens` per `deal_id` for cost attribution and anomaly detection in LLM usage.
*   **Debugging Guide Integration:** The observability tools are designed to support a clear debugging guide, allowing support engineers to quickly query specific `correlation_id` values or `deal_id`s to diagnose issues like missing files, processing delays, or incorrect classifications by inspecting component states (`DROPPED`, `FAILED`, `REVERTED`, `REQUIRES_REVIEW`).

### Graceful Degradation

The system is designed to degrade gracefully under various failure conditions, prioritizing data integrity and providing clear pathways for resolution rather than hard failures.

*   **Prioritizing User Changes:** In cases of ETag collision during mutation, the system will `REVERT` its automated rename, respecting the user's concurrent modifications. This prevents disruptive overwrites and prioritizes user intent.
*   **Human-in-the-Loop for Ambiguity:** Instead of making potentially incorrect automated decisions, the system will flag `REQUIRES_REVIEW` for low-confidence AI classifications, routing these to an advisor for manual validation.
*   **Actionable Failure Feedback:** Rather than silent errors, the system ensures that failures (e.g., password-protected files) result in explicit `_Needs_Human_Eyes` folders and advisory notifications, transforming potential roadblocks into clear, actionable tasks.
*   **Isolation of Failures:** The distributed architecture, coupled with message queues and circuit breakers, ensures that a failure in one component (e.g., a downstream CRM being offline) does not cascade and impact the core file processing pipeline or other integrations.

## Success Metrics

The success of the Headless M&A Data Structuring API will be measured across several dimensions, focusing on the core value propositions of friction reduction, processing efficiency, AI accuracy, and ultimately, the quantifiable impact on M&A advisor bandwidth and deal momentum. These metrics are designed to be Specific, Measurable, Achievable, Relevant, and Time-bound (SMART).

### 1. Core Business Impact & User Experience

These metrics directly reflect the product's vision of "Invisible Intelligence" and its impact on key user personas (sell-side founders, CFOs, M&A advisors).

*   **Metric 1.1: Frictionless Adoption for Sell-Side Users**
    *   **Description:** Measures the extent to which sell-side users can leverage the system without needing to learn new software interfaces, create new logins, or adopt new workflows.
    *   **Baseline:** Traditional VDR onboarding requires new logins, password management, and learning a new UI.
    *   **Target:** Exactly **0 net-new login credentials or UI onboarding sessions** required for sell-side users within 3 months of V1 launch.
    *   **Measurement:** Qualitative user feedback from initial pilot deals, analysis of user journey telemetry (absence of login/onboarding flows), and explicit confirmation from M&A advisors.

*   **Metric 1.2: Advisor Bandwidth Reduction**
    *   **Description:** Quantifies the reduction in time M&A advisors spend on administrative tasks related to document ingestion, classification, renaming, and client follow-up. This directly impacts their effective hourly rate.
    *   **Baseline:** Industry average of 40% advisor bandwidth consumed by document administration.
    *   **Target:** A demonstrable **30% reduction** in advisor time spent on document administration and client follow-up within 6 months of V1 launch, freeing them to focus purely on deal strategy and buyer negotiation.
    *   **Measurement:** Pre and post-implementation time-motion studies or detailed activity logging provided by M&A advisory firm partners. Surrogate metrics like automated renaming success rate and proactive missing file notifications will also contribute.

### 2. System Performance & Reliability

These metrics ensure the underlying API and processing pipeline are robust, fast, and always available.

*   **Metric 2.1: End-to-End Processing Velocity**
    *   **Description:** The total time taken from a user dropping a raw file into their integrated cloud storage to the structured, deterministic metadata being available in the `mna.egress.v1` Kafka topic (ready for downstream consumption).
    *   **Baseline:** Industry average of 48 hours for manual processing.
    *   **Target:** Time from webhook ingestion to structured metadata availability is **< 5 minutes for 95% of successfully processed files** within 2 months of V1 launch.
    *   **Measurement:** Distributed tracing (`x-correlation-id`) to track event timestamps across the Ingress Gateway, Kafka queues, AI Document Processing Engine, Storage Mutation, and Egress API. Monitored via Prometheus/Grafana dashboards.

*   **Metric 2.2: System Availability (Uptime)**
    *   **Description:** Measures the operational uptime of the critical components of the Headless M&A Data Structuring API.
    *   **Baseline:** N/A (new system).
    *   **Target:** **99.9% uptime** for the Ingress Gateway and core AI Document Processing Engine processing pipeline (excluding planned maintenance) annually.
    *   **Measurement:** Standard monitoring tools (e.g., Datadog, Prometheus/Grafana) tracking service health, API response times, and error rates (specifically 5xx errors) from external and internal probes.

*   **Metric 2.3: Integration Success Rate**
    *   **Description:** The percentage of successful interactions with external cloud storage providers (Box, SharePoint, Google Drive) and external LLM APIs (OpenAI/Anthropic).
    *   **Baseline:** N/A (new integrations).
    *   **Target:** Maintain a **>98% success rate** for all external API calls (HTTP 2xx responses) within 3 months of V1 launch.
    *   **Measurement:** Monitoring external API call logs, response codes, and latencies through the distributed tracing system and component-specific metrics in Prometheus/Grafana.

### 3. AI Quality & Data Health

These metrics ensure the intelligence layer provides accurate, reliable, and transparent outputs.

*   **Metric 3.1: AI Classification Accuracy**
    *   **Description:** The precision of the Vision-Language Model (VLM) in correctly classifying documents into predefined M&A taxonomies.
    *   **Baseline:** N/A (new AI model).
    *   **Target:** Achieve **>95% AI classification accuracy** against a human-validated ground truth dataset for the 5 standard M&A taxonomies by V1 launch, and maintain this accuracy continuously.
    *   **Measurement:** Regular batch evaluation of AI classifications on a held-out test set; Human-in-the-Loop review API logs for `REQUIRES_REVIEW` documents will provide feedback data.

*   **Metric 3.2: Visibility into Processing Failures (Zero Silent Failures)**
    *   **Description:** Measures the effectiveness of the error handling strategy to ensure no file processing failures are silent.
    *   **Baseline:** Manual processes often lead to silent failures or delayed discovery.
    *   **Target:** **100% of `FAILED` or `REQUIRES_REVIEW` `DocumentProcessingJob` events** must result in an explicit, actionable notification to the M&A advisor (via `_Needs_Human_Eyes` folder creation, Slack/Email alert, or entry in a review queue) within 15 minutes of failure detection, within 1 month of V1 launch.
    *   **Measurement:** Audit logs from `EgressDeliveryLog` and `StorageMutationOperation` linked to `FAILED` or `REQUIRES_REVIEW` job statuses. Monitoring for unaddressed `FAILED` jobs beyond threshold.

### 4. Operational Efficiency & Cost

These metrics ensure the system operates sustainably and within budget.

*   **Metric 4.1: LLM Cost Efficiency**
    *   **Description:** Monitors the consumption of LLM tokens per document processed, directly impacting operational costs.
    *   **Baseline:** N/A (new LLM integration).
    *   **Target:** Average LLM token cost per successfully processed document to remain **within a target budget (e.g., < $0.05 per document)**, monitored monthly and optimized quarterly.
    *   **Measurement:** `llm_prompt_tokens` and `llm_completion_tokens` logged per `deal_id` and `job_id` in the `document_processing_jobs` table, aggregated for FinOps dashboards. Alerts for significant deviations from cost targets.

### 5. Delight Features Adoption & Impact

These metrics measure the success of the "bonus chunks" that contribute to the "magical" user experience.

*   **Metric 5.1: Auto-Redaction Usage & Accuracy**
    *   **Description:** The effectiveness of automatically generating redacted clones for sensitive documents.
    *   **Baseline:** N/A.
    *   **Target:** For >75% of documents identified as `contains_pii`, a `[Filename]_REDACTED.pdf` clone is successfully generated during mutation within 3 months of relevant feature rollout. PII masking accuracy to be >90% against a test set.
    *   **Measurement:** `StorageMutationOperation` audit logs for `_REDACTED.pdf` creation and manual spot-checks for PII masking efficacy.

*   **Metric 5.2: Momentum High-Fives Engagement**
    *   **Description:** Measures the usage and positive reception of automated celebratory notifications to advisors.
    *   **Baseline:** N/A.
    *   **Target:** **>80% open rate** (for email) or **click-through rate** (for Slack if applicable) on "Momentum High-Five" notifications, coupled with positive qualitative feedback from advisors, within 3 months of feature rollout.
    *   **Measurement:** Egress API logs for notification delivery and engagement tracking via Slack/Email platform analytics. Qualitative advisor surveys.

## Dependencies

The Headless M&A Data Structuring API is designed to be an invisible intelligence layer, integrating deeply with existing enterprise tools and internal systems. Its successful operation and continuous evolution depend on robust integration with several external services and the collaborative efforts of various internal teams.

### 1. External Integrations & Third-Party Services

The core functionality of the API hinges on reliable access and seamless interaction with these external providers.

*   **1.1. Cloud Storage Providers (Box, SharePoint, Google Drive)**
    *   **Nature:** Primary data ingress points. Our system relies on their webhook mechanisms to detect file uploads/modifications and their APIs for file download, renaming, moving, and metadata updates.
    *   **Impact:** Critical for document ingestion and in-place mutation. Instability, API changes, or rate limiting from these providers directly impacts our ability to process files and deliver the "invisible" experience.
    *   **Mitigation:** Proactive monitoring of provider API status, implementation of robust retry mechanisms and circuit breakers, and adherence to provider-specific best practices for API usage and OAuth.
    *   **Owner:** External Partnerships / Platform Engineering

*   **1.2. External Large Language Model (LLM) Providers (e.g., OpenAI, Anthropic)**
    *   **Nature:** Provide the underlying AI capabilities for document classification, metadata extraction, nomenclature generation, summarization, and PII detection.
    *   **Impact:** Critical for the intelligence layer. Downtime, API changes, rate limits, or changes in model performance (e.g., prompt drift, increased hallucination) directly affect the quality and cost-efficiency of our AI processing.
    *   **Mitigation:** Multi-provider strategy where feasible, diligent monitoring of LLM API health and cost, regular evaluation of model performance (AI Confidence Scores), and robust prompt engineering practices.
    *   **Owner:** AI/ML Engineering

*   **1.3. Optical Character Recognition (OCR) Service**
    *   **Nature:** Converts images and scanned PDFs into machine-readable text, enabling subsequent AI processing.
    *   **Impact:** Essential for processing unstructured image-based documents. Performance and accuracy directly affect the quality of input for the VLM/LLM.
    *   **Mitigation:** Careful selection of a performant and accurate OCR provider, monitoring OCR success rates, and implementing fallback strategies for corrupted files.
    *   **Owner:** AI/ML Engineering

*   **1.4. Downstream AI Agents / CrewAI Integration (M&A crewAI agentic solution)**
    *   **Nature:** Our structured data Egress API feeds metadata to these agents (as outlined in the completed idea "M&A crewAI agentic solution to automate buyer and seller onboarding and decis..."). These agents are responsible for generating user-facing communications (Slack/Email) and further automating M&A workflows.
    *   **Impact:** Critical for completing the user experience (e.g., "Momentum High-Fives," missing file notifications) and for leveraging the structured data for advanced automation.
    *   **Mitigation:** Clear API contracts and robust error handling for egress webhooks, including retry mechanisms and Dead Letter Queues (DLQ). Close coordination with the team developing the CrewAI agents.
    *   **Owner:** Product Team / AI/ML Engineering (for CrewAI agent development)

*   **1.5. Communication Platforms (Slack, Email Service Provider)**
    *   **Nature:** Used by downstream CrewAI agents to send notifications and "Momentum High-Fives" to M&A advisors and sell-side users.
    *   **Impact:** Essential for closing the feedback loop with users and advisors. Outages or deliverability issues would undermine the "Invisible Deal Quarterback" experience.
    *   **Mitigation:** Monitoring of delivery success rates, selection of reliable email service providers, and adherence to best practices for notification deliverability.
    *   **Owner:** AI/ML Engineering (for CrewAI agent integration) / Operations

### 2. Internal Platform Services

The API leverages foundational internal infrastructure components that are critical for its operation, scalability, and resilience. While internal, these are often managed by dedicated platform or SRE teams, making us a consumer of their services.

*   **2.1. Managed PostgreSQL Database (PostgreSQL 16)**
    *   **Nature:** Serves as the primary data store for all application state, event logs, and extracted metadata.
    *   **Impact:** Fundamental for system operation, state tracking, and data integrity (ACID guarantees). Performance bottlenecks or downtime would be catastrophic.
    *   **Mitigation:** Adherence to platform team's best practices for schema design, query optimization, and capacity planning. Robust monitoring and alerting from the platform team.
    *   **Owner:** Platform Engineering / SRE Team

*   **2.2. Managed Kafka Message Broker**
    *   **Nature:** Provides asynchronous communication, decoupling services, and ensuring ordered, replayable event processing.
    *   **Impact:** Critical for scalability, resilience, and maintaining event integrity across distributed components.
    *   **Mitigation:** Adherence to platform team's Kafka best practices for topic design, partitioning, consumer group management, and monitoring.
    *   **Owner:** Platform Engineering / SRE Team

*   **2.3. Managed Redis Cache**
    *   **Nature:** Used for rate limiting, idempotency checks, and ephemeral data storage (e.g., anomaly detection aggregations).
    *   **Impact:** Essential for protecting the Ingress Gateway from abuse and optimizing performance.
    *   **Mitigation:** Adherence to platform team's Redis best practices, monitoring cache hit rates, and ensuring appropriate instance sizing.
    *   **Owner:** Platform Engineering / SRE Team

*   **2.4. Ephemeral S3/Blob Storage**
    *   **Nature:** Temporary storage for files during the OCR and AI processing pipeline, ensuring secure wiping post-mutation.
    *   **Impact:** Crucial for handling file payloads during processing and ensuring data security (PII retention policies).
    *   **Mitigation:** Adherence to platform team's S3 security and lifecycle management policies, ensuring proper access controls and deletion schedules.
    *   **Owner:** Platform Engineering / SRE Team

### 3. Cross-Functional Team Dependencies

Successful delivery and operation require collaboration and input from various internal teams.

*   **3.1. Security Team**
    *   **Nature:** Review and approval of OAuth integration flows with cloud storage providers, data encryption standards, PII handling, and overall system security architecture.
    *   **Impact:** Non-negotiable for handling sensitive M&A data. Failure to meet security standards will block deployment.
    *   **Mitigation:** Early engagement with the Security team during design, regular security reviews (e.g., penetration testing), and adherence to internal security policies.
    *   **Owner:** Security Team

*   **3.2. Legal & Compliance Team**
    *   **Nature:** Review of data residency, privacy policies, PII redaction logic, and compliance with industry regulations (e.g., GDPR, SOC 2, FINRA).
    *   **Impact:** Essential for legal compliance and avoiding regulatory penalties.
    *   **Mitigation:** Early and continuous engagement with Legal & Compliance throughout the development lifecycle to ensure all features and data handling practices are compliant.
    *   **Owner:** Legal & Compliance Team

*   **3.3. DevOps / SRE Team**
    *   **Nature:** Support for infrastructure provisioning (PostgreSQL, Kafka, Redis, S3), deployment pipelines (CI/CD, Blue/Green), monitoring, alerting, and incident response for the service itself.
    *   **Impact:** Critical for operational stability, scalability, and rapid recovery from outages.
    *   **Mitigation:** Close collaboration on architecture design, adherence to operational playbooks, and joint ownership of service reliability targets (SLOs/SLAs).
    *   **Owner:** DevOps / SRE Team

*   **3.4. Product & Data Analytics Team**
    *   **Nature:** Definition of instrumentation requirements, development of dashboards, and analysis of success metrics (e.g., Advisor Bandwidth Reduction).
    *   **Impact:** Essential for validating the business impact and making data-driven product decisions.
    *   **Mitigation:** Early collaboration on defining success metrics and ensuring proper instrumentation is built into the API.
    *   **Owner:** Product Analytics Team

## Assumptions

This section outlines the critical assumptions made during the planning and design of the Headless M&A Data Structuring API. These assumptions are foundational to the project's scope, timelines, and expected outcomes. Should any of these assumptions prove false, there could be significant impacts on the project's feasibility, cost, or success metrics.

### 1. User Behavior & Adoption Assumptions

*   **1.1. User Willingness to Adopt Invisible Workflows:** We assume that sell-side founders and CFOs, along with M&A advisors, are willing to embrace a "headless" solution where document processing and feedback occur invisibly in their existing cloud storage and communication channels, even without a dedicated, interactive UI.
    *   **Impact if False:** Low adoption rates, continued reliance on legacy VDRs, and failure to achieve the targeted reduction in onboarding friction.
*   **1.2. Acceptable Trade-off for UI Control:** We assume that the benefits of dramatically reduced onboarding friction (no new logins, no new UIs) significantly outweigh the loss of control over *bespoke, interactive, new-portal-based UI control and active client prompting through a proprietary interface*. This distinction acknowledges the system's asynchronous, native-tool-based prompting (`00_Diligence_Progress.pdf`, Slack/Email).
    *   **Impact if False:** User dissatisfaction with the perceived lack of direct control, leading to decreased value and potential pushback from advisors who prefer more explicit proprietary UI client engagement.
*   **1.3. User Comfort with File Renaming In-Place:** We assume that users are comfortable with our middleware non-destructively renaming files in their existing shared folders (e.g., `Scan_0045_Final.pdf` to `Phase1_VendorContract_AWS_Oct2023_v1.pdf`), as long as the original content is preserved and the operation is clearly auditable.
    *   **Impact if False:** User distrust, confusion, or resistance to automated file modifications, potentially leading to manual undoing of changes or disengagement with the system.
*   **1.4. Responsiveness to Async Notifications:** We assume that M&A advisors and sell-side users will reliably act upon asynchronous Slack/Email notifications regarding processing updates, missing documents, or files requiring human review, given the absence of a central dashboard for status tracking.
    *   **Impact if False:** Delays in document resolution, overlooked requests for missing files, and a breakdown in the "Invisible Deal Quarterback" communication flow.
*   **1.5. User Acceptance of Automated Redaction/Quarantine:** We assume that sell-side founders/CFOs and M&A advisors will accept automated PII redaction and file quarantining (moving files to `_Needs_Human_Eyes` folders) as a necessary security or processing measure. This acceptance is based on the understanding that these operations are non-destructive and provide clear, actionable remediation paths.
    *   **Impact if False:** User confusion, resistance, or legal concerns regarding automated handling of sensitive documents, undermining trust in the system.

### 2. Technical & API Assumptions

*   **2.1. Cloud Storage Provider API Stability & Capabilities:** We assume that the APIs for Box, SharePoint, and Google Drive will remain stable, performant, and consistently provide the necessary functionality for:
    *   Robust and timely webhook notifications for file events, specifically that **webhooks are delivered within < 5 seconds (p95)**.
    *   Reliable file download/upload capabilities (including large files).
    *   Atomic and optimistic concurrency-controlled file renaming/moving (e.g., ETag support).
    *   Secure OAuth and credential management for programmatic access.
    *   **Impact if False:** Significant technical blockers, degraded performance, data inconsistencies, and potential security vulnerabilities.
*   **2.2. External LLM and OCR API Stability & Performance:** We assume that the chosen External LLM APIs (e.g., OpenAI, Anthropic) and OCR services will maintain their current levels of accuracy, latency, availability, and cost-effectiveness.
    *   **Impact if False:** Degraded AI classification accuracy, increased processing times (impacting "Processing Velocity" metric), significant increases in FinOps costs, or complete failure of the cognitive engine.
*   **2.3. M&A Taxonomy Stability:** We assume that the 5 standard M&A taxonomies used for AI classification are sufficiently stable and comprehensive for V1, requiring **fewer than 2 changes to core document categories or transaction phases per quarter** post-launch.
    *   **Impact if False:** Extensive re-training of AI models, re-prompting, and potential disruption to downstream systems relying on the classified metadata.
*   **2.4. Data Volume & Complexity Management:** We assume that the initial data volumes and complexity of "messy" files dropped into shared folders (e.g., ZIP dumps of 500 chaotic files) are manageable within the defined processing velocity targets using the current architecture and chosen LLM/OCR providers.
    *   **Impact if False:** Failure to meet performance SLAs, increased processing backlogs, and unforeseen infrastructure scaling challenges.
*   **2.5. Security & Compliance Integration:** We assume that the existing internal security and compliance frameworks are adequate and can be extended to cover the new headless architecture, especially regarding OAuth flows, data residency, PII handling, and audit trails for external integrations.
    *   **Impact if False:** Major delays due to security/compliance reviews, requiring significant architectural rework, or potential regulatory non-compliance.
*   **2.6. Robustness of Optimistic Concurrency Control:** We assume that the use of ETags for optimistic concurrency control in storage mutation operations will effectively prevent file corruption or data loss in the event of concurrent user modifications.
    *   **Impact if False:** File corruption, user frustration, and a breakdown of trust in the system's non-destructive mutation capabilities.
*   **2.7. AI Model Maintainability & Evolution:** We assume that the AI models (VLM/LLM) will require ongoing monitoring, fine-tuning, and potential retraining to maintain accuracy and adapt to evolving M&A taxonomies and document types, incurring continuous operational and development costs.
    *   **Impact if False:** Unforeseen long-term maintenance burden, degradation of AI accuracy over time, and a negative impact on FinOps targets due to unbudgeted AI model updates.
*   **2.8. External API Burst Capacity:** We assume that external cloud storage provider APIs (Box, SharePoint, Google Drive) have sufficient burst capacity to handle high-volume, concurrent file uploads and mutations triggered by our system, aligning with our daily volume capacity targets.
    *   **Impact if False:** Rate limiting issues, delayed processing, and service interruptions during peak file ingestion periods.

### 3. Operational & Business Assumptions

*   **3.1. Availability of Internal Platform Services:** We assume that core internal platform services (as detailed in the Dependencies section, 2.1-2.4) will consistently meet their defined SLAs for uptime, performance, and data integrity.
    *   **Impact if False:** Service outages, data loss, and cascading failures across the Headless M&A Data Structuring API.
*   **3.2. Existing M&A crewAI Agent Integration:** We assume that the downstream M&A crewAI agentic solution is sufficiently mature or will be developed in parallel to effectively consume the structured metadata and generate actionable communications (e.g., Slack messages, checklist updates) as envisioned.
    *   **Impact if False:** The structured data remains siloed, the "Invisible Deal Quarterback" vision is incomplete, and key user feedback loops are not realized.
*   **3.3. Advisor Firm Technical Enablement:** We assume that M&A advisory firms will have the necessary internal technical capabilities (e.g., IT support, administrative access) to assist clients with initial OAuth integrations and troubleshoot any file access issues that might arise.
    *   **Impact if False:** Increased burden on our support team, slower adoption, and friction during initial client setup.
*   **3.4. Cost-Effectiveness of LLM Usage:** We assume that the average LLM token cost per successfully processed document will remain **below $0.05 (as per Success Metrics)**, and that FinOps attribution per `deal_id` will provide sufficient visibility for cost optimization. This also assumes that new LLM models or pricing changes from providers will not significantly alter this cost structure.
    *   **Impact if False:** Unsustainable operational costs, requiring re-evaluation of AI usage patterns or significant architectural changes.
*   **3.5. Internal Communication Tool Reliability:** We assume that internal communication platforms (Slack, Email) used by M&A advisors are consistently available and reliable, ensuring timely delivery and reception of system-generated notifications.
    *   **Impact if False:** Advisors miss critical updates, leading to delays in deal progress or unaddressed issues, undermining the "Invisible Deal Quarterback" experience.
