from os import getenv, linesep
from logging import getLogger
from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from shutil import rmtree
from http import HTTPStatus
from cbmc_starter_kit import setup_proof
from asyncio import sleep, wait_for, TimeoutError
from asyncio.subprocess import Process, create_subprocess_exec, PIPE
from datetime import datetime

from ..utils.errors import HTTPError

log = getLogger(__name__)

DATA_DIR = getenv("DATA_DIR")
PROOF_ROOT = getenv("PROOF_ROOT")

CBMC_PROOFS_TASK: Process | None = None
CBMC_PROOFS_TASK_OUTPUT = Path(PROOF_ROOT) / "output/output.txt"
CBMC_PROOFS_TASK_OUTPUT_RESET = False

router = APIRouter(prefix="/cbmc", tags=["cbmc"])


# ------------------------------------------------------------
# CBMC Proofs
# ------------------------------------------------------------


class CBMCProof(BaseModel):
    name: str
    src: Path


@router.get("/proofs")
async def get_cbmc_proofs() -> list[CBMCProof]:
    """Return list of CBMC proofs."""
    log.info("Listing all CBMC proofs")

    proofs = [
        dir
        for dir in Path(PROOF_ROOT).iterdir()
        if dir.is_dir() and (dir / "cbmc-proof.txt").exists()
    ]

    log.debug(f"Found {len(proofs)} proofs")
    log.debug(proofs)

    source_files: list[str] = []
    for proof in proofs:
        with open(proof / "cbmc-proof.txt", "r") as file:
            file.readline()  # skip first line
            # TODO: handle case where src file does not exist (proof created outside of cassis-verif)
            src = file.readline().split(":")[1].strip()
            source_files.append(src)

    proofs = [
        CBMCProof(name=proof.name, src=Path(src))
        for proof, src in zip(proofs, source_files, strict=True)
    ]

    return sorted(proofs, key=lambda proof: proof.name)


@router.post("/proofs", responses={400: {"model": HTTPError}})
async def create_cbmc_proof(proof: CBMCProof) -> CBMCProof:
    """Create a CBMC proof for function func_name in source file src_file."""

    log.info(f"Creating CBMC proof '{proof.name}'")
    proof_dir = Path(PROOF_ROOT) / proof.name

    try:
        proof_dir.mkdir()

    except FileExistsError:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Proof with name '{proof.name}' already exists"
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
    with open(proof_dir / "cbmc-proof.txt", "a") as file:
        print(f"{proof.name}:{proof.src}", file=file, end=linesep)

    return proof


@router.delete(
    "/proofs/{proof_name}",
    status_code=HTTPStatus.NO_CONTENT,
    responses={409: {"model": HTTPError}},
)
async def delete_cbmc_proof(proof_name: str) -> None:
    """Delete CBMC proof."""
    log.info(f"Deleting CBMC proof '{proof_name}'")

    if CBMC_PROOFS_TASK is not None:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            """
            Cannot delete proof while verification task is running.
            Wait until task is completed or cancel task.
            """,
        )

    try:
        rmtree(Path(PROOF_ROOT) / proof_name)

    except FileNotFoundError:
        pass


# TODO: get harness files (get proof dirs and then harness files from makefile)


# ------------------------------------------------------------
# CBMC Task Execution
# ------------------------------------------------------------


class CBMCTaskStatus(BaseModel):
    is_running: bool
    # TODO: maybe add more fields like stdout, stderr, etc.


class CBMCTaskRun(BaseModel):
    name: str
    start_date: datetime


@router.post(
    "/task",
    responses={409: {"model": HTTPError}},
)
async def start_cbmc_verification_task(tasks: BackgroundTasks) -> CBMCTaskRun:
    """Execute all CBMC proofs."""
    global CBMC_PROOFS_TASK
    log.info("Start CBMC verification task")

    if CBMC_PROOFS_TASK is not None:
        raise HTTPException(HTTPStatus.CONFLICT, "Verification Task already running")

    num_proof_runs = len(await get_cbmc_verification_task_runs())

    # call run-cbmc-proofs.py in subprocess
    CBMC_PROOFS_TASK = await create_subprocess_exec(
        "python3",
        "run-cbmc-proofs.py",
        cwd=PROOF_ROOT,
        stdout=PIPE,
        stderr=PIPE,
    )

    tasks.add_task(_buffer_task_output)

    proof_runs = await get_cbmc_verification_task_runs()

    # wait until litani is initialized
    while len(proof_runs) <= num_proof_runs:
        await sleep(0.5)
        proof_runs = await get_cbmc_verification_task_runs()

    if len(proof_runs) > 10:  # TODO: get from env
        # remove oldest run
        rmtree(Path(PROOF_ROOT) / "output/litani/runs" / proof_runs[-1].name)

    return proof_runs[0]


@router.get("/task/status")
async def get_cbmc_verification_task_status() -> CBMCTaskStatus:
    """Return status of CBMC proof execution."""
    log.info("Get CBMC verification task status")
    return CBMCTaskStatus(is_running=CBMC_PROOFS_TASK is not None)


