---
run_id: 89c8c39dd360
status: completed
created: 2026-03-23T13:45:52.357018+00:00
completed: 2026-03-23T16:36:55.356303+00:00
project: "[[business-compliance-tool]]"
tags: [idea, prd, completed]
---

# an invoicing and payments product that allows a company to collect via a mult...

> Part of [[business-compliance-tool/business-compliance-tool|Business compliance tool]] project

## Original Idea

an invoicing and payments product that allows a company to collect via a multitude of payment methods including stripe, PayPal, Amazon pay, Apple Pay, eBay, ACH via bank (customer initiated), credit card, ACH pull (take from customer account directly), bitcoin, ethereum, and other popular payment cryptocurrencies (limit to top 25 at most), etc. And allow the company to do business in various business models including subscription billing, one time payments, metered payments, tiered usage payments, buy now pay later, etc. This can be both with or without potential escrow options. There should be sophistication in various models of what exists currently and allow greater sophistication that doesn't current exist allowing for a range of business models sometimes not supported by other systems. Invoices should be able to interpret a contract and invoice accordingly via a proper invoicing schedule per the contract / order and collect necessary info that may be missing in doing so. This tool should facilitate the collects and payment of the products purchased. The tool should provision or deprovision as needed to gate keep functions not purchased etc. This should be more capable and user friendly than the guideline examples of zuora, ordway, Recurly, chargebee, etc. There should be a capability to read contracts to support and then have the ability to read/write into accounting systems (Netsuite, Quickbooks, xero, Intacct, etc.) and crm’s (Salesforce, hubspot, Zoho crm, odoo, etc.) as needed to facilitate record keeping, auditable records, and knowledge sharing throughout and organization.

## Refined Idea

# Refined Product Idea: AI-Native Quote-to-Cash Orchestration & Billing Sub-Ledger

## Executive Summary
The proposed product is an **AI-Native Quote-to-Cash Orchestration Engine** designed to sit between an organization’s CRM (Salesforce, HubSpot) and their core ERP/accounting system (NetSuite, QuickBooks Online). Rather than attempting to replace primary payment processors like Stripe, this platform acts as an agnostic, highly sophisticated billing sub-ledger and orchestration layer. It utilizes AI to translate complex, unstructured enterprise contracts into structured billing schedules, orchestrates multi-modal payments (including fiat, instant-settlement crypto, and milestone-based escrow), and provides a unified Entitlement API to manage product provisioning. 

## Target Market & Ideal Customer Profile (ICP)
**Industry Domain:** B2B FinTech / Revenue Operations (RevOps)
**ICP:** Mid-market to Enterprise B2B SaaS, Hardware-as-a-Service (HaaS), and Managed Service Providers ($20M–$200M+ ARR). 
These companies typically have sales-led motions with highly negotiated, non-standard contracts that mix one-time fees, recurring subscriptions, and tiered/metered usage. They are outgrowing basic Stripe Billing or QBO invoices, but find legacy enterprise systems like Zuora or Recurly too rigid, developer-heavy, and unforgiving to implement.

## The Problem Space (User Pain-Points)
As a seasoned RevOps Systems Architect, I constantly see mid-market companies bleed revenue and operational efficiency due to a disconnected Quote-to-Cash process. The specific pain points this product solves include:
1.  **The "Contract-to-System" Gap:** Sales teams close complex deals with custom terms (e.g., "Net 60, 3 months free, 10% step-down discount in Year 2, metered overages"). Today, high-paid finance operators manually read these PDFs and key them into billing systems, leading to human error and revenue leakage.
2.  **Rigid Billing Engines:** Incumbent systems struggle with "hybrid" business models. If a customer buys a software subscription, physical hardware, and hourly consulting in one contract, systems like Chargebee or Ordway often require massive workarounds.
3.  **Accounting Nightmares:** Accepting alternative payments (like Crypto) introduces massive ASC 606 revenue recognition and tax liability risks. Furthermore, dumping thousands of micro-transactional usage events directly into QuickBooks Online or NetSuite breaks their General Ledgers (as noted in prior project memory regarding QBO/NetSuite constraints).
4.  **Decoupled Provisioning:** When an invoice goes unpaid, the process of restricting user access (deprovisioning) is rarely automated, resulting in companies providing free services to delinquent accounts.

## Core Capabilities & Feature Strategy

### 1. AI-Assisted Contract Parsing & Billing Orchestration (Powered by Vertex AI)
Instead of fully autonomous (and risky) AI billing, the system acts as a "Human-in-the-Loop" copilot. 
*   **Intelligent Extraction:** The system ingests closed-won contracts from CRMs (Salesforce, HubSpot, Zoho). Vertex AI parses the unstructured text to identify billing entities, payment terms, discounts, and schedules.
*   **Drafting & Validation:** It generates a proposed "Billing Schedule Draft." If the AI detects missing information (e.g., a missing PO number or an ambiguous SLA penalty), it flags the RevOps user to provide the missing data before activation. 

### 2. Universal Hybrid Billing Engine
The platform supports a superset of modern pricing models out-of-the-box, allowing them to be combined on a single invoice:
*   Standard recurring (monthly/annual).
*   High-volume metered and tiered usage.
*   Milestone-based billing (tied to project delivery, supporting Escrow integrations for large service contracts).
*   Buy-Now-Pay-Later (B2B financing integrations).

### 3. Omni-Channel Payment Gateway Router
The system does not process payments itself; it provides a unified checkout and collections interface that routes to specialized gateways:
*   **Traditional:** Stripe, PayPal, Braintree, and direct ACH (push/pull).
*   **Alternative/Crypto:** To mitigate the massive accounting risks of holding volatile assets, the system integrates with processors (like BitPay or Coinbase Commerce) that accept the top 25 cryptocurrencies but **instantly settle in Fiat (USD) to the merchant**. This satisfies buyer demand for crypto payments while protecting the merchant's balance sheet and NetSuite integration.

### 4. Event-Driven Entitlement API (Provisioning)
To gatekeep functions, the system exposes a robust webhook and REST API (FastAPI) for entitlements. When a contract is signed, the system emits a `provision.granted` event. If an invoice enters a >60-day past-due state, it emits a `provision.suspended` event. The client's core application listens to these webhooks to automatically adjust user access, entirely removing Finance/Engineering bottleneck.

### 5. Smart Sub-Ledger ERP Sync
Addressing the known complexities of ERP integration (NetSuite's strict object relational models and QBO's flat Chart of Accounts):
*   The system acts as the source of truth for *billing state*. 
*   It aggregates complex, high-frequency usage data and pushes clean, summarized Invoices, Payments, and Journal Entries to NetSuite, Xero, or Intacct. 
*   It maintains bi-directional sync for auditable record-keeping, ensuring the CRM reflects real-time payment status without cluttering the ERP with raw metered events.

## Non-Obvious Risks & Mitigations
*   **Risk:** AI Hallucination resulting in under-billing a massive enterprise contract.
    *   **Mitigation:** The AI cannot activate a schedule autonomously. It creates "Pending Approvals" with confidence scores. High-value or low-confidence extractions require explicit RevOps sign-off.
*   **Risk:** Scope Creep ("Boiling the Ocean" by trying to integrate every gateway and CRM).
    *   **Mitigation:** Launch with a highly constrained integration matrix: Salesforce/HubSpot for CRM, Stripe/ACH for fiat payments, Coinbase Commerce for auto-fiat crypto, and NetSuite/QBO for accounting.
*   **Risk:** Regulatory constraints with Escrow and Crypto.
    *   **Mitigation:** Partner with licensed Escrow-as-a-Service API providers rather than holding funds directly, ensuring the platform remains a software provider, not a regulated financial institution.

## Executive Summary

### Problem Statement
Mid-market B2B enterprises consistently suffer from revenue leakage and operational bottlenecks due to a highly fragmented Quote-to-Cash (Q2C) lifecycle. High-value, custom-negotiated contracts are manually transcribed into rigid billing systems, causing costly human errors, delayed invoicing, and massive reconciliation nightmares when micro-transactional usage data or alternative payments pollute core ERP general ledgers.

### Target Audience & Stakeholders
*   **Ideal Customer Profile (ICP):** Mid-market to Enterprise B2B SaaS, Hardware-as-a-Service (HaaS), and Managed Service Providers with $20M–$200M+ ARR operating with sales-led motions.
*   **Key Stakeholders:** Revenue Operations (RevOps) leaders seeking automated contract-to-billing workflows; Finance/Controllers requiring strict ASC 606 compliance and clean ERP sub-ledgers; and Engineering/Product teams needing simplified, decoupled entitlement management.

### Proposed Solution & Key Differentiators
The **AI-Native Quote-to-Cash Orchestration Engine** acts as an intelligent, agnostic billing sub-ledger bridging front-office CRMs (Salesforce, HubSpot) and back-office ERPs (NetSuite, QuickBooks Online). 

**Key Differentiators include:**
*   **AI-Assisted Contract Parsing (Vertex AI):** Acts as a "Human-in-the-Loop" copilot to extract complex billing schedules, pricing tiers, and discounts from unstructured PDF contracts, eliminating manual data entry.
*   **RevOps Configuration Portal:** A dedicated React/TypeScript administrative UI where RevOps and Finance teams manage billing rules, review AI-generated schedule drafts, and explicitly approve configurations before activation.
*   **Universal Hybrid Billing:** Natively orchestrates recurring, high-volume metered, and milestone-based (escrow) billing models within a single, unified invoice.
*   **Smart Sub-Ledger ERP Sync:** Protects rigid ERP accounting architectures by acting as the ultimate system of record for billing state. It aggregates high-frequency usage data and pushes only clean, summarized journal entries to NetSuite and QBO. It employs robust, idempotent retry mechanisms and dead-letter queues to guarantee data integrity during network outages or API limits.
*   **Omni-Channel & Auto-Settling Crypto Routing:** Provides a unified checkout interface that handles traditional fiat (Stripe, ACH) and instantly settles top-25 cryptocurrencies into USD (via Coinbase Commerce), mitigating balance sheet exposure to crypto volatility.
*   **Event-Driven Entitlement API:** Exposes a robust FastAPI-driven webhook architecture (`provision.granted`, `provision.suspended`) to automate user access, programmatically halting service for delinquent accounts to prevent revenue leakage.

### Non-Functional Requirements
*   **Performance:** FastAPI REST endpoints and webhook emissions must maintain a p95 latency of <200ms. Usage data ingestion APIs must support a throughput of 5,000 RPS.
*   **Scalability:** The system must seamlessly handle 10,000+ concurrent active contracts and scale horizontally to accommodate end-of-month billing run spikes.
*   **Availability:** Target 99.99% uptime for core payment routing and entitlement APIs, with graceful degradation strategies for non-critical CRM syncing workflows.
*   **Security & Compliance:** Strict adherence to SOC 2 Type II and GDPR standards. All Personally Identifiable Information (PII) and contract data must be AES-256 encrypted at rest (MongoDB Atlas) and TLS 1.3 in transit.

### Expected Business Impact, Success Criteria & Analytics
**Business Outcomes:**
*   **Accelerated Cash Flow:** Reduce the time from a CRM "Closed-Won" event to initial invoice generation by 80%.
*   **Revenue Protection:** Achieve zero un-billed usage overages and eliminate "free service" for accounts >60 days past due within 6 months.
*   **Operational Efficiency:** Reduce manual contract reconciliation time by 60%, maintaining zero ASC 606 compliance violations.

**Metrics & Analytics Strategy:**
To track these outcomes and monitor system health, the platform will implement comprehensive instrumentation collecting:
*   **Operational Metrics:** API response times, webhook delivery success rates (target >99.9%), and external integration error rates.
*   **Product Usage Metrics:** Vertex AI extraction confidence scores vs. manual RevOps override rates (to continuously fine-tune the model), feature adoption by billing model type, and portal engagement metrics.

### Key Dependencies & Risks
*   **Dependency:** Reliability of third-party APIs (Salesforce, HubSpot, NetSuite, Stripe, Coinbase Commerce) and Google Vertex AI.
    *   *Mitigation:* Implement circuit breakers, exponential backoff, and extensive logging. Maintain offline capabilities for webhook queuing.
*   **Risk:** AI Hallucination/Drift resulting in incorrect enterprise billing.
    *   *Mitigation:* Mandatory "Human-in-the-Loop" approval via the RevOps portal for any contract lacking a 95%+ confidence score; ongoing LLM fine-tuning using collected manual override data.
*   **Risk:** Shifting regulatory constraints regarding B2B Crypto payments.
    *   *Mitigation:* Strictly enforce an auto-fiat settlement architecture via licensed partners (e.g., Coinbase Commerce), ensuring the application never takes custody of digital assets.

### High-Level Phasing
*   **Phase 1: Core Sub-Ledger & AI Copilot:** Implementation of Vertex AI contract extraction, RevOps UI, core CRM integrations, and foundational summarized ERP sync.
*   **Phase 2: Hybrid Billing & Provisioning:** Delivery of the universal billing engine and the FastAPI event-driven Entitlement webhooks.
*   **Phase 3: Omni-Channel Payments:** Integration of traditional gateways and auto-fiat settling alternative/crypto processors.

