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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Green Landscape AI Lead Engine starting...")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Green Landscape AI Lead Engine",
    version="1.0.0",
    description="Exclusive lead generation + qualification pipeline for Green Landscape Irrigation",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(leads.router)
app.include_router(score.router)
app.include_router(vapi.router)
