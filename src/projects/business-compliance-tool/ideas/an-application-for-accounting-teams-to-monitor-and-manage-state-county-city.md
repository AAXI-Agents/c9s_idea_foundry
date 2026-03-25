---
run_id: b8931a4d8997
status: completed
created: 2026-03-23T12:32:19.988400+00:00
completed: 2026-03-23T13:14:24.604448+00:00
project: "[[business-compliance-tool]]"
tags: [idea, prd, completed]
---

# an application for accounting teams to monitor and manage state, county, city...

> Part of [[business-compliance-tool/business-compliance-tool|Business compliance tool]] project

## Original Idea

an application for accounting teams to monitor and manage state, county, city, and local compliance requirements, fee payments, and deadlines for companies within the United States, with future expansion to worldwide operations. The application should identify compliance needs, highlight necessary information for accounting teams, prepare fees and payment methods, and facilitate payments and information updates.

## Refined Idea

# Product Idea: JurisTrack – Automated Local Compliance & Entity Management Engine

## Executive Summary
JurisTrack is an intelligent RegTech application designed for mid-market and enterprise accounting teams to proactively monitor, manage, and execute state, county, and municipal compliance filings and fee payments. Moving beyond standard sales tax automation (e.g., Avalara), JurisTrack tackles the hyper-fragmented, high-risk operational burden of local business licenses, franchise taxes, annual reports, and localized municipal fees (e.g., Denver Occupational Privilege Tax, San Francisco Gross Receipts). By leveraging AI-driven document parsing, workflow agents, and deep ERP integrations, JurisTrack ensures companies maintain "Good Standing" across all US jurisdictions, preventing operational lockouts and M&A derailing due to missed trivial fees. 

## The Problem Statement
As a veteran Corporate Controller, I can attest that managing local US compliance is a multi-headed hydra. With over 10,000 distinct tax and licensing authorities in the US, the post-COVID shift to remote work has triggered massive, often invisible "nexus" footprints for mid-market companies. 

Currently, accounting teams face four critical failure points:
1. **Blind Nexus Discovery:** Companies rely on manual self-reporting. If HR hires an employee in a new city, Finance rarely knows they need to register for a local business license until a penalty notice arrives.
2. **The "Last Mile" Payment Nightmare:** Municipalities are technologically archaic. Paying a $50 fee often requires navigating clunky web portals built in 2005 or mailing a physical paper check.
3. **Physical Mail Bottlenecks:** Jurisdictions communicate primarily via physical mail. Vital notices regarding fee changes or deadlines sit on a receptionist's desk rather than reaching the compliance calendar.
4. **Reconciliation Drag:** Manually entering hundreds of small municipal payments into the general ledger (QuickBooks Online or NetSuite) consumes days of accounting capacity during month-end close.

## Target Audience
* **Primary Users:** Corporate Controllers, VP of Finance, Accounting Managers, and In-house Legal/Compliance Officers at US-based mid-market companies ($10M–$150M ARR) with distributed workforces.
* **Secondary Users:** External CPA firms managing entity compliance on behalf of multi-tenant client portfolios.

## Core Capabilities & Technical Implementation
To solve these pain points, JurisTrack must be built as a closed-loop system that handles discovery, extraction, execution, and reconciliation.

**1. Dynamic Nexus Discovery & ERP Sync**
Instead of waiting for manual input, the system must integrate securely with core HRIS platforms (via API) and ERPs (QuickBooks Online, NetSuite). When a new employee address or new revenue source is detected in a previously unregistered ZIP code, the system automatically flags a "Potential Nexus Trigger" for the accounting team, identifying the exact city, county, and state compliance requirements associated with that location.

**2. AI-Powered Notice Parsing (Vertex AI)**
Accounting teams receive hundreds of physical mail notices monthly. Users will scan and upload these documents into JurisTrack. Utilizing **Google Vertex AI** (Document AI), the system will ingest these unstructured PDFs, automatically extracting the Jurisdiction Name, Account ID, Due Date, Fee Amount, and Payment Instructions, turning physical mail into structured, trackable database records in **MongoDB Atlas**.

**3. Agentic Portal Navigation & Fee Monitoring (crewAI)**
Because local government APIs are practically non-existent, JurisTrack will utilize **crewAI agents** written in **Python 3.11**. These agents will be configured to periodically navigate known municipal web portals, log in securely using stored credentials, and "scrape" current account balances, fee updates, and status changes, alerting the user via the **React + TypeScript** frontend if a discrepancy exists between the portal and the internal database.

**4. Frictionless Payment & Ledger Reconciliation**
To solve the "last mile" payment issue, the application will provide a unified payment clearinghouse. Users fund a central JurisTrack wallet, and the **FastAPI** backend orchestrates the outward payments (via virtual cards for portals, or automated check-cutting APIs for archaic towns). Crucially, utilizing the **NetSuite REST API and QBO API**, every cleared payment will automatically generate a Vendor Bill or Journal Entry in the client’s ERP, accurately tagged with the correct GL Account, Department, and Location dimensions.

## Key Risks & Mitigations
* **Regulatory Liability:** If JurisTrack misses a deadline, who pays the penalty? *Mitigation:* The system must maintain immutable audit logs of all user approvals and agent actions. The PRD must specify robust fallback mechanisms: if a crewAI agent fails to scrape a portal due to a UI change, a high-priority alert must route to a human operator immediately.
* **Data Security:** Handling state tax IDs, EINs, and municipal portal passwords requires enterprise-grade security. *Mitigation:* All sensitive credentials must be encrypted at rest in MongoDB using envelope encryption, and never exposed to the frontend React application. 

## Success Criteria
* **Coverage:** Ability to support compliance tracking for all 50 US States and the top 500 municipal jurisdictions at launch.
* **Automation:** 90% of uploaded government notices are successfully parsed by Vertex AI without requiring manual data-entry corrections.
* **Time Savings:** Reduce the time spent paying and reconciling local compliance fees from 20 hours/month to under 2 hours/month for a mid-market finance team.

## Executive Summary

**Problem Statement**
US mid-market companies face a hyper-fragmented, high-risk operational burden when managing local business licenses, franchise taxes, and municipal fees across more than 10,000 distinct jurisdictions. Accelerated by the post-COVID shift to distributed workforces, accounting teams struggle with "blind" nexus discovery, technologically archaic municipal payment systems, physical mail bottlenecks, and manual ERP reconciliation. These disjointed processes result in costly compliance penalties, wasted accounting capacity during month-end close, and the potential derailment of M&A activities due to compromised entity standing.

**Target Audience & Key Personas**
*   **Primary Users: Corporate Controllers, VPs of Finance, Accounting Managers** (mid-market companies, $10M–$150M ARR)
    *   *Pain Points:* Severe audit risk from unmapped jurisdictions; wasted team capacity manually processing $50 checks; disconnected, un-reconciled ledger entries.
    *   *Goals:* Attain 100% compliance visibility with zero late fees; automate month-end reconciliation; eliminate manual physical mail processing.
*   **Secondary Users: External CPA / Compliance Firms**
    *   *Pain Points:* Context-switching across multi-tenant client portfolios; high cost of onboarding new clients' historical compliance data; liability for missed filing deadlines.
    *   *Goals:* Manage a unified multi-client dashboard; securely scale entity management without adding administrative headcount; leverage automated scraping for portfolio-wide fee updates.

**Proposed Solution & Key Workflows**
JurisTrack is an intelligent, closed-loop RegTech application built to proactively monitor, manage, and execute local compliance filings. Detailed Functional Requirements will be mapped in subsequent sections, but the core system relies on four pillars supported by robust human-in-the-loop workflows:
*   **Dynamic Nexus Discovery & Dashboarding:** Secure API integrations with core HRIS platforms and ERPs (QuickBooks Online, NetSuite) automatically detect new revenue sources or employee addresses. Users interact via a central dashboard providing full CRUD (Create, Read, Update, Delete) capabilities for entity configurations, alongside an approval queue for investigating "Potential Nexus Triggers."
*   **AI-Powered Notice Parsing:** Utilizing Google Vertex AI (Document AI), the system ingests scanned physical mail. It structures unstructured PDFs (Jurisdiction, Account ID, Due Date, Fee Amount) into MongoDB Atlas.
*   **Agentic Portal Navigation:** Autonomous crewAI agents (Python 3.11) securely log into legacy municipal web portals to scrape account balances and track status changes, reconciling this data against internal records.
*   **Frictionless Payment & Reconciliation:** A central FastAPI payment clearinghouse orchestrates virtual cards and automated check-cutting. Users manage a 1-click payment approval workflow. Every cleared payment utilizes NetSuite/QBO APIs to write back categorized Vendor Bills or Journal Entries.

**Non-Functional Requirements & Architecture Targets**
To guarantee enterprise readiness, JurisTrack must adhere to strict quantitative baselines:
*   **Performance:** All critical user-facing API interactions must achieve <500ms response times (p95).
*   **Scalability:** At launch, the architecture must seamlessly support 5,000 active entities, 500 mapped municipal jurisdictions, and 500 concurrently active daily users.
*   **Reliability:** The system will target a 99.9% uptime SLA for core web application availability.
*   **Security & Compliance:** Built for SOC 2 Type II compliance readiness. All sensitive credentials (municipal portal passwords, EINs, Tax IDs) must be secured via envelope encryption at rest in MongoDB and never exposed to the React frontend.
*   **Data Retention:** Immutable audit logs and extracted document data must be retained for a minimum of 7 years to support regulatory audits.

