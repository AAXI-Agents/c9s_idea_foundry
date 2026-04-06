---
tags:
  - user-feedback
  - gap-ticket
status: in-progress
priority: critical
domain: webapp
created: 2026-04-03
---

# [GAP] Web App Frontend — No Implementation Exists

> A complete design system (1000+ lines, 8 screens, full token system) exists in `obsidian/Website Design/DESIGN.md`, but zero frontend code has been written. This is the largest gap in the project.

---

## Context

- **Discovered by**: Agent (codebase audit)
- **Discovered during**: User Feedback review, 2026-04-03
- **Related page(s)**: [[Website Design/DESIGN]]

---

## Current Behaviour

- 57 REST API endpoints are implemented and tested
- Full design system exists with typography, color, spacing, shadow, motion tokens
- 8 screens documented: Workspace Home, Ideas Board, Idea Detail, PRD Detail, PRD Editor, Publishing, Settings, Activity Feed
- WCAG AA accessibility spec, responsive breakpoints, component patterns all defined
- **No frontend code exists anywhere in the repo**

Users can only interact via Slack or direct API calls.

---

## Expected Behaviour

A web application that consumes the REST API, matching the design system spec, providing the 8 documented screens.

---

## Affected Area

- [ ] API endpoint (missing / incomplete / wrong response)
- [ ] Database schema (missing field / index / collection)
- [ ] Slack integration (missing intent / button / handler)
- [ ] Web app (missing page / component / flow)
- [ ] Agent / Flow (missing step / wrong output)
- [ ] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Questions for User

> Update the **Your Answer** fields below. The agent-suggested answers are prefilled — change any you disagree with.

### Q1: Frontend framework

Which framework should the web app use?

| Option | Pros | Cons |
|--------|------|------|
| **React + Next.js** | Most ecosystem support, SSR, API routes | Heavier bundle |
| **React + Vite** | Fast dev, simple SPA | No SSR |
| **Vue + Nuxt** | Clean syntax, SSR | Smaller ecosystem |
| **Svelte + SvelteKit** | Smallest bundle, fast | Smaller ecosystem |

**Agent Suggested Answer**: **React + Next.js**. The design system is component-based (buttons, cards, modals, sidebars) which maps naturally to React. Next.js provides SSR for SEO, API route proxying for SSO auth, and `app/` router for layouts. The 57 existing REST endpoints can be consumed directly.

**Your Answer**: **React + Next.js**.

---

### Q2: Hosting / deployment

Where will the frontend be deployed?

| Option | Description |
|--------|-------------|
| **A) Same server** | Serve from FastAPI via static files |
| **B) Vercel / Netlify** | Separate deployment, CORS to backend |
| **C) Docker compose** | Frontend + backend in same compose stack |
| **D) Other** | _(specify)_ |

**Agent Suggested Answer**: **C) Docker compose**. The backend already runs in containers. Adding a frontend service to the same compose file keeps everything co-located. Nginx or Traefik can handle routing.

**Your Answer**: B

---

### Q3: Build priority — which screens first?

The design system has 8 screens. Which should be built first?

| Screen | Dependencies |
|--------|-------------|
| Workspace Home | Projects API |
| Ideas Board | Ideas API, Projects API |
| Idea Detail | Ideas API |
| PRD Detail | PRD Flow API |
| PRD Editor | PRD Flow API |
| Publishing | Publishing API |
| Settings | User Profile API *(GAP-api-user-profile-endpoint)* |
| Activity Feed | Flow runs API |

**Agent Suggested Answer**: Build in this order: **Projects → Ideas Board → PRD Detail → Publishing → Settings → Activity Feed → PRD Editor → Workspace Home**. This follows the core user loop (pick project → see ideas → view PRD → publish) and defers the most complex screens (editor, dashboard).

**Your Answer**: there is a seperate web app in the same root folder "c9s_idea_foundry_web". call out any missing design from their "obsidian/screens". Create list design screen gap here.

**Screen Gap Analysis** (DESIGN.md vs `c9s_idea_foundry_web/obsidian/screens/`):

