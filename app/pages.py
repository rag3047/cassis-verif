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
from .controllers.files import list_directory_tree

log = getLogger(__name__)

PROOF_ROOT = getenv("PROOF_ROOT")

templates = Jinja2Templates(directory="app/templates", undefined=ChainableUndefined)
# templates.env.filters["json_encode"] = json.dumps
# templates.env.globals["project_name"] = "CBMC Starter Kit"
pages = APIRouter()


@pages.route("/")
async def home(request: Request) -> HTMLResponse:
    log.info("Rendering home page")

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
    log.info("Rendering results page")

    context = {
        "request": request,
    }
    return templates.TemplateResponse("results.html", context)


@pages.route("/software-design-document")
async def software_design_document(request: Request) -> HTMLResponse:
    log.info("Rendering software design document page")

    context = {
        "request": request,
    }
    return templates.TemplateResponse("software-design-document.html", context)


@pages.route("/doxygen")
async def doxygen(request: Request) -> HTMLResponse:
    log.info("Rendering doxygen page")

    context = {
        "request": request,
    }
    return templates.TemplateResponse("doxygen.html", context)


@pages.route("/editor")
async def editor(request: Request) -> HTMLResponse:
    log.info("Rendering editor page")

    file_path = request.query_params.get("file_path", None)
    log.debug(f"{file_path=}")
    # include_hidden = request.query_params.get("include_hidden", False)
    # log.debug(f"include hidden files: {include_hidden}")

    context = {
        "request": request,
        "file_path": file_path,
        # "files": await list_directory_tree(include_hidden=include_hidden),
    }

    return templates.TemplateResponse("editor.html", context)