**Edge Cases & Error Handling**
Given the system’s reliance on external, volatile environments, robust fallback mechanisms are required:
*   *Discovery False Positives:* If the HRIS integration flags a temporary travel address as a nexus, the user dashboard provides a 1-click "Dismiss/Exclude" workflow to override the flag.
*   *AI Parsing Degradation:* If Vertex AI confidence falls below the 90% threshold or the document format is unrecognized, the item is immediately routed to a designated manual review queue, preventing silent data drops.
*   *Agentic Scraping Blocks:* If a crewAI agent encounters CAPTCHAs, IP bans, or municipal site downtime, the system implements exponential backoff retries. After 3 failures, an alert is triggered to a human operator.
*   *Payment/ERP Write-back Failures:* Should a municipal payment clear but the NetSuite/QBO API rate-limits the write-back, a dead-letter queue will automatically retry the ledger sync, flagging the Controller if unresolved within 24 hours.

**Dependencies & Critical Risks**
*   **External API Volatility:** Over-reliance on HRIS, ERP, and municipal web structures. *Mitigation:* Implement strict API circuit breakers, retry logic, and active DOM-change monitoring for scraping agents.
*   **crewAI Framework Maturity:** Agentic orchestration is a rapidly evolving field. *Mitigation:* Isolate agent logic to independent microservices to allow framework swapping if necessary, and maintain deep internal Python/LLM engineering expertise.
*   **Regulatory Rule Changes:** Rapidly shifting localized municipal fee structures. *Mitigation:* Develop an internal, dynamic compliance rules engine maintained by a dedicated internal data operations team, rather than hardcoding business logic.

**Business Impact, Analytics & Success Criteria**
Systematic event logging (tracking parsing success, agent completion rates, payment funnel drop-offs, and user time-in-app) will be instrumented to measure the following success criteria:
*   **Operational Efficiency:** Reduce the time finance teams spend paying and reconciling local compliance fees from an average of 20 hours/month to under 2 hours/month.
*   **Automation Efficacy:** Achieve a 90% success rate in zero-touch Vertex AI parsing of uploaded government notices without manual data-entry corrections.
*   **Market Coverage:** Successfully support automated compliance tracking for all 50 US States and the top 500 municipal jurisdictions at launch.
*   **Risk Reduction:** Maintain 100% "Good Standing" across tracked entities, eliminating unbudgeted municipal late fees and penalties.

**High-Level Timeline & Phasing**
*   **Phase 1 (Months 1-2):** Data Architecture, MongoDB Schema with envelope encryption, core ERP/HRIS API integrations, and Vertex AI parsing pipelines.
*   **Phase 2 (Months 3-4):** crewAI agent development for top 500 municipalities, FastAPI payment orchestration, and centralized wallet infrastructure.
*   **Phase 3 (Months 5-6):** React + TypeScript frontend dashboard (CRUD, workflow queues, human-in-the-loop fallbacks), robust audit logging, internal analytics telemetry, and Beta launch.

## Executive Product Summary

# Executive Product Summary: JurisTrack

## The Real Problem: The Existential Risk of Invisible Administrative Debt
When a Controller asks for a "better way to track local compliance fees," we must not take the request literally. They don't actually want a better tracking dashboard. They want the problem to disappear entirely. 

Today, mid-market companies are distributed across thousands of hyper-fragmented jurisdictions. Hiring a single remote engineer in a new city silently triggers a web of archaic local tax and licensing requirements. The literal problem is that managing these 10,000+ local jurisdictions involves physical mail, clunky 2005-era municipal portals, and manual ERP reconciliation. But the *real* problem is the asymmetry of risk: a forgotten $50 Denver Occupational Privilege Tax can quietly revoke a company's "Good Standing," silently derailing a $100M M&A event or triggering catastrophic operational lockouts. Finance leaders live in terror of what they don't know, yet they resent spending 20 hours a month on administrative trivia.

JurisTrack is not a compliance dashboard. It is an **autonomous legal entity infrastructure layer**. We are not building software to help accountants pay local fees; we are building an AI-native back office that pays the fees, guarantees entity standing, and mathematically eliminates the risk of human error.

## The 10-Star Vision: Self-Driving Entity Management
The 3-star version of this product is a glorified calendar that sends email reminders when municipal fees are due. We are scrapping that. 

The 10-star version operates like a magical, invisible compliance team. It plugs directly into the HRIS and ERP. The moment an employee address changes, JurisTrack calculates the nexus footprint. It intercepts the resulting physical mail, uses AI to extract the data, deploys autonomous agents to log into government portals to pay the fees via virtual cards, and writes the exact journal entry back to the general ledger—all before the Controller even finishes their morning coffee.

If we miss a filing deadline, *we* pay the penalty. That is the level of confidence we must architect into this system. 

By combining **crewAI** for autonomous municipal web navigation, **Google Vertex AI** for flawless document parsing, and deep bidirectional integrations via the **NetSuite and QuickBooks Online (QBO) APIs**, we are creating the definitive "Last Mile" execution engine for local compliance.

## The Ideal User Experience: "This is Exactly What I Needed"
Imagine a Controller, Sarah, at a $50M ARR SaaS company. 

1. **Invisible Discovery:** Sarah's HR team hires a new Account Executive in San Francisco. Sarah does nothing. JurisTrack detects the new address via an HRIS webhook, flags a San Francisco Gross Receipts Tax nexus, and automatically queues the registration requirements.
2. **The "Last Mile" Solved:** A month later, a physical notice arrives. It’s scanned and dropped into JurisTrack. **Vertex AI** instantly parses the unstructured PDF (Account ID, Due Date, $150 Fee). 
3. **Agentic Execution:** Instead of Sarah navigating the city’s notoriously awful website, a **crewAI agent** written in Python 3.11 securely logs in using credentials stored in **MongoDB Atlas** (via envelope encryption). It verifies the balance and queues the payment.
4. **1-Tap Approval:** Sarah gets a Slack notification: *"San Francisco Gross Receipts Tax: $150 due. Tap to approve."* She taps "Approve."
5. **Frictionless Reconciliation:** A **FastAPI** worker triggers a virtual card payment. Upon clearance, the system uses the NetSuite REST API to automatically create a Vendor Bill, fully categorized by GL Account and Department, with the original scanned PDF securely attached.

Sarah spent exactly 3 seconds on a task that used to take 30 minutes, and her company's standing is guaranteed.

## Delight Opportunities ("Oh nice, they thought of that")
To elevate the product from functional to magical, we will build these high-impact, low-effort features (each <30 mins of dev/config effort):

1. **The "M&A Ready" Data Room Button:** A single button in the React frontend that instantly generates a cleanly formatted ZIP file containing the "Certificates of Good Standing" and last 12 months of tax receipts for every registered jurisdiction. *Value: Turns weeks of due diligence panic into a 3-second export.*
2. **Pre-Hire Nexus Cost Previews:** A Slack slash-command (`/juristrack cost [ZIP Code]`). Before HR extends an offer to a remote employee in a new state, they can instantly see the exact annualized cost of local compliance and licensing for that specific zip code.
3. **Audit-Proof GL Attachments:** When JurisTrack writes the Vendor Bill back to NetSuite or QBO, it doesn't just pass the numbers—it automatically attaches the Vertex AI-processed PDF of the municipal notice directly to the ledger entry. When auditors ask for proof, it’s already natively in the ERP.
4. **"Zero Silent Failures" Dead-Letter Dashboard:** A beautiful, real-time widget showing agents actively retrying tasks (e.g., "Retrying Denver Portal: IP Rate Limit"). It visually proves the system is working hard in the background, building immense trust.

## Scope Mapping: The 12-Month Trajectory

* **Current State (The Baseline):** Companies rely on manual spreadsheets, physical mail bottlenecks, retroactive penalty discoveries, and manual GL data entry. Complete operational chaos.
* **Launch Plan (Months 1-6): The Automated System of Record**
  * *M1-M2:* Establish MongoDB Atlas schema with strict envelope encryption. Build Google Vertex AI document parsing pipelines. Establish HRIS/ERP read connections.
  * *M3-M4:* Deploy initial crewAI agents (Python 3.11) targeting the top 500 municipalities. Build the FastAPI payment clearinghouse and virtual card orchestration.
  * *M5-M6:* Deliver the React + TypeScript frontend dashboard for entity CRUD operations, human-in-the-loop fallback queues, and Slack approval workflows. Launch Beta.
* **12-Month Ideal: The Autonomous Infrastructure**
  * Expand agentic coverage to 5,000+ local jurisdictions. 
  * Shift from a "software tool" to a "managed liability platform"—offering SLA-backed penalty guarantees.
  * Launch a public "Local Compliance API" derived from our crewAI scraping data, effectively becoming the Plaid/Stripe for municipal tax infrastructure.

## Zero Silent Failures: Architecture as Empathy
Given our reliance on 2005-era municipal websites and physical mail, external failures are guaranteed. Our architecture must absorb this chaos gracefully. 
* **AI Degradation:** If Vertex AI confidence on a scanned notice drops below 95%, the system does not guess. It immediately halts and routes the document to a human-in-the-loop UI.
* **Agent Blocks:** If a crewAI agent hits an unexpected CAPTCHA or the municipal portal UI changes, it triggers an exponential backoff. After 3 attempts, it alerts our internal data operations team to fix the agent script while keeping the user informed. 
* **ERP Sync Drops:** If a municipal payment clears but the QBO API rate-limits the write-back, a dead-letter queue automatically retries the sync. 

No missed payments. No dropped data. Absolute transparency.

