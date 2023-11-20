from os import getenv
from typing import Annotated
from fastapi import APIRouter, Query
from pathlib import Path
from cbmc_starter_kit import repository
from logging import getLogger
from pydantic import BaseModel

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
    tags = repository.function_tags(DATA_DIR)

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
