# Pre-Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all code bugs, validate the full API test suite, write complete technical docs, create Docker + Traefik production assets, and push a clean release commit to GitHub.

**Architecture:** FastAPI runs as a Docker container behind Traefik on the VPS. A second Nginx container serves the static dashboard. Traefik routes `api.arkanatech.net` → FastAPI and `leads.arkanatech.net` → dashboard, issuing Let's Encrypt SSL automatically via ACME.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, Docker, Nginx (dashboard only), Traefik (VPS reverse proxy), Supabase (cloud), VAPI

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `src/api/main.py` | Modify | CORS from env var; add `INTERNAL_API_KEY` to required env |
| `frontend/index.html` | Modify | `window.API_BASE` injection point (line 390) |
| `schema.sql` | Modify | Add `next_call_at`, `appointment_at`, `appointment_notes` columns |
| `tools/scripts/test_api.py` | Modify | Port 8001, API key headers, 3 new tests |
| `.env.example` | Modify | Add `ALLOWED_ORIGINS` |
| `docs/architecture.md` | Create | Updated system architecture |
| `docs/api.md` | Create | All endpoints with curl examples |
| `docs/deployment.md` | Create | Docker + Traefik VPS guide |
| `docs/runbooks/operations.md` | Create | Restart, logs, scraper triggers |
| `docs/decisions/001-lead-sources.md` | Move | From root |
| `docs/decisions/002-voicebot-stack.md` | Move | From root |
| `docs/decisions/003-n8n-orchestration.md` | Move | From root |
| `README.md` | Modify | Correct quick-start, Docker commands |
| `Dockerfile` | Create | FastAPI app (playwright-based image) |
| `Dockerfile.dashboard` | Create | Nginx static dashboard with API_BASE injection |
| `docker/nginx-dashboard.conf` | Create | Nginx config for dashboard container |
| `docker/entrypoint.sh` | Create | Injects API_BASE at container start |
| `docker-compose.prod.yml` | Create | Production stack with Traefik labels |

---

## Task 1: Fix CORS — replace hardcoded origins with env var

**Files:**
- Modify: `src/api/main.py`
- Modify: `.env.example`

- [ ] **Step 1: Update `src/api/main.py` CORS middleware**

Replace the hardcoded `allow_origins` list (lines 54–67) with:

