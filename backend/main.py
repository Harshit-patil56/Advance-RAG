"""FastAPI application entrypoint.

Registers all routers, configures CORS from environment variables (PRD 14.4),
registers the global AppError exception handler (PRD 13.1),
and runs Qdrant collection setup on startup (PRD 6.3).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from core.exceptions import AppError
from core.qdrant import ensure_collections_exist
from routers import folders, health, history, ingest, query, settings as settings_router, sessions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Starting up: ensuring Qdrant collections exist …")
    await ensure_collections_exist()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Adaptive Domain-Aware RAG Intelligence System",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — origins are read from environment; wildcard not permitted (PRD 14.4)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler — returns PRD Section 13.1 error envelope
# ---------------------------------------------------------------------------


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(sessions.router)
app.include_router(folders.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(history.router)
app.include_router(health.router)
app.include_router(settings_router.router)
