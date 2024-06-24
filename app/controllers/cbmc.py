import re
import json
import psutil

from typing import Literal
from os import getenv, remove, linesep
from logging import getLogger
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    WebSocket,
    status,
    Request,
)
from websockets.exceptions import ConnectionClosedOK
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, UUID4
from pathlib import Path
from shutil import rmtree, make_archive, copytree
from cbmc_starter_kit import setup_proof
from asyncio import sleep
from asyncio.subprocess import Process, create_subprocess_exec, PIPE
from datetime import datetime, timezone
from io import TextIOWrapper

from ..utils.models import HTTPError
from ..utils.html import inject_css_links

log = getLogger(__name__)

DATA_DIR = getenv("DATA_DIR")
PROOF_ROOT = getenv("PROOF_ROOT")
CBMC_ROOT = getenv("CBMC_ROOT")

VERIFICATION_TASK: Process | None = None
VERIFICATION_TASK_OUTPUT = Path(PROOF_ROOT) / "output/output.txt"

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
    report_link: str


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
async def get_cbmc_proof_by_name(proof_name: str) -> CBMCProof:
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

    if VERIFICATION_TASK is not None:
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
async def get_cbmc_loop_info(
    proof_name: str,
    rebuild: bool = False,
) -> list[CBMCLoop]:
    """Return a list of loops in the given cbmc proof."""
    log.info(f"Get loop info for proof '{proof_name}' ({rebuild=})")

    proof = await get_cbmc_proof_by_name(proof_name)
    proof_dir = Path(PROOF_ROOT) / proof_name
    goto_binary = proof_dir / "gotos" / proof.harness.replace(".c", ".goto")

    # only build goto binary if it doesn't exist or rebuild is True
    if rebuild or not goto_binary.exists():
        if VERIFICATION_TASK is not None:
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


class VerificationTask(BaseModel):
    name: str
    start_time: datetime


@router.get("/tasks")
async def get_verification_tasks() -> list[VerificationTask]:
    """Return list of all verification tasks."""
    log.info("Get verification tasks")

    path = Path(f"{PROOF_ROOT}/output/litani/runs")

    if not path.exists():
        return []

    task_dirs = [dir for dir in path.iterdir() if dir.is_dir()]
    start_times: list[datetime] = []

    for dir in task_dirs:
        try:
            run_json = dir / "html/run.json"
            run_data = json.loads(run_json.read_text())
            # Note: python 3.10 does not allow parsing of the following iso format: 2024-02-07T13:14:50Z
            #       therefore we need to drop the timezone information and add it manually
            start_time = datetime.fromisoformat(run_data["start_time"][:-1])
            # manually set timezone to UTC (without changing the time itself)
            start_time = start_time.replace(tzinfo=timezone.utc)
            # convert to local timezone
            start_times.append(start_time.astimezone())

        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            start_times.append(datetime.fromtimestamp(dir.stat().st_ctime).astimezone())

    results = [
        VerificationTask(
            name=dir.name,
            start_time=start_time,
        )
        for dir, start_time in zip(task_dirs, start_times, strict=True)
    ]

    log.debug(f"{results=}")

    return sorted(results, key=lambda run: run.start_time, reverse=True)


@router.post(
    "/tasks",
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def start_verification_task(tasks: BackgroundTasks) -> VerificationTask:
    """Start a new verification task."""
    global VERIFICATION_TASK, VERIFICATION_TASK_OUTPUT
    log.info("Start verification task")

    if VERIFICATION_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Verification Task already running",
        )

    num_proof_runs = _get_verification_task_count()

    # create output buffer file
    VERIFICATION_TASK_OUTPUT.parent.mkdir(exist_ok=True)
    VERIFICATION_TASK_OUTPUT.touch(exist_ok=True)
    fd = VERIFICATION_TASK_OUTPUT.open("w")

    # call run-cbmc-proofs.py in subprocess
    VERIFICATION_TASK = await create_subprocess_exec(
        "python3",
        "run-cbmc-proofs.py",
        cwd=PROOF_ROOT,
        stdout=fd,
        stderr=PIPE,
    )

    tasks.add_task(_cleanup_verification_task, fd)

    proof_runs = await get_verification_tasks()

    # wait until litani is initialized
    while len(proof_runs) <= num_proof_runs:
        await sleep(0.5)
        proof_runs = await get_verification_tasks()

    # if len(proof_runs) > 10:  # TODO: get from env
    #     # remove oldest run
    #     rmtree(Path(PROOF_ROOT) / "output/litani/runs" / proof_runs[-1].name)

    return proof_runs[0]


