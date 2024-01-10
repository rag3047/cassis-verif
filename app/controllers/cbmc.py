import re

from typing import Literal
from os import getenv, remove, linesep
from logging import getLogger
from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, status
from websockets.exceptions import ConnectionClosedOK
from fastapi.responses import FileResponse
from pydantic import BaseModel, UUID4
from pathlib import Path
from shutil import rmtree, make_archive
from cbmc_starter_kit import setup_proof
from asyncio import sleep
from asyncio.subprocess import Process, create_subprocess_exec, PIPE, DEVNULL
from datetime import datetime
from io import TextIOWrapper


from ..utils.models import HTTPError

log = getLogger(__name__)

DATA_DIR = getenv("DATA_DIR")
PROOF_ROOT = getenv("PROOF_ROOT")

CBMC_PROOFS_TASK: Process | None = None
CBMC_PROOFS_TASK_OUTPUT = Path(PROOF_ROOT) / "output/output.txt"

RE_HARNESS_FILE = re.compile(r"^HARNESS_FILE\s+=\s+(?P<name>.+)$", re.MULTILINE)
RE_LOOP_NAME = re.compile(r"^Loop (?P<name>.+):$", re.MULTILINE)
RE_LOOP_DATA = re.compile(
    r"^\s+file (?P<file>.+?) line (?P<line>\d+?) function (?P<function>.+)$",
    re.MULTILINE,
)

router = APIRouter(prefix="/cbmc", tags=["cbmc"])


# ------------------------------------------------------------
# CBMC Proofs
# ------------------------------------------------------------


class CBMCProofCreate(BaseModel):
    name: str
    src: Path | None


class CBMCProof(CBMCProofCreate):
    harness: str


@router.get("/proofs")
async def get_cbmc_proofs() -> list[CBMCProof]:
    """Return list of CBMC proofs."""
    log.info("Listing all CBMC proofs")

    proofs_dirs = [
        dir
        for dir in Path(PROOF_ROOT).iterdir()
        if dir.is_dir() and (dir / "cbmc-proof.txt").exists()
    ]

    log.debug(f"Found {len(proofs_dirs)} proofs")
    log.debug(proofs_dirs)

    proofs: list[CBMCProof] = []

    for proof_dir in proofs_dirs:
        try:
            proofs.append(_load_proof_data(proof_dir))

        except HTTPException:
            pass

    return sorted(proofs, key=lambda proof: proof.name)


@router.get(
    "/proofs/{proof_name}",
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPError}},
)
async def get_cbmc_proof(proof_name: str) -> CBMCProof:
    """Return CBMC proof with given name."""
    log.info(f"Get CBMC proof '{proof_name}'")

    proof_dir = Path(PROOF_ROOT) / proof_name

    if not proof_dir.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Proof not found: {proof_name}")

    return _load_proof_data(proof_dir)


@router.post(
    "/proofs",
    responses={status.HTTP_400_BAD_REQUEST: {"model": HTTPError}},
)
async def create_cbmc_proof(proof: CBMCProofCreate) -> CBMCProof:
    """Create a CBMC proof for function func_name in source file src_file."""

    log.info(f"Creating CBMC proof '{proof.name}'")
    proof_dir = Path(PROOF_ROOT) / proof.name

    try:
        proof_dir.mkdir()

    except FileExistsError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Proof with name '{proof.name}' already exists",
        )

    for filename in setup_proof.proof_template_filenames():
        lines = setup_proof.read_proof_template(filename)
        lines = setup_proof.patch_function_name(lines, proof.name)
        lines = setup_proof.patch_path_to_makefile(lines, PROOF_ROOT, proof_dir)
        lines = setup_proof.patch_path_to_proof_root(lines, PROOF_ROOT, DATA_DIR)
        lines = setup_proof.patch_path_to_source_file(
            lines, Path(DATA_DIR) / proof.src, DATA_DIR
        )
        setup_proof.write_proof_template(lines, filename.name, proof_dir)

    setup_proof.rename_proof_harness(proof.name, proof_dir)

    # append src file to cbmc-proof.txt
    if proof.src is not None:
        with open(proof_dir / "cbmc-proof.txt", "a") as file:
            print(f"{proof.name}:{proof.src}", file=file, end=linesep)

    # TODO: find corresponding header file (if any) and insert include statement in harness file

    return _load_proof_data(proof_dir)


