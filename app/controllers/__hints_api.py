from logging import getLogger

from ..utils.models import Hint

log = getLogger(__name__)


async def get_function_hint(function_name: str) -> Hint:
    """Get the hint for a function"""
    log.info(f"Getting hint for function {function_name}")

    # TODO
    log.warn("Hints API currently not implemented")
    return Hint(hint=None)


async def get_struct_hints(struct_name: str) -> Hint:
    """Get the hints for a struct"""
    log.info(f"Getting hints for struct {struct_name}")

    # TODO
    log.warn("Hints API currently not implemented")
    return Hint(hint=None)


async def get_macro_hint(macro_name: str) -> Hint:
    """Get the hint for a macro"""
    log.info(f"Getting hint for macro {macro_name}")

    # TODO
    log.warn("Hints API currently not implemented")
    return Hint(hint=None)
