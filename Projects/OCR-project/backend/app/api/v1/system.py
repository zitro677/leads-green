from fastapi import APIRouter
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.core.storage import get_client

router = APIRouter()


@router.get("/health")
async def health():
    status = {"db": "ok", "redis": "ok", "minio": "ok"}
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
    except Exception:
        status["db"] = "error"
    try:
        get_client()
    except Exception:
        status["minio"] = "error"
    overall = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    return {"status": overall, **status}


@router.get("/queue/stats")
async def queue_stats():
    return {"queued": 0, "active": 0, "workers": 0}
