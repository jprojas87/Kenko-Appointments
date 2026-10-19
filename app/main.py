from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

from app.database import create_tables
from app.errors import register_error_handlers
from app.logging_config import add_correlation_id_middleware, configure_logging
from app.routes.appointments import router as appointments_router
from app.routes.catalog import router as catalog_router
from app.routes.health import router as health_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    create_tables()
    yield


configure_logging()
app = FastAPI(title="Kenko Appointments", lifespan=lifespan)
add_correlation_id_middleware(app)
register_error_handlers(app)

api_router = APIRouter()
api_router.include_router(appointments_router)
api_router.include_router(catalog_router)
app.include_router(api_router, prefix="/api/v1")
app.include_router(health_router)


def custom_openapi() -> dict[str, object]:
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        security_schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        security_schemes.setdefault("HTTPBearer", {"type": "http", "scheme": "bearer"})
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
