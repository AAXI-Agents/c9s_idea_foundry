---
run_id: 2ac65871e97f
status: completed
created: 2026-03-23T12:32:17.373128+00:00
completed: 2026-03-23T13:43:56.221696+00:00
project: "[[business-compliance-tool]]"
tags: [idea, prd, completed]
---

# An application for accounting teams/firms to monitor and manage state, county...

> Part of [[business-compliance-tool/business-compliance-tool|Business compliance tool]] project

## Original Idea

An application for accounting teams/firms to monitor and manage state, county, city, and local compliance requirements, fee payments, and deadlines across the United States, with future expansion to worldwide operations. The tool should identify compliance needs, highlight preparation tasks, manage payments, and facilitate information updates, acting as a compliance officer/facilitator.

## Refined Idea

**Domain Identity:** RegTech / AccountingTech
**Stakeholder Persona:** VP of Tax & Compliance at a high-growth mid-market enterprise ($50M+ ARR) / Partner at a regional CPA Firm.

***

# Product Idea: AI-Powered "Long-Tail" Local Compliance & Nexus Facilitator 

## Executive Summary
Current corporate compliance solutions (like Avalara or CSC) effectively handle top-level transactional sales tax and state-level Secretary of State (SOS) annual reports. However, they completely ignore the "long tail" of localized compliance: county business licenses, municipal gross receipts taxes, personal property tax declarations, and local permits. This platform is an AI-driven RegTech application that acts as an automated Compliance Co-Pilot. Designed for mid-market finance teams and CPA firms, it leverages AI agents to monitor, identify, prepare, and facilitate payments for thousands of highly fragmented local jurisdictions across the United States (with architectural extensibility for global entity management). 

## Problem Statement
When a mid-market company hires a remote employee, opens a small warehouse, or ships inventory to a new ZIP code, they unknowingly trigger localized compliance requirements (economic or physical nexus). Because the US has over 10,000 distinct taxing jurisdictions—most of which lack modern APIs and rely on archaic PDF forms or basic web portals—finance teams are forced to track these obligations in massive, fragile spreadsheets. Missing a $50 local business license renewal often results in severe penalties, revoked operating privileges, or delayed M&A due diligence. Furthermore, managing the direct disbursement of thousands of micro-payments to separate municipal portals introduces massive operational overhead and money-transmitter liabilities for accounting software platforms.

## Target Audience & Value Proposition
* **Mid-Market Finance Teams ($10M–$100M ARR):** Replaces reliance on tribal knowledge and Excel calendars, ensuring continuous compliance as the business expands its physical and economic footprint.
* **Outsourced Accounting (CAS) Firms / CPA Partners:** Enables firms to offer "Local Compliance as a Service" profitably without hiring armies of data-entry clerks to monitor municipal websites. 

## Core Mechanics & Key Features

**1. Nexus Trigger Intelligence (The "When")**
Instead of relying on users to manually input new compliance obligations, the system proactively identifies them. By connecting to the user’s ERP/GL (NetSuite or QuickBooks Online via secure FastAPI integrations), the system analyzes payroll ZIP codes, new physical asset ledger entries, and regional sales volume. Google Vertex AI evaluates this structured data against a proprietary jurisdictional database to flag potential new local requirements (e.g., "New payroll run detected in Cook County, IL — Action Required: Register for Chicago Employer's Expense Tax").

**2. Multi-Agent Municipal Scraping & Parsing (The "What")**
Because local governments rarely offer REST APIs, the application utilizes a crewAI-powered multi-agent workflow to bridge the gap. 
* *Scraper Agents:* Periodically navigate known municipal URLs to detect changes in filing deadlines or fee structures.
* *Document Parsing Agents:* Ingest archaic municipal PDFs or notices (via Vertex AI multi-modal capabilities) to extract due dates, penalty clauses, and required supporting schedules, translating unstructured government text into structured tasks in the system.

**3. ERP-Integrated Payment Facilitation (The "How")**
To completely avoid the legal and security risks of holding client funds or acting as a money transmitter for 10,000+ local governments, the platform explicitly *does not* disburse funds directly. Instead, when a compliance fee is calculated and approved in the React+TypeScript frontend, the Python backend generates a structured Accounts Payable (AP) Bill directly into the client’s NetSuite or QBO environment. The client’s existing AP workflow (e.g., Bill.com) handles the actual cash disbursement, while the platform tracks the payment status via webhook callbacks.

**4. The Compliance Master State (Centralized Ledger)**
All entity data, historical filings, jurisdiction login credentials (securely vaulted), and communication logs are stored centrally in MongoDB Atlas. The application provides a unified calendar and dashboard indicating upcoming deadlines, blocked items, and missing information, effectively acting as an automated, always-on Compliance Officer. 

## Technical & Architectural Alignment
* **Backend:** Python 3.11 with FastAPI to handle high-throughput ERP syncing, webhook callbacks from QBO/NetSuite, and RESTful client interactions. 
* **Database:** MongoDB Atlas is utilized for its flexible schema design, which is critical when storing highly variable, unstructured jurisdictional requirements that do not fit neatly into relational tables.
* **AI Orchestration:** crewAI framework drives the asynchronous web-scraping and data-extraction workflows, while Google Vertex AI handles the LLM-based interpretation of complex tax codes and municipal PDFs.
* **Frontend:** React + TypeScript provides a responsive, type-safe dashboard for finance users to review AI-flagged tasks and approve ERP bill generation.
* **Global Scalability:** While the MVP focuses exclusively on the extreme complexity of US local/state compliance, the data model (Entity -> Jurisdiction -> Requirement -> Task) is intentionally designed to support future international expansion (e.g., VAT registrations, statutory local accounts).

## Executive Summary

# Executive Summary

**Problem Statement**
Mid-market enterprises and regional CPA firms are severely underequipped to manage the "long tail" of localized compliance. While top-level state and transactional taxes are well-served by industry incumbents, localized obligations—county business licenses, municipal gross receipts taxes, and personal property declarations—across over 10,000 US jurisdictions remain a deeply fragmented operational blind spot. With localized compliance penalties costing mid-market US businesses an estimated billions annually in fines, revoked operating privileges, and stalled M&A due diligence, the financial risk is substantial. Because municipalities lack modern APIs and rely heavily on archaic PDF forms or rudimentary web portals, finance teams are forced to track compounding obligations using brittle, manual spreadsheets. Furthermore, attempting to centralize the payment of thousands of municipal micro-transactions introduces prohibitive money-transmitter liabilities and massive operational overhead for existing accounting software platforms.

**Target Audience & Key Stakeholders**
* **VP of Tax & Compliance (Mid-Market Enterprises, $50M+ ARR):** Requires automated, continuous compliance monitoring as the business expands its physical and economic footprint (e.g., remote hires, new regional warehouses), eliminating reliance on tribal knowledge and manual calendars.
* **Partners at Regional CPA Firms (Outsourced Accounting / CAS):** Seeks to profitably offer comprehensive "Local Compliance as a Service" without the margin-crushing need to hire armies of data-entry clerks to monitor disparate municipal websites.
* **Compliance Specialist / Senior Staff Accountant (Day-to-Day Operator):** Drowning in manual spreadsheet reconciliation and disjointed municipal web portals. Their goal is to manage a centralized, automated queue with clear audit trails, eliminating data entry errors and the anxiety of missed deadlines.

**Proposed Solution & Key Differentiators**
The platform is an AI-driven RegTech application operating as an automated Compliance Co-Pilot, purpose-built to conquer the fragmented municipal landscape. It differentiates itself through four foundational pillars:
1. **Proactive Nexus Trigger Intelligence:** Shifting from reactive manual entry to proactive detection, the Python 3.11/FastAPI backend continuously ingests structured data from the client's ERP (NetSuite, QuickBooks Online). Google Vertex AI evaluates real-time payroll ZIP codes, new physical asset ledgers, and regional sales volumes against a proprietary jurisdictional database to flag emerging local compliance triggers.
2. **Multi-Agent Municipal Scraping & Parsing:** Bypassing the systemic lack of municipal APIs, a crewAI-powered multi-agent workflow actively monitors local government portals. Scraper agents detect changes in filing deadlines, while Vertex AI extracts key data from unstructured government PDFs, transforming them into structured tasks.
3. **Streamlined Exception-Based Workflow:** Users receive proactive notifications of AI-detected triggers. Within a React + TypeScript dashboard, they review the parsed municipal data and automatically calculated fees, click to approve (or dispute/override) the transaction, and receive real-time confirmation once the liability is recorded.
4. **Zero-Liability ERP-Integrated Payment Facilitation:** To strictly avoid money-transmitter liabilities, the platform does not hold or route client funds. Upon frontend approval, the system pushes a structured Accounts Payable (AP) Bill directly to the client's ERP. The client's existing AP engine handles the cash disbursement, while the platform tracks settlement via webhook callbacks.

**Non-Functional Requirements & Performance Targets**
* **Performance:** AI parsing of municipal documents completed in < 30 seconds; AP Bill push to ERP executed in < 5 seconds post-user approval.
* **Scalability:** Architected to support up to 500 concurrent client entities and process 50,000+ monthly compliance tasks via asynchronous queueing.
* **Reliability & Security:** 99.9% platform uptime SLA. Strict adherence to SOC 2 Type II compliance standards, featuring AES-256 encryption for all vaulted municipal portal credentials stored in MongoDB Atlas.

**Edge Cases & Error Handling**
* **Scraper Breakages & AI Accuracy:** If municipal UI changes break scraper agents, the system automatically alerts engineering and falls back to a manual review queue. Vertex AI extractions are assigned confidence scores; scores below 90% mandate human-in-the-loop review before workflow progression.
* **Integration Failures:** Failed NetSuite/QBO AP syncs trigger asynchronous retry logic with exponential backoff. Persistent failures are surfaced as high-priority alerts in the user's dashboard.
* **Dispute Workflows:** Users possess full control to override AI-suggested nexus triggers, manually adjust calculated fees, or dismiss false positives, with all overrides logged for auditability and AI fine-tuning.

**Business Impact, Analytics, & Success Criteria**
* **Risk Eradication:** Achieve a 0% localized compliance penalty rate for fully onboarded entities.
* **Operational Efficiency:** Reduce manual research and tracking hours by at least 80% for CAS practices and internal finance teams.
* **Product Telemetry:** Track Monthly Active Users (MAU) engagement, target an average time from task detection to AP Bill approval of < 48 hours, and maintain a 99.9% AP sync success rate.
* **Risk Mitigation:** Proactively manage dependencies on municipal website volatility (via crewAI redundancy), AI model drift (via MongoDB interaction logging), and ERP API rate limits (via intelligent request batching).

## Executive Product Summary

# Executive Product Summary: The Invisible Shield for Geographic Expansion

## The Real Problem: The Friction and Fear of Growth
When a company comes to us asking for a "municipal compliance scraper," they are asking for the wrong thing. Nobody actually wants to track 10,000 fragmented local government portals, and they certainly don't want a new dashboard to manage them. 

The real problem is the **friction of geographic growth and the anxiety of invisible liabilities.** 

When a mid-market company hires a remote engineer in a new zip code or opens a regional warehouse, they are focused on growth. Yet, that simple act unknowingly steps on localized bureaucratic landmines—county business licenses, municipal gross receipts taxes, personal property declarations. Today, Finance and Tax leaders live in low-grade terror that a missed $50 local fee will snowball into revoked operating privileges, frozen bank accounts, or a stalled $100M M&A due diligence process. 

They don't need a compliance tracker. They need an **Autonomous Operating Privilege Engine**. They need a system that ensures their right to operate and grow is never compromised by archaic local bureaucracy. 

## The 10-Star Product Vision
The standard version of this product is a dashboard that alerts a user: *"You have a new tax due in Cook County, go figure it out."* 

**We are going to scrap that and build the 10-star version.**

The 10-star version is practically invisible. It requires zero manual data entry. It sits silently on top of the company's existing ERP (NetSuite or QuickBooks Online). It watches the ledger. When a new payroll zip code appears, the system doesn't just send an alert. 

Instead, our system:
1. **Detects** the trigger instantly via FastAPI webhooks.
2. **Understands** the local requirement using Vertex AI against our jurisdictional database.
3. **Dispatches** a crewAI agent to navigate the archaic local municipal portal and fetch the required PDF form.
4. **Fills** the form automatically.
5. **Drafts** a complete, ready-to-pay Accounts Payable (AP) Bill directly inside the client’s ERP, attaching the completed local form.

We bypass money-transmitter liabilities entirely. We don't hold funds; we just perfectly tee up the payment in the system the client already uses. The user's experience is simply clicking "Approve" in NetSuite. We turn unstructured, archaic local bureaucracy into a silent, automated API.

## The Ideal User Experience ("This is exactly what I needed")
Imagine Sarah, VP of Tax at a $75M SaaS company. On a Tuesday, HR hires a new remote account executive in a small municipality in Ohio. Sarah doesn't know this town exists, let alone its specific local tax codes.