```python
import os

# Read ALLOWED_ORIGINS from env — comma-separated list
# Example: "https://leads.arkanatech.net,https://api.arkanatech.net,null"
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost,http://127.0.0.1,http://localhost:8001,http://127.0.0.1:8001,null"
)
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.ngrok-free\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Add `ALLOWED_ORIGINS` to `_REQUIRED_ENV` validation**

In `src/api/main.py`, `ALLOWED_ORIGINS` is optional (has a default), but `INTERNAL_API_KEY` is missing. Update `_REQUIRED_ENV`:

```python
_REQUIRED_ENV = [
    "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "VAPI_API_KEY", "VAPI_ASSISTANT_ID", "VAPI_PHONE_NUMBER_ID",
    "OPENAI_API_KEY",
    "JWT_SECRET_KEY",
    "INTERNAL_API_KEY",
]
```

- [ ] **Step 3: Add `ALLOWED_ORIGINS` to `.env.example`**

Add after the `INTERNAL_API_KEY` line:

```bash
# CORS — comma-separated list of allowed origins (no trailing slashes)
# Development default covers localhost. Production: set your actual domains.
ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,null
# Production example:
# ALLOWED_ORIGINS=https://leads.arkanatech.net,https://api.arkanatech.net
```

- [ ] **Step 4: Verify server reloads without error**

```bash
cd C:/Users/luisz/Projects/Leads-green
curl -s http://127.0.0.1:8001/health
```

Expected: `{"status":"ok","service":"green-landscape-lead-engine"}`

- [ ] **Step 5: Commit**

```bash
git add src/api/main.py .env.example
git commit -m "fix: CORS from ALLOWED_ORIGINS env var, add INTERNAL_API_KEY to startup validation"
```

---

## Task 2: Fix Frontend — configurable API base URL

**Files:**
- Modify: `frontend/index.html` (line 390)

- [ ] **Step 1: Add `window.API_BASE` injection point in `<head>`**

In `frontend/index.html`, add this as the FIRST `<script>` tag inside `<head>` (before Tailwind/Alpine):

```html
<!-- API base URL — overridden at runtime by Nginx entrypoint in production -->
<script>window.API_BASE = null;</script>
```

- [ ] **Step 2: Change `const API` to read from `window.API_BASE`**

On line 390, change:
```javascript
const API = 'http://127.0.0.1:8001'
```
To:
```javascript
const API = window.API_BASE || 'http://127.0.0.1:8001'
```

- [ ] **Step 3: Verify dashboard still loads locally**

Open `frontend/index.html` in a browser (file:// or via server). Confirm leads board loads and shows data from `http://127.0.0.1:8001`.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "fix: make API base URL configurable via window.API_BASE for Docker deployment"
```

---

## Task 3: Fix `schema.sql` — add missing columns

**Files:**
- Modify: `schema.sql`

- [ ] **Step 1: Add `next_call_at` column to leads table definition**

In `schema.sql`, after `retry_count INTEGER DEFAULT 0,` add:

```sql
    next_call_at TIMESTAMPTZ,           -- earliest retry timestamp (null = call immediately)
    appointment_at TIMESTAMPTZ,         -- booked appointment date/time
    appointment_notes TEXT,             -- summary/notes from VAPI call for the appointment
```

- [ ] **Step 2: Update the status comment to include exhausted**

Change:
```sql
    status TEXT DEFAULT 'new',      -- "new" | "queued" | "calling" | "qualified" | "booked" | "lost" | "exhausted"
```
(already correct — verify it matches)

- [ ] **Step 3: Add index for retry scheduling**

After the existing indexes block, add:

```sql
CREATE INDEX idx_leads_next_call_at ON leads(next_call_at)
    WHERE status = 'queued' AND next_call_at IS NOT NULL;
```

- [ ] **Step 4: Commit**

```bash
git add schema.sql
git commit -m "fix: schema.sql reflects current DB state including migrations 003 and 004"
```

---

## Task 4: Fix `test_api.py` — port, auth headers, new tests

**Files:**
- Modify: `tools/scripts/test_api.py`

- [ ] **Step 1: Change default BASE_URL to port 8001**

Line 18, change:
```python
BASE_URL = "http://localhost:8000"
```
To:
```python
BASE_URL = "http://localhost:8001"
```

Also update the startup error message (line 248):
```python
print(f"  uvicorn src.api.main:app --reload --port 8001\n")
```

- [ ] **Step 2: Add API key constant and inject into all requests**

After `BASE_URL`, add:
```python
API_KEY = "gl-lead-engine-2026"
AUTH_HEADERS = {"X-API-Key": API_KEY}
```

Then update every `httpx.get` and `httpx.post` call to include `headers=AUTH_HEADERS`. For example:
```python
# test_health — no auth needed, but harmless to include
resp = httpx.get(f"{BASE_URL}/health", timeout=10)

# test_score_high
resp = httpx.post(f"{BASE_URL}/score", json=payload, headers=AUTH_HEADERS, timeout=10)

# test_leads_list
resp = httpx.get(f"{BASE_URL}/leads", params={"status": "new"}, headers=AUTH_HEADERS, timeout=10)

# test_leads_list_queued
resp = httpx.get(f"{BASE_URL}/leads", params={"status": "queued", "limit": 10}, headers=AUTH_HEADERS, timeout=10)

# test_ingest_valid
resp = httpx.post(f"{BASE_URL}/ingest", json=payload, headers=AUTH_HEADERS, timeout=30)

