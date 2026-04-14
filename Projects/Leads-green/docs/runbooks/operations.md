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
