---
run_id: bc96a68e8500
status: completed
created: 2026-03-27T05:04:27.845142+00:00
completed: 2026-03-27T05:42:28.390585+00:00
project: "[[viral-avatar-contents]]"
tags: [idea, prd, completed]
---

# a team of AI agents that can take an idea from me in a paragraph to help me i...

> Part of [[viral-avatar-contents/viral-avatar-contents|Viral Avatar Contents]] project

## Original Idea

a team of AI agents that can take an idea from me in a paragraph to help me iterate through the initial idea into a storyboard scene which each scene is anywhere from 3-8 seconds for fully animated or longer form where user just talk with avatar with eleven labs voice like avatar talking into the screen. The form can be anywhere for an ad of 30-90 seconds or into a long form of 5-15mins.

## Refined Idea

**Industry/Domain:** Creator Economy, Digital Marketing Technology (MarTech), and Social Media Management.

**Persona:** Chief Content Officer (CCO) / Digital Agency Owner who manages cross-platform digital presence for multiple high-profile creators and B2B brands.

***

**Product Vision: Multi-Agent AI Video Content Pipeline (Slack-First MVP)**

In today’s hyper-competitive digital landscape, brand relevance is dictated by content velocity and platform-specific formatting. However, scaling video production across distinct channels—ranging from hyper-kinetic 30-90 second TikToks and YouTube Shorts to 5-15 minute deep-dive YouTube videos—presents a massive operational bottleneck. As a Chief Content Officer, the pain point is clear: creative teams are burning out not from filming, but from the tedious ideation, scripting, storyboarding, and pacing required to feed these diverse algorithms. Existing platforms like Synthesia or native HeyGen are merely rendering engines; they require a fully baked, perfectly timed script to function. They do not solve the "blank page" problem or the cross-platform adaptation problem.

The proposed solution bridges this critical competitive gap by shifting the product from a mere "video generator" to a comprehensive "AI creative pipeline." This platform will leverage a CrewAI-orchestrated multi-agent system, powered by Gemini, to transform a single, raw paragraph of text into a production-ready video asset, fully customized to the user’s digital avatar and voice.

To ensure immediate market validation and eliminate friction for busy creators, the Minimal Viable Product (MVP) will live entirely within Slack. A user will drop a rough concept into a Slack channel. From there, the system’s agentic workflow takes over. An "Idea Refiner" agent will analyze the target channel (TikTok, X, Threads, or YouTube) and expand the paragraph into a platform-optimized script. Following this, a "Storyboard Agent" will decompose the script into precise visual beats. For short-form ads and social content, the agent will structure the video into engaging 3-8 second scene intervals, potentially prompting B-roll or dynamic avatar framing. For long-form 5-15 minute content, it will generate a cohesive, continuous "talking head" structure, designed to maintain viewer retention over longer durations. 

Crucially, this system addresses the inherent risk of the "uncanny valley" and brand-safety failures through a mandatory Human-in-the-Loop (HITL) architecture. Before any expensive or time-consuming video rendering occurs, the agents will post the structured storyboard, scene pacing, and dialogue back into the Slack thread. The user can iterate on this draft via conversational prompts or approve it directly via Block Kit buttons. Only upon approval does the system dispatch the data to the generation layer. 

The generation layer will utilize the user’s personalized avatar—modeled from 5-10 uploaded images and synthesized using ElevenLabs for ultra-realistic voice cloning, paired with HeyGen for lifelike video and lip-syncing. This ensures the final output is virtually indistinguishable from a natively recorded video, preserving brand authenticity. Furthermore, Clip + ViT will be utilized in the backend to ensure visual alignment and quality assurance of the generated frames.

From a technical and scalability perspective, video rendering is notoriously slow and computationally expensive. A synchronous architecture would result in timeout errors and severe user frustration. Therefore, this product must strictly separate the data and execution layers. The architecture will rely on FastAPI for robust REST and Webhook endpoints, coupled with a RabbitMQ pub/sub message broker to handle the queuing of long-running HeyGen and ElevenLabs API tasks. MongoDB Atlas will serve as the persistence layer, tracking the state of each PRD and video job. When a video render is finally complete, the CrewAI event listener will trigger a webhook to seamlessly deliver the final MP4 file—or a secure download link—directly back to the original Slack thread. 

This platform ultimately provides unparalleled leverage. By combining the conversational ease of a Slack MVP, the creative heavy-lifting of CrewAI agents, and the state-of-the-art generation capabilities of ElevenLabs and HeyGen, we are offering an end-to-end content engine. It allows a single creator or marketer to produce a month’s worth of highly tailored, multi-channel video content from a handful of text prompts, radically reducing production costs while maximizing audience engagement.

## Executive Summary

## Executive Summary

**Problem Statement**
Chief Content Officers (CCOs) and digital marketing agencies face severe operational bottlenecks and creative burnout when scaling high-volume, hyper-tailored, platform-specific video content across varied algorithmic formats (e.g., fast-paced 30-90 second TikToks versus 5-15 minute YouTube deep dives). Existing AI video tools function merely as passive rendering engines that require perfectly timed, pre-written scripts. They fail to solve the "blank page" problem, provide zero cross-platform adaptation intelligence, and expose brands to uncanny valley and brand-safety risks without proper workflow friction.

**Target Audience & Stakeholders**
*   **Chief Content Officers (CCOs) / Digital Agency Owners:**
    *   *Goals:* Maximize content ROI, ensure strict brand consistency across all channels, and scale agency output without proportional headcount increases.
    *   *Pain Points:* High operational costs of multi-platform video production, team burnout from repetitive ideation, and the risk of off-brand or "uncanny" AI outputs damaging client reputation.
*   **Social Media Managers:**
    *   *Goals:* Maintain daily, high-velocity publishing schedules and maximize platform-specific engagement rates.
    *   *Pain Points:* Manual adaptation of core concepts into distinct scripts for TikTok, X, Threads, and YouTube is deeply time-consuming; waiting days for traditional video editing limits their ability to trend-jack.
*   **Key Stakeholders:** Internal Engineering & AI Operations teams (focused on cost-efficient API scaling and system reliability) and Brand Marketing Directors (requiring strict aesthetic oversight).

**Proposed Solution & Key Differentiators**
To bridge the gap between simple video generation and a true creative pipeline, we are building a Multi-Agent AI Video Content Engine, launched initially as a frictionless, Slack-first Minimal Viable Product (MVP). 
*   **User Setup & Personalization:** Users securely authenticate via Gmail/Email to manage multiple customized "media channels" (e.g., grouping output styles for TikTok vs. YouTube). Users personalize a dedicated avatar per channel by uploading 5-10 reference images and a voice sample.
*   **Autonomous Ideation & Storyboarding:** Users submit a raw concept into a Slack channel. An "Idea Refiner" agent (Gemini) transforms the prompt into a platform-optimized script. A "Storyboard Agent" then deconstructs it into precise visual beats (e.g., 3-8 second rapid intervals for Shorts).
*   **Human-In-The-Loop (HITL) Workflow:** Storyboards, pacing, and dialogue are surfaced natively in Slack via Block Kit. Users iteratively refine or approve the draft, ensuring 100% brand safety before triggering expensive render APIs.
*   **Best-in-Class Generation:** Post-approval, the system synthesizes a highly personalized output using the custom avatar, ElevenLabs for ultra-realistic voice cloning, and HeyGen for lifelike video and lip-syncing. Clip + ViT is deployed for backend visual quality assurance.
*   **Resilient Architecture & Error Handling:** The system strictly separates data and execution layers using FastAPI, MongoDB Atlas, and a RabbitMQ pub/sub broker. 
    *   *System Constraints:* Built to support 10 concurrent video generation workflows per agency during MVP. Target time from initial Slack prompt to first storyboard draft notification is < 5 minutes. All user media and generated content are encrypted at rest and in transit.
    *   *Failure Management:* External API failures (HeyGen/ElevenLabs) trigger exponential backoff retries; persistent failures notify the user via Slack for manual intervention. Invalid inputs (e.g., poor audio quality) are caught upfront with immediate Slack feedback. Internal rate limiting prevents API cost overruns.

**Expected Business Impact & Success Criteria**
*   **Operational Velocity:** Reduce ideation-to-render cycle time by 80%, enabling a single marketer to produce a month’s worth of content in under 48 hours.
*   **System Reliability:** Achieve a >95% successful render delivery rate without timeout failures during MVP.
*   **Brand Safety & Quality:** Maintain a 100% HITL intervention rate prior to rendering execution, reducing wasted computational spend on sub-par outputs by an estimated 40%.
*   **User Adoption:** Onboard and retain 5 distinct digital agencies on the Slack MVP within the first 6 weeks (minimum of 3 completed video pipelines per user per week).
*   **Analytics Tracking:** Success will be measured via MongoDB by explicitly tracking: agent task completion latency, HITL approval/rejection event rates, specific third-party API call success/failure rates, and user funnel drop-offs.

**Dependencies & Risks**
*   **Vendor Lock-in & Escalating Costs (HeyGen, ElevenLabs, Gemini):** Heavy reliance on premium generative APIs risks violating the project's "low cost" mandate at scale.
    *   *Mitigation:* Implement strict internal rate limits and queuing. Design the integration layer modularly to allow fast swapping of LLM or rendering providers if costs surge. Negotiate enterprise volume tiers post-MVP.
*   **Third-Party API Downtime:** Disruption in external generative services completely halts the final video creation step.
    *   *Mitigation:* Asynchronous RabbitMQ architecture ensures requests are safely queued and not dropped. Automated Slack notifications inform users of delayed render times due to upstream provider issues.
*   **Ethical & Legal Compliance (Avatars/Voice):** Potential legal issues regarding consent, deepfakes, and misuse of personalized digital clones.
    *   *Mitigation:* Mandate explicit consent agreements during account creation. The strict HITL architecture ensures a human is always accountable for the final initiated render.
*   **Asynchronous UX Friction:** Video generation is computationally intensive, risking user frustration if expected to be instant.
    *   *Mitigation:* Over-communicate state via Slack messaging (e.g., "Your video is in the render queue. Expected time: 15 minutes. We will ping you here when it's ready.").

## Executive Product Summary

# Executive Product Summary: The Omnipresence Engine

## The Real Problem We Are Solving
When someone asks for an "AI video generator," they don't actually want to render videos. They want to survive the algorithmic treadmill. 

