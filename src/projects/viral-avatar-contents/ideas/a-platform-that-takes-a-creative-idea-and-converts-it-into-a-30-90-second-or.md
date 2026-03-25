---
run_id: abdc1bfa1ed7
status: completed
created: 2026-03-23T12:49:59.613205+00:00
completed: 2026-03-23T14:28:55.332928+00:00
project: "[[viral-avatar-contents]]"
tags: [idea, prd, completed]
---

# A platform that takes a creative idea and converts it into a 30-90 second or ...

> Part of [[viral-avatar-contents/viral-avatar-contents|Viral Avatar Contents]] project

## Original Idea

A platform that takes a creative idea and converts it into a 30-90 second or 5-10 minute video, iterated through a storyboard cycle with unique avatars, automated scene generation, visual feedback during storyboarding, and overall feedback on music and narration. The platform will use open-source tools with no guardrails to support diverse businesses, targeting influencer and traditional marketing, with a pricing model per video.

## Refined Idea

**1. Industry / Domain**
Marketing Technology (MarTech) / AI-Driven Creator Economy and Social Media Content Generation.

**2. Expert Persona**
VP of Marketing Technology & Digital Strategy. I have spent over fifteen years building and scaling content automation platforms for global brands and top-tier influencer networks. I understand the brutal algorithmic realities of modern social media, the non-negotiable requirement for brand safety, and the severe adoption friction that comes with introducing complex new tools to fast-moving creative teams.

**3. Probing the Idea (The Hard Questions)**
*   **Question 1: Who actually wants "no guardrails" and "open-source" for commercial video generation?** You mentioned targeting traditional marketing and influencers with a "no guardrails" open-source approach. Have you considered the catastrophic brand safety risks, copyright infringement liabilities, and deepfake regulations this invites?
*   **Question 2: Why are we focusing on 5-10 minute videos?** The algorithmic reality of TikTok, YouTube Shorts, Instagram Reels, and Threads heavily favors high-retention, short-form content. Why build infrastructure for long-form video when the target audience’s primary growth channels demand hyper-condensed formats? 
*   **Question 3: How do we overcome the initial adoption friction of a complex web-based storyboard UI?** Busy social media managers and creators will not abandon their current workflows to learn a heavy, multi-step web platform just to test an unproven tool. How do we meet them where they already work and prove instant time-to-value?
*   **Question 4: How are we handling multi-channel personalization efficiently?** A script and avatar style that works on LinkedIn will completely fail on TikTok. How does the system adapt a single creative idea into distinct, platform-native formats without forcing the user to manually rewrite everything?

**4. Answering the Questions (Domain Context & Technical Reality)**
*   **Answer 1 (Brand Safety & Tech Stack):** We absolutely must pivot away from a "no guardrails" open-source wild west. To ensure broadcast-quality output and mitigate enterprise liability, we must utilize premium, specialized AI models. We will use HeyGen for photorealistic avatar synthesis, ElevenLabs for flawless voice cloning, and Google Gemini for intelligent script generation. This ensures high-fidelity results while keeping us within safe, commercial-grade API boundaries.
*   **Answer 2 (Format Constraints):** We must strictly limit video generation to 15-60 seconds. This is the sweet spot for TikTok, Shorts, X, and Threads. This constraint not only guarantees we are building for the most viral algorithms on the market, but it also tightly controls our per-video API costs (rendering HeyGen and ElevenLabs economically viable). 
*   **Answer 3 (The Slack MVP):** The Minimal Viable Product must skip the complex website entirely. We will build a Slack-first MVP using CrewAI event listeners. Marketers spend all day in Slack. By allowing a user to drop a simple text idea into a Slack channel and receive a fully rendered video back in minutes, we eliminate adoption friction. The complex backend operations will be decoupled via a robust data layer using FastAPI, MongoDB, and RabbitMQ webhooks.
*   **Answer 4 (CrewAI & Multi-Channel Logic):** We will leverage CrewAI to orchestrate a multi-agent workflow. A user will upload 5-10 pictures and a voice sample to create a personalized avatar for a specific "media channel." When a raw idea is submitted, Gemini-powered agents will rewrite the concept into multiple platform-specific scripts (e.g., a professional tone for X, a high-energy hook for TikTok). The system will generate multiple options, allowing the user to select and finalize the best variation directly within Slack.

***

**5. Refined Product Idea**

The proposed product is a highly automated, AI-driven short-form video generation platform designed specifically for fast-moving social media marketers and influencers. The core problem this platform solves is the massive time and resource bottleneck involved in producing platform-specific, talking-head video content for fragmented social media ecosystems like TikTok, YouTube Shorts, X, and Threads. Instead of a heavy, complex web interface that demands hours of user onboarding, this platform operates on a frictionless Minimal Viable Product model seamlessly integrated directly into Slack, meeting collaborative teams exactly where they already work.

The system is built on a sophisticated, multi-agent architecture utilizing the CrewAI framework. When a user submits a raw creative idea or a simple text prompt into the designated Slack channel, a team of specialized AI agents powered by Google Gemini takes over. These agents iterate on the idea, automatically expanding it into concise, highly engaging scripts optimized strictly for 15-60 second video formats, ensuring alignment with modern social media algorithms that prioritize immediate hooks and high viewer retention. Because a single tone does not work across all networks, the platform allows users to create and manage multiple media channels. The agents autonomously generate tailored variations of the script to suit the distinct audience expectations of each targeted channel, providing multiple media results for the user to review and finalize within the Slack interface.

A major competitive differentiator is the platform's deep, high-fidelity personalization capabilities, moving away from generic stock avatars. Users authenticate via Gmail or standard email to manage their digital assets securely. For each distinct media channel, a user can train a highly personalized avatar by uploading just 5 to 10 reference images alongside a sample audio recording of their voice. The backend utilizes Clip and ViT for advanced vision recognition and asset validation. To synthesize the final output, the platform leverages premium API integrations, relying on ElevenLabs to generate incredibly natural, cloned voiceovers and HeyGen to animate the custom visual avatars with broadcast-quality lip-sync and facial expressions. 

Technically, the product is engineered for maximum scalability and seamless future expansion. It employs a fully decoupled architecture where the underlying data layer is separated from the front-end interfaces via FastAPI REST endpoints and webhooks. As the user interacts with the CrewAI event listener in Slack, background tasks are efficiently managed and queued through RabbitMQ pub/sub mechanisms, with all state, user profiles, and digital asset metadata persistently stored in MongoDB Atlas. This architectural rigor ensures that while the initial MVP relies on Slack for immediate market validation and frictionless user adoption, the platform is perfectly positioned to expand into a full-fledged React and TypeScript web application, delivering rapid, cost-effective, and highly personalized video content at enterprise scale.

## Executive Summary

## Executive Summary

**1. Problem Statement**
In today's algorithmic reality, sustainable growth on platforms like TikTok, YouTube Shorts, X, and Threads demands a high-velocity output of hyper-condensed, platform-specific short-form video content. However, marketing and creative teams face two crippling bottlenecks. First, traditional talking-head video production is highly resource-intensive, requiring hours of scripting, recording, and editing to tailor one message across multiple fragmented networks. Second, attempting to solve this with complex, multi-step web-based AI tools creates massive adoption friction; fast-moving social media managers will not abandon their daily collaborative workflows to learn heavy new software. Furthermore, utilizing "no-guardrails" open-source generation models to cut costs introduces catastrophic brand safety risks, copyright infringement liabilities, and deepfake regulatory exposure.

**2. Target Audience & Key Stakeholders**
*   **Primary User 1: Social Media Manager**
    *   *Pain Point:* Adapting a single content narrative for distinct platform algorithms (e.g., TikTok vs. X) takes hours of manual rewriting and re-editing.
    *   *Goal:* Generate and publish 3-5 distinct, platform-specific video variations from a single text prompt in under 15 minutes.
*   **Primary User 2: Brand Influencer / Creator**
    *   *Pain Point:* Scaling daily video output is bottlenecked by the physical time required to be on-camera, leading to burnout.
    *   *Goal:* Maintain 100% visual and vocal authenticity while producing 15-60 second videos with zero actual filming time.
*   **Key Stakeholders:** VP of Marketing (focused on content ROI/volume), Legal & Compliance (focused on IP and deepfake safeguards), Engineering (focused on architecture scalability), and **IT/Infrastructure Lead** (focused on system operational health, network security, and enterprise integration policies).

**3. Proposed Solution & Key Differentiators**
We are building a highly automated, AI-driven short-form video generation platform structured as a frictionless, Slack-first Minimal Viable Product (MVP). By integrating the interface directly into Slack, we meet collaborative teams exactly where they already work.

The system is orchestrated by a multi-agent architecture utilizing the **CrewAI framework**. When a user drops a raw idea into Slack, **Google Gemini-powered agents** automatically iterate and expand the concept into multiple highly engaging, 15-60 second scripts tailored to user-defined media channels. Users securely authenticate via email to train personalized avatars by uploading 5-10 reference images and a voice sample. Using Clip and ViT for advanced vision validation, the backend orchestrates premium APIs: **ElevenLabs** for flawless voice cloning and **HeyGen** for photorealistic, broadcast-quality avatar animation. 

*   **Zero Adoption Friction:** Eliminates web UI onboarding by running the entire generation, review, and publishing loop natively in Slack.
*   **Algorithmic Constraint by Design:** Strict enforcement of 15-60 second limits optimizes for viral algorithms while capping per-video API costs.
*   **Enterprise-Grade Brand Safety:** Rejects open-source liabilities in favor of bounded, commercial-grade AI models (HeyGen, ElevenLabs, Gemini).

**4. Core Functional Requirements (MVP Scope)**
To deliver the end-to-end Slack workflow, the system must support the following explicit user capabilities:
1.  **Account Management:** Users can securely authenticate and create accounts via standard Email/Gmail OAuth.
2.  **Channel Configuration:** Users can define specific "Media Channels" (e.g., "Company TikTok", "Personal X") and set target audience tones.
    *   **2.1. Social Media Account Linking:** Users can securely link and authorize their external social media accounts (e.g., TikTok, YouTube, X, Threads) via OAuth to a specific Media Channel, granting necessary permissions for direct video publishing. The system will automatically manage token refreshes and alert users to expired authorizations.
3.  **Avatar & Voice Training:** Users can upload 5-10 images and a voice sample to generate a highly personalized digital clone linked to a specific channel.
4.  **Idea Submission:** Users can trigger the generation pipeline by submitting a text idea via a Slack slash command or bot mention.
5.  **Multi-Script Review:** The system generates 2-3 script variations via Gemini. Users can review, edit, and select the winning script via Slack Block Kit buttons.
6.  **Video Rendering & Approval:** The system synthesizes the final video using HeyGen/ElevenLabs. Users receive the rendered video in Slack for final approval.
7.  **Direct Publishing:** Users can trigger a webhook to publish the approved video to the designated social network directly from the Slack interface.
8.  **Asset Management:** Users can view, delete, or retrain their avatars and voice profiles.

**5. Non-Functional Requirements (Targets)**
*   **Performance:** Script generation (3 variations) must complete in <30 seconds. Video rendering (for a 60-second clip) must complete in <5 minutes. Slack interactive responses must occur in <2 seconds.
*   **Availability:** 99.5% uptime for the core asynchronous message processing pipeline (RabbitMQ/FastAPI).
*   **Scalability:** The system must support up to 100 concurrent video generation requests without dropping Slack webhook events.
*   **Security:** All user uploads (images, voice) and generated assets must be encrypted at rest (AES-256 via MongoDB Atlas) and in transit (TLS 1.2+).
*   **Cost Efficiency:** Average API execution cost (Gemini + ElevenLabs + HeyGen) must remain strictly below $1.00 per finalized 60-second video.

**6. Edge Cases & Error Handling Strategy**
*   **API Failures/Timeouts:** If an external dependency (HeyGen, ElevenLabs) times out, the RabbitMQ worker will queue a retry with exponential backoff. The user will receive a graceful Slack update ("Video rendering delayed by vendor, retrying...").
*   **Input Quality Rejection:** If uploaded avatar images fail Clip/ViT quality thresholds (e.g., poor lighting, multiple faces), the system will immediately reject the upload with specific, actionable feedback in Slack before incurring generation costs.
*   **Content Policy Violations:** Gemini agents are instructed with strict guardrails. Ideas flagged for NSFW, hate speech, or deepfake policy violations will immediately halt the workflow and notify the user of the policy breach.

**7. Analytics & Success Tracking**
System instrumentation will log explicit telemetry events to measure adoption and efficiency, including:
*   `user_authenticated` and `channel_configured` (to track WAU and onboarding success).
*   `idea_submitted` and `script_variation_selected` (to track Gemini output utility).
*   `video_render_started`, `video_render_completed` (with payload tracking total API cost in USD), and `video_render_failed` (with detailed error taxonomy).
*   `publish_to_social_success` (to track end-to-end completion rate).

