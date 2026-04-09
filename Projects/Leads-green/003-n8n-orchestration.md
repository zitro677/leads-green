# ADR-003 — Orchestration with n8n

**Date**: 2025-04  
**Status**: Accepted

---

## Context

Multiple scrapers run on different schedules. Leads need to flow through dedup → enrich → score → CRM → voicebot automatically. We need an orchestrator.

## Decision: n8n (self-hosted on Arkana Tech VPS)

Arkana Tech already runs n8n at `flows.arkanatech.net`. This is the natural choice.

## Key Workflows

### Workflow 1: `scraper_orchestrator`
```
Schedule (every 6h) → HTTP Request each scraper endpoint → 
Aggregate results → Webhook to pipeline
```

### Workflow 2: `lead_intake_pipeline`
```
Webhook (new lead) → Supabase duplicate check → 
IF duplicate: skip
ELSE: Claude API score → Supabase insert → 
IF score ≥ 55: trigger voicebot workflow
ELSE: add to manual review queue → Telegram notification
```

### Workflow 3: `voicebot_caller`
```
Webhook (high-score lead) → Check TCPA window →
IF in window: VAPI outbound call →
  Call complete: save outcome to Supabase → 
  IF booked: Telegram alert + Google Sheets row
  IF no answer: schedule retry (max 3x)
ELSE: queue for next window
```

### Workflow 4: `weekly_report`
```
Schedule (Monday 8am) → Query Supabase stats →
Build summary (leads/source, calls/outcome, bookings) →
Send Telegram report to owner
```

## n8n Custom Nodes Needed
- `hillsborough-permits` — County open data API wrapper
- `vapi-outbound` — VAPI call trigger + status webhook handler
- `lead-scorer` — Claude API scoring call

## Environment Variables Required
```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
VAPI_API_KEY=
VAPI_PHONE_NUMBER_ID=
ANTHROPIC_API_KEY=
SERPAPI_KEY=
APIFY_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
CALENDLY_API_KEY=
```