Today, Chief Content Officers and creators face a brutal reality: social algorithms demand infinite, hyper-specific content (fast-paced TikToks, deeply researched YouTube videos, snappy Threads). Trying to meet this demand manually causes profound creative burnout. Yet, delegating this to current AI tools yields uncanny, soulless talking heads reading perfectly sterile scripts. The real problem isn't video editing speed—it is **scaling authentic human presence without degrading brand trust or crushing the creator.**

We are not building a rendering tool. We are building a frictionless creative partner that eliminates the "blank page" anxiety and handles the grueling translation of a single core idea into native languages for every distinct social platform.

## The 10-Star Product Vision
The 10-star version of this product is an **Autonomous Digital Twin Agency** that lives entirely where the creator already works: Slack. 

It does not wait for a perfectly formatted script. It listens to a messy, half-baked shower thought ("Hey, let's talk about how AI is going to change SaaS pricing models"), understands the creator's historical tone, and orchestrates a CrewAI-powered team of agents to proactively pitch fully-realized storyboards. It understands that a TikTok needs a 3-second pattern-interrupt hook, while a YouTube Short needs continuous pacing. 

By marrying world-class generative models (ElevenLabs for voice, HeyGen for visual likeness) with a strict Human-In-The-Loop (HITL) approval gateway, we deliver magic: the leverage of a 10-person media team, operating at the speed of thought, with zero brand-safety risk.

## The Ideal User Experience: "This is Exactly What I Needed"
Imagine it is Tuesday morning. The CCO of an agency is drinking coffee and drops a three-sentence thought into a dedicated Slack channel. 

They don't open a new tab. They don't log into a web app. 

Within exactly three minutes, the CrewAI **Storyboard Agent** replies natively in the Slack thread via Block Kit:
> *"Here is your script optimized for TikTok. I've placed a visual hook in the first 3 seconds, suggested a zoom-in at second 15 to break the visual monotony, and adjusted the tone to match your aggressive 'thought leadership' persona."*

Below the text are two buttons: **[Approve & Render]** or **[Make it Punchier]**. 

The CCO clicks **[Approve]**. Behind the scenes, the system queues the heavy compute via RabbitMQ and FastAPI. The user goes to their 10:00 AM meeting. At 10:25 AM, Slack pings: the finished, hyper-realistic MP4 is waiting in the thread, verified by Clip+ViT vision models for lip-sync accuracy. 

The user just saved 14 hours of production time, and the output actually sounds and looks exactly like them.

## Delight Opportunities (The "Bonus Chunks")
These are low-effort, high-impact features (<30 mins each) that signal we deeply understand the creator's workflow:

1. **A/B Hook Generation:** When the agent surfaces the storyboard draft, it automatically provides *two* distinct opening hooks for the first 3 seconds. Creators know the hook is 90% of the battle; this shows we know it too.
2. **The "Make it Punchier" Button:** A single Slack action button on the script draft that triggers the Gemini LLM to cut 20% of the fluff and increase pacing. No prompt engineering required by the user.
3. **Zero-Anxiety State Pings:** Video rendering is computationally slow. We eliminate silent failures. If the HeyGen API takes longer than expected, the system automatically sends a Slack message: *"HeyGen is running 5 minutes behind today. Your video is safely queued and rendering. Will ping you when it's done."* 
4. **Auto-Thumbnail Frame Extraction:** Using Clip+ViT, the system automatically flags the most expressive frame of the generated video and extracts it as a high-res JPEG for the user to use as a YouTube/TikTok cover image.

## Scope Mapping: The 12-Month Trajectory

* **Current State (The Baseline):** Content teams manually brainstorm, script, film, and edit. Output is limited to maybe 2-3 videos a week. Cross-platform adaptation is an afterthought.
* **This MVP (Months 1-3):** **Slack-First Prompt-to-Video Pipeline.** 
  We deploy a FastAPI/MongoDB backbone with CrewAI agents. Users authenticate via email, upload 5-10 photos and a voice sample. From Slack, they submit raw text. Agents refine the idea, format the storyboard, and request HITL approval via Block Kit. Upon approval, RabbitMQ orchestrates ElevenLabs and HeyGen to deliver the final MP4 back to Slack.
* **V2 (Months 4-6):** **Multi-Channel Workspaces.** 
  Users configure multiple "media channels" (e.g., the B2B LinkedIn avatar vs. the casual TikTok avatar). The system introduces automated B-roll injection to break up the "talking head" format.
* **The 12-Month Ideal:** **Proactive Omnipresence.** 
  The system connects via webhook to the user's blog, X (Twitter) account, or RSS feed. When the user publishes a written piece, the CrewAI Event Listener catches it, automatically drafts three distinct short-form video strategies, and sends a Slack notification: *"I see your new blog post is doing well. I drafted 3 TikToks based on the core arguments. Ready to render?"*

## Business Impact & Success Criteria
For digital marketing agencies and CCOs, this platform transitions video creation from a low-margin, high-friction service into a high-margin, infinitely scalable product. By decoupling ideation from the physical constraints of filming, agencies can onboard 5x more clients without increasing headcount.

**Success is strictly defined by the following metrics (tracked via MongoDB):**
1. **HITL First-Pass Acceptance Rate:** The ultimate measure of our AI models. Are users clicking "Approve & Render" on the first draft >75% of the time? If not, our agents lack context.
2. **Operational Velocity:** Time from Slack prompt to initial Storyboard draft must be strictly < 5 minutes.
3. **System Reliability & Error Visibility:** Maintain a >95% successful render delivery rate. 100% of vendor API timeouts (HeyGen/ElevenLabs) must be caught and communicated to the user via Slack—*zero silent failures.*
4. **MVP Adoption:** Onboard and retain 5 digital agencies within the first 6 weeks, with a minimum pipeline velocity of 3 completed videos per user, per week. 

This is not just a tool for making videos; it is an infrastructure for digital omnipresence.

## Engineering Plan

# Engineering Plan: The Omnipresence Engine

## 1. Architecture Overview

### System Boundaries and Components
The system is strictly partitioned into a synchronous **API Gateway Layer** (handling fast HTTP interactions and security) and an asynchronous **Execution Layer** (handling long-running LLM and rendering tasks). This decoupling is mandatory to respect Slack's 3-second webhook timeout and manage the unreliability/latency of third-party rendering APIs.

```text
                           TRUST BOUNDARY
                           |
[ Slack Workspace ]        |    [ Public Internet ]
      |                    |           |
      | Webhooks / Events  |           | Webhooks (HeyGen)
      v                    |           v
+-----------------------------------------------------------------+
|                         FASTAPI GATEWAY                         |
|  +--------------------+   +-------------------+   +----------+  |
|  | Slack Auth (HMAC)  |   | Vendor Auth (Sig) |   | REST API |  |
|  +--------------------+   +-------------------+   +----------+  |
+-----------------------------------------------------------------+
      | (Async Enqueue)                 | (CRUD / State Read)
      |                                 v
      |                          +-----------------+
      |                          |  MongoDB Atlas  | <-- Single Source 
      v                          +-----------------+     of Truth
+------------------------+              ^
|   RabbitMQ Broker      |              |
| - Interactions         |              | (State Updates)
| - CrewAI Tasks         |              |
| - Render Tasks         |              |
| - Dead Letter (DLX)    |              |
+------------------------+              |
      |            |                    |
      |            |                    |
      v            v                    |
+------------+ +--------------------------------------------------+
| OBSIDIAN   | |                  WORKER NODES                    |
| Knowledge  | |                                                  |
| Graph      | |  +--------------------+   +-------------------+  |
+------------+ |  | CrewAI Orchestrator|   | Render Pipeline   |  |
               |  | - Idea Refiner     |   | - ElevenLabs      |  |
               |  | - Storyboard Agent |   | - HeyGen          |  |
               |  | - Slack Interpreter|   | - Event Listener  |  |
               |  +--------------------+   +-------------------+  |
               |            |                        |            |
               +------------|------------------------|------------+
                            v                        v
                      [ Gemini LLM ]           [ Clip + ViT ]
```

### Technology Stack & Rationale
*   **FastAPI (Python):** Chosen for native async support, crucial for high-throughput webhook handling.
*   **MongoDB Atlas:** Document model perfectly fits hierarchical data (Jobs -> Storyboards -> Scenes).
*   **RabbitMQ:** Message broker for pub/sub. Provides necessary features like Dead Letter Exchanges (DLX), message TTLs, and explicit consumer acknowledgements required for retry loops.
*   **CrewAI + Gemini:** Agent orchestration framework. Gemini selected for high-context-window reasoning and cost-efficiency during heavy iteration phases.
*   **Clip + ViT:** Vision models used purely as automated QA gates to prevent rendering costs on bad avatar source images or glitchy video outputs.

### Data Flow Summaries
*   **Happy Path:** User sends text -> FastAPI validates HMAC, drops to MQ, returns 200 -> CrewAI worker picks up, expands script -> CrewAI posts Block Kit to Slack -> User clicks Approve -> FastAPI drops to MQ -> Render worker calls ElevenLabs -> HeyGen -> HeyGen webhook to FastAPI -> FastAPI validates signature, alerts Render worker -> Clip+ViT verifies -> Slack user gets MP4.
*   **Nil/Empty Path:** User sends "hi" -> CrewAI recognizes lack of intent -> Asks for clarification in Slack thread without creating a `ProductionJob`.
*   **Error Path (Vendor Timeout):** HeyGen 502s -> Render worker catches exception -> Increments `retryCount` in MongoDB -> NACKs message to RabbitMQ -> Re-queued. If `retryCount == 3` -> Routed to DLX -> Job marked `Failed` -> Slack bot notifies user "HeyGen is currently offline."

---

## 2. Component Breakdown

### A. Avatar Management & Validation
Handles the ingestion of creator profiles. Relies on vision models to prevent downstream rendering failures.

```text
State Machine: AvatarState
==========================
       [Pending]
           | (5+ images uploaded)
           v
      [Validating] -----------------------+ (Clip+ViT Score <= 0.85)
           |                              |
           | (Clip+ViT Score > 0.85)      v
           v                           [Failed]
        [Ready]                           | (User replaces images)
                                          +---------------------> [Pending]
```

