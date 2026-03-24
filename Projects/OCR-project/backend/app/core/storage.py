from __future__ import annotations
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
import io

from app.config import settings

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_use_ssl,
        )
        try:
            if not _client.bucket_exists(settings.minio_bucket):
                _client.make_bucket(settings.minio_bucket)
        except S3Error:
            pass
    return _client


def upload_file(object_key: str, data: bytes, content_type: str = "application/pdf") -> None:
    client = get_client()
    client.put_object(
        settings.minio_bucket,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_file(object_key: str) -> bytes:
    client = get_client()
    response = client.get_object(settings.minio_bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_presigned_url(object_key: str, expires: int = 3600) -> str:
    client = get_client()
    return client.presigned_get_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=expires),
    )


def delete_file(object_key: str) -> None:
    client = get_client()
    client.remove_object(settings.minio_bucket, object_key)
