"""
POST /score — score a single lead.
Used by n8n WF-002 to score leads before inserting into Supabase.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.persistence.models import ScoringResult
from src.pipeline.scorer import score_lead

router = APIRouter(tags=["scoring"])


class ScoreRequest(BaseModel):
    source: str
    source_id: str | None = None
    signal: str | None = None
    signal_type: str = "unknown"
    zip_code: str | None = None
    phone: str | None = None
    email: str | None = None
    property_type: str = "residential"


@router.post("/score", response_model=ScoringResult)
async def score_endpoint(req: ScoreRequest):
    result = score_lead(req.model_dump())
    return result
