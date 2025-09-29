"""Main FastAPI application with WebSocket support."""
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config.database import get_supabase_client
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
async def test_rag(supabase = Depends(get_supabase_client)):
    """Test endpoint for RAG functionality."""
    from app.services.ai.rag_search import RAGSearch
    rag_search = RAGSearch(supabase)
    test_results = rag_search.test_search_functionality()
    return {
        "status": "success",
        "results": test_results
    }


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include Temporal router
from app.api.v1.endpoints.temporal import router as temporal_router
app.include_router(temporal_router, prefix=settings.API_V1_STR, tags=["Temporal"])

# Include Enhanced LangGraph conversation API with full integration
from app.api.v1.langgraph_conversation_api import router as langgraph_router
app.include_router(langgraph_router, prefix=settings.API_V1_STR)

# Include DSPy Integration API
from app.api.v1.dspy_integration_api import router as dspy_router
app.include_router(dspy_router, prefix=settings.API_V1_STR)

# Include PipeCat Voice AI API
from app.api.v1.pipecat_voice_api import router as voice_router
app.include_router(voice_router, prefix=settings.API_V1_STR)

# Add Voice WebSocket endpoint
from fastapi import WebSocket
from app.core.voice.websocket_handler import handle_voice_websocket

@app.websocket("/ws/voice/{session_id}")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time voice communication."""
    await handle_voice_websocket(websocket, session_id)

@app.websocket("/ws/voice")
async def voice_websocket_endpoint_auto(websocket: WebSocket):
    """WebSocket endpoint for real-time voice communication with auto-generated session ID."""
    await handle_voice_websocket(websocket)

# Include Chat Flow Router for direct access
from app.api.v1.chat_flow_router import get_chat_flow_router
chat_router = get_chat_flow_router()


# Modern Service Mesh Integration
@app.on_event("startup")
async def startup_event():
    """Initialize service mesh with modern dependency management"""
    logger.info(f"🚀 Starting Service Mesh-Enhanced {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    try:
        from app.core.service_mesh.integrations import get_service_mesh
        service_mesh = await get_service_mesh()
        
        # Initialize service mesh
        results = await service_mesh.initialize()
        
        if results["success"]:
            logger.info("✅ Service Mesh initialized successfully")
            
            # Log individual service statuses
            for service_name, status in results.get("services", {}).items():
                if status.get("status") == "success":
                    logger.info(f"✅ {service_name}: ACTIVE")
                else:
                    logger.warning(f"⚠️ {service_name}: {status.get('error', 'Unknown error')}")
            
            logger.info("🎯 Modern Service Mesh: READY FOR PRODUCTION")
            
        else:
            logger.error("❌ Service Mesh initialization failed")
            # Don't raise exception to allow graceful degradation
            
    except Exception as e:
        logger.error(f"❌ Service Mesh startup error: {e}")
        # Continue with basic startup for backward compatibility
        await _legacy_startup()


async def _legacy_startup():
    """Legacy startup for backward compatibility"""
    logger.info("🔄 Falling back to legacy startup...")
    
    # Initialize Kafka integration
    from app.core.kafka.integration import initialize_kafka_integration
    from app.config.database import get_supabase_client
    
    try:
        supabase_client = get_supabase_client()
        await initialize_kafka_integration(supabase_client=supabase_client)
        logger.info("✅ Legacy services initialized")
    except Exception as e:
        logger.warning(f"⚠️ Legacy initialization warning: {e}")


# Modern Service Mesh Shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown with service mesh"""
    logger.info("🛑 Shutting down Service Mesh-Enhanced X-SevenAI Framework")
    
    try:
        from app.core.service_mesh.integrations import get_service_mesh
        service_mesh = await get_service_mesh()
        
        # Graceful shutdown through service mesh
        shutdown_results = await service_mesh.shutdown()
        
        if shutdown_results["success"]:
            logger.info(f"✅ Service Mesh shutdown completed in {shutdown_results.get('duration', 0):.2f}s")
        else:
            logger.error("❌ Service Mesh shutdown failed")
            
        # Legacy cleanup for backward compatibility
        await _legacy_cleanup()
        
    except Exception as e:
        logger.error(f"❌ Service Mesh shutdown error: {e}")
        await _legacy_cleanup()
    
    logger.info("✅ Framework shutdown complete")


async def _legacy_cleanup():
    """Legacy cleanup for backward compatibility"""
    try:
        # Cleanup Kafka
        try:
            from app.core.kafka.manager import cleanup_kafka_manager
            await cleanup_kafka_manager()
            logger.info("✅ Legacy Kafka cleanup completed")
        except Exception as e:
            logger.warning(f"⚠️ Legacy Kafka cleanup warning: {e}")
        
        # Cleanup Redis
        try:
            from app.api.v1.redis_persistence import RedisPersistenceManager
            redis_manager = RedisPersistenceManager()
            await redis_manager.close()
            logger.info("✅ Legacy Redis cleanup completed")
        except Exception as e:
            logger.warning(f"⚠️ Legacy Redis cleanup warning: {e}")
        
        # Cleanup Temporal
        try:
            from app.workflows.temporal_integration import get_temporal_manager
            temporal_manager = get_temporal_manager()
            await temporal_manager.close()
            logger.info("✅ Legacy Temporal cleanup completed")
        except Exception as e:
            logger.warning(f"⚠️ Legacy Temporal cleanup warning: {e}")
            
    except Exception as e:
        logger.error(f"❌ Legacy cleanup error: {e}")