@router.delete(
    "/proofs/{proof_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def delete_cbmc_proof(proof_name: str) -> None:
    """Delete CBMC proof."""
    log.info(f"Deleting CBMC proof '{proof_name}'")

    if CBMC_PROOFS_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            """
            Cannot delete proof while verification task is running.
            Wait until task is completed or cancel task.
            """,
        )

    try:
        rmtree(Path(PROOF_ROOT) / proof_name)

    except FileNotFoundError:
        pass


class CBMCLoop(BaseModel):
    name: str
    function: str
    file: str
    line: int


@router.get(
    "/proofs/{proof_name}/loops",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_cbmc_proof_loop_info(
    proof_name: str, rebuild: bool = False
) -> list[CBMCLoop]:
    """Return a list of cbmc loops."""
    log.info(f"Get loop info for proof '{proof_name}' ({rebuild=})")

    proof = await get_cbmc_proof(proof_name)
    proof_dir = Path(PROOF_ROOT) / proof_name
    goto_binary = proof_dir / "gotos" / proof.harness.replace(".c", ".goto")

    # only build goto binary if it doesn't exist or rebuild is True
    if rebuild or not goto_binary.exists():
        if CBMC_PROOFS_TASK is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                """Cannot rebuild proof while verification task is running.""",
            )

        task = await create_subprocess_exec(
            "make",
            "veryclean",
            "goto",
            cwd=str(proof_dir),
            stdout=PIPE,
            stderr=PIPE,
        )

        stdout, stderr = await task.communicate()

        log.info(stdout.decode("ascii"))
        if task.returncode != 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Failed to build goto binary: {stderr.decode('ascii')}",
            )

    task = await create_subprocess_exec(
        "cbmc",
        "--show-loops",
        str(goto_binary),
        cwd=str(proof_dir),
        stdout=PIPE,
        stderr=PIPE,
    )

    stdout, stderr = await task.communicate()

    if task.returncode != 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Failed to get loop info (check server logs for details): {stderr.decode('ascii')}",
        )

    stdout_txt = stdout.decode("ascii")

    loop_names: list[str] = RE_LOOP_NAME.findall(stdout_txt)
    loop_data: list[tuple[str, str, str]] = RE_LOOP_DATA.findall(stdout_txt)

    loops = [
        CBMCLoop(
            name=name,
            function=function,
            line=int(line),
            # builtin library files are enclosed in <>, everything else starts with "/"
            file=file[len(DATA_DIR) + 1 :] if file.startswith(DATA_DIR) else file,
        )
        for name, (file, line, function) in zip(loop_names, loop_data, strict=True)
    ]

    return sorted(loops, key=lambda loop: loop.name)


# ------------------------------------------------------------
# CBMC Task Execution
# ------------------------------------------------------------


class CBMCTaskStatus(BaseModel):
    is_running: bool
    # TODO: maybe add more fields like stdout, stderr, etc.


class CBMCResult(BaseModel):
    name: str
    start_date: datetime