@router.delete(
    "/tasks/current",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def cancel_verification_task() -> None:
    """Cancel the currently running verification task"""
    global VERIFICATION_TASK
    log.info("Canceling verification task")

    if VERIFICATION_TASK is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Verification task not running")

    # Note: for some weird reaseon CBMC_PROOFS_TASK.terminate() does not actually terminate
    #       the process (might be because the subprocess is waiting on subprocess.run() itself).
    #       Therefore, we need to manually terminate the process and all its children.
    # TODO: Currently, this leaves a bunch of zombie processes behind, which should probably be
    #       fixed at some point.

    proc = psutil.Process(VERIFICATION_TASK.pid)
    proc.terminate()
    for child in proc.children(recursive=True):
        child.terminate()


class VerificationTaskStatus(BaseModel):
    is_running: bool
    # TODO: maybe add more fields like stdout, stderr, etc.


@router.get("/tasks/current/status")
async def get_verification_task_status() -> VerificationTaskStatus:
    """Return status of the currently running verification task."""
    log.info("Get verification task status")
    return VerificationTaskStatus(is_running=VERIFICATION_TASK is not None)


@router.websocket("/tasks/current/output")
async def get_verification_task_output(websocket: WebSocket) -> None:
    """Return output of the current verification task."""
    log.info("Get verification task output")

    await websocket.accept()

    if not VERIFICATION_TASK_OUTPUT.exists():
        await websocket.send_text("No output available")
        await websocket.close()
        return

    try:
        with open(VERIFICATION_TASK_OUTPUT, "r") as file:
            # send current file contents
            for line in file:
                await websocket.send_text(line)

            # send new lines as they are added until task is completed
            while VERIFICATION_TASK is not None:
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


class VerificationResult(BaseModel):
    # proof_name: str
    is_complete: bool = False
    status: str | None = None
    errors: list[str] = []
    coverage_percentage: float | None = None


@router.get("/tasks/current/result/{proof_name}")
async def get_latest_verification_result(
    proof_name: str,
) -> VerificationResult:
    """Return results of the latest verification task."""
    log.info("Get latest verification task result")
    log.debug(f"{proof_name=}")

    report_dir = (
        Path(PROOF_ROOT) / "output/latest/html/artifacts" / proof_name / "report/json"
    )

    if not report_dir.exists():
        log.debug(f"Report not found: {report_dir}")
        return VerificationResult(is_complete=False)

    status = None
    errors: list[str] = []
    coverage_percentage: float | None = None

    result_json = report_dir / "viewer-result.json"
    if result_json.exists():
        result = json.loads(result_json.read_text())
        viewer_result = result.get("viewer-result", {})

        status = viewer_result.get("prover", "")
        errors = viewer_result.get("results", {}).get("false", [])

    else:
        log.debug(f"Result file not found: {result_json}")

    coverage_json = report_dir / "viewer-coverage.json"
    if coverage_json.exists():
        coverage = json.loads(coverage_json.read_text())
        viewer_coverage = coverage.get("viewer-coverage", {})

        coverage_percentage = viewer_coverage.get("overall_coverage", {}).get(
            "percentage", None
        )

    else:
        log.debug(f"Coverage file not found: {coverage_json}")

    log.debug(f"{status=}")
    log.debug(f"{errors=}")
    log.debug(f"{coverage_percentage=}")

    return VerificationResult(
        is_complete=True,
        status=status,
        errors=errors,
        coverage_percentage=coverage_percentage,
    )


@router.get(
    "/tasks/{version}/download",
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPError}},
)
async def download_verification_task_result(
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


@router.get(
    # Note: this path allows for directory browsing using relative paths (i.e. navigate the dashboard)
    "/tasks/{version}/files/{file_path:path}",
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPError}},
    response_model=None,
)
async def get_verification_task_result(
    request: Request,
    version: UUID4 | Literal["latest"] = "latest",
    file_path: str | None = None,
) -> FileResponse | HTMLResponse:
    """Return results of CBMC proof execution."""
    log.info("Get CBMC verification task results")

    version_str = str(version).lower()
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

    if path.suffix != ".html":
        return FileResponse(path)

    # inject css links to style litani dashboard pages
    base_url = str(request.base_url)
    css_links = [
        f"{base_url}static/layout.css",
        f"{base_url}static/scrollbar.css",
        f"{base_url}static/results.css",
    ]

    log.debug(f"injecting css links: {css_links}")
    html = inject_css_links(path.read_text(), css_links)

    return HTMLResponse(content=html, status_code=200)


