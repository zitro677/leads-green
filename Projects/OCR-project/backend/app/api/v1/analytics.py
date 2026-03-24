from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.analytics import AnalyticsEvent
from app.models.document import Document
from app.schemas.analytics import AnalyticsSummary, UsageOverTime, TimeSeriesPoint
from app.api.v1.dependencies import get_current_user

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Document).where(Document.user_id == current_user.id)
    docs = (await db.scalars(q)).all()

    total_docs = len(docs)
    by_file_type: dict = {}
    for d in docs:
        by_file_type[d.file_type] = by_file_type.get(d.file_type, 0) + 1
    total_size = sum(d.file_size_bytes for d in docs)

    return AnalyticsSummary(
        total_documents=total_docs,
        total_tokens=0,
        total_size_bytes=total_size,
        avg_processing_ms=0.0,
        by_file_type=by_file_type,
        by_ocr_engine={},
        top_languages=[],
        error_rate=0.0,
    )


@router.get("/usage-over-time", response_model=UsageOverTime)
async def usage_over_time(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UsageOverTime(granularity=granularity, data=[])
