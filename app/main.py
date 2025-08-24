"""Main FastAPI application with WebSocket support."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config.settings import settings
from app.config.database import engine, Base
from app.config.logging import get_logger
from app.api.v1.api import api_router
from app.core.middleware import (
    CorrelationIdMiddleware,
    ErrorHandlingMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    BusinessContextMiddleware
)
from app.ngrok_config import get_cors_config, init_websocket_endpoints

# Get logger
logger = get_logger(__name__)

# Note: Database schema is managed via Alembic migrations.
# Avoid creating tables at runtime to prevent drift and race conditions in production.

# Create FastAPI app
is_prod = settings.ENVIRONMENT.lower() == "production"
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=None if is_prod else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
)

# Add middleware in order (last added = first executed)
app.add_middleware(CORSMiddleware, **get_cors_config())
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BusinessContextMiddleware)

# Initialize WebSocket endpoints
init_websocket_endpoints(app)

# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Root endpoint with OPTIONS handler
@app.api_route("/", methods=["GET", "OPTIONS"])
async def root(request: Request):
    """Root endpoint with CORS support."""
    if request.method == "OPTIONS":
        return JSONResponse(status_code=200, content={"method": "OPTIONS"})
    
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs" if not is_prod else None,
        "environment": settings.ENVIRONMENT
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION
    }


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("WebSocket support enabled")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down application")