@router.delete(
    "/tasks/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def delete_verification_task_results(version: UUID4) -> None:
    """Delete verification task"""
    log.info("Delete CBMC verification task results")

    version_str = str(version).lower()
    log.debug(f"{version_str=}")

    runs = await get_verification_tasks()

    if not any(run.name == version_str for run in runs):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Version not found: {version_str}",
        )

    if runs[0].name == version_str and VERIFICATION_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot delete result of currently running verification task.",
        )

    path = Path(f"{PROOF_ROOT}/output/litani/runs/{version_str}")
    rmtree(path)


# ------------------------------------------------------------
# Download Data
# ------------------------------------------------------------


@router.get("/download")
async def download_all_cbmc_files(
    tasks: BackgroundTasks,
    format: Literal["zip", "tar", "gztar", "bztar", "xztar"] = "zip",
) -> None:
    """Download all CBMC files as an archive."""
    log.info("Download all CBMC files")

    path = Path(CBMC_ROOT)

    path = copytree(
        path,
        "/tmp/cbmc_data",
        # ignore output directory
        ignore=lambda path, names: names if "/output" in path else [],
    )

    abs_file_path = make_archive(
        "cbmc_data",  # archive file name
        format,
        path,  # root directory to archive
    )

    tasks.add_task(_cleanup_tmp_dir)
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
    global VERIFICATION_TASK
    log.debug("Cleanup verification task output")

    _, stderr = await VERIFICATION_TASK.communicate()

    fd.close()

    if VERIFICATION_TASK.returncode > 0:
        log.error(
            f"CBMC verification task failed with returncode {VERIFICATION_TASK.returncode}: {stderr.decode('ascii')}"
        )

    elif VERIFICATION_TASK.returncode < 0:
        log.warn(
            f"CBMC verification task cancelled by user (signal={-VERIFICATION_TASK.returncode})"
        )

    log.info(f"CBMC verification task completed")
    VERIFICATION_TASK = None


def _cleanup_archive_file(abs_file_path: str) -> None:
    """Delete archive file."""
    log.debug(f"Cleanup archive file after download: {abs_file_path}")
    remove(abs_file_path)


def _cleanup_tmp_dir() -> None:
    """Delete tmp directory content."""
    log.debug(f"Cleanup tmp directory after download")
    rmtree("/tmp/cbmc_data")


def _get_verification_task_count() -> int:
    """Return number of verification task."""
    log.info("Get number of verification task")

    path = Path(f"{PROOF_ROOT}/output/litani/runs")

    if not path.exists():
        return 0

    # count number of directories in output/litani/runs
    return sum(1 for el in path.iterdir() if el.is_dir())


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
        report_link=f"results?file-path=artifacts/{proof_dir.name}/report/html/index.html",
    )
