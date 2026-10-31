import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="garage",
    )


class UploadError(Exception):
    pass


def upload_image(content: bytes, content_type: str) -> str:
    """Uploads an image to the S3 bucket and returns its object key.

    Raises UploadError for anything the caller should turn into a 4xx
    (unsupported type, too large) — a network/S3 failure raises the
    underlying boto exception, which the router turns into a 502.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UploadError(f"Unsupported content type: {content_type}")
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadError("Image exceeds the 8 MB upload limit")

    extension = ALLOWED_CONTENT_TYPES[content_type]
    key = f"events/{uuid.uuid4().hex}.{extension}"

    settings = get_settings()
    client = _client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    return key


def get_image(key: str) -> tuple[bytes, str]:
    """Fetches an object's bytes and content-type for proxying to a client.

    Raises FileNotFoundError if the key doesn't exist, or the underlying
    boto exception for any other failure.
    """
    settings = get_settings()
    client = _client()
    try:
        response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in ("NoSuchKey", "404"):
            raise FileNotFoundError(key) from exc
        raise
    body = response["Body"].read()
    content_type = response.get("ContentType", "application/octet-stream")
    return body, content_type