## Business Impact & Competitive Positioning
This is a massive wedge strategy into the Office of the CFO. 

While incumbents like Avalara focus strictly on transactional Sales Tax, they completely ignore the hyper-fragmented "long tail" of local franchise taxes, municipal fees, and occupational licenses. By solving the ugliest, most manual, least-glamorous problem in the accounting department, JurisTrack earns the right to become the central nervous system for all entity management.

The business opportunity is a high-ACV, high-retention SaaS product with a zero-churn profile. Once a mid-market company wires JurisTrack into their HRIS, NetSuite/QBO environment, and banking stack, it becomes structural. Furthermore, our proprietary database of mapped municipal portals—maintained by our crewAI agents—creates an insurmountable data moat that legacy competitors cannot replicate without completely rebuilding their architecture. 

We aren't just saving accountants 20 hours a month; we are structurally derisking mid-market enterprise growth.

## Engineering Plan

# Engineering Plan: JurisTrack

## 1. Architecture Overview

JurisTrack is an autonomous legal entity infrastructure layer. The architecture is explicitly designed around the "Zero Silent Failures" principle. It relies on asynchronous processing for long-running or external-facing tasks (AI inference, web scraping, ERP syncing) and a synchronous API for deterministic CRUD and UI operations. 

### System Boundaries and Components

```ascii
                                +-------------------+
                                |   External HRIS   |
                                | (Gusto/Rippling)  |
                                +---------+---------+
                                          | Webhooks
+-------------------+           +---------v---------+           +-------------------+
|                   |           |                   |           |                   |
|  React + TS SPA   +<--------->+  FastAPI Gateway  +<--------->+ QBO / NetSuite    |
|  (Controller UI)  |   REST    |  (Sync API Node)  |   REST    | External APIs     |
|                   |           |                   |           |                   |
+---------+---------+           +---------+---------+           +-------------------+
          |                               |                               ^
          v                               v                               |
+-------------------+           +---------+---------+                     |
|                   |           |                   |                     |
|   Slack Bot API   |           |  MongoDB Atlas    |                     |
|  (Approvals/Pre-  |           | (Primary Datastore|                     |
|   Hire Nexus)     |           |  w/ KMS Envelope  |                     |
|                   |           |   Encryption)     |                     |
+-------------------+           +---------+---------+                     |
                                          ^                               |
                                          |                               |
                                +---------+---------+           +---------+---------+
                                |                   |           |                   |
                                | Redis / Celery    +---------->+ Payment Gateway   |
                                |  Message Broker   |           |  (Stripe / Lob)   |
                                |                   |           |                   |
                                +---------+---------+           +-------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
+-------v-------+                 +-------v-------+                 +-------v-------+
|  Worker Node  |                 |  Worker Node  |                 |  Worker Node  |
| (crewAI Sync) |                 | (Vertex AI)   |                 | (ERP / Pay)   |
|  Playwright   |                 |  Document AI  |                 |  Sync Engine  |
+-------+-------+                 +-------+-------+                 +-------+-------+
        |                                 |
+-------v-------+                 +-------v-------+
|   Municipal   |                 | Google Cloud  |
|   Websites    |                 | Storage (PDFs)|
+---------------+                 +---------------+
```

### Technology Stack Decisions
*   **Backend:** Python 3.11 + FastAPI. *Rationale:* Native `asyncio` support for high-throughput I/O. Python is mandatory for native crewAI integration and the vast ML/AI ecosystem.
*   **Database:** MongoDB Atlas. *Rationale:* Document flexibility is required for highly unstructured municipal outputs, but we will enforce strict JSON schemas at the application layer (e.g., `Decimal128` for currency).
*   **Frontend:** React + TypeScript + Vite. *Rationale:* Strict typing on the frontend prevents UI-driven data corruption.
*   **AI Engine (Parsing):** Google Vertex AI. *Rationale:* Best-in-class OCR and structured data extraction from archaic, low-quality municipal mail PDFs.
*   **Agent Engine:** crewAI + Playwright. *Rationale:* Role-based agent orchestration for traversing unstable municipal DOMs.
*   **Queue/Broker:** Redis + Celery (or ARQ). *Rationale:* Required for dead-letter queues (DLQ), explicit retries, and exponential backoff for unpredictable external systems.

### Data Flow Diagram: Agentic Portal Sync (Happy, Empty, Error Paths)

```ascii
[Cron Trigger] -> [FastAPI Queues Task] -> [Redis]
                       |
                 [Worker Picks Task]
                       |
               (Decrypt Credentials)
                       |
               [Playwright / crewAI] --> (Target: SF Portal)
                       |
      +----------------+----------------+-----------------+
      | (Happy Path)   | (Empty Path)   | (Error Path)    |
      v                v                v                 v
[Extracts $150]   [Extracts $0.00]  [Site Redesigned] [Invalid Creds]
      |                |                |                 |
      v                v                v                 v
[Save Decimal128] [Save Decimal128] [Take Screenshot] [Log Error]
      |                |                |                 |
      v                v                v                 v
[Update DB State] [Update DB State] [Flag For Human]  [Flag For Human]
[Completed]       [Completed]       [Requires_Intervention] [Failed_Auth]
      |                |                |                 |
      v                v                v                 v
[Trigger Payment] [Do Nothing]      [Slack Alert]     [Slack Alert]
```

---

## 2. Component Breakdown & State Machines

### 2.1 NexusFootprint State Machine
*Purpose:* Track economic/physical presence triggers from HRIS.

```ascii
                             +------------+
                             |  Detected  | <---------------------+
                             +-----+------+                       |
                                   | (Automated crewAI Trigger)   | (crewAI Timeout/Fail)
                             +-----v------+                       |
                             |Investigating+----------------------+
                             +-----+------+
                                   | (crewAI Mapping Success)
                             +-----v------+
                             |  Action_   |
                             |  Required  |
                             +--+------+--+
               (User Dismisses) |      | (User Marks Registered)
              +-----------------+      +-----------------+
              v                                          v
        +-----------+                              +------------+
        |  Ignored  |                              | Registered |
        | (Terminal)|                              | (Terminal) |
        +-----------+                              +------------+
```

### 2.2 ComplianceNotice State Machine
*Purpose:* Track lifecycle of uploaded physical mail to payment staging.

```ascii
 [Uploaded] --(GCS Upload)--> [Extracting] --(Vertex Callback)--> [Needs_Review]
                                                                        |
                                                +-----------------------+-----------------------+
                                                | (User Rejects)                                | (User Approves)
                                                v                                               v
                                            [Rejected]                                      [Approved]
                                            (Terminal)                                      (Terminal) --> Spawns PortalSyncTask
```

### 2.3 PortalSyncTask State Machine
*Purpose:* Execute web scraping via crewAI.

```ascii
 [Pending] --(Worker Picks Up)--> [Running]
                                      |
         +----------------------------+-----------------------------+
         | (Success)                  | (Bad Password)              | (DOM Changed / Timeout)
         v                            v                             v
    [Completed]                 [Failed_Auth]          [Requires_Human_Intervention]
    (Terminal)                    (Terminal)                    (Terminal / Manual Override)
```

### 2.4 CompliancePayment State Machine
*Purpose:* Ensure zero dropped transactions across Gateways and ERPs.

```ascii
 [Draft] --(User Approves)--> [Processing] --(Webhook)--> [Cleared]
                                |                             |
                            (Gateway Reject)            (Auto-Trigger ERP)
                                |                             v
                                |                   [Ledger_Sync_Pending] <-----+
                                |                             |                 | (Retry 1..3)
                                |                     +-------+-------+         |
                                |          (200 OK)   |               | (5xx)   |
                                v                     v               +---------+
                            [Failed] <--------- [Ledger_Synced]       | (Max Retries Met)
                           (Terminal)             (Terminal)          v
                                                                   [Failed]
```

### 2.5 API Contract Sketches (Strict Inputs)

**`PUT /api/v1/notices/{id}/review`**
*   **Payload:**
    ```json
    {
      "dueDate": "2024-02-28T00:00:00Z",
      "feeAmount": "250.00", // Enforced string to parse into Decimal128
      "status": "Approved"   // Literal: 'Approved' | 'Rejected'
    }
    ```
*   **Responses:** `200 OK` (Success), `409 Conflict` (If state is already terminal), `422 Unprocessable Entity` (If `feeAmount` < 0 or invalid decimal).

**`POST /api/v1/payments/{id}/sync-ledger`**
*   **Payload:** `{}` (Empty, ID in path)
*   **Responses:** `200 OK` (Sync successful, returns `ledgerSyncId`), `409 Conflict` (If state != `Ledger_Sync_Pending`), `502 Bad Gateway` (ERP timeout).

---

## 3. Implementation Phases (Jira Epics & Stories)

### Epic 1: Foundation & Security (Size: M)
*Dependencies: None*
*   **Story 1.1:** Setup FastAPI + MongoDB Atlas infrastructure via Terraform.
*   **Story 1.2:** Implement JWT Auth and RBAC middleware.
*   **Story 1.3:** Implement KMS Envelope Encryption for `PortalCredential` storage (Keys never leave memory; stored as ciphertext in DB).
*   **Story 1.4:** Build Base API CRUD for `Tenants` and canonical `Jurisdictions`.

### Epic 2: AI Notice Ingestion (Size: L)
*Dependencies: Epic 1*
*   **Story 2.1:** Implement GCS bucket upload logic and `ComplianceNotice` MongoDB model.
*   **Story 2.2:** Integrate Google Vertex AI Document AI API and map output to strictly typed fields.
*   **Story 2.3:** Build state machine enforcer for `ComplianceNotice` (`Uploaded` -> `Approved`).
*   **Story 2.4:** Build React UI for side-by-side PDF viewing and manual overrides (HITL).

