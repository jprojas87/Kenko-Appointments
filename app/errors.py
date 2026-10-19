from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_correlation_id
from app.schemas import ErrorDetail, ErrorResponse


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"


class BusinessRuleError(DomainError):
    status_code = 422
    code = "business_rule_violation"


class UnauthenticatedError(DomainError):
    status_code = 401
    code = "unauthorized"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            correlation_id=get_correlation_id() or "",
        )
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(by_alias=True))


async def domain_error_handler(_request: Request, exception: DomainError) -> JSONResponse:
    return _error_response(exception.status_code, exception.code, exception.message)


async def http_error_handler(_request: Request, exception: StarletteHTTPException) -> JSONResponse:
    codes = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        503: "service_unavailable",
    }
    message = exception.detail if isinstance(exception.detail, str) else "Solicitud no válida"
    return _error_response(
        exception.status_code,
        codes.get(exception.status_code, "http_error"),
        message,
    )


async def validation_error_handler(
    _request: Request, _exception: RequestValidationError
) -> JSONResponse:
    return _error_response(422, "validation_error", "Datos de solicitud inválidos")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