# test_ingest_empty
resp = httpx.post(f"{BASE_URL}/ingest", json={"leads": []}, headers=AUTH_HEADERS, timeout=10)

# test_vapi_webhook_ignored
resp = httpx.post(f"{BASE_URL}/vapi/outcome", json=payload, timeout=10)

# test_vapi_webhook_end_of_call
resp = httpx.post(f"{BASE_URL}/vapi/outcome", json=payload, timeout=10)
```

- [ ] **Step 3: Add `test_leads_booked` — verify appointment fields**

```python
def test_leads_booked():
    """GET /leads?status=booked — appointment fields must be present in schema."""
    resp = httpx.get(
        f"{BASE_URL}/leads",
        params={"status": "booked", "limit": 5},
        headers=AUTH_HEADERS,
        timeout=10,
    )
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "leads")
    assert_key(data, "count")
    # If any booked leads exist, verify appointment_at field is present (can be null)
    for lead in data["leads"]:
        if "appointment_at" not in lead and "id" in lead:
            # Field missing entirely from response — DB migration not applied
            raise AssertionError(
                "appointment_at field missing from booked lead — run migration 004"
            )
```

- [ ] **Step 4: Add `test_auth_login` — JWT token returned**

```python
def test_auth_login():
    """POST /auth/login — returns JWT access token."""
    payload = {"username": "admin", "password": "changeme123"}
    resp = httpx.post(f"{BASE_URL}/auth/login", json=payload, timeout=10)
    # Accept 200 (success) or 401 (wrong password — but endpoint is reachable)
    if resp.status_code not in (200, 401):
        raise AssertionError(
            f"Expected 200 or 401 from /auth/login, got {resp.status_code}. Body: {resp.text[:200]}"
        )
    if resp.status_code == 200:
        data = resp.json()
        assert_key(data, "access_token")
        assert_key(data, "token_type")
        assert_key(data, "role")
```

- [ ] **Step 5: Add `test_retry_queued` — background task started**

```python
def test_retry_queued():
    """POST /leads/retry-queued — should start background retry run."""
    resp = httpx.post(
        f"{BASE_URL}/leads/retry-queued",
        headers=AUTH_HEADERS,
        timeout=10,
    )
    assert_status(resp, 200)
    data = resp.json()
    assert_key(data, "status")
    if data["status"] != "started":
        raise AssertionError(f"Expected status='started', got '{data['status']}'")
```

- [ ] **Step 6: Register the three new tests in `main()`**

In the `main()` function, add after `test_vapi_webhook_end_of_call`:
```python
run("GET  /leads?status=booked — appointment fields present", test_leads_booked)
run("POST /auth/login — JWT token returned", test_auth_login)
run("POST /leads/retry-queued — background retry started", test_retry_queued)
```

- [ ] **Step 7: Run the full test suite**

```bash
cd C:/Users/luisz/Projects/Leads-green
conda activate IA
python tools/scripts/test_api.py --base-url http://localhost:8001
```

Expected output — all 12 tests pass:
```
Green Landscape AI Lead Engine — API Tests
Target: http://localhost:8001

Running tests...

  [PASS] GET  /health — liveness check
  [PASS] POST /score — high-quality lead (expect action=call)
  [PASS] POST /score — low-quality lead (expect action=discard)
  [PASS] GET  /leads?status=new — list leads
  [PASS] GET  /leads?status=queued&limit=10 — filtered list
  [PASS] POST /ingest — 1 valid lead
  [PASS] POST /ingest — empty list (expect 400)
  [PASS] POST /vapi/outcome — non-end-of-call event (expect ignored)
  [PASS] POST /vapi/outcome — end-of-call-report (expect accepted)
  [PASS] GET  /leads?status=booked — appointment fields present
  [PASS] POST /auth/login — JWT token returned
  [PASS] POST /leads/retry-queued — background retry started