### Epic 3: Dynamic Nexus Discovery (Size: M)
*Dependencies: Epic 1*
*   **Story 3.1:** Implement webhook ingest endpoint for HRIS payloads (Gusto/Rippling).
*   **Story 3.2:** Build crewAI "Jurisdiction Analyst" agent using Python 3.11 to map zip codes to local taxes.
*   **Story 3.3:** Implement `NexusFootprint` state machine and Slack notification bot.
*   **Story 3.4:** Build Slack slash-command `/juristrack cost [ZIP Code]` for Pre-Hire Cost Previews.

### Epic 4: Agentic Portal Sync (Size: XL)
*Dependencies: Epic 1*
*   **Story 4.1:** Setup Celery/Redis async worker infrastructure for long-running scraping tasks.
*   **Story 4.2:** Build base crewAI Playwright agent with strict 120-second timeout and screenshot capture on failure.
*   **Story 4.3:** Implement `PortalSyncTask` state machine and DLQ for `Requires_Human_Intervention`.
*   **Story 4.4:** Write individual agent routing logic for the Top 10 High-Volume Municipalities (e.g., SF, Denver, Seattle).

### Epic 5: Payments & Ledger Reconciliation (Size: XL)
*Dependencies: Epic 1, Epic 2*
*   **Story 5.1:** Integrate Stripe Issuing / Virtual Card API for payment execution.
*   **Story 5.2:** Build AI Vendor Mapping tool (crewAI agent) to map messy ERP vendors to JurisTrack canonical IDs.
*   **Story 5.3:** Integrate NetSuite REST API and QBO API for Vendor Bill creation with PDF attachments.
*   **Story 5.4:** Implement `CompliancePayment` state machine with 3x exponential backoff retry for ERP sync failures.

### Epic 6: Polish & "M&A Ready" Data Room (Size: S)
*Dependencies: Epics 1-5*
*   **Story 6.1:** Build React "M&A Ready" export button (ZIP compilation of all paid receipts/Good Standings).
*   **Story 6.2:** Build "Zero Silent Failures" Dead-Letter Dashboard UI.
*   **Story 6.3:** Implement end-to-end performance and penetration testing.

---

## 4. Data Model

All DB interaction goes through an ODM (e.g., Beanie or Motor) to enforce schemas.

### Core Entities
*   **`Tenants`**: Root isolation entity.
*   **`Jurisdictions`**: Canonical list managed by JurisTrack (e.g., "City of Denver").
*   **`PortalCredentials`**:
    *   `tenantId`, `jurisdictionId`
    *   `encryptedPayload` (Binary, KMS encrypted, contains username/password)
*   **`NexusFootprint`**:
    *   Strict validation: `postalCode` must match `^\d{5}(-\d{4})?$`.
    *   Compound unique index: `{tenantId: 1, postalCode: 1, triggerType: 1}`.
*   **`ComplianceNotice`**:
    *   Strict type: `feeAmount` stored as `Decimal128`.
    *   Validation: `confidenceScore` restricted to `0.0 <= x <= 1.0`.
*   **`PortalSyncTask`**:
    *   Index: `{ status: 1, scheduledFor: 1 }` (Critical for worker queue polling).
*   **`CompliancePayment`**:
    *   Strict type: `amount` stored as `Decimal128` (Must be > 0.0).
    *   Index: `{ tenantId: 1, status: 1, erpVendorId: 1 }`.

### Migration Strategy
*   Schema changes are additive. Breaking changes require a dual-write phase.
*   Because `Decimal128` conversion from legacy floats can cause precision loss, the system blocks insertion of standard floats at the API layer.

---

## 5. Error Handling & Failure Modes

Every component is designed with the assumption that the downstream dependency will fail.

| Component | Failure Mode | Detection | Handling Strategy | Error Classification |
| :--- | :--- | :--- | :--- | :--- |
| **Vertex AI** | Blurry/Handwritten PDF yields garbage data. | `confidenceScore` < 0.90 | Degrade to manual entry. Halt auto-approval. Flag fields in UI. | Minor (Expected) |
| **crewAI Agent** | Municipal site adds Cloudflare CAPTCHA. | Playwright timeout / DOM missing. | Take screenshot. Transition to `Requires_Human_Intervention`. Alert Ops. | Major |
| **crewAI Agent** | Rate limited by city server (429). | HTTP 429 response. | Exponential backoff. Retry up to 3 times before failing. | Minor |
| **QBO/NetSuite API**| API goes down or hits rate limit during GL write-back. | HTTP 5xx or 429 during `Ledger_Sync_Pending`.| Dead-Letter Queue (DLQ). Retry at 1m, 5m, 30m. Retain `Pending` state. | Major |
| **Payment Gateway** | NSF (Insufficient Funds) in Wallet. | Synchronous 402/Reject from Stripe. | Mark `Failed`. Alert Controller immediately via Slack. | Critical |
| **DB / KMS** | KMS key unavailable, cannot decrypt creds. | API Exception. | Circuit breaker trips. Pause all `PortalSyncTask` workers. | Critical |

---

## 6. Test Strategy

We cannot test against live production ERPs or live municipal portals in CI/CD.

*   **Unit Testing (Pytest):**
    *   State machine transitions (asserting invalid transitions throw `409 Conflict`).
    *   Financial math rounding (`Decimal128` accuracy).
    *   Input payload validation (Pydantic models).
*   **Integration Testing:**
    *   **Mocking APIs:** Responses from QBO, NetSuite, and Vertex AI are mocked using VCR.py to replay exact HTTP payloads.
    *   **Database:** Use a local MongoDB container (Testcontainers) for index and query validation.
*   **E2E / Agent Testing:**
    *   We maintain static HTML snapshots of the Top 50 municipal portals in our test suite.
    *   Playwright agents run against these local static HTML files in CI/CD to ensure DOM parsing logic remains stable.
*   **Edge Case Matrix:**
    *   *Nil path:* HRIS sends address with missing ZIP code -> Rejected 400.
    *   *Empty path:* crewAI finds table but `$0.00` balance -> Processed correctly as zero-dollar fee.
    *   *Error path:* PDF uploaded is actually an executable -> Rejected at GCS layer via MIME type validation.

---

## 7. Security & Trust Boundaries

*   **Envelope Encryption:** Passwords for municipal portals are encrypted using AWS KMS/GCP KMS. The DEK (Data Encryption Key) is stored in MongoDB, but the KEK (Key Encryption Key) remains in KMS. If MongoDB is compromised, the credentials remain mathematically secure.
*   **Network Boundaries:**
    *   React UI interacts *only* with the API Gateway.
    *   Worker nodes operate in a private subnet. They have outbound internet access (to scrape sites) but *no* inbound access.
    *   Database is strictly bound to the VPC; no public IP.
*   **Data Classification:**
    *   **PII:** Employee addresses (from HRIS). Stored encrypted, automatically redacted from logs.
    *   **Financial Data:** Tax IDs, EINs, Bank Accounts. Strictly encrypted at rest.
*   **Input Validation:** File uploads must pass `libmagic` MIME-type checks and size limits (Max 5MB) to prevent maliciously crafted payloads crashing Vertex AI.

---

## 8. Deployment & Rollout

*   **Infrastructure as Code:** All infrastructure defined in Terraform.
*   **Sequence:**
    1. Run automated test suite (Pytest + Playwright).
    2. Deploy DB migrations (if any) using a backward-compatible schema approach.
    3. **Blue/Green Deployment:** Spin up new FastAPI pods and Worker pods.
    4. Shift 10% of HTTP traffic to new pods.
    5. Monitor `5xx` error rates and DLQ depth.
    6. If stable for 5 minutes, shift 100% traffic.
    7. Terminate old pods.
*   **Rollback Plan:**
    *   *Trigger:* Spikes in 500s or Worker exceptions > 1%.
    *   *Action:* Revert load balancer traffic back to Blue pods (takes < 5 seconds).
    *   *DB:* Because migrations are strictly additive, reverting code does not break the DB schema.
*   **Feature Flags:** (via LaunchDarkly / Unleash)
    *   `enable_auto_erp_sync`: Kept FALSE for new clients until Vendor mapping is human-verified.
    *   `enable_live_payments`: Kept FALSE in staging environments.

---

## 9. Observability

*   **Logging:**
    *   Strict structured JSON logging.
    *   Required keys: `trace_id`, `tenant_id`, `component` (e.g., `crewai_worker`), `level`.
    *   *Security rule:* `password`, `ssn`, `ein` explicitly scrubbed via custom log formatter.
*   **Metrics (Prometheus / Datadog):**
    *   `juristrack_agent_success_rate`: Percentage of `PortalSyncTask` runs reaching `Completed`. (Alert if < 85%).
    *   `juristrack_dlq_depth`: Number of items in Dead Letter Queues. (Alert if > 0 for > 30 mins).
    *   `juristrack_vertex_confidence_avg`: Rolling average of AI extraction confidence.
*   **Debugging Guide (Common Scenario: Agent hitting "Requires Intervention"):**
    1. Locate `taskId` in logs.
    2. Pull `screenshotUrl` from GCS to visually inspect what the agent saw.
    3. Check `agentLog` dump in MongoDB for exact Playwright step failure.
    4. Update Playwright CSS selector locally -> run against snapshot -> deploy hotfix.

## Problem Statement

