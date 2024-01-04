from os import getenv
from logging import getLogger

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
    from .__hints_prebuilt import router

else:
    log.info("Using hints API")
    from .__hints_api import router

__all__ = ["router"]