### B. CrewAI Storyboard Orchestrator
The cognitive engine. It must strictly enforce JSON schema outputs from LLMs to ensure the execution layer can parse the pacing.

```text
State Machine: JobState
=======================
      [Draft]
         | (Kickoff via RabbitMQ)
         v
     [Refining]
         |
         v
   [Storyboarding] <------+ (JSON Schema Error, retries < 3)
         |                |
         | (Valid JSON)   |
         v                |
   [PendingReview] -------+ (User requests edits in Thread)
         |
         | (User clicks 'Approve')
         v
 [ApprovedForRender] ---> [Cancelled] (User clicks 'Cancel' or 30m TTL)
```

### C. Async Rendering Pipeline
Choreographs deterministic API calls out of non-deterministic vendor services.

```text
State Machine: RenderState
==========================
       [Queued]
          |
          v
  [AudioGenerating] <-------+ (ElevenLabs 5xx, retry < 3)
          |                 |
          | (MP3 received)  |
          v                 |
  [VideoGenerating] <-------+ (HeyGen 5xx, retry < 3)
          |                 |
          | (Webhook OK)    |
          v                 |
     [Completed]         [Failed] <--- (Max retries reached OR Clip+ViT Reject)
```

### API Contract Sketches

*   `POST /slack/events`
    *   **Payload:** Standard Slack event wrapper (`event.text`, `event.thread_ts`).
    *   **Action:** Verify HMAC. If `thread_ts` matches an active `SlackInteractionSession`, push to `interactions` MQ. Return 200 immediately.
*   `POST /slack/interactions`
    *   **Payload:** URL-encoded payload containing `actions[0].action_id`.
    *   **Action:** Verify HMAC. Update DB state (`ApprovedForRender`). Push to `render_tasks` MQ. Return 200 immediately.
*   `POST /api/v1/webhooks/heygen`
    *   **Headers:** `X-Signature`
    *   **Payload:** `{ "event": "video_success", "video_id": "string", "video_url": "string" }`
    *   **Action:** Verify signature. Find `RenderTask` by `heyGenJobId`. If `Completed`, return 200 (idempotency). Else, push `verify_video` task to MQ. Return 200.

---

## 3. Implementation Phases (Jira Epic & Story Map)

### Phase 1: Epic - Foundation & Infrastructure (Size: M)
*Setup the robust boundaries, CI/CD, and DB schemas.*
*   **Story 1.1:** Provision MongoDB Atlas, set up DB connections in FastAPI with connection pooling.
*   **Story 1.2:** Implement standard FastAPI middleware: Slack `X-Slack-Signature` HMAC verification, rate-limiting (Token Bucket).
*   **Story 1.3:** Provision RabbitMQ. Configure `render_events_exchange`, standard queues, and the Dead Letter Exchange (`render_events_dlx`).
*   **Story 1.4:** Define Pydantic models for MongoDB schemas (`UserProfile`, `CreatorPersona`, `ProductionJob`, `RenderTask`).

### Phase 2: Epic - User & Avatar Provisioning (Size: M)
*Allow users to map Slack identities to AI avatars.*
*   **Story 2.1:** Create `/api/v1/personas` CRUD endpoints.
*   **Story 2.2:** Build the Slack `/omni-profile` slash command to trigger profile setup.
*   **Story 2.3:** Implement Clip+ViT background task. Expose an internal Python function to download S3 images, score them (>0.85), and update `AvatarState`.
*   **Story 2.4:** Build Slack notification service for `AvatarState == Failed` explaining which image failed and why.

### Phase 3: Epic - CrewAI Orchestration (Size: L)
*The core cognitive pipeline.*
*   **Story 3.1:** Implement the `Idea Refiner` Agent in CrewAI using Gemini. Prompt tuning for channel-specific pacing (TikTok vs YT).
*   **Story 3.2:** Implement the `Storyboard Agent` with strict JSON output parsing (`Scene` sub-document schema).
*   **Story 3.3:** Add fallback logic: If JSON parsing fails 3 times, fallback to a single continuous scene to prevent pipeline lockup.
*   **Story 3.4:** Create `job_kickoff` RabbitMQ consumer to tie Slack prompts to the CrewAI workflow.

### Phase 4: Epic - HITL Slack Interactivity (Size: M)
*Bringing the magic to the user's workspace.*
*   **Story 4.1:** Build Slack Block Kit generator mapping a JSON storyboard to visual Slack blocks (Approve/Cancel buttons).
*   **Story 4.2:** Implement `SlackInteractionSession` MongoDB TTL logic. Handle TTL expiration state changes.
*   **Story 4.3:** Create threaded reply listener. If user replies in thread, pass text to `SlackInterpretMessageTool` to modify the JSON and update the Block Kit message.
*   **Story 4.4:** Wire "Approve" button to trigger `RenderState -> Queued` transition.

### Phase 5: Epic - Async Rendering Pipeline (Size: XL)
*The execution layer. High failure risk; requires extreme robustness.*
*   **Story 5.1:** Implement ElevenLabs API client. Generate audio from `Scene` dialogue. Handle 429/5xx with MQ NACKs.
*   **Story 5.2:** Implement HeyGen API client. Pass ElevenLabs audio + avatar ID.
*   **Story 5.3:** Create HeyGen Webhook listener. Implement `X-Signature` validation and idempotency lock using MongoDB `findOneAndUpdate`.
*   **Story 5.4:** Implement Clip+ViT post-render validation. Sample first frame of the returned MP4; if rejected, route to DLX.
*   **Story 5.5:** Build final delivery mechanism: Upload MP4 to Slack thread or provide signed S3 URL.

---

## 4. Data Model

### Database schema decisions
Using MongoDB Atlas. Heavy use of `ObjectId` references rather than embedding, as `ProductionJobs` will grow large with iteration history, and embedding them in `CreatorPersona` would breach document size limits and cause write-locks.

**Key Indexes:**
1.  `UserProfile`: `{ slackWorkspaceId: 1, slackUserId: 1 }` (Unique Compound).
2.  `ProductionJob`: `{ createdAt: 1 }` (TTL index = 30 days) - Auto-purges unrendered drafts to save DB space.
3.  `SlackInteractionSession`: `{ updatedAt: 1 }` (TTL index = 30 mins) - Auto-expires abandoned approval prompts.
4.  `RenderTask`: `{ heyGenJobId: 1 }` (Unique, Sparse) - Critical for webhook idempotency.

**Document: `SlackInteractionSession`**
| Field | Type | Attributes | Description |
| :--- | :--- | :--- | :--- |
| `_id` | ObjectId | PK | Primary key |
| `jobId` | ObjectId | FK, Indexed | Maps to `ProductionJob` |
| `slackThreadTs` | String | Indexed | Slack thread timestamp for reply tracking |
| `iterationCount` | Int32 | Default: 0 | Limits loop to 5 max |
| `status` | String | Enum | Awaiting, Iterating, Resolved, Expired |
| `updatedAt` | ISODate | TTL Indexed | Last activity |

---

## 5. Error Handling & Failure Modes

*Thoughtfulness over speed: we handle more edge cases, not fewer.*

| Component / Failure Mode | Detection | Handling Strategy | Classification |
| :--- | :--- | :--- | :--- |
| **Slack Webhook Timeout** | Slack API retries payload. | FastAPI endpoints return 200 OK synchronously before logic runs. | Critical |
| **LLM Hallucinates Format** | Pydantic JSON parser throws ValidationError. | Catch error, re-prompt LLM with error context. Max retries: 3. Fallback to continuous 1-scene script. | Major |
| **Infinite Feedback Loop** | User keeps asking for tweaks via Slack thread. | `iterationCount` in MongoDB. At 5, bot posts: "I might be confused. Please edit the text directly." | Minor |
| **ElevenLabs/HeyGen 502** | HTTP Client throws exception. | Catch, increment `RenderTask.retryCount`. `NACK` message to MQ. If `retryCount == 3`, route to DLX. | Major |
| **HeyGen Webhook Duplicate** | Webhook received twice for same job. | Mongo `findOneAndUpdate` with `{ renderState: { $ne: "Completed" } }`. Second call returns 200 OK but does no work. | Minor |
| **Silent API Failure** | Task sits in `VideoGenerating` forever. | Cron sweeps `RenderTasks` in `VideoGenerating` > 1 hr. Flags as `Failed`, notifies user. | Major |

---

## 6. Test Strategy

**Test Pyramid:**
1.  **Unit Tests (70%):**
    *   Test JSON Schema validators for Storyboard generation.
    *   Test all State Machine transition logic (ensure `PendingReview` cannot skip directly to `VideoGenerating`).
    *   Test HMAC validation logic using static dummy payloads and signatures.
2.  **Integration Tests (20%):**
    *   MongoDB idempotency locks (concurrent webhook deliveries).
    *   RabbitMQ pub/sub routing (ensure DLX routing works when `retryCount` maxes out).
    *   External API mocks (responses for ElevenLabs/HeyGen).
3.  **End-to-End Tests (10%):**
    *   *The Golden Path:* Simulate a Slack POST -> Mock CrewAI -> Approve Mock -> Mock Rendering -> Verify Final Slack payload formatting.

**Performance / Load:**
*   Simulate 100 concurrent webhook deliveries from HeyGen to ensure DB connection pooling handles the spike without starving the Slack interaction endpoints.

---

## 7. Security & Trust Boundaries

*   **Attack Surface 1: Slack Webhooks.**
    *   *Risk:* Malicious actor sends fake Slack approvals.
    *   *Mitigation:* Strict `X-Slack-Signature` verification on *every* request. Replay attacks prevented by checking `X-Slack-Request-Timestamp` (< 5 minutes old).
*   **Attack Surface 2: Vendor Webhooks (HeyGen).**
    *   *Risk:* Attacker fakes successful rendering webhooks to exfiltrate generated videos or poison DB state.
    *   *Mitigation:* Webhook endpoint strictly checks HeyGen's HMAC signature. Unknown `video_id`s are dropped.
*   **Attack Surface 3: PII & Image Data.**
    *   *Risk:* Avatar source images are exposed.
    *   *Mitigation:* Images stored in private S3 buckets. CrewAI and vision models access them via short-lived (15 min) pre-signed URLs. They are never public.

---

## 8. Deployment & Rollout Strategy