**8. Key Dependencies, Risks & Mitigations**
*   **Dependency: Core Generative APIs (Slack, Google Gemini, HeyGen, ElevenLabs).**
    *   *Risk:* Vendor API changes, rate limiting, or pricing surges.
    *   *Mitigation:* Implement an abstraction layer in the backend data mapping to allow swapping of LLM or TTS providers if necessary. Strictly cache standard outputs.
*   **Dependency: `yt-dlp` (Internal Reference Tool).**
    *   *Role:* Used internally by the backend data processing layer to download public reference videos strictly for AI agent context parsing and content style analysis (not for direct output synthesis).
    *   *Risk:* Potential IP infringement claims, legal complexities, and platform-level IP blocking or rate-limiting.
    *   *Mitigation:* Enforce strict internal usage policies ensuring downloaded media is instantly purged from memory post-analysis, never exposed to the end-user, and never used in generated output. Implement robust proxy rotation and rate-limit compliance to prevent IP bans.
*   **Risk (Market/User):** Users may find the Slack interface too limiting for complex video edits.
    *   *Mitigation:* Position the MVP strictly for rapid, single-take "talking head" formats. Future web UI expansion is supported by the decoupled FastAPI backend.
*   **Risk (Regulatory):** Generating personalized avatars scales the risk of deepfake misuse.
    *   *Mitigation:* Require authenticated accounts, enforce strict Terms of Service, watermark outputs if required by regional law, and limit voice cloning to user-provided and verified samples.

**9. Business Impact & Expected ROI**
*   **Production Velocity:** Decrease the end-to-end production time of platform-specific talking-head videos from an average of 48 hours to under 10 minutes.
*   **User Adoption:** Achieve greater than 75% Weekly Active User (WAU) retention among onboarded creative teams within the first 30 days of the Slack MVP rollout.
*   **Risk Mitigation:** Achieve a 0% incidence rate of brand safety violations, secured through bounded commercial APIs and strict input validation.

## Executive Product Summary

# Executive Product Summary: The Digital Ubiquity Engine

## 1. The Real Problem: The "Ubiquity Tax" on Human Creativity
When someone says, "we need an AI video generator," they are answering the wrong prompt. The actual problem isn't that rendering video is slow. The problem is that modern brand relevance demands absolute ubiquity, and ubiquity destroys human creators. 

To grow today, a creator or brand must maintain a high-velocity output of platform-specific, short-form video (15-60 seconds) across TikTok, YouTube Shorts, X, and Threads. This imposes a massive "Ubiquity Tax"—the soul-crushing hours spent scripting, lighting, filming, and editing variations of the exact same core message to appease different algorithms. 

Attempting to solve this with complex, web-based AI dashboards forces social media managers to abandon their flow state to learn heavy new software. Attempting to solve this with open-source "no guardrails" AI introduces catastrophic brand safety risks and deepfake liabilities. 

**The real need:** Creators and marketers need a way to instantly translate a passing thought into a high-fidelity, multi-platform content empire without ever turning on a camera, leaving their primary workspace, or risking their brand's reputation.

## 2. The 10-Star Product Vision
We are not building a video editing tool. We are building a **Digital Ubiquity Engine**. 

We are collapsing the 48-hour production lifecycle into a 5-minute asynchronous background task, accessible from the place teams already live: **Slack**. By leveraging the **CrewAI framework**, we are creating an autonomous production studio. A user drops a raw, unpolished idea into a Slack channel. In the background, **Google Gemini-powered agents** dissect the idea, cross-reference it with trending formats (safely parsed via internal, ephemeral `yt-dlp` reference streams), and rewrite it into tailored, 15-60 second scripts optimized for distinct algorithmic "Media Channels" (e.g., "Company TikTok" vs. "Founder's X").

This requires uncompromising taste and zero tolerance for the uncanny valley. We reject generic stock models. Through a secure email authentication flow, users train a deeply personalized avatar (validated instantly by **Clip + ViT** vision models). We orchestrate premium, commercial-grade APIs—**ElevenLabs** for flawless voice cloning and **HeyGen** for photorealistic, broadcast-quality animation. 

This is magic. It is 100% visual and vocal authenticity with 0% filming time, heavily bounded by enterprise-grade safety guardrails.

## 3. The Ideal User Experience ("This is exactly what I needed")
Imagine Sarah, a VP of Marketing. She’s waiting in line for coffee when she reads an industry news headline. She opens the Slack app on her phone.

She types: `/generate-video Idea: The new SaaS pricing models are basically just cable bundles all over again. Give me a hot take for TikTok and a professional breakdown for X.`

Instantly, the CrewAI event listener catches the webhook. Within 15 seconds, Sarah’s Slack pings with a beautifully formatted Block Kit message containing two distinct scripts. The TikTok script is punchy, designed for a 15-second loop. The X script is analytical and structured for a 45-second retention drop. 

She clicks "Approve Both." 

A **RabbitMQ** worker takes over, orchestrating the **FastAPI** backend to render the videos using her pre-trained **HeyGen** avatar and **ElevenLabs** voice profile. Five minutes later, she receives the rendered 4K videos directly in Slack, alongside a button: **"Publish to Linked Accounts."** She taps it. Before her coffee is even poured, she has natively published two high-production-value, platform-specific videos to two different networks. 

She thinks: *"I just produced a half-day's worth of content while standing in line."*

## 4. Delight Opportunities (The "Oh Nice, They Thought of That" Features)
To elevate this from a utility to a beloved product, we must engineer delight into the micro-interactions. Here are 4 low-effort, high-impact features (<30 mins each to implement) that prove we understand our users:

*   **Zero Silent Failures (The "Ugly Lighting" Catcher):** When a user uploads their 5-10 avatar training images, our **Clip + ViT** layer evaluates them instantly. Instead of a generic "Failed," the Slack bot replies: *"I can't use image #3 because the lighting is too harsh on the left side of your face. Upload one more facing a window and we’re good to go!"*
*   **The 3-Second Audio Hook Preview:** Waiting 5 minutes for a HeyGen render can feel like a black box. The moment the Gemini script is approved, the system uses ElevenLabs to generate just the first 3 seconds of audio (the hook) and drops it in Slack. Users hear their own cloned voice reading the hook *immediately* while the video renders in the background.
*   **Vibe-Matched Slack Reactions:** When CrewAI agents generate the scripts, the bot automatically reacts to the message with a platform-specific emoji (🔥 for TikTok, 👔 for X/LinkedIn, 🧵 for Threads) so the user instantly visually categorizes the content variations without reading the headers.
*   **Proactive OAuth Token Health:** Nothing is worse than hitting "Publish" and realizing your TikTok token expired. Our backend cron job checks OAuth token health daily. If a token expires in 48 hours, the bot sends a quiet DM: *"Your YouTube Shorts connection expires tomorrow. Click here to re-authorize so your next video doesn't get stuck."*

## 5. Scope Mapping: The 12-Month Trajectory
We optimize for the 6-month future by building a decoupled architecture today. **MongoDB Atlas** stores all persistent states, **FastAPI** handles all routing, and **RabbitMQ** ensures we never drop a webhook if a user spams the system. 

*   **Current State:** Fragmented, expensive manual video production requiring physical cameras, multiple software subscriptions, and massive context-switching.
*   **This Plan (The Slack MVP):** The "Frictionless Ingestion" phase. We bypass web UI onboarding entirely. Users authenticate, configure channels, generate scripts via CrewAI + Gemini, render via HeyGen + ElevenLabs, and publish—100% within Slack. We prove time-to-value instantly.
*   **6-Month Horizon:** Deep Analytics & Approval Workflows. We introduce multi-seat approval chains in Slack (Creator drafts -> Legal approves -> Publisher posts) with deep API cost-tracking per user.
*   **12-Month Ideal:** The Full **React + TypeScript** Command Center. The Slack MVP remains the frictionless daily driver for idea ingestion, but power users can now log into a gorgeous web dashboard to manage massive asset libraries, view cross-platform engagement analytics, seamlessly swap foundational LLMs (via our abstraction layer), and visually orchestrate complex CrewAI flows.

## 6. Business Impact & Success Criteria
This product is positioned to capture the enterprise MarTech and high-tier Creator Economy markets by solving the friction of creation and the liability of AI generation. By enforcing strict algorithmic constraints (15-60 seconds) and bounded commercial models, we guarantee virality-optimized output while locking our unit economics at <$1.00 per generated video.

**We will know we are successful when:**
1.  **Velocity Multiplier:** The end-to-end production time from "idea" to "published platform-native video" drops from an average of 48 hours to strictly under 10 minutes.
2.  **Frictionless Retention:** We achieve >75% Weekly Active User (WAU) retention in the first 30 days. High retention proves that operating natively in Slack effectively eradicated the UI adoption barrier.
3.  **Zero-Defect Brand Safety:** We achieve exactly 0% incidence of deepfake or brand safety policy violations. Our closed-loop architecture ensures that Gemini's guardrails and MongoDB's AES-256 encryption protect all enterprise IP flawlessly.

## Engineering Plan

# Engineering Plan: The Digital Ubiquity Engine

## 1. Architecture Overview

### 1.1 System Boundaries & Component Map

The system utilizes an event-driven, decoupled architecture prioritizing asynchronous processing. The ingestion boundary is exclusively the Slack Event API. The data boundary is encapsulated by FastAPI and MongoDB Atlas. The compute boundary is split into CPU-bound tasks (FastAPI, Webhooks) and long-running GPU/AI-bound tasks orchestrated via RabbitMQ workers.

```text
                        +---------------------------------------+
                        |           SLACK WORKSPACE             |
                        |  (Event Subscriptions & Interactivity)|
                        +-------------------+-------------------+
                                            |
                                 [Slack Event Webhooks]
                                            |
+-----------------------------------------------------------------------------------+
|                            FASTAPI (API / WEBHOOK LAYER)                          |
|   +-------------------+  +-------------------+  +-----------------------------+   |
|   | Slack Integrator  |  |  Data Repository  |  | External Webhook Handlers   |   |
|   | (Auth, Route,     |  |  (State Checks,   |  | (HeyGen, ElevenLabs)        |   |
|   |  Idempotency)     |  |   Validation)     |  |                             |   |
|   +---------+---------+  +---------+---------+  +--------------+--------------+   |
+-------------|----------------------|---------------------------|------------------+
              |                      |                           |
        [Publish Msg]          [Read/Write]                [Update State]
              |                      |                           |
+-------------v-------+    +---------v---------+   +-------------v------------------+
|   RABBITMQ CLUSTER  |    |   MONGODB ATLAS   |   |  OBSIDIAN (Knowledge Graph)    |
| - Validation Queue  |    | - Users, Channels |   | - Base tone rules              |
| - CrewAI Queue      |    | - Assets, Avatars |   | - Platform constraints         |
| - Render Queue      |    | - Ideas, Renders  |   | - Dynamic RAG chunks           |
| - Dead Letter Queue |    +-------------------+   +--------------------------------+
+-------------+-------+              |
              |                      | [State Reads]
+-------------v----------------------v----------------------------------------------+
|                            WORKER POOL (PYTHON/CELERY)                            |
|                                                                                   |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  | Asset Validator    |   | CrewAI Orchestrator   |   | Render Orchestrator    |  |
|  | (Clip + ViT)       |   | (Gemini, Agents,      |   | (API Integrations,     |  |
|  |                    |   |  yt-dlp, RAG lookup)  |   |  S3 Transfers)         |  |
|  +---------+----------+   +-----------+-----------+   +-----------+------------+  |
+------------|--------------------------|---------------------------|---------------+
             |                          |                           |
      [Validate Images]        [Generate Scripts]           [Generate Video]
             |                          |                           |
+------------v-----------+ +------------v-----------+ +-------------v---------------+
| LOCAL ML (Clip + ViT)  | | GEMINI API (VertexAI)  | | HEYGEN & ELEVENLABS APIs    |
+------------------------+ +------------------------+ +-----------------------------+
```

### 1.2 Technology Stack Rationale
*   **MongoDB Atlas:** Document structure is ideal for fluid AI metadata and nested agent execution logs. Provides TTL indexes for transient data and ACID compliance at the document level for state transitions.
*   **FastAPI:** Async native. Perfect for concurrent webhook ingestion and rapid I/O.
*   **RabbitMQ:** Essential for decoupling Slack's 3-second acknowledgement window from 5-minute video renders. Guarantees message delivery and provides Dead Letter Queues (DLQ) for exponential backoff on API rate limits.
*   **CrewAI:** Provides deterministic agent orchestration with built-in tool execution (`yt-dlp` injection, Obsidian RAG lookup) while preventing agent infinite loops.

### 1.3 Data Flow Diagrams