==================================================
All 12 tests passed.
==================================================
```

If any test fails, fix the underlying issue before proceeding to documentation.

- [ ] **Step 8: Commit**

```bash
git add tools/scripts/test_api.py
git commit -m "fix: test_api.py — port 8001, auth headers, 3 new tests (booked, auth, retry)"
```

---

## Task 5: Write `docs/architecture.md`

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Create the updated architecture doc**

```bash
# Remove outdated root-level file first (content replaced by docs/architecture.md)
# Do NOT delete yet — copy content first
```

Create `docs/architecture.md` with this content:

````markdown
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
````

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: updated architecture.md — auth, retry logic, appointment fields, lifecycle"
```

---

## Task 6: Write `docs/api.md`

**Files:**
- Create: `docs/api.md`

- [ ] **Step 1: Create `docs/api.md`**

````markdown
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
````

- [ ] **Step 2: Commit**

```bash
git add docs/api.md
git commit -m "docs: add complete API reference with curl examples"
```

---

## Task 7: Write `docs/deployment.md`

**Files:**
- Create: `docs/deployment.md`

- [ ] **Step 1: Create `docs/deployment.md`**

````markdown
# Deployment Guide — Green Landscape AI Lead Engine

**Target VPS:** InterServer Ubuntu, `arkanatech.net` (2.135.148.139.172)  
**Pattern:** Docker containers routed by existing Traefik reverse proxy  
**Subdomains:** `api.arkanatech.net` (FastAPI), `leads.arkanatech.net` (dashboard)

---

## Prerequisites on VPS

Already present on the server:
- Docker + Docker Compose
- Traefik container (handles SSL + routing for all services)
- Traefik configured for ACME Let's Encrypt

---

## Step 1: Find Traefik network name

```bash
docker network ls | grep -i traefik
```

Look for the external network Traefik uses (usually `traefik_proxy`, `ai_default`, or similar).  
Update `docker-compose.prod.yml` → `networks.traefik_proxy.name` with the actual name.

To confirm Traefik is on the network:
```bash
docker inspect traefik | grep -A5 Networks
```

---

## Step 2: Clone the repository

```bash
cd /opt
git clone https://github.com/zitro677/green-landscape-ai.git leads-green
cd leads-green
```

---

## Step 3: Create `.env` from template

```bash
cp .env.example .env
nano .env
```

**Required values to fill in:**

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `VAPI_API_KEY` | VAPI API key |
| `VAPI_ASSISTANT_ID` | VAPI assistant ID |
| `VAPI_PHONE_NUMBER_ID` | VAPI phone number ID |
| `OPENAI_API_KEY` | OpenAI key (for scoring) |
| `JWT_SECRET_KEY` | Random 64-char string: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `INTERNAL_API_KEY` | Strong random key for n8n/scrapers |
| `ALLOWED_ORIGINS` | `https://leads.arkanatech.net,https://api.arkanatech.net` |
| `NGROK_URL` | Leave empty in production |
| `APP_ENV` | `production` |

---

## Step 4: Build and start containers

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

---

## Step 5: Verify containers are running

```bash
docker compose -f docker-compose.prod.yml ps
```

Expected:
```
NAME                STATUS    PORTS
leads-api           running   8001/tcp
leads-dashboard     running   80/tcp
```

---

## Step 6: Check API health

```bash
curl https://api.arkanatech.net/health
```

Expected: `{"status":"ok","service":"green-landscape-lead-engine"}`

If SSL not yet provisioned, wait 60 seconds for Traefik ACME challenge to complete.

---

## Step 7: Update VAPI webhook URL

In your VAPI dashboard, update the assistant's Server URL to:
```
https://api.arkanatech.net/vapi/outcome
```

---

## Step 8: Configure retry cron (hourly)

Add a cron job on the VPS to trigger the retry queue every hour during business hours:

```bash
crontab -e
```

