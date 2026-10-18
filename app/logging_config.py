import logging
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_record_factory_installed = False


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def configure_logging(level: str = "INFO") -> None:
    global _record_factory_installed

    if not _record_factory_installed:
        original_factory = logging.getLogRecordFactory()

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = original_factory(*args, **kwargs)
            record.correlation_id = get_correlation_id() or "-"
            return record

        logging.setLogRecordFactory(record_factory)
        _record_factory_installed = True

    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [correlationId=%(correlation_id)s] %(name)s: %(message)s",
    )


async def correlation_id_middleware(request: Request, call_next: Any) -> Response:
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid4())
    token = _correlation_id.set(correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
    finally:
        _correlation_id.reset(token)


def add_correlation_id_middleware(app: FastAPI) -> None:
    app.middleware("http")(correlation_id_middleware)