**Happy Path (Content Generation):**
```text
Slack Msg -> FastAPI (ACK 200) -> DB (Insert Idea) -> RabbitMQ (Pub Queue)
  -> Worker (Sub Queue) -> CrewAI + Gemini (Generate) -> DB (Insert Scripts)
  -> FastAPI (Post Block Kit to Slack) -> User (Clicks Approve)
  -> FastAPI (Update DB) -> RabbitMQ (Pub Render) -> Worker (11Labs -> HeyGen)
  -> DB (Update Render State) -> HeyGen Webhook -> FastAPI -> DB (Completed)
  -> FastAPI (Post Video URL to Slack)
```

**Error Path (HeyGen Rate Limit / Timeout):**
```text
Worker -> HeyGen API (429 Too Many Requests)
  -> Worker catches exception -> DB (Increment retry_count)
  -> RabbitMQ (NACK -> DLQ with 5m TTL)
  -> DLQ expires -> RabbitMQ (Re-queue to Main)
  -> Worker -> HeyGen API (Success)
  ... [If max_retries hit] ...
  -> DB (Update Render State -> Failed) -> FastAPI (Post Error Alert to Slack)
```

---

## 2. Component Breakdown

### 2.1 Multi-Channel Profile Provisioning
*   **Purpose:** Maps Slack identities to logical `MediaChannels`. Governs the tone rules for LLM generation.
*   **Interfaces:** Slack Command (`/create-channel`), DB (`User`, `MediaChannel`).
*   **State Machine (`MediaChannel`):**
```text
         [User: Create]
               |
               v
          +---------+  [User: Archive]  +----------+
          |         |------------------>|          |
          | ACTIVE  |                   | ARCHIVED |
          |         |<------------------|          |
          +---------+  [User: Restore]  +----------+
            |     ^
            |     | (Rejected: Active -> Active)
            +-----+
```

### 2.2 Digital Asset Validation & Avatar Pipeline
*   **Purpose:** Validates human faces/audio inputs securely before provisioning external API twins.
*   **Interfaces:** Slack S3 Presigned URL generator, Local Clip+ViT Worker, ElevenLabs/HeyGen Setup APIs.
*   **State Machine (`AvatarModel`):**
```text
   [Upload]      [Trigger >= 5 img, 1 aud]     [Clip/ViT >= 0.85]          [Webhook Success]
 +---------+      +-------------------+        +------------+              +-------+
 |  DRAFT  |----->| PENDING_VALIDATION|------->|  TRAINING  |------------->| READY |
 +---------+      +-------------------+        +------------+              +-------+
                       |                             |                         |
     [Clip/ViT < 0.85] |                             | [API Error/Timeout]     | (Rejected:
                       v                             v                         |  Ready -> Training)
                  +-----------------------------------------+                  |
                  |                  FAILED                 |<-----------------+
                  +-----------------------------------------+
```

### 2.3 AI Script Generation & CrewAI Workflow
*   **Purpose:** Orchestrates multi-agent translation of raw ideas into distinct, platform-optimized scripts (15-60s limit).
*   **Interfaces:** CrewAI Orchestrator, Obsidian (Markdown files via RAG tool), `yt-dlp` tool, Gemini API.
*   **State Machine (`ContentIdea`):**
```text
  [Slack Msg]     [Worker ACKs]         [CrewAI Success]         [User Approves]
 +-----------+     +------------+         +--------+               +----------+
 | SUBMITTED |---->| GENERATING |-------->| REVIEW |-------------->| APPROVED |
 +-----------+     +------------+         +--------+               +----------+
                         |                    |                          |
        [CrewAI Failure] |                    | [User Cancels]           | (Fires video.render msg)
                         v                    v                          v
                     +-------------------------------+
                     |           REJECTED            |
                     +-------------------------------+
```

### 2.4 Asynchronous Avatar Rendering Engine
*   **Purpose:** Connects finalized scripts to ElevenLabs (TTS) and HeyGen (Video) sequentially.
*   **Interfaces:** ElevenLabs API, HeyGen API, S3 (Transient Audio Storage).
*   **State Machine (`VideoRender`):**
```text
  [Approved Msg]  [Worker Starts]         [Audio on S3]            [HeyGen Webhook]
 +--------+      +-------------------+     +-----------------+      +-----------+
 | QUEUED |----->| SYNTHESIZING_AUDIO|---->| RENDERING_VIDEO |----->| COMPLETED |
 +--------+      +-------------------+     +-----------------+      +-----------+
                        |                          |
    [11Labs Max Retry]  |                          | [HeyGen Max Retry/Timeout]
                        v                          v
                   +------------------------------------+
                   |               FAILED               |
                   +------------------------------------+
```

---

## 3. Implementation Phases

### Epic 1: Foundation & Data Layer (Size: M)
*   **Story 1.1:** Initialize FastAPI project with structured logging, configuration management, and MongoDB Atlas motor (async) driver.
*   **Story 1.2:** Implement database models and strict indexes for `User`, `MediaChannel`, `AvatarModel`, `DigitalAsset`, `ContentIdea`, `ScriptVariation`, and `VideoRender`.
*   **Story 1.3:** Provision RabbitMQ exchanges, main queues, and Dead Letter Queues (DLQs). Create abstract base worker class.
*   **Story 1.4:** Implement Slack Event API authentication, signature validation middleware, and idempotency lock (Redis or Mongo TTL based on `slack_event_id`).

### Epic 2: Slack Integration & Multi-Channel Setup (Size: L)
*   **Story 2.1:** Implement `/setup-channel` Slack slash command listener and intent-parsing agent (Gemini) to generate `MediaChannel` records.
*   **Story 2.2:** Build Slack interactive Block Kit builder for listing, editing, and archiving `MediaChannels`.
*   **Story 2.3:** Implement DB state guards preventing a user from archiving their final `Active` channel.
*   **Story 2.4:** Implement proactive OAuth/Token health cron job for connected outputs (e.g., mock YouTube connection warnings).

### Epic 3: Asset Validation & Avatar Pipeline (Size: L)
*   **Story 3.1:** Implement S3 presigned URL generation for secure Slack file uploads via `/upload-asset`.
*   **Story 3.2:** Build Clip + ViT worker to consume S3 images, calculate facial consistency score, and transition `AvatarModel` state.
*   **Story 3.3:** Handle `< 0.85` confidence scores by routing specific "Zero Silent Failures" diagnostic messages back to the user's Slack thread.
*   **Story 3.4:** Integrate external ElevenLabs Voice Clone API and HeyGen Avatar Training API, exposing webhook endpoints for async success updates.

