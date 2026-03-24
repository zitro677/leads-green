import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class UploadResponse(BaseModel):
    job_id: str
    document_id: uuid.UUID
    status: str
    estimated_wait_seconds: int = 30


class DocumentStatus(BaseModel):
    status: str
    progress_pct: Optional[int] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None


class PageResult(BaseModel):
    page: int
    text: str
    confidence: Optional[float] = None


class DocumentResult(BaseModel):
    document_id: uuid.UUID
    extracted_text: str
    pages: List[PageResult]
    ocr_engine: str
    confidence_avg: Optional[float] = None
    language_detected: Optional[str] = None
    tokens_used: int
    processing_ms: int


class DocumentListItem(BaseModel):
    id: uuid.UUID
    original_name: str
    file_size_bytes: int
    file_type: str
    status: str
    page_count: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: List[DocumentListItem]
    total: int
    page: int
    limit: int
