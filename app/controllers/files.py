import re

from os import getenv, remove
from typing import Literal, Annotated
from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from fastapi.responses import FileResponse
from logging import getLogger
from pathlib import Path
from http import HTTPStatus
from shutil import make_archive

from ..utils.errors import HTTPError

log = getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

DATA_DIR = getenv("DATA_DIR")
PROOF_ROOT = getenv("PROOF_ROOT")

# TODO: add endpoint to add new file/folder to proof/include/stubs/sources


@router.get(
    "/",
    response_model=list[Path],
    responses={404: {"model": HTTPError}},
)
async def get_files(include_hidden: bool = False) -> list[Path]:
    """Return list of all files."""
    log.info("Listing all files")

    paths = [path.relative_to(DATA_DIR) for path in Path(DATA_DIR).rglob("*")]

    if not include_hidden:
        paths = [
            path
            for path in paths
            # ignore files and directories starting with "."
            if not any(part.startswith(".") for part in path.parts)
            # ignore cbmc internal stuff
            and not str(path).startswith("cbmc/proofs/lib")
            and not str(path).startswith("cbmc/proofs/output")
            and not str(path) == "cbmc/proofs/run-cbmc-proofs.py"
            and not re.match(r"cbmc/proofs/.+?/(?:logs|report|gotos)", str(path))
        ]

    # TODO: Map to some model with preserves type (dir/file)?
    return sorted(paths)


@router.get(
    "/proofs/{proof_name}/files",
    responses={404: {"model": HTTPError}},
    deprecated=True,
)
async def get_proof_files(proof_name: str) -> list[Path]:
    """Return list of all files in proof directory."""
    log.info(f"Listing all files for proof '{proof_name}'")

    proof_dir = Path(PROOF_ROOT) / proof_name

    if not proof_dir.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, "Proof not found")

    return sorted(
        file.relative_to(proof_dir)
        for file in proof_dir.iterdir()
        if file.is_file()
        and not file.name == "cbmc-proof.txt"
        and not file.name == "cbmc-viewer.json"
    )


@router.get(
    "/proofs/{proof_name}/files/{file_name:path}",
    response_class=FileResponse,
    responses={404: {"model": HTTPError}},
    deprecated=True,
)
async def download_proof_file(proof_name: str, file_name: str) -> FileResponse:
    """Return file content from proof directory."""
    log.info(f"Reading file '{file_name}' from proof '{proof_name}'")

    proof_dir = Path(PROOF_ROOT) / proof_name

    if not proof_dir.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, "Proof not found")

    file_path = proof_dir / file_name

    if not file_path.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, "File not found")

    return FileResponse(file_path)


@router.post(
    "/proofs/{proof_name}/files/{file_name:path}",
    status_code=HTTPStatus.NO_CONTENT,
    deprecated=True,
)
async def upload_proof_file(
    proof_name: str,
    file_name: str,
    content: Annotated[str, Body()],
) -> None:
    """Upload file to proof directory."""
    log.info(f"Uploading file '{file_name}' to proof '{proof_name}'")

    proof_dir = Path(PROOF_ROOT) / proof_name

    if not proof_dir.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, "Proof not found")

    file_path = proof_dir / file_name

    with open(file_path, "w") as file:
        file.write(content)


@router.post("/proofs/download")
async def download_all_proofs(
    tasks: BackgroundTasks,
    format: Literal["zip", "tar", "gztar", "bztar", "xztar"] = "zip",
) -> FileResponse:
    """Download all CBMC proofs."""
    log.info("Downloading CBMC proofs")

    abs_file_path = make_archive("cbmc-proofs", format, PROOF_ROOT)
    log.debug(f"Archive file created: '{abs_file_path}'")

    # register task to delete archive after download
    tasks.add_task(_cleanup_archive_file, abs_file_path)

    return FileResponse(
        abs_file_path,
        filename=Path(abs_file_path).name,
    )


# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------


def _cleanup_archive_file(abs_file_path: str) -> None:
    """Delete archive file."""
    log.debug(f"Cleanup archive file after download: {abs_file_path}")
    remove(abs_file_path)