### Epic 4: Script Engine & CrewAI Integration (Size: XL)
*   **Story 4.1:** Implement the `ContentIdea` webhook listener to capture raw prompts and push to the `crewai.generate` queue.
*   **Story 4.2:** Build the CrewAI pipeline: Master Expander Agent and N Channel Adapter Agents (dynamically scaled based on user's `Active` channels).
*   **Story 4.3:** Integrate Obsidian RAG capabilities as a CrewAI Tool for dynamic tone lookup.
*   **Story 4.4:** Integrate `yt-dlp` as a CrewAI tool to fetch reference video pacing metadata if a URL is provided in the prompt.
*   **Story 4.5:** Implement length constraint middleware (15-60s -> ~40-150 words). Reject and trigger CrewAI retry loop if violated.
*   **Story 4.6:** Build Slack Block Kit interface for rendering script variations with "3-Second Audio Hook Preview" integration.

### Epic 5: Asynchronous Render Engine (Size: XL)
*   **Story 5.1:** Implement worker consuming from `video.render` queue. Transmit `scriptContent` to ElevenLabs and stream output to S3.
*   **Story 5.2:** Transmit S3 audio URL and `heyGenAvatarId` to HeyGen rendering API. Implement robust exponential backoff for 429s.
*   **Story 5.3:** Create `/webhooks/heygen/video-render` listener to transition `VideoRender` state to `Completed`.
*   **Story 5.4:** Implement cron watchdog to mark `RenderingVideo` objects as `Failed` if unchanged for > 30 minutes.
*   **Story 5.5:** Push final MP4 URL and "Publish to Connected Networks" mock-action button to Slack.

---

## 4. Data Model

**Database:** MongoDB Atlas
**Design Pattern:** Denormalized reads where possible, strict reference IDs for stateful objects.
**Shared Audit Fields:** All collections must include `createdAt` (Date), `updatedAt` (Date).

*   **Users Collection**
    *   `_id`: ObjectId
    *   `slackId`: String (Unique Index)
    *   `email`: String (Unique Index)
    *   `isActive`: Boolean
*   **MediaChannels Collection**
    *   `_id`: ObjectId
    *   `userId`: ObjectId (Ref: Users)
    *   `platformType`: Enum `[TikTok, YouTubeShorts, X, Threads, LinkedIn]`
    *   `channelName`: String
    *   `tonePrompt`: String
    *   `status`: Enum `[Active, Archived]` (Index)
    *   *Constraint*: Compound Unique Index on `(userId, channelName)`.
*   **AvatarModels Collection**
    *   `_id`: ObjectId
    *   `userId`: ObjectId (Ref: Users)
    *   `heyGenAvatarId`: String (Sparse Index)
    *   `elevenLabsVoiceId`: String (Sparse Index)
    *   `status`: Enum `[Draft, PendingValidation, Training, Ready, Failed]`
    *   `validationErrors`: Array[String]
*   **DigitalAssets Collection**
    *   `_id`: ObjectId
    *   `avatarModelId`: ObjectId (Ref: AvatarModels)
    *   `assetType`: Enum `[Image, Audio]`
    *   `s3Key`: String
    *   `fileSizeKb`: Int32
    *   `isValidated`: Boolean
*   **ContentIdeas Collection**
    *   `_id`: ObjectId
    *   `userId`: ObjectId (Ref: Users)
    *   `rawPrompt`: String
    *   `referenceVideoUrl`: String (Optional)
    *   `status`: Enum `[Submitted, Generating, Review, Approved, Rejected]` (Index)
*   **ScriptVariations Collection**
    *   `_id`: ObjectId
    *   `ideaId`: ObjectId (Ref: ContentIdeas)
    *   `channelId`: ObjectId (Ref: MediaChannels)
    *   `scriptContent`: String
    *   `estimatedDurationSec`: Int32
    *   `isSelected`: Boolean
    *   *Constraint*: Compound Unique Index on `(ideaId, channelId)`.
*   **VideoRenders Collection**
    *   `_id`: ObjectId
    *   `scriptId`: ObjectId (Ref: ScriptVariations) (Unique Index)
    *   `avatarModelId`: ObjectId (Ref: AvatarModels)
    *   `status`: Enum `[Queued, SynthesizingAudio, RenderingVideo, Completed, Failed]` (Index)
    *   `finalVideoUrl`: String
    *   `retryCount`: Int32

---

## 5. Error Handling & Failure Modes

| Component / Dependency | Failure Mode | Classification | Handling Strategy |
| :--- | :--- | :--- | :--- |
| **Slack Event Webhooks** | Duplicate event delivery due to timeout | Minor | Fast-fail middleware using MongoDB `slack_event_id` unique index (TTL 24h). Discard duplicates, return 200 OK immediately. |
| **CrewAI + Gemini API** | Context window exceeded or hallucination | Major | Try/catch block in worker. Re-queue message (max 2 retries). If max retries hit, state -> `Rejected`. DM user: "Idea was too complex for generation. Try simplifying." |
| **Clip + ViT Worker** | Out of Memory (OOM) / GPU Failure | Critical | Use process-level circuit breakers. Message returns to queue. Trigger PagerDuty alert if queue depth > 50. |
| **ElevenLabs API** | 429 Rate Limit / 503 Unavailable | Major | Dead Letter Queue (DLQ). Exponential backoff: 5s, 30s, 2m, 10m. Max retries: 5. State remains `SynthesizingAudio`. |
| **HeyGen API Webhook** | Webhook dropped / Never received | Critical | Background Cron Watchdog runs every 5 minutes. Queries `VideoRenders` where `status=RenderingVideo` and `updatedAt < (now - 35m)`. Updates state to `Failed` and alerts user. |
| **`yt-dlp` tool** | Target video deleted or platform blocked IP | Minor | Tool catches exception gracefully. Returns empty context to CrewAI. Agent proceeds with `rawPrompt` only. Logs warning to observability stack. |

---

## 6. Test Strategy

### 6.1 Test Pyramid
1.  **Unit Tests (70% coverage requirement):**
    *   *State Machine Transitions*: Explicitly test all invalid state transitions (e.g., asserting `Active -> Active` raises an exception).
    *   *AI Constraints*: Test the word-count-to-duration estimation logic.
    *   *CrewAI Formatting*: Mock LLM output to ensure JSON parsing and schema extraction are flawless.
2.  **Integration Tests (20% coverage requirement):**
    *   *Data Layer*: Test compound indexes and constraints (e.g., preventing duplicate `ScriptVariations` for the same channel).
    *   *API Contracts*: Assert HeyGen/ElevenLabs incoming webhook schemas correctly map to internal DB updates and HMAC signatures are validated.
3.  **End-to-End Tests (10% coverage requirement):**
    *   Mock Slack POST -> Trigger Queue -> Mock Worker (bypassing AI logic) -> Output Block Kit generation.

### 6.2 Critical Paths (Must not deploy if failing)
*   User Slack authentication flow.
*   Validation logic preventing >60-second scripts from reaching expensive HeyGen endpoints.
*   Idempotency lock on Slack webhooks.

---

## 7. Security & Trust Boundaries

### 7.1 Attack Surface Analysis
*   **Slack Webhooks:** Vulnerable to spoofing. *Mitigation*: All inbound requests must validate the `X-Slack-Signature` header using the signing secret.
*   **HeyGen Webhooks:** Vulnerable to state manipulation. *Mitigation*: Validate HMAC payload signatures.
*   **Prompt Injection:** Users inputting raw ideas designed to jailbreak the Gemini prompt into violating brand safety. *Mitigation*: The CrewAI prompt explicitly defines boundaries. `yt-dlp` ingested transcripts are heavily sanitized before being injected into the LLM context.
*   **S3 Presigned URLs:** Vulnerable to malicious file uploads. *Mitigation*: URLs strict TTL of 15 minutes. Restricted by MIME type and strict bucket policies maxing out at 50MB.

### 7.2 Data Classification
*   **PII**: User emails, Avatar Voice Profiles, Facial Images.
    *   *Handling*: Encrypted at rest (MongoDB Atlas AES-256). S3 buckets block public access.
*   **Enterprise IP**: Generated Scripts, Brand Tone Prompts.
    *   *Handling*: Tenant isolation enforced strictly at the database query level (`where userId = ?`).

---

## 8. Deployment & Rollout

### 8.1 Deployment Sequence
1.  **Phase 1:** Provision Infrastructure (Terraform) -> VPC, MongoDB Atlas cluster, RabbitMQ (Amazon MQ), S3 buckets, VertexAI IAM roles.
2.  **Phase 2:** Deploy FastAPI (API/Webhook layer) to container orchestration (ECS / EKS). Connect Slack Event subscriptions.
3.  **Phase 3:** Deploy Python Worker Pool. Establish connection to main RabbitMQ exchange.
4.  **Phase 4:** Migrate Obsidian RAG state to persistent volume accessible by workers.

### 8.2 Rollback Plan
*   *Application Layer*: Blue/Green deployment strategy. If error rates (5xx) exceed 2% within 5 minutes post-deploy, instantly failover traffic to the Blue environment.
*   *Data Layer*: Database migrations must be forward-compatible. Never drop columns/fields until the *subsequent* release.
*   *Worker Layer*: Stop consuming queues immediately, drain inflight tasks, deploy `N-1` image, resume queues.

---

## 9. Observability

### 9.1 Logging Schema
Structured JSON logging is mandatory. Every log entry must include:
*   `trace_id`: Generated at Slack webhook ingestion and passed via RabbitMQ message headers to all subsequent workers.
*   `user_id`: Sourced from MongoDB upon auth resolution.
*   `component`: (e.g., `CrewAI_Orchestrator`, `HeyGen_Webhook`).

### 9.2 Metrics & Alerting (Prometheus / Grafana)
*   **Cost Metrics:** Daily aggregations of HeyGen credits used and Gemini tokens consumed per tenant. Alert if daily burn rate > $X.
*   **Performance Metrics:** CrewAI generation time (P95). Video rendering total duration (P95).
*   **Failure Metrics:** Rate of Dead Letter Queue (DLQ) messages. Trigger Critical Page if DLQ ingestion > 10 msgs/minute.

### 9.3 Debugging Guide for Common Issues
*   *Symptom*: Renders stuck in `RenderingVideo` state.
    *   *Action*: Check HeyGen API status page. Verify webhook URL is correctly registered in HeyGen dashboard. Check worker logs for failed payload deserialization.
*   *Symptom*: User reports "CrewAI failed to generate script".
    *   *Action*: Search logs by `trace_id`. Identify if Gemini returned a rate limit, or if `yt-dlp` tool crashed due to a bad reference link blocking the agent loop.

## Problem Statement

**1. The Current State: The "Ubiquity Tax" on Creative Teams**
In the modern Marketing Technology (MarTech) landscape, the algorithmic reality of platforms like TikTok, YouTube Shorts, X, and Threads demands a relentless, high-velocity output of hyper-condensed (15-60 second) video content. To maintain brand relevance and sustainable growth, creators and marketing teams can no longer publish a single video across all networks. Each platform requires unique pacing, distinct tonal hooks, and specific narrative structures. Currently, producing this multi-channel output requires a massive, manual 48-hour production lifecycle involving scripting variations, setting up physical lighting, filming multiple takes, and editing distinct assets. This creates a severe "Ubiquity Tax"—a crippling operational bottleneck that consumes creative bandwidth, bloats marketing budgets, and ultimately leads to creator burnout. 

**2. The Pain Points: Friction, Liability, and the Uncanny Valley**
While AI video generation exists in the market, current solutions fail to address the realities of fast-moving enterprise and influencer workflows due to three distinct frictions:

*   **Adoption Friction via Complex UI:** Existing AI video platforms force social media managers to abandon their daily collaborative flow states (e.g., Slack) to learn heavy, multi-step web dashboards. This high barrier to entry results in low user adoption, as teams will not disrupt established workflows merely to test an unproven tool.
*   **The Uncanny Valley of Inauthentic Avatars:** Solutions that rely on generic stock avatars or low-fidelity voice cloning fail the authenticity test required by modern social media audiences. Furthermore, even personalized avatar generation, if not executed with premium models and meticulous validation, can inadvertently introduce its own "uncanny valley" effect—resulting in immediate algorithmic suppression and a destruction of viewer trust.
*   **Catastrophic Enterprise Risk:** Attempts to cut costs by utilizing "no-guardrails," open-source AI models introduce unacceptable enterprise liabilities. These unmanaged models expose brands to catastrophic brand safety risks, copyright infringement lawsuits, and severe deepfake regulatory violations.

**3. Impact Quantification**
The failure to efficiently generate high-fidelity, platform-specific content results in measurable business losses. Brand networks are restricted to publishing 1-2 generic videos a week instead of the algorithmically demanded 10+ tailored variations. This directly suppresses organic reach, reduces return on ad spend (ROAS) due to creative fatigue, and increases the churn risk of high-tier creators who cannot sustain the physical demands of constant on-camera production.

**4. Why Now?**
The convergence of hyper-fragmented social media algorithms and the rapid maturation of premium, bounded AI models creates an immediate market window. Brands are desperate for a solution that collapses the 48-hour production cycle into minutes, but they absolutely require a frictionless interface and commercial-grade legal safeguards to protect their IP and user trust. Delivering this capability directly into the communication channels where teams already live (Slack) represents a critical opportunity to capture the enterprise MarTech and Creator Economy markets.

## User Personas

**1. Persona 1: Sarah, The Strategic Leader (VP of Marketing / Digital Strategy)**

*   **Background & Role:** Sarah manages a multi-million dollar marketing budget for a mid-to-large B2B SaaS company. She oversees a team of content creators, social media managers, and paid acquisition specialists. She is ultimately responsible for the brand's digital ROI and reputation.
*   **Goals:**
    *   Achieve algorithmic ubiquity across major platforms (TikTok, X, LinkedIn, YouTube Shorts) without linearly scaling headcount or production budgets.
    *   Maintain absolute brand safety, ensuring all AI-generated content adheres to strict corporate guidelines and avoids copyright/deepfake liabilities.
    *   Reduce the time-to-market for reactionary content (e.g., responding to industry news) from days to hours.
*   **Pain Points:**
    *   **The "Ubiquity Tax":** Her team spends 80% of their time on mechanical production tasks (filming, lighting, multi-platform editing) and only 20% on actual creative ideation.
    *   **Adoption Friction:** She has purchased heavy "all-in-one" AI video dashboards before, but her fast-moving team abandons them because they disrupt their daily, Slack-centric communication flow.
    *   **Quality vs. Cost:** She refuses to use cheap, open-source AI models that produce "uncanny valley" results, but she cannot afford to hire external agencies for every 15-second TikTok video.
*   **Usage Context:** Daily power user, but exclusively via Slack. She expects to drop a raw idea into a channel between meetings, review the generated script variations, click an approval button, and have the finalized asset delivered back to her for publishing without ever opening a web browser.

**2. Persona 2: Alex, The Tactical Creator (Social Media Manager / Brand Influencer)**

*   **Background & Role:** Alex is the face and voice of the brand on social media (or an independent creator). They understand the brutal, daily grind required to appease the algorithms of TikTok and Threads.
*   **Goals:**
    *   Produce 3-5 high-retention, 15-60 second videos daily to sustain channel growth.
    *   Ensure their distinct visual identity and vocal tone are perfectly replicated across all content, maintaining parasocial trust with their audience.
    *   Reclaim their time from the physical demands of being on-camera constantly.
*   **Pain Points:**
    *   **Creative Burnout:** The physical toll of setting up cameras, doing multiple takes, and editing out pauses for hyper-condensed formats is exhausting and unsustainable.
    *   **Platform Fragmentation:** Alex knows that a hook that works on X will fail on TikTok. Manually rewriting and re-recording the same core message for different audiences is tedious.
    *   **Tool Fatigue:** They hate logging into clunky, multi-step web applications just to generate a 30-second clip. They want tools that meet them where they are already collaborating.
*   **Usage Context:** Frequent, burst-usage. Alex will use the platform to initially train their personalized avatar and voice model (uploading images/audio). Daily, they will rely on the Slack integration to quickly turn trending topics into platform-specific scripts, review the instantaneous "3-second audio hooks," and approve renders while focusing on community engagement rather than video editing.

**3. Persona 3: Chris, The Technical Admin (IT / Infrastructure Lead)**

*   **Background & Role:** Chris manages enterprise IT operations, security compliance, and vendor integrations. He is the gatekeeper for any new tool introduced into the corporate Slack workspace.
*   **Goals:**
    *   Ensure secure, frictionless integration of the Slack app without compromising network security.
    *   Maintain strict oversight of API usage costs (HeyGen, ElevenLabs, Gemini) to prevent budget overruns.
    *   Ensure all user-generated assets (images, voice clones) are securely stored and meet enterprise compliance standards (e.g., encrypted at rest).
*   **Pain Points:**
    *   **Shadow IT:** Teams adopting unauthorized SaaS tools that expose corporate data or rack up hidden API bills.
    *   **Silent Failures:** Vendor integrations that break quietly (e.g., an expired OAuth token for YouTube publishing), resulting in emergency IT tickets from angry marketing teams.
    *   **Unbounded AI Risk:** Tools that lack proper guardrails, risking inappropriate content generation or data leaks.
*   **Usage Context:** Setup and monitoring user. Chris will perform the initial OAuth installation of the Slack app. Post-launch, he relies on the system's "Proactive OAuth Token Health" alerts via Slack to prevent publishing failures and depends on the backend DLQ (Dead Letter Queue) alerting to monitor for sustained API outages (e.g., HeyGen downtime). He does not generate videos but relies on the system's architectural rigor (FastAPI, MongoDB AES-256) to ensure enterprise safety.

## Functional Requirements

**F1: Identity & Access Management**

*   **FR-1.01: Slack Workspace Installation**
    *   **Priority:** SHALL
    *   **Description:** The system must allow a Slack Workspace Admin to install the Digital Ubiquity Engine Slack application via a standard OAuth 2.0 flow.
    *   **Acceptance Criteria:** 
        *   Given an unauthenticated workspace admin clicks the install link.
        *   When they authorize the requested scopes (commands, chat:write, files:read).
        *   Then the system stores the installation metadata and redirects to a success page.
*   **FR-1.02: User Account Provisioning via Slack**
    *   **Priority:** SHALL
    *   **Description:** When a user interacts with the bot for the first time, the system must securely provision a user profile mapping their Slack ID to an authenticated email (via Google OAuth/Email).
    *   **Acceptance Criteria:**
        *   Given a new user types a command (e.g., `/setup-channel`).
        *   When they do not exist in the `Users` collection.
        *   Then the bot replies with an ephemeral message containing a secure login/registration link.

**F2: Media Channel Configuration**

*   **FR-2.01: Create Media Channel Command**
    *   **Priority:** SHALL
    *   **Description:** The system must allow users to create logical profiles representing target platforms via a Slack command.
    *   **Acceptance Criteria:**
        *   Given an authenticated user types `/create-channel [Name] for [Platform]`.
        *   When the platform is valid (TikTok, X, YouTube Shorts, Threads, LinkedIn).
        *   Then the system creates a `MediaChannel` record in MongoDB and confirms via Slack.
*   **FR-2.02: Define Channel Tone Rules**
    *   **Priority:** SHALL
    *   **Description:** Users must be able to specify the tonal and stylistic prompt instructions for a given Media Channel via a Slack modal.
    *   **Acceptance Criteria:**
        *   Given a user clicks "Edit Tone" on a channel in Slack.
        *   When they submit the text block (e.g., "Professional, analytical, no emojis").
        *   Then the system updates the `MediaChannel.tonePrompt` property.
*   **FR-2.03: OAuth Publishing Authorization**
    *   **Priority:** SHALL
    *   **Description:** Users must be able to securely connect their external social media accounts (TikTok, X, YouTube) to a specific Media Channel for direct publishing.
    *   **Acceptance Criteria:**
        *   Given a user initiates account linking for a channel.
        *   When they complete the respective platform's OAuth flow.
        *   Then the system securely stores the refresh/access tokens and marks the channel as "Publish-Ready".
*   **FR-2.04: Archive Media Channel**
    *   **Priority:** SHALL
    *   **Description:** The system must allow authenticated users to archive a `MediaChannel` to prevent future script generations and revoke active publishing tokens.
    *   **Acceptance Criteria:**
        *   Given a user triggers a `/manage-channels` command and selects "Archive" on a specific channel.
        *   When the system confirms the action.
        *   Then the `MediaChannel` status transitions from `Active` to `Archived` in MongoDB, and associated OAuth tokens are revoked.
*   **FR-2.05: List Active Channels**
    *   **Priority:** SHOULD
    *   **Description:** The system should allow users to view a summary of all active `MediaChannel`s.
    *   **Acceptance Criteria:**
        *   Given a user types `/list-channels`.
        *   When the command is received.
        *   Then the system replies with a Block Kit message listing all `Active` channels and their linked social media status.

**F3: Digital Asset Ingestion & Validation**

*   **FR-3.01: Avatar Image Upload**
    *   **Priority:** SHALL
    *   **Description:** Users must be able to securely upload 5-10 reference images of their face via Slack for Avatar training.
    *   **Acceptance Criteria:**
        *   Given a user uses the `/upload-asset image` command.
        *   When the system receives the command.
        *   Then the system returns a secure, time-bound (15 min TTL) S3 presigned URL for upload.
*   **FR-3.02: Synchronous Image Validation (Clip + ViT)**
    *   **Priority:** SHALL
    *   **Description:** The system must instantly evaluate uploaded images for facial consistency and lighting quality before proceeding to expensive API training.
    *   **Acceptance Criteria:**
        *   Given an image is uploaded to S3.
        *   When the local ML worker calculates a confidence score < 0.85.
        *   Then the system rejects the image and sends an actionable error message to Slack (e.g., "Lighting too harsh on the left side").
*   **FR-3.03: Voice Sample Upload**
    *   **Priority:** SHALL
    *   **Description:** Users must be able to securely upload a high-quality audio file (minimum 30 seconds) to create a voice clone profile.
    *   **Acceptance Criteria:**
        *   Given a user uploads an audio file via the presigned URL.
        *   When the file is processed.
        *   Then the system updates the `AvatarModel` state and queues the audio for ElevenLabs ingestion.
*   **FR-3.04: Avatar Profile Management & Channel Assignment**
    *   **Priority:** SHALL
    *   **Description:** The system must allow users to create multiple distinct `AvatarModel` profiles and selectively assign them to specific `MediaChannel` records.
    *   **Acceptance Criteria:**
        *   Given an authenticated user triggers the `/manage-avatars` command.
        *   When the Slack UI presents their trained avatars.
        *   Then the user can select an avatar and link it to one or more configured `MediaChannels` via a dropdown menu.
*   **FR-3.05: Archive Avatar Profile**
    *   **Priority:** SHALL
    *   **Description:** The system must allow users to archive an `AvatarModel` profile, removing its association from any active `MediaChannel`s.
    *   **Acceptance Criteria:**
        *   Given a user triggers `/manage-avatars` and selects "Archive" on an avatar.
        *   When the system confirms the action.
        *   Then the `AvatarModel` status transitions to `Archived`, and the system removes its ID from any associated `MediaChannel` records.

**F4: Script Generation Pipeline**

*   **FR-4.01: Idea Ingestion Command**
    *   **Priority:** SHALL
    *   **Description:** The system must accept raw text ideas or reference URLs via Slack to initiate the content generation pipeline.
    *   **Acceptance Criteria:**
        *   Given a user types `/generate-video [Idea or URL]`.
        *   When the command is received.
        *   Then the system acknowledges receipt (HTTP 200 OK) within 3 seconds and queues the `ContentIdea`.
*   **FR-4.02: Multi-Agent Script Generation (CrewAI)**
    *   **Priority:** SHALL
    *   **Description:** The CrewAI orchestrator must generate distinct script variations for every active `MediaChannel` the user has configured, applying that channel's specific tone rules.
    *   **Acceptance Criteria:**
        *   Given a queued `ContentIdea`.
        *   When the CrewAI worker executes.
        *   Then it outputs N distinct `ScriptVariations` (where N = number of active channels) and saves them to MongoDB.
*   **FR-4.03: Strict Duration Constraints**
    *   **Priority:** SHALL
    *   **Description:** The system must enforce a hard constraint that generated scripts will resolve to 15-60 seconds of spoken audio (approximately 40-150 words).
    *   **Acceptance Criteria:**
        *   Given the Gemini agent completes a draft.
        *   When the word count falls outside the 40-150 word boundary.
        *   Then the system forces a retry loop within CrewAI to rewrite the script before saving.
*   **FR-4.04: Reference URL Processing for Idea Generation**
    *   **Priority:** SHALL
    *   **Description:** If a user provides a reference URL, the system must use `yt-dlp` via a CrewAI tool to extract non-copyrighted metadata (pacing, visual cues, general topic) to inform script generation.
    *   **Acceptance Criteria:**
        *   Given a user submits `/generate-video [Idea] from [URL]`.
        *   When the `yt-dlp` tool parses the URL.
        *   Then the extracted metadata is securely passed to Gemini agents as context, and the output `ScriptVariations` contain zero direct transcript copies from the source material.
*   **FR-4.05: Iterate on Script Generation**
    *   **Priority:** SHALL
    *   **Description:** The system must allow users to reject initial script variations and provide text feedback to trigger a refined generation loop.
    *   **Acceptance Criteria:**
        *   Given a user clicks "Refine Scripts" on a Block Kit review message.
        *   When the user submits text feedback via the resulting Slack modal.
        *   Then the system updates the `ContentIdea` with the new feedback, creates a new iteration ID, and re-queues the generation task for the CrewAI orchestrator.
*   **FR-4.06: Cancel Script Generation**
    *   **Priority:** SHOULD
    *   **Description:** The system should allow users to cancel an active script generation job.
    *   **Acceptance Criteria:**
        *   Given a `ContentIdea` is in the `Generating` state.
        *   When the user clicks the "Cancel Generation" button on the loading message.
        *   Then the system transitions the state to `Rejected` and attempts to gracefully halt the CrewAI task.

**F5: Review & Render Orchestration**

*   **FR-5.01: Script Review Interface (Block Kit)**
    *   **Priority:** SHALL
    *   **Description:** The system must present the generated script variations to the user in Slack for review, utilizing Vibe-Matched emojis (e.g., 🔥 for TikTok).
    *   **Acceptance Criteria:**
        *   Given script generation is complete.
        *   When the system posts to Slack.
        *   Then the message contains the text of the scripts alongside "Approve," "Reject," and "Refine Scripts" interactive buttons.
*   **FR-5.02: 3-Second Audio Hook Preview**
    *   **Priority:** SHOULD
    *   **Description:** Upon script approval, the system must immediately generate and post the first 3 seconds of the cloned voice audio to Slack.
    *   **Acceptance Criteria:**
        *   Given a user clicks "Approve" on a script.
        *   When the ElevenLabs API returns the initial audio chunk.
        *   Then the system uploads the chunk to S3 and posts a playable audio file to the Slack thread.
*   **FR-5.03: Full Video Rendering Orchestration**
    *   **Priority:** SHALL
    *   **Description:** The system must orchestrate the sequential rendering process: full TTS via ElevenLabs, followed by avatar animation via HeyGen.
    *   **Acceptance Criteria:**
        *   Given the audio generation is complete on S3.
        *   When the worker submits the job to HeyGen.
        *   Then the `VideoRender` status is updated to `RenderingVideo` while awaiting the HeyGen webhook.
*   **FR-5.04: Cancel Video Rendering**
    *   **Priority:** SHOULD
    *   **Description:** The system should allow users to cancel a video rendering job before the final external API call is executed.
    *   **Acceptance Criteria:**
        *   Given a `VideoRender` is in the `Queued` or `SynthesizingAudio` state.
        *   When the user clicks "Cancel Render" in Slack.
        *   Then the system halts the RabbitMQ task, updates the state to `Failed` (Cancelled by User), and no further API calls to HeyGen are made.

**F6: Publishing & Delivery**

*   **FR-6.01: Final Asset Delivery**
    *   **Priority:** SHALL
    *   **Description:** Upon successful rendering, the system must deliver the final MP4 video file (or secure link) back to the user's Slack thread.
    *   **Acceptance Criteria:**
        *   Given the system receives a "Completed" webhook from HeyGen.
        *   When the webhook signature is validated.
        *   Then the system posts the final video URL to the original Slack thread.
*   **FR-6.02: Native Social Publishing**
    *   **Priority:** SHALL
    *   **Description:** The system must allow users to natively publish the approved video to the linked social media account directly from Slack.
    *   **Acceptance Criteria:**
        *   Given the final video is delivered in Slack.
        *   When the user clicks the "Publish to Linked Accounts" button.
        *   Then the system uses the stored OAuth token to post the video to the target platform and replies with a success confirmation.
*   **FR-6.03: Video Rejection Workflow**
    *   **Priority:** SHALL
    *   **Description:** The system must allow users to gracefully reject a finalized video and provide actionable next steps within Slack.
    *   **Acceptance Criteria:**
        *   Given a completed video is posted to Slack.
        *   When the user clicks the "Reject Video" button.
        *   Then the system updates the `VideoRender` state to `Rejected` and returns a Block Kit menu offering options to: "Edit Script & Re-Render", "Retrain Avatar", or "Discard Idea".
*   **FR-6.04: Publishing Failure Notification & Retry**
    *   **Priority:** SHALL
    *   **Description:** The system must detect and notify the user of failed social media publishing attempts with specific error messages, offering actionable retry options.
    *   **Acceptance Criteria:**
        *   Given a publishing attempt fails (e.g., due to an expired OAuth token).
        *   When the failure is caught by the webhook layer.
        *   Then the system sends an ephemeral Slack message to the user containing the specific error and a Block Kit button to "Reauthorize Channel" or "Retry Publish".

## Non-Functional Requirements

**NFR-1: Performance & Latency**
*   **NFR-1.01: Slack Ingestion Acknowledgement**
    *   The system MUST return an HTTP 200 OK acknowledgment to all incoming Slack Event webhooks within 3000 milliseconds to prevent Slack from retrying and causing duplicate message loops.
*   **NFR-1.02: Script Generation Latency**
    *   The CrewAI orchestration layer (including Gemini API calls and `yt-dlp` reference parsing) MUST complete the generation of up to 3 distinct script variations within a P95 latency of 30 seconds.
*   **NFR-1.03: Asynchronous Render Duration**
    *   The entire asynchronous video render pipeline (including ElevenLabs TTS synthesis, S3 transfers, and HeyGen video rendering for a 60-second clip) MUST complete within a P95 latency of 10 minutes.
*   **NFR-1.04: S3 Asset Upload TTL**
    *   Pre-signed S3 URLs generated for user avatar/voice training uploads MUST explicitly expire within 15 minutes of generation.

**NFR-2: Reliability & Resilience**
*   **NFR-2.01: External API Backoff Strategy**
    *   Workers interacting with ElevenLabs and HeyGen MUST implement an exponential backoff retry strategy for HTTP 429 (Too Many Requests) and HTTP 5xx errors. The strategy must cap at a maximum of 5 retries before routing the message to a Dead Letter Queue (DLQ).
*   **NFR-2.02: System Availability**
    *   The core asynchronous message processing pipeline (FastAPI webhook ingestion and RabbitMQ queueing) MUST maintain an uptime SLA of 99.5%, ensuring user commands are captured even if downstream rendering APIs are temporarily unavailable.
*   **NFR-2.03: Idempotency Guarantees**
    *   The webhook ingestion layer MUST implement an idempotency lock using the `slack_event_id` with a 24-hour TTL in MongoDB to guarantee that transient network duplicates do not trigger duplicate LLM or render API costs.

**NFR-3: Scalability & Resource Efficiency**
*   **NFR-3.01: Concurrent Render Processing**
    *   The RabbitMQ worker pool MUST be architected to horizontally scale to support processing at least 100 concurrent video rendering jobs without dropping incoming Slack webhooks or degrading ingestion latency.
*   **NFR-3.02: Media Channel Extensibility**
    *   The database architecture (specifically the `ScriptVariations` collection) MUST support dynamic scaling of Media Channels without requiring schema migrations (e.g., adding a new network like "Pinterest" should only require a new `platformType` enum mapping).
*   **NFR-3.03: CrewAI Worker Efficiency**
    *   The average CPU utilization of CrewAI worker instances SHOULD NOT exceed 70% under peak load (100 concurrent jobs), and average memory utilization SHOULD NOT exceed 80% before horizontal autoscaling is triggered.
*   **NFR-3.04: Database I/O Efficiency**
    *   The average database read/write IOPS (Input/Output Operations Per Second) for MongoDB Atlas MUST remain below 80% of the provisioned tier capacity under peak load to prevent state-transition bottlenecks.

**NFR-4: Security & Compliance**
*   **NFR-4.01: Encryption at Rest**
    *   All user Personally Identifiable Information (PII), including emails, slack IDs, and uploaded digital assets (images/audio), MUST be encrypted at rest utilizing AES-256 encryption via MongoDB Atlas and AWS S3.
*   **NFR-4.02: Tenant Isolation**
    *   The data access layer MUST enforce strict tenant isolation at the database query level (e.g., `WHERE userId = ?`) to ensure generated scripts, voice clones, and brand tone prompts cannot cross-pollinate between different corporate workspaces.
*   **NFR-4.03: Webhook Signature Validation**
    *   All incoming HTTP POST requests to the `/slack/events` or external vendor webhook endpoints MUST validate cryptographic signatures (e.g., `X-Slack-Signature`) before processing payload data.
*   **NFR-4.04: Data Privacy & Biometric Compliance**
    *   The system MUST process and store user-uploaded biometric data (facial images, voice samples) in a manner strictly compliant with GDPR (Article 9) and CCPA. The Slack onboarding flow MUST capture and immutably log explicit user consent prior to the creation and use of their digital avatars.
*   **NFR-4.05: Synthetic Media Regulatory Readiness**
    *   The system architecture MUST be designed to support the immediate future injection of C2PA metadata or visual watermarks to comply with evolving global regulations regarding the disclosure of AI-generated synthetic media.

**NFR-5: Cost & Unit Economics**
*   **NFR-5.01: Maximum API Cost Per Video**
    *   The combined API execution cost (Gemini token consumption + ElevenLabs character cost + HeyGen credit cost) MUST NOT exceed a total of $1.00 USD per finalized 60-second video.
*   **NFR-5.02: Strict Duration Enforcement**
    *   To enforce the unit economics defined in NFR-5.01, the system MUST programmatically block any script from proceeding to the ElevenLabs/HeyGen render queues if the estimated duration exceeds 60 seconds (calculated at ~150 words).

**NFR-6: Observability & Monitoring**
*   **NFR-6.01: System Health Polling**
    *   The system MUST continuously monitor the health and performance of all core components (FastAPI, RabbitMQ queues, MongoDB, CrewAI workers) with telemetry metrics collected at a minimum 1-minute interval.
*   **NFR-6.02: Critical Alerting SLAs**
    *   Critical system anomalies—specifically a RabbitMQ Dead Letter Queue (DLQ) ingestion rate exceeding 10 messages per minute or external API 5xx spikes—MUST trigger automated alerts to the IT/Operations team within 5 minutes of occurrence.
*   **NFR-6.03: Proactive Cost Alerting**
    *   The system MUST track aggregated API consumption costs daily. It MUST automatically dispatch a Slack alert to the designated Technical Admin if projected monthly costs exceed the workspace's configured threshold by >10%.
*   **NFR-6.04: Distributed Traceability**
    *   All asynchronous processing jobs MUST generate a unique `trace_id` upon initial Slack webhook ingestion. This ID MUST be passed and logged across all relevant microservices, RabbitMQ headers, and external API payloads to enable end-to-end debugging.

**NFR-7: Data Management & Retention**
*   **NFR-7.01: Generated Asset Lifecycle**
    *   Finalized video assets (MP4s) stored in S3 MUST be retained for a maximum of 90 days. After 90 days, the system MUST automatically transition them to cold storage or delete them via an automated S3 lifecycle policy.
*   **NFR-7.02: Raw Biometric Asset Lifecycle**
    *   Raw uploaded avatar images and voice samples MUST be securely retained only as long as the associated `AvatarModel` is in an `Active` state. Upon the model transitioning to an `Archived` state, the raw assets MUST be permanently deleted from S3 within 7 days.
*   **NFR-7.03: Audit Log Immutability**
    *   All system state transitions and user action audit logs (e.g., consent grants, script approvals, publishing events) MUST be immutably retained in MongoDB for a minimum of 1 year to satisfy enterprise compliance and debugging requirements.

**NFR-8: Auditing & Reporting**
*   **NFR-8.01: Audit Log Queryability**
    *   The system MUST provide an accessible mechanism (via secure API or integrated logging tool) to query all immutable audit logs based on user ID, timestamp, and event type to support rapid compliance checks.
*   **NFR-8.02: Performance & Cost Reporting**
    *   The system MUST generate automated weekly reports summarizing key metrics (average script generation time, render duration, uptime) and aggregated API consumption costs per workspace, accessible to designated Technical Admins.
*   **NFR-8.03: Compliance Reporting Capability**
    *   The system MUST support the programmatic extraction of user consent records (captured under NFR-4.04) to demonstrate compliance with biometric data handling regulations during audits.

**NFR-9: Disaster Recovery & Business Continuity**
*   **NFR-9.01: Recovery Time Objective (RTO)**
    *   In the event of a catastrophic primary infrastructure failure (e.g., AWS region outage), the core Slack ingestion and job queuing service (FastAPI and RabbitMQ) MUST be fully operational in a failover state within an RTO of 4 hours.
*   **NFR-9.02: Recovery Point Objective (RPO)**
    *   Critical state data (user profiles, channel configurations, and avatar metadata) stored in MongoDB Atlas MUST maintain an RPO of 15 minutes, ensuring minimal data loss during a critical failure.
*   **NFR-9.03: Automated Backups**
    *   The system MUST implement automated, encrypted daily backups of all MongoDB Atlas data, with verified restoration procedures tested at least quarterly.

**NFR-10: Usability & User Experience (Slack-First)**
*   **NFR-10.01: Command Discoverability**
    *   All primary user actions (e.g., `/generate-video`, `/manage-avatars`) MUST be registered natively as Slack Slash Commands with clear, concise descriptions to ensure immediate discoverability without external documentation.
*   **NFR-10.02: Notification Actionability**
    *   All system-generated Slack messages (status updates, errors, approvals) MUST utilize Slack Block Kit to present clean formatting and MUST include interactive buttons (e.g., "Retry", "Approve", "Reauthorize") to resolve issues instantly without typing.
*   **NFR-10.03: Zero-Context Switching Constraint**
    *   The primary critical path (Idea Submission -> Script Review -> Video Approval -> Social Publishing) MUST be completable entirely within the Slack client interface, requiring absolutely 0 external browser navigations.

## Edge Cases

**1. Input & Ingestion Edge Cases**

*   **EC-1.01: Invalid or Unsupported Reference URL**
    *   *Scenario:* A user submits a `/generate-video` command with a reference URL that `yt-dlp` cannot parse (e.g., a private Google Drive link, a password-protected Vimeo video, or an unsupported obscure platform).
    *   *System Behavior:* The `yt-dlp` CrewAI tool must catch the parsing exception gracefully. It MUST NOT crash the agent loop. The system will log the specific `yt-dlp` failure reason (e.g., "Authentication required") to observability. The Gemini agent will proceed to generate the script relying *solely* on the raw text prompt provided alongside the URL, appending a quiet Slack warning to the output: *(Note: Could not parse reference URL. Script generated using text prompt only).*
*   **EC-1.02: Obscene or Policy-Violating Input Prompt**
    *   *Scenario:* A user submits a raw idea containing hate speech, explicit NSFW content, or malicious prompt injection designed to bypass Gemini guardrails.
    *   *System Behavior:* The initial Gemini prompt evaluation layer MUST reject the input before queuing it for full script expansion. The `ContentIdea` state transitions immediately from `Submitted` to `Rejected`. The system replies to the user's Slack thread with an ephemeral, generic policy violation notice (e.g., "Idea rejected: violates brand safety guidelines") without echoing the toxic input back into the channel.
*   **EC-1.03: Massive Raw Prompt Exceeding Context Window**
    *   *Scenario:* A user copies and pastes a 10,000-word blog post into the `/generate-video` Slack command, exceeding the allowed token limit or the Slack command character limit.
    *   *System Behavior:* The FastAPI ingestion endpoint MUST validate the string length of the `rawPrompt`. If it exceeds a predefined threshold (e.g., 3,000 characters), it returns an immediate HTTP 400 response with a Slack ephemeral message instructing the user to "Please summarize your idea to under 500 words to ensure optimal script generation."

**2. Asset Generation Edge Cases**

*   **EC-2.01: Multi-Face Image Uploads for Avatar Training**
    *   *Scenario:* A user uploads 5 reference images to train their avatar, but one of the images contains multiple faces (e.g., a group shot), confusing the HeyGen model.
    *   *System Behavior:* The local Clip+ViT worker MUST detect the presence of >1 bounding box for a human face in any single uploaded image. The specific image is marked as `isValidated: false`. The overall `AvatarModel` state transitions to `Failed`. The Slack bot notifies the user specifying the exact image file name: "Image 'group_photo.jpg' contains multiple faces. Please upload images featuring only your face."
*   **EC-2.02: Non-Lexical AI Script Hallucination**
    *   *Scenario:* The Gemini LLM hallucinates and generates a script variation containing heavy markdown formatting, code blocks, or non-pronounceable characters (e.g., `[INSERT EXPLOSION SOUND]`) that will cause the ElevenLabs TTS API to fail or sound robotic.
    *   *System Behavior:* A regex validation step MUST run on the `scriptContent` before it is presented to the user. If non-lexical bracketed directions or code blocks are detected, the system forces an internal retry loop within CrewAI (up to 2 times) with a stricter prompt to output "spoken text only." If the retry limit is exhausted, that specific `ScriptVariation` is discarded, and only the successful variations are shown in Slack.
*   **EC-2.03: Unsupported or Corrupted Asset File Type**
    *   *Scenario:* A user attempts to upload a `.pdf` file instead of an image for avatar training, or uploads a fundamentally corrupted `.mp3` for voice training.
    *   *System Behavior:* The initial FastAPI/S3 validation layer MUST intercept invalid MIME types before queuing the processing worker. For corrupted files that pass MIME checks but fail structural parsing, the local worker MUST catch the exception. The `AvatarModel` state transitions to `Failed`, and the user is sent an ephemeral Slack message: "Asset upload failed: Unsupported or corrupted file. Please upload a valid JPG, PNG, or MP3 file."
*   **EC-2.04: S3 Upload Timeout (Presigned URL Expiry)**
    *   *Scenario:* A user requests an upload link via `/upload-asset` but gets distracted and attempts the upload 20 minutes later, after the presigned URL's 15-minute TTL has expired.
    *   *System Behavior:* The S3 upload will fail with an HTTP 403 Forbidden. The background worker monitoring the expected upload MUST detect the lack of an `S3 ObjectCreated` event within the TTL window. It will send a Slack ping: "Your upload link expired. Please run the command again to generate a new secure link."
*   **EC-2.05: Low-Quality Voice Clone Rejection**
    *   *Scenario:* The ElevenLabs API successfully trains a voice clone and generates a video, but the output sounds unacceptably unnatural or distorted to the user, prompting them to click "Reject Video."
    *   *System Behavior:* The `VideoRender` transitions to `Rejected`. The Slack bot responds with a Block Kit menu offering specific mitigation paths, crucially including a "Retrain Voice Model" button that triggers a fresh `/upload-asset audio` flow with tips on recording clearer audio (e.g., "Ensure no background noise and speak closer to the microphone").

**3. State & Concurrency Edge Cases**

*   **EC-3.01: Archiving a Channel Mid-Generation**
    *   *Scenario:* A user submits an idea for "Channel A", but then immediately archives "Channel A" while the CrewAI workers are still in the `Generating` state.
    *   *System Behavior:* Before saving the final `ScriptVariations` to MongoDB, the worker MUST perform a final state check on the associated `MediaChannel`. If the channel is `Archived`, the worker discards that specific script variation. It will not be presented to the user for review.
*   **EC-3.02: Double-Clicking the "Approve" Button**
    *   *Scenario:* A user experiences network lag and clicks the Slack "Approve" button on a script twice, potentially triggering two identical, expensive video rendering jobs.
    *   *System Behavior:* The FastAPI Slack Interaction handler MUST enforce an idempotency lock using the Slack `action_ts` timestamp. Furthermore, the `VideoRender` collection utilizes a unique index on `scriptId`. The second request will fail the unique constraint check, be silently ignored, and no duplicate RabbitMQ message will be queued.

**4. External API Edge Cases**

*   **EC-4.01: Prolonged HeyGen API Outage**
    *   *Scenario:* The HeyGen video rendering API experiences a total regional outage. Video rendering jobs back up in the RabbitMQ queue, and retries continually fail, eventually hitting the DLQ.
    *   *System Behavior:* Once a `VideoRender` job exhausts its 5 maximum retries and lands in the DLQ, the system state updates to `Failed`. A cron job sweeps the DLQ. Instead of retrying indefinitely, it sends a Slack message to the user: "Video rendering is currently delayed due to an upstream vendor outage. Your script is saved. Please try re-rendering from the script menu later."
*   **EC-4.02: Slack Webhook Delivery Timeout on Render Completion**
    *   *Scenario:* The HeyGen webhook successfully hits our FastAPI endpoint, updating the database to `Completed`. However, when our system attempts to POST the final MP4 URL back to the Slack channel, the Slack API times out or returns a 50x error.
    *   *System Behavior:* The final step of the worker process (posting to Slack) MUST wrap the Slack API call in a retry block (exponential backoff, max 3 tries). If it fails permanently, the database accurately reflects `Completed`, but the user remains uninformed. A separate "Orphaned Renders" cron job will identify `Completed` renders that lack a Slack `message_ts` delivery receipt and attempt to safely re-deliver them.
*   **EC-4.03: ElevenLabs TTS API Hard Failure**
    *   *Scenario:* During the `SynthesizingAudio` phase, the ElevenLabs API repeatedly returns a 500 Internal Server Error, exhausting the defined exponential backoff retry limit.
    *   *System Behavior:* The RabbitMQ worker routes the job to the DLQ. The `VideoRender` state updates to `Failed_TTS`. The system sends an explicit Slack message: "Audio generation failed due to a vendor outage. Your script is saved. Please attempt to re-render later."
*   **EC-4.04: HeyGen API Content Rejection or Low-Quality Render**
    *   *Scenario:* HeyGen's API successfully receives the payload but rejects the render request due to a violation of *their* internal content safety policies, or it returns a `Completed` webhook with a video file containing severe visual glitches that pass Clip+ViT but fail human review.
    *   *System Behavior:* If explicitly rejected by HeyGen, the `VideoRender` status transitions to `Failed_VendorContentPolicy`, triggering a Slack alert to the user. If returned with visual artifacts (post-completion), the user utilizes the `Reject Video` Block Kit workflow. The system logs the user's rejection reason (e.g., "visual glitch") to inform future HeyGen integration improvements, updating the state to `Rejected_UserQuality`.
*   **EC-4.05: Slack API Interaction Failure**
    *   *Scenario:* The system attempts to send a Block Kit message (e.g., script review, status update) to a user in Slack, but the Slack API returns a 4xx or 5xx error (e.g., rate limit exceeded, invalid token).
    *   *System Behavior:* All outbound Slack API calls MUST be wrapped in an exponential backoff retry block (max 3 retries). If failures persist, the system logs the Slack API error, transitions the `ContentIdea` or `VideoRender` state to `User_Notification_Failed`, and triggers an observability alert. The user will not receive the push notification but can query their job status via `/list-assets`.

**5. Publishing & Distribution Edge Cases**

*   **EC-5.01: Expired or Revoked OAuth Publishing Token**
    *   *Scenario:* A user clicks "Publish to Linked Accounts" for a completed video, but the stored OAuth token for that specific platform (e.g., TikTok) has naturally expired or was manually revoked by the user in the target app.
    *   *System Behavior:* The FastAPI publishing adapter MUST catch the `401 Unauthorized` exception from the social network API. The system updates the `MediaChannel` status to `Authorization_Required`. The user receives an immediate Slack message containing the specific error and a Block Kit "Reauthorize Channel" button to seamlessly restart the OAuth flow.
*   **EC-5.02: Platform-Specific Content Moderation Rejection**
    *   *Scenario:* The video renders successfully and the OAuth token is valid, but the target social network's API (e.g., YouTube Shorts) rejects the payload due to a platform-specific moderation rule (e.g., flagged background audio, prohibited keywords).
    *   *System Behavior:* The publishing adapter MUST parse the rejection payload from the target API. The video is not published. The system sends a Slack message detailing the exact platform and reason for rejection: *"Publishing to YouTube Shorts failed: Content flagged for [Reason]. You may need to refine your script and re-render."*

**6. User Account Lifecycle Edge Cases**

*   **EC-6.01: User Account Deactivation/Deletion Mid-Process**
    *   *Scenario:* An authenticated user initiates a script generation or video render, but their account is deactivated or deleted by an admin before the background job completes.
    *   *System Behavior:* All active or queued jobs associated with the deactivated user's `userId` MUST be immediately marked as `Cancelled_UserDeleted`. The CrewAI orchestrator and RabbitMQ workers will cease processing for these jobs to halt API costs. Any partial assets generated (e.g., script variations, cached audio) are flagged for automated deletion within 24 hours to comply with strict data retention policies.

## Error Handling

**1. Error Taxonomy & General Strategy**
The Digital Ubiquity Engine prioritizes "Zero Silent Failures." Because the primary interface is an asynchronous Slack bot, users cannot be left waiting indefinitely for background tasks that have crashed. All errors are categorized into three levels, each with a specific mitigation and user communication strategy:
*   **Validation Errors (4xx):** Issues with user input (bad commands, invalid files). Recoverable via immediate user correction.
*   **External API, Integration & Delivery Errors (5xx/429/401):** Temporary or persistent failures with external vendors (ElevenLabs, HeyGen, Social Platforms, Slack API) or LLMs. Recoverable via automated system retries or explicit user re-authorization.
*   **Critical System Failures (5xx):** Infrastructure crashes (e.g., database timeouts). Requires graceful degradation and ops notification.

**2. User Input & Validation Errors**

| Error Condition | Trigger | System Handling | User-Facing Slack Message |
| :--- | :--- | :--- | :--- |
| **Invalid Slash Command** | User types an unrecognized command or omits required parameters (e.g., `/generate-video` with no text). | FastAPI regex router catches error. Drops request. | *Ephemeral*: "Hmm, I didn't quite catch that. Try `/generate-video [your idea]` or type `/help` for a list of commands." |
| **Image Validation Failure** | Local Clip+ViT worker scores an uploaded avatar image below 0.85 (e.g., poor lighting, multiple faces). | Worker marks `DigitalAsset` as `Failed`. Halts avatar training queue. | *Thread Reply*: "I can't use image #3 because the lighting is too harsh on the left side of your face. Upload one more facing a window and we’re good to go!" |
| **Prompt Exceeds Token Limit** | User submits a massive block of text exceeding the Gemini context window or hardcoded limits. | FastAPI rejects payload before DB insertion. | *Ephemeral*: "That idea is a bit too long! Please summarize your concept to under 500 words so I can generate the best scripts for you." |
| **Expired Upload Link** | User attempts to upload an asset to an S3 presigned URL after the 15-minute TTL expires. | Background cron detects lack of S3 `ObjectCreated` event within TTL. | *Direct Message*: "Your secure upload link has expired. Please run the `/upload-asset` command again to generate a new one." |

**3. AI & Orchestration Errors**

| Error Condition | Trigger | System Handling | User-Facing Slack Message |
| :--- | :--- | :--- | :--- |
| **Gemini Hallucination / Bad Formatting** | CrewAI agent outputs non-lexical text (e.g., bracketed instructions) that fails the strict TTS regex validation. | Worker catches validation error. Triggers internal CrewAI retry loop (max 2). If still failing, drop that specific script variation. | *None* (Handled silently if 1+ variations succeed). If all fail: "I struggled to format that idea correctly for video. Could you try rephrasing it slightly?" |
| **Policy Violation (Brand Safety)** | Gemini model flags the input idea as violating NSFW, hate speech, or deepfake policies. | `ContentIdea` state updated to `Rejected`. Worker terminates task. | *Thread Reply*: "I cannot generate scripts for this idea as it violates our brand safety and content policies. Please submit a different concept." |
| **Reference URL Unreachable** | `yt-dlp` tool fails to scrape the provided reference link (e.g., video is private or deleted). | Tool catches exception. Agent proceeds using *only* the user's raw text prompt. | *Appended to Script Result*: "(Note: I couldn't access your reference link, so I generated these scripts based purely on your text prompt!)" |

