from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from app.auth.dependencies import require_role
from app.config import get_settings
from app.models.user import Role
from app.services.storage import UploadError, get_image, upload_image, upload_image_pair

router = APIRouter(tags=["uploads"])


def _require_s3_configured() -> None:
    settings = get_settings()
    if not all(
        [
            settings.s3_endpoint_url,
            settings.s3_access_key_id,
            settings.s3_secret_access_key,
            settings.s3_bucket_name,
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image uploads are not configured on this server",
        )


@router.post(
    "/backoffice/uploads",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.admin, Role.redacteur))],
)
async def create_upload(file: UploadFile, thumbnail: UploadFile | None = None) -> dict:
    _require_s3_configured()
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    try:
        if thumbnail is not None:
            key = upload_image_pair(
                content,
                content_type,
                await thumbnail.read(),
                thumbnail.content_type or "application/octet-stream",
            )
        else:
            key = upload_image(content, content_type)
    except UploadError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return {"url": f"/uploads/{key}"}


@router.get("/uploads/{key:path}")
def read_upload(key: str) -> Response:
    _require_s3_configured()
    try:
        content, content_type = get_image(key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    except Exception as exc:  # noqa: BLE001 — any S3 failure becomes a 502 for the client
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch image"
        ) from exc
    return Response(content=content, media_type=content_type)