## Executive Product Summary

# Executive Product Summary: The Contract Compiler

## The Real Problem: English is a Terrible Programming Language
When someone says they need a "better billing system," they are misdiagnosing the disease. The root problem isn't Quote-to-Cash fragmentation. The actual problem is a fundamental impedance mismatch between how Sales sells and how businesses operate.

Sales teams close complex, high-value B2B deals using bespoke terms, staggered discounts, clawbacks, and metered overages written in unstructured legal prose (English). But businesses run on Code and Math (billing schedules, ASC 606 revenue recognition, and binary software entitlements). 

Right now, highly paid Finance and RevOps professionals are forced to act as human compilers—reading 40-page PDFs and manually translating legal clauses into rigid ERP architectures. This results in silent failures: millions in unbilled overages, delayed invoices, broken NetSuite sub-ledgers, and delinquent accounts getting free software because Finance forgot to tell Engineering to turn them off. 

We don't just need a billing sub-ledger. We need a universal translator. 

## The 10-Star Vision: The Revenue Physics Engine
We are building a **Contract Compiler**. You drop a signed PDF into the system, and it compiles unstructured legal agreements into operational physics: deterministic billing schedules, clean ERP journal entries, and automated software provisioning. 

Instead of replacing Stripe or rewriting NetSuite, this system sits precisely in the middle as the intelligent, AI-native nervous system for revenue. 

**The 10x Leap:**
*   **From Data Entry to Orchestration:** Vertex AI reads the contract and instantly proposes the operational reality. Humans don't enter data; they simply review and approve the AI's translation.
*   **Decoupling the Complexity:** We protect the fragile architectures of NetSuite and QuickBooks Online. Instead of polluting flat charts of accounts with millions of micro-transactions, we act as the ultimate billing state machine, pushing only perfectly summarized, auditor-ready journal entries.
*   **Zero Silent Failures:** Every invoice status is mapped directly to a FastAPI webhook (`provision.granted`, `provision.warning`, `provision.suspended`). If a customer doesn't pay, the software automatically downgrades. The gap between Finance and Engineering is eliminated.

## The Ideal User Experience: "This is Exactly What I Needed"
Imagine a RevOps leader, Sarah, on the last day of the quarter. Sales just closed a massive, non-standard enterprise deal: hardware, a SaaS subscription, 3 months of escrow-based consulting, and a weird 12% step-down discount in Year 2. The client wants to pay in USDC crypto. 

In the old world, Sarah would spend three days hacking this into five different systems. 

In our world, Sarah drags the signed Salesforce PDF into our React/TypeScript portal. A loading skeleton shimmers for 4 seconds. The screen splits. On the left is the original PDF. On the right is the fully generated billing schedule. 
The magic moment? She hovers her mouse over the "12% Year 2 Discount" line item on the right, and the system automatically scrolls the PDF on the left, highlighting the exact legal sentence that generated it in bright yellow. 

The system confirms the fiat-settling Coinbase Commerce route is active to eliminate balance sheet risk, previews the clean, summarized journal entries it will send to NetSuite, and shows the exact JSON payload it will fire to Engineering to unlock the user's account. Sarah clicks "Approve & Activate." A three-day nightmare becomes a three-minute delight. 

## Delight Opportunities (The "Oh Nice" Moments)
These are high-impact, low-effort features (<30 mins to build) that create outsized emotional resonance for the user:

1.  **Contract-to-Code Deep Linking:** As described above, pass the bounding box coordinates from Vertex AI's extraction to the frontend. Clicking any generated billing rule visually highlights the source text in the embedded PDF viewer. *Impact: Massive trust in the AI's output.*
2.  **The "Explain to Auditor" Button:** Add a one-click export on any invoice or journal entry that generates a plain-English text file: *"This $4,200 charge was generated based on Section 4.1 of the MSA signed on Oct 12, applying a 10% volume discount."* *Impact: Turns a grueling audit into a 5-second task.*
3.  **The "Gentle Nudge" Webhook (`provision.warning`):** Instead of just firing a kill-switch when an invoice is 60 days late, fire a webhook at day 45. This allows the client's product team to show an elegant in-app banner ("Update payment to avoid interruption") without hard-locking the user. *Impact: Enhances the end-user experience and accelerates collections.*
4.  **Dead-Letter Queue Visibility:** Expose a simple "Sync Health" dashboard. If the NetSuite API is down, don't just fail silently. Show a badge: "42 Invoices safely queued. Will retry in 15 minutes." *Impact: Eliminates Finance anxiety during end-of-month close.*

## Scope Mapping: The 12-Month Trajectory

*   **Current State (The Baseline):** High-volume, unstructured contracts are manually translated into rigid systems. QBO/NetSuite integrations are breaking due to API limits and dirty historical ledgers. Provisioning is a manual Slack message to Engineering.
*   **This Plan (Months 0-6) — The Foundation:** 
    *   Deploy Vertex AI "Human-in-the-loop" contract parsing.
    *   Launch the Hybrid Billing Engine (recurring, metered, milestone).
    *   Implement the summarized, idempotent NetSuite/QBO sync.
    *   Launch FastAPI webhooks for basic entitlement gating and traditional/crypto auto-fiat payment routing.
*   **12-Month Ideal (Months 6-12) — The Autonomous Revenue Engine:**
    *   **Self-Healing AI:** crewAI agents proactively monitor CRM for contract amendments and suggest billing schedule updates automatically.
    *   **Predictive Cash Flow:** Machine learning models analyze payment latency across thousands of invoices to predict exact cash-in dates and highlight churn-risk accounts before they default.
    *   **Automated Dunning & Collections Workflows:** Fully autonomous, multi-channel payment recovery.

## Business Impact & Competitive Positioning
This isn't just a workflow tool; it is a strategic cash flow accelerator. 

*   **The Market Opportunity:** Mid-market B2B ($20M-$200M ARR) is a wasteland for billing. Stripe is too simple; Zuora is too heavy and requires a massive engineering implementation. By acting as an agnostic orchestration layer, we don't have to rip-and-replace their current stack—we just make it actually work.
*   **Accelerated Cash Velocity:** We reduce the time from a CRM "Closed-Won" status to the first invoice from days to minutes. 
*   **Zero Revenue Leakage:** By binding the literal contract to the actual software entitlement via webhooks, we guarantee that no customer receives software they haven't paid for, and no metered overage goes unbilled.
*   **Risk Mitigation:** We ensure pristine ASC 606 compliance and completely isolate the core ERP from crypto volatility and micro-transaction pollution.

**Success Criteria:**
1. **Time-to-Invoice:** >80% reduction in time between contract signature and invoice generation.
2. **AI Confidence:** Vertex AI achieves a >95% confidence score (requiring zero human edits) on standard contract templates within 90 days of deployment.
3. **ERP Integrity:** 100% of journal entries synced to NetSuite/QBO without silent API failures, validated by the dead-letter queue recovery rates.

## Engineering Plan

# Engineering Plan: The Contract Compiler (AI-Native Quote-to-Cash)

## 1. Architecture Overview

The Contract Compiler is a distributed, event-driven system operating as a universal translation and orchestration layer between external CRMs, Payment Gateways, and ERPs. It isolates strict financial architectures (ERPs) from unstructured upstream inputs (Contracts) and high-frequency downstream events (Usage/Provisioning).

### 1.1 System Components and Boundaries

```ascii
                                +-------------------+
                                |   External CRMs   | (Salesforce, HubSpot)
                                +---------+---------+
                                          | Webhook (Contract Won)
                                          v
+-----------------------------------------+-----------------------------------------+
| TRUST BOUNDARY: INTERNAL VPC            |                                         |
|                                         |                                         |
|  +--------------------+      +----------+-----------+      +-------------------+  |
|  | Frontend SPA       |      | API Gateway / Core   |      | Async Worker Pool |  |
|  | (React + TS)       |<---->| (FastAPI + Py 3.11)  |----->| (crewAI Tasks,    |  |
|  | - PDF Viewer       |      | - Auth & Rate Limits |<-----|  Cron Jobs)       |  |
|  | - AI Copilot UI    |      | - Idempotency Layer  |      +---------+---------+  |
|  +--------------------+      +----------+-----------+                |            |
|                                         |                            |            |
|                                         v                            v            |
|                              +----------+-----------+      +-------------------+  |
|                              | Persistence Layer    |      | External AI Model |  |
|                              | (MongoDB Atlas)      |      | (Google Vertex AI)|  |
|                              +----------------------+      +-------------------+  |
+-----------------------------------------+-----------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
        v                                 v                                 v
+-------------------+             +-------------------+             +-------------------+
| Payment Gateways  |             | Entitlement API   |             | Core ERPs         |
| (Stripe, Coinbase)|             | (Webhooks to App) |             | (NetSuite, QBO)   |
+-------------------+             +-------------------+             +-------------------+
```

### 1.2 Technology Stack Decisions & Rationale

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend API** | Python 3.11 + FastAPI | High-performance async support natively handles I/O-bound webhook traffic. Pydantic ensures strict runtime validation of AI outputs. |
| **Frontend** | React + TypeScript | Strict typing prevents state mismatches when handling complex billing nested arrays. Enables highly interactive PDF-to-Code mapping UI. |
| **Database** | MongoDB Atlas | Document model naturally fits hierarchical billing schedules and dynamic product catalogs. TTL indexes manage webhook dead-letter queues. |
| **AI Orchestration**| crewAI + Vertex AI | crewAI natively manages multi-agent workflows (Extraction Agent vs. Dunning Agent). Vertex AI provides enterprise-grade data privacy (no training on user data) and superior document reasoning. |

### 1.3 Data Flow Architecture

**Happy Path (Contract to Provisioning):**
```ascii
[CRM] -> (1) POST /contracts/parse -> [FastAPI] -> (2) Save `Uploaded` -> [MongoDB]
[FastAPI] -> (3) Queue AI Task -> [crewAI Worker]
[crewAI] -> (4) Read PDF & Prompt -> [Vertex AI] -> (5) Return JSON Draft
[crewAI Worker] -> (6) Update DB `PendingReview` -> [MongoDB]
[Frontend] -> (7) User calls PATCH /approve -> [FastAPI] -> (8) Update DB `Active`
[Cron] -> (9) Generate Invoice -> [FastAPI] -> (10) State: `Issued`
[Gateway] -> (11) POST /invoices/pay -> [FastAPI] -> (12) State: `Paid` -> (13) Emit `provision.granted`
[Worker] -> (14) POST Signed Webhook -> [Customer App]
```

**Failure/Error Paths:**
*   *Nil/Empty Path*: PDF contains no recognizable financial terms. AI confidence `0.0`, Schedule empty. Skips to `PendingReview`, hard-blocks until manual entry.
*   *Error Path (Webhook Delivery)*: Customer App returns `503`. System catches, sets `WebhookDelivery` status to `Pending`, increments `retry_count`, and schedules exponential backoff.

---

## 2. Component Breakdown & State Machines

### 2.1 AI Contract Copilot (Extraction Engine)
*   **Purpose**: Translate unstructured PDFs into deterministic `BillingSchedule` objects.
*   **Dependencies**: Vertex AI via crewAI, MongoDB (`ContractDocument`, `BillingSchedule`).
*   **Interfaces**: `POST /api/v1/contracts/parse`, `PATCH /api/v1/contracts/{id}/approve`.

**State Machine: `ContractDocument`**
```ascii
  [Upload Event]
        |
        v
  +------------+   Agent Start    +-------------+
  |  Uploaded  | ---------------> |   Parsing   |
  +------------+                  +-------------+
                                     |       |
                 Agent Success (JSON)|       | Agent Fail / Unreadable
                                     v       v
      +------------+  User Rejects +---------------+
      |   Active   | <------------ | PendingReview |
      +------------+               +---------------+
         ^                               |
         | User Approves / AI Auto       | User Rejects
         +-------------------------------+
```

### 2.2 Universal Hybrid Billing Engine
*   **Purpose**: Cron-driven mathematical engine that evaluates active schedules and generates point-in-time invoices.
*   **Dependencies**: MongoDB (`BillingSchedule`, `Invoice`), Omni-Channel Payment Router.
*   **Interfaces**: Internal Cron, `POST /api/v1/invoices/generate`, `POST /api/v1/invoices/{id}/pay`.

**State Machine: `Invoice`**
```ascii
                     +---------+   Anomaly Detected
                     |  Draft  | -------------------> [PendingApproval]
                     +---------+                              |
                          |                                   | Human Override
                          | Cron Auto-Issue                   |
                          v                                   v
+--------+           +----------+                        +----------+
| Voided | <-------- |  Issued  | ---------------------> | Overdue  | (Date > Due)
+--------+           +----------+                        +----------+
                          |                                   |
                          | Partial Payment                   | Full Payment
                          v                                   |
                   [PartiallyPaid]                            |
                          |                                   v
                          +----- (Amount Due == 0) ----> +----------+
                                                         |   Paid   |
                                                         +----------+
```