Add:
```cron
0 8-21 * * 1-6 curl -s -X POST https://api.arkanatech.net/leads/retry-queued -H "X-API-Key: your-key" > /dev/null 2>&1
```

This runs at the top of every hour from 8AM to 9PM, Monday–Saturday (TCPA window).

---

## Updating the app

```bash
cd /opt/leads-green
git pull
docker compose -f docker-compose.prod.yml build leads-api
docker compose -f docker-compose.prod.yml up -d --no-deps leads-api
```

Zero-downtime: Traefik health-checks the new container before routing traffic.
````

- [ ] **Step 2: Commit**

```bash
git add docs/deployment.md
git commit -m "docs: Docker + Traefik deployment guide for arkanatech.net VPS"
```

---

## Task 8: Write `docs/runbooks/operations.md`

**Files:**
- Create: `docs/runbooks/operations.md`

- [ ] **Step 1: Create `docs/runbooks/operations.md`**

````markdown
# Operations Runbook — Green Landscape AI Lead Engine

## Check system health

```bash
# API liveness
curl https://api.arkanatech.net/health

# Container status
docker compose -f /opt/leads-green/docker-compose.prod.yml ps

# Recent logs
docker compose -f /opt/leads-green/docker-compose.prod.yml logs --tail=50 leads-api
```

---

## Restart the API

```bash
docker compose -f /opt/leads-green/docker-compose.prod.yml restart leads-api
```

---

## View live API logs

```bash
docker compose -f /opt/leads-green/docker-compose.prod.yml logs -f leads-api
```

---

## Trigger scrapers manually

```bash
# Hillsborough building permits (best quality)
curl -X POST https://api.arkanatech.net/scrape/permits \
  -H "X-API-Key: your-key"

# New homeowners (Zillow/public records)
curl -X POST https://api.arkanatech.net/scrape/new_owners \
  -H "X-API-Key: your-key"

# Facebook Groups
curl -X POST https://api.arkanatech.net/scrape/facebook_groups \
  -H "X-API-Key: your-key"
```

Scrapers run in background — check logs for progress.

---

## Trigger retry calls manually

```bash
curl -X POST https://api.arkanatech.net/leads/retry-queued \
  -H "X-API-Key: your-key"
```

---

## Check pipeline stats

```bash
curl "https://api.arkanatech.net/leads/stats?period=7d" \
  -H "X-API-Key: your-key" | python3 -m json.tool
```

---

## Add a lead to DNC manually

```python
# On VPS, in the project directory
cd /opt/leads-green
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from src.persistence.client import add_to_dnc
add_to_dnc('+18135551234', reason='requested')
print('Added to DNC')
"
```

---

## Reset a stuck lead

If a lead is stuck in `calling` status after a VAPI error:

```bash
curl "https://api.arkanatech.net/leads?status=calling&limit=10" \
  -H "X-API-Key: your-key"
```

Then via Supabase dashboard, update the lead's status back to `queued`.

---

## Database migrations

Migrations live in `tools/migrations/`. Apply new ones via **Supabase Dashboard → SQL Editor**.

Current migrations:
- `001_schema.sql` — initial schema (applied at project creation)
- `002_users.sql` — auth users table
- `003_next_call_at.sql` — retry scheduling column
- `004_appointment_fields.sql` — appointment_at, appointment_notes

---

## Emergency: stop all calls

To pause VAPI calls immediately, set `MAX_CALL_ATTEMPTS=0` in `.env` and restart:

```bash
cd /opt/leads-green
echo "MAX_CALL_ATTEMPTS=0" >> .env
docker compose -f docker-compose.prod.yml restart leads-api
```

