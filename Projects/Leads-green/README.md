# 🌿 Green Landscape Irrigation — AI Lead Engine

> **Arkana Tech** · Built for Green Landscape Irrigation, Tampa FL  
> Replaces Angie's List with a proprietary, AI-powered lead generation and qualification pipeline

---

## Why This Exists

Green Landscape Irrigation pays ~**$1,000/month** for Angie's List leads that are:
- **Shared** with 5–10 competitors
- **Not focused** on irrigation specifically  
- **Slow to convert** — no automation on the follow-up side

This system delivers **exclusive, intent-qualified leads** through automated scraping of public sources, enrichment, AI scoring, and an outbound **voicebot (Jimmy)** that calls, qualifies, and books estimates — all before a human is involved.

---

## System Overview

```
[Lead Sources] → [Scraper Engine] → [Pipeline/Scorer] → [Supabase CRM]
                                                              ↓
                                                    [VAPI Voicebot]
                                                              ↓
                                                   [Estimate Booked]
                                                              ↓
                                                [Telegram Notification]
```

---

## Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd green-landscape-ai
cp .env.example .env  # fill API keys

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run scrapers manually
python src/scrapers/permits.py       # County permits
python src/scrapers/zillow.py        # New listings
python src/scrapers/facebook.py      # FB Groups

# 4. Run pipeline
python src/pipeline/runner.py

# 5. Start API
uvicorn src/api/main:app --reload
```

---

## Lead Sources

| Source | Type | Volume/week | Quality |
|---|---|---|---|
| Hillsborough Building Permits | Public records | 50–200 | ⭐⭐⭐⭐⭐ |
| Zillow new listings Tampa | New homeowners | 100–300 | ⭐⭐⭐⭐ |
| Google competitor reviews | Dissatisfied clients | 20–50 | ⭐⭐⭐⭐⭐ |
| Facebook HOA Groups | High intent posts | 10–30 | ⭐⭐⭐⭐ |
| Reddit Tampa | Intent signals | 5–15 | ⭐⭐⭐ |
| SerpAPI local search | Active searchers | 30–80 | ⭐⭐⭐⭐⭐ |

---

## Voicebot — Jimmy

Jimmy is the outbound voice agent powered by **VAPI + ElevenLabs**.  
Persona: Friendly, professional, local to Tampa.  
See `tools/prompts/jimmy_v1.md` for the full script.

---

## Cost Comparison

| Solution | Monthly Cost | Lead Exclusivity | Volume Control |
|---|---|---|---|
| Angie's List | $1,000 | ❌ Shared | ❌ Fixed |
| This System | ~$150–250 infra | ✅ Exclusive | ✅ Configurable |

Savings: **$750–850/month** after infrastructure costs.

---

## Skills (`.claude/skills/`)

- `lead-scraper/SKILL.md` — How to add/extend scrapers
- `voicebot/SKILL.md` — VAPI configuration and prompt engineering
- `lead-scoring/SKILL.md` — Scoring model logic
- `n8n-workflows/SKILL.md` — n8n automation flows

---

## Docs

- `docs/architecture.md` — System design decisions
- `docs/decisions/` — Architecture Decision Records (ADRs)
- `docs/runbooks/` — Operational playbooks
