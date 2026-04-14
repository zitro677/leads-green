# API Reference — Green Landscape AI Lead Engine

Base URL (local): `http://localhost:8001`  
Base URL (production): `https://api.arkanatech.net`

## Authentication

Most endpoints require one of:
- `X-API-Key: <INTERNAL_API_KEY>` — machine-to-machine (n8n, scrapers)
- `Authorization: Bearer <jwt>` — human users (dashboard)

---

## Health

### `GET /health`
No auth required.

```bash
curl https://api.arkanatech.net/health
```
```json
{"status": "ok", "service": "green-landscape-lead-engine"}
```

---

## Auth

### `POST /auth/login`
```bash
curl -X POST https://api.arkanatech.net/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```
```json
{"access_token": "eyJ...", "token_type": "bearer", "role": "admin"}
```

### `POST /auth/change-password`
Requires JWT Bearer token.
```bash
curl -X POST https://api.arkanatech.net/auth/change-password \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"current_password": "old", "new_password": "new-secure-pass"}'
```

---

## Leads

### `GET /leads`
Requires auth (JWT or API key).

| Param | Default | Description |
|---|---|---|
| `status` | `new` | Filter: new, queued, calling, qualified, booked, lost, exhausted |
| `limit` | `50` | Max results (1–500) |

```bash
curl "https://api.arkanatech.net/leads?status=booked&limit=20" \
  -H "X-API-Key: your-key"
```

### `GET /leads/stats`
```bash
curl "https://api.arkanatech.net/leads/stats?period=7d" \
  -H "X-API-Key: your-key"
```
Periods: `24h`, `7d`, `30d`

### `GET /leads/route`
Optimized field-visit route for no-phone leads.
```bash
curl "https://api.arkanatech.net/leads/route?start=11510+Spring+Hill+Dr+FL&limit=80" \
  -H "X-API-Key: your-key"
```

### `POST /leads/{id}/call`
Trigger VAPI outbound call.
```bash
curl -X POST "https://api.arkanatech.net/leads/LEAD-UUID/call" \
  -H "X-API-Key: your-key"
```
```json
{"status": "calling", "vapi_call_id": "019d..."}
```

### `POST /leads/{id}/sms`
Send intro SMS via Twilio.
```bash
curl -X POST "https://api.arkanatech.net/leads/LEAD-UUID/sms" \
  -H "X-API-Key: your-key"
```

### `POST /leads/{id}/email`
Send intro email via Gmail SMTP.
```bash
curl -X POST "https://api.arkanatech.net/leads/LEAD-UUID/email" \
  -H "X-API-Key: your-key"
```

### `POST /leads/retry-queued`
Fire calls for all queued leads past their `next_call_at`. Runs in background.
```bash
curl -X POST "https://api.arkanatech.net/leads/retry-queued" \
  -H "X-API-Key: your-key"
```
```json
{"status": "started", "message": "Retry run launched in background"}
```

---

## Ingest

### `POST /ingest`
Bulk ingest raw leads from scrapers or n8n.
```bash
curl -X POST https://api.arkanatech.net/ingest \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "leads": [{
      "source": "permits",
      "source_id": "PERMIT-2026-001",
      "name": "John Doe",
      "phone": "8135551234",
      "address": "123 Oak Ave",
      "city": "Tampa",
      "zip_code": "33602",
      "signal": "New pool permit — irrigation likely needed",
      "signal_type": "new_construction",
      "property_type": "residential"
    }]
  }'
```
```json
{"total": 1, "inserted": 1, "duplicates": 0, "discarded": 0, "queued_for_call": 1, "queued_for_review": 0, "errors": 0}
```

---

## Scraper Triggers

### `POST /scrape/{source}`
Trigger a scraper in background. Sources: `permits`, `new_owners`, `facebook_groups`
```bash
curl -X POST "https://api.arkanatech.net/scrape/permits" \
  -H "X-API-Key: your-key"
```

---

## Score

### `POST /score`
Score a single lead without saving.
```bash
curl -X POST https://api.arkanatech.net/score \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"source": "permits", "signal_type": "new_construction", "zip_code": "33602", "phone": "8135551234"}'
```
```json
{"score": 75, "reason": "New construction + Tampa ZIP + phone present", "action": "call"}
```

---

## VAPI Webhook

### `POST /vapi/outcome`
Called by VAPI after each call ends. Returns immediately, processes in background.
```json
{"status": "accepted"}
```
Non-end-of-call events return `{"status": "ignored"}`.
