# CLAUDE.md — Green Landscape Irrigation · AI Lead Engine

## Project Identity
- **Client**: Green Landscape Irrigation (Tampa, FL)
- **Website**: greenlandscapingirrigation.com
- **Owner**: Arkana Tech (Luis Ortiz)
- **Goal**: Replace $1,000/mo Angie's List subscription with a proprietary lead generation + qualification system focused on **irrigation services**

## Problem Statement
Angie's List delivers shared leads (same lead goes to 5–10 contractors). The client pays ~$1,000/mo and competes in real-time. The solution must deliver **exclusive, intent-qualified leads** — fewer but better — plus an automated voicebot to call and qualify them before a human ever touches the phone.

## Core Modules
| Module | Description | Tech |
|---|---|---|
| `src/scrapers/` | Multi-source lead harvesting | Python, Playwright, SerpAPI |
| `src/pipeline/` | Lead dedup, enrichment, scoring | Python, Supabase |
| `src/voicebot/` | Outbound call + qualification | VAPI, ElevenLabs |
| `src/api/` | REST API for dashboard/webhook | FastAPI |
| `src/persistence/` | DB models, Supabase client | Python, Supabase |

## Lead Sources (Priority Order)
1. **Hillsborough County Building Permits** — new construction = new irrigation needed
2. **Zillow / Realtor.com new listings** — new homeowners in Tampa Bay area
3. **Google Maps reviews scraper** — find dissatisfied customers of competitors
4. **Facebook Groups** — Tampa HOA groups, neighborhood groups
5. **Reddit** — r/tampa, r/TampaBayArea, r/homeimprovement
6. **Nextdoor keywords** — irrigation, sprinkler, lawn, landscape
7. **Google Search intent** — SerpAPI for local irrigation queries
8. **Instagram hashtags** — #tampahomes #tampalawn #tampairrigation

## Voicebot Flow
```
Lead arrives → Score ≥ threshold → VAPI triggers call → 
Jimmy (ElevenLabs voice) introduces Green Landscape → 
Qualifies (property type, urgency, budget range) → 
Books estimate OR escalates to human
```

## Tech Stack
- **Language**: Python 3.11+, TypeScript (n8n custom nodes)
- **Scraping**: Playwright, BeautifulSoup4, SerpAPI
- **Orchestration**: n8n (self-hosted, flows.arkanatech.net)
- **Database**: Supabase (PostgreSQL + pgvector)
- **Voicebot**: VAPI + ElevenLabs
- **API**: FastAPI
- **Notifications**: Telegram Bot
- **CRM export**: Google Sheets (simple) or Airtable

## Constraints
- Respect robots.txt and rate limits on all scrapers
- TCPA compliance for outbound calls in Florida
- No PII stored beyond what is needed for qualification
- County permit data is public record — safe to use

## Claude Instructions
- Always check `docs/architecture.md` before modifying src structure
- Lead scoring logic lives in `src/pipeline/scorer.py` — do not duplicate
- Voicebot prompts are versioned in `tools/prompts/` — edit there first
- When adding a new lead source, add an ADR in `docs/decisions/`
- Run `tools/scripts/validate_leads.py` before any DB insert