### 2.3 Event-Driven Entitlement Gateway
*   **Purpose**: Isolate application logic from financial state via cryptographic webhooks.
*   **Dependencies**: Invoice state changes, `WebhookDelivery` worker.
*   **Interfaces**: `POST /api/v1/webhooks/endpoints`, `GET /api/v1/entitlements/{id}`.

**State Machine: `Entitlement`**
```ascii
  [Contract Start Date]
          |
          v
    +----------+                   +-------------+
    | Inactive |                   | Terminated  |
    +----------+                   +-------------+
          |                              ^
          | Invoice Paid                 | Contract Ends
          v                              |
  +--------------+  Invoice > 60d late   |
  | Provisioned  | ----------------------+
  +--------------+                       |
          ^                              v
          |                        +-----------+
          +----------------------- | Suspended |
              Invoice Paid         +-----------+
```

### 2.4 Smart Sub-Ledger ERP Sync
*   **Purpose**: Aggregate high-volume transactions into summarized double-entry journal logs to protect ERP rate limits.
*   **Dependencies**: NetSuite/QBO APIs, AI Account Mapping Agent.
*   **Interfaces**: `POST /api/v1/ledger/sync`.

**State Machine: `LedgerSyncBatch`**
```ascii
 [Cron Job Rollup]
        |
        v
   +---------+  Sync Trigger   +------------+
   | Queued  | --------------> | Processing | <---------+
   +---------+                 +------------+           |
        ^                         |  |  |               | (Retry After)
        |          +--------------+  |  +------------+  |
        |          | 429 Error       | 200 OK        |  |
        |          v                 v               v  |
        |  +-------------+     +----------+    +--------------+
        +- | RateLimited |     |  Synced  |    | Failed /     |
   (Retry) +-------------+     +----------+    | Part. Failed |
                                               +--------------+
```

---

## 3. Implementation Phases (Jira Mapping)

### Phase 1: Foundation & Data Layer (Epic 1)
*Goal: Base infrastructure, Auth, DB schemas, and standard CRUD APIs.*
*   **[Story 1.1]** Configure FastAPI project structure, global exception handlers, and JSON logging. (Complexity: S)
*   **[Story 1.2]** Implement MongoDB Atlas connection pooling and base Pydantic models for Customer and Product catalogs. (Complexity: M)
*   **[Story 1.3]** Implement multi-tenant JWT middleware and role-based access control (Admin, RevOps, Finance). (Complexity: M)
*   **[Story 1.4]** Scaffold React/Vite/TS frontend with basic routing and API client. (Complexity: S)

### Phase 2: AI Contract Parsing & UI (Epic 2)
*Goal: Ingest PDFs, extract data via Vertex AI, and render the side-by-side UI.*
*   **[Story 2.1]** Create `POST /contracts/parse` and AWS S3/GCS file upload handling. (Complexity: M)
*   **[Story 2.2]** Build crewAI async worker architecture (Celery/RQ) to orchestrate Vertex AI prompts. (Complexity: L)
*   **[Story 2.3]** Engineer Vertex AI prompt and JSON schema enforcement for `BillingSchedule` generation. (Complexity: L)
*   **[Story 2.4]** Build React side-by-side UI: PDF viewer on left, generated Schedule UI on right. (Complexity: XL)
*   **[Story 2.5]** Implement `PATCH /contracts/{id}/approve` with strict state machine validation. (Complexity: S)

### Phase 3: Hybrid Billing Engine & Payments (Epic 3)
*Goal: Daily cron generation of invoices and payment webhook ingestion.*
*   **[Story 3.1]** Build Invoice Generation Cron (evaluates recurring, metered, milestone schedules). (Complexity: XL)
*   **[Story 3.2]** Implement AI Anomaly Detection agent to flag usage spikes (`PendingApproval`). (Complexity: M)
*   **[Story 3.3]** Build `POST /invoices/{id}/pay` webhook receiver with strict idempotency keys. (Complexity: L)
*   **[Story 3.4]** Integrate Stripe & Coinbase Commerce SDKs for checkout link generation. (Complexity: M)

### Phase 4: Entitlements & Webhooks (Epic 4)
*Goal: Zero-touch provisioning via cryptographic webhooks.*
*   **[Story 4.1]** Create `WebhookEndpoint` CRUD APIs and HMAC-SHA256 secret generation. (Complexity: M)
*   **[Story 4.2]** Implement Entitlement State Machine engine (listening to Invoice state changes). (Complexity: L)
*   **[Story 4.3]** Build background webhook dispatcher with exponential backoff and `WebhookDelivery` logging. (Complexity: L)
*   **[Story 4.4]** Build Frontend "Sync Health" Dashboard for dead-letter queue visibility. (Complexity: S)

### Phase 5: Smart ERP Sync & Rollup (Epic 5)
*Goal: Summarize transactions and sync to NetSuite/QBO without rate-limiting.*
*   **[Story 5.1]** Implement `LedgerSyncBatch` aggregation logic (Credits = Debits validation). (Complexity: L)
*   **[Story 5.2]** Build NetSuite/QBO API adapter layer with 429 `retry_after` handling. (Complexity: M)
*   **[Story 5.3]** Implement AI Chart of Accounts Mapping Agent for unknown product SKUs. (Complexity: L)

---

## 4. Data Model (MongoDB)

*Note: All collections include implicitly `tenant_id` for B2B data isolation.*

### 4.1 Collections & Schema

1.  **`contracts`**
    *   `_id` (ObjectId)
    *   `crm_reference_id` (String, Unique Index)
    *   `file_url` (String)
    *   `status` (Enum: Uploaded, Parsing, PendingReview, Active, Rejected)
    *   `created_at` (Datetime)

2.  **`billing_schedules`**
    *   `_id` (ObjectId)
    *   `contract_id` (ObjectId, Ref: contracts)
    *   `customer_id` (ObjectId)
    *   `payment_terms` (Enum)
    *   `ai_confidence_score` (Float)
    *   `line_items` (Array of nested objects: `item_id`, `billing_model`, `amount`, `quantity`, `start_date`, `end_date`)
    *   *Indexes*: `{contract_id: 1}`, `{customer_id: 1, status: 1}`

3.  **`invoices`**
    *   `_id` (ObjectId)
    *   `invoice_number` (String, Unique Index)
    *   `billing_schedule_id` (ObjectId)
    *   `subtotal`, `tax_amount`, `total_amount`, `amount_due` (Float)
    *   `state` (Enum: Draft, Issued, PartiallyPaid, Paid, Overdue)
    *   `issue_date`, `due_date` (Datetime)

4.  **`webhook_deliveries`** (The Dead-Letter Queue)
    *   `_id` (ObjectId)
    *   `endpoint_id` (ObjectId)
    *   `status` (Enum: Pending, Delivered, Failed)
    *   `retry_count` (Int)
    *   `payload` (Dict)
    *   `created_at` (Datetime)
    *   *Indexes*: TTL Index on `created_at` (30 days), `{status: 1}` for worker queries.

### 4.2 Schema Decisions
*   **Float over Decimal**: While standard accounting mandates Decimal to prevent precision loss, MongoDB handles standard Floats efficiently. We will enforce `Decimal128` data types in MongoDB and cast to `Decimal` in Python Pydantic models to ensure mathematical precision for billing.
*   **NoSQL Referencing**: We avoid deeply nested documents for `Invoices` inside `BillingSchedules` to prevent mega-documents. References (`ObjectId`) are used.

---

## 5. Error Handling & Failure Modes

| Component / Failure Mode | Classification | Handling Strategy |
| :--- | :--- | :--- |
| **AI Hallucination** (Extracts wrong price) | Critical | Gatekept by `ai_confidence_score`. Any score < 0.95 forces `PendingReview` state. Humans must explicitly PATCH. |
| **Payment Webhook Dropped** (Network failure) | Critical | Gateway SDKs retry natively. API ensures *Idempotency* via `gateway_transaction_id`. Processing the same payment twice yields `200 OK` but mutates DB once. |
| **Customer App Webhook 5xx** | Major | System enters DLQ. Retries at [1m, 5m, 30m, 2h, 12h]. After 5 retries, alerts Finance via "Sync Health" dashboard. |
| **ERP API Rate Limit (429)** | Major | `LedgerSyncBatch` catches 429, extracts `Retry-After` header, updates state to `RateLimited`, and sleeps the task queue. |
| **Vertex API Timeout** | Minor | Worker catches timeout, updates Contract state to `PendingReview` with `0.0` score, forcing manual data entry without blocking system. |

---

## 6. Test Strategy

We adopt a rigid testing pyramid utilizing `pytest`, `pytest-asyncio`, and `mongomock`.

### 6.1 Critical Paths (100% Coverage Required)
1.  **Billing Math**: Subtotal, Tax, Discount, and `amount_due` calculations.
2.  **State Machine Guards**: Attempting to approve an already `Active` contract, or paying a `Voided` invoice MUST throw `409 Conflict`.
3.  **Webhook Cryptography**: HMAC generation and payload verification.

### 6.2 Test Matrix Edge Cases
*   **Timezones**: Invoice generation cron running at 23:59 UTC vs 00:01 UTC.
*   **Floating Point Math**: Ensuring `Decimal` types handle `0.1 + 0.2 = 0.3` without `0.30000000000000004` rounding errors.
*   **Double Payments**: Firing two concurrent POST requests to `/invoices/{id}/pay` for the exact remaining balance. Ensure DB transaction locks prevent negative `amount_due`.

### 6.3 Performance / Load
*   Target: `POST /invoices/pay` (webhook receiver) must respond in < 200ms at 500 RPS to satisfy Stripe/Coinbase timeout windows. Async workers handle the DB mutation off the main thread if under extreme load.

---

## 7. Security & Trust Boundaries

### 7.1 Attack Surface Mitigation
*   **SSRF Protection**: `POST /webhooks/endpoints` validates user-supplied URLs against an internal blocklist (rejects `localhost`, `127.0.0.1`, `169.254.169.254`) to prevent internal network scanning.
*   **Replay Attacks**: All outgoing webhooks include a timestamp in the header (`X-Timestamp`). The HMAC signature includes the timestamp. Downstream clients should reject payloads older than 5 minutes.
*   **Tenant Data Isolation**: Every FastAPI dependency injects the `tenant_id` from the decoded JWT. All MongoDB queries implicitly append `{ "tenant_id": current_tenant }`.

### 7.2 Data Classification
*   **Financial / PII**: Customer names, addresses, and transaction amounts. Stored at rest using MongoDB's default WiredTiger encryption.
*   **Secrets**: API Keys (Stripe, NetSuite, Webhook Secrets). Stored in a dedicated Secret Manager (e.g., GCP Secret Manager/AWS Secrets Manager), NEVER in environment variables or plain text in DB.

---

## 8. Deployment & Rollout

### 8.1 Deployment Sequence
1.  **Database Migrations**: Add new indexes via motor/pymongo script. (Backward compatible).
2.  **Background Workers**: Deploy new crewAI / Celery worker images.
3.  **Backend API**: Rolling update of FastAPI pods (k8s/ECS).
4.  **Frontend**: Upload React build to CDN, update `index.html`.

### 8.2 Rollback Plan
1.  *Identify failure*: Alert fires for `HTTP 5xx > 1%` or `Webhook Latency > 2s`.
2.  *Halt traffic*: Traffic shifted to previous replica set.
3.  *Worker drain*: Stop background workers to prevent malformed data mutation.
4.  *Revert code*: CI/CD pipeline triggers deployment of `N-1` image.
5.  *Data reconciliation*: Execute runbook script to find and clean up any `Invoice` records stuck in transient states during the bad deployment window.

---

## 9. Observability

### 9.1 Logging
*   All logs output in JSON format.
*   Required Keys per request log: `tenant_id`, `trace_id`, `user_id`, `endpoint`, `latency_ms`, `status_code`.

### 9.2 Metrics & Alerting (Prometheus/Grafana)
*   **Business Metrics**:
    *   `time_to_invoice_hours`: Average delta between CRM `Closed-Won` and Invoice `Issued`.
    *   `ai_auto_approval_rate`: Percentage of contracts hitting >= 0.95 confidence.
*   **System Metrics**:
    *   `dlq_depth`: Number of webhooks in `Pending` state > 1 hour. **[ALERT: P2]**
    *   `erp_sync_failures`: Number of `LedgerSyncBatch` in `Failed` state. **[ALERT: P1]**
    *   `api_error_rate`: > 1% 5xx errors over 5 minutes. **[ALERT: P1]**

### 9.3 Debugging Guide (Common Scenarios)
*   *Scenario: Customer complains App feature didn't unlock after payment.*
    1.  Query `invoices` by `invoice_number`. Verify state is `Paid`.
    2.  Query `entitlements` by `customer_id`. Verify state is `Provisioned`.
    3.  Query `webhook_deliveries` for that `entitlement_id`. Look at `status` and `retry_count`.
    4.  If `Failed`, inspect the `error_payload` to see if the customer's endpoint returned 401 Unauthorized or 503, proving the fault lies on their side.