**Deployment Sequence:**
1.  **Phase 1: DB & MQ.** Terraform scripts apply MongoDB Atlas and RabbitMQ configurations.
2.  **Phase 2: FastAPI Web/Webhook layer.** Deployed to ECS/K8s with Auto-Scaling based on CPU.
3.  **Phase 3: Worker Nodes.** Deployed to a separate node group. Scaling based on RabbitMQ queue depth (e.g., KEDA scaling).

**Feature Flags:**
*   `FF_ENABLE_VISION_QA`: Toggles the Clip+ViT checking step (allows bypassing if vision model API is down).
*   `FF_MOCK_VENDOR_RENDER`: Routes rendering tasks to a mock service returning a dummy MP4 (saves massive cost during internal E2E testing).

**Rollback Plan:**
1.  If worker nodes fail (bad prompt logic), revert worker container image. Queue will temporarily build up but no data is lost.
2.  If DB migration is bad, system enters read-only mode, deploy reverse migration script, restore Web container image.

---

## 9. Observability

**Logging Requirements:**
*   All logs must be JSON formatted.
*   Mandatory injected context: `jobId`, `slackUserId`, `traceId`.
*   Do NOT log raw user prompts or generated scripts (Privacy / PII). Log lengths and token counts instead.

**Key Metrics & Alerts:**
1.  **`system.hitl.acceptance_rate`**: Tracks % of users clicking "Approve" on first draft. Alert if < 60% (indicates prompt engineering regression).
2.  **`queue.render_tasks.depth`**: Number of videos waiting to render. Alert if > 50 (indicates vendor API bottleneck).
3.  **`queue.dlx.count`**: Messages hitting the Dead Letter Queue. Alert if > 0 (requires manual engineering intervention).
4.  **`endpoint.slack_events.latency`**: P99 latency of Slack endpoints. Critical Alert if > 2.0s (Approaching the 3.0s Slack timeout limit).

## Problem Statement

**The Current State: The Algorithmic Treadmill**
In today’s hyper-competitive digital landscape, brand relevance is dictated by sheer content velocity and strict adherence to platform-specific formatting. A single core message must be fundamentally restructured for distinct algorithmic environments: a TikTok requires a jarring 3-second visual hook and rapid scene changes, while a deep-dive YouTube video relies on cohesive, sustained pacing to maintain 15-minute viewer retention. Currently, content teams are trapped in a severe operational bottleneck, manually brainstorming, scripting, storyboarding, and pacing distinct variations of the same idea. Due to these manual constraints, an agency's output is typically capped at a meager 2-3 high-quality videos per week per client, making true multi-channel omnipresence physically impossible without massive capital expenditure.

**The Pain Point: The Failure of Incumbent AI Solutions**
When Chief Content Officers attempt to scale production using current AI video generators (e.g., native HeyGen or Synthesia), they hit a wall: these platforms are merely passive rendering engines. They do not solve the "blank page" problem, nor do they possess the intelligence to adapt a rough concept into a platform-optimized storyboard. They require a fully baked, perfectly timed script to even begin functioning. Furthermore, offloading content creation entirely to basic LLMs without strict, human-driven quality gates frequently produces "uncanny valley," soulless talking heads. This introduces unacceptable brand-safety risks, as off-brand pacing or sterile phrasing actively degrades audience trust and client reputation.

**Business Impact: Margin Compression and Creative Burnout**
The inability to efficiently translate raw ideas into production-ready assets transforms video creation into a low-margin, high-friction service. The cognitive load and manual effort required for cross-platform adaptation cost an estimated 10 to 14 hours of production time per campaign. As a direct consequence, digital agencies cannot scale their client base without linearly scaling their creative headcount, effectively crushing profitability. Creative teams are experiencing profound burnout—not from the creative act of filming, but from the grueling, repetitive administrative burden of algorithm-specific script formatting and pacing.

**Why Now?**
The shift toward short-form, high-velocity video is complete, and the market penalty for low output is compounding. Social media platforms now actively suppress brands that fail to maintain daily, native-format publishing cadences. As competitors begin leveraging piecemeal AI tools to increase volume, agencies relying on traditional manual scripting workflows are rapidly losing market share. There is an urgent, immediate market demand for an infrastructure that bridges the gap between raw human ideation and automated rendering, eliminating production friction without sacrificing the authenticity and safety of the final brand output.

## User Personas

**Primary Persona: The Scale-Driven Chief Content Officer (CCO)**

**Demographics & Role Context**
*   **Title:** Chief Content Officer (CCO) / Digital Agency Owner
*   **Age:** 32–45
*   **Industry:** Creator Economy, B2B Marketing, Digital Media Agencies
*   **Daily Tech Stack:** Slack (primary), Asana/Monday, Figma, Premiere Pro, native social media analytics dashboards.
*   **Role Definition:** They are the operational brain behind multiple high-profile personal brands and B2B digital presences. They do not personally edit videos, but they are entirely responsible for the strategy, output velocity, and brand safety of the final assets.

**Daily Reality & Usage Context**
The CCO lives in a state of continuous, high-volume context switching. They spend 80% of their day communicating asynchronously with clients, copywriters, and video editors, almost exclusively within Slack. Their workflow is characterized by sudden bursts of inspiration ("shower thoughts" dropped into channels) followed by long, agonizing wait times for creative teams to translate those thoughts into formatted scripts and final videos. They do not have the time or patience to log into a separate SaaS web portal to learn complex prompt engineering. If an application requires them to leave Slack, or if it fails silently without notifying them, they will abandon the tool immediately.

**Key Pain Points**
*   **The "Blank Page" Bottleneck:** They have excellent, high-level strategic ideas but lack the time to manually format them into the distinct narrative structures required for TikTok (3-second visual hooks) versus YouTube (10-minute sustained pacing).
*   **Creative Burnout & Margin Compression:** Scaling their agency is currently impossible without linearly scaling their headcount of scriptwriters and video editors, which destroys their profit margins.
*   **Brand Safety Paranoia:** They have tried existing AI video tools and found them to be "uncanny" and "soulless." Releasing an off-brand, poorly paced, or robotic video could permanently damage their client's trust and audience retention. They refuse to use any tool that publishes automatically without a strict Human-in-the-Loop (HITL) review.
*   **System Anxiety:** They have experienced the frustration of initiating heavy computational tasks (like video rendering) only to have the system time out 20 minutes later without warning. They require constant, transparent communication about system state.

**Goals & Desired Outcomes**
*   **Omnipresence Without Overhead:** To take a single core thought, drop it into a chat, and receive three distinct, platform-optimized videos back, effectively doing the work of a 10-person media team.
*   **Frictionless Iteration:** To guide the AI's output using natural, conversational language (e.g., "Make it punchier") rather than wrestling with complex UI sliders or JSON payloads.
*   **Zero-Risk Execution:** To have an absolute, final approval gate (via a simple Slack Block Kit button) before any expensive API calls or final video renders are executed, ensuring total aesthetic control.

## Functional Requirements

### Glossary of Key Terms
*   **Media Channel:** A logical grouping of configuration settings targeting a specific platform (e.g., "B2B LinkedIn," "Casual TikTok") that dictates formatting, pacing, and tone.
*   **CreatorPersona:** A unique digital avatar profile containing trained visual likeness (from images) and cloned voice data (from audio samples).
*   **ProductionJob:** A single lifecycle instance tracking the journey from a raw text prompt through ideation, storyboarding, approval, and final render.
*   **AvatarState:** The validation status of uploaded media (`Pending`, `Validating`, `Ready`, `Failed`).
*   **RenderState:** The execution status of the final third-party API rendering process (`Queued`, `AudioGenerating`, `VideoGenerating`, `Completed`, `Failed`).

---

### 1. User, Channel, & Persona Management

**FR-1.01: User Authentication**
*   **Priority:** SHALL
*   **Description:** The system shall authenticate users via OAuth2 utilizing Gmail/Email credentials before allowing them to trigger workflows or manage profiles.
*   **Acceptance Criteria:**
    *   *Given* an unauthenticated user attempts to interact with the Slack bot,
    *   *When* they submit a command,
    *   *Then* the system returns an ephemeral Slack message prompting them to authenticate via a secure web link.

**FR-1.02: Avatar Media Ingestion & Validation**
*   **Priority:** SHALL
*   **Description:** The system shall provide an endpoint for users to upload 5-10 reference images and a voice sample to create a `CreatorPersona`.
*   **Acceptance Criteria:**
    *   *Given* a user submits avatar source images and a voice sample,
    *   *When* the media is received,
    *   *Then* the system shall utilize Clip+ViT to score the images; if the score > 0.85, the visual data is approved.
    *   *Then* the system shall validate the voice sample for a minimum 30-second duration, clear audio quality, and acceptable file format (WAV or MP3). 
    *   *Then* if both pass, the `AvatarState` becomes `Ready`. If either fails, it becomes `Failed` and notifies the user via Slack specifying which media type failed.
*   **API Contract Sketch:**
    *   `POST /api/v1/personas/{persona_id}/media`
    *   *Request:* `multipart/form-data` (images `file[]`, audio `file`)
    *   *Response:* `202 Accepted` with `{"status": "Validating", "jobId": "uuid"}`

**FR-1.03: Media Channel Creation & Management**
*   **Priority:** SHALL
*   **Description:** Users shall be able to create, name, and modify "Media Channels" natively within Slack using Block Kit modals.
*   **Acceptance Criteria:**
    *   *Given* an authenticated user invokes the `/omni-channel` slash command,
    *   *When* they select "Create New Channel,"
    *   *Then* a Block Kit modal appears allowing them to name the channel, select a target platform (e.g., TikTok, YouTube), and define baseline tonal instructions.

**FR-1.04: Persona-Channel Association**
*   **Priority:** SHALL
*   **Description:** The system shall allow users to explicitly link a `CreatorPersona` (Avatar + Voice) to a specific Media Channel.
*   **Acceptance Criteria:**
    *   *Given* a user is configuring a Media Channel via Slack Block Kit,
    *   *When* they access the "Assign Avatar" section,
    *   *Then* they are presented with a dropdown of their `Ready` status `CreatorPersonas` to select and save to the channel.

