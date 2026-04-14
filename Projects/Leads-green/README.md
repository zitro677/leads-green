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
