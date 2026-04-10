---
tags:
  - user-feedback
  - gap-ticket
status: open
priority: high
domain: sso
created: 2026-04-10
---

# [GAP] SSO OAuth Key Rotation & Token Refresh Resilience

> App-side SSO fixes are deployed (v0.63.2), but SSO server-side and web app client-side issues remain that cause intermittent login failures.

---

## Context

- **Discovered by**: Agent (log analysis)
- **Discovered during**: SSO OAuth login investigation (v0.63.1 → v0.63.2)
- **Related page(s)**: [[Session Log]], [[SSO API]]

---

## Current Behaviour

1. **Stale public key**: The RSA public key file (`sso_public_key.pem`) was last updated on April 6. Every local JWT decode fails with `InvalidSignatureError`. The app now auto-fetches the key from `SSO_BASE_URL/sso/auth/public-key` on failure (v0.63.2), but there is no proactive rotation mechanism.

2. **Token refresh race condition**: When `/auth/sso/userinfo` returns 401, the web app fires multiple concurrent `/auth/sso/token/refresh` requests. Refresh tokens are single-use — the first request succeeds (200), the second gets 500 from the SSO server (consumed token). This is visible in logs: `POST /auth/sso/token/refresh → 200 (1731ms)` followed immediately by `POST /auth/sso/token/refresh → 500 (1351ms)`.

3. **No JWKS endpoint**: The SSO server does not expose a standard `/.well-known/jwks.json` endpoint. The app must hit `/sso/auth/public-key` (a custom endpoint) and manually save the PEM file to disk.

---

## Expected Behaviour

1. Public key rotation should be **seamless** — either the SSO server provides JWKS, or the app proactively refreshes the key on a schedule.
2. Token refresh should be **atomic** — only one refresh request per expired token.
3. The SSO server should follow standard OAuth 2.0 / OIDC conventions for key discovery.

---

## Affected Area

- [x] API endpoint (missing / incomplete / wrong response)
- [ ] Database schema (missing field / index / collection)
- [ ] Slack integration (missing intent / button / handler)
- [x] Web app (missing page / component / flow)
- [ ] Agent / Flow (missing step / wrong output)
- [ ] Documentation (missing / outdated)
- [x] Configuration / Environment

---

## Recommendations & Suggestion

### R1: SSO Server — Expose JWKS Endpoint

The SSO server should expose a standard `/.well-known/jwks.json` (JSON Web Key Set) endpoint per RFC 7517. This allows all client apps to auto-discover the current signing key and rotate seamlessly without manual PEM file management.

**Action required**: SSO team implements JWKS endpoint. App team updates JWT validation to fetch keys from JWKS (with caching + TTL).

**Your Answer**: <!-- Replace this with your decision -->

---

### R2: Web App — Token Refresh Mutex

The web app should implement a client-side mutex/lock for token refresh. When the first 401 triggers a refresh, all subsequent requests should queue and wait for the refresh to complete, then retry with the new access token. This prevents concurrent refresh requests that waste single-use refresh tokens.

**Action required**: Web app team implements a refresh token mutex (e.g. a Promise-based lock or request interceptor queue in the HTTP client).

**Your Answer**: <!-- Replace this with your decision -->

---

### R3: App — Background Key Refresh Scheduler

Add a background scheduler (daemon thread) that periodically fetches the public key from the SSO server (e.g. every 6 hours). This ensures the local key stays fresh proactively, reducing the first-request latency penalty of on-demand key fetch failures.

**Agent Suggested Answer**: Implement as a daemon thread similar to the existing `token_refresh_scheduler.py` pattern. Fetch every 6 hours + immediate fetch on startup.

**Your Answer**: <!-- Replace this with your decision -->

---

### S1 (Suggestion): Validation Strategy — Local-First vs Remote-First

Currently the app tries local JWT decode first, then falls back to remote introspection. An alternative is to use remote introspection as the primary validation (always authoritative) and local decode only as a fast-path optimization when the key is known-good.

- **Option A**: Keep current local-first strategy (fast path when key is valid, 3-phase fallback handles rotation)
- **Option B**: Switch to remote-first (always authoritative, no key management needed, but adds ~200ms per request)

**Agent Suggested Answer**: **Option A** — the v0.63.2 3-phase fallback handles key rotation gracefully, and local-first avoids the per-request network overhead to the SSO server.

**Your Answer**: <!-- Replace this with your decision -->

---

## Resolution

_Pending user answers to R1–R3 and S1._

---

## Acceptance Criteria

- [ ] R1: SSO server exposes JWKS endpoint (or equivalent standard key discovery)
- [ ] R2: Web app sends at most 1 concurrent token refresh request per session
- [ ] R3: App proactively refreshes public key on a schedule (if JWKS not available)
- [ ] S1: Validation strategy decision recorded and implemented if changed

---

## References

- v0.63.1 session log — initial introspection fix
- v0.63.2 session log — 3-phase validation + auto key fetch
- RFC 7517 (JSON Web Key Set)
- RFC 7662 (OAuth 2.0 Token Introspection)
- Logs: `logs/crewai.log.2026-04-10` — full trace of 401 loop, key rotation errors, concurrent refresh 500s
