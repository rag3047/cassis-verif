import re

from os import getenv
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChainableUndefined
from pathlib import Path
from logging import getLogger

from .controllers.git import get_git_config
from .controllers.cbmc import get_cbmc_proofs
from .controllers.ctags import get_functions

log = getLogger(__name__)

PROOF_ROOT = getenv("PROOF_ROOT")

templates = Jinja2Templates(directory="app/templates", undefined=ChainableUndefined)
# templates.env.filters["json_encode"] = json.dumps
# templates.env.globals["project_name"] = "CBMC Starter Kit"
pages = APIRouter()


@pages.route("/")
async def home(request: Request) -> HTMLResponse:
    try:
        git_config = await get_git_config()

    except HTTPException as e:
        git_config = None

    context = {
        "request": request,
        "proofs": await get_cbmc_proofs(),
        "git_config": git_config,
        "functions": await get_functions(limit=5),
    }
    return templates.TemplateResponse("home.html", context)


@pages.route("/results")
async def results(request: Request) -> HTMLResponse:
    context = {
        "request": request,
    }
    return templates.TemplateResponse("results.html", context)


@pages.route("/software-design-document")
async def software_design_document(request: Request) -> HTMLResponse:
    context = {
        "request": request,
    }
    return templates.TemplateResponse("software-design-document.html", context)


@pages.route("/editor")
async def editor(request: Request) -> HTMLResponse:
    proof_name = request.query_params.get("proof_name")
    log.debug(f"{proof_name=}")

    if proof_name is None:
        raise HTTPException(
            status_code=400,
            detail="Missing required query parameter 'proof_name'",
        )

    makefile = Path(PROOF_ROOT) / proof_name / "Makefile"

    match = re.search(
        r"^\s*HARNESS_FILE\s+=\s+(?P<file>.*)$",
        makefile.read_text(),
        re.MULTILINE,
    )

    if match is None:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve harness name for proof '{proof_name}'",
        )

    harness: str = match.group("file")
    log.debug(f"{harness=}")

    harness_file = Path(PROOF_ROOT) / proof_name / (harness + ".c")
    log.debug(f"{harness_file=}")

    if not harness_file.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Could not find harness file for proof '{proof_name}'",
        )

    context = {
        "request": request,
        # "files": await get_proof_files(proof_name),
        "proof_name": proof_name,
        "file_name": harness + ".c",
    }
    return templates.TemplateResponse("editor.html", context)
