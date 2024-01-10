from os import getenv
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse
from logging import getLogger
from asyncio.subprocess import Process, create_subprocess_exec, PIPE
from pathlib import Path
from asyncio import Task, create_task
from pydantic import BaseModel
from lxml import etree as ET
from lxml.etree import _Element as Element, _ElementTree as ElementTree

from ..utils.models import HTTPError
from .hints import get_hints

log = getLogger(__name__)


router = APIRouter(prefix="/doxygen", tags=["doxygen"])

DOXYGEN_DIR = getenv("DOXYGEN_DIR")
DOXYGEN_BUILD_TASK: Process | None = None
DOXYGEN_INIT_TASK: Task | None = None


@router.post(
    "/build",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_409_CONFLICT: {"model": HTTPError}},
)
async def build_doxygen_doc():
    """Build the doxygen documentation"""
    global DOXYGEN_BUILD_TASK
    log.info("Building doxygen documentation")
    _check_doxygen_is_available()

    # call doxygen in subprocess
    DOXYGEN_BUILD_TASK = await create_subprocess_exec(
        "doxygen",
        "Doxyfile",
        cwd=DOXYGEN_DIR,
        stdout=PIPE,
        stderr=PIPE,
    )

    _, stderr = await DOXYGEN_BUILD_TASK.communicate()

    if DOXYGEN_BUILD_TASK.returncode > 0:
        log.error(
            f"Doxygen build task failed with returncode {DOXYGEN_BUILD_TASK.returncode}: {stderr.decode('ascii')}"
        )

    log.info(f"Doxygen build task completed")
    DOXYGEN_BUILD_TASK = None


@router.get(
    # Note: this path allows for directory browsing using relative paths (i.e. navigate doxygen)
    "/docs/{file_path:path}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_doxygen_docs(file_path: str) -> FileResponse:
    """Return doxygen documentation."""
    log.info("Get doxygen documentation")
    _check_doxygen_is_available()

    file_path = file_path or "index.html"
    abs_path = Path(DOXYGEN_DIR) / "html" / file_path

    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"File not found: {file_path}")

    return FileResponse(abs_path)


class DoxygenCallgraphs(BaseModel):
    file_href: Path
    callgraph: Path
    inverse_callgraph: Path


@router.get(
    "/callgraphs",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_doxygen_callgraph_image_paths(
    file_name: Annotated[str, Query(..., alias="file-name")],
    func_name: Annotated[str, Query(..., alias="func-name")],
) -> DoxygenCallgraphs:
    """Return the paths to the doxygen callgraph images."""
    log.info("Get doxygen callgraph image paths")
    _check_doxygen_is_available()

    index = _get_doxygen_index()
    _, func_ref = _get_file_and_func_refs(index, file_name, func_name)

    html_dir = Path(DOXYGEN_DIR) / "html"

    # TODO: this is a weird hack to get the file path from the function refid and
    # might not work in all cases?
    file_href = Path(func_ref.replace("_1", ".html#"))
    func_ref = func_ref.replace("_1", "_")
    callgraph = html_dir / f"{func_ref}_cgraph_org.svg"
    inverse_callgraph = html_dir / f"{func_ref}_icgraph_org.svg"

    # "_org" files for callgraphs are only generated if the callgraph is large.
    # If they don't exist, use the normal files.
    if not callgraph.exists():
        callgraph = html_dir / f"{func_ref}_cgraph.svg"

    if not inverse_callgraph.exists():
        inverse_callgraph = html_dir / f"{func_ref}_icgraph.svg"

    log.debug(f"{file_href=!s}")
    log.debug(f"{callgraph=!s}")
    log.debug(f"{inverse_callgraph=!s}")

    if not callgraph.exists() or not inverse_callgraph.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Callgraph images not found. Try rebuilding the doxygen documentation.",
        )

    return DoxygenCallgraphs(
        file_href=file_href,
        callgraph=callgraph.relative_to(html_dir),
        inverse_callgraph=inverse_callgraph.relative_to(html_dir),
    )


class DoxygenFunctionParam(BaseModel):
    type: str
    name: str
    ref: str | None = None
    hint: str | None = None


@router.get(
    "/function-params",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_doxygen_function_params(
    file_name: Annotated[str, Query(..., alias="file-name")],
    func_name: Annotated[str, Query(..., alias="func-name")],
) -> list[DoxygenFunctionParam]:
    """Return the function parameters for the given file and function."""
    log.info("Get doxygen function parameters")
    _check_doxygen_is_available()

    index = _get_doxygen_index()
    file_ref, func_ref = _get_file_and_func_refs(index, file_name, func_name)

    function_params = _get_function_params(file_ref, func_ref)

    for param in function_params:
        if param.type.startswith("struct"):
            struct_name = param.type.split(" ")[1]
            param.hint = (await get_hints("struct", struct_name)).hint

    return function_params


class DoxygenFunctionRef(BaseModel):
    name: str
    kind: str
    href: str
    type: str | None = None
    hint: str | None = None


@router.get(
    "/function-refs",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPError},
        status.HTTP_409_CONFLICT: {"model": HTTPError},
    },
)
async def get_doxygen_function_refs(
    file_name: Annotated[str, Query(..., alias="file-name")],
    func_name: Annotated[str, Query(..., alias="func-name")],
) -> list[DoxygenFunctionRef]:
    """Return the function's references for the given file and function."""
    log.info("Get doxygen function references")
    _check_doxygen_is_available()

    index = _get_doxygen_index()
    file_ref, func_ref = _get_file_and_func_refs(index, file_name, func_name)

    function_refs = _get_function_refs(file_ref, func_ref)

    # get hints for function refs (if any)
    for ref in function_refs:
        ref.hint = (await get_hints(ref.kind, ref.name)).hint

    return sorted(
        [ref for ref in function_refs if "::" not in ref.name],
        key=lambda x: x.kind,
    )