## Problem Statement

Mid-market B2B enterprises ($20M–$200M ARR) are experiencing critical revenue leakage, bloated operational costs, and severe data integrity issues due to a fundamental impedance mismatch in their Quote-to-Cash (Q2C) lifecycle. Specifically, there is a structural disconnect between how enterprise sales are won and how businesses actually operate. Sales teams close high-value, complex deals using unstructured legal prose that includes bespoke terms, staggered discounts, clawbacks, and metered overages. Conversely, downstream operations—revenue recognition, billing schedules, and software provisioning—require deterministic logic, math, and strict data architectures.

Currently, organizations bridge this gap by forcing highly paid Revenue Operations (RevOps) and Finance professionals to act as "human compilers." These teams must manually read extensive PDF contracts and transcribe highly customized terms into rigid billing engines. This inherently flawed, manual workflow creates four critical failure domains:

*   **Rampant Revenue Leakage and Invoicing Delays:** Manual data entry inevitably leads to silent financial failures. Complex contractual levers—such as step-down discounts in Year 2, pro-rated fees, or tiered metered overages—are frequently misconfigured or missed entirely. Furthermore, the bottleneck of manual translation delays the time-to-invoice from the moment a CRM deal is marked "Closed-Won," severely degrading cash velocity.
*   **Inflexible Billing Engines Unable to Support Hybrid Models:** Incumbent billing platforms natively struggle with non-standard, multi-modal contracts. When a single agreement mixes a recurring SaaS subscription, physical hardware delivery, and milestone-based consulting (e.g., escrow terms), existing systems require brittle workarounds across multiple fragmented platforms, destroying any single source of truth for revenue tracking.
*   **ERP General Ledger Degradation and Compliance Risks:** To manage billing complexity, companies often attempt to force thousands of micro-transactional usage events directly into their core accounting systems. This fundamentally breaks the architectural constraints of tools like NetSuite (which relies on strict relational models) and QuickBooks Online (which utilizes a flat Chart of Accounts), resulting in un-auditable data bloat and system timeouts. Additionally, accommodating modern buyer demands for alternative payments, such as cryptocurrency, without a proper settlement intermediary introduces massive ASC 606 revenue recognition violations and unacceptable balance sheet volatility.
*   **Decoupled Entitlement and Provisioning:** A company’s financial state is rarely bound to its application state. When a customer's invoice becomes 60 days past due, Finance must manually notify Engineering (often via ad-hoc Slack messages) to restrict or suspend the user's access. Because this deprovisioning process is asynchronous and human-dependent, organizations routinely provide thousands of dollars in free software and services to delinquent accounts.

Ultimately, mid-market companies are outgrowing simple invoicing tools but lack the engineering capital to implement heavy, legacy enterprise billing systems (like Zuora). The core disease is the manual translation layer between the signed contract and the operational reality—resulting in a fragmented ecosystem where revenue is lost, compliance is risked, and core accounting systems are pushed past their architectural limits.

## User Personas

The success of the Contract Compiler relies on solving the distinct, often conflicting needs of three critical stakeholders within the B2B enterprise ecosystem: Revenue Operations, Finance, and Engineering. 

### 1. Sarah — The Revenue Operations (RevOps) Director
* **Demographics:** 34 years old, highly analytical, sits at the intersection of Sales, Finance, and Systems. She is the operational glue holding the Quote-to-Cash process together.
* **Usage Frequency & Context:** **Daily Power User.** She lives in the frontend React/TypeScript administrative portal, primarily during the end-of-quarter or end-of-month crunch when Sales is closing complex, non-standard deals.
* **Specific Pain Points:**
  * Forced to act as a "human compiler," spending days manually reading 40-page PDF contracts and translating bespoke Sales terms (e.g., "12% step-down discount in Year 2", escrow milestones) into legacy billing software.
  * Constant anxiety about missing a custom billing term, leading to unbilled overages or delayed invoicing.
  * Hacking workarounds into systems like Chargebee to support hybrid deals (SaaS + Hardware + Services).
* **Goals & Desired Outcomes:**
  * Wants to drag-and-drop a signed Salesforce PDF and have the system instantly propose a highly accurate `BillingSchedule` draft.
  * Needs visual proof to trust the AI. Her "magic moment" is utilizing the **Contract-to-Code Deep Linking** feature—clicking a generated billing rule and seeing the exact source text highlighted in the embedded PDF viewer.
  * Wants to confidently hit "Approve & Activate," reducing a three-day reconciliation nightmare to a three-minute review task.

### 2. Marcus — The Corporate Controller (Finance)
* **Demographics:** 45 years old, CPA background, deeply methodical, and strictly focused on GAAP/ASC 606 compliance, revenue recognition, and audit readiness.
* **Usage Frequency & Context:** **Weekly/Monthly Power User.** He logs into the portal to monitor the "Sync Health" dashboard, verify end-of-month ledger roll-ups, and generate reports for external auditors.
* **Specific Pain Points:**
  * General Ledger (GL) pollution. He despises when thousands of micro-transactional usage events are dumped directly into NetSuite or QuickBooks Online, breaking the relational models and flat charts of accounts.
  * Silent API failures during end-of-month closes where ERP rate limits (429 errors) cause missing journal entries.
  * Sales pushing to accept cryptocurrency, which terrifies him due to balance sheet volatility, tax liability, and complex revenue recognition rules.
* **Goals & Desired Outcomes:**
  * Requires the system to act as a strict, summarized sub-ledger. He wants perfectly balanced, aggregated journal entries (`LedgerSyncBatch`) pushed to the ERP, not raw events.
  * Demands absolute data integrity and visibility. He needs to see a dead-letter queue dashboard that explicitly states "42 Invoices safely queued. Will retry in 15 minutes" rather than experiencing silent system failures.
  * Needs alternative payments (Crypto) to be instantly auto-settled into Fiat (USD) via the Omni-Channel router, entirely insulating his balance sheet from crypto volatility.
  * Wants the "Explain to Auditor" one-click export to instantly justify how a specific invoice amount was mathematically derived from a contract clause.

### 3. David — The Lead Software Engineer (Product/Platform)
* **Demographics:** 31 years old, favors modern, cloud-native architectures. Focuses on core product features, not back-office administrative tooling.
* **Usage Frequency & Context:** **Occasional / "Set-and-Forget" User.** He interacts primarily with the FastAPI REST endpoints and webhook payloads during initial setup, and only revisits the system to investigate delivery logs if a customer reports an access issue.
* **Specific Pain Points:**
  * Being a human bottleneck. He hates receiving ad-hoc Slack messages from Finance stating, "Customer X didn't pay, please disable their account."
  * Having to write and maintain complex, custom billing logic (like pro-rated downgrades) within the core application codebase.
  * Dealing with poorly documented APIs, missing idempotency keys, and webhooks that fail silently without retry mechanisms.
* **Goals & Desired Outcomes:**
  * Wants a completely decoupled entitlement architecture. He wants his application to simply listen for cryptographically signed (HMAC-SHA256) webhooks like `provision.granted`, `provision.warning`, and `provision.suspended`.
  * Values the "Gentle Nudge" webhook (`provision.warning`) at day 45 of delinquency, allowing his team to gracefully render an in-app payment warning banner rather than building hard-coded logic.
  * Requires robust, developer-friendly tooling: comprehensive OpenAPI documentation, predictable JSON payloads, strict state machine enforcement, and reliable exponential backoff for failed webhook deliveries.

## Functional Requirements

### 1. AI Contract Copilot (Extraction Engine)

**FR-001: Contract Ingestion and State Initialization**
* **Priority:** SHALL
* **Description:** The system ingests PDF documents via a REST endpoint. Upon successful upload, it saves the file to cloud storage (S3/GCS) and initializes a `ContractDocument` record in MongoDB with the status `Uploaded`.
* **Acceptance Criteria:**
  * **Given** an authenticated user or CRM webhook provides a valid PDF (Version 1.4+, maximum file size 50MB) and `crm_reference_id`,
  * **When** `POST /api/v1/contracts/parse` is called,
  * **Then** the system returns a `202 Accepted` with a new `contract_id` and updates the internal state to `Parsing`.
* **API Endpoint:** 
  * `POST /api/v1/contracts/parse`
  * Request schema: `multipart/form-data` (file), `crm_reference_id` (string)
  * Response schema: `{ "contract_id": "string", "status": "Parsing" }`

**FR-002: Vertex AI Orchestration**
* **Priority:** SHALL
* **Description:** A background crewAI worker securely passes the PDF text to Google Vertex AI. The AI model extracts the unstructured legal terms and returns a structured JSON payload mapping to the `BillingSchedule` Pydantic schema, accompanied by an `ai_confidence_score`.
* **Acceptance Criteria:**
  * **Given** a `ContractDocument` in `Parsing` state,
  * **When** the crewAI task completes successfully,
  * **Then** the system updates the status to `PendingReview` and saves the generated `BillingSchedule` draft to the database.

**FR-003: Contract-to-Code UI Deep Linking**
* **Priority:** SHALL
* **Description:** The React/TypeScript frontend renders a split-screen view. The left pane displays the original PDF; the right pane displays the generated `BillingSchedule`. Hovering over or clicking a generated line item on the right must trigger the left pane to auto-scroll and highlight the exact source text using bounding box coordinates returned by the AI.
* **Acceptance Criteria:**
  * **Given** a user is viewing a contract in `PendingReview`,
  * **When** the user clicks the "12% Discount" line item,
  * **Then** the PDF viewer scrolls to Section 4.1 and highlights the text "12% step-down discount in Year 2".

**FR-004: Manual Review and Activation**
* **Priority:** SHALL
* **Description:** RevOps users must explicitly approve or manually override the AI-generated schedule before activation. If the `ai_confidence_score` is >= 0.95, the UI displays a "Recommended for Auto-Approval" badge.
* **Acceptance Criteria:**
  * **Given** a contract in `PendingReview` state,
  * **When** a user submits `PATCH /api/v1/contracts/{id}/approve`,
  * **Then** the system transitions the contract to `Active`, locking the `BillingSchedule` from further structural edits.

**FR-005: Manual Contract Creation & Data Entry**
* **Priority:** SHOULD
* **Description:** The system allows RevOps users to manually create a `ContractDocument` record and its associated `BillingSchedule` directly within the UI, bypassing the AI parsing engine for simple or non-PDF agreements.
* **Acceptance Criteria:**
  * **Given** a user navigates to the "New Contract" UI,
  * **When** they manually enter the required billing parameters and click "Save & Activate",
  * **Then** the system creates an `Active` contract and skips the `Parsing` and `PendingReview` states entirely.

### 2. Universal Hybrid Billing Engine

**FR-006: Automated Invoice Generation**
* **Priority:** SHALL
* **Description:** A daily cron job evaluates all `Active` billing schedules. It calculates point-in-time totals (subtotal, tax, discounts) for standard recurring, tiered metered, and milestone-based line items, generating an `Invoice` record.
* **Acceptance Criteria:**
  * **Given** an active `BillingSchedule` with a line item scheduled for today,
  * **When** the internal cron job executes,
  * **Then** the system creates an `Invoice` with status `Issued` and calculates the `amount_due` using `Decimal` precision logic.

**FR-007: "Explain to Auditor" Export**
* **Priority:** SHOULD
* **Description:** The system provides a one-click export for any generated invoice that outputs a plain-text audit trail, mapping the exact mathematical calculation to the natural language contract clause that triggered it.
* **Acceptance Criteria:**
  * **Given** an `Issued` invoice,
  * **When** a user clicks "Export Audit Trail",
  * **Then** the system generates a text string that explicitly includes the original base amount, applied discounts, applied tax rates, the final calculated `amount_due`, and cites the specific bounding-box text clause from the PDF (e.g., *"Base: $5,000. Less 10% volume discount (Section 4.1). Plus 5% Tax. Total $4,725."*).

### 3. Omni-Channel Payment Router

**FR-008: Omni-Channel Checkout Generation**
* **Priority:** SHALL
* **Description:** The system generates a unified, hosted checkout link for an `Issued` invoice. The checkout UI dynamically displays payment options based on the active gateways configured for that specific tenant.
* **Acceptance Criteria:**
  * **Given** an invoice in `Issued` or `PartiallyPaid` state,
  * **When** a user accesses the checkout link,
  * **Then** they are presented only with the payment options explicitly enabled by their tenant administrator, preventing direct crypto custody on the merchant balance sheet.

