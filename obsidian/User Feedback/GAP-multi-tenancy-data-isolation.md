---
tags:
  - user-feedback
  - gap-ticket
status: in-progress
priority: critical
domain: database, api, security
created: 2026-04-14
---

# [GAP] Multi-Tenancy Data Isolation — All Users See All Data

> All enterprise users can see all data regardless of their organization. Data must be scoped by `enterprise_id` and `organization_id`.

---

## Context

- **Discovered by**: User
- **Discovered during**: Production usage review
- **Related page(s)**: [[Database/MongoDB Schema]], [[APIs/API Overview]], [[Architecture/Project Overview]]

---

## Current Behaviour

- All API endpoints return **all data** in the database (no tenant filtering)
- `GET /projects` returns every project from every organization
- `GET /ideas` returns every idea from every organization
- Slack flows operate without org boundaries — a Slack workspace could trigger flows that surface another org's data
- JWT tokens already carry `enterprise_id` and `organization_id` claims, but these are **never used** in any MongoDB query or API filter
- No collection has `enterprise_id` or `organization_id` fields in its schema
- Background schedulers (Confluence publisher) scan globally without tenant scope

---

## Expected Behaviour

- **Organization isolation**: Users in org A can only see/modify org A's data
- **Enterprise visibility**: Enterprise-level (corporate) accounts can see all organizations under that enterprise
- Every document in every collection carries `enterprise_id` + `organization_id`
- Every query includes tenant filtering
- Slack workspace → organization mapping established
- Background processes respect tenant boundaries

---

## Affected Area

- [x] API endpoint (missing / incomplete / wrong response)
- [x] Database schema (missing field / index / collection)
- [x] Slack integration (missing intent / button / handler)
- [ ] Web app (missing page / component / flow)
- [x] Agent / Flow (missing step / wrong output)
- [x] Documentation (missing / outdated)
- [ ] Configuration / Environment

---

## Resolution

_Pending — design document created, awaiting user decision._
