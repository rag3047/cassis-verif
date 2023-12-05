import re

from os import getenv
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChainableUndefined
from logging import getLogger

from .controllers.cbmc import (
    get_cbmc_proofs,
    get_cbmc_verification_task_result_list,
    get_cbmc_verification_task_status,
)

log = getLogger(__name__)

PROOF_ROOT = getenv("PROOF_ROOT")

templates = Jinja2Templates(directory="app/templates", undefined=ChainableUndefined)
pages = APIRouter()


@pages.route("/")
async def home(request: Request) -> HTMLResponse:
    log.info("Rendering home page")

    context = {
        "request": request,
        "proofs": await get_cbmc_proofs(),
        "task_status": await get_cbmc_verification_task_status(),
        "results": await get_cbmc_verification_task_result_list(),
    }

    return templates.TemplateResponse("home.html", context)


@pages.route("/results")
async def results(request: Request) -> HTMLResponse:
    log.info("Rendering results page")

    version = request.query_params.get("version", "latest")
    log.debug(f"{version=}")

    context = {
        "request": request,
        "version": version,
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

    # TODO: add support for pre-selected path/file based on proof name
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
