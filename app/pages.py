from os import getenv
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChainableUndefined
from logging import getLogger
from contextlib import suppress

from .controllers.hints import get_function_hint
from .controllers.doxygen import (
    get_doxygen_docs,
    get_doxygen_callgraph_image_paths,
    get_doxygen_function_params,
    get_doxygen_function_refs,
)
from .controllers.cbmc import (
    get_cbmc_proof,
    get_cbmc_proofs,
    get_cbmc_verification_task_result_list,
    get_cbmc_verification_task_status,
    get_cbmc_proof_loop_info,
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

    doxygen_available = False
    href = request.query_params.get("href", "index.html")

    try:
        await get_doxygen_docs("")
        doxygen_available = True

    except HTTPException:
        pass

    context = {
        "doxygen_available": doxygen_available,
        "href": href,
        "request": request,
    }

    return templates.TemplateResponse("doxygen.html", context)


@pages.route("/editor")
async def editor(request: Request) -> HTMLResponse:
    log.info("Rendering editor page")

    file_name = request.query_params.get("file-name", None)
    proof_name = request.query_params.get("proof-name", None)
    log.debug(f"{file_name=}")
    log.debug(f"{proof_name=}")

    selected_proof = None
    loops = []
    callgraphs = None
    params = []
    references = []
    hint = None

    if proof_name:
        with suppress(HTTPException):
            selected_proof = await get_cbmc_proof(proof_name)

        with suppress(HTTPException):
            loops = await get_cbmc_proof_loop_info(proof_name)

        with suppress(HTTPException):
            hint = await get_function_hint(proof_name)

    if proof_name and file_name and file_name != "None":
        with suppress(HTTPException):
            callgraphs = await get_doxygen_callgraph_image_paths(
                file_name.split("/")[-1],
                proof_name,
            )

        with suppress(HTTPException):
            params = await get_doxygen_function_params(
                file_name.split("/")[-1],
                proof_name,
            )

        with suppress(HTTPException):
            references = await get_doxygen_function_refs(
                file_name.split("/")[-1],
                proof_name,
            )

    log.debug(f"{selected_proof=}")
    log.debug(f"{loops=}")
    log.debug(f"{callgraphs=}")
    log.debug(f"{params=}")
    log.debug(f"{references=}")
    log.debug(f"{hint=}")

    context = {
        "request": request,
        "selected_proof": selected_proof,
        "proofs": await get_cbmc_proofs(),
        "loops": loops,
        "graphs": callgraphs,
        "params": params,
        "references": references,
        "hint": hint,
    }

    return templates.TemplateResponse("editor.html", context)
