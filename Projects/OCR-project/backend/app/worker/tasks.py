import tempfile
import time
import uuid
from celery import shared_task
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300, time_limit=360)
def process_document(self, document_id: str) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.document import Document, OCRResult
    from app.ocr.pipeline import OCRPipeline
    from app.core.storage import download_file
    from sqlalchemy import select
    import asyncio

    async def _run():
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, uuid.UUID(document_id))
            if not doc:
                return {"error": "document not found"}

            doc.status = "processing"
            await db.commit()

            start_ms = int(time.time() * 1000)
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    pdf_bytes = download_file(doc.storage_key)
                    pdf_path = f"{tmpdir}/original.pdf"
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)

                    pipeline = OCRPipeline()
                    result = pipeline.run(pdf_path)

                processing_ms = int(time.time() * 1000) - start_ms

                ocr_result = OCRResult(
                    document_id=doc.id,
                    extracted_text=result["extracted_text"],
                    pages_data={"pages": result["pages"]},
                    ocr_engine=result["ocr_engine"],
                    confidence_avg=result.get("confidence_avg"),
                    language_detected=result.get("language_detected"),
                    processing_ms=processing_ms,
                    tokens_used=result.get("tokens_used", 0),
                )
                db.add(ocr_result)
                doc.status = "completed"
                doc.file_type = result.get("file_type", "pdf_unknown")
                doc.page_count = result.get("page_count")
                await db.commit()

                from app.worker.webhook_tasks import dispatch_webhooks
                dispatch_webhooks.delay(document_id)

                return {"status": "completed", "document_id": document_id}

            except Exception as exc:
                doc.status = "failed"
                doc.error_message = str(exc)
                await db.commit()
                raise self.retry(exc=exc, countdown=60)

    import asyncio
    return asyncio.run(_run())


@celery_app.task
def analytics_rollup():
    logger.info("Running analytics rollup")
