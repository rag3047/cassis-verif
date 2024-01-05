from logging import getLogger
from pydantic import BaseModel

log = getLogger(__name__)


class Hint(BaseModel):
    hint: str | None


async def get_function_hint(function_name: str) -> Hint:
    """Get the hint for a function"""
    log.info(f"Getting hint for function {function_name}")

    # TODO
    raise NotImplementedError()


async def get_struct_hints(struct_name: str) -> Hint:
    """Get the hints for a struct"""
    log.info(f"Getting hints for struct {struct_name}")

    # TODO
    raise NotImplementedError()


async def get_macro_hint(macro_name: str) -> Hint:
    """Get the hint for a macro"""
    log.info(f"Getting hint for macro {macro_name}")

    # TODO
    raise NotImplementedError()
