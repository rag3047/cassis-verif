from os import getenv
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChainableUndefined
from logging import getLogger
from contextlib import suppress
from asyncio import gather

from .controllers.hints import get_function_hint
from .controllers.sdd import get_sdd_available
from .controllers.doxygen import (
    get_doxygen_docs,
    get_doxygen_callgraph_image_paths,
    get_doxygen_function_params,
    get_doxygen_function_refs,
)
from .controllers.cbmc import (
    get_cbmc_proof_by_name,
    get_cbmc_proofs,
    get_verification_tasks,
    get_verification_task_status,
    get_cbmc_loop_info,
    get_latest_verification_result,
)


log = getLogger(__name__)

PROOF_ROOT = getenv("PROOF_ROOT")

templates = Jinja2Templates(directory="app/templates", undefined=ChainableUndefined)
pages = APIRouter()


@pages.route("/")
async def home(request: Request) -> HTMLResponse:
    log.info("Rendering home page")

    proofs = await get_cbmc_proofs()

    stats = {}
    for proof in proofs:
        stats[proof.name] = await get_latest_verification_result(proof.name)

    context = {
        "title": "Home | Cassis-Verif",
        "request": request,
        "proofs": proofs,
        "task_status": await get_verification_task_status(),
        "results": await get_verification_tasks(),
        "stats": stats,
    }

    return templates.TemplateResponse("home.html", context)


@pages.route("/results")
async def results(request: Request) -> HTMLResponse:
    log.info("Rendering results page")

    version = request.query_params.get("version", "latest")
    log.debug(f"{version=}")

    file_path = request.query_params.get("file-path", "index.html")
    log.debug(f"{file_path=}")

    context = {
        "title": "Results | Cassis-Verif",
        "request": request,
        "version": version,
        "file_path": file_path,
    }

    return templates.TemplateResponse("results.html", context)


@pages.route("/software-design-document")
async def software_design_document(request: Request) -> HTMLResponse:
    log.info("Rendering software design document page")

    context = {
        "title": "SDD | Cassis-Verif",
        "sdd_available": await get_sdd_available(),
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
        "title": "Doxygen | Cassis-Verif",
        "request": request,
    }

    return templates.TemplateResponse("doxygen.html", context)


@pages.route("/editor")
async def editor(request: Request) -> HTMLResponse:
    log.info("Rendering editor page")

    file_path = request.query_params.get("file-name", None)
    proof_name = request.query_params.get("proof-name", None)
    log.debug(f"{file_path=}")
    log.debug(f"{proof_name=}")

    selected_proof = None
    loops = []
    callgraphs = None
    params = []
    references = []
    hint = None

    if proof_name:
        with suppress(HTTPException):
            [selected_proof, loops, hint] = await gather(
                get_cbmc_proof_by_name(proof_name),
                get_cbmc_loop_info(proof_name),
                get_function_hint(proof_name),
                # return_exceptions=True,
            )

    if proof_name and file_path and file_path != "None":
        file_name = file_path.split("/")[-1]

        with suppress(HTTPException):
            [callgraphs, params, references] = await gather(
                get_doxygen_callgraph_image_paths(file_name, proof_name),
                get_doxygen_function_params(file_name, proof_name),
                get_doxygen_function_refs(file_name, proof_name),
                # return_exceptions=True,
            )

    log.debug(f"{selected_proof=}")
    log.debug(f"{loops=}")
    log.debug(f"{callgraphs=}")
    log.debug(f"{params=}")
    log.debug(f"{references=}")
    log.debug(f"{hint=}")

    context = {
        "title": "Editor | Cassis-Verif",
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


@pages.route("/howto")
async def howto(request: Request) -> HTMLResponse:
    log.info("Rendering howto page")

    context = {
        "title": "How To | Cassis-Verif",
        "request": request,
    }

    return templates.TemplateResponse("howto.html", context)
