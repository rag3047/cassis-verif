from fastapi import APIRouter, HTTPException
from logging import getLogger
from asyncio.subprocess import Process, create_subprocess_exec, PIPE
from http import HTTPStatus

from ..utils.errors import HTTPError

log = getLogger(__name__)

router = APIRouter(prefix="/doxygen", tags=["doxygen"])

DOXYGEN_BUILD_TASK: Process | None = None


@router.post("/build", responses={409: {"model": HTTPError}})
async def build_doxygen_doc():
    """Build the doxygen documentation"""
    log.info("Building doxygen documentation")

    if DOXYGEN_BUILD_TASK is not None:
        log.warn("Doxygen build task already running")
        raise HTTPException(HTTPStatus.CONFLICT)

    # call doxygen in subprocess
    DOXYGEN_BUILD_TASK = await create_subprocess_exec(
        "doxygen",
        "/cassis-verif/Doxyfile",
        stdout=PIPE,
        stderr=PIPE,
    )

    stdout, stderr = await DOXYGEN_BUILD_TASK.communicate()

    if DOXYGEN_BUILD_TASK.returncode > 0:
        log.error(
            f"Doxygen build task failed with returncode {DOXYGEN_BUILD_TASK.returncode}: {stderr.decode('ascii')}"
        )

    log.info(f"Doxygen build task completed: {stdout.decode('ascii')}")
    DOXYGEN_BUILD_TASK = None