Revert by removing the line and restarting.
````

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/operations.md
git commit -m "docs: add operations runbook — health check, restart, scrapers, DNC, migrations"
```

---

## Task 9: Move ADRs and update README

**Files:**
- Move: `001-lead-sources.md` → `docs/decisions/001-lead-sources.md`
- Move: `002-voicebot-stack.md` → `docs/decisions/002-voicebot-stack.md`
- Move: `003-n8n-orchestration.md` → `docs/decisions/003-n8n-orchestration.md`
- Modify: `README.md`

- [ ] **Step 1: Move ADR files**

```bash
cd C:/Users/luisz/Projects/Leads-green
cp 001-lead-sources.md docs/decisions/001-lead-sources.md
cp 002-voicebot-stack.md docs/decisions/002-voicebot-stack.md
cp 003-n8n-orchestration.md docs/decisions/003-n8n-orchestration.md
git rm 001-lead-sources.md 002-voicebot-stack.md 003-n8n-orchestration.md
```

- [ ] **Step 2: Overwrite `README.md`**

Replace the full content of `README.md`:

````markdown
# Green Landscape Irrigation — AI Lead Engine

> **Built by Arkana Tech** for Green Landscape Irrigation, Tampa FL  
> Replaces $1,000/mo Angie's List with exclusive, AI-qualified leads + automated voicebot

---

## What It Does

- **Scrapes** public sources (building permits, Zillow, Facebook HOA groups) for irrigation-intent leads
- **Scores** each lead 0–100 using signal-based rules
- **Calls** high-score leads automatically via VAPI voicebot "Jimmy"
- **Books** estimate appointments and notifies the owner via Telegram
- **Dashboard** at `leads.arkanatech.net` shows the full pipeline in real time

---

## Quick Start (Local Development)

```bash
# 1. Clone
git clone https://github.com/zitro677/green-landscape-ai.git
cd green-landscape-ai

# 2. Create conda env and install deps
conda create -n IA python=3.11 -y
conda activate IA
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env — fill in SUPABASE_URL, VAPI keys, OPENAI_API_KEY, JWT_SECRET_KEY, INTERNAL_API_KEY

# 4. Start API
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# 5. Open dashboard
# Open frontend/index.html in your browser (file:// works)

# 6. Run test suite
python tools/scripts/test_api.py --base-url http://localhost:8001
```

---

## Production Deployment (Docker + Traefik)

See `docs/deployment.md` for the full VPS guide.

```bash
# On the VPS
git clone https://github.com/zitro677/green-landscape-ai.git /opt/leads-green
cd /opt/leads-green
cp .env.example .env && nano .env
docker compose -f docker-compose.prod.yml up -d
```

---

## Docs

| Document | Description |
|---|---|
| `docs/architecture.md` | System design, data models, scoring logic |
| `docs/api.md` | All endpoints with curl examples |
| `docs/deployment.md` | VPS setup: Docker + Traefik + SSL |
| `docs/runbooks/operations.md` | Day-to-day ops: restart, logs, scrapers |
| `docs/decisions/` | Architecture Decision Records |

---

## Cost Comparison

| Solution | Monthly Cost | Exclusivity |
|---|---|---|
| Angie's List | $1,000 | ❌ Shared (5–10 competitors) |
| This System | ~$150–250 | ✅ Exclusive |

**Net saving: ~$750–850/month**
````

- [ ] **Step 3: Commit**

```bash
git add docs/decisions/ README.md
git commit -m "docs: move ADRs to docs/decisions/, update README with correct quick-start and Docker commands"
```

---

## Task 10: Create `Dockerfile`

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
# Green Landscape AI Lead Engine — FastAPI container
# Uses Microsoft Playwright base image for scraper support
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ src/
COPY tools/ tools/
COPY schema.sql .
COPY .env.example .

# Default port — override with PORT env var if needed
EXPOSE 8001

# 2 workers: enough for VPS, keeps memory predictable
CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "2", \
     "--log-level", "info"]
```

- [ ] **Step 2: Test the build locally (if Docker Desktop available)**

```bash
cd C:/Users/luisz/Projects/Leads-green
docker build -t leads-api:test .
```

Expected: build completes, no errors. Image will be ~1.8GB (playwright base).

