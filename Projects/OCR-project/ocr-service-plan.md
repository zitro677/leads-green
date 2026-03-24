# OCR Document Service — Plan Completo de Arquitectura

> Servicio escalable para extracción de texto de documentos PDF (digitales y escaneados),
> multi-usuario, con entrega por JSON/webhook, frontend de carga/resultados,
> analytics backend y despliegue completamente dockerizado.

---

## Tabla de Contenidos

1. [Visión General del Sistema](#1-visión-general-del-sistema)
2. [Diagrama de Arquitectura](#2-diagrama-de-arquitectura)
3. [Stack Tecnológico](#3-stack-tecnológico)
4. [Estructura de Directorios](#4-estructura-de-directorios)
5. [Esquema de Base de Datos](#5-esquema-de-base-de-datos)
6. [Diseño de Endpoints API](#6-diseño-de-endpoints-api)
7. [Pipeline de Procesamiento OCR](#7-pipeline-de-procesamiento-ocr)
8. [Sistema de Webhooks](#8-sistema-de-webhooks)
9. [Docker y Docker Compose](#9-docker-y-docker-compose)
10. [Seguridad](#10-seguridad)
11. [Escalabilidad](#11-escalabilidad)
12. [Arquitectura del Frontend](#12-arquitectura-del-frontend)
13. [Variables de Entorno](#13-variables-de-entorno)
14. [Orden de Implementación](#14-orden-de-implementación)
15. [Decisiones de Diseño y Compromisos](#15-decisiones-de-diseño-y-compromisos)

---

## 1. Visión General del Sistema

El servicio recibe archivos PDF (digitales o escaneados), los procesa con una pipeline OCR
multi-estrategia, devuelve el texto extraído como JSON via API REST y/o webhooks, persiste
métricas de uso en PostgreSQL, y expone un dashboard de analytics para el usuario.

**Flujo principal:**

```
Usuario sube PDF → API recibe archivo → MinIO almacena → Redis encola tarea
→ Worker OCR procesa → Resultado guardado en PostgreSQL → JSON vía API / Webhook HTTP POST
```

---

## 2. Diagrama de Arquitectura

```
                    ┌─────────────────────────────────────────────┐
                    │            NGINX Reverse Proxy               │
                    │     (SSL, rate limiting, body limit)         │
                    └──────────┬──────────────────┬───────────────┘
                               │                  │
                   ┌───────────▼──────┐  ┌────────▼──────────┐
                   │  React Frontend  │  │  FastAPI Backend   │
                   │  (Upload UI +    │  │  (REST API v1)     │
                   │   Results View)  │  │  Gunicorn/Uvicorn  │
                   └──────────────────┘  └────────┬──────────┘
                                                   │
                        ┌──────────────────────────┼─────────────────────┐
                        │                          │                     │
             ┌──────────▼───────┐      ┌──────────▼──────┐  ┌──────────▼──────┐
             │   Redis 7        │      │  PostgreSQL 16   │  │   MinIO          │
             │  - Celery broker │      │  - users         │  │  (S3-compat.)    │
             │  - Result cache  │      │  - documents     │  │  Archivos PDF    │
             │  - Rate limits   │      │  - ocr_results   │  │  originales      │
             └──────────┬───────┘      │  - analytics     │  └─────────────────┘
                        │              │  - webhooks      │
          ┌─────────────┼──────────┐   └─────────────────┘
          │             │          │
┌─────────▼──────┐ ┌────▼──────┐ ┌▼──────────────┐
│ Celery Worker 1│ │ Worker 2  │ │   Worker N     │
│ (OCR + webhook)│ │  (OCR)    │ │   (OCR)        │
└────────┬───────┘ └───────────┘ └────────────────┘
         │
┌────────▼──────────────────────────────────────────────┐
│                  OCR Pipeline                          │
│                                                        │
│  PDF → pdfplumber → ¿texto extraíble?                  │
│            │ SI → digital_extractor (rápido)           │
│            │ NO → pdf2image → preprocessor (OpenCV)    │
│                    → pytesseract (primario)             │
│                    → easyocr (fallback)                 │
└────────┬──────────────────────────────────────────────┘
         │
┌────────▼─────────────┐
│  Webhook Dispatcher  │  POST firmado (HMAC-SHA256) a URL externa
└──────────────────────┘
```

---

## 3. Stack Tecnológico

### 3.1 Backend — Python / FastAPI

| Componente       | Librería / Herramienta              | Propósito                                      |
|------------------|-------------------------------------|------------------------------------------------|
| Framework API    | FastAPI 0.111+                      | API REST async, OpenAPI autogenerado           |
| Servidor ASGI    | Uvicorn + Gunicorn                  | Producción con manejo de workers               |
| Cola de tareas   | Celery 5.3+                         | Procesamiento async distribuido                |
| Broker           | Redis 7                             | Broker Celery + caché de resultados            |
| ORM              | SQLAlchemy 2.0 (async)              | Interacción DB con soporte async               |
| Migraciones      | Alembic                             | Versionado de esquema                          |
| Validación       | Pydantic v2                         | Modelos request/response con tipado estricto   |
| Autenticación    | python-jose + passlib               | JWT + bcrypt                                   |
| HTTP Client      | httpx                               | Dispatch async de webhooks                     |
| Almacenamiento   | boto3 / minio-py                    | Object storage S3-compatible                   |
| File validation  | python-magic                        | Validación de tipo MIME por magic bytes        |

### 3.2 Librerías OCR

| Librería               | Rol                              | Cuándo se usa                                 |
|------------------------|----------------------------------|-----------------------------------------------|
| pdfplumber             | Extracción de texto digital      | Primera pasada en todos los PDFs (más rápido) |
| pypdf / pypdf2         | Metadata + split de páginas      | Pre-procesamiento                              |
| pdf2image              | Rasterización PDF → imagen       | Antes de pytesseract/easyocr                  |
| pytesseract            | Wrapper Tesseract 5              | OCR primario para PDFs escaneados             |
| easyocr                | OCR con deep learning            | Fallback para layouts complejos/multi-idioma  |
| Pillow                 | Procesamiento de imagen          | Desinclinación, contraste, binarización       |
| opencv-python-headless | Pre-procesamiento avanzado       | Reducción de ruido, umbralización adaptativa  |
| langdetect             | Detección de idioma              | Enrutar al paquete de idioma correcto         |
| tiktoken               | Conteo de tokens                 | Analytics — tokens extraídos por documento    |

### 3.3 Frontend — React

| Componente     | Librería              | Propósito                                          |
|----------------|-----------------------|----------------------------------------------------|
| Framework      | React 18 + Vite       | Build rápido, HMR, bundling moderno                |
| Lenguaje       | TypeScript            | Seguridad de tipos                                 |
| UI             | shadcn/ui + Tailwind  | Componentes accesibles sin dependencia pesada      |
| Estado global  | Zustand               | Estado global ligero                               |
| HTTP/Polling   | TanStack Query        | Estado servidor, polling de jobs, caché            |
| File Upload    | react-dropzone        | Drag-and-drop con validación de tipo               |
| Routing        | React Router v6       | Navegación SPA                                     |
| Gráficas       | Recharts              | Visualizaciones del dashboard de analytics         |
| Código/JSON    | react-syntax-highlighter | Display formateado de salida JSON               |

### 3.4 Infraestructura

| Componente     | Herramienta           | Notas                                               |
|----------------|-----------------------|-----------------------------------------------------|
| Reverse Proxy  | NGINX                 | SSL, rate limiting, archivos estáticos              |
| Base de datos  | PostgreSQL 16         | Almacén primario de datos                           |
| Caché / Broker | Redis 7               | Broker Celery, backend de resultados, caché API     |
| File Storage   | MinIO                 | S3-compatible, corre en Docker                      |
| Contenedores   | Docker + Compose      | Orquestación completa del stack                     |

---

## 4. Estructura de Directorios

```
ocr-service/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── nginx/
│   ├── nginx.conf
│   └── ssl/
│       ├── cert.pem
│       └── key.pem
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   └── app/
│       ├── main.py                   # FastAPI app factory, lifespan, CORS, routers
│       ├── config.py                 # Settings via pydantic-settings
│       ├── database.py               # SQLAlchemy async engine + session factory
│       ├── models/
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── document.py
│       │   ├── analytics.py
│       │   └── webhook.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── document.py           # Pydantic request/response
│       │   ├── analytics.py
│       │   ├── webhook.py
│       │   └── auth.py
│       ├── api/
│       │   └── v1/
│       │       ├── router.py         # Agrupador de routers
│       │       ├── auth.py           # /auth/* endpoints
│       │       ├── documents.py      # Upload, status, result endpoints
│       │       ├── webhooks.py       # Webhook CRUD endpoints
│       │       └── analytics.py     # Analytics query endpoints
│       ├── core/
│       │   ├── security.py           # JWT, hash, API key logic
│       │   ├── storage.py            # Wrapper MinIO client
│       │   ├── rate_limit.py         # Redis-backed sliding window
│       │   └── exceptions.py         # HTTP exception handlers
│       ├── worker/
│       │   ├── celery_app.py         # Instancia Celery + configuración
│       │   ├── tasks.py              # process_document task
│       │   └── webhook_tasks.py      # dispatch_webhooks task con retry
│       └── ocr/
│           ├── pipeline.py           # Orquestador: detecta tipo, enruta
│           ├── digital_extractor.py  # Ruta pdfplumber + pypdf
│           ├── scan_extractor.py     # Ruta pdf2image + pytesseract
│           ├── easyocr_extractor.py  # Fallback EasyOCR
│           ├── preprocessor.py       # Mejora de imagen (OpenCV, Pillow)
│           └── token_counter.py      # Conteo de tokens con tiktoken
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/
│       │   ├── Upload.tsx            # Drag-and-drop + progreso de subida
│       │   ├── Results.tsx           # Texto extraído + vista JSON
│       │   ├── Dashboard.tsx         # Gráficas de analytics
│       │   └── Webhooks.tsx          # Gestión de webhooks
│       ├── components/
│       │   ├── FileDropzone.tsx
│       │   ├── JobStatusPoller.tsx   # Polling /jobs/{id}/status
│       │   ├── TextViewer.tsx
│       │   └── AnalyticsChart.tsx
│       ├── hooks/
│       │   ├── useJobStatus.ts
│       │   ├── useUpload.ts
│       │   └── useWebhooks.ts
│       └── lib/
│           ├── api.ts                # Instancia axios con interceptores
│           └── queryClient.ts
└── worker/
    └── Dockerfile                    # Dockerfile separado para workers Celery
```

---

## 5. Esquema de Base de Datos

### 5.1 Tabla `users`

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    api_key       VARCHAR(64) UNIQUE,             -- Clave API hasheada (SHA-256)
    plan          VARCHAR(32) DEFAULT 'free',     -- free | pro | enterprise
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.2 Tabla `documents`

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    original_name   VARCHAR(512) NOT NULL,
    storage_key     VARCHAR(1024) NOT NULL,        -- Clave objeto en MinIO
    file_size_bytes BIGINT NOT NULL,
    file_type       VARCHAR(32) NOT NULL,           -- pdf_digital | pdf_scanned | pdf_mixed
    mime_type       VARCHAR(128) NOT NULL,
    page_count      INTEGER,
    status          VARCHAR(32) DEFAULT 'queued',  -- queued | processing | completed | failed
    celery_task_id  VARCHAR(255),
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_user_id   ON documents(user_id);
CREATE INDEX idx_documents_status    ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
```

### 5.3 Tabla `ocr_results`

```sql
CREATE TABLE ocr_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    extracted_text      TEXT NOT NULL,
    pages_data          JSONB NOT NULL,            -- Texto por página, confianza, bounding boxes
    ocr_engine          VARCHAR(64) NOT NULL,       -- pdfplumber | pytesseract | easyocr | mixed
    confidence_avg      FLOAT,                     -- Confianza promedio OCR 0-100
    language_detected   VARCHAR(32),
    processing_ms       INTEGER NOT NULL,           -- Tiempo de procesamiento en ms
    tokens_used         INTEGER NOT NULL,           -- Conteo tiktoken del texto extraído
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.4 Tabla `analytics_events` (append-only, alta escritura)

```sql
CREATE TABLE analytics_events (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    document_id     UUID REFERENCES documents(id),
    event_type      VARCHAR(64) NOT NULL,   -- upload | processing_start | processing_end
                                            -- | download | webhook_sent | error
    file_type       VARCHAR(32),
    file_size_bytes BIGINT,
    tokens_used     INTEGER,
    processing_ms   INTEGER,
    ocr_engine      VARCHAR(64),
    page_count      INTEGER,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partición mensual para escalabilidad
CREATE TABLE analytics_events_2026_01 PARTITION OF analytics_events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE INDEX idx_analytics_user_id    ON analytics_events(user_id);
CREATE INDEX idx_analytics_event_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_created_at ON analytics_events(created_at DESC);
```

### 5.5 Tabla `webhooks`

```sql
CREATE TABLE webhooks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    url         VARCHAR(2048) NOT NULL,
    secret      VARCHAR(255) NOT NULL,        -- Secreto de firma HMAC-SHA256
    events      VARCHAR(32)[] NOT NULL,        -- ['completed', 'failed', 'all']
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.6 Tabla `webhook_deliveries`

```sql
CREATE TABLE webhook_deliveries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id      UUID REFERENCES webhooks(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id),
    payload         JSONB NOT NULL,
    attempt_count   INTEGER DEFAULT 0,
    last_status     INTEGER,                  -- Código HTTP de respuesta
    last_error      TEXT,
    delivered_at    TIMESTAMPTZ,
    next_retry_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhook_deliveries_retry
    ON webhook_deliveries(next_retry_at)
    WHERE delivered_at IS NULL;
```

---

## 6. Diseño de Endpoints API

### 6.1 Autenticación

```
POST   /api/v1/auth/register          Registrar nuevo usuario
POST   /api/v1/auth/login             Devuelve JWT access + refresh token
POST   /api/v1/auth/refresh           Renovar access token
POST   /api/v1/auth/api-key           Generar API key para acceso programático
DELETE /api/v1/auth/api-key           Revocar API key
```

### 6.2 Procesamiento de Documentos

```
POST   /api/v1/documents/upload
       Body: multipart/form-data { file, webhook_url? (one-time), options? }
       Returns: { job_id, document_id, status: "queued", estimated_wait_seconds }

GET    /api/v1/documents/{document_id}/status
       Returns: { status, progress_pct, queued_at, started_at, estimated_completion }

GET    /api/v1/documents/{document_id}/result
       Returns:
       {
         "document_id": "uuid",
         "extracted_text": "Texto completo...",
         "pages": [{ "page": 1, "text": "...", "confidence": 95.1 }],
         "ocr_engine": "pytesseract",
         "confidence_avg": 94.2,
         "language_detected": "es",
         "tokens_used": 1240,
         "processing_ms": 4820
       }

GET    /api/v1/documents/{document_id}/result/download
       Returns: Descarga de archivo JSON (Content-Disposition: attachment)

GET    /api/v1/documents/
       Query: page, limit, status, from_date, to_date, file_type
       Returns: lista paginada de documentos del usuario

DELETE /api/v1/documents/{document_id}
       Elimina documento, archivo en MinIO y resultado asociado
```

### 6.3 Gestión de Webhooks

```
POST   /api/v1/webhooks/
       Body: { name, url, secret, events: ["completed", "failed"] }
       Returns: { webhook_id, name, url, events, is_active }

GET    /api/v1/webhooks/
       Returns: lista de webhooks del usuario

GET    /api/v1/webhooks/{webhook_id}
       Returns: configuración del webhook + historial de entregas recientes

PUT    /api/v1/webhooks/{webhook_id}
       Actualizar configuración del webhook

DELETE /api/v1/webhooks/{webhook_id}

POST   /api/v1/webhooks/{webhook_id}/test
       Envía payload de prueba a la URL del webhook

GET    /api/v1/webhooks/{webhook_id}/deliveries
       Historial paginado de entregas con códigos de estado y payloads
```

### 6.4 Analytics

```
GET    /api/v1/analytics/summary
       Query: from_date, to_date
       Returns:
       {
         "total_documents": 245,
         "total_tokens": 182400,
         "total_size_bytes": 524288000,
         "avg_processing_ms": 3840,
         "by_file_type": { "pdf_digital": 180, "pdf_scanned": 65 },
         "by_ocr_engine": { "pdfplumber": 180, "pytesseract": 55, "easyocr": 10 },
         "top_languages": ["es", "en", "pt"],
         "error_rate": 0.02
       }

GET    /api/v1/analytics/usage-over-time
       Query: from_date, to_date, granularity (day|week|month)
       Returns: serie temporal de documentos, tokens, tiempo de procesamiento

GET    /api/v1/analytics/documents/{document_id}
       Detalle de analytics por documento

GET    /api/v1/analytics/export
       Query: from_date, to_date, format (csv|json)
       Returns: descarga de datos de analytics
```

### 6.5 Sistema / Admin

```
GET    /api/v1/health           Estado del servicio (DB, Redis, MinIO)
GET    /api/v1/metrics          Métricas formato Prometheus (solo interno)
GET    /api/v1/queue/stats      Profundidad de cola, workers activos, tareas en curso
```

---

## 7. Pipeline de Procesamiento OCR

### 7.1 Árbol de Decisiones

```
PDF Recibido
     │
     ▼
pdfplumber.open(pdf) → extraer texto
     │
     ├── ¿Tiene texto extraíble? (len > threshold de 50 chars/página promedio)
     │        │
     │        SI ──→ digital_extractor.py (ruta pdfplumber)
     │                  Extraer texto por página, metadata, proxy de confianza
     │                  Validar calidad de salida
     │                  Guardar en ocr_results
     │
     └── NO (escaneado o mixto) ──→ pdf2image.convert_from_path()
                  │
                  ▼
             preprocessor.py (por imagen)
                  ├── Pillow: escala de grises, mejora de contraste (ImageEnhance)
                  └── OpenCV: umbralización adaptativa, deskew, denoising
                  │
                  ▼
             langdetect en muestra de primera página
                  │
                  ├── Layout simple / idioma único ──→ pytesseract
                  │   tesseract.image_to_data() → confianza por palabra
                  │
                  └── Layout complejo / multi-idioma / baja confianza
                            ──→ easyocr reader.readtext()
                                (GPU opcional, fallback a CPU)
                  │
                  ▼
             Agregar resultados por página en JSON unificado
             Contar tokens con tiktoken
             Guardar en ocr_results + analytics_events
```

### 7.2 Flujo de Tareas Celery

```python
# Diseño conceptual de las tareas

@celery_app.task(bind=True, max_retries=3, soft_time_limit=300, time_limit=360)
def process_document(self, document_id: str) -> dict:
    # 1. Obtener metadata del documento desde DB
    # 2. Descargar archivo de MinIO a ruta temporal
    # 3. Actualizar status del documento -> "processing"
    # 4. Ejecutar OCRPipeline.run(path, options)
    # 5. Guardar resultado en tabla ocr_results
    # 6. Actualizar status del documento -> "completed"
    # 7. Emitir analytics_event
    # 8. Disparar dispatch_webhooks.delay(document_id)
    # 9. Limpiar archivo temporal
    # En excepción: status -> "failed", guardar error_message, re-raise para retry

@celery_app.task(bind=True, max_retries=5)
def dispatch_webhooks(self, document_id: str):
    # 1. Consultar webhooks que coincidan con user_id y events "completed"
    # 2. Construir payload firmado (HMAC-SHA256)
    # 3. httpx.post(webhook.url, json=payload, headers={"X-Signature": sig})
    # 4. Registrar entrega en webhook_deliveries
    # 5. En falla: retry con backoff exponencial (2^attempt * 60s, máx 5 intentos)
```

---

## 8. Sistema de Webhooks

### 8.1 Estructura del Payload

```json
{
  "event": "document.completed",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-03-21T14:30:00Z",
  "data": {
    "original_name": "factura_marzo.pdf",
    "file_type": "pdf_scanned",
    "file_size_bytes": 2048000,
    "page_count": 3,
    "ocr_engine": "pytesseract",
    "confidence_avg": 94.2,
    "language_detected": "es",
    "tokens_used": 1240,
    "processing_ms": 4820,
    "extracted_text": "Texto completo extraído aquí...",
    "pages": [
      { "page": 1, "text": "Texto página 1...", "confidence": 95.1 },
      { "page": 2, "text": "Texto página 2...", "confidence": 93.8 },
      { "page": 3, "text": "Texto página 3...", "confidence": 93.7 }
    ]
  }
}
```

### 8.2 Headers de Seguridad

```
X-OCR-Signature:   sha256=<hex_digest_hmac_sha256>
X-OCR-Delivery-ID: <delivery_uuid>
X-OCR-Timestamp:   <unix_epoch>
```

**Verificación en el consumidor:**
```python
import hmac, hashlib, time

def verify_webhook(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    # Rechazar entregas con más de 300 segundos de antigüedad
    if abs(time.time() - int(timestamp)) > 300:
        return False
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### 8.3 Política de Reintentos

| Intento | Demora      |
|---------|-------------|
| 1       | 1 minuto    |
| 2       | 4 minutos   |
| 3       | 16 minutos  |
| 4       | 64 minutos  |
| 5       | 256 minutos |

Después de 5 fallas la entrega se marca `permanently_failed`. Los usuarios pueden re-disparar manualmente desde el dashboard.

---

## 9. Docker y Docker Compose

### 9.1 `docker-compose.yml` (Producción)

```yaml
version: "3.9"

services:

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    networks:
      - ocr-network
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    expose:
      - "3000"
    networks:
      - ocr-network
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
    expose:
      - "8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      minio:
        condition: service_started
    networks:
      - ocr-network
    restart: unless-stopped

  worker:
    build:
      context: ./worker
      dockerfile: Dockerfile
    command: >
      celery -A app.worker.celery_app worker
      --loglevel=info
      --concurrency=4
      -Q ocr,webhooks
    env_file: .env
    depends_on:
      - redis
      - postgres
      - minio
    deploy:
      replicas: 2
    networks:
      - ocr-network
    restart: unless-stopped

  beat:
    build:
      context: ./worker
      dockerfile: Dockerfile
    command: celery -A app.worker.celery_app beat --loglevel=info
    env_file: .env
    depends_on:
      - redis
    networks:
      - ocr-network
    restart: unless-stopped

  flower:
    build:
      context: ./worker
      dockerfile: Dockerfile
    command: celery -A app.worker.celery_app flower --port=5555
    expose:
      - "5555"
    env_file: .env
    depends_on:
      - redis
    networks:
      - ocr-network
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-ocr_service}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - ocr-network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - ocr-network
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    expose:
      - "9000"
      - "9001"
    networks:
      - ocr-network
    restart: unless-stopped

networks:
  ocr-network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 9.2 `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

### 9.3 `worker/Dockerfile` (Imagen más pesada — incluye Tesseract)

```dockerfile
FROM python:3.12-slim-bookworm

# Instalar Tesseract 5, idiomas, Poppler (pdf2image), OpenCV deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    tesseract-ocr-por \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata/

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info", "--concurrency=4", "-Q", "ocr,webhooks"]
```

### 9.4 `frontend/Dockerfile` (Multi-stage build)

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve
FROM node:20-alpine AS runner
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
```

### 9.5 `nginx/nginx.conf` (Fragmento clave)

```nginx
# Zonas de rate limiting
limit_req_zone $binary_remote_addr zone=upload:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m    rate=60r/m;

server {
    listen 443 ssl;
    server_name tudominio.com;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Security headers
    add_header X-Content-Type-Options  "nosniff"    always;
    add_header X-Frame-Options         "DENY"       always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Endpoint de subida — rate limit estricto, body grande
    location /api/v1/documents/upload {
        limit_req        zone=upload burst=3 nodelay;
        client_max_body_size 50M;
        proxy_pass       http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API general
    location /api/ {
        limit_req    zone=api burst=20;
        proxy_pass   http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend SPA
    location / {
        proxy_pass http://frontend:3000;
    }
}
```

### 9.6 `requirements.txt` (Worker — completo)

```text
# Framework
fastapi==0.111.0
uvicorn[standard]==0.30.1
gunicorn==22.0.0

# Queue
celery[redis]==5.3.6
redis==5.0.4
flower==2.0.1

# DB
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1

# Validación / Auth
pydantic[email]==2.7.1
pydantic-settings==2.3.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9

# HTTP
httpx==0.27.0

# Storage
boto3==1.34.116
minio==7.2.7

# File validation
python-magic==0.4.27

# OCR - Digital PDF
pdfplumber==0.11.0
pypdf==4.2.0

# OCR - Scanned PDF
pdf2image==1.17.0
pytesseract==0.3.10
easyocr==1.7.1

# Image processing
Pillow==10.3.0
opencv-python-headless==4.9.0.80

# Language detection
langdetect==1.0.9

# Tokens
tiktoken==0.7.0
```

---

## 10. Seguridad

### 10.1 Autenticación y Autorización

- **JWT access tokens**: expiración de 15 minutos. Cortos para limitar exposición en caso de robo.
- **Refresh tokens**: 7 días de expiración, almacenados en cookies `httpOnly` para prevenir acceso via XSS.
- **API keys**: SHA-256 hasheadas en DB; la clave en texto plano se muestra solo una vez en creación. Uso via header `Authorization: ApiKey <key>`.
- **Aislamiento por usuario**: todas las consultas DB incluyen `WHERE user_id = :current_user_id`. Los workers validan ownership del documento antes de procesar.

### 10.2 Seguridad en Subida de Archivos

- **Validación de tipo**: MIME type validado server-side con `python-magic` (lee magic bytes, no la extensión). Rechazar todo lo que no sea `application/pdf`.
- **Límite de tamaño**: 50 MB impuesto en NGINX y nuevamente a nivel de ruta FastAPI.
- **Aislamiento en almacenamiento**: archivos en MinIO bajo `/{user_id}/{document_id}/original.pdf`. URLs pre-firmadas con expiración de 1 hora para acceso interno de workers.
- **Limpieza de archivos temporales**: workers siempre usan `tempfile.TemporaryDirectory()` como context manager para garantizar limpieza incluso en excepción.

### 10.3 Seguridad de Webhooks

- Firma HMAC-SHA256 en cada entrega.
- Solo se aceptan URLs webhook HTTPS (validador Pydantic `AnyHttpsUrl`).
- Validación SSRF: rechazar IPs privadas `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `localhost`, `127.0.0.1`. Usar `httpx` con `follow_redirects=False`.

### 10.4 Seguridad de Infraestructura

- Toda comunicación inter-contenedor sobre la red interna `ocr-network`. Solo NGINX expone puertos 80/443 externamente.
- Redis requiere contraseña. MinIO requiere credenciales fuertes.
- Usuarios no-root en todos los contenedores.
- Backend de resultados de Celery en Redis con TTL de 1 hora para prevenir acumulación sin límite.

---

## 11. Escalabilidad

### 11.1 Escalado Horizontal

| Componente         | Eje de Escalado                     | Estado                           |
|--------------------|-------------------------------------|----------------------------------|
| FastAPI Backend    | Réplicas detrás de NGINX upstream   | Sin estado — estado en PG/Redis  |
| Celery Workers     | `deploy.replicas` en Compose        | Sin estado — tareas desde Redis  |
| PostgreSQL         | Réplicas de lectura para analytics  | Primary/replica streaming        |
| Redis              | Redis Cluster o Redis Sentinel      | Distribuido                      |
| MinIO              | Modo distribuido (4+ nodos)         | Object storage                   |

### 11.2 Dos Colas Celery Independientes

- `ocr`: workers intensivos en CPU/memoria. Escalar según profundidad de cola.
- `webhooks`: workers ligeros de dispatch HTTP. Pueden compartir instancias con OCR a baja carga.

### 11.3 Niveles de Rate Limiting

```
Plan Free:       5 subidas/minuto,   100 MB/día,   500 tokens/día
Plan Pro:        20 subidas/minuto,  1 GB/día,     tokens ilimitados
Plan Enterprise: Límites custom,     ilimitado,    SLA garantizado
```

Estado del rate limit en Redis usando ventana deslizante: clave `ratelimit:{user_id}:{minute_bucket}`.

### 11.4 Escalabilidad de Base de Datos

- `analytics_events` usa particionado por mes. Particiones antiguas se archivan o eliminan sin bloqueo.
- Agregados de analytics pre-computados por tarea Celery Beat (rollups cada hora) para evitar agregación en tiempo real costosa.

### 11.5 Ruta de Migración a Kubernetes

Cuando Docker Compose sea insuficiente, la arquitectura mapea directamente:

- Cada servicio `docker-compose` → `Deployment` o `StatefulSet`
- `.env` → `ConfigMap` + `Secret`
- `deploy.replicas` → `HorizontalPodAutoscaler` con KEDA (leyendo profundidad de cola Redis)
- MinIO distribuido → AWS S3 / GCS

---

## 12. Arquitectura del Frontend

### 12.1 Página Upload (`/upload`)

1. Área `react-dropzone` acepta PDFs hasta 50 MB con validación previa de tipo/tamaño en cliente.
2. Al soltar, se sube el archivo via `multipart/form-data POST` a `/api/v1/documents/upload`.
3. Progreso de subida via `axios` con `onUploadProgress` (hook `useUpload`).
4. Al éxito, la respuesta retorna `document_id`. El usuario es redirigido a `/results/{document_id}`.

### 12.2 Página Results (`/results/:documentId`)

1. Hook `useJobStatus` hace polling a `GET /api/v1/documents/{id}/status` cada 2 segundos con TanStack Query (`refetchInterval`).
2. Mientras el status es `queued` o `processing`, se muestra una barra de progreso animada (indeterminada).
3. Al completarse, se muestra el resultado en dos pestañas: "Texto Plano" y "Vista JSON" (con `react-syntax-highlighter`).
4. Botón "Descargar JSON" dispara el endpoint `/result/download`.
5. Desglose por página en acordeón colapsable con texto y score de confianza.

### 12.3 Página Dashboard (`/dashboard`)

- Tarjetas resumen: total documentos, total tokens, tiempo promedio de procesamiento, tasa de error.
- Gráfica de línea: documentos procesados en el tiempo (toggle de granularidad: día/semana/mes).
- Gráfica de dona: distribución por tipo de archivo (PDF digital vs escaneado).
- Gráfica de barras: motores OCR más utilizados.
- Tabla de datos: historial reciente de documentos con búsqueda y paginación.

### 12.4 Página Webhooks (`/webhooks`)

- Lista de webhooks registrados con badges de estado (activo/inactivo, último código de entrega).
- Formulario de creación/edición con input de URL, checkboxes de eventos y display del secreto generado.
- Tabla de historial de entregas por webhook: intentos, código HTTP, timestamp.
- Botón "Enviar Prueba" que dispara un payload de test y muestra la respuesta inline.

---

## 13. Variables de Entorno

```bash
# .env.example

# ── PostgreSQL ─────────────────────────────────────────────────────────────────
POSTGRES_USER=ocr_user
POSTGRES_PASSWORD=CAMBIA_ESTO_password_fuerte
POSTGRES_DB=ocr_service
DATABASE_URL=postgresql+asyncpg://ocr_user:CAMBIA_ESTO_password_fuerte@postgres:5432/ocr_service

# ── Redis ──────────────────────────────────────────────────────────────────────
REDIS_PASSWORD=CAMBIA_ESTO_redis_password
REDIS_URL=redis://:CAMBIA_ESTO_redis_password@redis:6379/0

# ── MinIO ──────────────────────────────────────────────────────────────────────
MINIO_ROOT_USER=ocr_admin
MINIO_ROOT_PASSWORD=CAMBIA_ESTO_minio_password
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=ocr-documents
MINIO_USE_SSL=false

# ── JWT ────────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY=CAMBIA_ESTO_clave_aleatoria_256_bits
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Celery ─────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL=redis://:CAMBIA_ESTO_redis_password@redis:6379/1
CELERY_RESULT_BACKEND=redis://:CAMBIA_ESTO_redis_password@redis:6379/2
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=360

# ── OCR ────────────────────────────────────────────────────────────────────────
TESSERACT_PATH=/usr/bin/tesseract
OCR_MAX_FILE_SIZE_MB=50
OCR_TEMP_DIR=/tmp/ocr_processing
EASYOCR_GPU=false

# ── Rate Limiting ──────────────────────────────────────────────────────────────
RATE_LIMIT_UPLOADS_PER_MINUTE=5
RATE_LIMIT_API_PER_MINUTE=60

# ── Aplicación ─────────────────────────────────────────────────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=["https://tudominio.com"]
API_V1_PREFIX=/api/v1
```

---

## 14. Orden de Implementación

### Fase 1 — Infraestructura Core (Días 1–3)
- [ ] Configurar `docker-compose.yml` con PostgreSQL, Redis, MinIO
- [ ] Crear skeleton FastAPI con `main.py`, `config.py`, `database.py`
- [ ] Escribir migraciones Alembic para todas las tablas
- [ ] Implementar endpoints de auth JWT (`/register`, `/login`, `/refresh`)

### Fase 2 — Pipeline OCR (Días 4–7)
- [ ] Implementar `ocr/pipeline.py` con árbol de decisión digital/escaneado
- [ ] Implementar `ocr/digital_extractor.py` (ruta pdfplumber)
- [ ] Implementar `ocr/preprocessor.py` (Pillow + OpenCV)
- [ ] Implementar `ocr/scan_extractor.py` (pdf2image + pytesseract)
- [ ] Implementar `ocr/easyocr_extractor.py` como fallback
- [ ] Implementar `ocr/token_counter.py` con tiktoken
- [ ] Tests unitarios para cada extractor con fixtures PDF de ejemplo

### Fase 3 — Cola y API (Días 8–11)
- [ ] Configurar `worker/celery_app.py` y `worker/tasks.py` (tarea `process_document`)
- [ ] Implementar `core/storage.py` (upload/download/presign en MinIO)
- [ ] Implementar endpoints `/api/v1/documents/` (upload, status, result, list, delete)
- [ ] Implementar emisión de eventos de analytics
- [ ] Implementar `worker/webhook_tasks.py` con firma HMAC y lógica de retry
- [ ] Implementar endpoints CRUD `/api/v1/webhooks/`

### Fase 4 — Analytics y Admin (Días 12–14)
- [ ] Implementar endpoints de consulta `/api/v1/analytics/`
- [ ] Implementar tarea Celery Beat para rollups de analytics horarios
- [ ] Implementar `/api/v1/queue/stats` y `/api/v1/health`

### Fase 5 — Frontend (Días 15–21)
- [ ] Scaffold React + Vite + TypeScript + Tailwind + shadcn/ui
- [ ] Construir `Upload.tsx` con react-dropzone y tracking de progreso
- [ ] Construir `Results.tsx` con polling y display texto/JSON
- [ ] Construir `Dashboard.tsx` con visualizaciones Recharts
- [ ] Construir `Webhooks.tsx` interfaz de gestión

### Fase 6 — Hardening de Producción (Días 22–25)
- [ ] Configuración NGINX: rate limiting, SSL, headers de seguridad
- [ ] Agregar validación de tipo de archivo con `python-magic`
- [ ] Agregar protección SSRF para URLs de webhook
- [ ] Tests de integración para el flujo completo upload → proceso → entrega webhook
- [ ] Load test con Locust para verificar comportamiento de concurrencia

---

## 15. Decisiones de Diseño y Compromisos

| Decisión              | Enfoque Elegido           | Alternativa            | Razón                                                                 |
|-----------------------|---------------------------|------------------------|-----------------------------------------------------------------------|
| Enrutamiento OCR      | Digital primero, escaneado como fallback | Siempre pytesseract | pdfplumber es 10-50x más rápido en PDFs digitales y preserva estructura |
| Cola de tareas        | Celery + Redis            | Celery + RabbitMQ      | Redis ya se usa para caché, menos componentes de infraestructura       |
| Almacenamiento        | MinIO (S3-compatible)     | Volumen local          | Escala a múltiples nodos, migración fácil a AWS S3                    |
| ORM                   | SQLAlchemy 2.0 async      | Django ORM             | FastAPI es async-first; asyncpg provee acceso no bloqueante a DB      |
| Framework frontend    | React + Vite + shadcn/ui  | Next.js                | Sin necesidad de SSR (datos autenticados y dinámicos); Vite más rápido |
| Analytics storage     | PostgreSQL con particionado | ClickHouse / TimescaleDB | Stack unificado. Para >100M filas/mes, migrar solo esa tabla        |
| GPU EasyOCR           | Deshabilitado por defecto (CPU) | GPU siempre      | GPU requiere Docker runtime CUDA; CPU funciona en cualquier deployment |

---

## Resumen de Servicios Docker

| Servicio   | Puerto interno | Puerto externo | Descripción                        |
|------------|----------------|----------------|------------------------------------|
| nginx      | 80, 443        | 80, 443        | Reverse proxy, SSL, rate limiting  |
| frontend   | 3000           | —              | React SPA (proxiado por NGINX)     |
| backend    | 8000           | —              | FastAPI REST API                   |
| worker     | —              | —              | Celery OCR workers (x2 réplicas)   |
| beat       | —              | —              | Celery Beat scheduler              |
| flower     | 5555           | —              | Monitor de tareas Celery           |
| postgres   | 5432           | —              | Base de datos principal            |
| redis      | 6379           | —              | Broker + caché                     |
| minio      | 9000, 9001     | —              | Object storage (9001 = consola)    |

---

*Documento generado el 2026-03-21. Versión del plan: 1.0*