On Wednesday morning, Sarah gets a Slack notification (or email): 
> *"Growth detected in Cuyahoga Falls, OH. We've prepared your required Local Business Registration and drafted the $150 AP Bill in NetSuite. Click here to review."*

She clicks the link, bringing her to our React + TypeScript dashboard (or directly to NetSuite). She sees a side-by-side view: on the left, the plain-English explanation of why this was triggered; on the right, the perfectly filled-out municipal PDF. She clicks "Approve." The bill is paid via her normal AP workflow. The municipal login credentials, the filing history, and the receipt are securely vaulted in MongoDB Atlas. 

Sarah thinks: *"I didn't even know we had an employee there yet, and this system already solved the compliance problem. This is exactly what I needed."*

## Delight Opportunities (<30 Min "Bonus Chunks")
To make the product feel magical and deeply empathetic to the user's daily life, we will include these high-leverage delight features:

1. **Plain-English "Why Did This Happen?" Tooltips:** Finance hates black boxes. Next to every AI-generated AP bill, Vertex AI generates a one-sentence, human-readable explanation: *"You ran payroll for John Doe in Zip Code 44221, which triggers this specific municipal tax."* 
2. **The "Clean Bill of Health" M&A Button:** A single click generates a beautiful, auditor-ready PDF report proving the company has zero local compliance gaps across all active jurisdictions. This instantly eliminates the most stressful part of due diligence.
3. **Transparent "Agent at Work" States (Zero Silent Failures):** When a municipal website changes its UI and our crewAI scraper fails, we *never* just show a red error. We show: *"The Cook County website updated its layout. Our AI is currently re-mapping the portal. We will retry in 2 hours."* This turns a failure into a demonstration of the product's value.
4. **Expansion "What-If" Map:** A simple map interface where a user can drop a pin anywhere in the US and instantly see: *"If you hire someone here, it will add 3 local compliance filings costing $250/year."* 

## Scope Mapping: The 12-Month Trajectory

* **Current State (The Baseline):** Finance teams rely on tribal knowledge, frantic googling, and massive, brittle Excel spreadsheets. Deadlines are missed, and M&A deals are delayed by surprise local liabilities.
* **This Plan (Months 1-6):** The "Invisible Shield." We launch the ERP integration (NetSuite/QBO), the crewAI scraping engine, and the AP Bill generation workflow. We eliminate manual tracking and automate the generation of compliance tasks based on active payroll and asset triggers. We build the data moat in MongoDB Atlas.
* **12-Month Ideal (Months 7-12):** Predictive Expansion Intelligence. The system shifts from *reacting* to ERP data to *advising* the business. We introduce global extensibility (VAT, local statutory accounts). The system automatically audits historical ERP data to find and remediate years of previously missed local liabilities, acting as an instant cleanup crew for new clients.

## Business Impact & Success Criteria
This isn't just a SaaS tool; it's the creation of an insurmountable data moat. By structuring the unstructured "long tail" of US municipalities, we are building a proprietary dataset that Avalara and legacy incumbents have completely ignored. 

**Success is not measured by high Monthly Active Users (MAU).** In fact, if the user spends hours in our app, we have failed. We want *low* time-in-app and *high* integration volume. 

**Core Success Criteria:**
1. **The Ultimate Metric:** 0% localized compliance penalty rate and zero M&A compliance delays for fully onboarded entities.
2. **Time to Value:** Target an average time from a new ERP trigger (e.g., payroll run) to AP Bill draft of < 24 hours.
3. **Frictionless Resolution:** Maintain a 99.9% AP sync success rate with QBO and NetSuite.
4. **Agent Resiliency:** >90% of municipal website layout changes are adapted to by crewAI and Vertex AI without requiring a human-in-the-loop fallback.

By reframing local compliance from a "tracking problem" to an "automated operating privilege," we aren't just selling software; we are selling the confidence to grow.

## Engineering Plan

# Engineering Plan: Autonomous Operating Privilege Engine (Local Compliance Co-Pilot)

## 1. Architecture Overview

### 1.1 System Boundaries & Architecture Diagram

The system is a classic event-driven, asynchronous architecture built to handle high-volume, non-deterministic workflows (AI processing, web scraping) while maintaining strict consistency for financial data.

```text
=====================================================================================================
                                      TRUST BOUNDARY (CLIENT ERP)
=====================================================================================================
      [NetSuite]                  [QuickBooks Online (QBO)]
          |  ^                                |  ^
 Webhooks |  | REST API              Webhooks |  | REST API
 (Events) |  | (AP Bills)            (Events) |  | (AP Bills)
          v  |                                v  |
=====================================================================================================
                                  TRUST BOUNDARY (CORE PLATFORM VPC)
=====================================================================================================
                                  +-----------------------+
           +--------------------->| API Gateway / WAF     |<------------------------+
           |                      +-----------------------+                         |
           |                                 |                                      |
           |                                 v                                      v
  +------------------+             +-------------------+                  +-------------------+
  | External Webhook |             | FastAPI Backend   |                  | React + TypeScript|
  | Validation (HMAC)|             | (REST APIs)       |                  | SPA Dashboard     |
  +------------------+             +-------------------+                  +-------------------+
           |                                 |                                      |
           | (Produces)                      | (Reads/Writes)                       | (Reads/Writes)
           v                                 v                                      v
  +------------------+             +-------------------+                  +-------------------+
  | Redis Queue      |             | MongoDB Atlas     |<-----------------| User Auth (JWT)   |
  | (Celery Broker)  |             | (Persistence)     |                  +-------------------+
  +------------------+             +-------------------+
           |                                 ^
           | (Consumes)                      | (Updates State)
           v                                 |
  +----------------------------------------------------+
  | Celery Background Workers (Python 3.11)            |
  |  - Webhook Ingestion & Idempotency Check           |
  |  - Nexus Trigger Evaluator                         |
  |  - Task Math/Logic Calculator                      |
  |  - AP Bill Sync Engine                             |
  +----------------------------------------------------+
           |                         |                 |
           v                         v                 v
  +------------------+      +-----------------+  +-----------------+
  | crewAI Agents    |      | Google Vertex AI|  | GCP Cloud       |
  | (Web Scraping)   |      | (LLM / OCR)     |  | Storage (Vault) |
  +------------------+      +-----------------+  +-----------------+
           |                         |
           v                         v
=====================================================================================================
                          TRUST BOUNDARY (PUBLIC INTERNET / EXTERNAL APIS)
=====================================================================================================
  [10,000+ Municipal Gov Portals (HTML/PDF)]
```

### 1.2 Technology Stack & Rationale
*   **Backend Application:** Python 3.11 + FastAPI. *Rationale:* Native async support for high-throughput webhook handling. Unrivaled ecosystem for AI/ML integration (Vertex AI, crewAI).
*   **Background Processing:** Celery + Redis. *Rationale:* Critical for isolating non-deterministic, long-running AI/Scraping tasks from synchronous REST API endpoints.
*   **Database:** MongoDB Atlas. *Rationale:* Jurisdictional tax requirements and unstructured local government data schemas vary wildly. A rigid relational schema would require constant, brittle migrations.
*   **AI/ML:** Google Vertex AI (Gemini Pro/Vision) + crewAI. *Rationale:* Multimodal capabilities are essential for parsing scanned municipal PDFs. crewAI provides robust agentic workflows with built-in retry logic.
*   **Frontend:** React + TypeScript. *Rationale:* Strong typing prevents UI state bugs; component-based architecture for complex dual-pane (PDF vs. Math) views.

### 1.3 Data Flow Diagram: Nexus Trigger to AP Bill

```text
[ERP Webhook] -> (1) API Gateway -> (2) FastAPI (/nexus-event) -> (3) HMAC Validation 
                                      |
   +----------------------------------+
   | 
   v
(4) Check Idempotency (MongoDB)
   |-- [Empty/Nil Path]: Duplicate/Malformed -> Return 400/202, Drop
   |-- [Happy Path]: Queue Event in Redis -> Return 202 Accepted
   v
(5) Celery Worker Pops Event -> Calls Vertex AI
   |-- [Error Path]: Vertex Timeout -> Retry w/ Exponential Backoff -> Fail to DLQ
   |-- [Happy Path]: Confidence > 0.80 -> State = FLAGGED -> Generate ComplianceTask
   v
(6) Compliance Task Worker -> Evaluates missing data
   |-- [Nil Path]: Missing Data -> State = INFO_NEEDED -> Wait for User
   |-- [Happy Path]: Math successful -> State = READY_FOR_APPROVAL
   v
(7) User Approves in React UI -> State = PAYMENT_APPROVED -> Queue AP Sync
   v
(8) AP Sync Worker -> Matches Vendor via AI -> Pushes to ERP
   |-- [Error Path]: ERP 400 (Closed Period) -> State = FAILED -> Alert User
   |-- [Happy Path]: ERP 201 -> State = ERP_ACCEPTED
   v
(9) Inbound ERP Webhook (Payment Cleared) -> State = COMPLETED
```

---

## 2. Component Breakdown

### 2.1 Feature 1: ERP Nexus Trigger Intelligence Engine
*   **Purpose:** Ingests raw ERP telemetry, standardizes it, and queries Vertex AI to determine if local nexus was breached.
*   **Dependencies:** QBO/NetSuite Webhook Subscriptions, Redis, Vertex AI.
*   **State Machine (`NexusTriggerEvent`):**
    ```text
    [PENDING] ---> (Worker Picks Up) ---> [ANALYZING]
                                              |
      +-------------------+-------------------+-------------------+
      | (Conf > 0.8)      | (Conf 0.4 - 0.79) | (Conf < 0.4)      |
      v                   v                   v                   |
    [FLAGGED] <-----> [FLAGGED]* (Needs Rev) [DISMISSED]          | (User action)
      |                                                           v
      +-------------------(User Approves)-------------------> [PROCESSED]
    ```
*   **API Contracts:**
    *   `POST /api/v1/webhooks/erp/nexus-event` -> `202 Accepted`
    *   `GET /api/v1/nexus-events?state=FLAGGED` -> `200 OK`
    *   `POST /api/v1/nexus-events/{id}/process` -> `200 OK` (Scaffolds Task)

### 2.2 Feature 2: Multi-Agent Municipal Scraping
*   **Purpose:** Keeps the central tax logic database updated by scraping and parsing archaic municipal portals/PDFs.
*   **Dependencies:** crewAI, Vertex AI Vision (OCR), GCP Cloud Storage.
*   **State Machine (`ScrapeJob`):**
    ```text
    [QUEUED] ---> (Cron/Manual Trigger) ---> [IN_PROGRESS]
                                                  |
           +--------------------+-----------------+--------------------+
           | (Conf > 0.9)       | (Conf 0.5-0.89) | (Timeout/403 x3)   |
           v                    v                 v                    |
     [COMPLETED]        [REVIEW_REQUIRED]      [FAILED]                |
           ^                    |                 |                    |
           +---(Admin Approves)-+                 +--(Admin Retries)---+
    ```
*   **API Contracts:**
    *   `POST /api/v1/municipal-sources/scrape-jobs` -> `202 Accepted`
    *   `PUT /api/v1/municipal-sources/scrape-jobs/{id}/approve` -> `200 OK`

### 2.3 Feature 3: Compliance Task Master Ledger
*   **Purpose:** The central UI and math evaluation engine. Combines user telemetry + tax rules to calculate liability.
*   **Dependencies:** Valid `JurisdictionRequirement`, valid `Company` telemetry.
*   **State Machine (`ComplianceTask`):**
    ```text
    [DRAFT] --> (Missing Info) --> [INFO_NEEDED]
       |                                |
    (Math OK)                     (User Provides Info)
       |                                |
       v                                v
    [READY_FOR_APPROVAL] <--------------+
       |
    (User Clicks Approve)
       |
       v
    [PAYMENT_APPROVED] --> (To Feature 4) --> [BILL_CREATED] --> (ERP Webhook) --> [COMPLETED]
    ```
*   **API Contracts:**
    *   `GET /api/v1/compliance-tasks` -> `200 OK`
    *   `PUT /api/v1/compliance-tasks/{id}` -> `200 OK` (User overrides/adds info)
    *   `POST /api/v1/compliance-tasks/{id}/approve` -> `200 OK`

### 2.4 Feature 4: ERP-Integrated AP Bill Generation
*   **Purpose:** Creates AP Bills in the client ERP without holding client funds, relying on semantic vendor mapping.
*   **Dependencies:** QBO/NetSuite REST APIs.
*   **State Machine (`ApBillSyncRecord`):**
    ```text
    [PENDING_PUSH] ---> (Worker Executes) ---> [ERP_ACCEPTED] ---> (Webhook Received) ---> [PAYMENT_CLEARED]
          ^                                          |
          | (User Retries)                           | (API 4xx/5xx Error)
          +------------- [FAILED] <------------------+
    ```
*   **API Contracts:**
    *   `POST /api/v1/erp/ap-bills/sync` -> `202 Accepted` (Internal)
    *   `POST /api/v1/webhooks/erp/payment-cleared` -> `200 OK`

---

