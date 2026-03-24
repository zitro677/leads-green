import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.document import Document, OCRResult
from app.schemas.document import UploadResponse, DocumentStatus, DocumentResult, DocumentListResponse, DocumentListItem, PageResult
from app.api.v1.dependencies import get_current_user
from app.core import storage
from app.core.rate_limit import check_rate_limit

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_rate_limit(str(current_user.id), limit=5)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    doc_id = uuid.uuid4()
    storage_key = f"{current_user.id}/{doc_id}/original.pdf"
    storage.upload_file(storage_key, contents)

    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        original_name=file.filename or "upload.pdf",
        storage_key=storage_key,
        file_size_bytes=len(contents),
        file_type="pdf_unknown",
        mime_type=file.content_type,
        status="queued",
    )
    db.add(doc)
    await db.flush()

    from app.worker.tasks import process_document
    task = process_document.delay(str(doc_id))
    doc.celery_task_id = task.id

    return UploadResponse(job_id=task.id, document_id=doc_id, status="queued")


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.user_id == current_user.id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatus(status=doc.status, queued_at=doc.created_at, started_at=None)


@router.get("/{document_id}/result", response_model=DocumentResult)
async def get_result(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.user_id == current_user.id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "completed":
        raise HTTPException(status_code=409, detail=f"Document status is '{doc.status}'")

    result = await db.scalar(select(OCRResult).where(OCRResult.document_id == document_id))
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    pages = [PageResult(**p) for p in result.pages_data.get("pages", [])]
    return DocumentResult(
        document_id=document_id,
        extracted_text=result.extracted_text,
        pages=pages,
        ocr_engine=result.ocr_engine,
        confidence_avg=result.confidence_avg,
        language_detected=result.language_detected,
        tokens_used=result.tokens_used,
        processing_ms=result.processing_ms,
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Document).where(Document.user_id == current_user.id)
    if status:
        q = q.where(Document.status == status)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    docs = (await db.scalars(q.offset((page - 1) * limit).limit(limit))).all()
    return DocumentListResponse(
        items=[DocumentListItem.model_validate(d) for d in docs],
        total=total or 0,
        page=page,
        limit=limit,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.scalar(select(Document).where(Document.id == document_id, Document.user_id == current_user.id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    storage.delete_file(doc.storage_key)
    await db.delete(doc)
