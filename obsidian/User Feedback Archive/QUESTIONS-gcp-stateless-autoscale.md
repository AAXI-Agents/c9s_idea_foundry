---
tags:
  - user-feedback
  - decisions
status: resolved
related: GAP-infra-gcp-stateless-autoscale
created: 2026-04-12
---

# Decisions: GCP Stateless Auto-Scale

> Open questions for the GCP statelessness audit. Please tick your preferred option for each question.

---

## Q1: How should the Slack token refresh race condition (CRITICAL) be fixed?

> Two instances refreshing the same single-use Slack token simultaneously will permanently brick it. How should we prevent this?

- [ ] **Option A: CAS Guard (compare-and-swap)** — Use `find_one_and_update` with `refresh_token` filter — if another instance already refreshed, update is a no-op, reload from DB. Simplest approach, no extra infrastructure. Relies on MongoDB atomicity.

- [ ] **Option B: MongoDB Distributed Lock** — Create a TTL-indexed lock document in MongoDB before refreshing. Only the instance holding the lock refreshes. Adds a lock collection but guarantees exclusivity. Slight overhead per refresh cycle.

- [ ] **Option C: Leader Election** — Designate one instance as the token refresh leader via MongoDB-based lease. Only the leader runs the scheduler. Most robust but most complex to implement and maintain.

- [x] **Suggested: CAS Guard + Leader Lease** — Use CAS guard (Option A) as the safety net, plus a lightweight MongoDB lease so only one instance actively schedules refreshes. Belt-and-suspenders: the lease reduces contention, the CAS prevents damage if the lease fails.

---

## Q2: How should startup recovery races be fixed?

> Multiple instances starting simultaneously each run startup recovery, causing duplicate Confluence publishes and Jira tickets. How should we prevent this?

- [ ] **Option A: Atomic Claim Pattern** — Use `find_one_and_update` to atomically set a `claiming_instance` flag before publishing/delivering. Only the instance that wins the claim proceeds. Minimal code change, proven pattern.

- [ ] **Option B: Separate Init Job** — Move startup recovery to a Cloud Run job or init container that runs once before scaling. Clean separation of concerns but adds deployment complexity and a new service to manage.

- [ ] **Option C: MongoDB Leader Lease** — Only the instance holding a lease runs startup recovery. Reuses the leader election pattern if implemented for Q1. Adds complexity but centralizes coordination.

- [x] **Suggested: Atomic Claim + Idempotency Guards** — Use atomic claim (Option A) plus add idempotency checks (e.g., check `confluence_url` already set before publishing, check Jira tickets already exist before creating). Defense in depth with minimal complexity. Even if a claim leaks, no duplicate work occurs.

---

## Q3: How should PRD output files (`output/prds/`) be handled for stateless containers?

> PRD markdown/HTML are written to local `output/` directory. Local disk is ephemeral in containers. MongoDB already has all the data. What should we do?

- [ ] **Option A: GCS FUSE Mount** — Mount a GCS bucket at `output/` via GCS FUSE. Minimal code changes — existing file I/O works as-is. Slight latency overhead on file operations. Requires FUSE driver in container.

- [x] **Option B: Direct GCS Writes** — Refactor file I/O to use GCS client library (`google-cloud-storage`). Clean cloud-native approach but requires code changes everywhere files are written/read. Adds GCP dependency.

- [ ] **Option C: MongoDB-Only (eliminate local files)** — Serve outputs directly from MongoDB, remove local file writes entirely. Most stateless — zero filesystem dependency. Requires new API endpoint for file serving and refactoring of output generation.

- [ ] **Suggested: MongoDB-Only + On-Demand GCS Export** — Eliminate local file writes (Option C) for day-to-day operation. Add an optional GCS export endpoint for bulk download/archival when needed. Best of both worlds: fully stateless by default, cloud storage available on demand.

---

## Q4: How should logging be configured for GCP auto-scaled containers?

> Logs currently go to local `logs/crewai.log.*` files, which are split across instances and lost on termination.

- [ ] **Option A: Stdout JSON Logging** — Output structured JSON to stdout in production. GCP Cloud Logging picks this up automatically with zero config. Keep file logging for local dev via env var toggle. Simplest and most portable approach.

- [ ] **Option B: Cloud Logging Client Library** — Use `google-cloud-logging` Python client for direct integration. Richer metadata (trace IDs, labels, severity mapping) but adds a dependency and GCP coupling. Slightly harder to test locally.

- [ ] **Option C: Keep File Logging + Sidecar** — Keep current file logging unchanged, add a logging sidecar container (Fluentd/Fluent Bit) to ship logs from the volume. Zero code changes but adds deployment complexity and a sidecar per instance.

- [x] **Suggested: Stdout JSON + Optional Cloud Logging** — Default to stdout JSON (Option A) with an env var `LOG_TARGET=cloud` to enable Cloud Logging client (Option B) for teams that want richer metadata. Most flexible — works in any environment, optionally enhanced on GCP.

---

## Q5: Which GCP compute service should be the deployment target?

> The application needs auto-scaling, health checks, and support for background PRD flow execution.

- [ ] **Option A: Cloud Run** — Fully managed, scales to zero, pay-per-request. Best for HTTP workloads. Simpler ops. Limitation: 60-min max request timeout, no persistent background threads (scheduler must be adapted). Cheapest at low-to-medium scale.

- [ ] **Option B: GKE Autopilot** — Managed Kubernetes with auto-scaling. Supports background threads, long-running processes, persistent volumes, and leader election natively. More ops overhead but most flexible. Best for complex workloads.

- [ ] **Option C: Compute Engine MIG** — Managed Instance Group with auto-scaling. Most control — supports everything including persistent disks, custom networking, any process model. Highest ops burden. Best if you need VM-level control.

- [x] **Suggested: Cloud Run + Cloud Tasks for Background Work** — Use Cloud Run for the API server (auto-scales, stateless). Offload long-running PRD flows to Cloud Tasks or Cloud Run Jobs triggered by the API. Keeps the API fast-scaling and stateless while supporting long-running work beyond the 60-min limit. Token refresh scheduler replaced by Cloud Scheduler calling a refresh endpoint.

---

## How to Respond

Tick one checkbox per question above. If none of the options fit, add a comment below the question with your preference. Once all questions are answered, this file will be updated to `status: resolved` and implementation will proceed.
