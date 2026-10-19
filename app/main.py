from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.database import create_tables
from app.errors import register_error_handlers
from app.logging_config import add_correlation_id_middleware, configure_logging
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
app.include_router(api_router, prefix="/api/v1")
app.include_router(health_router)