**FR-1.05: Multi-Channel Prompt Selection**
*   **Priority:** SHALL
*   **Description:** Users must be able to select which Media Channel they are targeting when submitting a prompt.
*   **Acceptance Criteria:**
    *   *Given* a user has multiple configured Media Channels,
    *   *When* they submit a prompt,
    *   *Then* the system defaults to their "Primary" channel unless they use an explicit Slack command (e.g., `/omni-create [channel_name] [prompt]`), at which point the system applies that specific channel's persona and pacing rules.

**FR-1.06: Persona & Channel Deletion (Data Retention)**
*   **Priority:** SHOULD
*   **Description:** Users shall be able to delete a `CreatorPersona` or Media Channel.
*   **Acceptance Criteria:**
    *   *Given* a user selects "Delete Persona" via the Slack management modal,
    *   *When* they confirm the destructive action,
    *   *Then* the system hard-deletes the associated image and audio files from S3 buckets, removes the ElevenLabs/HeyGen reference IDs, and marks the MongoDB record as `deleted`.

### 2. Core AI Workflow: Ideation & Storyboarding

**FR-2.01: Slack Input Ingestion**
*   **Priority:** SHALL
*   **Description:** The system shall listen to a designated Slack channel and ingest raw text prompts provided by authenticated users to initiate a `ProductionJob`.
*   **Acceptance Criteria:**
    *   *Given* a user posts a message in the configured Slack channel,
    *   *When* the webhook triggers `POST /slack/events`,
    *   *Then* the system verifies the HMAC signature, acknowledges the webhook within 3 seconds, and queues the prompt via RabbitMQ.
*   **API Contract Sketch:**
    *   `POST /slack/events`
    *   *Request Body:* `{ "token": "...", "event": { "type": "message", "text": "idea text", "user": "U123" } }`
    *   *Response:* `200 OK` (Empty body, synchronous acknowledgement).

**FR-2.02: Intent & Empty Prompt Handling**
*   **Priority:** SHALL
*   **Description:** The system's agent orchestrator shall evaluate incoming Slack messages to determine if there is sufficient intent to create a video.
*   **Acceptance Criteria:**
    *   *Given* a user sends a greeting or vague message (e.g., "hello" or "make a video"),
    *   *When* the CrewAI Slack Interpreter analyzes it,
    *   *Then* the system shall reply in the Slack thread asking for clarification, without advancing the `JobState` to `Refining` or incurring generation costs.

**FR-2.03: Platform-Specific Storyboard Generation**
*   **Priority:** SHALL
*   **Description:** The CrewAI "Idea Refiner" and "Storyboard Agent" (powered by Gemini) shall parse the validated input and generate a JSON-structured storyboard optimized for the requested platform.
*   **Acceptance Criteria:**
    *   *Given* a prompt targeting "TikTok",
    *   *When* the Storyboard Agent processes it,
    *   *Then* the output must strictly adhere to a JSON schema featuring scene durations of 3-8 seconds and a distinct visual hook in Scene 1. If targeting "YouTube", it must generate cohesive continuous scenes for durations up to 15 minutes.

**FR-2.04: Historical Tone Adaptation**
*   **Priority:** SHOULD
*   **Description:** The Idea Refiner agent shall reference past successful outputs to mimic the creator's voice.
*   **Acceptance Criteria:**
    *   *Given* a user has previously completed `ProductionJobs` for a specific Media Channel,
    *   *When* generating a new storyboard,
    *   *Then* the CrewAI Idea Refiner agent shall retrieve the textual transcripts of the last 3 approved jobs from MongoDB and use them as few-shot examples to align the new script's tone and vocabulary.

### 3. Human-in-the-Loop (HITL) & Interaction

**FR-3.01: Block Kit Storyboard Presentation**
*   **Priority:** SHALL
*   **Description:** The system shall convert the JSON storyboard output into a readable Slack Block Kit message posted as a threaded reply to the user's original prompt.
*   **Acceptance Criteria:**
    *   *Given* the Storyboard Agent successfully generates a JSON storyboard,
    *   *When* the `JobState` transitions to `PendingReview`,
    *   *Then* a Slack message containing the script, scene pacing, and interactive buttons (`[Approve]`, `[Make it Punchier]`, `[Cancel]`) is posted to the thread.

**FR-3.02: Thread-Based Iteration (Conversational Edits)**
*   **Priority:** SHALL
*   **Description:** Users shall be able to modify the storyboard draft by replying directly to the Slack thread with conversational text or clicking the "Make it Punchier" button.
*   **Acceptance Criteria:**
    *   *Given* the system is in `PendingReview` state,
    *   *When* the user replies in the thread (e.g., "Change the tone to be more professional"),
    *   *Then* the CrewAI orchestrator updates the JSON storyboard based on the feedback and posts an updated Block Kit message to the thread.

**FR-3.03: Execution Approval Gate**
*   **Priority:** SHALL
*   **Description:** The system shall strictly prevent any external rendering API calls until the user explicitly clicks the `[Approve]` Block Kit button.
*   **Acceptance Criteria:**
    *   *Given* a storyboard is presented in Slack,
    *   *When* the user clicks `[Approve]`,
    *   *Then* the `JobState` updates to `ApprovedForRender`, the Slack UI updates to indicate rendering has started, and a render task is pushed to RabbitMQ.
*   **API Contract Sketch:**
    *   `POST /slack/interactions`
    *   *Request Body:* URL-encoded payload containing `payload={"type":"block_actions","actions":[{"action_id":"approve_render"}]}`
    *   *Response:* `200 OK` (Empty body).

### 4. Generation & Quality Assurance

**FR-4.01: Audio Synthesis Integration (ElevenLabs)**
*   **Priority:** SHALL
*   **Description:** The system shall send the approved dialogue to the ElevenLabs API, mapped to the user's pre-configured voice clone.
*   **Acceptance Criteria:**
    *   *Given* a job enters `AudioGenerating` state,
    *   *When* the ElevenLabs API successfully returns an MP3 payload,
    *   *Then* the system transitions to `VideoGenerating` state and initiates the HeyGen workflow.

**FR-4.02: Video Rendering Integration (HeyGen)**
*   **Priority:** SHALL
*   **Description:** The system shall orchestrate the HeyGen API using the generated MP3 and the user's associated visual avatar ID.
*   **Acceptance Criteria:**
    *   *Given* the `RenderTask` has an audio file and an Avatar ID,
    *   *When* the HeyGen API is called,
    *   *Then* the system safely queues the request and listens for a signed, asynchronous HeyGen completion webhook.
*   **API Contract Sketch:**
    *   `POST /api/v1/webhooks/heygen`
    *   *Headers:* `X-Signature: <hmac_hash>`
    *   *Request Body:* `{ "event": "video_success", "video_id": "string", "video_url": "https://..." }`
    *   *Response:* `200 OK` (Idempotent success acknowledgement).

**FR-4.03: Post-Render Vision QA**
*   **Priority:** SHOULD
*   **Description:** The system shall automatically validate the final rendered video using Clip+ViT to prevent "uncanny" visual anomalies before delivery.
*   **Acceptance Criteria:**
    *   *Given* the HeyGen webhook returns a successful video URL,
    *   *When* the system downloads the MP4,
    *   *Then* it runs Clip+ViT against sampled frames. If Clip+ViT-derived metrics for lip-sync accuracy fall below 85% OR facial distortion exceeds 2 standard deviations from baseline source images, the `RenderState` transitions to `Failed`.

### 5. Delivery & Notifications

**FR-5.01: Asynchronous State Pings**
*   **Priority:** SHALL
*   **Description:** The system shall provide proactive Slack updates to prevent user anxiety regarding long-running render tasks.
*   **Acceptance Criteria:**
    *   *Given* a `RenderTask` has been in `VideoGenerating` state for > 5 minutes,
    *   *When* the cron watcher detects the delay,
    *   *Then* the system posts an ephemeral message to the Slack thread: "Your video is safely queued and rendering. Will ping you when it's done."

**FR-5.02: Final MP4 Delivery**
*   **Priority:** SHALL
*   **Description:** The system shall deliver the final rendered video directly into the original Slack thread context.
*   **Acceptance Criteria:**
    *   *Given* the `RenderState` transitions to `Completed` and QA checks pass,
    *   *When* the file size is under Slack's 1GB upload limit,
    *   *Then* the system uploads the MP4 directly to the Slack thread.
    *   *If* the file exceeds the 1GB limit, the system shall provide a secure, time-limited (24-hour expiry) signed S3 download link in the thread.

## Non-Functional Requirements

### 1. Performance & Latency Requirements

**NFR-1.01: Synchronous Webhook Acknowledgement**
*   **Description:** The FastAPI Gateway must acknowledge all incoming Slack webhooks (Events API and Interactions API) with an HTTP 200 OK within 3.0 seconds to prevent Slack from retrying the payload and causing duplicate job creation.
*   **Metric:** P99 latency for `/slack/events` and `/slack/interactions` endpoints MUST be < 2.5 seconds.
*   **Implementation:** All heavy computational tasks (LLM generation, database writes) must be immediately offloaded to RabbitMQ before the HTTP response is returned.

**NFR-1.02: Ideation Workflow Velocity**
*   **Description:** The system must process a raw user prompt, execute the CrewAI multi-agent ideation workflow (Idea Refiner + Storyboard Agent), and return the Block Kit storyboard draft to the Slack thread rapidly.
*   **Metric:** The time from Slack prompt ingestion to the initial `PendingReview` Block Kit message delivery MUST be < 5.0 minutes for 95% of requests.

**NFR-1.03: Rendering Queue Transparency**
*   **Description:** The system must proactively manage user expectations during long-running, non-deterministic third-party rendering processes.
*   **Metric:** If a `RenderTask` remains in the `VideoGenerating` state for > 5.0 minutes, the system MUST push an asynchronous status update to the Slack thread within 30 seconds of that threshold being crossed.

### 2. Reliability & Resilience

**NFR-2.01: External API Fault Tolerance**
*   **Description:** The asynchronous rendering pipeline must gracefully handle intermittent 5xx errors and rate limits (429s) from ElevenLabs and HeyGen.
*   **Metric:** The RabbitMQ worker nodes MUST implement exponential backoff retries for external API calls, with a maximum of 3 retries per `RenderTask` before routing the message to a Dead Letter Exchange (DLX).

