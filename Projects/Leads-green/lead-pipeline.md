# Runbook: Lead Pipeline Operations

## Daily Health Check

```bash
# Check leads captured in last 24h
python tools/scripts/stats.py --period 24h

# Check failed scraper runs
python tools/scripts/check_errors.py

# Verify VAPI call queue
python tools/scripts/call_queue.py --status pending
```

Expected outputs:
- ≥10 new leads/day (first 2 weeks may be lower)
- 0 scraper errors (or known/handled)
- Call queue < 50 (backlog alert if over)

---

## Adding Leads to Blacklist (Do Not Call)

```bash
python tools/scripts/blacklist.py --add "+18135551234" --reason "requested"
```

Or directly in Supabase: `INSERT INTO dnc_list (phone, reason, added_at) VALUES (...)`

---

## Manual Lead Entry

For leads captured outside the system (referrals, walk-ins):

```bash
python tools/scripts/add_lead.py \
  --source "manual" \
  --name "John Smith" \
  --phone "+18135559999" \
  --address "123 Main St Tampa FL 33609" \
  --signal "Referral from existing customer — needs sprinkler repair"
```

---

## Restarting After Downtime

```bash
# On VPS
cd /opt/green-landscape
docker-compose up -d

# Verify n8n
curl https://flows.arkanatech.net/healthz

# Verify FastAPI
curl https://api.greenlandscape.arkanatech.net/health

# Re-trigger any stuck leads
python tools/scripts/retry_stuck_leads.py
```

---

## Monitoring Voicebot Quality

Weekly review checklist:
- [ ] Listen to 5 random call recordings
- [ ] Check transcripts for Jimmy errors/confusion
- [ ] Review escalation reasons
- [ ] Check conversion rate vs prior week
- [ ] Adjust Jimmy prompt if needed (update `tools/prompts/`)

---

## Scaling Up

When ready to increase volume:
1. Upgrade Apify plan (more scraping quota)
2. Upgrade SerpAPI plan
3. Add more Tampa ZIP codes to target area
4. Consider adding Pinellas County permits (St. Pete, Clearwater)
5. Add commercial property queue (separate Jimmy script)

---

## Shutting Down Scrapers Temporarily

```bash
# Pause all n8n schedules
python tools/scripts/pause_workflows.py --all

# Or pause specific
python tools/scripts/pause_workflows.py --id WF-001
```

Re-enable:
```bash
python tools/scripts/pause_workflows.py --resume --all
```

---

## Cost Monitoring

Check monthly spend before the 1st of each month:
- VAPI: dashboard.vapi.ai → Usage
- Apify: console.apify.com → Billing  
- SerpAPI: serpapi.com → Dashboard
- Supabase: app.supabase.com → Billing

Alert threshold: If total > $200/mo, review and optimize scrapers.
