import json

from logging import getLogger
from pathlib import Path

from ..utils.models import Hint

log = getLogger(__name__)

HINTS_DIR = Path("hints")
HINTS_DB: dict[str, dict[str, str]] = {}

if not HINTS_DIR.exists():
    log.warn(
        f"No Hints directory found. Consider using the Hints-API or adding a hints.tgz file the project preset."
    )

else:
    hint_files = [f for f in HINTS_DIR.iterdir() if f.is_file() and f.suffix == ".json"]
    log.debug(f"Found {len(hint_files)} hint files")

    for file in hint_files:
        type = file.stem.split("_")[0]
        HINTS_DB[type] = json.loads(file.read_text())

    log.info(f"Loaded hints for the following types: {list(HINTS_DB.keys())}")


async def get_function_hint(function_name: str) -> Hint:
    """Get the hint for a function"""
    log.info(f"Getting hint for function {function_name}")

    function_hints = HINTS_DB.get("function", {})
    return Hint(hint=function_hints.get(function_name, None))


async def get_struct_hints(struct_name: str) -> Hint:
    """Get the hints for a struct"""
    log.info(f"Getting hints for struct {struct_name}")

    struct_hints = HINTS_DB.get("struct", {})
    return Hint(hint=struct_hints.get(struct_name, None))


async def get_macro_hint(macro_name: str) -> Hint:
    """Get the hint for a macro"""
    log.info(f"Getting hint for macro {macro_name}")

    macro_hints = HINTS_DB.get("macro", {})
    return Hint(hint=macro_hints.get(macro_name, None))