The management of local US corporate compliance is fundamentally broken, characterized by an extreme asymmetry of risk: a forgotten $50 municipal fee can silently revoke a company’s "Certificate of Good Standing," instantly derailing a $100M M&A transaction, stalling a funding round, or triggering catastrophic operational lockouts. Finance leaders at mid-market companies operate in a constant state of anxiety regarding this "invisible administrative debt," knowing that their existing systems are ill-equipped to handle the sheer fragmentation of local tax and licensing authorities.

**The "Why Now" Trigger: The Remote Work Nexus Explosion**
Historically, local compliance was a static problem bounded by physical office locations. However, the post-COVID shift to distributed workforces has radically expanded the operational footprint of mid-market ($10M–$150M ARR) companies. Hiring a single remote employee in a new city or state silently triggers a web of archaic local tax and licensing requirements across more than 10,000 distinct US municipal jurisdictions. 

Currently, accounting and compliance teams are trapped in a reactive, manual baseline characterized by four critical operational failure points:

*   **Blind Nexus Discovery:** Corporate systems are structurally disconnected. When an HR department hires a remote employee or Sales closes a deal in a new zip code, the Finance department rarely knows they have triggered a new local tax nexus. Consequently, companies rely on "blind discovery," often only learning about their obligation to register for a local business license or franchise tax when a penalty notice arrives months later.
*   **The Analogue Bottleneck (Physical Mail):** Local jurisdictions are technologically archaic and communicate primarily via physical mail. Vital regulatory notices regarding fee changes, account numbers, or rigid filing deadlines are mailed to generic corporate addresses. These unstructured paper documents frequently sit unread on a receptionist's desk or get lost in mail-forwarding processes, completely bypassing the finance team's compliance calendar.
*   **The "Last Mile" Execution Nightmare:** Merely paying a trivial municipal fee (e.g., the Denver Occupational Privilege Tax or the San Francisco Gross Receipts Tax) is an operational nightmare. To remit a $50 payment, a highly paid accountant must manually track down shared credentials, navigate fragile, poorly maintained web portals built in the mid-2000s, or resort to physically mailing a paper check. 
*   **Reconciliation Drag:** The sheer volume of localized micro-payments creates immense data-entry friction. Manually categorizing hundreds of discrete municipal portal receipts, extracting the relevant data, and logging the corresponding Vendor Bills or Journal Entries into enterprise ERPs (like NetSuite or QuickBooks Online) consumes valuable accounting capacity.

**Quantifiable Business Impact**
The current paradigm is unsustainable for scaling mid-market enterprises. It forces highly compensated Corporate Controllers and Accounting Managers to waste an average of 20+ hours per month acting as administrative data-entry clerks. More severely, the reliance on retroactive penalty discovery and manual human intervention ensures a 100% statistical likelihood of human error over a long enough timeline. The resulting non-compliance penalties, combined with the catastrophic business risk of losing legal entity standing during critical due diligence periods, demands a shift from reactive manual tracking to an autonomous, zero-failure infrastructure.

## User Personas

**1. Sarah: The Strategic Risk Manager (Primary Buyer & Approver)**
*   **Role:** Corporate Controller / VP of Finance at a mid-market SaaS company ($50M ARR).
*   **Demographics:** 35–45 years old, CPA credentialed, highly experienced with enterprise ERPs (NetSuite), but highly averse to unpredictable manual data entry.
*   **Context & Usage:** Sarah does not want to be in the JurisTrack app daily. She views compliance as "invisible administrative debt" that carries catastrophic asymmetrical risk (e.g., derailing an upcoming Series C or M&A event). She interacts with the system primarily via asynchronous Slack approvals and relies heavily on the "Zero Silent Failures" architecture to trust that the system is functioning without her intervention. 
*   **Pain Points:**
    *   Lives in constant fear of "blind nexus discovery"—discovering a missed tax liability months after the fact during an audit.
    *   Resents her highly paid team spending 20+ hours a month manually paying $50 municipal fees on clunky government websites.
*   **Goals & Outcomes:**
    *   Attain 100% compliance visibility with zero late fees.
    *   Achieve a 1-tap approval workflow for fee execution via Slack.
    *   Generate a comprehensive, audit-ready data room (Certificates of Good Standing) instantly via the "M&A Ready" export feature.

**2. Marcus: The Tactical Operator (Daily Power User)**
*   **Role:** Accounting Manager / Senior Staff Accountant.
*   **Demographics:** 28–35 years old, tech-savvy, manages the day-to-day month-end close process in QBO or NetSuite.
*   **Context & Usage:** Marcus is the primary daily user of the JurisTrack React dashboard. He handles the physical mail ingestion, manages the Human-in-the-Loop (HITL) exception queues, and ensures the downstream ERP syncs are accurate. He appreciates complete transparency into the system's background tasks.
*   **Pain Points:**
    *   Frustrated by the manual reconciliation drag required to enter hundreds of micro-transactions into the GL accurately.
    *   Burdened by physical mail bottlenecks, where crucial regulatory notices sit on the receptionist's desk.
*   **Goals & Outcomes:**
    *   Rely on Vertex AI to seamlessly ingest and parse physical mail without requiring manual data correction.
    *   Utilize the "Dead-Letter Dashboard" to monitor agent retries and API sync statuses, ensuring no dropped ledger entries.
    *   Automate the creation of fully categorized Vendor Bills and Journal Entries directly into NetSuite/QBO, completely eliminating manual reconciliation.

**3. Elena: The Cross-Functional Catalyst (Upstream Trigger User)**
*   **Role:** VP of People / Head of HR.
*   **Demographics:** 30–45 years old, manages the Gusto or Rippling HRIS platform, rarely interacts with accounting software directly.
*   **Context & Usage:** Elena is the primary source of the "nexus footprint" expansion. She interacts with JurisTrack indirectly via HRIS webhooks or directly via the Slack integration during the hiring process.
*   **Pain Points:**
    *   Lacks visibility into the hidden financial costs (local licensing, franchise taxes) of hiring remote talent in new, unregistered zip codes.
    *   Experiences friction when Finance retroactively pushes back on remote hires due to sudden compliance burdens.
*   **Goals & Outcomes:**
    *   Gain instant, pre-hire visibility into localized compliance costs via the `/juristrack cost [ZIP Code]` Slack slash-command.
    *   Ensure Finance is automatically notified (Dynamic Nexus Discovery) the moment a new employee address is logged in the HRIS, eliminating cross-departmental communication gaps.

**4. David: The External Administrator (Multi-Tenant Power User)**
*   **Role:** CPA / Outsourced Controller at an external accounting firm.
*   **Demographics:** 40–55 years old, highly organized, manages compliance for a portfolio of 15–30 different mid-market client entities.
*   **Context & Usage:** David leverages JurisTrack to scale his firm's entity management services. He requires strict data segregation (multi-tenancy) but unified visibility across his entire client roster.
*   **Pain Points:**
    *   Suffers extreme context-switching penalties when logging into 50 different municipal portals on behalf of 20 different clients.
    *   Bears professional liability for missed filing deadlines across highly fragmented client portfolios.
*   **Goals & Outcomes:**
    *   Manage a unified dashboard that aggregates "Action Required" items across all managed tenants.
    *   Rely on autonomous crewAI agents to securely scrape and monitor fee updates across the entire client portfolio simultaneously without adding administrative headcount to his firm.

## Functional Requirements

### 1. Dynamic Nexus Discovery & HRIS Integration

**FR-001: HRIS Webhook Ingestion**
*   **Priority:** SHALL
*   **Description:** The system ingests employee address changes or new hire events via webhooks from supported HRIS platforms (e.g., Gusto, Rippling).
*   **Acceptance Criteria:**
    *   **Given** an active HRIS integration exists for a tenant,
    *   **When** a new employee is hired or an address is updated,
    *   **Then** the system extracts the `postalCode` and triggers the NexusFootprint evaluation process.
*   **API Endpoint:** `POST /api/v1/webhooks/hris/events`

**FR-002: Nexus Footprint Evaluation**
*   **Priority:** SHALL
*   **Description:** The system maps incoming 5-digit zip codes against the JurisTrack canonical database of US tax jurisdictions to determine potential tax liabilities.
*   **Acceptance Criteria:**
    *   **Given** a valid `postalCode` (e.g., "94105"),
    *   **When** evaluated against the canonical database,
    *   **Then** the system creates a new `NexusFootprint` record with the status `Action_Required` if the jurisdiction is not already marked as `Registered` for that tenant.

**FR-003: Pre-Hire Cost Preview (Slack Integration)**
*   **Priority:** SHOULD
*   **Description:** The system provides a Slack slash-command allowing users to query estimated annualized compliance costs for a specific zip code prior to hiring.
*   **Acceptance Criteria:**
    *   **Given** a user types `/juristrack cost [5-digit zip]` in an authorized Slack workspace,
    *   **When** the command is executed,
    *   **Then** the system replies with an itemized list of potential state, county, and municipal fees based on the canonical database.

### 2. Notice Ingestion & AI Parsing

**FR-004: Physical Mail PDF Upload**
*   **Priority:** SHALL
*   **Description:** The system allows users to upload scanned physical mail (PDF format) via the React frontend.
*   **Acceptance Criteria:**
    *   **Given** an authenticated user on the Dashboard,
    *   **When** a valid PDF file (≤5MB) is uploaded,
    *   **Then** the system saves the file to Google Cloud Storage, creates a `ComplianceNotice` record with status `Uploaded`, and triggers the extraction workflow.
*   **API Endpoint:** `POST /api/v1/notices/upload`