@router.post(
    "/task",
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def start_cbmc_verification_task(tasks: BackgroundTasks) -> CBMCResult:
    """Execute all CBMC proofs."""
    global CBMC_PROOFS_TASK, CBMC_PROOFS_TASK_OUTPUT
    log.info("Start CBMC verification task")

    if CBMC_PROOFS_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Verification Task already running",
        )

    num_proof_runs = len(await get_cbmc_verification_task_result_list())

    CBMC_PROOFS_TASK_OUTPUT.parent.mkdir(exist_ok=True)
    CBMC_PROOFS_TASK_OUTPUT.touch(exist_ok=True)
    fd = CBMC_PROOFS_TASK_OUTPUT.open("w")

    # call run-cbmc-proofs.py in subprocess
    CBMC_PROOFS_TASK = await create_subprocess_exec(
        "python3",
        "run-cbmc-proofs.py",
        cwd=PROOF_ROOT,
        stdout=fd,
        stderr=PIPE,
    )

    tasks.add_task(_cleanup_verification_task, fd)

    proof_runs = await get_cbmc_verification_task_result_list()

    # wait until litani is initialized
    while len(proof_runs) <= num_proof_runs:
        await sleep(0.5)
        proof_runs = await get_cbmc_verification_task_result_list()

    # if len(proof_runs) > 10:  # TODO: get from env
    #     # remove oldest run
    #     rmtree(Path(PROOF_ROOT) / "output/litani/runs" / proof_runs[-1].name)

    return proof_runs[0]


@router.get("/task/status")
async def get_cbmc_verification_task_status() -> CBMCTaskStatus:
    """Return status of CBMC proof execution."""
    log.info("Get CBMC verification task status")
    return CBMCTaskStatus(is_running=CBMC_PROOFS_TASK is not None)


@router.delete(
    "/task",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def cancel_cbmc_verification_task(tasks: BackgroundTasks) -> None:
    """Cancel CBMC verification task"""
    global CBMC_PROOFS_TASK
    log.info("Canceling CBMC proofs")

    if CBMC_PROOFS_TASK is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Verification Task not running")

    # TODO: fix this
    CBMC_PROOFS_TASK.kill()

    # tasks.add_task(lambda: )

    # # remove cancelled proof run
    # TODO fix: maybe use background task instead?
    # proof_runs = await get_cbmc_verification_task_runs()
    # rmtree(Path(PROOF_ROOT) / "output/litani/runs" / proof_runs[0].name)


@router.websocket("/task/output")
async def get_cbmc_verification_task_output(websocket: WebSocket) -> None:
    """Return output of CBMC proof execution."""
    log.info("Get CBMC verification task output")

    await websocket.accept()

    if not CBMC_PROOFS_TASK_OUTPUT.exists():
        await websocket.send_text("No output available")
        await websocket.close()
        return

    try:
        with open(CBMC_PROOFS_TASK_OUTPUT, "r") as file:
            # send current file contents
            for line in file:
                await websocket.send_text(line)

            # send new lines as they are added until task is completed
            while CBMC_PROOFS_TASK is not None:
                line = file.readline()

                if not line:
                    await sleep(0.1)

                else:
                    await websocket.send_text(line)

    # raised when client closes connection during proof execution
    except ConnectionClosedOK:
        pass

    else:
        await websocket.close()


# ------------------------------------------------------------
# CBMC Task Results
# ------------------------------------------------------------


@router.get("/results")
async def get_cbmc_verification_task_result_list() -> list[CBMCResult]:
    """Return list of all CBMC verification task runs."""
    log.info("Get CBMC verification task runs")

    path = Path(f"{PROOF_ROOT}/output/litani/runs")

    if not path.exists():
        return []

    runs = [
        CBMCResult(
            name=run.name,
            start_date=datetime.fromtimestamp(run.stat().st_ctime),
        )
        for run in path.iterdir()
        if run.is_dir()
    ]

    log.debug(f"{runs=}")

    return sorted(runs, key=lambda run: run.start_date, reverse=True)


@router.get(
    # Note: this path allows for directory browsing using relative paths (i.e. navigate the dashboard)
    "/results/{version}/{file_path:path}",
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPError}},
)
async def get_cbmc_verification_task_result(
    version: UUID4 | None = None,
    file_path: str | None = None,
) -> FileResponse:
    """Return results of CBMC proof execution."""
    log.info("Get CBMC verification task results")

    version_str = str(version).lower() if version is not None else "latest"
    file_path = file_path or "index.html"

    log.debug(f"{file_path=}")
    log.debug(f"{version_str=}")

    if version_str == "latest":
        path = Path(f"{PROOF_ROOT}/output/latest/html/{file_path}")

    else:
        path = Path(f"{PROOF_ROOT}/output/litani/runs/{version_str}/html/{file_path}")

    log.debug(f"{path=}")

    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"File not found: {file_path}")

    return FileResponse(path)