**FR-009: Idempotent Payment Webhook Ingestion**
* **Priority:** SHALL
* **Description:** The system exposes a webhook receiver to ingest successful payment events from external gateways. It must strictly enforce idempotency to prevent double-crediting an invoice.
* **Acceptance Criteria:**
  * **Given** a valid webhook payload from a gateway (Stripe/Coinbase),
  * **When** `POST /api/v1/invoices/{id}/pay` is called with a specific `gateway_transaction_id`,
  * **Then** the system updates the invoice to `Paid` (if `amount_due` reaches 0). If the same transaction ID is received again, the system returns `200 OK` without mutating the database.

### 4. Event-Driven Entitlement API

**FR-010: Webhook Delivery and Cryptographic Signatures**
* **Priority:** SHALL
* **Description:** When an `Invoice` or `ContractDocument` changes state, the system fires webhooks to the customer's registered `WebhookEndpoint`. All outbound webhooks must include an `X-Timestamp` header and be signed via HMAC-SHA256 using the endpoint's secret key.
* **Acceptance Criteria:**
  * **Given** an invoice transitions to `Paid`,
  * **When** the webhook dispatcher fires the payload,
  * **Then** the payload includes the event type `provision.granted` and a valid HMAC signature in the `X-Signature` header.

**FR-011: The "Gentle Nudge" Warning Webhook**
* **Priority:** SHOULD
* **Description:** The system emits a proactive warning event prior to full suspension, allowing downstream applications to render in-app warnings.
* **Acceptance Criteria:**
  * **Given** an invoice is exactly 45 days past its `due_date`,
  * **When** the daily evaluation cron runs,
  * **Then** the system emits a `provision.warning` webhook payload.

**FR-012: Automated Suspension**
* **Priority:** SHALL
* **Description:** The system emits a suspension event when an invoice breaches the hard delinquency threshold, updating the internal entitlement state.
* **Acceptance Criteria:**
  * **Given** an invoice exceeds 60 days past its `due_date`,
  * **When** the daily evaluation cron runs,
  * **Then** the system transitions the `Entitlement` state to `Suspended` and emits a `provision.suspended` webhook payload.

### 5. Smart Sub-Ledger ERP Sync

**FR-013: Summarized Ledger Batching**
* **Priority:** SHALL
* **Description:** To protect downstream ERP architectures, the system aggregates individual micro-transactions and payment events into a balanced, double-entry `LedgerSyncBatch` before pushing to NetSuite or QBO.
* **Acceptance Criteria:**
  * **Given** 1,000 active micro-transactions occurred in a 24-hour period,
  * **When** the `POST /api/v1/ledger/sync` cron is triggered,
  * **Then** the system generates a single `LedgerSyncBatch` where Total Debits equal Total Credits, and transmits the summarized array to the target ERP.
* **API Endpoint:**
  * `POST /api/v1/ledger/sync`
  * Request schema: `{ "target_erp": "NetSuite|QBO", "date_range": { "start": "date", "end": "date" } }`
  * Response schema: `{ "batch_id": "string", "status": "Processing" }`

### 6. System & Integration Configuration (RevOps Portal)

**FR-014: Integration Lifecycle Management**
* **Priority:** SHALL
* **Description:** The system provides an administrative UI for authorized RevOps/Finance users to view the status of, connect, update credentials for, and safely disconnect external CRMs (Salesforce, HubSpot) and ERPs (NetSuite, QBO).
* **Acceptance Criteria:**
  * **Given** an Admin user navigates to the Integrations dashboard,
  * **When** they click "Disconnect" on an active NetSuite integration,
  * **Then** the system removes the stored credentials, suspends the `LedgerSyncBatch` cron jobs for that tenant, and updates the status to "Disconnected".

**FR-015: Tenant-Specific Payment Configuration**
* **Priority:** SHALL
* **Description:** The system allows administrators to enable, disable, and configure specific payment gateways (e.g., Stripe, ACH, Coinbase Commerce) independently per tenant.
* **Acceptance Criteria:**
  * **Given** a tenant administrator is configuring payment options,
  * **When** they toggle "Coinbase Commerce" to active and provide a valid API key,
  * **Then** subsequent checkout links (FR-008) generated for that tenant will render the Coinbase payment option.

**FR-016: Billing Rule Template Management**
* **Priority:** SHOULD
* **Description:** The system allows RevOps to define and save reusable billing rule templates (e.g., "Standard Enterprise SLA Overage") to be used for manual overrides or non-PDF contract creation (FR-005).
* **Acceptance Criteria:**
  * **Given** a RevOps user is manually creating a contract,
  * **When** they select "Apply Template: Standard Enterprise SLA Overage",
  * **Then** the line-item schema is automatically populated with the predefined logic and pricing structures.

**FR-017: Webhook Endpoint Configuration**
* **Priority:** SHALL
* **Description:** The system provides an interface for developers or RevOps to register target URLs to receive Entitlement webhooks, and securely generates the HMAC signing secret.
* **Acceptance Criteria:**
  * **Given** a user is configuring entitlements,
  * **When** they submit a valid HTTPS URL via `POST /api/v1/webhooks/endpoints`,
  * **Then** the system saves the endpoint, returns a newly generated HMAC-SHA256 secret key, and displays it exactly once.

**FR-018: Webhook Delivery Monitoring & Retries**
* **Priority:** SHALL
* **Description:** The system provides a dashboard for RevOps/Developers to view the status (success/failure) of all outbound webhook deliveries and manually re-trigger individual failed webhook payloads from the Dead-Letter Queue (DLQ).
* **Acceptance Criteria:**
  * **Given** a webhook delivery is sitting in the DLQ with `status: Failed`,
  * **When** the user clicks "Retry Payload" from the Delivery Monitoring dashboard,
  * **Then** the system immediately attempts to resend the payload and updates the `retry_count` and `status` based on the downstream response.

**FR-019: ERP Sync Health Dashboard**
* **Priority:** SHALL
* **Description:** The React UI provides a dashboard for Finance teams to independently monitor the success, failure, and processing status of `LedgerSyncBatch` exports to upstream ERPs.
* **Acceptance Criteria:**
  * **Given** a `LedgerSyncBatch` encountered a 429 Rate Limit error from NetSuite,
  * **When** the Finance user views the Sync Health Dashboard,
  * **Then** they see the batch listed as `RateLimited` alongside the timestamp for the next automated retry attempt.

## Non-Functional Requirements

### 1. Performance & Latency

*   **API Response Time (General):** All synchronous FastAPI endpoints (e.g., UI interactions, contract approvals) MUST respond in under **250ms** at the 95th percentile (p95) under normal load.
*   **Webhook Ingestion Latency:** The payment webhook receiver endpoint (`POST /api/v1/invoices/{id}/pay`) MUST acknowledge receipt (return `200 OK` or `202 Accepted`) in under **200ms** at the 99th percentile (p99) to satisfy the strict timeout windows of external gateways like Stripe and Coinbase Commerce.
*   **Contract Parsing Target:** The end-to-end asynchronous contract parsing process (from S3 upload to Vertex AI extraction to DB persistence) SHOULD complete in under **10 seconds** for a standard 20-page PDF document.
*   **ERP Sync Throughput:** The `LedgerSyncBatch` background cron MUST be capable of aggregating and preparing up to **10,000 micro-transactions per minute**.
*   **Resource Isolation:** The system MUST execute resource-intensive background tasks (e.g., ERP Sync, crewAI parsing, cron jobs) in strictly isolated worker processes or containers, guaranteeing they do not starve foreground web processes or degrade the synchronous API response times (p95 < 250ms).

### 2. Scalability & Concurrent Capacity

*   **Tenant Scaling:** The system MUST support horizontal scaling to handle at least **1,000 active enterprise tenants**, with complete logical data isolation between them enforced via `tenant_id` indexing in MongoDB Atlas.
*   **Concurrent Contracts:** The database and worker pool MUST seamlessly manage **10,000+ active `BillingSchedule` configurations** simultaneously evaluating during end-of-month or end-of-quarter invoice generation spikes.
*   **API Throughput:** The system MUST support a sustained inbound load of **5,000 Requests Per Second (RPS)** for usage data ingestion APIs, scaling pod replicas dynamically to prevent dropped payloads.

### 3. Reliability & Availability

*   **System Uptime:** Core payment routing interfaces and event-driven Entitlement API webhooks MUST meet a **99.99%** uptime Service Level Agreement (SLA).
*   **Graceful Degradation:** The UI/portal and non-critical workflows (e.g., historical reporting, sync health dashboards) MAY operate at a 99.9% uptime SLA and MUST gracefully degrade if downstream ERP APIs (NetSuite/QBO) experience outages, queueing data internally rather than failing user-facing requests.
*   **Recovery Time Objective (RTO):** In the event of a catastrophic regional failure, system operability MUST be restored within **4 hours**.
*   **Recovery Point Objective (RPO):** Data loss in a disaster scenario MUST not exceed **15 minutes** of transactional data, supported by continuous, automated MongoDB Atlas backups.
*   **Backup & Restore Strategy:** The system SHALL implement a documented, automated backup strategy for all persistent data. MongoDB Atlas point-in-time recovery MUST be enabled (7-day retention), with daily snapshots retained for 30 days and annual snapshots retained for 7 years. Raw PDF files in cloud storage (S3/GCS) MUST utilize versioning and cross-region replication. The full system restoration procedure MUST be tested bi-annually.

### 4. Security & Compliance

