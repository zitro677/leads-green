"""
FastAPI — Green Landscape AI Lead Engine

Endpoints:
  GET  /health         — liveness probe
  POST /ingest         — receive raw leads (from scrapers or n8n)
  POST /score          — score a single lead (used by n8n WF-002)
  POST /vapi/outcome   — VAPI webhook (end-of-call report)
  GET  /leads          — list leads by status (dashboard use)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes import health, leads, score, vapi

load_dotenv()

# Validate required env vars at startup — fail loud rather than mid-request
_REQUIRED_ENV = [
    "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "VAPI_API_KEY", "VAPI_ASSISTANT_ID", "VAPI_PHONE_NUMBER_ID",
    "OPENAI_API_KEY",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [v for v in _REQUIRED_ENV if not __import__("os").getenv(v)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {missing}")
    logger.info("Green Landscape AI Lead Engine starting...")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Green Landscape AI Lead Engine",
    version="1.0.0",
    description="Exclusive lead generation + qualification pipeline for Green Landscape Irrigation",
    lifespan=lifespan,
)

# Allow localhost origins for the dashboard + ngrok for VAPI callbacks.
# Auth is enforced via X-API-Key header on all write endpoints (see deps.py).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8002",
        "http://localhost:8002",
        "http://localhost",
        "http://127.0.0.1",
        "null",  # file:// dashboard origin
    ],
    allow_origin_regex=r"https://.*\.ngrok-free\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(leads.router)
app.include_router(score.router)
app.include_router(vapi.router)
