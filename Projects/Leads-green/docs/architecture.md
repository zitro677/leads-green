# Architecture — Green Landscape AI Lead Engine
> Last updated: 2026-04-13

## 1. System Overview

```
┌─────────────────────────────────────────────────────┐
│                   LEAD SOURCES                      │
│  Permits │ Zillow │ FB Groups │ Reddit │ SERP │ GMaps│
└────────────────────────┬────────────────────────────┘
                         │ raw leads (JSON)
                         ▼
┌─────────────────────────────────────────────────────┐
│              SCRAPER ENGINE (Python)                │
│  - Playwright (JS-heavy sites)                      │
│  - BeautifulSoup4 (static HTML)                     │
│  - SerpAPI (Google local intent)                    │
└────────────────────────┬────────────────────────────┘
                         │ normalized LeadRaw
                         ▼
┌─────────────────────────────────────────────────────┐
│              PIPELINE (Python)                      │
│  1. Dedup (source+id, phone hash, exhausted block)  │
│  2. Enrichment (reverse geocode, phone lookup)      │
│  3. Scoring (rule-based, 0–100)                     │
│  4. Routing (score ≥ 55 → call queue)               │
└────────────────────────┬────────────────────────────┘
                         │ enriched lead
                         ▼
┌─────────────────────────────────────────────────────┐
│              SUPABASE (PostgreSQL)                  │
│  leads │ call_outcomes │ dnc_list │ users           │
└────────────────────────┬────────────────────────────┘
                         │ leads with status=queued
                         ▼
┌─────────────────────────────────────────────────────┐
│              VOICEBOT — JIMMY (VAPI)                │
│  - Outbound call via VAPI + ElevenLabs voice        │
│  - Qualifies: property type, urgency, budget        │
│  - Outcome webhook → FastAPI → Supabase update      │
│  - Retry: 2 attempts, 24h apart                     │
│  - After 2 failures → exhausted (blocked from dedup)│
└────────────────────────┬────────────────────────────┘
                         │ outcome
                         ▼
              ┌──────────────────────┐
              │  booked → appointment_at stored    │
              │  not_interested → DNC added        │
              │  no_answer/voicemail → retry queue │
              └──────────────────────┘
                         │
                         ▼
              Telegram notification to owner
```

## 2. Authentication

Two auth mechanisms coexist:

| Mechanism | Header | Used by |
|---|---|---|
| API Key | `X-API-Key: <key>` | n8n, scrapers, machine-to-machine |
| JWT Bearer | `Authorization: Bearer <token>` | Dashboard, human users |

JWT issued by `POST /auth/login`. Tokens expire in 24h. Admin role required for destructive actions.

## 3. Lead Lifecycle

```
new → queued → calling → qualified → booked
                      ↘ lost (not_interested, added to DNC)
                      ↘ queued (no_answer/voicemail, next_call_at + 24h)
                      ↘ exhausted (2 failed attempts — permanently blocked)
```

Status `exhausted` is terminal. Dedup blocks re-ingestion by source_id AND phone.

## 4. Database Schema (current)

Table: `leads`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | auto |
| source | TEXT | permits, zillow, facebook, etc. |
| source_id | TEXT | unique per source |
| name, phone, email | TEXT | contact info |
| address, city, zip_code | TEXT | location |
| lat, lon | FLOAT | geocoded |
| property_type | TEXT | residential \| commercial |
| signal, signal_type | TEXT | raw capture trigger |
| score | INTEGER | 0–100 |
| score_reason | TEXT | scoring explanation |
| status | TEXT | new\|queued\|calling\|qualified\|booked\|lost\|exhausted |
| retry_count | INTEGER | VAPI call attempts |
| next_call_at | TIMESTAMPTZ | earliest retry time (null = now) |
| appointment_at | TIMESTAMPTZ | booked appointment datetime |
| appointment_notes | TEXT | call summary / booking notes |
| vapi_call_id | TEXT | VAPI call reference |
| notes | TEXT | manual notes |
| email_sent_at, sms_sent_at | TIMESTAMPTZ | outreach timestamps |

## 5. Scoring Logic

| Signal | Points |
|---|---|
| New construction permit (no irrigation listed) | +40 |
| New homeowner (listed last 60 days) | +30 |
| Explicit "irrigation" / "sprinkler" keyword | +25 |
| Tampa service area ZIP | +10 |
| Has phone number | +10 |
| Competitor 1-star review mentioning irrigation | +35 |
| Commercial property | +15 |
| No contact info | −30 |

Call threshold: **score ≥ 55**. Review threshold: **score ≥ 20**.

## 6. Retry Logic

- Max attempts: **2** (`MAX_CALL_ATTEMPTS` env var)
- Retry gap: **24 hours** (`CALL_RETRY_HOURS` env var)
- After attempt 1 failure (no_answer/voicemail): status = `queued`, `next_call_at` = now + 24h
- After attempt 2 failure: status = `exhausted`
- Exhausted leads blocked from all future scrapes via dedup

## 7. Infrastructure (VPS)

| Service | URL | Container |
|---|---|---|
| FastAPI | api.arkanatech.net | leads-api |
| Dashboard | leads.arkanatech.net | leads-dashboard |
| Reverse proxy + SSL | — | Traefik (existing) |
| Database | Supabase cloud | external |
| Voicebot | VAPI cloud | external |

## 8. TCPA Compliance

- Calls only between **8 AM – 9 PM ET, Monday–Saturday**
- DNC list checked before every call
- Max 2 attempts per lead
- Voicebot identifies itself as AI at call start
