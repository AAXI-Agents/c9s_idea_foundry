---
tags:
  - api
  - endpoints
  - integrations
---

# [CHANGE] PATCH /user/profile

> **⚠️ This API requires user feedback before implementation.**

Update local user preferences. The Figma design (B7 Settings) shows a profile section with an "Update" button, but user identity data (name, email, avatar) is managed by SSO.

**Method**: `PATCH`
**Path**: `/user/profile`
**Auth**: SSO Bearer token
**Tags**: User

---

## Design Questions for User

1. **Editable fields**: What fields should be editable locally? SSO manages name/email/avatar. Possible local-only fields:
   - `display_name` — override for the SSO name
   - `notification_preferences` — email/Slack notification settings
   - `default_project_id` — default project for new ideas
   - `timezone` — user timezone for timestamps
2. **Storage**: Should we create a new `userPreferences` MongoDB collection, or extend the existing `users` collection?
3. **SSO proxy**: Should any updates be proxied to the SSO service (e.g. display name changes)?
4. **Avatar upload**: Does the Settings page need avatar upload support, or is it SSO-only?
5. **Read endpoint**: Should there be a corresponding `GET /user/profile` to read the current profile + preferences?

---

## Proposed Request

```json
{
  "display_name": "Jane Smith",
  "default_project_id": "proj-abc123",
  "timezone": "America/New_York",
  "notification_preferences": {
    "email_on_completion": true,
    "slack_on_completion": true
  }
}
```

---

## Proposed Response — 200

Returns the updated user profile with both SSO-managed and local fields.

---

## Existing Implementation

- **SSO Webhooks**: `apis/sso_webhooks/` handles `user.created`, `user.updated` events
- **Users Collection**: `mongodb/` — stores user records matched by SSO `sub` claim or email
- **Auth Context**: `require_sso_user` dependency extracts user info from JWT

---

## Change Requests

### Pending

- [ ] Implement after user provides answers to design questions above

### Completed

_No completed change requests._