# ------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------


# Note: startup events are deprecated, but lifespan is not currently
#       supported on APIRouter (only on FastAPI itself)
@router.on_event("startup")
async def init_doxygen():
    """Initialize doxygen."""
    global DOXYGEN_INIT_TASK
    log.info("Doxygen startup initialization")
    # Note: we need to keep a reference to the task, because the event loop
    #       only keeps weak references. Otherwise, the task might be garbage
    #       collected mid-execution.
    DOXYGEN_INIT_TASK = create_task(build_doxygen_doc())


# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------


def _check_doxygen_is_available() -> None:
    """Check if doxygen is available."""
    if DOXYGEN_BUILD_TASK is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Doxygen build task running",
        )


def _get_doxygen_index() -> ElementTree:
    """Return the parsed doxygen index file."""
    log.info("Getting doxygen index file")

    index_file = Path(DOXYGEN_DIR) / "xml" / "index.xml"

    if not index_file.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Index file not found. Try rebuilding the doxygen documentation.",
        )

    return ET.parse(index_file)


def _get_file_and_func_refs(
    index: ElementTree,
    file_name: str,
    func_name: str,
) -> tuple[str, str]:
    """Retrieve file and function refids from the doxygen index."""
    log.info("Retrieving file and function refids")

    xpath = f"./compound[@kind='file' and name='{file_name}']"
    files: list[Element] = index.xpath(xpath)

    if len(files) == 0:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"File '{file_name}' not found in doxygen index.",
        )

    file = files[0]

    xpath = f"./member[@kind='function' and name='{func_name}']"
    functions: list[Element] = file.xpath(xpath)

    if len(functions) == 0:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Function '{func_name}' not found in doxygen index.",
        )

    func = functions[0]

    file_ref: str = file.get("refid")
    func_ref: str = func.get("refid")

    log.debug(f"{file_ref=}")
    log.debug(f"{func_ref=}")

    return file_ref, func_ref


def _get_function_params(file_ref: str, func_ref: str) -> list[DoxygenFunctionParam]:
    """Return the function parameters for the given file and function refids."""
    log.info("Getting doxygen function parameters")

    xml_file = Path(DOXYGEN_DIR) / "xml" / f"{file_ref}.xml"
    log.debug(f"{xml_file=!s}")

    if not xml_file.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"File '{file_ref}' not found in doxygen output.",
        )

    file_data: ElementTree = ET.parse(xml_file)

    xpath = f"./compounddef/sectiondef[@kind ='func']/memberdef[@kind='function' and @id='{func_ref}']/param"
    param_list: list[Element] = file_data.xpath(xpath)
    log.debug(f"#params={len(param_list)}")

    params: list[DoxygenFunctionParam] = []

    for param in param_list:
        param_type: Element = param.xpath("type")[0]
        param_name: str = param.xpath("declname/text()")[0]
        param_ref: list[Element] = param_type.xpath("ref")

        param_type_str: str = param_type.text
        param_ref_id: str | None = None

        if len(param_ref) > 0:
            param_ref_id = param_ref[0].get("refid", None)
            param_type_str += param_ref[0].text + param_ref[0].tail

        params.append(
            DoxygenFunctionParam(
                type=param_type_str,
                name=param_name,
                ref=param_ref_id,
            )
        )

    return params


def _get_function_refs(
    file_ref: str,
    func_ref: str,
) -> list[DoxygenFunctionRef]:
    """Return the function's references for the given file and function refids."""
    log.info("Getting doxygen function references")

    xml_file = Path(DOXYGEN_DIR) / "xml" / f"{file_ref}.xml"
    log.debug(f"{xml_file=!s}")

    if not xml_file.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"File '{file_ref}' not found in doxygen output.",
        )

    file_data: ElementTree = ET.parse(xml_file)

    xpath = f"./compounddef/sectiondef[@kind ='func']/memberdef[@kind='function' and @id='{func_ref}']/references"
    ref_list: list[Element] = file_data.xpath(xpath)
    log.debug(f"#refs={len(ref_list)}")

    refs: list[DoxygenFunctionRef] = []

    for ref in ref_list:
        ref_name: str = ref.text
        file, id = ref.get("refid").split("_1")

        if file == file_ref:
            # lookup ref in current file (file_data)
            xpath = f"./compounddef/sectiondef/memberdef[@id='{ref.get('refid')}']"
            data: Element = file_data.xpath(xpath)[0]
            ref_kind: str = data.get("kind")
            ref_type: str = data.findtext("type")

        else:
            # lookup ref in other file
            xpath = f"./compounddef/sectiondef/memberdef[@id='{ref.get('refid')}']"
            file_path = Path(DOXYGEN_DIR) / "xml" / f"{file}.xml"
            other_file_data: ElementTree = ET.parse(file_path)
            data: Element = other_file_data.xpath(xpath)[0]
            ref_kind: str = data.get("kind")
            ref_type: str = data.findtext("type")

        ref_kind = "macro" if ref_kind == "define" else ref_kind

        refs.append(
            DoxygenFunctionRef(
                name=ref_name,
                kind=ref_kind,
                type=ref_type,
                href=file + ".html#" + id,
            )
        )

    return refs
