from os import getenv
from logging import getLogger
from fastapi import APIRouter

log = getLogger(__name__)

USE_PREBUILT_HINTS = getenv("USE_PREBUILT_HINTS", "").lower() in (
    "true",
    "y",
    "yes",
    "1",
    "on",
)

if USE_PREBUILT_HINTS:
    log.info("Using prebuilt hints")
    from .__hints_prebuilt import get_function_hint, get_struct_hints, get_macro_hint

else:
    log.info("Using hints API")
    from .__hints_api import get_function_hint, get_struct_hints, get_macro_hint


router = APIRouter(prefix="/hints", tags=["hints"])
router.add_api_route("/function/{function_name}", get_function_hint)
router.add_api_route("/struct/{struct_name}", get_struct_hints)
router.add_api_route("/macro/{macro_name}", get_macro_hint)