If Docker not available locally, this will be verified on the VPS.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: Dockerfile for FastAPI app (playwright base for scraper support)"
```

---

## Task 11: Create `Dockerfile.dashboard` and Nginx config

**Files:**
- Create: `Dockerfile.dashboard`
- Create: `docker/nginx-dashboard.conf`
- Create: `docker/entrypoint.sh`

- [ ] **Step 1: Create `docker/nginx-dashboard.conf`**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # Serve dashboard SPA
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Health check for Traefik
    location /healthz {
        return 200 'ok';
        add_header Content-Type text/plain;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
}
```

- [ ] **Step 2: Create `docker/entrypoint.sh`**

```bash
#!/bin/sh
# Inject API_BASE into dashboard at container start
# Replaces the null placeholder with the actual API URL from env

API_BASE="${API_BASE:-http://localhost:8001}"

sed -i "s|window.API_BASE = null;|window.API_BASE = '${API_BASE}';|g" \
    /usr/share/nginx/html/index.html

echo "Dashboard starting — API_BASE=${API_BASE}"
exec nginx -g 'daemon off;'
```

- [ ] **Step 3: Create `Dockerfile.dashboard`**

```dockerfile
# Green Landscape Dashboard — Nginx static container
FROM nginx:1.27-alpine

# Copy dashboard files
COPY frontend/ /usr/share/nginx/html/

# Copy Nginx config
COPY docker/nginx-dashboard.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint (injects API_BASE at runtime)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.dashboard docker/
git commit -m "feat: dashboard Docker container with runtime API_BASE injection via Nginx"
```

---

## Task 12: Create `docker-compose.prod.yml`

**Files:**
- Create: `docker-compose.prod.yml`

- [ ] **Step 1: Find the Traefik external network name on the VPS**

On the VPS, run:
```bash
docker network ls
```

Look for the network Traefik belongs to. Common names: `traefik_proxy`, `ai_default`, `proxy`.  
Confirm with:
```bash
docker inspect traefik | python3 -c "import sys,json; c=json.load(sys.stdin)[0]; print(list(c['NetworkSettings']['Networks'].keys()))"
```

Use the result to fill in `docker-compose.prod.yml` below.

- [ ] **Step 2: Create `docker-compose.prod.yml`**

Replace `traefik_proxy` in the networks section with the actual Traefik network name from Step 1.

```yaml
# Production stack — Docker + Traefik
# Deploy: docker compose -f docker-compose.prod.yml up -d
# Update API: docker compose -f docker-compose.prod.yml build leads-api && docker compose -f docker-compose.prod.yml up -d --no-deps leads-api

services:

  leads-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: leads-api
    restart: unless-stopped
    env_file: .env
    environment:
      - APP_ENV=production
      - LOG_LEVEL=info
    labels:
      - "traefik.enable=true"
      # HTTPS router
      - "traefik.http.routers.leads-api.rule=Host(`api.arkanatech.net`)"
      - "traefik.http.routers.leads-api.entrypoints=websecure"
      - "traefik.http.routers.leads-api.tls.certresolver=letsencrypt"
      # HTTP → HTTPS redirect
      - "traefik.http.routers.leads-api-http.rule=Host(`api.arkanatech.net`)"
      - "traefik.http.routers.leads-api-http.entrypoints=web"
      - "traefik.http.routers.leads-api-http.middlewares=redirect-to-https"
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
      # Service port
      - "traefik.http.services.leads-api.loadbalancer.server.port=8001"
    networks:
      - traefik_proxy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  leads-dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    container_name: leads-dashboard
    restart: unless-stopped
    environment:
      - API_BASE=https://api.arkanatech.net
    labels:
      - "traefik.enable=true"
      # HTTPS router
      - "traefik.http.routers.leads-dashboard.rule=Host(`leads.arkanatech.net`)"
      - "traefik.http.routers.leads-dashboard.entrypoints=websecure"
      - "traefik.http.routers.leads-dashboard.tls.certresolver=letsencrypt"
      # HTTP → HTTPS redirect
      - "traefik.http.routers.leads-dashboard-http.rule=Host(`leads.arkanatech.net`)"
      - "traefik.http.routers.leads-dashboard-http.entrypoints=web"
      - "traefik.http.routers.leads-dashboard-http.middlewares=redirect-to-https"
      # Service port
      - "traefik.http.services.leads-dashboard.loadbalancer.server.port=80"
    networks:
      - traefik_proxy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

networks:
  traefik_proxy:
    external: true
    name: traefik_proxy   # ← CHANGE THIS to match your actual Traefik network name
```

