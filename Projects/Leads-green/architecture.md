# Architecture — Green Landscape AI Lead Engine

## 1. System Architecture

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
│  - Apify actors (FB/Reddit/Nextdoor)                │
│  - Hillsborough County open data API               │
└────────────────────────┬────────────────────────────┘
                         │ normalized LeadRaw schema
                         ▼
┌─────────────────────────────────────────────────────┐
│              PIPELINE (Python + n8n)                │
│  1. Deduplication (phone/email/address hash)        │
│  2. Enrichment (reverse phone, address → geo)       │
│  3. AI Scoring (Claude API, 0–100 score)            │
│  4. Routing (score → action queue)                  │
└────────────────────────┬────────────────────────────┘
                         │ enriched Lead schema
                         ▼
┌─────────────────────────────────────────────────────┐
│              SUPABASE (PostgreSQL)                  │
│  leads │ calls │ outcomes │ source_stats │ settings │
└────────────────────────┬────────────────────────────┘
                         │ triggers webhook → n8n
                         ▼
┌─────────────────────────────────────────────────────┐
│              VOICEBOT — JIMMY (VAPI)                │
│  - ElevenLabs voice (warm, professional)            │
│  - Qualification script (3 min max)                 │
│  - Books estimate via Calendly API                  │
│  - Call recording + transcript to Supabase          │
└────────────────────────┬────────────────────────────┘
                         │ outcome
                         ▼
              Telegram Alert to Owner
              Google Sheets CRM export
```

---

## 2. Data Models

### LeadRaw
```python
{
  "source": "hillsborough_permits",
  "source_id": "PERMIT-2025-XXXXX",
  "name": str | None,
  "phone": str | None,
  "email": str | None,
  "address": str,
  "city": "Tampa",
  "zip": str,
  "signal": str,           # raw text that triggered capture
  "signal_type": str,      # "new_construction" | "complaint" | "request" | "listing"
  "scraped_at": datetime,
  "raw_json": dict
}
```

### Lead (enriched)
```python
{
  "id": uuid,
  "source": str,
  "name": str | None,
  "phone": str | None,
  "email": str | None,
  "address": str,
  "lat": float,
  "lon": float,
  "zip": str,
  "property_type": "residential" | "commercial",
  "score": int,            # 0–100
  "score_reason": str,
  "status": "new" | "calling" | "qualified" | "booked" | "lost",
  "assigned_to": str | None,
  "created_at": datetime,
  "updated_at": datetime
}
```

### CallOutcome
```python
{
  "id": uuid,
  "lead_id": uuid,
  "vapi_call_id": str,
  "duration_seconds": int,
  "outcome": "no_answer" | "voicemail" | "not_interested" | "qualified" | "booked",
  "transcript": str,
  "booked_at": datetime | None,
  "created_at": datetime
}
```

---

## 3. Scoring Logic

Leads are scored 0–100. Threshold for voicebot call: **score ≥ 55**.

| Signal | Points |
|---|---|
| New construction permit (irrigation not listed) | +40 |
| New homeowner (listed in last 60 days) | +30 |
| Explicit "irrigation" or "sprinkler" keyword | +25 |
| Tampa ZIP code (service area) | +10 |
| Has phone number | +10 |
| Competitor 1-star review mentioning irrigation | +35 |
| Commercial property | +15 (separate queue) |
| No contact info | −30 |

---

## 4. Infrastructure

| Service | Purpose | Cost/mo |
|---|---|---|
| InterServer VPS | n8n + FastAPI self-hosted | ~$10 |
| Supabase Free/Pro | Database + auth | $0–25 |
| VAPI | Voicebot calls | ~$0.05/min |
| VAPI (OpenAI TTS) | Voice synthesis (built-in) | $0 extra |
| SerpAPI | Google search scraping | ~$50 |
| Apify | Social media scraping | ~$49 |
| Telegram Bot | Notifications | Free |
| **Total** | | **~$114–156/mo** |

vs. $1,000/mo Angie's List.

---

## 5. TCPA Compliance (Florida)

- Only call between **8 AM – 9 PM local time** (TCPA requirement)
- Honor opt-outs immediately — blacklist table in Supabase
- Do not call numbers on the **National Do Not Call Registry**
- Voicebot must identify itself as AI at the start of the call
- Call recordings stored 90 days max

---

## 6. Service Area (Tampa Bay)

Priority ZIPs: 33602–33619, 33629, 33634–33637, 33647  
Secondary: Brandon (33510–33511), Riverview (33569), Wesley Chapel (33543–33544)
