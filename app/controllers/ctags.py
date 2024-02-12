import json

from os import getenv
from typing import Annotated
from fastapi import APIRouter, Query
from pathlib import Path
from logging import getLogger
from pydantic import BaseModel
from subprocess import Popen, PIPE

log = getLogger(__name__)

DATA_DIR = getenv("DATA_DIR")

router = APIRouter(prefix="/ctags", tags=["ctags"])


class Function(BaseModel):
    name: str
    file: Path


class PagedResponse(BaseModel):
    data: list[Function]
    cursor: int
    total: int


@router.get("/functions")
async def get_functions(
    limit: Annotated[int, Query(ge=1)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    filter: str = "",
) -> PagedResponse:
    """Return list of all functions in all source files."""

    log.info("Reading functions from disk")
    tags = _function_tags(DATA_DIR)

    cbmc_dir = Path(DATA_DIR) / "cbmc"

    functions = [
        Function(
            name=tag["symbol"],
            file=tag["file"].relative_to(DATA_DIR),
        )
        for tag in tags
        # TODO: move this filter to funcion_tags function?
        # skip files in cbmc folder
        if cbmc_dir not in tag["file"].parents
    ]

    if filter:
        functions = [
            function
            for function in functions
            if filter.lower() in function.name.lower()
            or filter.lower() in str(function.file)
        ]

    log.debug(f"Found {len(functions)} functions (after filtering)")
    return PagedResponse(
        data=sorted(functions, key=lambda func: func.name)[offset : offset + limit],
        cursor=offset + limit,
        total=len(functions),
    )


def _function_tags(repo="."):
    """List of tags for function definitions in respository source files.

    Each tag is a dict '{"name": function, "path": source}' naming a
    function and a source file defining the function."""

    repo = Path(repo).resolve()

    files = ""

    find_cmd = ["find", ".", "-name", "*.c"]
    with Popen(find_cmd, cwd=repo, text=True, stdout=PIPE, stderr=PIPE) as pipe:
        files, _ = pipe.communicate()

    find_cmd = ["find", ".", "-name", "*.cpp"]
    with Popen(find_cmd, cwd=repo, text=True, stdout=PIPE, stderr=PIPE) as pipe:
        files_cpp, _ = pipe.communicate()
        files += files_cpp

    if files is None:  # run() logs errors on debug
        return []

    # legacy ctags does not give the kind of a symbol
    # assume a symbol is a function if the kind is None
    tags = _universal_ctags(repo, files.split())
    return [tag for tag in tags if tag["kind"] in ["function", None]]


def _universal_ctags(root, files):
    """Use universal ctags to list symbols defined in files under root."""

    # See universal ctags man page at https://docs.ctags.io/en/latest/man/ctags.1.html
    cmd = [
        "ctags",
        "-L",
        "-",  # read files from standard input, one file per line
        "-f",
        "-",  # write tags to standard output, one tag per line
        "--output-format=json",  # each tag is a one-line json blob
        "--fields=FNnK",  # json blob is {"name": symbol, "path": file, "line": line, "kind": kind}
    ]

    with Popen(
        cmd,
        cwd=root,
        text=True,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        encoding="utf-8",
    ) as pipe:
        stdout, _ = pipe.communicate(input="\n".join(files))
        strings = stdout.splitlines()

    return [tag for string in strings for tag in _extract_tag(root, string)]


def _extract_tag(root, string):
    """Extract tag from universal ctag output."""

    try:
        # universal ctag json output is '{"name": symbol, "path": file, "line": line, "kind": kind}'
        blob = json.loads(string)
        return [
            {
                "symbol": blob["name"],
                "file": root / blob["path"],
                "line": int(blob["line"]),
                "kind": blob["kind"],
            }
        ]
    except (
        json.decoder.JSONDecodeError,  # json is unparsable
        KeyError,  # json key is missing
        ValueError,  # invalid literal for int()
    ):
        return []
