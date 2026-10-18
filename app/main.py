import logging
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.config import Settings, get_settings
from app.db.session import make_engine, make_session_factory
from app.errors import AppError, error_payload, redact, validation_details
from app.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title="Trade Store",
        version="1.0.0",
        summary="Store the current version of financial trades.",
    )
    application.state.settings = settings
    application.state.engine = make_engine(settings.database_url)
    application.state.session_factory = make_session_factory(application.state.engine)
    application.include_router(health_router)
    _register_handlers(application)
    return application


def _register_handlers(application: FastAPI) -> None:
    @application.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "validation_error",
                "Request validation failed.",
                validation_details(list(exc.errors())),
            ),
        )

    @application.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed"}
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(codes.get(exc.status_code, "http_error"), message),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.error(redact(traceback.format_exc()))
        return JSONResponse(
            status_code=500,
            content=error_payload("internal_error", "An unexpected error occurred."),
        )


app = create_app()