@router.delete(
    "/results/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def delete_cbmc_verification_task_results(version: UUID4) -> None:
    """Delete results of CBMC proof execution."""
    log.info("Delete CBMC verification task results")

    version_str = str(version).lower()
    log.debug(f"{version_str=}")

    if CBMC_PROOFS_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot delete results while verification task is running.",
        )

    path = Path(f"{PROOF_ROOT}/output/litani/runs/{version_str}")

    if not path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Version not found: {version_str}"
        )

    rmtree(path)


@router.get(
    "/results/download",
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPError}},
)
async def download_cbmc_verification_task_result(
    version: UUID4,
    tasks: BackgroundTasks,
    format: Literal["zip", "tar", "gztar", "bztar", "xztar"] = "zip",
) -> FileResponse:
    """Download results of CBMC proof execution."""
    log.info("Download CBMC verification task results")

    version_str = str(version).lower()
    log.debug(f"{version_str=}")

    path = Path(PROOF_ROOT) / "output/litani/runs" / version_str

    if not path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Result not found: {version_str}",
        )

    abs_file_path = make_archive(
        version_str,  # archive file name
        format,
        path,  # root directory to archive
    )

    # delete archive file after download
    tasks.add_task(_cleanup_archive_file, abs_file_path)

    return FileResponse(
        abs_file_path,
        filename=Path(abs_file_path).name,
    )


# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------


async def _cleanup_verification_task(fd: TextIOWrapper) -> None:
    """Buffer Task STDOUT into a file."""
    global CBMC_PROOFS_TASK
    log.debug("Buffering CBMC verification task output")

    _, stderr = await CBMC_PROOFS_TASK.communicate()

    fd.close()

    if CBMC_PROOFS_TASK.returncode > 0:
        log.error(
            f"CBMC verification task failed with returncode {CBMC_PROOFS_TASK.returncode}: {stderr.decode('ascii')}"
        )

    elif CBMC_PROOFS_TASK.returncode < 0:
        log.warn(
            f"CBMC verification task cancelled by user (signal={-CBMC_PROOFS_TASK.returncode})"
        )

    log.info(f"CBMC verification task completed")
    CBMC_PROOFS_TASK = None


def _cleanup_archive_file(abs_file_path: str) -> None:
    """Delete archive file."""
    log.debug(f"Cleanup archive file after download: {abs_file_path}")
    remove(abs_file_path)


def _load_proof_data(proof_dir: Path) -> CBMCProof:
    """Loads the proof data from the given proof directory."""
    log.debug(f"Loading proof data from '{proof_dir}'")

    # get src file from cbmc-proof.txt
    proof_file = proof_dir / "cbmc-proof.txt"

    if not proof_file.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Proof not found: {proof_dir.name}",
        )

    lines = proof_file.read_text().splitlines()
    src_file = Path(lines[1].split(":")[1].strip()) if len(lines) > 1 else None

    # get harness file from Makefile
    makefile = proof_dir / "Makefile"

    if not makefile.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Failed to locate harness file for: {proof_dir.name}",
        )

    match = RE_HARNESS_FILE.search(makefile.read_text())

    if not match:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Failed to locate harness file for: {proof_dir.name}",
        )

    harness_file = match.group("name") + ".c"

    return CBMCProof(
        name=proof_dir.name,
        src=src_file,
        harness=harness_file,
    )