**NFR-2.02: Webhook Idempotency**
*   **Description:** The system must be resilient to duplicate webhook deliveries from HeyGen, ensuring that a video completion event is processed exactly once.
*   **Metric:** The `/api/v1/webhooks/heygen` endpoint MUST utilize a MongoDB `findOneAndUpdate` atomic operation (matching on `heyGenJobId` where `renderState` is not `Completed`) to enforce 100% idempotency under concurrent load.

**NFR-2.03: State Expiration (TTL)**
*   **Description:** The system must automatically clean up abandoned workflows to maintain database performance and prevent state locking.
*   **Metric:** `SlackInteractionSession` documents in MongoDB MUST have a TTL index configured to automatically expire and hard-delete records exactly 30 minutes after `updatedAt` if the user has not clicked `[Approve]` or `[Cancel]`.

**NFR-2.04: High Availability**
*   **Description:** The core API gateway and message brokering infrastructure must maintain high availability during standard business hours.
*   **Metric:** The FastAPI application and RabbitMQ broker MUST maintain a 99.9% uptime SLA, translating to no more than 43.8 minutes of downtime per month.

### 3. Scalability & Throughput

**NFR-3.01: Concurrent Video Rendering**
*   **Description:** The system must support the capacity required for digital agencies managing multiple clients simultaneously during the MVP phase.
*   **Metric:** The asynchronous execution layer MUST support a minimum of 10 concurrent `ProductionJobs` (from prompt ingestion to HeyGen rendering) per agency workspace without exceeding the 5-minute ideation latency target (NFR-1.02).

**NFR-3.02: Database Connection Pooling**
*   **Description:** The FastAPI application must handle sudden bursts of webhook traffic (e.g., multiple HeyGen renders completing simultaneously) without exhausting database connections.
*   **Metric:** The application MUST utilize MongoDB connection pooling configured to support a minimum of 100 concurrent webhook deliveries without connection starvation.

### 4. Security & Data Privacy

**NFR-4.01: Slack Request Verification**
*   **Description:** The system must strictly authorize all incoming requests from the Slack workspace to prevent spoofing or unauthorized job creation.
*   **Metric:** 100% of requests to `/slack/*` endpoints MUST be verified using HMAC-SHA256 signature validation against the `X-Slack-Signature` header and the application's `SLACK_SIGNING_SECRET`. Requests older than 5 minutes (via `X-Slack-Request-Timestamp`) MUST be rejected to prevent replay attacks.

**NFR-4.02: Vendor Webhook Verification**
*   **Description:** The system must authenticate incoming payloads from HeyGen to prevent malicious actors from altering database states or injecting malicious video links.
*   **Metric:** 100% of requests to `/api/v1/webhooks/heygen` MUST be verified using the specific `X-Signature` HMAC hash provided by the vendor.

**NFR-4.03: Avatar Media Encryption & Access**
*   **Description:** Highly sensitive user data (facial images and voice clones) must be protected from public exposure.
*   **Metric:** All `CreatorPersona` source images and audio files MUST be stored in private AWS S3 buckets (or equivalent), encrypted at rest (AES-256). The FastAPI application and background workers MUST access these assets exclusively via pre-signed URLs with a maximum lifespan of 15 minutes.

### 5. Observability & Telemetry

**NFR-5.01: Structured Logging**
*   **Description:** The system must generate machine-readable logs to facilitate rapid debugging of asynchronous workflows across distributed components.
*   **Metric:** 100% of application logs MUST be output in JSON format and MUST automatically inject the current `jobId`, `slackUserId`, and a distributed `traceId`.

**NFR-5.02: PII Redaction in Telemetry**
*   **Description:** The system must preserve user privacy and intellectual property within logging systems.
*   **Metric:** The application MUST NOT log raw user prompts or generated JSON storyboards. It SHALL only log metadata (e.g., token counts, string lengths, and schema validation success/failure booleans).

**NFR-5.03: Agent Interaction Tracking**
*   **Description:** User interactions with the CrewAI agents must be persisted for future LLM fine-tuning, strictly without disrupting the user flow.
*   **Metric:** 100% of conversational intents and Slack thread replies MUST be written asynchronously to the MongoDB `agentInteraction` collection. Database write failures for this tracking data MUST be caught and ignored, guaranteeing 0% impact on the synchronous user experience.

## Edge Cases

### 1. Input & Ideation Boundary Conditions

**EC-1.01: Vague or Non-Actionable Prompts**
*   **Condition:** The user submits a prompt via Slack that lacks sufficient context to generate a video (e.g., "Make a video about marketing," or "Hello").
*   **System Behavior:** The CrewAI Slack Interpreter agent identifies the `unknown` or insufficient intent. Instead of creating a `ProductionJob` or wasting token/generation costs, it replies in the same Slack thread asking for specific clarification (e.g., "I'd love to help. What specific marketing topic or angle would you like to cover?").

**EC-1.02: Exceeding Max Prompt Length**
*   **Condition:** The user pastes a massive text block (e.g., a 10,000-word blog post) directly into Slack that exceeds the LLM's optimal context window or token limits.
*   **System Behavior:** The API Gateway intercepts the payload size. If the text exceeds 2,500 words, it truncates the input, replies to the user stating the limit, and asks them to provide a condensed summary or focus on a specific section.

**EC-1.03: Inappropriate or NSFW Content Flags**
*   **Condition:** The user submits a prompt containing explicit, violent, or heavily regulated topics (e.g., financial advice, medical claims) that violate HeyGen/ElevenLabs terms of service.
*   **System Behavior:** The Idea Refiner agent, equipped with a moderation prompt, flags the input. The system immediately halts the job, marks `JobState` as `Cancelled`, and sends a private ephemeral Slack message explaining the safety violation.

### 2. Workflow & State Concurrency Scenarios

**EC-2.01: Stale "Approve" Button Clicks**
*   **Condition:** A user receives a Block Kit storyboard draft but ignores it. Two days later, they scroll up and click `[Approve & Render]`.
*   **System Behavior:** The Slack webhook payload hits the interactions endpoint. The system checks MongoDB and finds the `SlackInteractionSession` has expired (TTL is 30 minutes). The system returns an ephemeral message: "This draft has expired. Please submit a new prompt to generate a fresh storyboard."

**EC-2.02: Concurrent Approvals / Race Conditions**
*   **Condition:** Two team members in a shared Slack channel click `[Approve & Render]` on the exact same storyboard draft within milliseconds of each other.
*   **System Behavior:** The `/slack/interactions` endpoint utilizes an atomic MongoDB `findOneAndUpdate` operation checking for `status: "Awaiting"`. The first click transitions the state to `ApprovedForRender` and triggers RabbitMQ. The second click yields a null update, and the system sends an ephemeral message to the second user: "This video is already queued for rendering."

**EC-2.03: "Infinite" Iteration Loops**
*   **Condition:** A user continuously clicks `[Make it Punchier]` or provides endless conversational tweaks in the Slack thread without ever approving.
*   **System Behavior:** The system tracks `iterationCount` in the `SlackInteractionSession` document. Once the count reaches 5, the system posts a final message: "I seem to be having trouble nailing this tone. Please manually edit the script text below and paste it back, and I will render exactly what you provide."

### 3. Generation & Media Boundary Conditions

**EC-3.01: Invalid Avatar Source Imagery**
*   **Condition:** A user uploads 5 photos for a new `CreatorPersona`, but the images contain multiple faces, heavy occlusions (sunglasses/masks), or are extremely low resolution.
*   **System Behavior:** The background Clip+ViT process analyzes the images and scores them <= 0.85. The `AvatarState` transitions to `Failed`. The system sends a direct Slack message to the user: "Your avatar images couldn't be processed. Ensure only one face is visible, without sunglasses or heavy shadows," and prompts a re-upload.

**EC-3.02: Script Exceeds Target Platform Duration**
*   **Condition:** The user demands a highly complex, multi-point argument but specifically requests it be formatted for "TikTok." The generated storyboard dialogue exceeds the hard 60-second limit of YouTube Shorts/TikTok native formats.
*   **System Behavior:** During the Storyboarding phase, the agent validates estimated read time (based on ~150 words per minute). If it exceeds 60 seconds for a short-form target, the agent automatically truncates the script, prioritizes the hook, and adds a note to the Block Kit message: *"Note: I had to condense your points to fit the strict 60-second limit for TikTok. Review the shortened version below."*

**EC-3.03: Slack File Size Upload Limit Exceeded**
*   **Condition:** The user generates a 15-minute, 4K YouTube deep-dive video. The final MP4 returned from HeyGen is 1.2 GB, exceeding Slack's native 1GB file upload limit.
*   **System Behavior:** The final delivery worker checks the file size before attempting the Slack API upload. Detecting it is > 1GB, it bypasses the direct upload, uploads the file to a secure S3 bucket, and posts a Slack message containing a pre-signed, time-limited (24-hour) download link instead.

## Error Handling

### 1. User Input & Configuration Errors

**ERR-1.01: Unprocessable Avatar Media**
*   **Trigger:** A user uploads source images or voice samples that fail Clip+ViT validation (e.g., score <= 0.85 due to multiple faces, blurriness) or fail audio validation (e.g., Signal-to-Noise Ratio (SNR) < 20dB).
*   **System Action:** The `AvatarState` immediately transitions to `Failed`. The files are deleted from the temporary processing bucket to save storage.
*   **User Action:** The system posts a direct Slack message detailing the specific failure reason (e.g., "We detected multiple faces in image 3. Please upload photos containing only your face," or "Background noise is too high.") and provides a button to restart the upload flow.

**ERR-1.02: Missing Persona or Channel Configuration**
*   **Trigger:** A user submits a prompt to generate a video, but they have not completed the `CreatorPersona` setup or assigned a valid `Media Channel`.
*   **System Action:** The API Gateway intercepts the request before passing it to CrewAI. The message is dropped, preventing wasted LLM compute.
*   **User Action:** The system replies in the Slack thread: *"You haven't set up a Persona or selected a Media Channel yet. Use `/omni-profile` to create your avatar and `/omni-channel` to link it to a platform."*

**ERR-1.03: Unauthorized or Expired Access**
*   **Trigger:** A user's OAuth2 token expires, or their Slack user ID is no longer mapped to an active, authorized `UserProfile` in the database.
*   **System Action:** The FastAPI dependency injects an HTTP 401 Unauthorized exception. The job creation is blocked.
*   **User Action:** An ephemeral Slack message is triggered: *"Your session has expired or you are unauthorized. Please re-authenticate using `/omni-login`."*

