from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Resolve .env from project root regardless of where uvicorn is launched from
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://ocr_user:devpassword@localhost:5433/ocr_service"

    # Redis
    redis_url: str = "redis://:devpassword@localhost:6379/0"
    redis_password: str = "devpassword"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "ocr_admin"
    minio_root_password: str = "devpassword123"
    minio_bucket: str = "ocr-documents"
    minio_use_ssl: bool = False

    # JWT
    jwt_secret_key: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Celery
    celery_broker_url: str = "redis://:devpassword@localhost:6379/1"
    celery_result_backend: str = "redis://:devpassword@localhost:6379/2"
    celery_task_soft_time_limit: int = 300
    celery_task_time_limit: int = 360

    # OCR
    tesseract_path: str = "/usr/bin/tesseract"
    ocr_max_file_size_mb: int = 50
    ocr_temp_dir: str = "/tmp/ocr_processing"
    easyocr_gpu: bool = False

    # Rate limiting
    rate_limit_uploads_per_minute: int = 5
    rate_limit_api_per_minute: int = 60

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    api_v1_prefix: str = "/api/v1"


settings = Settings()
