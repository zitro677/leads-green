from celery import Celery
from app.config import settings

celery_app = Celery(
    "ocr_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks", "app.worker.webhook_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    task_routes={
        "app.worker.tasks.process_document": {"queue": "ocr"},
        "app.worker.webhook_tasks.dispatch_webhooks": {"queue": "webhooks"},
    },
    result_expires=3600,
    beat_schedule={
        "analytics-rollup-hourly": {
            "task": "app.worker.tasks.analytics_rollup",
            "schedule": 3600.0,
        }
    },
)
