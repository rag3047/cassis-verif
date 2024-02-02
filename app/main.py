import logging

from os import getenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException
from pathlib import Path
from importlib import import_module

from .utils.models import HTTPError
from .pages import pages

app_path = getenv("APP_PATH", "")

app = FastAPI(root_path=app_path)
app.debug = getenv("DEBUG", "").lower() in ("true", "y", "yes", "1", "on")

log_level = getenv("LOG_LEVEL", "INFO").upper() if not app.debug else "DEBUG"
numeric_log_level = getattr(logging, log_level, None)

if not isinstance(numeric_log_level, int):
    raise ValueError(f"Invalid log level: {log_level}")

logging.basicConfig(
    level=numeric_log_level,
    format="%(asctime)s | %(levelname)s | [%(name)s:%(lineno)s - %(funcName)s]: %(message)s",
)

log = logging.getLogger(__name__)
log.info(f"Log level set to: {log_level}")
log.info(f"App path: {app_path}")

# dynamically load routes from controllers
controller_dir = Path(__file__).parent / "controllers"
controllers = (
    file
    for file in controller_dir.glob("*.py")
    if file.is_file() and not file.name.startswith("__")
)

for controller in controllers:
    log.info(f"Loading controller: {controller.stem}")
    module = import_module(f"app.controllers.{controller.stem}")
    try:
        router = module.router
    except AttributeError:
        log.warning(
            f"Module '{controller.stem}' does not have a router defined. Skipping."
        )
    else:
        app.include_router(router, prefix="/api/v1")

app.include_router(pages, prefix=app_path)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# TODO: add mount point for clang language server


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    log.warn(f"HTTPException: {exc.status_code} - {exc.detail}")

    error_model = HTTPError(
        error_code=exc.status_code,
        detail=exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_model.model_dump(),
    )
