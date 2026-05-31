# sVault — API Contract

> Owned by `api-engineer`. Consumed by `ui-ux-designer` (frontend calls) and `qa-test-engineer`.
> Append new endpoint blocks as they are built. Do not remove existing entries.

---

## Onboarding — First-run checklist

### GET /api/v1/onboarding/status

**Auth:** Bearer JWT (any authenticated user, no role restriction).
**Scope:** Tenant + accessible org(s) — same as policies/documents.

**Response 200** `OnboardingStatus`

```json
{
  "steps": [
    {
      "key": "provider",
      "label": "Add an insurer/provider",
      "description": "Add at least one insurer or provider to start tracking policies.",
      "done": false,
      "href": "/app/providers"
    },
    {
      "key": "policy",
      "label": "Add your first policy",
      "description": "Create your first insurance policy record.",
      "done": false,
      "href": "/app/policies"
    },
    {
      "key": "document",
      "label": "Upload a policy document",
      "description": "Attach a policy document so your vault is complete.",
      "done": false,
      "href": "/app/policies"
    },
    {
      "key": "alert",
      "label": "Set up renewal alerts",
      "description": "Configure multi-channel alerts so renewals are never missed.",
      "done": false,
      "href": "/app/alerts"
    },
    {
      "key": "team",
      "label": "Invite a teammate",
      "description": "Invite a colleague to collaborate on your policy portfolio.",
      "done": false,
      "href": "/app/settings"
    }
  ],
  "complete": false,
  "completed_count": 0,
  "total": 5
}
```

**Errors:** 401 unauthorized (missing/invalid JWT).

**Step logic (server-computed):**
| key | done = true when |
|-----|-----------------|
| provider | providers count > 0 (tenant-scoped) |
| policy | policies count > 0 (tenant + org-scoped) |
| document | policy_documents count > 0 (tenant + org-scoped) |
| alert | alert_rules count > 0, or alerts count > 0 as fallback |
| team | profiles count > 1, or invitations count > 0 (tenant-scoped) |

---

## Notifications — History feed

### GET /api/v1/notifications/history

**Auth:** Bearer JWT (any authenticated user, no role restriction).
**Scope:** Tenant + accessible org(s) — same as alerts/approvals.

**Query params:**
| param | type | default | max | description |
|-------|------|---------|-----|-------------|
| limit | int | 50 | 200 | Max items per page |
| offset | int | 0 | — | Pagination offset |

**Response 200** `NotificationHistory`

```json
{
  "items": [
    {
      "id": "uuid",
      "type": "alert",
      "title": "Renewal reminder — Fleet Insurance",
      "subtitle": "30d before expiry · email",
      "href": "/app/alerts",
      "created_at": "2026-05-30T10:00:00Z"
    },
    {
      "id": "uuid",
      "type": "approval",
      "title": "Approval pending — Policy renewal",
      "subtitle": "policy",
      "href": "/app/approvals",
      "created_at": "2026-05-29T08:00:00Z"
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 142
}
```

**Differences from bell feed (`GET /notifications`):**
- Includes ALL alerts regardless of status (not just `scheduled`/`sent`)
- Includes ALL approvals regardless of status (not just `pending`)
- Paginated (limit/offset) — no 20-item cap
- No `unread_count` field

**Errors:** 401 unauthorized.

---

## Notifications — Bell feed (existing)

### GET /api/v1/notifications

**Auth:** Bearer JWT (any authenticated user).

**Response 200** `NotificationFeed`

```json
{
  "unread_count": 3,
  "items": [...]
}
```

Items capped at 20 (newest first). `unread_count` capped at 99.
