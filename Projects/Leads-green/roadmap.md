# Implementation Roadmap

## Phase 1 — Foundation (Week 1–2)
**Goal**: Pipeline working with public data sources only

- [ ] Setup Supabase project + create tables (leads, call_outcomes, dnc_list)
- [ ] Implement `BaseScraper` interface (`src/scrapers/base.py`)
- [ ] Build Hillsborough County permits scraper (`src/scrapers/permits.py`)
- [ ] Build basic lead scorer (`src/pipeline/scorer.py`)
- [ ] Setup FastAPI with `/ingest`, `/score`, `/health` endpoints
- [ ] Setup n8n WF-002 (Lead Intake Pipeline) — webhook only, no calls yet
- [ ] Test: ingest 50 permits, verify scoring, verify Supabase storage
- [ ] Setup Telegram bot notifications

**Deliverable**: Leads flowing from county permits → Supabase dashboard

---

## Phase 2 — More Sources (Week 3)
**Goal**: 50–100 leads/week from multiple sources

- [ ] Build Zillow scraper (new listings in Tampa ZIPs)
- [ ] Build SerpAPI scraper (local search intent + competitor review mining)
- [ ] Setup n8n WF-001 (Scraper Orchestrator — schedule-based)
- [ ] Add Reddit scraper (PRAW)
- [ ] Tune scoring weights based on Phase 1 data
- [ ] Setup WF-005 (Weekly Report to Telegram)

**Deliverable**: 50–100 new leads/week, auto-scored, in Supabase

---

## Phase 3 — Voicebot (Week 4–5)
**Goal**: Jimmy calling leads automatically

- [ ] Configure VAPI assistant (Jimmy)
- [ ] Record/configure ElevenLabs voice
- [ ] Implement VAPI trigger function (`src/voicebot/caller.py`)
- [ ] Setup n8n WF-003 (Voicebot Caller)
- [ ] Setup n8n WF-004 (VAPI Outcome Handler)
- [ ] Test with 10 real calls (low score threshold initially)
- [ ] Setup Calendly API integration for booking
- [ ] Setup WF-006 (Retry Caller)
- [ ] TCPA compliance review

**Deliverable**: Jimmy calling leads, booking estimates, outcomes tracked

---

## Phase 4 — Social Sources (Week 6–7)
**Goal**: Community/social media intent signals

- [ ] Setup Apify account + actors
- [ ] Build Facebook Groups scraper (Apify)
- [ ] Build Nextdoor scraper (Apify)
- [ ] Build Instagram hashtag monitor (Apify)
- [ ] Tune scoring for social signals
- [ ] A/B test Jimmy prompt variants

**Deliverable**: 30+ social leads/week, full pipeline running

---

## Phase 5 — Dashboard + Reporting (Week 8)
**Goal**: Client visibility into system performance

- [ ] Build simple Streamlit dashboard (leads by source, call outcomes, ROI vs Angie's List)
- [ ] Add Google Sheets export (simple CRM view for client)
- [ ] Document all runbooks
- [ ] Handoff documentation for client

**Deliverable**: Client can see ROI in real-time, system is fully documented

---

## Success Metrics (Month 1)

| Metric | Target | Angie's List Baseline |
|---|---|---|
| Leads/month | 80–150 | ~40–60 (client estimate) |
| Exclusive leads | 100% | 0% |
| Cost/lead | <$3 | ~$20–25 |
| Call-to-estimate rate | ≥25% | ~15% (industry avg) |
| Monthly infra cost | <$200 | $1,000 |

---

## Tech Debt / Future

- Add LangChain RAG for Jimmy to answer technical irrigation questions
- Add Google Ads integration (track which keywords generate leads)
- Multi-tenant: package this as Arkana Tech offering for other landscaping companies
- Add Pinellas County + Pasco County permits
- Add commercial property pipeline (separate Jimmy persona)
