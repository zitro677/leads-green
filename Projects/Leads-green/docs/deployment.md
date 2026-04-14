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