**4. External API, Integration & Delivery Errors**

| Error Condition | Trigger | System Handling | User-Facing Slack Message |
| :--- | :--- | :--- | :--- |
| **ElevenLabs / HeyGen Rate Limit (429)** | Vendor API returns a `Too Many Requests` error during the render phase. | RabbitMQ worker NACKs the message to the Dead Letter Queue (DLQ) with an exponential backoff TTL (5s, 30s, 2m, 10m). | *None initially.* (The system handles this silently unless max retries are hit). |
| **Vendor Persistent Outage (5xx)** | ElevenLabs or HeyGen is down. Message hits max DLQ retries (5). | Worker updates `VideoRender` state to `Failed_VendorOutage`. Flushes message from queue. | *Thread Reply*: "Video rendering is currently delayed due to an upstream vendor outage. Your approved script is safely saved. Please try clicking 'Render' again later." |
| **Publishing Token Expired** | Target social media platform returns `401 Unauthorized` when attempting to push the final video. | FastAPI publishing adapter updates `MediaChannel` state to `Authorization_Required`. | *Thread Reply (with Block Kit Button)*: "Publishing to TikTok failed because your connection expired. [Re-Authorize TikTok]" |
| **Social Platform Content Rejection** | Target social media API returns an error indicating a content policy violation during publishing. | FastAPI publishing adapter logs vendor response. Updates `VideoRender` status to `Failed_PlatformPolicy`. | *Thread Reply*: "Publishing to [Platform] failed: Content rejected by [Platform]'s moderation policies for [Specific Reason, if provided]. Please refine your script and try again." |
| **Missing Webhook Callback** | HeyGen accepts the render job but never fires the `Completed` webhook within the 30-minute expected window. | Cron watchdog transitions `VideoRender` from `RenderingVideo` to `Failed_Timeout`. | *Thread Reply*: "The video render timed out unexpectedly. Please click here to [Retry Render]." |
| **Critical Slack Message Delivery Failure** | System fails to post a crucial interactive message (e.g., script review) to Slack after exhausting outbound retries. | `ContentIdea` or `VideoRender` state updates to `Notification_Failed`. Triggers PagerDuty/Ops alert. | *Fallback Direct Message to Tech Admin*: "URGENT: Failed to deliver critical notification for [Job ID] to [User]. Please advise user to check `/list-assets` for status." |