### 2. Cognitive & Agentic Errors

**ERR-2.01: LLM JSON Formatting Hallucination**
*   **Trigger:** The CrewAI Storyboard Agent returns a script that violates the strict Pydantic JSON schema required for downstream pacing (e.g., missing scene duration timestamps).
*   **System Action:** The system intercepts the `ValidationError`. It automatically re-prompts the Gemini LLM up to three (3) times, injecting the specific formatting error into the context window.
*   **Fallback Strategy:** If it fails 3 times, the system abandons complex scene-by-scene pacing and generates a "continuous scene" fallback script to prevent pipeline lockup.
*   **User Action:** The user receives the Block Kit draft as normal. If the fallback was triggered, an informational note is appended: *"Note: Complex scene pacing failed to generate; this script is formatted as a single continuous take."*

**ERR-2.02: Prompt Context Exhaustion (Agent Drift)**
*   **Trigger:** A user replies to the storyboard draft in the Slack thread more than 5 times without clicking `[Approve]`. At this point, the LLM context window becomes saturated, leading to degraded prompt adherence.
*   **System Action:** The system tracks `iterationCount` in MongoDB. Upon reaching 5, the agent stops generating new LLM completions.
*   **User Action:** The agent posts: *"I seem to be having trouble nailing this tone. Please manually edit the script text below and paste it back, and I will render exactly what you provide."*

### 3. Execution & Third-Party API Errors

**ERR-3.01: Vendor API 5xx / 429 Errors (HeyGen/ElevenLabs)**
*   **Trigger:** A request to ElevenLabs (audio) or HeyGen (video) returns an HTTP 502 Bad Gateway, 503 Service Unavailable, or 429 Too Many Requests.
*   **System Action:** The RabbitMQ worker catches the exception, increments the `retryCount` in MongoDB, and issues a `NACK` (Negative Acknowledgement) to RabbitMQ with an exponential backoff delay (e.g., 30s, 2m, 5m). 
*   **User Action:** If the error is a 429 or transient 5xx, the system remains silent and retries. If `retryCount` exceeds 3, proceed to ERR-3.02.

**ERR-3.02: Terminal Vendor API Failure**
*   **Trigger:** The `RenderTask` `retryCount` reaches 3 due to persistent external API failures.
*   **System Action:** The message is routed to the Dead Letter Exchange (`render_events_dlx`) for engineering review. The `JobState` is marked as `Failed`.
*   **User Action:** The system sends an asynchronous Slack message to the user: *"HeyGen is currently experiencing an outage and we cannot complete your render right now. Your job is saved, and we will automatically retry it once their service is restored."*

**ERR-3.03: "Silent" API Stalls (Hard Timeout)**
*   **Trigger:** HeyGen accepts the render request (HTTP 200), but their asynchronous processing hangs entirely. The transparency ping (NFR-1.03) has fired at 5 minutes, but the completion webhook is never received.
*   **System Action:** A background cron scheduler sweeps the database every 5 minutes. If a `RenderTask` has been stuck in `VideoGenerating` for a hard limit of 60 minutes, it flags the task as `Failed`.
*   **User Action:** The system notifies the user via Slack: *"Your video render timed out at the provider level. We have automatically cancelled this attempt to save your credits. Please click [Retry Render] to try again."*

**ERR-3.04: Insufficient Vendor Credits**
*   **Trigger:** A request to HeyGen or ElevenLabs returns an HTTP 402 Payment Required or a specific JSON payload indicating insufficient account balance.
*   **System Action:** The RabbitMQ worker catches the specific error code. It does *not* retry. It routes the message to the DLX and marks the `JobState` as `Failed_Billing`.
*   **User Action:** The system notifies the user: *"Your [Vendor] account has insufficient credits to complete this render. Please top up your balance and click [Retry Render]."*

### 4. Infrastructure & Internal System Failures

**ERR-4.01: Database Unavailability (MongoDB)**
*   **Trigger:** The FastAPI Gateway or a worker node cannot reach MongoDB Atlas (e.g., connection timeout, DNS failure) when attempting to read/write state.
*   **System Action:** If occurring at the API Gateway during prompt ingestion, the gateway returns an HTTP 503 to Slack. If occurring asynchronously in a worker, the message is `NACK`ed back to RabbitMQ for deferred processing. Critical alerts are sent to the engineering team via Datadog.
*   **User Action:** If the prompt was just submitted, the Slack bot replies: *"Our system is currently experiencing a high load; please try again in a few minutes. Your prompt is saved."*

**ERR-4.02: Message Broker Unavailability (RabbitMQ)**
*   **Trigger:** The FastAPI Gateway successfully validates a Slack webhook but cannot push the message to RabbitMQ.
*   **System Action:** The Gateway logs a critical infrastructure error. Since the HTTP 200 OK was likely already sent to Slack to avoid webhook retries, the payload is written to a local disk fallback queue (or Redis cache if available) for a secondary process to pick up once RabbitMQ is restored.
*   **User Action:** The system utilizes a resilient notification microservice to send a delayed Slack message (e.g., after 30 seconds): *"We received your prompt, but encountered a temporary issue processing it. Our team has been alerted, and your request is safely queued."*

**ERR-4.03: Internal Service Runtime Errors**
*   **Trigger:** A completely unexpected exception occurs within the FastAPI worker node (e.g., an unhandled memory leak, an unexpected response format from Clip+ViT).
*   **System Action:** The global exception handler catches the error, logs the full stack trace with `jobId` and `traceId` to Sentry, and routes the associated RabbitMQ message to the Dead Letter Exchange to prevent the queue from blocking.
*   **User Action:** The system sends a generic fallback message: *"An unexpected error occurred while processing your request. Our engineering team has been notified and is looking into it."*

### 5. Post-Render Validation Errors

**ERR-5.01: Quality Assurance (QA) Rejection**
*   **Trigger:** HeyGen returns a completed MP4, but the internal Clip+ViT vision model detects severe lip-sync desynchronization or uncanny facial warping (score drops below acceptable thresholds).
*   **System Action:** The system blocks the delivery of the MP4. The `RenderState` is marked as `Failed_QA`. 
*   **User Action:** The system posts a Slack message: *"We generated your video, but our automated quality checks caught a visual glitch in the avatar rendering. We've halted delivery to protect your brand. Click [Regenerate] to try again."*

## Success Metrics

*Note: These metrics are often interdependent. For example, a high 'HITL First-Pass Acceptance Rate' is expected to positively influence 'Active Pipeline Velocity' and reduce the 'User "Give-Up" Rate'. They should be analyzed holistically to determine overall product health.*

### 1. Business & Adoption Metrics (The "Why")
These metrics determine if the product is solving the core market problem: scaling video production without proportional headcount increases or margin compression.

*   **MVP Agency Adoption Rate:**
    *   *Target:* Successfully onboard and retain 5 distinct digital marketing agencies on the Slack MVP within the first 6 weeks of launch.
    *   *Definition of "Retained":* An agency is considered retained if at least 2 unique `slackUserId`s from that workspace complete ≥ 1 `ProductionJob` per week, on average, over a 4-week period following their initial setup.
    *   *Measurement:* Track unique Slack Workspace IDs completing the `/omni-profile` setup process and their subsequent `Completed` jobs in MongoDB.
*   **Active Pipeline Velocity (Retention):**
    *   *Target:* A minimum of 3 completed video pipelines (from prompt ingestion to final MP4 delivery) per *active user*, per week.
    *   *Definition of "Active User":* A `slackUserId` who has submitted at least one prompt within the current 7-day rolling window.
    *   *Rationale:* Proves the tool is integrated into their daily/weekly operational workflow, not just a novelty.
    *   *Measurement:* Count of `ProductionJob` documents transitioning to `Completed` status, grouped by active `slackUserId` per 7-day rolling window.
*   **Operational Time Saved:**
    *   *Target:* Achieve an average of < 5 minutes of active user engagement per completed video, demonstrating an estimated 80% reduction from the baseline manual process (which typically requires 10-14 hours per campaign).
    *   *Measurement:* Calculated by comparing the timestamp of initial Slack prompt ingestion to the timestamp of the `[Approve]` button click for successfully completed jobs.
*   **Average Cost Per Completed Video (Cost Efficiency):**
    *   *Target:* Achieve an average cost of < $5.00 per completed `ProductionJob` during the MVP phase.
    *   *Rationale:* Ensures the "low cost to free" mandate is met and protects agency profit margins against scaling costs.
    *   *Measurement:* Aggregate API billing data (Gemini LLM tokens, ElevenLabs characters, HeyGen generation minutes) divided by the total number of `Completed` `ProductionJobs`.

### 2. Content Performance & UX Metrics (The "Magic")
These metrics evaluate the efficacy of the CrewAI agents, the frictionless nature of the Slack interface, and the actual real-world impact of the generated content.

*   **HITL First-Pass Acceptance Rate:**
    *   *Target:* >75% of generated storyboards receive an `[Approve]` click on the very first Block Kit draft presented.
    *   *Rationale:* This is the ultimate measure of our AI's contextual awareness and prompt-refinement capabilities. 
    *   *Measurement:* Track the `iterationCount` in the `SlackInteractionSession` document. Success = `iterationCount == 0` at the time of approval.
*   **Platform Engagement Rate (Post-Publish):**
    *   *Target:* Achieve an average engagement rate (likes, comments, shares) that is equal to or up to 10% higher than manually produced benchmark videos for a given client's specific media channel.
    *   *Rationale:* We must measure outcome, not just output. The AI must scale *authentic* human presence.
    *   *Measurement:* Requires integration with social media platform analytics APIs (e.g., TikTok Creator Center, YouTube Data API) to retrieve engagement data for published videos, linked via `ProductionJob` metadata.
*   **Perceived Naturalness Score (User Satisfaction):**
    *   *Target:* >80% average score (on a 1-5 scale) regarding the perceived authenticity of the generated avatar and voice.
    *   *Measurement:* Implement periodic, asynchronous in-app (Slack-based) micro-surveys asking for feedback on avatar/voice quality after a video is delivered.
*   **Structured Storyboard Fallback Rate:**
    *   *Target:* < 10% of generated storyboards trigger the fallback to a "continuous scene" script.
    *   *Rationale:* A high rate indicates the LLM is failing to consistently generate the required structured JSON output, degrading the "platform-optimized" value proposition.
    *   *Measurement:* Track `ProductionJob` metadata for instances where the `Fallback Strategy` (defined in Error Handling ERR-2.01) is triggered.
