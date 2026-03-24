import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta

import httpx
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app

logger = get_task_logger(__name__)

PRIVATE_RANGES = [
    "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
    "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
    "172.29.", "172.30.", "172.31.", "192.168.", "127.", "localhost",
]


def _is_ssrf_url(url: str) -> bool:
    return any(p in url for p in PRIVATE_RANGES)


def _sign_payload(secret: str, timestamp: str, body: bytes) -> str:
    msg = f"{timestamp}.".encode() + body
    return "sha256=" + hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


@celery_app.task(bind=True, max_retries=5)
def dispatch_webhooks(self, document_id: str):
    from app.database import AsyncSessionLocal
    from app.models.webhook import Webhook, WebhookDelivery
    from app.models.document import Document, OCRResult
    from sqlalchemy import select
    import asyncio

    async def _run():
        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, uuid.UUID(document_id))
            if not doc:
                return
            result = await db.scalar(select(OCRResult).where(OCRResult.document_id == doc.id))

            hooks = (await db.scalars(
                select(Webhook).where(
                    Webhook.user_id == doc.user_id,
                    Webhook.is_active == True,
                )
            )).all()

            payload = {
                "event": "document.completed",
                "document_id": document_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {
                    "original_name": doc.original_name,
                    "status": doc.status,
                    "ocr_engine": result.ocr_engine if result else None,
                    "tokens_used": result.tokens_used if result else 0,
                    "processing_ms": result.processing_ms if result else 0,
                },
            }
            body = json.dumps(payload).encode()
            timestamp = str(int(time.time()))

            for hook in hooks:
                if not any(e in hook.events for e in ["completed", "all"]):
                    continue
                if _is_ssrf_url(hook.url):
                    logger.warning("Skipping SSRF-risk URL: %s", hook.url)
                    continue

                signature = _sign_payload(hook.secret, timestamp, body)
                delivery = WebhookDelivery(
                    webhook_id=hook.id,
                    document_id=doc.id,
                    payload=payload,
                    attempt_count=1,
                )
                try:
                    async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
                        resp = await client.post(
                            hook.url,
                            content=body,
                            headers={
                                "Content-Type": "application/json",
                                "X-OCR-Signature": signature,
                                "X-OCR-Timestamp": timestamp,
                                "X-OCR-Delivery-ID": str(delivery.id),
                            },
                        )
                    delivery.last_status = resp.status_code
                    delivery.delivered_at = datetime.utcnow()
                except Exception as exc:
                    delivery.last_error = str(exc)
                    delay = (2 ** self.request.retries) * 60
                    delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                    raise self.retry(exc=exc, countdown=delay)
                finally:
                    db.add(delivery)
                    await db.commit()

    import asyncio
    asyncio.run(_run())