@router.websocket("/task/output")
async def get_cbmc_verification_task_output(websocket: WebSocket) -> None:
    """Return output of CBMC proof execution."""
    global CBMC_PROOFS_TASK_OUTPUT_RESET
    log.info("Get CBMC verification task output")

    await websocket.accept()

    if (
        not CBMC_PROOFS_TASK_OUTPUT.exists()
        or CBMC_PROOFS_TASK_OUTPUT.stat().st_size == 0
    ):
        await websocket.send_text("No output available")
        CBMC_PROOFS_TASK_OUTPUT.touch(exist_ok=True)

    with open(CBMC_PROOFS_TASK_OUTPUT, "r") as file:
        while True:
            if CBMC_PROOFS_TASK_OUTPUT_RESET:
                file.seek(0)
                CBMC_PROOFS_TASK_OUTPUT_RESET = False

            line = file.readline()

            if not line:
                await sleep(1)

            else:
                await websocket.send_text(line)


@router.get("/task/runs")
async def get_cbmc_verification_task_runs() -> list[CBMCTaskRun]:
    """Return list of all CBMC verification task runs."""
    log.info("Get CBMC verification task runs")

    path = Path(f"{PROOF_ROOT}/output/litani/runs")

    if not path.exists():
        return []

    runs = [
        CBMCTaskRun(
            name=run.name,
            start_date=datetime.fromtimestamp(run.stat().st_ctime),
        )
        for run in path.iterdir()
        if run.is_dir()
    ]

    log.debug(f"{runs=}")

    return sorted(runs, key=lambda run: run.start_date, reverse=True)


@router.get(
    "/task/results/{version}/{file_path:path}",
    responses={404: {"model": HTTPError}},
)
async def get_cbmc_verification_task_results(
    version: str | None = None,
    file_path: str | None = None,
) -> FileResponse:
    """Return results of CBMC proof execution."""
    log.info("Get CBMC verification task results")

    version = version.lower() or "latest"
    file_path = file_path or "index.html"

    log.debug(f"{file_path=}")
    log.debug(f"{version=}")

    if version == "latest":
        path = Path(f"{PROOF_ROOT}/output/latest/html/{file_path}")

    else:
        path = Path(f"{PROOF_ROOT}/output/litani/runs/{version}/html/{file_path}")

    log.debug(f"{path=}")

    if not path.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, f"File not found: {file_path}")

    return FileResponse(path)


@router.delete(
    "/task/results/{version}",
    status_code=HTTPStatus.NO_CONTENT,
    responses={409: {"model": HTTPError}},
)
async def delete_cbmc_verification_task_results(version: str) -> None:
    """Delete results of CBMC proof execution."""
    log.info("Delete CBMC verification task results")

    version = version.lower()
    log.debug(f"{version=}")

    if CBMC_PROOFS_TASK is not None:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            "Cannot delete results while verification task is running.",
        )

    path = Path(f"{PROOF_ROOT}/output/litani/runs/{version}")

    if not path.exists():
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Version not found: {version}")

    rmtree(path)


# TODO: download result as zip file


@router.delete(
    "/task",
    status_code=HTTPStatus.NO_CONTENT,
    responses={409: {"model": HTTPError}},
)
async def cancel_cbmc_verification_task() -> None:
    """Cancel CBMC verification task"""
    global CBMC_PROOFS_TASK
    log.info("Canceling CBMC proofs")

    if CBMC_PROOFS_TASK is None:
        raise HTTPException(HTTPStatus.CONFLICT, "Verification Task not running")

    CBMC_PROOFS_TASK.kill()

    # # remove cancelled proof run
    # TODO fix: maybe use background task instead?
    # proof_runs = await get_cbmc_verification_task_runs()
    # rmtree(Path(PROOF_ROOT) / "output/litani/runs" / proof_runs[0].name)


# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------

# TODO: autoremove old runs (configurable limit, default keep up to 10)


async def _buffer_task_output() -> None:
    """Buffer Task STDOUT into a file."""
    global CBMC_PROOFS_TASK, CBMC_PROOFS_TASK_OUTPUT_RESET
    log.debug("Buffering CBMC verification task output")

    with open(CBMC_PROOFS_TASK_OUTPUT, "w") as file:
        CBMC_PROOFS_TASK_OUTPUT_RESET = True

        while CBMC_PROOFS_TASK.returncode is None:
            # TODO: use asyncio.as_completed() to read both stdout and stderr
            # TODO fix: this "blocks" until the task is completed...
            try:
                line = await wait_for(CBMC_PROOFS_TASK.stdout.readline(), timeout=1)

                if not line:
                    break

                file.write(line.decode("ascii"))
                file.flush()

            except TimeoutError:
                pass  # check loop condition for cancellation

        # get remaining output (if any)
        stdout, stderr = await CBMC_PROOFS_TASK.communicate()
        file.write(stdout.decode("ascii"))

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


# async def _cleanup_task_when_done() -> None:
#     """Cleanup after verification task is completed."""
#     global CBMC_PROOFS_TASK

#     stdout, stderr = await CBMC_PROOFS_TASK.communicate()

#     if CBMC_PROOFS_TASK.returncode > 0:
#         log.error(
#             f"CBMC verification task failed with returncode {CBMC_PROOFS_TASK.returncode}: {stderr.decode('ascii')}"
#         )

#     elif CBMC_PROOFS_TASK.returncode < 0:
#         log.warn(
#             f"CBMC verification task cancelled by user (signal={-CBMC_PROOFS_TASK.returncode})"
#         )

#     log.info(f"CBMC verification task completed: {stdout.decode('ascii')}")
#     CBMC_PROOFS_TASK = None