**5. User-Initiated System Feedback Loops**

| Error Condition | Trigger | System Handling | User-Facing Slack Message |
| :--- | :--- | :--- | :--- |
| **User Rejects Video (Quality Issue)** | User clicks "Reject Video" on a delivered render and explicitly selects "Visual Quality" or "Avatar Distortion" via Block Kit. | `VideoRender` state updates to `Rejected_UserQuality`. System logs specific rejection reason and links it to the HeyGen `renderId` for monthly vendor review. | *Ephemeral*: "Thanks for the feedback. We've logged your concerns about video quality. You can now try [Edit Script & Re-Render] or [Retrain Avatar]." |

**6. System-Level Degradation Strategy**
If the primary RabbitMQ cluster or MongoDB Atlas instance experiences a catastrophic outage preventing job ingestion:
1.  FastAPI will catch the database/queue connection timeout.
2.  FastAPI will return a highly visible, graceful degradation message directly to the Slack payload: *"The Digital Ubiquity Engine is currently undergoing maintenance. We cannot accept new ideas at this moment, but we'll be back online shortly."*
3.  This prevents the Slack bot from silently swallowing commands and leaving users in the dark.

## Success Metrics

**1. Primary KPIs: Velocity, Efficiency, & Conversion**
*   **KPI-1.01: End-to-End Production Time**
    *   *Definition:* The total time elapsed from the initial Slack webhook ingestion (`/generate-video`) to the delivery of the final rendered video asset.
    *   *Baseline:* 48 hours (estimated manual production).
    *   *Target:* <10 minutes.
    *   *Type:* Leading Indicator.