## 3. Implementation Phases & Jira Mapping

### Epic 1: Foundation & Data Moat (Phase 1) - `Size: M`
*Focus: Establish boilerplate, auth, and MongoDB schema definitions.*
*   **Story 1.1:** Setup FastAPI project structure, Dockerfiles, and CI/CD pipelines.
*   **Story 1.2:** Implement JWT-based RBAC Authentication (Admin vs. Client roles).
*   **Story 1.3:** Configure MongoDB Atlas connections and implement base data models (`Company`, `JurisdictionRequirement`).
*   **Story 1.4:** Setup Celery + Redis worker infrastructure.

### Epic 2: ERP Nexus Engine (Phase 2) - `Size: L`
*Focus: Secure webhooks and AI-driven telemetry evaluation.*
*   **Story 2.1:** Implement `POST /nexus-event` webhook with HMAC-SHA256 validation and Idempotency keys.
*   **Story 2.2:** Build Vertex AI integration client for evaluating nexus triggers.
*   **Story 2.3:** Implement `NexusTriggerEvent` state machine worker.
*   **Story 2.4:** Build deterministic fallback (ZIP-to-County lookup) for AI failures.
*   **Story 2.5:** Create React Dashboard view for FLAGGED/DISMISSED nexus events.

### Epic 3: Multi-Agent Scraper Engine (Phase 3) - `Size: XL`
*Focus: Autonomous updating of the tax rule database.*
*   **Story 3.1:** Integrate crewAI framework and configure Scout/Download agents.
*   **Story 3.2:** Build Vertex AI Multimodal parser for PDF OCR and text extraction.
*   **Story 3.3:** Implement anomaly detection rules (e.g., fee > $5000 -> REVIEW_REQUIRED).
*   **Story 3.4:** Build Admin React UI for reviewing and mapping failed/flagged scrape jobs.

### Epic 4: Task Ledger & AI Math Engine (Phase 4) - `Size: L`
*Focus: The core user experience and compliance calculation logic.*
*   **Story 4.1:** Build background worker to parse `dynamic_fee_rule` against company telemetry.
*   **Story 4.2:** Implement deterministic math validation layer (post-AI output).
*   **Story 4.3:** Build the main React Dashboard grid for `ComplianceTask` management.
*   **Story 4.4:** Implement `INFO_NEEDED` fallback UX for missing ERP telemetry.

### Epic 5: AP Sync & Loop Closure (Phase 5) - `Size: L`
*Focus: Pushing bills to ERPs and listening for payment completion.*
*   **Story 5.1:** Build Vendor Semantic Matcher using Vertex AI embeddings.
*   **Story 5.2:** Implement QBO/NetSuite REST API push logic with exponential backoff.
*   **Story 5.3:** Build `POST /payment-cleared` webhook handler.
*   **Story 5.4:** Implement AP failure UI (manual retry / vendor override).

---

## 4. Data Model & Schema Decisions

**Database:** MongoDB Atlas (NoSQL).
**Rationale:** Jurisdictional requirements lack uniform schema. One city charges a flat $50, another charges a piecewise function based on headcount. Schema-less design is mandatory.

**Key Collections & Indexes:**

1.  **`Company`** (Tenant Data)
2.  **`JurisdictionRequirement`**
    *   *Indexes:* Unique Compound `{ jurisdiction_name: 1, requirement_type: 1 }`
3.  **`NexusTriggerEvent`**
    *   *Indexes:* Compound `{ company_id: 1, state: 1, created_at: -1 }` (For UI filtering).
    *   *TTL Index:* `{ created_at: 1 }` expiring after 365 days *only* for `DISMISSED` states to save storage.
4.  **`ScrapeJob`**
    *   *Indexes:* `{ state: 1, jurisdiction_id: 1 }`
5.  **`ComplianceTask`**
    *   *Indexes:* `{ company_id: 1, state: 1, due_date: 1 }`
6.  **`ApBillSyncRecord`**
    *   *Indexes:* Unique `{ compliance_task_id: 1 }`; Sparse Unique `{ erp_bill_id: 1 }` (Critical for inbound payment webhooks).
7.  **`IdempotencyKeys`**
    *   *Indexes:* Unique `{ key: 1 }`, TTL Index expiring after 48 hours. Used to deduplicate ERP webhooks.

**Migration Strategy:** MongoDB does not require formal schema migrations, but we will utilize a library like `Beanie` or `Motor` with Pydantic models to enforce application-layer schema validation. Field additions will have default values (`None` or `[]`) for backwards compatibility.

---

## 5. Error Handling & Failure Modes

**Design Philosophy:** Zero silent failures. Every failure must transition an entity into an actionable state (`FAILED`, `REVIEW_REQUIRED`, `INFO_NEEDED`).

| Component | Failure Mode | Classification | Mitigation Strategy | Resulting State |
| :--- | :--- | :--- | :--- | :--- |
| **Webhook Ingestion** | Invalid HMAC / Missing Signature | Security | Drop immediately, log to SecOps. Return 401. | None |
| **Webhook Ingestion** | Duplicate Webhook from ERP | Minor | Intercepted by Redis Idempotency cache. Return 200. | None |
| **Nexus / Math AI** | Vertex AI API Timeout | Major | Celery retry with exponential backoff (max 3 retries). | `PENDING` -> Dead Letter Queue |
| **Nexus / Math AI** | LLM Hallucination / Invalid Math | Major | Post-LLM deterministic validation. If total sum != base + dynamic, flag. | `INFO_NEEDED` (Human fallback) |
| **Scraper Agents** | Cloudflare / CAPTCHA 403 Block | Major | Rotate proxy pool via crewAI. If fails 3x, fallback to Admin. | `FAILED` |
| **AP Bill Sync** | Target ERP API Closed Period (400) | Critical | Capture exact ERP error string. Halt push. | `FAILED` -> Alert client in UI |
| **AP Bill Sync** | Upstream ERP 502/Timeout | Minor | Circuit breaker pattern + Celery retry with backoff. | `PENDING_PUSH` |

---

## 6. Test Strategy

### 6.1 Test Pyramid
*   **Unit Tests (Pytest):** >85% coverage. Focus strictly on deterministic logic (Pydantic validators, mathematical sum verifiers, RBAC permission checks, state transition guards).
*   **Integration Tests:** Test MongoDB interactions, Redis queueing, and Celery task execution. Mock external APIs (Vertex, QBO, NetSuite).
*   **End-to-End (E2E) Tests:** Core flow: Post dummy Webhook -> Force AI mock response -> Check DB state -> Trigger AP Sync -> Verify API request payload to mock ERP.

### 6.2 AI Determinism & Edge Case Testing
Since LLMs are non-deterministic, we *cannot* use live Vertex AI calls in standard CI pipelines.
*   **VCR.py / Mocking:** Record golden HTTP responses from Vertex AI for known payloads and replay them in CI to ensure downstream application logic handles the structured JSON correctly.
*   **Edge Case Matrix:**
    *   Payload with malformed ZIP code (`"zip": "ABCDE"`).
    *   Payload with a multi-state nexus (e.g., employee lives in OH, works in PA).
    *   PDF document entirely consisting of scanned images (no selectable text).
    *   Zero-dollar tax liability but mandatory filing requirement (`zero_dollar_return = true`).

---

## 7. Security & Trust Boundaries

*   **Webhook Authentication:** Strict validation of `X-Hub-Signature` (QBO) and equivalent NetSuite headers. Requests lacking valid HMAC are dropped at the middleware layer before touching business logic.
*   **Data Vaulting:** Municipal portal credentials and historical filing PDFs are vaulted in GCP Cloud Storage/Secret Manager, mapped via temporary signed URLs in the frontend.
*   **Prompt Injection Defense:** AI prompts are hard-coded in the backend. User input (e.g., memo fields) is enclosed in strict delimiters `### {user_input} ###` and LLM system prompts explicitly instruct the model to ignore actionable commands within the delimiters. Enforce `response_mime_type="application/json"` in Vertex to prevent arbitrary text execution.
*   **Money Transmitter Liability Guardrails:** The system *must never* accept credit card data for paying municipalities, nor should it hold bank account routing info for disbursement. The application explicitly limits its boundary to generating AP Bills in the client's source-of-truth ERP.

---

## 8. Deployment & Rollout

### 8.1 Deployment Sequence
We utilize a Blue/Green deployment strategy on managed Kubernetes (GKE) or AWS ECS.
1.  **Pre-Flight:** Run Pydantic schema validation tests against staging MongoDB.
2.  **Phase 1 (Data):** Apply MongoDB index updates (if any).
3.  **Phase 2 (Workers):** Deploy new Celery worker pods. Run old and new workers concurrently (draining queues).
4.  **Phase 3 (API):** Deploy FastAPI backend pods. Switch API Gateway traffic.
5.  **Phase 4 (UI):** Deploy React assets to CDN.

### 8.2 Feature Flagging
AI features are heavily feature-flagged (e.g., LaunchDarkly) to allow granular rollout:
*   `nexus_ai_evaluation_enabled` (Boolean)
*   `ap_vendor_semantic_matching_enabled` (Boolean)
If disabled, the system gracefully degrades to deterministic routing and manual dropdowns.

### 8.3 Rollback Plan
1. Revert API Gateway to "Blue" (previous) backend pods.
2. Scale down "Green" Celery workers.
3. Flush Redis queue of newly formatted messages (if schema breaking), or rely on Pydantic's `Extra.ignore` to process gracefully.
4. UI CDN points back to previous commit hash.

---

## 9. Observability

### 9.1 Logging Requirements
*   All logs are structured JSON sent to a centralized aggregator (Datadog / ELK).
*   **Traceability:** Every incoming webhook is assigned a `x-correlation-id`. This ID is injected into the Celery task context and passed to all downstream Vertex AI and ERP API calls.

### 9.2 Metrics & Alerting (Prometheus/Grafana)
*   **SLI:** Webhook Ingestion Success Rate. Alert if < 99.9% over 5 minutes.
*   **SLI:** AP Sync Success Rate. Alert if `FAILED` state transitions > 5% over 1 hour.
*   **AI Metric:** AI Confidence Score Histogram. Alert if the rolling average of Vertex AI confidence drops below 0.60 (indicates model drift or UI changes in municipal sites).
*   **Business Metric:** Time-to-Value (Average time from Webhook to AP Bill Draft). Target: < 24h.

### 9.3 Debugging Runbook for Common Failures
*   *Scenario: Inbound Webhooks are returning 202, but NexusTasks aren't generating.*
    *   **Step 1:** Check Redis queue length (`celery -A app inspect active`).
    *   **Step 2:** Check Datadog for Vertex AI rate limit (429) errors.
    *   **Step 3:** Verify Pydantic validation logs; if the ERP changed their webhook payload structure, events are being dropped by the worker schema validation. Adjust Pydantic model.

## Problem Statement

**The Current State: The Blind Spot in Geographic Expansion**
As mid-market enterprises scale, their physical and economic footprints naturally expand. A new remote hire in a different ZIP code, a pop-up warehouse, or localized inventory routing automatically triggers physical or economic nexus. While top-tier corporate compliance solutions (such as Avalara or CSC) efficiently handle top-level state sales tax and Secretary of State annual reports, they completely abandon the "long tail" of localized compliance. Across the United States, there are over 10,000 distinct, fragmented taxing jurisdictions that enforce local county business licenses, municipal gross receipts taxes, and personal property declarations. 

Currently, these municipalities operate in a technological dark age. They lack RESTful APIs, relying instead on archaic PDF forms, rudimentary and frequently changing web portals, and physical mail. Because enterprise ERPs (like NetSuite or QuickBooks Online) track the *triggers* of growth (payroll ZIP codes, fixed assets) but lack localized tax intelligence, a massive data gap exists. Finance teams are forced to bridge this gap manually using frantic web searches, tribal knowledge, and highly brittle Excel spreadsheets.