**FR-005: AI Data Extraction (Vertex AI)**
*   **Priority:** SHALL
*   **Description:** The system utilizes Google Vertex AI to extract structured data from the unstructured PDF notice.
*   **Acceptance Criteria:**
    *   **Given** a `ComplianceNotice` in the `Uploaded` state,
    *   **When** processed by the extraction worker,
    *   **Then** the system populates the `Jurisdiction Name`, `Account ID`, `Due Date`, and `Fee Amount` fields, and transitions the status to `Needs_Review`.

**FR-006: Human-in-the-Loop (HITL) Review Queue**
*   **Priority:** SHALL
*   **Description:** The system provides a UI queue for users to review AI-extracted data alongside the original PDF and approve or reject the extraction.
*   **Acceptance Criteria:**
    *   **Given** a `ComplianceNotice` with the status `Needs_Review`,
    *   **When** the user modifies (if necessary) and submits the data via the UI,
    *   **Then** the system updates the record, transitions the state to `Approved` or `Rejected`, and if approved, triggers the `PortalSyncTask`.
*   **API Endpoint:** `PUT /api/v1/notices/{id}/review`
    *   **Request Schema:** `{ "dueDate": "string(date-time)", "feeAmount": "string", "status": "Approved|Rejected" }`

### 3. Agentic Portal Sync & Execution

**FR-007: Autonomous Portal Login & Scraping**
*   **Priority:** SHALL
*   **Description:** The system deploys crewAI Playwright agents to securely log into municipal web portals and scrape the current account balance to verify the uploaded notice.
*   **Acceptance Criteria:**
    *   **Given** a spawned `PortalSyncTask` and valid, decrypted `PortalCredentials`,
    *   **When** the worker node executes the task,
    *   **Then** the agent navigates the portal, extracts the current outstanding balance, and updates the task status to `Completed` if the balance matches or is $0.00.

**FR-008: Agent Failure Escalation**
*   **Priority:** SHALL
*   **Description:** The system flags tasks requiring human intervention when agents encounter unsolvable blockers (e.g., CAPTCHAs, DOM changes).
*   **Acceptance Criteria:**
    *   **Given** a running `PortalSyncTask`,
    *   **When** the agent times out or fails to locate the target DOM elements after predetermined retries,
    *   **Then** the system captures a screenshot, saves it to GCS, transitions the task to `Requires_Human_Intervention`, and alerts the internal ops team.

### 4. Payments & ERP Reconciliation

**FR-009: Payment Execution via Virtual Card**
*   **Priority:** SHALL
*   **Description:** The system issues a virtual card payment via the integrated Payment Gateway to settle the municipal fee.
*   **Acceptance Criteria:**
    *   **Given** a `CompliancePayment` in the `Draft` state and a matching approved `PortalSyncTask`,
    *   **When** the user clicks "Approve Payment" via the UI or Slack,
    *   **Then** the system transitions the state to `Processing` and triggers the Gateway API to process the exact `feeAmount`.

**FR-010: ERP Ledger Write-Back**
*   **Priority:** SHALL
*   **Description:** The system creates a fully categorized Vendor Bill or Journal Entry in the tenant's connected ERP upon payment clearance.
*   **Acceptance Criteria:**
    *   **Given** a `CompliancePayment` transitions to the `Cleared` state,
    *   **When** the ERP sync worker executes,
    *   **Then** the system pushes a ledger entry to the ERP (QBO/NetSuite) tagged with the configured GL Account and Department, attaches the original PDF notice to the ERP record, and updates the state to `Ledger_Synced`.
*   **API Endpoint:** `POST /api/v1/payments/{id}/sync-ledger`

### 5. Compliance Dashboard & UI Capabilities

**FR-011: Entity & Credential Management (CRUD)**
*   **Priority:** SHALL
*   **Description:** The system allows Administrative users to manage legal entities, map them to Canonical Jurisdictions, and input municipal portal credentials.
*   **Acceptance Criteria:**
    *   **Given** an authenticated user with Admin RBAC privileges,
    *   **When** creating a new jurisdiction mapping,
    *   **Then** the system accepts the portal username and password, encrypts them immediately via the backend API, and stores them in the `PortalCredentials` collection.

**FR-012: The "M&A Ready" Data Room Export**
*   **Priority:** SHOULD
*   **Description:** The system provides a single-click export function compiling historical compliance proof for due diligence.
*   **Acceptance Criteria:**
    *   **Given** an authenticated user on the Dashboard,
    *   **When** the user clicks "Export Data Room",
    *   **Then** the system generates and downloads a ZIP file containing all uploaded PDFs and proof-of-payment receipts for the trailing 12 months, organized in folders by Jurisdiction.

## Non-Functional Requirements

### 1. Security & Data Privacy
*   **Data at Rest Encryption:** All sensitive system credentials (e.g., municipal portal passwords, API keys) MUST be encrypted at rest in MongoDB using envelope encryption (AWS KMS or GCP KMS). The Key Encryption Key (KEK) MUST never leave the KMS, and the Data Encryption Key (DEK) MUST only exist in memory during active worker execution.
*   **Data in Transit Encryption:** All data transmitted between the React UI, FastAPI Gateway, and external APIs (NetSuite, QBO, Municipal portals) MUST utilize TLS 1.2 or higher.
*   **Role-Based Access Control (RBAC):** The system MUST enforce strict JWT-based RBAC. Financial capabilities (e.g., approving payments) MUST be restricted to the "Controller/Admin" role, while "Operator" roles are restricted to viewing and resolving HITL (Human-In-The-Loop) queues.
*   **Compliance Readiness:** The application architecture and deployment pipelines MUST be configured to support SOC 2 Type II compliance from day one (e.g., automated vulnerability scanning, strictly separated environments, no developer SSH access to production).
*   **PII Handling:** Employee addresses ingested via HRIS webhooks MUST be treated as Personally Identifiable Information (PII) and MUST be automatically redacted from all application logs and tracing outputs.

### 2. Performance & Latency
*   **API Response Times:** 95% of synchronous, user-facing API requests (e.g., loading the dashboard, approving a payment) MUST return within <500ms (p95 latency).
*   **Agent Scraping Timeouts:** crewAI Playwright agents MUST have a hard execution timeout of 120 seconds per `PortalSyncTask`. If the DOM is unresponsive after 120 seconds, the task MUST gracefully terminate and transition state.
*   **AI Inference Latency:** The system MUST complete Vertex AI document parsing for standard single-page PDF uploads within 5 seconds (p90) to ensure a fluid user experience during manual uploads.
*   **Asynchronous Message Throughput:** The Redis/Celery queue MUST be capable of processing a minimum of 50 concurrent `PortalSyncTasks` without degrading the primary FastAPI Gateway's performance.

### 3. Reliability & Availability
*   **System Uptime SLA:** The core web application and API gateway MUST maintain a 99.9% uptime SLA, excluding planned maintenance windows.
*   **Message Persistence (RPO):** The system MUST enforce a Recovery Point Objective (RPO) of <5 minutes. All asynchronous task states (e.g., pending payments, queued portal syncs) MUST be persisted to MongoDB before execution to prevent data loss during worker node crashes.
*   **Queue Resiliency:** The architecture MUST utilize Dead-Letter Queues (DLQ) for all external integrations (ERP syncs, Payment clearing). Unhandled exceptions MUST NOT result in dropped transactions; they must be explicitly routed to the DLQ for manual intervention or automated exponential backoff retries.

### 4. Scalability
*   **Concurrent Users:** At launch, the system MUST support 500 concurrently active daily users (Controllers and CPAs) interacting with the dashboard without performance degradation.
*   **Entity & Jurisdiction Volume:** The database schema and index strategies MUST seamlessly support 5,000 active mapped entities and 500 distinct municipal jurisdictions at launch, with query performance remaining under the 500ms p95 threshold.
*   **Stateless Scaling:** All FastAPI web nodes and Celery/Playwright worker nodes MUST be entirely stateless, allowing horizontal scaling via Kubernetes (HPA) based on CPU utilization or queue depth.

### 5. Data Retention & Auditability
*   **Immutable Audit Logs:** Every state change to a `ComplianceNotice`, `NexusFootprint`, or `CompliancePayment` MUST generate an immutable audit log entry containing the `userId`, `timestamp`, `previousState`, and `newState`.
*   **Document Retention:** All ingested physical mail (PDFs) stored in Google Cloud Storage, along with their associated metadata and extraction confidence scores, MUST be retained for a minimum of 7 years to satisfy standard IRS and local regulatory audit requirements.
*   **Log Scrubbing:** The logging formatter MUST explicitly scrub sensitive JSON keys (`password`, `ssn`, `ein`, `account_number`) before transmitting logs to the observability platform (e.g., Datadog, Prometheus).

## Edge Cases

### 1. Dynamic Nexus Discovery (HRIS to JurisTrack)

*   **Boundary Condition: Overlapping Jurisdictions**
    *   *Scenario:* An HRIS address triggers multiple tax nexus footprints simultaneously (e.g., State Tax, County Tax, and a hyper-local City District Tax).
    *   *System Behavior:* The system evaluates the zip code against a deeply mapped canonical database, spawning separate `NexusFootprint` state machines for each distinct jurisdiction. It bundles them into a single "Action Required" Slack alert to avoid notification fatigue.
*   **User Behavior: Rapid Employee Relocation**
    *   *Scenario:* An employee's address in the HRIS is updated twice within 24 hours (e.g., HR correcting a typo), triggering a false nexus on the typo address.
    *   *System Behavior:* The user utilizes the "1-click Dismiss" functionality in the UI to transition the erroneous `NexusFootprint` to the `Ignored` terminal state, preventing any further agentic action or compliance tracking for that specific incorrect trigger.

