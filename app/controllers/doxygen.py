import xml.etree.ElementTree as ET

from os import getenv
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from logging import getLogger
from asyncio.subprocess import Process, create_subprocess_exec, PIPE
from pathlib import Path
from asyncio import Task, create_task

from ..utils.errors import HTTPError

log = getLogger(__name__)


router = APIRouter(prefix="/doxygen", tags=["doxygen"])

DOXYGEN_DIR = getenv("DOXYGEN_DIR")
DOXYGEN_BUILD_TASK: Process | None = None
DOXYGEN_INIT_TASK: Task | None = None


@router.post(
    "/build",
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def build_doxygen_doc():
    """Build the doxygen documentation"""
    global DOXYGEN_BUILD_TASK
    log.info("Building doxygen documentation")

    if DOXYGEN_BUILD_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Doxygen build task already running",
        )

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
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_doxygen_docs(file_path: str) -> FileResponse:
    """Return doxygen documentation."""
    global DOXYGEN_BUILD_TASK
    log.info("Get doxygen documentation")

    if DOXYGEN_BUILD_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Doxygen build task running",
        )

    file_path = file_path or "index.html"
    abs_path = Path(DOXYGEN_DIR) / "html" / file_path

    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"File not found: {file_path}")

    return FileResponse(abs_path)


@router.get(
    "/callgraphs",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_doxygen_callgraph_image_paths(
    file_name: str,
    func_name: str,
) -> tuple[str, str]:
    """Return the paths to the doxygen callgraph images."""
    global DOXYGEN_BUILD_TASK
    log.info("Get doxygen callgraph image paths")

    if DOXYGEN_BUILD_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Doxygen build task running",
        )

    _, func_ref = _parse_doxygen_index(file_name, func_name)

    # TODO: bugfix: excess "1" in func_ref
    callee_graph = Path(DOXYGEN_DIR) / "html" / f"{func_ref}_cgraph.svg"
    caller_graph = Path(DOXYGEN_DIR) / "html" / f"{func_ref}_icgraph.svg"

    log.debug(f"{callee_graph=}")
    log.debug(f"{caller_graph=}")

    if not callee_graph.exists() or not caller_graph.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Callgraph images not found. Try rebuilding the doxygen documentation.",
        )

    return callee_graph, caller_graph


# ------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------


# Note: startup events are deprecated, but lifespan is not currently
#       supported on APIRouter (only on FastAPI itself)
@router.on_event("startup")
async def init_doxygen():
    """Initialize doxygen."""
    global DOXYGEN_INIT_TASK
    log.info("Doxygen startup initialization")
    # Note: we need to keep a reference to the task, because the event loop
    #       only keeps weak references. Otherwise, the task might be garbage
    #       collected mid-execution.
    DOXYGEN_INIT_TASK = create_task(build_doxygen_doc())


# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------


def _parse_doxygen_index(file_name, func_name) -> tuple[str, str]:
    """Parse the doxygen index file and return file and function refids."""
    log.info("Parsing doxygen index file")

    index_file = Path(DOXYGEN_DIR) / "xml" / "index.xml"

    if not index_file.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Index file not found. Try rebuilding the doxygen documentation.",
        )

    index = ET.parse(index_file)

    # TODO: fix xpath ('and' currently not supported): ./doxygenindex/compound[@kind = 'file' and name={file_name}]
    file = index.find(f"./compound[name='{file_name}']")

    if file is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"File '{file_name}' not found in doxygen index.",
        )

    # TODO: fix xpath ('and' currently not supported): ./member[@kind = 'function' and name={func_name}]
    func = file.find(f"./member[name='{func_name}']")

    if func is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Function '{func_name}' not found in doxygen index.",
        )

    file_ref = file.attrib["refid"]
    func_ref = func.attrib["refid"]

    log.debug(f"{file_ref=}")
    log.debug(f"{func_ref=}")

    return file_ref, func_ref


# TODO: implement
def _extract_doxygen_data(file_ref: str, func_ref: str) -> dict[str, str]:
    """Extract doxygen data for the given file and function refids."""
    log.info("Extracting doxygen data")

    file_data = ET.parse(Path(DOXYGEN_DIR) / "xml" / f"{file_ref}.xml")