*   **KPI-1.02: Average API Cost Per Video**
    *   *Definition:* The aggregated vendor API execution cost (Gemini tokens + ElevenLabs characters + HeyGen credits) per finalized 60-second video.
    *   *Target:* <$1.00 USD.
    *   *Type:* Lagging Indicator (measured monthly).
*   **KPI-1.03: Video Publication Rate**
    *   *Definition:* The percentage of user-approved videos that are successfully published natively to at least one associated social media channel.
    *   *Calculation:* (`video_published_to_social` events / `video_render_completed` events where status is 'Approved') * 100.
    *   *Target:* >90%.
    *   *Type:* Lagging Indicator (Measures funnel conversion and true value realization).

**2. Adoption & Engagement Metrics**
*   **KPI-2.01: User Activation Rate**
    *   *Definition:* The percentage of users who install the Slack app, successfully authenticate, and configure at least one `MediaChannel` within 24 hours.
    *   *Target:* >80%.
    *   *Type:* Leading Indicator.
*   **KPI-2.02: Weekly Active User (WAU) Retention**
    *   *Definition:* Cohort-based retention measuring the percentage of users who generated at least one script variation in Week X and returned to generate at least one script variation in Week X+1.
    *   *Target:* >75% retention over a rolling 4-week cohort period.
    *   *Type:* Lagging Indicator (Proves the Slack-native interface eradicated UI adoption friction).