### 2. AI Notice Ingestion (PDF to Vertex AI)

*   **Boundary Condition: Multi-Notice "Batch" Uploads**
    *   *Scenario:* A user uploads a single 50-page PDF containing 20 different municipal notices stacked together.
    *   *System Behavior:* Vertex AI Document AI is configured to identify document boundaries. If it detects multiple distinct notices, it rejects the `Uploaded` state, transitions the file to `Needs_Review`, and prompts the user in the UI to split the document manually before extraction can proceed.
*   **Data Inconsistency: Predatory Solicitations**
    *   *Scenario:* A user accidentally uploads a scam "Certificate of Standing" solicitation that resembles a government notice but lacks a valid canonical Jurisdiction Name.
    *   *System Behavior:* The system fails to map the extracted "Jurisdiction" string to its internal database. Vertex AI extraction confidence drops to 0, forcing the document into the Human-in-the-Loop (HITL) queue with a visual warning flag: "Unrecognized Jurisdiction - Potential Solicitation."
*   **Security Boundary: Malicious File Payloads**
    *   *Scenario:* An attacker (or unaware user) attempts to upload an executable disguised with a `.pdf` extension.
    *   *System Behavior:* The backend API rejects the upload pre-GCS layer by utilizing `libmagic` to verify the true MIME type, returning an immediate HTTP 400 error.

### 3. Agentic Portal Sync (crewAI to Municipal Web)

*   **Data Inconsistency: $0.00 Returns vs. Nil Balances**
    *   *Scenario:* The agent scrapes the portal and finds a $0.00 balance, but the municipality requires an explicit "Zero-Dollar Return" form to be filed to maintain Good Standing.
    *   *System Behavior:* The agent is programmed with jurisdiction-specific routing logic. If the canonical database flags the jurisdiction as requiring "Zero-Dollar Filing," finding a $0.00 balance does *not* transition the state to `Completed`. Instead, it routes to `Requires_Human_Intervention` so the Controller can explicitly file the nil return.
*   **Network Failure: Unexpected MFA Prompts**
    *   *Scenario:* A previously stable municipal portal updates its security and prompts the crewAI Playwright agent for an SMS MFA code.
    *   *System Behavior:* The agent detects the unexpected DOM element (`input type="text" id="mfa"`), immediately captures a screenshot, and halts execution to avoid triggering a fraud lockout. The `PortalSyncTask` transitions to `Requires_Human_Intervention`, and the internal ops team is alerted via the Dead-Letter Dashboard to update the credentials with a virtual MFA number.
*   **Data Inconsistency: Mid-Cycle Fee Changes (Late Fees)**
    *   *Scenario:* The uploaded PDF notice states $150 is due, but by the time the agent scrapes the portal, a $25 late fee has been applied (Total: $175).
    *   *System Behavior:* The system detects the discrepancy between the `ComplianceNotice.feeAmount` and the scraped amount. It pauses the `PortalSyncTask`, flags the discrepancy in the UI, and issues a Slack alert to the Controller requiring manual approval of the new $175 amount before proceeding to the Payment gateway.

### 4. Frictionless Payment & Reconciliation (JurisTrack to ERP/Gateway)

*   **Network Failure: ERP Closed Periods**
    *   *Scenario:* The system attempts to write back a `CompliancePayment` to NetSuite, but the Accounting Manager has already closed the GL period for that month.
    *   *System Behavior:* The NetSuite API returns an error. The `CompliancePayment` state transitions from `Ledger_Sync_Pending` to a Dead-Letter Queue (DLQ). The system halts automatic retries, retains the state, and alerts the Controller to either re-open the period or manually map the entry to the current open period via the UI.
*   **Boundary Condition: Virtual Card Rejections**
    *   *Scenario:* The municipal payment portal strictly rejects prepaid/virtual credit card BINs (Bank Identification Numbers).
    *   *System Behavior:* The payment gateway returns an immediate synchronous rejection. The `CompliancePayment` state transitions to `Failed`. The Controller receives an immediate Slack alert specifying the rejection reason, allowing them to fall back to the automated check-cutting API (e.g., Lob integration).
*   **Concurrent Access: Race Condition on Payment Approval**
    *   *Scenario:* Two Admins (e.g., Controller and VP Finance) receive the same Slack approval notification and click "Approve" simultaneously.
    *   *System Behavior:* The system utilizes optimistic locking on the `CompliancePayment` document in MongoDB. The first request successfully transitions the state from `Draft` to `Processing`. The second request fails the state check and receives an HTTP 409 Conflict, preventing double-billing on the virtual card.

## Error Handling

The JurisTrack architecture is explicitly designed around the "Zero Silent Failures" principle. Because the system relies on volatile, archaic external dependencies (municipal portals, physical mail, legacy ERP APIs), failures are treated as expected, first-class states rather than exceptions. The system guarantees that no data is dropped and no compliance deadline is missed due to an unhandled technical failure.

### Error Taxonomy & Handling Strategies

**1. AI Document Parsing Degradation (Google Vertex AI)**
*   **Trigger:** The `confidenceScore` of the Vertex AI extraction falls below 0.95, or the document is completely illegible (e.g., handwritten notes, extremely blurry scans).
*   **System Action:** The system immediately halts the automated extraction pipeline for that specific document. It prevents transition to the `Approved` state.
*   **User Visibility:** The document is routed to the "Human-in-the-Loop" (HITL) queue in the React UI. Fields with low confidence are highlighted in yellow.
*   **Resolution:** A Controller or Accounting Manager manually reviews the PDF side-by-side with the extracted data, corrects the errors, and manually clicks "Approve" to resume the workflow.

**2. Agentic Navigation & Scraping Failures (crewAI / Playwright)**
*   **Trigger:** The Playwright agent encounters an unsolvable blocker on the municipal portal. Causes include: HTTP 429 Rate Limits, newly implemented Cloudflare CAPTCHAs, unexpected DOM redesigns, or server timeouts (>120 seconds).
*   **System Action:** 
    *   *For 429s/Timeouts (Transient):* The system utilizes Redis/Celery to trigger an exponential backoff retry strategy (e.g., retry at 1m, 5m, 30m).
    *   *For CAPTCHAs/DOM Changes (Terminal):* The system takes a full-page DOM screenshot, saves it to Google Cloud Storage, and immediately halts the agent. The `PortalSyncTask` state transitions to `Requires_Human_Intervention`.
*   **User Visibility:** The failure surfaces on the "Dead-Letter Dashboard." The Controller receives a medium-priority Slack alert indicating which jurisdiction is blocked.
*   **Resolution:** Internal Data Ops uses the captured screenshot and trace IDs to update the Playwright CSS selectors or credentials. Alternatively, the Controller can manually override the step by entering the balance themselves.