**Core Pain Points**
*   **The Operational Black Hole:** Highly paid finance professionals and outsourced CPA clerks waste hundreds of hours manually monitoring thousands of disparate municipal websites for changing deadlines, fee structures, and required PDF schedules.
*   **The Disconnected Tech Stack:** Current accounting tools treat localized tax as an afterthought. There is no automated link between an ERP ledger event (e.g., running payroll in Cook County, IL) and the resulting municipal obligation (e.g., registering for the Chicago Employer's Expense Tax).
*   **The Payment Transmission Trap:** Attempting to manually process and disburse thousands of $25 to $150 micro-payments to non-standard municipal portals introduces massive operational overhead and severe money-transmitter compliance risks for accounting platforms and CAS firms.

**Impact Quantification: The Asymmetric Risk**
The danger of long-tail compliance lies in its deep asymmetry. The cost of a required local permit or license is often negligible—frequently under $100. However, the cost of *missing* that requirement is catastrophic. 
*   **Compounding Financial Penalties:** A missed $50 local fee often generates severe, compounding monthly penalties that escalate into thousands of dollars before the business is even notified.
*   **Revoked Operating Privileges:** Municipalities routinely freeze local bank accounts or revoke business operating privileges for minor, persistent infractions.
*   **Stalled M&A Activity:** During acquisitions or funding rounds, un-audited, unresolved local tax liabilities are a primary cause of delayed due diligence, potentially stalling or derailing $50M–$100M+ transactions while armies of auditors scramble to clear the localized ledger.

**Why Now?**
The systemic shift toward remote, distributed workforces has transformed localized compliance from a manageable, infrequent headache into a daily operational crisis. A mid-market company that historically operated in three jurisdictions may now inadvertently operate in fifty, simply by hiring a distributed engineering team. The legacy methodology of "waiting for a notice in the mail" is fundamentally incompatible with the speed of modern business scaling. Finance leaders urgently require a system that eliminates this invisible liability and guarantees their right to operate freely without manual intervention.

## User Personas

### 1. The Strategic Defender: VP of Tax & Compliance
**Demographics & Role:**
*   **Name:** Sarah, 42
*   **Context:** VP of Tax at a high-growth, mid-market SaaS company ($75M ARR). She oversees a small internal team and relies heavily on automated systems (NetSuite) to manage the company's rapid, multi-state workforce expansion.
*   **Usage Frequency:** Occasional but high-stakes (Weekly summary review, ad-hoc M&A due diligence).

**Pain Points:**
*   **Invisible Liabilities:** She lives in constant fear of "gotcha" local tax penalties that accrue simply because HR hired a remote worker in a jurisdiction she is unaware of.
*   **M&A Friction:** Gathering proof of local compliance across 100+ micro-jurisdictions during a funding round or acquisition is a manual, anxiety-inducing nightmare that stalls deals.
*   **Black-Box Software:** She distrusts automated systems that make compliance decisions or payments without explaining the underlying tax logic.

**Goals & Desired Outcomes:**
*   Ensure a 0% localized compliance penalty rate to guarantee the company's uninterrupted right to operate.
*   Eliminate manual tracking entirely, relying on the platform to act as a silent, background "shield" connected to NetSuite.
*   Generate auditor-ready compliance reports instantly.

**Feature Focus:** 
She relies heavily on the "Clean Bill of Health" M&A Button for instant audit reporting, the Plain-English "Why Did This Happen?" tooltips to trust the AI's logic, and the Expansion "What-If" Map to forecast compliance costs before the company expands into a new state.

---

### 2. The Scalable Advisor: CAS Partner (CPA Firm)
**Demographics & Role:**
*   **Name:** David, 50
*   **Context:** Partner at a regional Client Advisory Services (CAS) firm. His firm manages the books and compliance for 40+ mid-market clients, primarily using QuickBooks Online (QBO).
*   **Usage Frequency:** Daily (Monitoring the multi-tenant dashboard across his entire client portfolio).

**Pain Points:**
*   **Margin-Crushing Labor:** Offering "local compliance" currently requires hiring armies of junior clerks to manually check municipal websites and manage brittle Excel spreadsheets. It is an unprofitable service line.
*   **Money Transmitter Risk:** He absolutely refuses to let his firm hold client funds or act as a payment intermediary for 10,000+ local governments due to severe legal liabilities.
*   **Client Communication Overhead:** Explaining to clients why they owe a $50 fee to an obscure county is time-consuming and often leads to pushback.

**Goals & Desired Outcomes:**
*   Transform local compliance from a loss-leader into a highly profitable, scalable "Compliance as a Service" offering.
*   Manage exceptions across 40+ clients from a single, unified multi-tenant dashboard.
*   Push completely drafted, mathematically verified AP Bills directly into clients' QBO instances for them to fund, absolving his firm of payment liability.

**Feature Focus:**
He requires the robust Multi-Tenant React Dashboard to view `ComplianceTask` states (e.g., `INFO_NEEDED`, `READY_FOR_APPROVAL`) across all clients. He depends entirely on the Zero-Liability ERP-Integrated Payment Facilitation to push AP Bills without touching client cash.

---

### 3. The Exception Handler: Compliance Specialist / AP Clerk
**Demographics & Role:**
*   **Name:** Marcus, 28
*   **Context:** Senior Staff Accountant / Compliance Ops at the mid-market enterprise (reporting to Sarah) or a CAS Analyst at David's CPA firm. He is the human-in-the-loop operator.
*   **Usage Frequency:** Daily power user.

**Pain Points:**
*   **Data Chasing:** He spends hours hunting down missing payroll details or asset ledgers to complete archaic PDF forms.
*   **Platform Breakages:** When local municipal websites randomly change their layout, his existing automated macros break, causing silent failures and missed deadlines.
*   **Disconnected Workflows:** Finding the tax amount in a PDF, logging into the ERP, creating a vendor, and drafting an AP bill involves too many manual, error-prone context switches.

**Goals & Desired Outcomes:**
*   Clear the daily queue of `FLAGGED` nexus events and `READY_FOR_APPROVAL` tasks rapidly with high confidence.
*   Never experience a "silent failure"; if a website changes, he needs to know immediately why the data is missing.
*   Have all necessary context (the municipal PDF and the calculated math) presented in a single pane of glass.

**Feature Focus:**
He interacts constantly with the AI Task Ledger. He relies on the Transparent "Agent at Work" States to know when a `ScrapeJob` is in a `FAILED` or `REVIEW_REQUIRED` state due to municipal website changes. He uses the side-by-side UI to verify Vertex AI's OCR extraction before clicking the final "Approve" button to sync the AP Bill.

---

### 4. The Verifier: Internal / External M&A Auditor
**Demographics & Role:**
*   **Name:** Arthur, 55
*   **Context:** External M&A Due Diligence Auditor or Internal Audit Lead. He enters the picture during high-stakes financial events (e.g., funding rounds, acquisitions) to verify the company's localized compliance footprint.
*   **Usage Frequency:** Rare but highly intensive (Deep dives during specific 30-day diligence windows).

**Pain Points:**
*   **Scattered Evidence:** He typically has to hunt through fragmented email chains, physical filing cabinets, and disparate state portals to find proof of local compliance.
*   **Unverifiable Data:** He struggles to connect a localized tax payment in the ERP back to the underlying PDF schedule and the specific trigger event that caused it.
*   **Delayed Deal Flow:** The inability to quickly verify the "long tail" of local compliance often holds up $100M+ transactions.

**Goals & Desired Outcomes:**
*   Quickly and definitively verify 100% compliance across all jurisdictions without relying on the target company's tribal knowledge.
*   Access a cryptographically secure, immutable record of past compliance filings and the mathematical logic behind them.

**Feature Focus:**
He is the primary consumer of the "Clean Bill of Health" M&A Button. He heavily relies on the immutable state history stored in MongoDB Atlas and the vaulted, original municipal PDFs secured in GCP Cloud Storage, mapped via temporary signed URLs.

---

### 5. The Growth Operator: CAS End-Client (CEO / Finance Director)
**Demographics & Role:**
*   **Name:** Emily, 38
*   **Context:** Finance Director at a 50-person remote-first startup. She completely outsources her accounting to David's CAS firm. She does *not* log into the RegTech platform; her entire experience is mediated through her own QuickBooks Online (QBO) environment.
*   **Usage Frequency:** Weekly (During her standard AP bill approval runs).

**Pain Points:**
*   **Unexpected Outflows:** She hates seeing random $50 or $150 bills for "Cuyahoga Falls Gross Receipts Tax" appear in her AP queue without context.
*   **Siloed Communication:** Tracking down her outsourced CPA to explain a micro-transaction wastes time and creates friction.
*   **Dashboard Fatigue:** She refuses to adopt another software dashboard just to see what local taxes she owes.

**Goals & Desired Outcomes:**
*   Understand exactly what she is paying for, and why, without leaving her existing QBO workflow.
*   Maintain absolute control over cash disbursement while trusting that the compliance research is handled flawlessly in the background.

**Feature Focus:**
Her experience is entirely defined by the platform's ERP-Integrated Payment Facilitation. Specifically, she benefits from the Plain-English "Why Did This Happen?" tooltips that the system's Vertex AI automatically injects into the *memo field* of the QBO AP Bill, allowing her to click "Approve" with complete confidence and zero context-switching.

## Functional Requirements

**Priority Definitions:**
*   **SHALL:** Mandatory requirement for the Minimum Viable Product (MVP). Failure to meet this requirement blocks launch.
*   **SHOULD:** High-priority requirement. Strongly desired for MVP, but can be deferred to a fast-follow phase if engineering resources are critically constrained.
*   **MAY:** Stretch goal or future enhancement. Not required for MVP.

---

### Foundation & Security

**FR-0.01: Secure Credential Management**
*   **Priority:** SHALL
*   **Description:** The system must provide a secure, RBAC-protected interface for clients and admins to upload login credentials required for accessing guarded municipal web portals.
*   **Acceptance Criteria:**
    *   **Given** a user with appropriate permissions navigates to the 'Jurisdiction Credentials' section
    *   **When** they input a username and password for a specific municipal portal
    *   **Then** the system encrypts the credentials using AES-256 before saving to MongoDB Atlas, ensuring the plaintext values are only ever accessible in-memory by authorized `crewAI` agents executing a specific `ScrapeJob`.

---

### Epic 1: ERP Nexus Trigger Intelligence Engine

**FR-1.01: ERP Webhook Ingestion & Validation**
*   **Priority:** SHALL
*   **Description:** The system must expose a secure REST API endpoint to receive asynchronous event webhooks from target ERP systems (NetSuite, QuickBooks Online) and prevent processing duplicate events.
*   **Acceptance Criteria:**
    *   **Given** an incoming `POST` request to `/api/v1/webhooks/erp/nexus-event` from an ERP
    *   **When** the payload contains a valid `X-Hub-Signature` (HMAC-SHA256) matching the tenant's stored secret, and the ERP-provided `Idempotency-Key` (or a system-generated SHA-256 hash fallback of the payload) is not found in the recent cache
    *   **Then** the system accepts the payload (Returns `202 Accepted`), stores the key in MongoDB to prevent duplication, and pushes the event to the Redis Celery queue.

**FR-1.02: AI-Driven Nexus Evaluation & Error Handling**
*   **Priority:** SHALL
*   **Description:** A background Celery worker must process queued ERP events using Google Vertex AI to determine if a local compliance nexus has been triggered, handling both successes and AI failures deterministically.
*   **Acceptance Criteria:**
    *   **Given** a queued ERP telemetry payload containing location data
    *   **When** the Celery worker queries Vertex AI against the proprietary jurisdictional database
    *   **Then** the AI must return a structured JSON response indicating a confidence score between `0.0` and `1.0`. If confidence is `> 0.80`, create a `NexusTriggerEvent` in the `FLAGGED` state. If `< 0.40`, set to `DISMISSED`. 
    *   **And If** Vertex AI encounters an API error, times out after retries, or returns an uninterpretable non-JSON string, the system logs the error, flags the event as `AI_ERROR`, and pushes it to an admin review queue.

**FR-1.03: Human-in-the-Loop Nexus Review**
*   **Priority:** SHOULD
*   **Description:** If Vertex AI returns an ambiguous confidence score (`0.40` to `0.79`), the system must pause automation and require manual user review to prevent false positives/negatives.
*   **Acceptance Criteria:**
    *   **Given** a `NexusTriggerEvent` generated with a confidence score of `0.65`
    *   **When** the user logs into the React dashboard
    *   **Then** the event is prominently displayed in a "Needs Review" queue, requiring the user to explicitly click "Confirm Trigger" or "Dismiss" before it converts into a `ComplianceTask`.

---

### Epic 2: Multi-Agent Municipal Scraping Engine

**FR-2.00: Jurisdictional Data Ingestion & Maintenance**
*   **Priority:** SHALL
*   **Description:** The system must maintain a central, proprietary jurisdictional database that maps US locations to specific municipal web portals, serving as the source of truth for AI agents.
*   **Acceptance Criteria:**
    *   **Given** an administrator specifies a new state or county to onboard
    *   **When** the system executes a predefined initial onboarding workflow
    *   **Then** the system populates the jurisdictional database in MongoDB with initial municipal URLs, basic metadata, and required schedule types, establishing the queue for future `ScrapeJob` executions.

**FR-2.01: Agentic Website Scraping**
*   **Priority:** SHALL
*   **Description:** The system must utilize crewAI agents to periodically navigate the URLs defined in the jurisdictional database (FR-2.00) to extract updated PDF forms, fee schedules, and filing deadlines.
*   **Acceptance Criteria:**
    *   **Given** a scheduled `ScrapeJob` for "Cook County Employer Tax"
    *   **When** the crewAI agent navigates the target URL and detects a new PDF link or a change in the page's core HTML structure indicating a fee update
    *   **Then** the agent downloads the PDF, uploads it to GCP Cloud Storage, and transitions the `ScrapeJob` state to `IN_PROGRESS` for OCR parsing.

**FR-2.02: AI Multimodal PDF Parsing & Anomaly Detection**
*   **Priority:** SHALL
*   **Description:** The system must use Vertex AI Vision to perform OCR on archaic municipal PDFs, extracting key-value pairs while guarding against hallucinated or wildly inaccurate fee data.
*   **Acceptance Criteria:**
    *   **Given** an `IN_PROGRESS` `ScrapeJob` with a linked GCP Storage PDF
    *   **When** Vertex AI processes the document
    *   **Then** it updates the `JurisdictionRequirement` schema in MongoDB with the extracted structured data. If the AI detects a base fee or dynamic percentage that deviates by more than 20% from historical data for that jurisdiction, or if the overall AI confidence is `< 0.90`, the `ScrapeJob` state updates to `REVIEW_REQUIRED`.

---

### Epic 3: Task Ledger & Compliance Calculation Engine

**FR-3.01: Dynamic Liability Calculation**
*   **Priority:** SHALL
*   **Description:** The system must calculate the final compliance fee by mathematically applying the parsed `JurisdictionRequirement` rules against the specific `Company` telemetry.
*   **Acceptance Criteria:**
    *   **Given** an approved `NexusTriggerEvent` converting into a `ComplianceTask`
    *   **When** the system applies the municipal math rules (e.g., "$50 base + 1.5% of regional payroll")
    *   **Then** the system calculates the exact `liability_amount` and transitions the task to `READY_FOR_APPROVAL`.

**FR-3.02: Missing Information Prompting (`INFO_NEEDED`)**
*   **Priority:** SHALL
*   **Description:** If the ERP telemetry is insufficient to complete the tax calculation (e.g., exact square footage of a warehouse is missing), the system must explicitly request it from the user.
*   **Acceptance Criteria:**
    *   **Given** a `ComplianceTask` attempting a calculation
    *   **When** a required variable is missing from the `Company` profile
    *   **Then** the task state changes to `INFO_NEEDED` and the React UI generates an input form for the user to provide the missing variable.

**FR-3.03: "Why Did This Happen?" AI Tooltips**
*   **Priority:** SHOULD
*   **Description:** The system must generate a human-readable explanation of why a task was created and exactly how the fee was calculated, ensuring absolute transparency.
*   **Acceptance Criteria:**
    *   **Given** a `READY_FOR_APPROVAL` task
    *   **When** the user views the task details in the dashboard
    *   **Then** the UI displays an AI-generated string explaining the trigger and the specific data points used in the calculation (e.g., "You ran payroll of $45,000 for John Doe in Zip Code 44221, triggering the $50 base fee + 1.5% dynamic payroll tax").

**FR-3.04: M&A "Clean Bill of Health" Report Generation**
*   **Priority:** MAY
*   **Description:** The system must be capable of exporting a consolidated audit trail of all compliance tasks for external diligence.
*   **Acceptance Criteria:**
    *   **Given** a user clicking the "Export Audit Report" button
    *   **When** the system queries the MongoDB ledger
    *   **Then** it generates and downloads a watermarked PDF detailing all historic and active `ComplianceTask` records, grouped by jurisdiction, with links to vaulted municipal receipts.

**FR-3.05: Immutable Compliance Ledger**
*   **Priority:** SHALL
*   **Description:** The system must maintain an immutable, time-stamped ledger of all state transitions and calculations to satisfy stringent auditor requirements.
*   **Acceptance Criteria:**
    *   **Given** any state change to a `NexusTriggerEvent` or `ComplianceTask` (e.g., `FLAGGED` to `READY_FOR_APPROVAL`)
    *   **When** the state transition is committed to the database
    *   **Then** a new, non-modifiable record is appended to the `ComplianceLedger` collection in MongoDB Atlas, capturing the timestamp, acting user ID, prior state, new state, and the exact snapshot of data used for the transition.

**FR-3.06: Compliance Task Dispute Workflow**
*   **Priority:** SHALL
*   **Description:** Users must be able to formally dispute a calculated or AI-generated task to handle edge cases or incorrect ERP data gracefully.
*   **Acceptance Criteria:**
    *   **Given** a `ComplianceTask` in the `READY_FOR_APPROVAL` or `ERP_ACCEPTED` state
    *   **When** a user clicks "Dispute Task" and provides a mandatory text reason
    *   **Then** the task state immediately transitions to `DISPUTED`, halting any automated AP syncing or payment clearance tracking. The task is routed to a dedicated `DISPUTE_REVIEW` admin queue, and an alert is generated for the designated oversight role (e.g., CAS Partner).

---

### Epic 4: ERP-Integrated Payment Facilitation

**FR-4.01: Accounts Payable (AP) Bill Syncing**
*   **Priority:** SHALL
*   **Description:** Upon user approval in the dashboard, the system must generate a fully coded AP Bill directly in the target ERP without holding or transmitting client funds. *(Note: Exact payload structure and base64 formatting must adhere to the external QBO/NetSuite API Data Contract document).*
*   **Acceptance Criteria:**
    *   **Given** a `ComplianceTask` in the `PAYMENT_APPROVED` state
    *   **When** the Celery AP Sync Worker executes `POST /api/v1/erp/ap-bills/sync`
    *   **Then** the system pushes a payload to the ERP's REST API containing the vendor mapped via `FR-4.02 Vendor Semantic Matching`, the calculated fee, the plain-English memo (`FR-3.03`), and the encoded PDF attachment. The local state updates to `ERP_ACCEPTED`.

**FR-4.02: Vendor Semantic Matching**
*   **Priority:** SHOULD
*   **Description:** The system must intelligently match the municipal payee name to an existing vendor record in the client's ERP to prevent duplicate vendor creation.
*   **Acceptance Criteria:**
    *   **Given** a municipal payee name of "Treasurer, City of Chicago" required for an AP Bill sync
    *   **When** preparing the AP Sync payload
    *   **Then** Vertex AI embeddings evaluate the client's ERP vendor list and selects an existing match (e.g., "City of Chicago Dept of Rev") if confidence is `> 0.85`, or initiates the creation of a new vendor record in the ERP if no match exists.

**FR-4.03: Inbound Payment Clearance Webhook**
*   **Priority:** SHALL
*   **Description:** The system must track when the client's internal AP workflow actually settles the bill to close the compliance loop.
*   **Acceptance Criteria:**
    *   **Given** an `ERP_ACCEPTED` `ApBillSyncRecord` 
    *   **When** the system receives an inbound webhook from the ERP (via `POST /api/v1/webhooks/erp/payment-cleared`) matching the previously synced `erp_bill_id`
    *   **Then** the corresponding `ComplianceTask` state is updated to `COMPLETED` and the overarching lifecycle is closed.

## Non-Functional Requirements

### 1. Performance & Scalability

**NFR-1.01: Webhook Ingestion Latency**
*   **Target:** The `POST /api/v1/webhooks/erp/nexus-event` endpoint must validate the HMAC signature, check the idempotency cache, queue the event in Redis, and return a `202 Accepted` response within **500ms (p95)** and **800ms (p99)** under peak load.
*   **Rationale:** ERP webhooks often have strict timeout thresholds (e.g., 3-5 seconds). Synchronous blocking operations must be pushed to background Celery workers to prevent webhook retries from the ERP.

**NFR-1.02: Concurrent Entity Processing**
*   **Target:** The system architecture (FastAPI + Celery + MongoDB) must horizontally scale to support a minimum of **500 concurrent client entities** (tenants) without degradation in ingestion latency or background job processing times.
*   **Rationale:** Required to support the multi-tenant CAS Partner persona (David) managing dozens of client files simultaneously.

**NFR-1.03: "Time-to-Value" Processing SLA**
*   **Target:** The end-to-end automated workflow—from the moment an ERP webhook is successfully ingested to the moment a `ComplianceTask` is placed in the `READY_FOR_APPROVAL` state—must complete within **5 minutes (p95)** for critical nexus events (e.g., new state payroll) and **15 minutes (p95)** for standard triggers (e.g., routine gross receipts), excluding tasks requiring human-in-the-loop fallback.
*   **Rationale:** Ensures users experience the "invisible shield" magic promptly after an ERP event occurs, driving trust and minimizing the anxiety of invisible liabilities.

**NFR-1.04: AP Sync Execution Latency**
*   **Target:** Upon user approval in the React dashboard, the transition from `PAYMENT_APPROVED` to executing the ERP API push and updating the state to `ERP_ACCEPTED` must occur within **5 seconds (p95)**.
*   **Rationale:** Provides immediate, snappy feedback to the user in the UI that their approval action was successfully registered with their source-of-truth ERP.

**NFR-1.05: Scraping Agent Scalability & Monitoring Frequency**
*   **Target:** The `crewAI` agent architecture must support simultaneously monitoring up to **5,000 active municipal web portals**. Critical jurisdictions (historically high-volatility) must be successfully scraped every **24 hours**, and all standard jurisdictions must be scraped every **72 hours**.
*   **Rationale:** Ensures comprehensive, up-to-date coverage across the "long tail" of jurisdictions without overwhelming the background worker infrastructure.

---

### 2. Security & Data Privacy

**NFR-2.01: Credential Encryption at Rest**
*   **Target:** All municipal portal login credentials (usernames, passwords, API tokens) must be encrypted at rest in MongoDB Atlas using **AES-256-GCM** or stronger. The encryption keys must be strictly managed via **GCP KMS with automated annual rotation configured**.
*   **Rationale:** A critical trust requirement for CAS partners and Enterprise VPs storing sensitive access data within a third-party platform.

**NFR-2.02: Money Transmitter Liability Avoidance**
*   **Target:** The system architecture must physically and programmatically prohibit the ingestion, storage, or transmission of client bank account routing numbers or primary credit card PANs intended for municipal fee disbursement.
*   **Rationale:** Eliminates the extreme regulatory burden and legal liability of registering as a Money Services Business (MSB) across all 50 states.

**NFR-2.03: Compliance Standards & Data Privacy**
*   **Target:** The system infrastructure and operational processes must be designed to achieve and maintain **SOC 2 Type II** compliance within 12 months of MVP launch, and adhere to relevant data privacy regulations (e.g., CCPA for California clients, if applicable) for the handling of all client and PII data.
*   **Rationale:** A hard prerequisite for selling SaaS products into mid-market enterprise finance and IT departments.

**NFR-2.04: Multi-Tenant Data Isolation**
*   **Target:** The application logic and database schema must enforce strict logical separation of tenant data (using `company_id` partitioning). A user authenticated for Company A must have zero programmatic or API ability to query, view, or modify data belonging to Company B.
*   **Rationale:** Prevents catastrophic cross-contamination of highly sensitive financial and geographic data across the CAS firm portfolio.

**NFR-2.05: Audit Trail Integrity**
*   **Target:** All user interactions, task state transitions, and system actions (e.g., AI evaluations, AP Bill syncs) must be permanently logged in an immutable audit trail.
*   **Rationale:** Ensures absolute non-repudiation and clear traceability, supporting the M&A diligence needs of the "Verifier" persona.

---

### 3. Reliability, Availability, & Maintainability

**NFR-3.01: Platform Uptime SLA**
*   **Target:** The core REST API and React dashboard must maintain an availability of **99.9%** (approx. 43.8 minutes of allowable downtime per month).
*   **Rationale:** Essential for ensuring users can review and approve time-sensitive AP bills without facing system outages near tax deadlines.

**NFR-3.02: Recovery Point Objective (RPO) and Recovery Time Objective (RTO)**
*   **Target:** The system must support an RPO of **1 hour** (maximum acceptable data loss) and an RTO of **4 hours** (maximum time to restore full service from a catastrophic failure).
*   **Rationale:** Ensures that in the event of a massive regional cloud failure, the immutable compliance ledger and pending tasks are preserved and quickly restored.

**NFR-3.03: Zero Silent Failures (Observability)**
*   **Target:** 100% of unhandled exceptions, Celery task timeouts, and Vertex AI API failures must be logged with a unique `x-correlation-id` and immediately trigger an alert to the engineering on-call rotation via Datadog/PagerDuty within **2 minutes** of occurrence.
*   **Rationale:** Fulfills the "Transparent Agent at Work" vision, ensuring the system can gracefully degrade rather than quietly dropping compliance tasks.

**NFR-3.04: Workflow Resilience Monitoring**
*   **Target:** 100% of tasks entering fallback states (`AI_ERROR`, `REVIEW_REQUIRED`, `INFO_NEEDED`, `DISPUTED`) must be continuously monitored for volume and aging. Alerts must trigger within **5 minutes** if a queue exceeds predefined thresholds (e.g., `AI_ERROR` queue > 10 items for > 1 hour).
*   **Rationale:** Ensures that human-in-the-loop and error handling mechanisms are actively managed and do not become operational "black holes."

**NFR-3.05: Data Retention & Archiving Policy**
*   **Target:** All `ComplianceTask` records, `ComplianceLedger` entries, and associated documents (vaulted PDFs) must be retained for a minimum of **7 years**. Automated archiving to cold storage (e.g., GCP Cloud Storage Coldline) must occur after **3 years**, retaining immediate retrieval capabilities via signed URLs.
*   **Rationale:** Legally essential for compliance, regulatory audits, and long-term M&A due diligence.

**NFR-3.06: External Source Adaptability (Maintainability)**
*   **Target:** The system architecture must allow the engineering team to deploy updates to `crewAI` agents to adapt to minor municipal website UI/form changes within **48 hours**, and major structural portal changes within **5 business days**.
*   **Rationale:** Directly addresses the volatility of municipal data sources, ensuring the platform's core data engine remains reliable despite a chaotic external environment.

---

### 4. Usability & Accessibility

**NFR-4.01: AI Confidence Transparency**
*   **Target:** Any data extracted by Vertex AI from a municipal PDF and displayed to the user must visually indicate the AI's internal confidence score if the score is between 0.80 and 0.90 (e.g., via a yellow warning icon next to the extracted value).
*   **Rationale:** Builds trust with the "Exception Handler" persona (Marcus) by highlighting exactly where human-in-the-loop verification is most valuable.

**NFR-4.02: UI Responsiveness**
*   **Target:** The main React dashboard grid displaying `ComplianceTasks` must render and become interactive within **1.5 seconds (p95)** for a tenant possessing up to 10,000 historical and active tasks.
*   **Rationale:** Prevents user frustration and dashboard fatigue for high-volume CAS partners managing extensive multi-state portfolios.

**NFR-4.03: Browser Compatibility**
*   **Target:** The React dashboard must be fully functional and visually consistent across the latest two major versions of Google Chrome, Mozilla Firefox, Apple Safari, and Microsoft Edge.
*   **Rationale:** Standard SaaS usability baseline to support diverse corporate IT environments.

## Edge Cases

### 1. Geographical & Entity Triggers

**EC-1.01: Multi-State/Multi-Jurisdiction Nexus for a Single Employee**
*   **Condition:** An employee lives in one local jurisdiction (e.g., Cuyahoga Falls, OH) but works physically in another (e.g., Cleveland, OH), triggering distinct, overlapping local payroll or transit taxes in both municipalities simultaneously based on a single ERP payload.
*   **System Behavior:** Vertex AI evaluates the complete geographic profile (Home vs. Work location) and generates *two distinct* `ComplianceTask` records linked to the single `NexusTriggerEvent`. The React UI presents them as a grouped workflow, allowing the user to approve both AP Bills with shared context.

**EC-1.02: Zero-Dollar Liability with Mandatory Filing Requirement**
*   **Condition:** A company triggers a local nexus (e.g., registering a pop-up shop) but generates zero gross receipts for the period. The mathematical fee is $0.00, but the municipality legally requires a "Zero Return" filing to maintain the operating privilege.
*   **System Behavior:** The Math Engine calculates the liability as $0.00. Instead of dismissing the task, the system transitions to `READY_FOR_APPROVAL` with a $0 AP Bill value. Upon approval, the system pushes the $0 Bill to the ERP (for audit trail purposes) and attaches the AI-filled "Zero Return" PDF, satisfying the legal requirement without triggering a cash disbursement.

**EC-1.03: Rapid Transient Nexus (The "Short-Term Project" Problem)**
*   **Condition:** A company ships inventory to a new state for a 3-week project, triggering an ERP event, but subsequently closes the operation before the next filing deadline.
*   **System Behavior:** The system logs the initial `NexusTriggerEvent`. If subsequent ERP telemetry indicates the nexus is closed (e.g., inventory balance dropping to zero in that ZIP code), the system flags the active `ComplianceTask` with a "Transient Nexus Detected" warning. It displays a clear UI banner on the task detail page and provides a dedicated "File Final Return" button, which alters the task workflow to automatically select the "Final Filing" checkbox on the generated municipal PDF.

**EC-1.04: Persistent ERP Data Corruption**
*   **Condition:** The incoming ERP webhook data (e.g., payroll ZIP codes, asset values) is intermittently or consistently corrupted for a specific client, leading to a high volume of `DISMISSED` or `AI_ERROR` nexus triggers.
*   **System Behavior:** The system monitors the rate of `DISMISSED` or `AI_ERROR` events per client source. If thresholds are exceeded (e.g., >20% of events in a rolling 7-day window), it automatically pauses the ERP webhook ingestion for that specific tenant, transitions the integration state to `DATA_QUALITY_HOLD`, and alerts the platform administrator and the client's admin (Sarah/David) via email/Slack to investigate the source data issue before resuming.

### 2. Municipal Form & Scraping Anomalies

**EC-2.01: Un-Parsable or "Image-Only" Municipal Scans**
*   **Condition:** The `crewAI` scraper downloads a PDF from a county website, but it is an old, scanned document containing only rasterized images with handwritten overlays, defeating standard OCR and Vertex AI parsing.
*   **System Behavior:** Vertex AI registers a confidence score of `< 0.40`. The system gracefully degrades the `ScrapeJob` state to `REVIEW_REQUIRED` and alerts a platform administrator. The admin can manually input the form fields into the MongoDB `JurisdictionRequirement` schema via a secure backend UI to unblock downstream client tasks.

**EC-2.02: Mandated "Wet Signatures" or Physical Mail**
*   **Condition:** A specific local jurisdiction entirely rejects electronic filings and requires a physical, ink-signed paper form mailed with a physical check.
*   **System Behavior:** The AI parser identifies the "mail-in only" constraint. The `ComplianceTask` transitions to a specialized `MANUAL_ACTION_REQUIRED` state. The system drafts the AP Bill in the ERP as usual (to cut a physical check via the client's AP system) but prompts the user to print, sign, and mail the attached PDF manually, tracking the task completion via a "Mark as Mailed" user attestation button rather than a digital API sync.

**EC-2.03: Opaque or Discretionary Municipal Fee Math**
*   **Condition:** A municipality's fee schedule states that the fee is "determined by the City Assessor upon review of application," making deterministic mathematical pre-calculation impossible.
*   **System Behavior:** The Task Ledger AI Math Engine recognizes the missing deterministic rule. It sets the `liability_amount` to `NULL` and changes the task state to `INFO_NEEDED`. The UI instructs the user to submit the base registration form first. Simultaneously, the system creates a linked sub-task ("Input Final Assessed Fee") with a 14-day due date, ensuring the user is reminded to return to the dashboard and manually input the final amount once the Assessor's notice arrives by mail.

**EC-2.04: Defunct or Unreachable Municipal Portal**
*   **Condition:** A `crewAI` agent attempts to access a municipal URL from the jurisdictional database, but the domain is unreachable, returns a persistent 404/500 error for >24 hours, or indicates the municipality has been merged/dissolved.
*   **System Behavior:** The `ScrapeJob` transitions to a `JURISDICTION_UNREACHABLE` state. The system triggers a PagerDuty alert to platform admins to manually investigate the municipal boundary change or IT failure. Affected active `ComplianceTasks` for that jurisdiction are temporarily paused and flagged with an "Awaiting Portal Restoration" banner.

### 3. Payment & ERP Synchronization

**EC-3.01: ERP Accounting Period Closed During Sync**
*   **Condition:** A user clicks "Approve" on a `ComplianceTask` in the React dashboard, but the client's internal accounting team has already closed the financial period (e.g., month-end) in NetSuite or QBO. The REST API push fails with a `400 Closed Period` error.
*   **System Behavior:** The AP Sync Worker catches the specific ERP error code. It transitions the `ApBillSyncRecord` to `FAILED` and surfaces a critical alert in the React UI: *"Sync Failed: Accounting period closed in NetSuite. Please adjust the posting date and retry."* The user is provided a UI component to update the `posting_date` and re-trigger the sync.

**EC-3.02: "Out-of-Band" Manual Payment**
*   **Condition:** A VP of Tax panics about a deadline and logs directly into a municipal portal to pay a $50 fee via a corporate credit card, entirely bypassing the platform's AP Bill sync workflow.
*   **System Behavior:** The `ComplianceTask` remains in `READY_FOR_APPROVAL`. The user utilizes the "Dispute Task / Mark as Paid Externally" workflow. They upload the credit card receipt directly to the dashboard. The system vaults the receipt, updates the state to `COMPLETED_OUT_OF_BAND`, and explicitly skips generating the AP Bill in the ERP to prevent duplicate payment.

**EC-3.03: Vendor Name Collision in ERP**
*   **Condition:** During the semantic vendor matching phase, Vertex AI identifies two highly similar existing vendors in the client's ERP (e.g., "City of Chicago Tax" and "Chicago Dept of Revenue"), resulting in an ambiguous match confidence (`< 0.85`).
*   **System Behavior:** The AP Sync process pauses. The `ComplianceTask` transitions to `VENDOR_MATCH_REQUIRED`. The React UI presents the user with the two potential matches (pulled live from the ERP) and an option to "Create New Vendor," forcing deterministic human resolution before the AP Bill is pushed.

### 4. Lifecycle & Security Anomalies

**EC-4.01: Retroactive Jurisdictional Changes**
*   **Condition:** A municipality announces a legislative change to a tax rate or deadline that applies retroactively to a period for which a `ComplianceTask` has already been calculated, paid, and marked as `COMPLETED`.
*   **System Behavior:** The system detects the retroactive change via `crewAI` agents updating the core `JurisdictionRequirement` schema. It queries the MongoDB `ComplianceLedger` for all `COMPLETED` tasks impacted by the retroactive date range. It automatically calculates the delta (underpayment/overpayment) and generates a new, linked `ComplianceTask` labeled "Retroactive Adjustment," prompting the user to approve a new AP Bill or log a credit memo.

**EC-4.02: Compromised Vaulted Credentials**
*   **Condition:** A client suspects, or an external security incident reveals, that their encrypted municipal login credentials have been compromised.
*   **System Behavior:** The system provides a "Revoke Credentials" emergency action in the Admin UI. Triggering this immediately rotates the affected GCP KMS keys, destroys the compromised plaintext string in memory, and transitions the jurisdiction's status for that tenant to `CREDENTIALS_INVALID`. All scheduled `crewAI` automated filings for that tenant/jurisdiction are paused until the client uploads a newly generated password.

**EC-4.03: Recurring Compliance Obligation Renewal**
*   **Condition:** A previously completed `ComplianceTask` (e.g., an initial business license registration) inherently triggers an annual or periodic renewal obligation, which must not rely on a fresh ERP trigger.
*   **System Behavior:** Upon the successful `COMPLETED` state of the initial task, a background Celery beat schedule references the `JurisdictionRequirement` schema to proactively schedule a new `NexusTriggerEvent` for the renewal period (e.g., 60 days before expiration). This new event inherits the approved telemetry from the previous year, placing a "Renewal Ready" task directly into the user's `READY_FOR_APPROVAL` queue.

**EC-4.04: Human-in-the-Loop Misjudgment (False Positive Override)**
*   **Condition:** A user (e.g., Marcus, the Exception Handler) mistakenly clicks "Confirm Trigger" on a `REVIEW_REQUIRED` nexus event that was actually a false positive, causing the system to draft an unnecessary AP Bill.
*   **System Behavior:** The user can initiate the Dispute Workflow on the `READY_FOR_APPROVAL` task, explicitly selecting "Mark as False Positive." If the bill has already reached the `ERP_ACCEPTED` state, the system attempts to send a `DELETE` or `VOID` payload via the ERP's REST API. Simultaneously, the system monitors for a high frequency of such user-initiated reversals per tenant, triggering a summary alert to the VP of Tax (Sarah) highlighting a potential need for operator retraining.

## Error Handling

### 1. Inbound ERP Webhook Ingestion Errors

**EH-1.01: Invalid HMAC Signature (`401 Unauthorized`)**
*   **Trigger:** The `X-Hub-Signature` header from the inbound NetSuite/QBO webhook does not match the cryptographic hash generated using the tenant's stored webhook secret.
*   **System Response:** The FastAPI Gateway immediately rejects the payload, returning a `401 Unauthorized`. 
*   **Recovery & Logging:** The payload is dropped completely. The system logs a `SECURITY_WARNING` to Datadog containing the originating IP address and tenant ID to monitor for potential unauthorized access attempts.
*   **User Experience:** Silent to the end-user. The ERP's internal webhook log will register the failure.

**EH-1.02: Webhook Idempotency Collision (`202 Accepted` - Silent Drop)**
*   **Trigger:** An inbound webhook is received with an `Idempotency-Key` (or payload hash) that already exists in the Redis cache within the 48-hour TTL window.
*   **System Response:** The system recognizes the retry/duplicate from the ERP. It returns a `202 Accepted` to satisfy the ERP's delivery requirement but actively drops the event before Celery queueing.
*   **Recovery & Logging:** Logged internally as an `IDEMPOTENCY_DROP` for telemetry, requiring no system recovery action.
*   **User Experience:** Silent to the user, preventing duplicate `ComplianceTask` generation in the UI.

### 2. AI & Multi-Agent Processing Errors

**EH-2.01: Vertex AI API Timeout or 5xx Error**
*   **Trigger:** A Celery worker attempting to evaluate a nexus trigger or parse a municipal PDF encounters a timeout or a 5xx response from the Google Vertex AI API.
*   **System Response:** The Celery worker initiates an exponential backoff retry sequence (e.g., 3 retries at 1m, 5m, and 15m intervals).
*   **Recovery & Logging:** If all retries fail, the associated `NexusTriggerEvent` transitions to `AI_ERROR`, or the `ScrapeJob` transitions to `FAILED`. A PagerDuty alert is sent to engineering.
*   **User Experience:** The `NexusTriggerEvent` appears in the React dashboard's "Needs Review" queue with a system banner: *"AI processing temporarily unavailable. Proceed manually or wait for auto-retry."*

**EH-2.02: AI Math Hallucination / Validation Failure**
*   **Trigger:** Post-Vertex AI parsing, the deterministic math validation layer detects that the extracted `total_fee` does not equal the sum of the extracted `base_fee` + `dynamic_calculation`.
*   **System Response:** The system rejects the AI's calculation. It prevents the creation of a `READY_FOR_APPROVAL` task.
*   **Recovery & Logging:** The task transitions to an `INFO_NEEDED` state. The discrepancy is logged to Datadog for model fine-tuning analysis.
*   **User Experience:** The user receives a dashboard notification: *"Fee calculation requires verification due to ambiguous municipal form."* The UI highlights the conflicting numbers on the side-by-side PDF view and requires manual user input to resolve the math.

**EH-2.03: crewAI Scraper Blocked (403 Forbidden / CAPTCHA)**
*   **Trigger:** A municipal portal firewall (e.g., Cloudflare) blocks the crewAI agent during a scheduled `ScrapeJob`.
*   **System Response:** The crewAI orchestrator automatically rotates the residential proxy IP and alters the user-agent string to attempt bypass.
*   **Recovery & Logging:** If blocked after 3 proxy rotation attempts, the `ScrapeJob` state transitions to `FAILED_BLOCKED`.
*   **User Experience:** The platform administrator's dashboard flags the jurisdiction. The system displays: *"Scraper blocked by Cook County portal. Manual PDF upload required for Q3 updates."* 

### 3. ERP-Integrated AP Sync Errors

**EH-3.01: ERP Accounting Period Closed (`400 Bad Request`)**
*   **Trigger:** The Celery AP Sync Worker attempts to push an approved AP Bill via REST API to QBO/NetSuite, but the target financial period is locked/closed by the client's controller.
*   **System Response:** The AP Sync Worker parses the explicit ERP error string. It halts the sync process immediately and transitions the `ApBillSyncRecord` to `FAILED`. **Crucially, the system does not attempt to automatically guess a new open period.**
*   **Recovery & Logging:** Logged as `ERP_SYNC_FAILED_PERIOD_CLOSED`. 
*   **User Experience:** The user is alerted in the UI: *"Sync Failed: Accounting period closed in NetSuite. Please adjust the posting date to an open period and retry."* The UI provides a date-picker override to re-trigger the sync.

**EH-3.02: ERP API Rate Limiting (`429 Too Many Requests`)**
*   **Trigger:** The system attempts to push a high volume of AP Bills simultaneously, exceeding the client's API tier limits for QBO/NetSuite.
*   **System Response:** The worker intercepts the `429` response and parses the `Retry-After` header (if available) or defaults to a standard Celery backoff.
*   **Recovery & Logging:** The `ApBillSyncRecord` remains in `PENDING_PUSH` state. The task is paused and re-queued according to the backoff schedule.
*   **User Experience:** The UI status indicator next to the approved task shows a spinning *"Syncing to ERP (Delayed by API limits)..."* message, maintaining transparency without requiring user intervention.

**EH-3.03: Upstream ERP Outage (`502/503/504`)**
*   **Trigger:** NetSuite or QuickBooks Online experiences a widespread API outage during AP Sync.
*   **System Response:** The system implements a Circuit Breaker pattern. After successive 5xx failures across multiple tenants for a specific ERP, the circuit trips, pausing all outbound syncs to that ERP.
*   **Recovery & Logging:** Syncs remain in `PENDING_PUSH`. The system periodically sends ping requests to the ERP health endpoint; when stable, the circuit closes and the Celery queue resumes processing.
*   **User Experience:** A global banner appears on the React dashboard: *"QuickBooks Online API is currently experiencing an outage. Approved bills are queued and will sync automatically once service is restored."*

**EH-3.04: ERP API Key Expiration / Invalidation**
*   **Trigger:** The Celery AP Sync Worker or an initial ERP webhook configuration attempt fails because the client's OAuth token or API Key for NetSuite/QBO has expired or been manually revoked.
*   **System Response:** The worker parses the unauthorized error code from the ERP. It immediately halts any further retry attempts for that specific tenant to prevent permanent IP bans from the ERP. The tenant's integration status transitions to `AUTH_INVALID`.
*   **Recovery & Logging:** Logged as `ERP_AUTH_ERROR`. A low-urgency PagerDuty alert is sent to engineering for tracking.
*   **User Experience:** A prominent banner appears on the user's React dashboard: *"ERP Integration Suspended: Your QuickBooks Online connection requires re-authentication."* The UI provides a direct "Reconnect QBO" OAuth link for the client to immediately resolve the issue.

### 4. Platform Access & Infrastructure Errors

**EH-4.01: User Authentication & Authorization Failure**
*   **Trigger:** A user attempts to log into the React dashboard with invalid credentials, or an authenticated user attempts an API call targeting a `company_id` for which they lack Role-Based Access Control (RBAC) permissions.
*   **System Response:** The API Gateway immediately rejects the request, returning a `401 Unauthorized` for bad credentials or a `403 Forbidden` for RBAC violations.
*   **Recovery & Logging:** The system increments a failed-login counter in Redis to mitigate brute-force attacks (triggering a temporary IP block after 5 failures). The event is logged to Datadog as `AUTH_FAILURE` or `RBAC_VIOLATION`.
*   **User Experience:** The user sees a standard "Invalid email or password" error on the login screen, or an "Access Denied: You do not have permission to view this client's workspace" overlay if navigating to an unauthorized URL.

**EH-4.02: Internal Database or Service Communication Failure**
*   **Trigger:** A core system component (e.g., FastAPI application, Celery worker) fails to connect to MongoDB Atlas, the Redis broker, or the GCP Secret Manager.
*   **System Response:** For asynchronous background tasks, the Celery worker catches the connection exception and initiates an exponential backoff retry logic. For synchronous REST API requests, the FastAPI endpoint catches the timeout and returns a `500 Internal Server Error` or `503 Service Unavailable`.
*   **Recovery & Logging:** The service logs a `DB_CONNECTION_ERROR` or `INTERNAL_SERVICE_ERROR`. If background task retries are exhausted, the affected entity (e.g., `ComplianceTask`) is transitioned to a `SYSTEM_ERROR` state. A critical PagerDuty alert is instantly routed to the engineering on-call rotation.
*   **User Experience:** If executing a synchronous action in the React UI, the dashboard displays a global banner: *"System experiencing temporary connectivity issues. Please try again shortly."* Asynchronous tasks simply remain in their pending states until the connection is restored.

### 5. User Interface & Data Validation Errors

**EH-5.01: User Input Data Validation Errors**
*   **Trigger:** A user attempts to submit data via the React UI (e.g., inputting a final assessed fee for an `INFO_NEEDED` task, or submitting a dispute reason) that fails predefined schema validation rules (e.g., submitting a string instead of a float, or leaving a mandatory field blank).
*   **System Response:** The React frontend intercepts the failure and prevents the API call. If the frontend validation is bypassed, the FastAPI backend evaluates the payload against its Pydantic models and immediately rejects the request, returning a `400 Bad Request` with a JSON array of the specific field violations.
*   **Recovery & Logging:** Backend validation failures are logged as `INPUT_VALIDATION_ERROR` for telemetry to identify confusing UI elements.
*   **User Experience:** Clear, immediate, actionable error messages are displayed directly beneath the problematic input fields in the UI (e.g., *"Fee amount must be a valid number"* or *"Dispute reason is required"*), preventing silent submission failures.

## Success Metrics

### 1. Primary Business Outcomes (The North Star)

**SM-1.01: Penalty Eradication Rate**
*   **Target:** 0% localized compliance penalty rate for entities and jurisdictions fully managed within the platform.
*   **Measurement:** Monthly aggregate of support tickets or system-logged `ComplianceTask` disputes tagged with "Received Penalty/Notice," verified against the client's connected ERP liability ledger.
*   **Timeframe:** Achieve and maintain 0% within 90 days of onboarding a new client entity.

**SM-1.02: Time-to-Value (Automation Velocity)**
*   **Target:** The average elapsed time from a valid `NexusTriggerEvent` creation (via ERP webhook) to a generated `READY_FOR_APPROVAL` AP Bill draft must be **< 24 hours**.
*   **Measurement:** MongoDB query calculating the delta between `created_at` timestamp on `NexusTriggerEvent` and the transition timestamp to `READY_FOR_APPROVAL` for the linked `ComplianceTask`.
*   **Timeframe:** Track continuously; 95th percentile (p95) must drop below 24 hours within 3 months of MVP launch.

**SM-1.03: Jurisdiction Coverage & Data Moat Growth**
*   **Target:** Successfully onboard and actively monitor a minimum of 2,500 distinct municipal jurisdictions within 6 months post-MVP launch, scaling to 5,000 active jurisdictions within 12 months.
*   **Measurement:** Count of active `JurisdictionRequirement` schemas with an associated `ScrapeJob` in an `ACTIVE` (non-failing) status in MongoDB.
*   **Rationale:** Directly measures the platform's ability to tackle the "long tail" problem and build the proprietary dataset (the "data moat") that legacy incumbents lack.
*   **Timeframe:** Measured monthly against the 6-month and 12-month scaling targets.

**SM-1.04: Client Activation & Retention**
*   **Target:** >80% of onboarded client entities must maintain an active, un-paused ERP webhook integration and successfully process at least one `ComplianceTask` per quarter. Maintain >90% client retention quarter-over-quarter.
*   **Measurement:** Count of active webhook subscriptions per tenant, quarterly count of `COMPLETED` tasks per tenant, and standard SaaS gross revenue retention tracking.
*   **Rationale:** Because we explicitly aim to *reduce* time-in-app (see SM-3.02), background system reliance and successful task completion are our primary proxies for active product engagement and value realization.
*   **Timeframe:** Measured monthly and quarterly.

**SM-1.05: Estimated Financial Impact of Penalty Avoidance**
*   **Target:** Annually demonstrate an estimated average of > $15,000 in penalties avoided per fully managed mid-market client entity.
*   **Measurement:** A programmatic proxy model that multiplies the number of `ComplianceTasks` successfully managed (where historical client baseline data indicates a high probability of missing the filing) by the jurisdiction's standard late fee/compounding penalty structure, aggregating the total "invisible savings."
*   **Timeframe:** Measured and reported annually during client business reviews.

**SM-1.06: Customer Peace of Mind Score (CSAT/NPS)**
*   **Target:** Achieve an average CSAT score of > 4.5/5 (or an NPS > 50) specifically regarding the reduction of compliance-related anxiety.
*   **Measurement:** Bi-annual in-app survey targeting the VP of Tax and CAS Partner personas featuring the specific prompt: *"How much has the Autonomous Operating Privilege Engine reduced your anxiety regarding localized compliance and M&A due diligence?"*
*   **Rationale:** Directly measures the emotional impact and value proposition of the "invisible shield" established in the Executive Summary.
*   **Timeframe:** Measured bi-annually.

### 2. Automation & AI Efficacy Metrics

**SM-2.01: Straight-Through Processing (STP) Rate**
*   **Target:** > 85% of all generated `ComplianceTasks` transition from `DRAFT` to `READY_FOR_APPROVAL` without hitting the `INFO_NEEDED` or `REVIEW_REQUIRED` fallback states.
*   **Measurement:** Ratio of tasks completing the happy path vs. total tasks generated per month via Datadog state transition dashboards.
*   **Timeframe:** Reach 85% within 6 months post-launch as Vertex AI model accuracy improves through interaction logging.

**SM-2.02: Agent Resiliency (Scraper Success Rate)**
*   **Target:** > 90% of `crewAI` scheduled `ScrapeJob` executions complete successfully (downloading updated PDFs and extracting valid data) without triggering a `FAILED` or `REVIEW_REQUIRED` state due to municipal UI changes.
*   **Measurement:** Datadog metrics tracking the terminal state of all `ScrapeJob` worker processes.
*   **Timeframe:** Ongoing. A drop below 90% in a rolling 7-day window triggers an engineering P1 alert.

**SM-2.03: AI Validation Discrepancy Rate**
*   **Target:** < 5% of Vertex AI extracted municipal math rules fail the deterministic post-LLM validation check (i.e., `total_fee` does not equal `base_fee` + `dynamic_calculation`).
*   **Measurement:** Count of `ComplianceTasks` specifically routed to `INFO_NEEDED` with the internal tag `MATH_VALIDATION_FAILURE`.
*   **Timeframe:** Achieve < 5% within 3 months of production data ingestion.

### 3. Operational & Integration Metrics

**SM-3.01: Frictionless ERP Resolution**
*   **Target:** Maintain a **99.9% AP Sync Success Rate** for bills pushed to QuickBooks Online and NetSuite.
*   **Measurement:** Ratio of `ApBillSyncRecord` transitions to `ERP_ACCEPTED` versus total sync attempts (excluding `400 Closed Period` user errors, focusing only on `5xx` or mapping failures).
*   **Timeframe:** Measured monthly, starting at MVP launch.

**SM-3.02: User Intervention Friction (Time-in-App)**
*   **Target:** The average time a user spends active in the React Dashboard per week should be **< 15 minutes**.
*   **Measurement:** Session duration tracking in Mixpanel or Amplitude.
*   **Rationale:** As explicitly stated in the product vision, high MAU or long session duration is an *anti-goal*. The system must act as an invisible shield; users should only log in to click "Approve" or clear explicit exceptions.
*   **Timeframe:** Monitor continuously; spikes above 15 minutes/week indicate poor AI confidence or confusing `INFO_NEEDED` UX.

### 4. Anti-Metrics (Leading Indicators of Failure)

**SM-4.01: High Dispute Rate**
*   **Threshold:** If > 10% of `READY_FOR_APPROVAL` tasks are marked as "Disputed/False Positive" by users in a given month.
*   **Action:** This indicates the `NexusTriggerEvent` AI evaluator is hallucinating rules or misinterpreting ERP telemetry. Requires immediate pause of webhook ingestion and retraining of the Vertex AI prompt templates.

## Dependencies

### 1. External Data & Infrastructure Dependencies

**DEP-1.01: ERP API Stability (NetSuite & QuickBooks Online)**
*   **Description:** The entire AP Bill generation workflow (FR-4.01) and webhook ingestion (FR-1.01) relies on the continued availability, backward compatibility, and acceptable rate limits of the Intuit (QBO) and Oracle (NetSuite) REST APIs.
*   **Criticality:** Blocker. If an ERP API undergoes a breaking change or extended downtime, automated compliance payments cease.
*   **Owner:** Backend Engineering Team.
*   **Mitigation:** Implement strict API versioning, robust Circuit Breaker patterns (EH-3.03), and subscribe to Intuit/Oracle developer status alerts. Design the webhook ingestion to fail gracefully and queue events if the ERP is unreachable.

**DEP-1.02: Google Vertex AI Availability & Model Drift**
*   **Description:** Nexus evaluation (FR-1.02) and multimodal PDF parsing (FR-2.02) are entirely dependent on Google Vertex AI (Gemini Pro/Vision).
*   **Criticality:** High. Complete failure degrades the system to a manual data-entry tool (`REVIEW_REQUIRED` state). Model drift could cause a spike in false positives/negatives.
*   **Owner:** AI/ML Engineering Team.
*   **Mitigation:** Implement programmatic confidence score monitoring (NFR-4.01). Maintain a human-in-the-loop fallback queue. Retain a secondary LLM provider (e.g., OpenAI) as a fallback API via a toggle if Vertex AI experiences a multi-day systemic failure.

**DEP-1.03: Municipal Website Volatility**
*   **Description:** The `crewAI` multi-agent scraper (FR-2.01) depends on 10,000+ local government websites remaining accessible and relatively consistent in their DOM structure.
*   **Criticality:** High. Municipalities frequently change layouts or block IP addresses, leading to stale compliance data.
*   **Owner:** Data Operations / Agent Engineering Team.
*   **Mitigation:** Utilize residential proxy rotation via `crewAI`. Enforce strict SLAs for agent updates (48h for UI changes per NFR-3.06). Maintain a manual Admin upload fallback (EH-2.01) for un-scrapeable sites.

**DEP-1.04: Google Cloud Platform (GCP) Core Services**
*   **Description:** The entire platform architecture (compute environments via GKE/ECS equivalents, networking, Cloud Storage for vaulted PDFs, Redis/Celery queueing infrastructure, MongoDB Atlas hosting, and KMS for credential encryption) relies on the continued availability and performance of GCP.
*   **Criticality:** Blocker. The system is inoperable without underlying cloud infrastructure.
*   **Owner:** DevOps / SRE Team.
*   **Mitigation:** Implement multi-region deployment strategies for core databases, leverage GCP's native redundancy across availability zones, and subscribe to GCP status alerts. Ensure rigorous infrastructure cost monitoring is in place via Datadog to prevent runaway auto-scaling.

### 2. Legal & Regulatory Dependencies

**DEP-2.01: Money Transmitter Exemption Status**
*   **Description:** The platform's operational model explicitly relies on *not* being classified as a Money Services Business (MSB) or money transmitter, as it only generates AP Bills (FR-4.01) and does not hold or move client cash.
*   **Criticality:** Blocker. Re-classification would require millions in licensing fees and fundamentally break the business model.
*   **Owner:** Legal & Compliance Counsel.
*   **Mitigation:** Legal counsel must review all API payload schemas and marketing language prior to MVP launch to ensure the platform is strictly defined as a data processor, not a payment gateway.

**DEP-2.02: SOC 2 Type II Compliance Readiness**
*   **Description:** To sell into mid-market ($50M+ ARR) enterprises and CAS firms, the platform infrastructure must meet SOC 2 Type II standards for security and confidentiality (NFR-2.03), particularly regarding credential vaulting (FR-0.01).
*   **Criticality:** High (Commercial Blocker). Lack of certification will stall M&A and enterprise procurement processes.
*   **Owner:** VP of Engineering / SecOps.
*   **Mitigation:** Engage a third-party auditing firm (e.g., Vanta or Drata) during Month 1 of MVP development to map MongoDB/GCP infrastructure to SOC 2 controls, ensuring continuous compliance tracking before launch.

### 3. Cross-Functional Dependencies

**DEP-3.01: Initial Jurisdictional Data Seeding**
*   **Description:** Before the AI agents can scrape (FR-2.01), a baseline proprietary database of municipal URLs, tax types, and baseline rules must be manually seeded and structured (FR-2.00).
*   **Criticality:** Blocker. The "Invisible Shield" cannot function without a baseline map of where to look.
*   **Owner:** Tax Subject Matter Experts (SMEs) / Data Entry Team.
*   **Mitigation:** Allocate dedicated SME resources (potentially outsourced) during Months 1-3 to manually map the top 2,500 highest-frequency US jurisdictions to provide the MVP with critical mass.

**DEP-3.02: Client ERP Authorization (OAuth)**
*   **Description:** The system cannot ingest webhooks or push AP Bills without the target client explicitly completing an OAuth 2.0 flow to authorize the application within their NetSuite or QBO environment.
*   **Criticality:** Blocker for individual client activation.
*   **Owner:** Customer Success / Onboarding Team.
*   **Mitigation:** Design a frictionless, 2-click onboarding UI. Create clear, plain-English documentation explaining *why* read/write AP access is required to alleviate security concerns from client IT departments.

**DEP-3.03: Ongoing Jurisdictional Rule & Content Curation**
*   **Description:** Maintaining the accuracy and completeness of the "proprietary jurisdictional database" (FR-2.00) in the face of evolving local tax laws, newly incorporated municipalities, or ambiguous rule interpretations requires continuous human oversight.
*   **Criticality:** High. Stale or incorrectly interpreted baseline data leads directly to compliance failures and breaches the 0% penalty metric (SM-1.01).
*   **Owner:** Tax Subject Matter Experts (SMEs) / Data Operations Team.
*   **Mitigation:** Establish a dedicated "Tax Content Team" and a formalized, weekly process for researching, updating, and validating jurisdictional rules, supported by internal admin tooling to adjust schemas when automated agents encounter un-parsable data (EC-2.01).

## Assumptions

### 1. Technical & Architecture Assumptions

**ASM-1.01: ERP API Capability**
*   **Assumption:** We assume that target ERP systems (specifically NetSuite and QuickBooks Online) support sub-minute latency webhooks for critical entity updates (e.g., payroll ZIP code additions, fixed asset ledger updates) and expose REST API endpoints capable of receiving base64 encoded PDF attachments alongside AP Bill creations.
*   **Risk Impact:** If ERP webhooks are batched daily rather than fired near-real-time, our "Time-to-Value" SLA (NFR-1.03) will fail. If PDF attachments cannot be synced programmatically, the "Clean Bill of Health" audit functionality breaks.

**ASM-1.02: AI Model Efficacy on Archaic Data**
*   **Assumption:** We assume that Google Vertex AI's multimodal capabilities (Vision + LLM) are advanced enough to parse unstructured, highly variable, and often low-resolution scanned PDFs generated by local municipalities with a confidence score `> 0.80` in at least 85% of cases (SM-2.01).
*   **Risk Impact:** If Vertex AI consistently fails to parse local forms (e.g., handwritten overlays, poor scan quality), the system degrades from an "Autonomous Engine" to an expensive manual data entry queue, destroying the product's core value proposition and margins.

**ASM-1.03: crewAI Proxy Evasion**
*   **Assumption:** We assume that utilizing residential proxy rotation within the `crewAI` scraping framework will be sufficient to bypass basic bot-protection mechanisms (like standard Cloudflare challenges) on municipal web portals for the majority of the 10,000+ target jurisdictions.
*   **Risk Impact:** If municipalities deploy highly aggressive anti-bot measures that defeat our proxy rotation, the core tax database will become rapidly outdated, leading to inaccurate AI calculations and compliance penalties.

**ASM-1.04: Sustainable Proxy Infrastructure**
*   **Assumption:** We assume a continuous, scalable, and cost-effective supply of residential proxy IP addresses will be available to support the `crewAI` scraping across thousands of municipal domains without incurring prohibitive operational costs or encountering widespread, unresolvable IP blocks.
*   **Risk Impact:** If proxy costs spike or availability drops significantly, `ScrapeJob` success rates (SM-2.02) will fall, directly impacting data freshness and compliance accuracy while crushing operational margins.

**ASM-1.05: Long-Term AI Model Stability & Retrainability**
*   **Assumption:** We assume that the underlying Vertex AI models will maintain their efficacy over time, and that a reliable, cost-effective MLOps process for continuous monitoring, retraining, and fine-tuning (leveraging logged user interactions from the MongoDB `ComplianceLedger`) can be established to prevent model drift.
*   **Risk Impact:** Failure of this assumption could lead to a slow, silent degradation of Straight-Through Processing (STP) rates (SM-2.01) and an unmanageable increase in `REVIEW_REQUIRED` tasks, eroding user trust and breaking the "invisible shield" promise.

### 2. Legal & Regulatory Assumptions

**ASM-2.01: "Processor" Legal Exemption**
*   **Assumption:** We assume that by exclusively drafting AP Bills in the client's native ERP—and explicitly never taking custody of client funds or bank routing data—the platform definitively bypasses classification as a Money Services Business (MSB) or Money Transmitter under federal and state laws.
*   **Risk Impact:** If regulatory bodies interpret the "facilitation" of compliance payments (even via AP sync) as requiring MSB licensure, the project will require millions in unanticipated legal setup costs and months of delay.

**ASM-2.02: Electronic Signature Acceptance**
*   **Assumption:** We assume that a functionally viable majority (>80%) of the target 2,500 priority municipal jurisdictions accept electronically generated, typed, or digitally stamped signatures on their compliance forms, as opposed to requiring physically mailed "wet" signatures.
*   **Risk Impact:** If a high volume of jurisdictions demand physical mail, the platform's automation value drops significantly, forcing the `Compliance Specialist` persona (Marcus) to perform manual printing and mailing operations (EC-2.02).

### 3. User Behavior & Market Assumptions

**ASM-3.01: Willingness to Grant ERP Write Access**
*   **Assumption:** We assume that mid-market VPs of Tax and external CAS Partners are willing and able to grant our application OAuth 2.0 "Write" permissions to their highly sensitive ERP AP ledgers.
*   **Risk Impact:** If enterprise IT/SecOps teams block AP Write access due to security paranoia, the "invisible shield" workflow breaks, and the product becomes a mere "read-only" alerting dashboard, failing to differentiate from legacy competitors.

**ASM-3.02: Value Over Control**
*   **Assumption:** We assume that target users value "peace of mind" and time-saving automation more than granular control over every minor $50 local fee calculation, meaning they will confidently use the "Approve" workflow without feeling the need to double-check Vertex AI's math manually against the municipality's website.
*   **Risk Impact:** If users distrust the AI and manually recalculate every fee out of fear (the "Black Box" pain point), the "Time-in-App" anti-metric (SM-3.02) will spike, indicating the product has failed to eliminate user anxiety.

**ASM-3.03: ERP Data Quality & Consistency**
*   **Assumption:** We assume that, for fully integrated clients, the source data flowing from their ERP (e.g., payroll ZIP code entries, active asset ledgers) is generally accurate, complete, and consistently structured enough to reliably inform the `NexusTriggerEvent` evaluations.
*   **Risk Impact:** Chronic poor data quality from the client's ERP will lead to frequent false positives, unnecessary `INFO_NEEDED` tasks, or `AI_ERROR` states, forcing the platform to pause the integration (EC-1.04) and drastically reducing automation velocity.