*   **KPI-2.03: Multi-Channel Utilization**
    *   *Definition:* The percentage of WAU who generate scripts for two or more distinct `MediaChannels` (e.g., TikTok and X) per single raw idea submitted.
    *   *Target:* >50%.
    *   *Type:* Leading Indicator (Validates the core premise of the CrewAI multi-agent adapter workflow).

**3. Quality, Reliability, & Safety Metrics**
*   **KPI-3.01: Script Approval Rate**
    *   *Definition:* The percentage of initial CrewAI-generated scripts approved by the user *without* requiring a user-initiated "Refine Scripts" action.
    *   *Target:* >60%.
    *   *Type:* Leading Indicator (Measures Gemini prompt and RAG effectiveness).
*   **KPI-3.02: Avatar Acceptance Rate**
    *   *Definition:* The percentage of new `AvatarModel` profiles that yield user-approved videos within their first 3 generation attempts, without the user triggering a "Reject Video -> Retrain Avatar/Voice" workflow.
    *   *Calculation:* (`video_render_completed` events marked 'Approved' for a new avatar / total new `avatar_training_completed` events) * 100, scoped to the first 3 renders.
    *   *Target:* >70%.
    *   *Type:* Leading Indicator (Measures subjective quality of Clip+ViT and HeyGen output).
*   **KPI-3.03: Error Recovery Rate**
    *   *Definition:* The percentage of user-facing error events (e.g., `Authorization_Required`, `Failed_Timeout`) that are successfully resolved by the user utilizing the provided Block Kit action buttons (e.g., "Reauthorize", "Retry Render").
    *   *Calculation:* (`retry_success` + `reauthorize_success` events) / Total `error_notification_sent` events requiring user action.
    *   *Target:* >85%.
    *   *Type:* Lagging Indicator (Validates the "Zero Silent Failures" UX strategy).
*   **KPI-3.04: Zero-Defect Brand Safety**
    *   *Definition:* Incidence rate of deepfake or brand safety policy violations in generated output.
    *   *Target:* 0%.
    *   *Type:* Lagging Indicator.
*   **KPI-3.05: Render Completion Rate**
    *   *Definition:* The percentage of approved scripts that successfully complete the asynchronous render pipeline without exhausting the Dead Letter Queue (DLQ) maximum retry limit.
    *   *Target:* >95%.
    *   *Type:* Lagging Indicator (Measures API integration resilience).

**4. Instrumentation Requirements**
To track these metrics accurately, the following events MUST be instrumented via the data layer (MongoDB) and streamed to a downstream analytics provider (e.g., PostHog/Mixpanel):
*   `slack_app_installed` (properties: `workspace_id`, `user_id`)
*   `user_authenticated`
*   `media_channel_created` (properties: `platformType`)
*   `avatar_training_completed` (properties: `clip_vit_score`)
*   `idea_ingested` (properties: `word_count`, `has_reference_url`)
*   `script_generation_completed` (properties: `generation_latency_ms`, `variation_count`)
*   `script_approved` vs. `script_refined` vs. `script_rejected`
*   `video_render_completed` (properties: `total_api_cost_usd`, `render_latency_ms`, `avatar_model_id`, `status: Approved|Rejected`)
*   `video_rejected` (properties: `rejection_reason: visual_quality|audio_quality|script_error`)
*   `video_published_to_social` (properties: `target_platform`)
*   `error_notification_sent` (properties: `error_type: VendorOutage|AuthRequired|ValidationFailed`)
*   `user_clicked_action_button` (properties: `button_type: RetryRender|Reauthorize|Refine`)
*   `retry_success` / `reauthorize_success`

## Dependencies

**1. Primary KPIs: Velocity, Efficiency, & Conversion**
*   **KPI-1.01: End-to-End Production Time**
    *   *Definition:* The total time elapsed from the initial Slack webhook ingestion (`/generate-video`) to the delivery of the final rendered video asset.
    *   *Baseline:* 48 hours (estimated manual production).
    *   *Target:* <10 minutes.
    *   *Type:* Leading Indicator.
*   **KPI-1.02: Average API Cost Per Video**
    *   *Definition:* The aggregated vendor API execution cost (Gemini tokens + ElevenLabs characters + HeyGen credits) per finalized 60-second video.
    *   *Target:* <$1.00 USD.
    *   *Type:* Lagging Indicator (measured monthly).
*   **KPI-1.03: Video Publication Rate**
    *   *Definition:* The percentage of user-approved videos that are successfully published natively to at least one associated social media channel.
    *   *Calculation:* (`video_published_to_social` events / `video_render_completed` events where status is 'Approved') * 100.
    *   *Target:* >90%.
    *   *Type:* Lagging Indicator (Measures funnel conversion and true value realization).

**2. Adoption & Engagement Metrics**
*   **KPI-2.01: User Activation Rate**
    *   *Definition:* The percentage of users who install the Slack app, successfully authenticate, and configure at least one `MediaChannel` within 24 hours.
    *   *Target:* >80%.
    *   *Type:* Leading Indicator.
*   **KPI-2.02: Weekly Active User (WAU) Retention**
    *   *Definition:* Cohort-based retention measuring the percentage of users who were active (triggered an `idea_ingested` or `script_generation_completed` event) in Week X and remained active in Week X+1, measured from their initial activation date.
    *   *Target:* >75% retention over a rolling 4-week cohort period.
    *   *Type:* Lagging Indicator (Proves the Slack-native interface eradicated UI adoption friction).
*   **KPI-2.03: Multi-Channel Utilization**
    *   *Definition:* The percentage of WAU who generate scripts for two or more distinct `MediaChannels` (e.g., TikTok and X) per single raw idea submitted.
    *   *Target:* >50%.
    *   *Type:* Leading Indicator (Validates the core premise of the CrewAI multi-agent adapter workflow).

**3. Quality, Reliability, & Safety Metrics**
*   **KPI-3.01: Script Approval Rate**
    *   *Definition:* The percentage of initial CrewAI-generated scripts approved by the user *without* requiring a user-initiated "Refine Scripts" action.
    *   *Target:* >60%.
    *   *Type:* Leading Indicator (Measures Gemini prompt and RAG effectiveness).
*   **KPI-3.02: Avatar Acceptance Rate**
    *   *Definition:* The percentage of new `AvatarModel` profiles that yield user-approved videos within their first 3 generation attempts, without the user triggering a "Reject Video -> Retrain Avatar/Voice" workflow.
    *   *Calculation:* (`video_render_completed` events marked 'Approved' for a new avatar / total new `avatar_training_completed` events) * 100, scoped to the first 3 renders.
    *   *Target:* >70%.
    *   *Type:* Leading Indicator (Measures subjective quality of Clip+ViT and HeyGen output).
*   **KPI-3.03: Error Recovery Rate**
    *   *Definition:* The percentage of user-facing error events that are successfully resolved by the user utilizing the provided Block Kit action buttons.
    *   *Calculation:* (`retry_success` + `reauthorize_success` events) / Total `error_notification_sent` events requiring user action.
    *   *Target:* >85%.
    *   *Type:* Lagging Indicator (Validates the "Zero Silent Failures" UX strategy).
*   **KPI-3.04: Zero-Defect Brand Safety**
    *   *Definition:* Incidence rate of deepfake or brand safety policy violations in generated output.
    *   *Target:* 0%.
    *   *Type:* Lagging Indicator.
*   **KPI-3.05: Render Completion Rate**
    *   *Definition:* The percentage of approved scripts that successfully complete the asynchronous render pipeline without exhausting the Dead Letter Queue (DLQ) maximum retry limit.
    *   *Target:* >95%.
    *   *Type:* Lagging Indicator (Measures API integration resilience).

**4. Instrumentation Requirements**
To track these metrics accurately, the following events MUST be instrumented via the data layer (MongoDB) and streamed to a downstream analytics provider (e.g., PostHog/Mixpanel):
*   `slack_app_installed` (properties: `workspace_id`, `user_id`)
*   `user_authenticated`
*   `media_channel_created` (properties: `platformType`)
*   `avatar_training_completed` (properties: `clip_vit_score`)
*   `idea_ingested` (properties: `word_count`, `has_reference_url`)
*   `script_generation_completed` (properties: `generation_latency_ms`, `variation_count`)
*   `script_approved` / `script_refined` / `script_rejected`
*   `video_render_completed` (properties: `total_api_cost_usd`, `render_latency_ms`, `avatar_model_id`, `status: Approved|Rejected`)
*   `video_rejected` (properties: `rejection_reason: visual_quality|audio_quality|script_error`)
*   `video_published_to_social` (properties: `target_platform`)
*   `error_notification_sent` (properties: `error_type: VendorOutage|AuthRequired|ValidationFailed`)
*   `user_clicked_action_button` (properties: `button_type: RetryRender|Reauthorize|Refine`)
*   `retry_success` / `reauthorize_success`

## Assumptions

**1. User Behavior & Ecosystem Assumptions**
*   **Slack as Primary OS & IT Integration:** We assume that our target demographic (VP of Marketing, Social Media Managers) predominantly uses Slack for collaboration, and that the Digital Ubiquity Engine Slack application can be installed into enterprise workspaces after standard IT security reviews (e.g., vendor questionnaire, basic security review, no custom code audit or extensive penetration testing required) within an average timeframe of 2 weeks.
*   **Input Quality:** We assume users will be able to provide the minimum required assets (5-10 clear images, 30+ seconds of clean audio) necessary to pass the Clip+ViT validation threshold (0.85) without requiring extensive external guidance or professional studio equipment.
*   **Tolerance for Asynchrony:** We assume users will accept a 5-to-10 minute wait time for final video rendering, provided the initial script generation and 3-second audio hook preview are delivered almost instantly (<30 seconds).

**2. Internal Team & Operational Assumptions**
*   **Internal Team Capability:** We assume that the existing engineering team has, or can rapidly acquire, the necessary expertise in event-driven architecture, distributed systems, CrewAI framework, AI model integration (Gemini, HeyGen, ElevenLabs), and Slack API development to deliver the robust MVP described in the Engineering Plan within the projected timeline.
*   **Operational Bandwidth:** We assume that the IT/Operations team (Persona: Chris) has sufficient bandwidth to support the deployment, ongoing monitoring (e.g., DLQ alerts, system health polling), and incident response for this new, complex AI-driven infrastructure.

**3. Technical & Third-Party Architecture Assumptions**
*   **Vendor API Stability:** We assume that HeyGen and ElevenLabs will maintain their current API availability, performance SLAs (handling 60-second video renders in under 5 minutes), and endpoint contract structures during the MVP lifecycle.
*   **LLM Context Windows:** We assume Google Gemini's context window and rate limits are sufficient to handle multi-channel script variations and `yt-dlp` metadata ingestion simultaneously without hitting aggressive throttling caps under our projected load.
*   **`yt-dlp` Efficacy:** We assume that `yt-dlp` can reliably parse and extract metadata from major social media URLs (TikTok, YouTube) without being permanently IP-blocked or rate-limited by the host platforms during the MVP phase.

**4. Economic & Commercial Assumptions**
*   **API Unit Costs:** We assume the combined usage costs for ElevenLabs (per character pricing) and HeyGen (per credit pricing) will remain stable enough to guarantee our projected unit cost of <$1.00 USD per 60-second finalized video.
*   **Algorithmic Viability:** We assume that AI-generated avatars, when produced at HeyGen's premium tier with user-cloned voices, are currently sophisticated enough to avoid algorithmic shadow-banning by platforms like TikTok and Instagram Reels.

**5. Regulatory & Compliance Assumptions**
*   **Liability Boundaries:** We assume that by offloading the actual synthetic media generation to premium, bounded commercial APIs (HeyGen, ElevenLabs), we inherit their established content guardrails, significantly mitigating our direct liability for deepfakes or copyright infringement compared to hosting open-source models directly.
*   **Platform Policy Stability:** We assume that the target publishing platforms (X, TikTok, Threads) will continue to allow AI-generated content via their official APIs without requiring complex watermarking or metadata tags that our current vendors cannot yet provide.

**6. Market & Competitive Assumptions**
*   **Competitive Differentiation & Market Acceptance:** We assume that the "Zero Adoption Friction (Slack-Native)" and "Deep, High-Fidelity Personalization" (via custom avatars) differentiators will be sufficient to capture significant market share and drive user adoption, even if existing or emerging AI video solutions offer more complex, web-based video editing features.
*   **Organic Growth Potential:** We assume that the viral nature of short-form video content and the severe efficiency gains offered by the product will generate sufficient organic, word-of-mouth growth within existing Slack workspaces, reducing reliance on expensive paid acquisition channels for initial MVP adoption.
