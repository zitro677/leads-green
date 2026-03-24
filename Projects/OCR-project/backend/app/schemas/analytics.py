from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_documents: int
    total_tokens: int
    total_size_bytes: int
    avg_processing_ms: float
    by_file_type: Dict[str, int]
    by_ocr_engine: Dict[str, int]
    top_languages: List[str]
    error_rate: float


class TimeSeriesPoint(BaseModel):
    date: str
    documents: int
    tokens: int
    avg_processing_ms: float


class UsageOverTime(BaseModel):
    granularity: str
    data: List[TimeSeriesPoint]
