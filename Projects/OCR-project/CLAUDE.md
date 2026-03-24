# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scalable OCR document service that extracts text from PDFs (digital and scanned), supports multi-user access, delivers results via JSON API and webhooks, and provides an analytics dashboard. Fully Dockerized.

## Commands

### Docker (primary workflow)
```bash
docker compose up --build          # Start all services
docker compose up --build worker   # Rebuild only workers
docker compose -f docker-compose.dev.yml up  # Dev mode
docker compose down -v             # Tear down with volumes
```

### Backend (inside container or local venv)
```bash
# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Run backend locally (dev)
uvicorn app.main:app --reload --port 8000

# Run a single test
pytest tests/test_ocr_pipeline.py::test_digital_extraction -v

# Celery worker (local)
celery -A app.worker.celery_app worker --loglevel=info -Q ocr,webhooks

# Celery beat scheduler
celery -A app.worker.celery_app beat --loglevel=info
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # Vite dev server
npm run build      # Production build
npm run lint       # ESLint
```

## Architecture

### Request Flow
```
User uploads PDF → FastAPI (backend:8000) → validates MIME type (python-magic) → stores in MinIO →
creates document record (PostgreSQL) → enqueues Celery task (Redis) → returns {job_id, document_id}

Celery worker picks up task → downloads from MinIO to tempfile → runs OCR pipeline →
saves result to ocr_results table → dispatches webhook (dispatch_webhooks task)
```

### OCR Pipeline (`backend/app/ocr/pipeline.py`)
Decision tree — the pipeline in `pipeline.py` routes each PDF to one of three extractors:
1. **`digital_extractor.py`** — pdfplumber when text is extractable (>50 chars/page avg)
2. **`scan_extractor.py`** — pdf2image → OpenCV/Pillow preprocessing → pytesseract (primary)
3. **`easyocr_extractor.py`** — fallback for complex layouts, multi-language, or low pytesseract confidence

Language detection (`langdetect`) runs on the first-page sample to route Tesseract to the correct language pack.

### Two Celery Queues
- **`ocr`** — CPU/memory intensive; scale workers independently based on queue depth
- **`webhooks`** — lightweight HTTP dispatch with exponential backoff retry (5 attempts: 1/4/16/64/256 min)

### Authentication Dual-Mode
Both JWT (for browser users) and API keys (for programmatic access) are supported. JWT access tokens expire in 15 min; refresh tokens are 7 days in `httpOnly` cookies. API keys are SHA-256 hashed in DB — shown only once at creation, sent via `Authorization: ApiKey <key>`.

### Storage Paths
Files in MinIO are stored under `/{user_id}/{document_id}/original.pdf`. Workers access files via pre-signed URLs (1-hour expiry). All queries include `WHERE user_id = :current_user_id` for row-level isolation.

## Key Design Decisions

- **Two Dockerfiles**: `backend/Dockerfile` is lightweight (no OCR libs). `worker/Dockerfile` installs Tesseract 5, Poppler, and OpenCV system deps — only workers need these.
- **`analytics_events` is append-only and partitioned by month** — never update rows; pre-computed rollups via Celery Beat (hourly) avoid expensive real-time aggregation.
- **Workers always use `tempfile.TemporaryDirectory()` as a context manager** — guarantees cleanup even on exception.
- **Webhook SSRF protection**: private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, localhost) are rejected; `follow_redirects=False` on httpx.
- **Rate limiting** is Redis sliding-window keyed as `ratelimit:{user_id}:{minute_bucket}`, enforced both at NGINX (upload: 5r/m, api: 60r/m) and in FastAPI middleware.

## Stack

| Layer | Tech |
|---|---|
| Backend API | FastAPI 0.111 + Uvicorn/Gunicorn |
| Task queue | Celery 5.3 + Redis 7 |
| Database | PostgreSQL 16, SQLAlchemy 2.0 async, Alembic |
| Object storage | MinIO (S3-compatible) |
| OCR | pdfplumber, pytesseract (Tesseract 5), easyocr, pdf2image, OpenCV, Pillow |
| Frontend | React 18 + Vite, TypeScript, shadcn/ui + Tailwind, Zustand, TanStack Query |
| Proxy | NGINX (SSL termination, rate limiting, 50 MB body limit on upload) |

## Environment

Copy `.env.example` to `.env`. Required variables: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `JWT_SECRET_KEY`.

## Frontend Polling Pattern

The Results page polls `GET /api/v1/documents/{id}/status` every 2 seconds using TanStack Query `refetchInterval`. Once `status === "completed"`, the query stops and the result is fetched. Do not change this to WebSockets without updating both the hook (`useJobStatus.ts`) and the backend.
