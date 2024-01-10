from logging import getLogger
from fastapi import APIRouter, UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from pathlib import Path

from ..utils.models import HTTPError

log = getLogger(__name__)

router = APIRouter(prefix="/sdd", tags=["sdd"])


@router.get(
    "",
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPError}},
)
async def get_sdd() -> FileResponse:
    """Download the Software Design Document."""
    log.info("Downloading SDD")

    sdd_path = Path.cwd() / "sdd.pdf"

    if not sdd_path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No SDD found",
        )

    return FileResponse(sdd_path, media_type="application/pdf")


@router.post(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_400_BAD_REQUEST: {"model": HTTPError}},
)
async def upload_sdd(file: UploadFile) -> None:
    """Upload a new Software Design Document."""
    log.info("Uploading SDD")

    if file.content_type != "application/pdf":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid file type, must be a PDF",
        )

    sdd_path = Path.cwd() / "sdd.pdf"

    # transfer chunk by chunk
    chunk_size = 1024
    with open(sdd_path, "wb") as f:
        while chunk := await file.read(chunk_size):
            f.write(chunk)
