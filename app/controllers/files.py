import re

from os import getenv
from typing import Literal, Annotated
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from logging import getLogger
from pathlib import Path
from http import HTTPStatus
from shutil import rmtree

from ..utils.errors import HTTPError

log = getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

DATA_DIR = getenv("DATA_DIR")
PROOF_ROOT = getenv("PROOF_ROOT")

# regex used to filter cbmc internal stuff
RE_PATH_CBMC_INTERNALS = re.compile(
    r"cbmc/proofs/(?:lib|output|run-cbmc-proofs\.py)|cbmc/proofs/.+?/(?:logs|report|gotos)"
)


class FileSystemPath(BaseModel):
    path: Path
    type: Literal["dir", "file"]


@router.get(
    "",
    responses={404: {"model": HTTPError}},
)
async def list_directory_tree(
    include_hidden: bool = False,
) -> list[FileSystemPath]:
    """Return all paths in the data directory."""
    log.info("Listing data directory tree")

    paths = (path for path in Path(DATA_DIR).rglob("*"))

    if not include_hidden:
        paths = (
            FileSystemPath(
                path=path.relative_to(DATA_DIR),
                type="dir" if path.is_dir() else "file",
            )
            for path in paths
            # ignore files and directories starting with "."
            if not any(part.startswith(".") for part in path.parts)
            # ignore cbmc internal stuff
            and not RE_PATH_CBMC_INTERNALS.search(str(path))
        )

    return sorted(paths, key=lambda p: (p.type, p.path))


@router.get(
    "/{path:path}",
    responses={404: {"model": HTTPError}},
)
async def download_file(path: str) -> FileResponse:
    """Return file content from proof directory."""
    log.info(f"Downloading file '{path}'")

    file_path = Path(DATA_DIR) / path

    if not file_path.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, "File not found")

    if not file_path.is_file():
        raise HTTPException(HTTPStatus.NOT_FOUND, "File not found")

    return FileResponse(file_path)


@router.post(
    "",
    status_code=HTTPStatus.NO_CONTENT,
    responses={409: {"model": HTTPError}},
)
async def create_path(
    path: FileSystemPath,
) -> None:
    """Creates a new directory or file."""
    log.info(f"Creating path '{path.path}' (type={path.type})")

    abs_path = Path(DATA_DIR) / path.path

    try:
        if path.type == "dir":
            abs_path.mkdir(parents=True, exist_ok=False)

        elif path.type == "file":
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.touch(exist_ok=False)

    except OSError:
        raise HTTPException(HTTPStatus.CONFLICT, "Path already exists")


@router.delete(
    "/{path:path}",
    status_code=HTTPStatus.NO_CONTENT,
)
async def delete_path(path: str) -> None:
    """Delete file or directory."""
    log.info(f"Deleting path '{path}'")

    abs_path = Path(DATA_DIR) / path

    if abs_path.is_dir():
        rmtree(abs_path)

    elif abs_path.is_file():
        abs_path.unlink(missing_ok=True)


@router.put(
    "/{path:path}",
    status_code=HTTPStatus.NO_CONTENT,
    responses={404: {"model": HTTPError}},
)
async def update_file(
    path: str,
    content: Annotated[str, Body()],
):
    """Update file denoten by given path."""
    log.info(f"Updating file '{path}'")

    file_path = Path(DATA_DIR) / path

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(HTTPStatus.NOT_FOUND, "File not found")

    with open(file_path, "w") as file:
        file.write(content)