**3. ERP Ledger Write-Back Failures (QBO / NetSuite API)**
*   **Trigger:** Following a successful virtual card payment, the synchronous API call to NetSuite or QBO fails (e.g., HTTP 502 Bad Gateway, 401 Unauthorized due to expired tokens, or hitting the ERP's API concurrency limits).
*   **System Action:** The `CompliancePayment` remains securely in the `Ledger_Sync_Pending` state. The message is routed to a Dead-Letter Queue (DLQ). The system will automatically attempt 3 retries over 24 hours.
*   **User Visibility:** The payment shows as "Cleared" in the UI, but a prominent warning icon indicates "Ledger Sync Pending." If the DLQ fails after 3 attempts, a high-priority Slack alert is sent to the Controller.
*   **Resolution:** The Controller can click a "Force Retry Sync" button in the UI once the ERP is confirmed back online, or download the PDF receipt to enter the Journal Entry manually.

**4. Payment Gateway Rejections (Stripe / Lob)**
*   **Trigger:** The system attempts to authorize the virtual card, but the transaction is rejected synchronously by the gateway (e.g., HTTP 402 Insufficient Funds, suspected fraud lock, or the municipality doesn't accept virtual BINs).
*   **System Action:** The `CompliancePayment` state is immediately transitioned to `Failed`. The ERP sync is aborted.
*   **User Visibility:** A critical-priority, direct-message Slack alert is sent to the primary Controller and VP of Finance.
*   **Resolution:** The Controller must log into the JurisTrack dashboard, resolve the funding issue, or manually execute the payment outside the system and flag the record as "Paid Externally."

### Graceful Degradation Strategy
If a critical external API (e.g., Vertex AI or NetSuite) experiences a prolonged global outage, the system degrades gracefully into a "Staging Mode." Users can still upload PDFs, review HITL queues, and approve payments. The system queues all outbound actions in MongoDB/Redis and pauses worker node polling until the external service health check returns a 200 OK, at which point the backlog is processed chronologically. Users are notified via a global UI banner that processing is delayed.

## Success Metrics

### Primary North Star Metric
*   **Time Spent on Local Compliance Tasks (per Entity):** Reduce the average time a mid-market finance team spends managing, paying, and reconciling local compliance fees from an established baseline of **20 hours/month** to **< 2 hours/month** within 90 days of full onboarding.
    *   *Measurement:* Calculated via a combination of self-reported baseline surveys during onboarding and active "Time-in-App" telemetry (via tools like Mixpanel or LogRocket) per active tenant.

### AI & Agentic Efficacy Metrics
These metrics measure the success of the autonomous infrastructure in delivering the "Zero Silent Failures" vision.
*   **Zero-Touch Document Parse Rate:** Achieve a **≥ 90%** success rate where uploaded municipal notices are processed by Vertex AI and transition straight to `Approved` without requiring any manual correction in the Human-in-the-Loop (HITL) queue.
    *   *Measurement:* Tracked via MongoDB event logs comparing total `ComplianceNotice` documents uploaded versus the count of documents where `confidenceScore` required a `Needs_Review` state transition.
*   **Autonomous Agent Sync Success Rate:** Ensure that **≥ 85%** of initiated `PortalSyncTask` jobs successfully complete the scraping sequence and verify the balance without routing to `Requires_Human_Intervention`.
    *   *Measurement:* Querying the terminal state ratio of all crewAI tasks logged in the Redis/Celery backend within a 30-day rolling window.

### Operational & Risk Mitigation Metrics
*   **Entity "Good Standing" Guarantee:** Maintain a **100%** uncompromised Good Standing record for all active, tracked entities across all mapped jurisdictions.
    *   *Measurement:* Zero reported instances (support tickets or customer churn feedback) of missed filing deadlines or incurred late penalties on jurisdictions actively managed within JurisTrack.
*   **Dead-Letter Queue (DLQ) Recovery Rate:** Ensure that **> 95%** of ERP ledger sync failures (`Ledger_Sync_Pending`) caught by the DLQ are successfully resolved via automated exponential backoff retries without requiring manual Controller intervention.
    *   *Measurement:* PromQL/Datadog dashboards tracking the ratio of initial 5xx ERP API failures versus the ultimate `Ledger_Synced` terminal state count.

### Adoption & Go-To-Market Metrics
*   **Market Coverage Expansion:** Successfully support automated compliance tracking (via canonical database mapping and crewAI Playwright logic) for all **50 US States** and the **top 500 municipal jurisdictions** by launch day.
    *   *Measurement:* Internal Data Ops tracking of verified, active canonical `Jurisdictions` in MongoDB mapping to a successful test-suite run.
*   **"M&A Ready" Feature Adoption:** **> 50%** of active tenants utilize the "M&A Ready" Data Room export button at least once within their first 6 months of usage.
    *   *Measurement:* Mixpanel event tracking triggered when the export ZIP compilation is successfully downloaded.

## Dependencies

### 1. Third-Party API & External System Integrations

*   **HRIS Platforms (Gusto, Rippling, etc.):** 
    *   *Purpose:* Upstream data source for triggering the `NexusFootprint` state machine.
    *   *Risk Factor:* JurisTrack is entirely dependent on the reliability of the HRIS webhooks. Changes to the HRIS API payloads, expired authentication tokens, or delayed webhook firing will directly delay nexus discovery, potentially exposing the client to compliance risk.
*   **ERP Systems (NetSuite REST API, QuickBooks Online API):**
    *   *Purpose:* Downstream destination for the `Ledger_Synced` state, creating Vendor Bills and Journal Entries.
    *   *Risk Factor:* Strict rate limits, API concurrency caps, and intermittent downtime from the ERP providers necessitate a robust Dead-Letter Queue (DLQ) and exponential backoff retry architecture. Furthermore, changes to a client's specific ERP Chart of Accounts without updating JurisTrack will cause ledger sync failures.
*   **Google Vertex AI (Document AI):**
    *   *Purpose:* The core extraction engine for converting unstructured physical mail PDFs into structured `ComplianceNotice` records.
    *   *Risk Factor:* Degradation in AI inference speed or OCR accuracy due to upstream Google Cloud issues will directly bottleneck the notice ingestion pipeline, forcing more documents into the Human-in-the-Loop (HITL) queue.
*   **Payment Gateway (Stripe Issuing / Lob):**
    *   *Purpose:* The financial execution layer for issuing virtual cards or cutting physical checks to municipal entities.
    *   *Risk Factor:* Funding delays, rejected transactions, or API outages from the gateway prevent the `CompliancePayment` from transitioning from `Processing` to `Cleared`, causing missed payment deadlines.

### 2. External Environmental Systems

*   **US Municipal Web Portals:**
    *   *Purpose:* The target interfaces for the crewAI Playwright agents to execute the `PortalSyncTask` (verifying balances and queuing payments).
    *   *Risk Factor:* This is the most volatile dependency. Municipal portals (over 10,000 distinct sites) are not contractually obligated to maintain API parity or DOM stability. Unannounced UI redesigns, the implementation of aggressive Cloudflare CAPTCHAs, or unannounced server downtime will break the agentic scraping sequence, requiring immediate internal intervention and script updates.

### 3. Internal & Cross-Functional Operational Needs

*   **Internal Data Operations Team:**
    *   *Purpose:* Maintenance of the JurisTrack Canonical Jurisdiction Database and the crewAI Playwright routing logic.
    *   *Risk Factor:* The engineering/ops team must rapidly respond to "Requires Intervention" flags generated by UI changes on municipal portals. If the operational response time is slower than the compliance deadline, the "Zero Silent Failures" guarantee is broken.
*   **Customer Human-in-the-Loop (HITL) Engagement:**
    *   *Purpose:* The designated Controller or Accounting Manager must actively approve low-confidence AI extractions and authorize outbound virtual card payments via Slack or the React dashboard.
    *   *Risk Factor:* While the system automates the preparation, the legal execution of funds requires human authorization. Delayed approvals by the client will result in missed deadlines.

### 4. Core Infrastructure Prerequisites

*   **Cloud KMS (AWS KMS / GCP KMS):**
    *   *Purpose:* Provides the Key Encryption Keys (KEK) required to encrypt and decrypt sensitive `PortalCredentials` and PII stored in MongoDB.
    *   *Risk Factor:* If the KMS service experiences an outage or a network routing issue prevents access, the FastAPI worker nodes cannot decrypt the portal passwords. This will trigger a critical circuit breaker, pausing all `PortalSyncTask` workers globally until access is restored.

## Assumptions

### 1. User & Business Assumptions
*   **Organizational Authority:** We assume that Corporate Controllers and VP of Finance users possess the necessary organizational authority to connect third-party RegTech applications directly to their core HRIS (Gusto, Rippling) and ERP systems (NetSuite, QBO). `[Validation Strategy: Measure drop-off rates during the initial integration step of the onboarding funnel.]`
*   **Centralized Wallet Acceptance (Adoption Risk):** We assume that mid-market companies are willing to fund a centralized "JurisTrack Wallet" to facilitate automated virtual card and check clearing, preferring this over direct JurisTrack integration with their corporate bank accounts (e.g., SVB, Chase) for each micro-transaction. `[Validation Strategy: Qualitative interviews with early-adopter Controllers during Beta phase.]`
*   **Multi-Tenant Trust:** We assume that external CPA firms (Secondary Users) are willing to aggregate multiple client sub-accounts into a single multi-tenant dashboard, relying on JurisTrack's RBAC rather than demanding completely isolated software instances. `[Validation Strategy: Feedback loops from CPA pilot programs.]`

### 2. Technical & Integration Assumptions
*   **Vertex AI Efficacy:** We assume that Google Vertex AI (Document AI) is capable of consistently achieving a baseline extraction confidence score of >90% on standard, unstructured government physical mail PDFs when properly configured for this specific domain. `[Validation Strategy: Run a historical batch of 1,000 real municipal notices through the prototype pipeline before Beta launch.]`
*   **Manageable Bot Mitigation:** We assume that the targeted top 500 municipal web portals (defined by the highest transaction volume within our target mid-market profiles) do not universally employ un-bypassable, enterprise-grade bot mitigation (e.g., interactive Cloudflare Turnstile challenges, DataDome) that would permanently block headless Playwright browsers. `[Validation Strategy: Develop and run baseline scraping scripts against a representative sample of 50 target portals during M1.]`
*   **API Volatility Manageability:** We assume that the established Dead-Letter Queue (DLQ) and exponential backoff architecture is mathematically sufficient to manage the expected rate limits and downtime of downstream ERP APIs (NetSuite, QBO) without resulting in permanent state drift or ledger sync lockouts. `[Validation Strategy: Load testing the API Gateway with simulated 5xx ERP responses in staging.]`
*   **Data Type Precision:** We assume that `Decimal128` data types in MongoDB will flawlessly preserve financial accuracy for all parsed fee amounts, preventing any floating-point rounding errors during payment execution or ERP sync. `[Validation Strategy: Automated unit testing asserting exact fractional matches across thousands of simulated transactions.]`

### 3. Regulatory & Operational Assumptions
*   **Legal Acceptance of Automated Actions:** We assume that automated payments via virtual cards and agentic filings on municipal portals are universally recognized as legally compliant and sufficient for maintaining corporate "Good Standing" across the top 500 targeted jurisdictions. `[Validation Strategy: Formal review by external compliance counsel prior to Beta launch.]`
*   **The "Zero Silent Failure" Human Fallback:** To maintain the vision of "mathematically eliminating human error," we assume users accept the 48-hour Human-In-The-Loop (HITL) queue *only because* JurisTrack's internal Data Operations team acts as the ultimate, SLA-backed guarantor. If a user fails to approve a queue item before a deadline, we assume the operational structure allows our internal team to step in and execute the requirement safely. `[Validation Strategy: Draft Service Level Agreements (SLAs) with legal and operations teams to codify the fallback liability.]`
*   **Payment Method Acceptance:** We assume that payment via Stripe Issuing virtual cards or Lob automated check-cutting is legally and practically accepted by the top 500 targeted US municipal jurisdictions for the settlement of local fees. `[Validation Strategy: Direct municipal outreach and review of published payment terms during M1-M2 canonical database creation.]`