*   **User "Give-Up" Rate (Abandonment):**
    *   *Target:* < 10% of initiated `ProductionJobs` expire due to the 30-minute TTL without an `[Approve]` or `[Cancel]` action.
    *   *Measurement:* Monitor MongoDB TTL deletions against total initiated jobs.

### 3. System & Operational Metrics (The "Engine")
These metrics track the health of our decoupled, asynchronous architecture and our ability to manage unreliable third-party rendering APIs.

*   **Successful Render Delivery Rate:**
    *   *Target:* >95% of jobs that reach the `ApprovedForRender` state successfully result in a delivered MP4 (or secure S3 link) to the Slack thread.
    *   *Rationale:* Prevents "System Anxiety." Users must trust that clicking approve guarantees a result.
    *   *Measurement:* The ratio of `ProductionJob` records in `Completed` state versus those in `Failed` state.
*   **Direct Social Media Publishing Success Rate:**
    *   *Target:* >90% of user-initiated direct publishes to social media platforms via Slack successfully complete.
    *   *Measurement:* Track successful HTTP 2xx/201 responses from external social media publishing API endpoints.
*   **Prompt-to-Draft Latency (Ideation Velocity):**
    *   *Target:* As defined in NFR-1.02, the time from Slack prompt ingestion to the initial `PendingReview` Block Kit message delivery must be strictly < 5.0 minutes for 95% of requests.
    *   *Measurement:* Datadog/system logs tracking the delta between the `POST /slack/events` timestamp and the corresponding Slack message API POST timestamp.
*   **Zero Silent Failures (Error Visibility):**
    *   *Target:* 100% of terminal vendor API timeouts or persistent 5xx errors must result in a proactive Slack notification to the user.
    *   *Measurement:* Every message routed to the RabbitMQ Dead Letter Exchange (`render_events_dlx`) must have a corresponding log entry proving a Slack error message was dispatched.
*   **Post-Render QA Rejection Rate (Guardrail Metric):**
    *   *Target:* < 5% of completed HeyGen renders are rejected by the internal Clip+ViT vision validation step.
    *   *Rationale:* While QA protects the user, a high rejection rate means we are burning API costs on failed renders.
    *   *Measurement:* Track the frequency of `RenderState` transitioning to `Failed_QA` in MongoDB. If this spikes, our initial `AvatarState` validation criteria (e.g., Clip+ViT score > 0.85, SNR > 20dB) are too loose.

## Dependencies

### 1. Third-Party API & Model Dependencies

**DEP-1.01: CrewAI & Gemini (Core Ideation)**
*   **Purpose:** The system relies entirely on CrewAI orchestrating the Google Gemini LLM for the "Idea Refiner" and "Storyboard" agents. This translates raw prompts into formatted JSON scripts.
*   **Dependency Risk:** Changes to Gemini's pricing, deprecation of the specific models used (e.g., Gemini 1.5 Pro), or severe API latency will directly halt the ideation phase, resulting in failed `ProductionJobs`.
*   **Mitigation Strategy:** The architectural decoupling via RabbitMQ ensures that LLM timeout failures do not crash the Slack gateway. The CrewAI layer must be abstracted via interfaces to allow for rapid swapping to an alternative LLM (e.g., Claude or OpenAI) if Gemini experiences prolonged downtime.

**DEP-1.02: ElevenLabs (Audio Synthesis)**
*   **Purpose:** Generates ultra-realistic, custom-cloned voice audio from the approved JSON storyboard dialogue.
*   **Dependency Risk:** ElevenLabs enforces strict rate limits and requires high-quality source audio for training. Account credit exhaustion or API outages will completely block the transition from `AudioGenerating` to `VideoGenerating`.
*   **Mitigation Strategy:** Implement exponential backoff retries (max 3) for 429/5xx errors as defined in the Engineering Plan. Ensure clear API contract logging to instantly catch HTTP 402 (Payment Required) errors to alert administration.

**DEP-1.03: HeyGen (Video Rendering)**
*   **Purpose:** The final rendering engine that synchronizes the ElevenLabs audio with the visual `CreatorPersona` avatar.
*   **Dependency Risk:** Video rendering is the most computationally expensive and slowest component. HeyGen API degradation, webhook delivery failure, or unnotified changes to their webhook schema will cause jobs to stall infinitely in the `VideoGenerating` state.
*   **Mitigation Strategy:** The system relies strictly on asynchronous webhooks (`/api/v1/webhooks/heygen`) rather than polling. To mitigate silent webhook drops, the system depends on a 60-minute TTL cron-sweep (defined in Error Handling) to automatically flag and clean up stalled rendering tasks.

**DEP-1.04: Slack API & Block Kit**
*   **Purpose:** Serves as the exclusive user interface (UI) for the MVP, handling authentication, prompt ingestion, HITL approvals via Block Kit, and final MP4 delivery.
*   **Dependency Risk:** The system is bound by Slack's strict 3.0-second webhook acknowledgement window. Furthermore, any changes to Slack's Block Kit schema or changes to their 1GB file upload limit will break core user interaction flows.
*   **Mitigation Strategy:** FastAPI endpoints are engineered to acknowledge payloads synchronously before routing to RabbitMQ. The final delivery worker includes a fallback to S3 URL generation if the MP4 exceeds Slack's file size limits.

### 2. Infrastructure Dependencies

**DEP-2.01: RabbitMQ (Message Broker)**
*   **Purpose:** The critical bridge between the synchronous FastAPI gateway and the asynchronous execution layer. It manages the queueing of LLM requests, rendering tasks, and retry logic.
*   **Dependency Risk:** If RabbitMQ goes down, the FastAPI gateway can no longer ingest new user prompts or process HeyGen webhooks, effectively taking the entire application offline.
*   **Mitigation Strategy:** RabbitMQ must be deployed in a highly available cluster. The FastAPI gateway must be configured to fail gracefully (returning a 503 Service Unavailable to Slack, rather than a silent timeout) if the RabbitMQ connection is refused.

**DEP-2.02: MongoDB Atlas (State Persistence)**
*   **Purpose:** Acts as the single source of truth for user profiles, `AvatarState`, `JobState`, and asynchronous interaction TTLs (e.g., the 30-minute block on stale approvals).
*   **Dependency Risk:** Heavy concurrent webhook traffic (e.g., a batch of HeyGen videos finishing simultaneously) could lead to database connection starvation, crashing the FastAPI application.
*   **Mitigation Strategy:** Rely on proper MongoDB connection pooling within the FastAPI lifecycle and utilize atomic `findOneAndUpdate` operations to ensure strict idempotency and prevent database locks during high-throughput events.

### 3. Upstream Data Dependencies

**DEP-3.01: User-Provided Media Quality**
*   **Purpose:** The `CreatorPersona` requires high-fidelity images and audio to train the ElevenLabs and HeyGen models effectively.
*   **Dependency Risk:** Garbage in, garbage out. If users upload blurry photos with multiple faces or highly compressed, noisy audio, the resulting avatar will fall into the "uncanny valley," violating the core brand-safety value proposition.
*   **Mitigation Strategy:** The system has a hard dependency on the internal Clip+ViT vision model and internal audio SNR validation scripts to act as an automated gateway. The system *must* reject poor-quality media upfront during the `/omni-profile` setup before any API training costs are incurred.

## Assumptions

### 1. User & Behavioral Assumptions

*   **Assumption 1.01: Slack as Primary Workspace**
    *   *Statement:* The target persona (CCO/Agency Owner) spends the majority of their operational day communicating within Slack and prefers interacting with a bot via Slack Block Kit over adopting and learning a new standalone web application.
    *   *Validation:* Monitor the "Give-Up Rate" defined in Success Metrics. If high, it invalidates the assumption that a Slack-first UI is sufficiently frictionless for this complex workflow.
*   **Assumption 1.02: Willingness to Trust HITL Automation**
    *   *Statement:* Users are willing to trust AI with their visual and vocal likeness *provided* there is a mandatory, transparent Human-in-the-Loop (HITL) approval step before any rendering costs or outputs are finalized.
*   **Assumption 1.03: Availability of High-Quality Training Data**
    *   *Statement:* The target users have readily available access to 5-10 high-resolution, front-facing images and clear, low-noise audio samples of their clients/creators to fulfill the `CreatorPersona` setup requirements.

### 2. Technical & Architectural Assumptions

*   **Assumption 2.01: Third-Party API Reliability (HeyGen & ElevenLabs)**
    *   *Statement:* While non-deterministic, HeyGen and ElevenLabs APIs will maintain sufficient uptime and reasonable latency bounds to allow our decoupled asynchronous architecture (via RabbitMQ) to fulfill a 95% successful render delivery rate.
    *   *Validation:* Monitored via the Dead Letter Queue (DLX) hit rate. If vendor APIs consistently fail beyond our 3-retry exponential backoff limit, this assumption is invalidated, requiring a pivot to multi-vendor fallback routing.
*   **Assumption 2.02: Efficacy of LLM JSON Formatting**
    *   *Statement:* The Gemini model, when orchestrated by CrewAI with strict prompting, can reliably and consistently output complex pacing data (scene durations, visual beats) in a valid Pydantic JSON schema format.
*   **Assumption 2.03: Viability of Vision Models for QA**
    *   *Statement:* Clip + ViT models are sophisticated enough to automatically and reliably detect "uncanny valley" anomalies (e.g., severe lip-sync failure or facial distortion) in generated MP4s, acting as a viable substitute for human QA review.

### 3. Business & Market Assumptions

*   **Assumption 3.01: Platform Algorithm Acceptance**
    *   *Statement:* Social media algorithms (TikTok, YouTube Shorts, Threads) do not actively detect and penalize high-quality AI-generated video content in a way that harms organic reach, assuming the content itself is engaging and correctly formatted.
    *   *Validation:* Monitored via the "Platform Engagement Rate" success metric comparing AI output to manual output.
*   **Assumption 3.02: Cost Margins and Viability**
    *   *Statement:* The combined compute and API token costs of Gemini, ElevenLabs, and HeyGen per `ProductionJob` will remain low enough to offer this product at a price point that is highly attractive to agencies while preserving strong software margins.
