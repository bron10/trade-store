import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe", response_model=None)
def ready(request: Request) -> JSONResponse | dict[str, str]:
    if database_ready(request.app.state.engine):
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "unavailable"})


def database_ready(engine: object) -> bool:
    connect = getattr(engine, "connect", None)
    if connect is None:
        logger.warning("readiness check failed: %s", "missing_engine")
        return False
    try:
        with connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("readiness check failed: %s", type(exc).__name__)
        return False