*   **Regulatory Compliance:** The platform architecture and data handling practices MUST strictly adhere to **SOC 2 Type II** standards and **GDPR** regulations from Day 1.
*   **Financial Reporting Standards:** The system SHALL ensure all generated financial data—specifically the summarized outputs of the `LedgerSyncBatch`—are structurally compliant with **GAAP** and **ASC 606** revenue recognition principles before transmission to upstream ERPs.
*   **Data Encryption:** All Personally Identifiable Information (PII) and raw contract data MUST be encrypted at rest using **AES-256** (via MongoDB's default WiredTiger encryption) and in transit using **TLS 1.3**.
*   **Secret Management:** API keys (Stripe, NetSuite, external CRMs) and webhook signing secrets MUST be stored in a dedicated, secure vault (e.g., AWS Secrets Manager/GCP Secret Manager) and MUST NEVER be logged, printed, or exposed in plain text within the database.
*   **Webhook Security:** All outbound `Entitlement` webhooks MUST be cryptographically signed using **HMAC-SHA256**. The payload header MUST include an `X-Timestamp` to allow downstream systems to prevent replay attacks (rejecting payloads older than 5 minutes).
*   **Network Boundaries:** The `POST /api/v1/webhooks/endpoints` registration feature MUST include SSRF (Server-Side Request Forgery) protection, strictly rejecting internal loopback addresses (e.g., `localhost`, `127.0.0.1`, `169.254.169.254`).

### 5. Data Integrity & Precision

*   **Financial Mathematics:** The system MUST NOT use standard floating-point arithmetic for currency calculations. All financial subtotal, tax, discount, and `amount_due` calculations MUST be executed using `Decimal` data types in Python and stored as `Decimal128` in MongoDB to prevent rounding errors.
*   **Idempotency:** All payment ingestion and ERP sync API endpoints MUST implement strict idempotency keys (e.g., `gateway_transaction_id`). Processing the identical payload multiple times MUST result in exactly one database mutation.

### 6. Usability, Maintainability & Data Management

*   **UI Learnability:** The React/TypeScript frontend portal SHALL allow a new RevOps user to successfully navigate the core "golden path" (upload a PDF, review the AI draft, map a rule, and approve) in under **30 minutes** of training.
*   **Code Quality & Linting:** The Python/FastAPI backend MUST adhere strictly to **PEP 8** standards. The React frontend MUST maintain strict TypeScript typing with **0 `any` types** permitted in billing logic, passing CI/CD linting with a >90% compliance score.
*   **Test Coverage:** All core mathematical and state-machine logic MUST maintain a minimum of **80% automated test coverage** (unit and integration tests combined) before any deployment to production.
*   **Data Migration Tooling:** The system SHALL provide a documented REST API and/or bulk-import tooling optimized for efficient, validated ingestion of historical contracts and billing data during new tenant onboarding. This tooling MUST structurally validate all incoming historical data to prevent downstream ERP pollution.

### 7. Observability & Logging

*   **Structured Logging:** All application logs MUST be output in JSON format. Every log entry MUST include the following key-value pairs: `tenant_id`, `trace_id`, `user_id`, `endpoint`, `latency_ms`, and `status_code`.
*   **Auditability:** The system MUST maintain an immutable audit log of all human interactions with a `ContractDocument` or `BillingSchedule`, tracking `user_id`, `timestamp`, `action_type` (e.g., "manual_override", "approved"), and the previous/new state values.

## Edge Cases

### 1. AI Contract Parsing Anomalies

*   **Contradictory Legal Clauses:**
    *   *Scenario:* A contract PDF contains an "Executive Summary" table stating a 10% discount, but the legal text in Section 4.2 explicitly states a 5% discount.
    *   *System Behavior:* Vertex AI MUST extract both values and assign a low `ai_confidence_score` (< 0.80) to the discount field, appending a metadata flag indicating "Conflicting Values Found." This forces the `ContractDocument` into the `PendingReview` state, requiring the RevOps user to explicitly select the correct value before activation.
*   **Hand-Written Margin Notes or Strike-throughs:**
    *   *Scenario:* A sales rep manually crosses out a printed price on the PDF, writes a new price in pen, and scans the document.
    *   *System Behavior:* If the OCR/Vertex AI pipeline detects handwritten text or strike-throughs overlaying financial terms, the system MUST flag the document with a `ManualReviewRequired` tag, setting the `ai_confidence_score` to `0.0`. The deep-linking UI must highlight the altered bounding box in red to draw the RevOps user's immediate attention.
*   **Ambiguous or Missing Critical Clauses:**
    *   *Scenario:* Contract PDF is ingested, but the AI cannot confidently extract a required `BillingSchedule` field (e.g., 'Payment Terms', 'Term Length') due to ambiguity or absence in the text.
    *   *System Behavior:* The AI MUST return `null` for the field with a low `ai_confidence_score` (< 0.5), flagging the contract as `PendingReview` with a metadata flag "Missing Critical Term." The UI must explicitly prompt the RevOps user to manually input the missing data before the schedule can be activated.
*   **Corrupted/Unreadable PDF Upload:**
    *   *Scenario:* An uploaded PDF is corrupted, password-protected, or fundamentally unreadable by the OCR/Vertex AI pipeline.
    *   *System Behavior:* The system MUST reject the upload at the FastAPI layer during `POST /api/v1/contracts/parse` with a `400 Bad Request` and a user-friendly error message ("Invalid PDF Format/Protected"), preventing the file from entering the async parsing pipeline.
*   **Duplicate Contract Ingestion:**
    *   *Scenario:* The same contract PDF or `crm_reference_id` is accidentally submitted multiple times (e.g., due to user error or a re-triggered CRM webhook).
    *   *System Behavior:* The `POST /api/v1/contracts/parse` endpoint MUST check for existing `ContractDocument` records with the same `crm_reference_id` or matching PDF hash. If a duplicate is detected for an `Active` or `PendingReview` contract, the system MUST return a `409 Conflict` status code with an existing `contract_id` reference, preventing the creation of a redundant `ContractDocument` record.

### 2. Hybrid Billing & Mathematical Boundaries

*   **Zero-Dollar Invoices & "100% Free" Periods:**
    *   *Scenario:* A contract specifies "First 3 months free," resulting in an `Invoice` generation where the `amount_due` is exactly $0.00.
    *   *System Behavior:* The cron job MUST still generate the `Invoice` with a $0.00 value. It MUST instantly transition the state from `Issued` to `Paid` without routing to a payment gateway. The system MUST still emit the `provision.granted` webhook to ensure the user receives access to the free software, and MUST generate a $0.00 `LedgerSyncBatch` entry for auditable revenue recognition (ASC 606) tracking.
*   **Leap Year and Proration Slippage:**
    *   *Scenario:* An annual SaaS subscription is upgraded to a higher tier on February 29th, requiring daily proration calculations.
    *   *System Behavior:* The billing math engine MUST utilize the exact number of days in the specific calendar year (366 for leap years) when calculating the daily rate using `Decimal128` types, ensuring the proration does not result in a recurring 1-cent discrepancy at the end of the term.

### 3. Payment Gateway & Crypto Volatility

*   **Crypto Slippage (Micro-Underpayments):**
    *   *Scenario:* A client pays a $10,000 USD invoice using ETH via Coinbase Commerce. By the time the transaction settles on the blockchain (minutes later), gas fees or momentary volatility result in a fiat settlement of $9,999.85.
    *   *System Behavior:* The system MUST NOT leave the invoice in a `PartiallyPaid` state indefinitely for immaterial amounts. If the received fiat amount is within a configurable "Slippage Tolerance Threshold" (e.g., $1.00 or 0.1%), the system MUST automatically transition the invoice to `Paid` and record the $0.15 variance as a separate "Currency Exchange Loss" line item in the corresponding `LedgerSyncBatch`.
*   **Concurrent Double Payments (Race Condition):**
    *   *Scenario:* A user clicks "Pay" twice rapidly on the Stripe checkout page, or two different AP clerks attempt to pay the same invoice simultaneously via ACH and Crypto.
    *   *System Behavior:* The `POST /api/v1/invoices/{id}/pay` webhook receiver MUST utilize an optimistic locking mechanism on the MongoDB `Invoice` document. The first transaction to arrive updates the invoice to `Paid`. The second transaction, upon checking the `version` or `state` of the document, will recognize the invoice is already paid. The system MUST accept the webhook (`200 OK`) but trigger an automated "Overpayment Refund Workflow" alert to the Finance team, preventing a negative `amount_due`.

### 4. Entitlement API Race Conditions

*   **Payment Clears During the Automated Suspension Window:**
    *   *Scenario:* An invoice hits day 60 of delinquency. At 11:59 PM, the customer pays via credit card. At 12:00 AM, the daily cron job runs to suspend delinquent accounts.
    *   *System Behavior:* The cron job MUST evaluate the *current* state of the `Invoice` at the exact millisecond of execution, not the state at the start of the batch run. Because the payment webhook mutated the state to `Paid` at 11:59 PM, the cron job MUST bypass the suspension logic and refrain from emitting the `provision.suspended` webhook.
*   **Partial Payment During Delinquency:**
    *   *Scenario:* An invoice is between 45 and 60 days past due, and a partial payment is received via ACH.
    *   *System Behavior:* The system MUST update the `Invoice` status to `PartiallyPaid` and reduce the `amount_due`. However, the delinquency clock for the *remaining* balance MUST continue. The `provision.warning` webhook should not be re-emitted if already sent, and no `provision.granted` is sent until the invoice is fully `Paid`.

### 5. External Integration & ERP Sync Anomalies

*   **Unmapped Product SKUs in Ledger Batch:**
    *   *Scenario:* The RevOps team adds a new product ("Enterprise Consulting Tier 2") to a contract, but Finance has not yet created the corresponding Income Account mapping in NetSuite.
    *   *System Behavior:* When generating the `LedgerSyncBatch`, the system MUST evaluate all line items against the cached Chart of Accounts. If an unmapped SKU is found, the system MUST NOT fail the entire batch. It MUST route the unmapped line item to a configurable "Suspense / Uncategorized Revenue" account in the ERP, flag the `LedgerSyncBatch` status as `SyncedWithWarnings`, and trigger an alert to the Finance dashboard to manually re-classify the funds in NetSuite.
*   **Persistent ERP Sync Failure:**
    *   *Scenario:* The connected ERP (NetSuite/QBO) API consistently returns non-recoverable errors (e.g., 401 Unauthorized due to expired tokens, 403 Forbidden).
    *   *System Behavior:* After 5 consecutive failed `LedgerSyncBatch` pushes over a 24-hour period, the system MUST transition the tenant's ERP connection status to `Error`, disable further automated cron sync attempts to prevent endless retry loops, send a critical alert to the Finance dashboard, and move all pending batches to a long-term DLQ for manual intervention.
*   **Delayed/Failed CRM Webhook Ingestion:**
    *   *Scenario:* The initial CRM "Contract Won" webhook (triggering `POST /api/v1/contracts/parse`) is significantly delayed or fails to be delivered to the system.
    *   *System Behavior:* The system MUST implement a periodic reconciliation process (via crewAI/cron jobs) to query connected CRMs for recently "Closed-Won" deals without corresponding `ContractDocument` records. Unprocessed deals MUST then be automatically ingested to prevent missed contracts and delayed invoicing.

### 6. Contract Lifecycle Management

*   **Contract Amendment or Cancellation:**
    *   *Scenario:* An `Active` contract is amended mid-term by Sales, or canceled entirely by the client, requiring immediate changes to the `BillingSchedule`.
    *   *System Behavior:* The system MUST NOT mutate the original `Active` record. It MUST allow RevOps to upload an amendment PDF or trigger a cancellation workflow. This MUST create a new `BillingSchedule` version (with an explicit `start_date` for future billing) or immediately trigger a final prorated adjustment and a `provision.suspended` webhook (if canceled), preserving an immutable audit trail of the original contract's state.

### 7. Multi-Currency & Localization Anomalies

*   **Multi-Currency Contract Denomination:**
    *   *Scenario:* A contract specifies billing in a non-USD fiat currency (e.g., EUR, GBP), but the core ERP general ledger operates in USD.
    *   *System Behavior:* The system MUST store the `amount_due` in the contract's natively specified currency. For `LedgerSyncBatch` entries pushing to USD-denominated ERPs, the system MUST perform currency conversion using an integrated, auditable daily exchange rate source (e.g., ECB or Open Exchange Rates) and explicitly record the exact FX rate utilized within the batch metadata.

## Error Handling

### 1. Error Taxonomy & Response Strategy

The Contract Compiler categorizes system failures into four distinct severities, mapped directly to HTTP status codes and operational handling protocols to ensure strict data integrity and a seamless RevOps experience.

| Category | HTTP Code | Source | Definition | Handling Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Validation / Client** | `400`, `422`, `409` | Client Input Validation / API Schema Violation | Missing required fields, invalid PDF formats, or state-machine violations (e.g., trying to approve an already `Active` contract). | Synchronous rejection with actionable UI feedback. No data mutation. |
| **Authentication** | `401`, `403` | Integrations, Admin Portal | Expired JWTs, invalid API keys for CRM/ERP integrations, or insufficient role permissions. | Synchronous rejection. Force user re-authentication or prompt integration re-connection. |
| **External Dependency** | `429`, `502`, `503`, `504` | NetSuite, Stripe, Vertex AI | Third-party rate limits, timeouts, or temporary unavailability. | Asynchronous queueing (DLQ), exponential backoff, and graceful degradation. |
| **System Fault** | `500` | Core Backend (FastAPI/MongoDB) | Unhandled exceptions, database connection drops, or memory limits. | Circuit breaker trips, synchronous generic error to user, P1 alert to Engineering. |

### 2. Specific Failure Modes & Handling

#### 2.1 AI Parsing Failures (Vertex AI / crewAI)
*   **Error Condition:** The uploaded PDF is unreadable, corrupted, or Vertex AI times out (exceeding a configurable 30-second threshold).
*   **System Handling:** The background crewAI worker catches the timeout or OCR failure exception. It transitions the `ContractDocument` in MongoDB to the `PendingReview` state, forcing an `ai_confidence_score` of `0.0`.
*   **User-Facing Message:** "Automated parsing failed. Please manually map the billing rules using the templates on the right."
*   **Logging/Alerting:** Logged as a `WARN` event. No paging alert, as the human-in-the-loop fallback natively handles this without blocking operations.

#### 2.2 ERP Rate Limits & Sync Failures (NetSuite / QBO)
*   **Error Condition:** The `POST /api/v1/ledger/sync` cron job attempts to push a `LedgerSyncBatch` and receives a `429 Too Many Requests` or `503 Service Unavailable` from the target ERP.
*   **System Handling:** The system MUST intercept the `429` status. The worker intercepts the `Retry-After` header. If present, it sleeps for the specified duration. Otherwise, it implements a default exponential backoff strategy (e.g., `[5m, 15m, 1h]`). The batch status transitions to `RateLimited`.
*   **User-Facing Message:** (In Sync Health Dashboard): "ERP Sync paused due to upstream rate limits. 42 batches queued. Automatically retrying at [Time]."
*   **Logging/Alerting:** Logged as `WARN`. If a batch fails 5 consecutive times, it is routed to the Dead-Letter Queue (DLQ), status updates to `Failed`, and a `P2` alert is sent to the Finance Slack channel.

#### 2.3 Webhook Delivery Failures (Entitlement API)
*   **Error Condition:** The system emits a `provision.granted` or `provision.suspended` webhook, but the client's registered endpoint returns a `5xx` error or times out.
*   **System Handling:** The webhook dispatcher logs the failure and inserts the payload into the `webhook_deliveries` MongoDB collection (the DLQ) with `status: Pending`. It implements an exponential backoff retry strategy: `[1m, 5m, 30m, 2h, 12h]`. 
*   **User-Facing Message:** (In Sync Health Dashboard): "Webhook delivery failed. Target server returned 503. Retry X of 5 scheduled."
*   **Logging/Alerting:** Logged as `ERROR`. If all 5 retries are exhausted, the status updates to `Failed`, and a `P2` alert is fired to the Engineering on-call rotation.

#### 2.4 Payment Gateway Webhook Failures (Stripe / Coinbase)
*   **Error Condition:** The internal `POST /api/v1/invoices/{id}/pay` endpoint goes down while Stripe is attempting to push a "Payment Succeeded" event.
*   **System Handling:** The system relies on the external gateway's native retry logic (e.g., Stripe retries over 3 days). When the system recovers, it processes the queued webhooks. To prevent race conditions during recovery, strict idempotency is enforced using the `gateway_transaction_id` to ensure no invoice is credited twice.
*   **User-Facing Message:** None (handled asynchronously).
*   **Logging/Alerting:** Uptime monitoring triggers a `P1` alert if the `/pay` endpoint is unreachable for > 1 minute.

#### 2.5 State Machine Violations
*   **Error Condition:** A RevOps user double-clicks the "Approve & Activate" button, sending two concurrent `PATCH /api/v1/contracts/{id}/approve` requests.
*   **System Handling:** The FastAPI backend utilizes optimistic concurrency control in MongoDB. The first request successfully updates the state from `PendingReview` to `Active`. The second request detects the state is no longer `PendingReview` and throws a `409 Conflict`.
*   **User-Facing Message:** "This contract has already been activated."
*   **Logging/Alerting:** Logged as `INFO`. No alert required.

#### 2.6 External API Schema Mismatch Failures
*   **Error Condition:** An external API (CRM, ERP, Payment Gateway) changes its schema, causing the Contract Compiler's ingestion or processing logic to fail (e.g., unexpected JSON structure, missing mandatory fields).
*   **System Handling:** The system MUST log the schema mismatch as an `ERROR`, flag the affected `ContractDocument` or `LedgerSyncBatch` with an `IntegrationSchemaError` status, and route it to the DLQ.
*   **User-Facing Message:** "Integration error: External system schema mismatch. Please contact support."
*   **Logging/Alerting:** Logged as `ERROR`. A `P2` alert is sent to Engineering on-call.

#### 2.7 Integration Authentication Token Expiry
*   **Error Condition:** An automated background job (e.g., `LedgerSyncBatch` cron) attempts to connect to an external ERP (NetSuite, QBO) but the stored API token/credentials have expired or been revoked.
*   **System Handling:** The system MUST catch the `401 Unauthorized` or `403 Forbidden` error, mark the integration status as `Expired/Revoked`, pause all automated operations for that tenant's integration to prevent endless failures, and route any affected batches to the DLQ.
*   **User-Facing Message:** (In Sync Health Dashboard): "ERP Integration failed: Authentication expired. Please re-authenticate NetSuite."
*   **Logging/Alerting:** Logged as `ERROR`. A `P2` alert is sent to the Finance Slack channel.

### 3. Manual Resolution Tools & Auditability

For items routed to the Dead-Letter Queue (DLQ) after exhausting automated retries, the system SHALL provide RevOps and Finance teams with a dedicated UI dashboard. This interface must allow authorized users to review the failed payload, modify data if necessary (e.g., correcting an invalid NetSuite Customer ID), and manually resubmit or explicitly discard the failed payload/batch. 

To maintain strict financial compliance, all manual modifications and resubmissions of DLQ payloads MUST be immutably audited. The system MUST track `user_id`, `timestamp`, `action_type` ('modified_payload', 'resubmitted', 'discarded'), and store a precise diff of the `previous_payload` versus the `new_payload` in MongoDB.

*(Note: Refer to the Non-Functional Requirements section for overarching logging configurations, log levels, and data retention policies).*

### 4. Graceful Degradation Strategy

The Contract Compiler architecture assumes that external CRMs and ERPs are inherently brittle. Therefore, the core internal web application MUST remain highly resilient.

*   **External Outages:** If NetSuite is down, RevOps users must still be able to upload PDFs, run AI extraction, and approve contracts. The resulting invoices are simply queued internally. If Vertex AI is down, users must still be able to manually create and activate contracts using pre-defined Billing Rule Templates.
*   **Internal Non-Critical Service Degradation:** If a non-critical internal service (e.g., the search indexing worker or historical analytics processing) experiences performance degradation or a temporary outage, the core billing and payment processing pathways MUST remain completely unaffected. The user interface for the affected features MUST display an informative loading state or partial data, rather than failing the entire portal.
*   **Core System Unavailability User Experience:** If core internal services (e.g., the primary MongoDB Atlas cluster or the FastAPI routing layer) become entirely unavailable, the frontend React SPA MUST display a clear, informative "System Unavailable" state. This state must include an estimated recovery time (if known) and direct users to the corporate status page, preventing blank screens or infinite loading spinners.

## Success Metrics

### 1. Business & Financial Impact (Primary KPIs)

*   **Overall Q2C Cycle Time Reduction:**
    *   *Definition:* The macro delta representing the total time from contract inception (CRM "Closed-Won") to full invoice payment and subsequent ERP synchronization, compared against historical manual processes.
    *   *Baseline:* To be established pre-launch by auditing a statistically significant sample of historical Q2C data.
    *   *Target:* > 50% reduction in total end-to-end cycle time within 6 months of launch.
    *   *Measurement:* Aggregate the median `Time-to-Invoice` latency with the duration required for external payment reconciliation and the `ERP Data Freshness` timestamps.
*   **Time-to-Invoice (Velocity):**
    *   *Definition:* The median time elapsed between the system receiving a CRM "Closed-Won" webhook and the successful generation of an `Issued` invoice state.
    *   *Baseline:* Estimated 3 days (72 hours) based on industry standards for manual processing.
    *   *Target:* < 4 hours (representing a reduction of > 94% from the 3-day baseline).
    *   *Measurement:* Calculated via MongoDB timestamps (delta between `created_at` on `ContractDocument` to `issue_date` on `Invoice`).
*   **Unbilled Usage (Revenue Leakage):**
    *   *Definition:* The total dollar value of metered overages or staggered discounts that were missed or misconfigured during contract transcription.
    *   *Baseline:* Estimated 2-4% of total ARR for mid-market hybrid billing models.
    *   *Target:* $0.00 (100% capture of all contractually defined value).
    *   *Measurement:* Audited quarterly by comparing a representative statistical sample (e.g., 10% of new contracts per quarter) of original PDF contracts against the generated `BillingSchedule` line items and subsequent `LedgerSyncBatch` totals.
*   **Billing Schedule Accuracy:**
    *   *Definition:* The percentage of `Issued` invoices that mathematically match the approved `BillingSchedule` (inclusive of recurring, metered, and milestone components).
    *   *Baseline:* Variable based on historical manual entry error rates.
    *   *Target:* > 99.9% accuracy.
    *   *Measurement:* Monitored continuously via internal reconciliation scripts comparing the calculated `amount_due` array against the mathematical parameters locked within the `Active` `BillingSchedule`.
*   **Payment Success Rate by Channel:**
    *   *Definition:* The percentage of attempted payments that successfully result in an `Invoice` transitioning to `Paid` status, segmented by payment method.
    *   *Baseline:* To be established post-launch based on initial transaction volume.
    *   *Target:* > 99.5% for fiat payments (Stripe/ACH); > 98% for crypto payments (accounting for network volatility).
    *   *Measurement:* Querying MongoDB `Invoice` records for webhook `payment_attempts` versus the final `status: Paid`, segmented by the specific gateway router.
*   **Post-Activation Contract Compliance Rate:**
    *   *Definition:* The percentage of `Active` contracts where all terms (billing thresholds, suspension rules) are continually met and accurately reflected in downstream systems.
    *   *Baseline:* To be established by auditing current manual post-activation compliance.
    *   *Target:* > 99% compliance.
    *   *Measurement:* Regular, automated audits comparing the `Active` contract terms against current system states (e.g., comparing the `Entitlement` status array against the delinquent `Invoice` array).

### 2. AI Performance, Operational Efficiency & User Adoption

*   **AI Auto-Approval Rate (Straight-Through Processing):**
    *   *Definition:* The percentage of `ContractDocument` uploads that achieve an `ai_confidence_score` >= 0.95 and are approved by RevOps *without* any manual field edits.
    *   *Baseline:* 0% (currently entirely manual).
    *   *Target:* > 80% within 90 days of launch; > 95% on standardized contract templates.
    *   *Measurement:* Monitored via Grafana dashboards querying MongoDB for contracts where `status` changed from `PendingReview` to `Active` without triggering a `manual_override` audit event.
*   **Manual Reconciliation Time:**
    *   *Definition:* The average active time a RevOps or Finance user spends in the UI per contract to verify or correct the AI-generated `BillingSchedule`.
    *   *Baseline:* ~45 minutes per enterprise contract.
    *   *Target:* < 5 minutes per contract.
    *   *Measurement:* React front-end telemetry tracking the duration between a user opening a `PendingReview` document and clicking "Approve & Activate."
*   **User Engagement & Feature Adoption:**
    *   *Definition:* The Monthly Active Users (MAU) within the RevOps Configuration Portal, specifically tracking the utilization of core features like AI draft review, manual contract creation, and integration configuration.
    *   *Baseline:* N/A (new portal).
    *   *Target:* > 70% MAU of licensed RevOps/Finance personnel within 6 months.
    *   *Measurement:* Front-end analytics tracking user auth tokens and specific UI event triggers (e.g., clicking "Save Template").

### 3. System Health & Platform Reliability

*   **Automated Entitlement Action Success Rate:**
    *   *Definition:* The percentage of `provision.suspended` and `provision.granted` webhooks that are successfully received and actioned by the client's infrastructure, leading to a verified software entitlement state change.
    *   *Baseline:* N/A (currently a manual, asynchronous Slack process).
    *   *Target:* > 98% within 3 months of launch.
    *   *Measurement:* Tracked via an inbound `provision.actioned` confirmation webhook from the client system, or via automated scheduled API audits comparing the Contract Compiler's internal `Entitlement` state with the client application's database.
*   **ERP Sync Integrity:**
    *   *Definition:* The percentage of `LedgerSyncBatch` transactions successfully pushed to NetSuite/QBO without falling into a terminal `Failed` state.
    *   *Baseline:* Variable, heavily dependent on current ad-hoc workarounds and 429 rate limits.
    *   *Target:* 100% success rate (accounting for automated retries), with 0 silent failures.
    *   *Measurement:* Dead-Letter Queue (DLQ) depth monitored via Prometheus. A successful metric requires the DLQ to resolve to 0 depth continuously.
*   **ERP Data Freshness:**
    *   *Definition:* The median latency from a `LedgerSyncBatch` becoming internally available to its successful transmission and confirmation in the target upstream ERP.
    *   *Baseline:* Highly variable due to manual batch pushes.
    *   *Target:* < 1 hour for standard daily batches; < 15 minutes for critical month-end close batches.
    *   *Measurement:* Calculated by comparing the `created_at` timestamp of the `LedgerSyncBatch` with the `erp_sync_timestamp` populated upon receiving a `200 OK` response from NetSuite/QBO.
*   **Webhook Delivery Reliability:**
    *   *Definition:* The fundamental infrastructure success rate of outbound webhooks reaching the client's endpoint, regardless of the downstream application's subsequent processing.
    *   *Baseline:* N/A (new feature).
    *   *Target:* > 99.9% delivery success within the first 3 exponential backoff retry attempts.
    *   *Measurement:* Querying the `webhook_deliveries` MongoDB collection for final terminal statuses.

### 4. Experimentation & A/B Testing

*   **UI Layout for Copilot Review:**
    *   *Hypothesis:* Presenting the AI's confidence score color-coded by individual line-item (rather than a single global score for the contract) will decrease *Manual Reconciliation Time* by 20%.
    *   *Experiment:* A/B test the "PendingReview" UI layout. Group A receives a single global confidence score. Group B receives field-level confidence scores with specific low-confidence fields highlighted in yellow.
    *   *Measurement:* Compare the median UI session duration between Group A and Group B using React front-end telemetry events.

## Dependencies

### 1. Third-Party Integrations & Upstream/Downstream Systems

*   **Google Vertex AI API:**
    *   *Purpose:* Core extraction of unstructured contract data (PDFs) into structured `BillingSchedule` JSON schemas.
    *   *Risk:* Model deprecation, latency, or unannounced API schema changes.
    *   *Mitigation:* Strict version pinning of the Vertex AI models (managed via GCP Model Registry and specific deployment configurations). Fallback UI allows manual contract entry if the API is unreachable.
*   **Upstream CRM Systems (Salesforce, HubSpot):**
    *   *Purpose:* Triggering the Quote-to-Cash flow via inbound webhooks upon a "Closed-Won" event and providing the initial contract PDF.
    *   *Risk:* CRM admin changes webhook configurations, or API limits prevent pulling the PDF.
    *   *Mitigation:* Provide clear, versioned webhook configuration documentation for RevOps admins. Implement a daily reconciliation cron job to catch missed Closed-Won events.
*   **Downstream ERP Systems (NetSuite, QuickBooks Online):**
    *   *Purpose:* Destination for the summarized `LedgerSyncBatch` journal entries to maintain auditable financial records.
    *   *Risk:* Extremely strict API rate limits (HTTP 429) and flat Chart of Account constraints.
    *   *Mitigation:* Implementation of a robust batching engine with exponential backoff and a Dead-Letter Queue (DLQ) to ensure data is never lost, only delayed.
*   **Payment Gateways (Stripe, Coinbase Commerce, ACH Processors):**
    *   *Purpose:* Processing fiat and cryptocurrency payments from generated invoices.
    *   *Risk:* Coinbase Commerce specifically carries the risk of regulatory shifts regarding crypto processing.
    *   *Mitigation:* The system natively relies on the gateways to handle regulatory/KYC checks and auto-settle crypto into USD. The Contract Compiler never takes custody of funds.
*   **Escrow-as-a-Service API Providers (e.g., Stripe Connect Escrow, Dwolla):**
    *   *Purpose:* Facilitating milestone-based billing without the Contract Compiler acting as a regulated financial institution.
    *   *Risk:* Vendor lock-in or licensing changes from the escrow provider.
    *   *Mitigation:* Abstract the escrow logic behind a generic `MilestoneBilling` internal interface to allow swapping escrow vendors. Additionally, conduct regular market research (quarterly) for alternative providers to mitigate vendor lock-in risks, and ensure legal review of all escrow provider contracts for licensing changes.

### 2. Infrastructure & Platform Dependencies

*   **Cloud Platform (Google Cloud Platform / AWS):**
    *   *Purpose:* Hosting the entire application infrastructure, including compute, networking, security, and managed services.
    *   *Risk:* Regional outages, service degradation, or unannounced policy changes by the cloud provider.
    *   *Mitigation:* Leverage multi-region deployments for critical, user-facing services (e.g., API Gateway, core FastAPI cluster) and databases (MongoDB Atlas). Adhere to specific cloud provider best practices for high availability (e.g., GCP Cloud Architecture Framework, AWS Well-Architected Framework).
*   **MongoDB Atlas:**
    *   *Purpose:* Primary persistence layer for tenant data, `BillingSchedules`, `Invoices`, and webhook Dead-Letter Queues.
    *   *Risk:* Database downtime halts all contract orchestration and invoice generation.
    *   *Mitigation:* Utilize multi-AZ deployments with automated point-in-time recovery backups (7-day retention minimum).
*   **Cloud Storage (AWS S3 / Google Cloud Storage):**
    *   *Purpose:* Secure, immutable storage of original contract PDFs.
    *   *Risk:* Accidental deletion or unauthorized access.
    *   *Mitigation:* Enforce strict IAM roles, bucket versioning, and AES-256 encryption at rest.
*   **crewAI Framework:**
    *   *Purpose:* Orchestrating the background worker tasks that interface with Vertex AI and handle automated dunning workflows.
    *   *Risk:* Framework breaking changes in future open-source updates.
    *   *Mitigation:* Pin the crewAI package version in `pyproject.toml` and maintain >80% unit test coverage on the worker logic to catch update regressions.
*   **Broader Open-Source Software Ecosystem:**
    *   *Purpose:* Foundation for the Python backend (FastAPI, Pydantic, etc.), React/TypeScript frontend, and asynchronous processing (Celery/RQ).
    *   *Risk:* Security vulnerabilities (CVEs), maintainer abandonment, or unexpected breaking changes in upstream libraries.
    *   *Mitigation:* Implement automated dependency scanning (e.g., Snyk, Dependabot), maintain a strict dependency versioning policy, and conduct regular security audits.
*   **CI/CD Pipeline & Tooling:**
    *   *Purpose:* Automating code integration, testing, and deployment across all environments.
    *   *Risk:* Pipeline failures (e.g., build breaks, deployment issues) disrupt development velocity and deployment cadence.
    *   *Mitigation:* Implement redundant CI/CD runners, maintain strict test gates (e.g., forcing 80% coverage), and ensure clear rollback strategies for backend FastAPI pods and frontend React builds.

### 3. Internal & Client Cross-Functional Team Dependencies

*   **Client Engineering Teams:**
    *   *Purpose:* The entire automated provisioning value proposition relies on the client's engineering team implementing a secure endpoint to ingest the `provision.granted` and `provision.suspended` webhooks.
    *   *Risk:* Client engineers de-prioritize the integration, resulting in continued "free service" for delinquent accounts.
    *   *Mitigation:* Provide exhaustive OpenAPI documentation, copy-pasteable webhook signature verification code snippets (in Python/Node/Go), and clear integration guides within the RevOps portal.
*   **Client Finance/Controllership Teams:**
    *   *Purpose:* Defining the initial Chart of Accounts mapping and configuring the specific ASC 606 revenue recognition rules within the Contract Compiler's ERP integration settings.
    *   *Risk:* Incorrect mapping leads to massive ledger pollution in NetSuite.
    *   *Mitigation:* Mandatory onboarding checklists and the "SyncedWithWarnings" DLQ feature to catch unmapped SKUs before they reach the ERP.
*   **Internal Product & Engineering Teams (Core App Dev):**
    *   *Purpose:* Collaboration on defining precise entitlement states, integrating provisioning webhooks into core application logic, and setting up monitoring/alerting infrastructure for the Contract Compiler.
    *   *Risk:* Resource constraints or conflicting priorities within core app teams delay the full realization of automated entitlements.
    *   *Mitigation:* Establish clear SLAs for response to webhook documentation feedback. Align on a shared roadmap for provisioning features, ensuring the Contract Compiler's webhooks provide sufficient data for client consumption.
*   **Internal Security Operations (SecOps) / Incident Response Team:**
    *   *Purpose:* Monitoring for security threats, responding to incidents, and ensuring a continuous compliance posture.
    *   *Risk:* Inadequate security monitoring or slow incident response could lead to data breaches or regulatory penalties.
    *   *Mitigation:* Establish clear runbooks for security incident response, natively integrate Contract Compiler JSON logs with centralized SIEM tools, and conduct regular security drills.
*   **Internal Customer Support / Operations Team:**
    *   *Purpose:* Providing first-line support for client inquiries, troubleshooting user issues within the RevOps portal, and escalating technical problems.
    *   *Risk:* Lack of product knowledge or diagnostic tools impedes efficient issue resolution, leading to a poor customer experience.
    *   *Mitigation:* Provide comprehensive knowledge base articles, runbooks for common integration issues (e.g., resolving a "RateLimited" ERP sync status), and clear escalation paths to engineering.

### 4. Legal & Regulatory Dependencies

*   **SOC 2 & GDPR Compliance Frameworks:**
    *   *Purpose:* Required for enterprise SaaS sales motions. The system processes highly sensitive financial data and PII.
    *   *Risk:* Failing a SOC 2 audit prevents go-to-market motions for the ICP ($20M-$200M ARR mid-market companies).
    *   *Mitigation:* Design all data models with strict tenant-isolation, implement AES-256 encryption on all databases, and maintain an immutable audit log of all manual overrides.
*   **Internal Legal Counsel / Contract Review Specialists:**
    *   *Purpose:* Providing expert guidance on the interpretation of complex or novel contract clauses, and validating the Vertex AI extraction logic against legal intent.
    *   *Risk:* Misinterpretation of legal text by AI (even with human-in-the-loop) leads to non-compliance or revenue miscalculation.
    *   *Mitigation:* Establish a monthly feedback loop for AI model training data. This includes mandatory legal review of edge-case contract parsing outputs (e.g., contradictory clauses) and model performance reports to ensure alignment with true legal intent.

## Assumptions

### 1. Business & Market Assumptions

*   **Standardization of Legal Formats:** We assume that while the specific clauses within target customer contracts are highly variable (bespoke discounts, metered tiers), the underlying document format itself relies on standardized PDF structures (e.g., recognizable text layers, standard optical character recognition patterns) rather than heavily image-based or handwritten documentation.
*   **Evolution of Contract Term Complexity:** We assume that while contracts remain bespoke, the fundamental *types* of billing clauses and legal structures (e.g., recurring, metered, milestones) will not evolve so rapidly or become so infinitely variable that the AI model requires constant re-engineering or per-tenant bespoke training to maintain the >80% confidence baseline.
*   **Adoption of Auto-Fiat Crypto Settlements:** We assume that the primary barrier to mid-market B2B crypto adoption is balance sheet volatility and tax complexity (ASC 606), not the payment method itself. Therefore, we assume clients will readily adopt crypto payments if the platform strictly guarantees instant, auto-fiat settlement (e.g., via Coinbase Commerce).
*   **Willingness to Decouple Entitlements:** We assume that client engineering teams are willing and have the technical capacity to decouple their core application's access-control logic from their legacy billing systems, migrating to our webhook-driven (`provision.granted`, `provision.suspended`) architecture.
*   **Market Readiness for Q2C Orchestration Layer:** We assume that mid-market B2B enterprises ($20M-$200M ARR) are actively seeking and willing to adopt a specialized, AI-native Q2C orchestration middleware that bridges existing CRMs and ERPs, rather than seeking a monolithic ERP replacement or continuing with manual spreadsheet workarounds.
*   **Client Technical Capability for Integrations:** We assume that client engineering teams possess sufficient technical expertise and resources to implement and maintain integrations with our Event-Driven Entitlement API (FR-010) within a reasonable timeframe, leveraging our provided OpenAPI documentation.
*   **Client Historical Data Quality:** We assume that any historical contract and billing data provided by clients for migration, while potentially diverse, will be structured enough to be ingested and mapped via our automated Data Migration Tooling without requiring extensive manual cleansing or re-entry by our implementation team.

### 2. Technical & Infrastructure Assumptions

*   **ERP Extensibility Constraints:** We assume that core ERPs (specifically NetSuite and QuickBooks Online) cannot reliably handle high-frequency, micro-transactional usage data due to hard API rate limits (e.g., HTTP 429) and flat Chart of Account restrictions. Our architecture inherently assumes that *aggregation prior to sync* (`LedgerSyncBatch`) is mandatory.
*   **Vertex AI Capabilities:** We assume Google Vertex AI (and the orchestrating crewAI agents) can consistently achieve an extraction confidence score of >80% on standard B2B SaaS and Hardware-as-a-Service contracts without requiring custom, per-tenant fine-tuning models from Day 1.
*   **Long-term AI Model Stability & Performance:** We assume that the underlying Google Vertex AI platform will continue to evolve in a way that enhances or maintains extraction accuracy and performance, and that the unit costs for inference remain predictable and sustainable for our business model.
*   **Webhook Idempotency:** We assume that external payment gateways (Stripe, Coinbase Commerce) will occasionally misfire or double-send webhook events due to network latency. The system architecture assumes these events are inherently unreliable, necessitating strict internal idempotency locks based on `gateway_transaction_id`.
*   **Data Precision:** We assume that standard floating-point arithmetic is structurally insufficient for enterprise billing. The system assumes a baseline requirement of strict `Decimal` math in Python and `Decimal128` storage in MongoDB Atlas to prevent rounding errors across massive transaction volumes.
*   **Predictable Data Storage Costs:** We assume that the long-term storage costs for immutable PDF documents in cloud storage and the historical audit logs in MongoDB Atlas will remain within predictable budget forecasts, even with the exponential growth in processed contracts and strict data retention requirements.

### 3. Operational & Delivery Assumptions

*   **Human-in-the-Loop Necessity & RevOps Bandwidth:** We assume that 100% autonomous AI billing is currently unacceptable to corporate controllers and auditors due to hallucination risks. The success of this product assumes target RevOps and Finance teams will have adequate operational bandwidth to consistently perform the required manual reviews and approvals of AI-generated drafts. 
*   **Scalability of Human-in-the-Loop Review Throughput:** We assume that because the AI extraction reduces manual data entry by >95%, the projected volume of `PendingReview` contracts will remain well within the operational capacity of RevOps teams to review and approve within acceptable service level objectives (e.g., <24 hours), even during peak end-of-quarter billing cycles.
*   **User-Friendly ERP/CRM Configuration:** We assume that the complexity of configuring integration mappings (e.g., Chart of Accounts, custom fields) for NetSuite and QuickBooks Online via the RevOps Configuration Portal will be manageable for Finance/RevOps users with minimal specialized training, successfully abstracting away the underlying ERP API complexity.
*   **API Availability:** We assume the documented APIs for Salesforce, HubSpot, NetSuite, QBO, Stripe, and Coinbase Commerce will remain fundamentally stable and will provide at least 6 months' advance notice for any breaking changes or major deprecations during the Phase 1 (Months 0-6) development window.
*   **Regulatory Stasis:** We assume the current regulatory frameworks governing Escrow-as-a-Service APIs and auto-fiat cryptocurrency settlements will remain relatively stable, allowing the Contract Compiler to operate strictly as an orchestration software provider rather than requiring registration as a regulated financial institution.
*   **Team Capacity:** We assume the engineering team possesses the necessary proficiency in Python 3.11, FastAPI, React/TypeScript, and MongoDB Atlas to execute the complex, distributed state-machine logic required for the Event-Driven Entitlement Gateway within the proposed 6-month foundation timeline.

### 4. Contingency Planning

*   **Assumption Invalidation Strategy:** We assume that while these foundational premises hold true today, market or technical conditions may shift. For each critical assumption listed above (e.g., Vertex AI failing to consistently reach the >80% baseline confidence, or API providers issuing 30-day deprecation notices), a documented contingency plan (e.g., shifting to a different foundational LLM model, or mandating structured contract templates via a CRM CPQ integration) SHALL be defined by Product Management and reviewed quarterly, ensuring rapid response if an assumption proves false.