| DESIGN.md Screen | Web App Screen | Status |
|-----------------|----------------|--------|
| Workspace Home | `01-dashboard.md` (Dashboard) | **Covered** — maps to `/` route |
| Ideas Board | `02-ideas.md` (deprecated → Project Detail) | **Partial** — standalone ideas page exists but deprecated; ideas moving into Project Detail view (no screen doc for Project Detail yet) |
| Idea Detail | _(none)_ | **Missing** — no individual idea view screen doc; PRD viewing planned as nested under `/projects/[id]/ideas/[runId]` per ideas.md note |
| PRD Detail | `03-prds.md` (deprecated → Idea Detail) | **Partial** — standalone PRDs page exists but deprecated; PRD viewing planned under Idea Detail |
| PRD Editor | _(none)_ | **Missing** — no screen doc for inline PRD editing (Milkdown editor per D2) |
| Publishing | _(none)_ | **Missing** — no screen doc for Confluence/Jira publishing status and actions |
| Settings | `04-settings.md` | **Covered** — profile + integrations |
| Activity Feed | _(none)_ | **Missing** — no screen doc for agent activity/flow history view |
| _(auth screens)_ | `05-login.md`, `06-register.md`, `07-forgot-password.md` | **Covered** — C9S SSO login, register, forgot password |
| _(missing)_ | _(none)_ | **Missing** — no Project Detail screen doc (the new hub for ideas + PRDs per deprecated notes) |

**Summary**: 5 screen designs are missing from the web app:
1. **Project Detail** — the new hub replacing standalone Ideas/PRDs pages
2. **Idea Detail** — individual idea view with PRD viewer
3. **PRD Editor** — inline Milkdown markdown editing
4. **Publishing** — Confluence/Jira publishing status + actions
5. **Activity Feed** — agent interaction history

---

### Q4: Separate repo or monorepo?

Should the frontend live in this repo or a separate one? The web app already exists at `c9s_idea_foundry_web` as a separate folder.

**Recommendation A**: **Keep as separate repo** — The web app already lives at `c9s_idea_foundry_web` alongside the backend. Keep this separation: independent deploy cycles, framework isolation (Python backend vs TypeScript frontend), and clean CI. OpenAPI spec types can be auto-generated via `openapi-typescript` and published as an npm package or git submodule.

**Recommendation B**: **Move into monorepo** — Add a `webapp/` folder inside this repo. Shared TypeScript types auto-generated from `docs/openapi/openapi.json`. Single CI pipeline for backend + frontend. Atomic commits when API changes require frontend updates. Trade-off: larger repo, mixed Python/Node tooling.

**Recommendation C**: **Hybrid — separate repos with shared type package** — Keep repos separate but create a shared `@c9s/api-types` npm package auto-generated from the OpenAPI spec. Published on version bump. Both repos consume the package. Best of both worlds: independent deploys + type safety, but adds a third publish step.

**Suggestion**: Recommendation A (keep separate) — the web app already exists as a separate project (`c9s_idea_foundry_web`). Restructuring into a monorepo would be disruptive for no practical gain. Use `openapi-typescript` to generate types from the OpenAPI spec and import them directly.

**Your Answer**: <!-- Replace this with your decision -->

---

## Acceptance Criteria

- [ ] User answers all 4 questions above
- [ ] Framework chosen and scaffolded
- [ ] Auth flow integrated with existing SSO
- [ ] At least the first 3 screens functional
- [ ] Design tokens from DESIGN.md exported to CSS/Tailwind
- [ ] CI pipeline includes frontend build + lint

---

## References

- [[Website Design/DESIGN]] — Full design system (1000+ lines)
- [[APIs/API Overview]] — 57 REST endpoints
- [[SSO API]] — 18 SSO endpoints
- [[GAP-api-user-profile-endpoint]] — Settings page dependency

---

## Resolution

- **Version**: 0.55.0
- **Date**: 2026-04-04
- **Summary**: Recorded decisions: React + Next.js (Q1), Vercel deployment (Q2). Added screen gap analysis for Q3 — 5 missing screen designs identified (Project Detail, Idea Detail, PRD Editor, Publishing, Activity Feed). Q4 (monorepo vs separate repo) remains unanswered.