> **Important:** Before deploying to VPS, update `networks.traefik_proxy.name` with the actual network name found in Step 1.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat: docker-compose.prod.yml — Traefik labels for api.arkanatech.net + leads.arkanatech.net"
```

---

## Task 13: Final commit and push to GitHub

- [ ] **Step 1: Stage all remaining untracked files**

```bash
cd C:/Users/luisz/Projects/Leads-green
git status --short
```

Stage any remaining untracked files that belong in the repo:
```bash
git add src/api/auth.py
git add src/api/routes/auth.py
git add src/api/routes/admin.py
git add tools/migrations/
git add tools/scripts/seed_test_leads.py
git add src/pipeline/dedup.py
git add src/pipeline/runner.py
git add src/voicebot/caller.py
git add src/api/routes/leads.py
git add src/api/deps.py
git add requirements.txt
```

- [ ] **Step 2: Verify nothing sensitive is staged**

```bash
git diff --cached --name-only
```

Confirm `.env` is NOT in the list. If it appears, remove it:
```bash
git restore --staged .env
```

- [ ] **Step 3: Final commit**

```bash
git commit -m "$(cat <<'EOF'
Pre-deployment: fixes, tests, docs, Docker assets

- CORS driven by ALLOWED_ORIGINS env var (no hardcoded URLs)
- INTERNAL_API_KEY added to startup validation
- Frontend API_BASE injectable at runtime via window.API_BASE
- schema.sql updated: next_call_at, appointment_at, appointment_notes
- test_api.py: port 8001, auth headers, 12 tests all passing
- docs/: architecture, api, deployment, runbooks, decisions
- README.md: correct quick-start + Docker commands
- Dockerfile + Dockerfile.dashboard + docker-compose.prod.yml
- Auth system: JWT login, change-password, admin routes
- Retry logic: 2 attempts, 24h gap, exhausted dedup block
- Booked leads: appointment_at displayed in dashboard

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push origin master
```

- [ ] **Step 5: Verify on GitHub**

Open `https://github.com/zitro677/green-landscape-ai` and confirm:
- Latest commit message matches
- `docs/` folder visible with all files
- `Dockerfile`, `Dockerfile.dashboard`, `docker-compose.prod.yml` present
- `.env` is NOT present

---

## Success Checklist

- [ ] All 12 API tests pass: `python tools/scripts/test_api.py --base-url http://localhost:8001`
- [ ] `ALLOWED_ORIGINS` env var controls CORS
- [ ] `window.API_BASE` in `frontend/index.html` (line ~14 and ~390)
- [ ] `schema.sql` has `next_call_at`, `appointment_at`, `appointment_notes`
- [ ] `docs/architecture.md`, `docs/api.md`, `docs/deployment.md`, `docs/runbooks/operations.md` all exist
- [ ] `Dockerfile` builds successfully
- [ ] `Dockerfile.dashboard` + `docker/entrypoint.sh` + `docker/nginx-dashboard.conf` exist
- [ ] `docker-compose.prod.yml` has correct Traefik labels
- [ ] Clean push to GitHub — no `.env`, no `.venv`
- [ ] Ready for `docker compose -f docker-compose.prod.yml up -d` on VPS
