from os import getenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from logging import getLogger
from asyncio.subprocess import Process, create_subprocess_exec, PIPE
from http import HTTPStatus
from pathlib import Path
from asyncio import create_task

from ..utils.errors import HTTPError

log = getLogger(__name__)

router = APIRouter(prefix="/doxygen", tags=["doxygen"])

DOXYGEN_DIR = getenv("DOXYGEN_DIR")
DOXYGEN_BUILD_TASK: Process | None = None


@router.post(
    "/build",
    responses={409: {"model": HTTPError}},
)
async def build_doxygen_doc():
    """Build the doxygen documentation"""
    global DOXYGEN_BUILD_TASK
    log.info("Building doxygen documentation")

    if DOXYGEN_BUILD_TASK is not None:
        raise HTTPException(HTTPStatus.CONFLICT, "Doxygen build task already running")

    # call doxygen in subprocess
    DOXYGEN_BUILD_TASK = await create_subprocess_exec(
        "doxygen",
        "/cassis-verif/Doxyfile",
        stdout=PIPE,
        stderr=PIPE,
    )

    _, stderr = await DOXYGEN_BUILD_TASK.communicate()

    if DOXYGEN_BUILD_TASK.returncode > 0:
        log.error(
            f"Doxygen build task failed with returncode {DOXYGEN_BUILD_TASK.returncode}: {stderr.decode('ascii')}"
        )

    log.info(f"Doxygen build task completed")
    DOXYGEN_BUILD_TASK = None


@router.get(
    "/docs/{file_path:path}",
    responses={
        404: {"model": HTTPError},
        409: {"model": HTTPError},
    },
)
async def get_doxygen_docs(file_path: str) -> FileResponse:
    """Return doxygen documentation."""
    global DOXYGEN_BUILD_TASK
    log.info("Get doxygen documentation")

    if DOXYGEN_BUILD_TASK is not None:
        raise HTTPException(HTTPStatus.CONFLICT, "Doxygen build task running")

    file_path = file_path or "index.html"
    abs_path = Path(DOXYGEN_DIR) / file_path

    if not abs_path.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, f"File not found: {file_path}")

    return FileResponse(abs_path)


# execute doxygen build task on startup
# note: reference is required to avoid garbage collecting the running task
task = create_task(build_doxygen_doc())
