"""Main FastAPI application with WebSocket support."""
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.config.settings import settings
from app.config.logging import get_logger
from app.api.v1.api import api_router
from app.core.middleware import (
    CorrelationIdMiddleware,
    ErrorHandlingMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
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
# Move CORSMiddleware to be added last so it executes first and properly handles
# CORS preflight (OPTIONS) requests before other middleware.
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, **get_cors_config())

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


# Root endpoint with OPTIONS and HEAD handler
@app.api_route("/", methods=["GET", "HEAD", "OPTIONS"])
async def root(request: Request):
    """Root endpoint with CORS and health check support."""
    if request.method == "OPTIONS":
        return JSONResponse(status_code=200, content={"method": "OPTIONS"})
    
    if request.method == "HEAD":
        return JSONResponse(status_code=200, content={})
    
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


# RAG Test endpoint
@app.get("/test-rag")
async def test_rag(db: Session = Depends(get_db)):
    """Test endpoint for RAG functionality."""
    from app.services.ai.centralAI.rag_search import RAGSearch
    rag_search = RAGSearch(db)
    test_results = rag_search.test_search_functionality()
    return {
        "status": "success",
        "results": test_results
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