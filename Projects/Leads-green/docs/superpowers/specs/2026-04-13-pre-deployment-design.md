# Pre-Deployment Design — Green Landscape AI Lead Engine
**Date:** 2026-04-13  
**Status:** Approved (updated for Docker + Traefik)  
**Author:** Claude Code + Luis Ortiz (Arkana Tech)

---

## Goal

Prepare the Green Landscape AI Lead Engine for production deployment on a VPS (`arkanatech.net`, IP `2.135.148.139.172`). Covers code fixes, test validation, documentation, and GitHub push. VPS provisioning follows immediately after.

---

## Approach

Fix code issues first → run full test suite to confirm green → write documentation against confirmed-working state → commit and push to GitHub in one clean release commit.

---

## VPS Architecture (existing)

| Component | Details |
|---|---|
| OS | Ubuntu |
| RAM | 22.91 GiB |
| Reverse proxy | **Traefik** (Docker container) — handles all routing + SSL via Let's Encrypt |
| All services | Docker containers |
| Running services | n8n, Flowise (×2), Supabase (×2 instances), PostgreSQL, Redis, Qdrant |
| Domain | `arkanatech.net` |

**Deployment pattern:** every service is a Docker container with Traefik labels that define its hostname and SSL. No standalone Nginx or manual Certbot needed — Traefik handles ACME automatically.

---

## Section 1 — Code Fixes

Six bugs identified during pre-deployment audit:

| # | File | Issue | Fix |
|---|---|---|---|
| 1 | `src/api/main.py` | Hardcoded ngrok + localhost CORS origins | Replace with `ALLOWED_ORIGINS` env var (comma-separated) |
| 2 | `tools/scripts/test_api.py` | Hardcoded port 8000, missing API key on auth'd routes | Update default to 8001, add `X-API-Key` header to all requests |
| 3 | `src/api/main.py` | `INTERNAL_API_KEY` missing from startup validation | Add to `_REQUIRED_ENV` list |
| 4 | `frontend/index.html` | `API = 'http://127.0.0.1:8001'` hardcoded | Read from `window.API_BASE` injected by Nginx, fallback to `http://127.0.0.1:8001` |
| 5 | `schema.sql` | Missing columns from migrations 003 + 004 | Add `next_call_at`, `appointment_at`, `appointment_notes` |
| 6 | Git | New files (auth, admin, migrations, scripts) untracked | Stage and commit all |

---

## Section 2 — Test Suite

All tests run via `python tools/scripts/test_api.py --base-url http://localhost:8001`.

| Test | Endpoint | Assertion |
|---|---|---|
| Health | `GET /health` | 200, `status=ok` |
| Score high | `POST /score` | 200, score ≥ 55, action = call |
| Score low | `POST /score` | 200, action = discard |
| List new | `GET /leads?status=new` | 200, list + count match |
| List queued | `GET /leads?status=queued&limit=10` | 200 |
| List booked | `GET /leads?status=booked` | 200, appointment fields present |
| Ingest valid | `POST /ingest` | 200, 0 errors |
| Ingest empty | `POST /ingest []` | 400 |
| VAPI ignored | `POST /vapi/outcome` (non-end-of-call) | 200, `status=ignored` |
| VAPI accepted | `POST /vapi/outcome` (end-of-call-report) | 200, `status=accepted` |
| Auth login | `POST /auth/login` | 200, JWT token returned |
| Retry queued | `POST /leads/retry-queued` | 200, `status=started` |

All 12 tests must pass before documentation is written.

---

## Section 3 — Documentation Structure

```
docs/
├── architecture.md          # Updated: auth, retry logic, appointments, DB schema
├── api.md                   # All endpoints with curl examples
├── deployment.md            # VPS: Docker + Traefik + env vars + docker-compose
├── runbooks/
│   └── operations.md        # Restart, logs, trigger scrapers, monitor
└── decisions/
    ├── 001-lead-sources.md  # Moved from root
    ├── 002-voicebot-stack.md
    └── 003-n8n-orchestration.md
```

`README.md` — updated with correct quick-start (port 8001, conda env, Docker commands).  
`schema.sql` — updated as canonical DB definition including all migrations.

### Target subdomains
- Dashboard: `https://leads.arkanatech.net` — Nginx container (static), routed by Traefik
- API: `https://api.arkanatech.net` — uvicorn container, routed by Traefik
- SSL: Traefik ACME (Let's Encrypt, automatic)

### Docker assets to create
- `Dockerfile` — multi-stage Python build for FastAPI app
- `Dockerfile.dashboard` — Nginx serving `frontend/` with `API_BASE` injection
- `docker-compose.prod.yml` — production stack with Traefik labels

---

## Section 4 — GitHub

Single commit: `"Pre-deployment: fixes, tests, docs"` pushed to `master`.

**Included:**
- All 6 code fixes
- Updated + passing test suite (12/12)
- Full docs structure
- Updated schema.sql, README.md
- Dockerfile, Dockerfile.dashboard, docker-compose.prod.yml

**Excluded (gitignored):**
- `.env`, `.venv/`, `*.log`, `data/`

---

## Success Criteria

- [ ] All 12 API tests pass against live server on port 8001
- [ ] `ALLOWED_ORIGINS` env var drives CORS (no hardcoded URLs)
- [ ] Dashboard `API_BASE` injected at runtime (works from any origin)
- [ ] `docs/` folder complete and accurate
- [ ] Docker images build cleanly (`docker build` passes)
- [ ] Clean git commit pushed to GitHub
- [ ] Ready for `docker-compose up` on VPS
