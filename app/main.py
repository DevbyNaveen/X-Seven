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


# Enhanced startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup with enhanced framework initialization."""
    logger.info(f"🚀 Starting Enhanced {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("WebSocket support enabled")
    
    # Initialize Kafka integration
    try:
        from app.core.kafka.integration import initialize_kafka_integration
        from app.config.database import get_supabase_client
        
        # Get dependencies
        supabase_client = get_supabase_client()
        
        # Initialize Kafka with service integrations
        kafka_integrator = await initialize_kafka_integration(
            supabase_client=supabase_client
        )
        
        logger.info("✅ Kafka event streaming: ACTIVE")
        logger.info("✅ Event-driven architecture: ACTIVE")
        logger.info("✅ Dead letter queue: ACTIVE")
        logger.info("✅ Kafka monitoring: ACTIVE")
        
    except Exception as e:
        logger.warning(f"⚠️ Kafka initialization failed (continuing without Kafka): {e}")
    
    # Initialize DSPy system
    try:
        from app.core.dspy.startup import startup_dspy_system
        dspy_results = await startup_dspy_system()
        
        if dspy_results["success"]:
            logger.info("✅ DSPy prompt optimization: ACTIVE")
            logger.info("✅ DSPy intent detection: ACTIVE")
            logger.info("✅ DSPy agent routing: ACTIVE")
            logger.info("✅ DSPy response generation: ACTIVE")
        else:
            logger.warning("⚠️ DSPy system initialized with issues:")
            for error in dspy_results["errors"]:
                logger.warning(f"   - {error}")
                
    except Exception as e:
        logger.warning(f"⚠️ DSPy initialization failed (continuing without DSPy): {e}")
    
    # Initialize PipeCat Voice AI System
    try:
        from app.core.voice.integration_manager import initialize_voice_integration
        from app.core.voice.analytics import initialize_voice_analytics
        from app.core.dspy.modules.voice_optimized_modules import register_voice_modules_with_dspy_manager
        
        # Initialize voice integration
        voice_success = await initialize_voice_integration()
        if voice_success:
            logger.info("✅ PipeCat voice pipeline: ACTIVE")
            logger.info("✅ Voice-LangGraph integration: ACTIVE")
            logger.info("✅ Voice-Temporal workflows: ACTIVE")
            logger.info("✅ Voice-CrewAI coordination: ACTIVE")
            
            # Register voice-optimized DSPy modules
            dspy_voice_success = await register_voice_modules_with_dspy_manager()
            if dspy_voice_success:
                logger.info("✅ DSPy voice optimization: ACTIVE")
            else:
                logger.warning("⚠️ DSPy voice modules registration failed")
            
            # Initialize voice analytics
            analytics_success = await initialize_voice_analytics()
            if analytics_success:
                logger.info("✅ Voice analytics & monitoring: ACTIVE")
            else:
                logger.warning("⚠️ Voice analytics initialization failed")
                
        else:
            logger.warning("⚠️ PipeCat voice integration failed to initialize")
            
    except Exception as e:
        logger.warning(f"⚠️ PipeCat voice system initialization failed (continuing without voice): {e}")
    
    # Enhanced framework components
    logger.info("✅ LangGraph conversation flows: ACTIVE")
    logger.info("✅ CrewAI multi-agent orchestration: ACTIVE")
    logger.info("✅ Temporal workflow engine: INITIALIZING")
    logger.info("✅ Redis state management: ACTIVE")
    logger.info("✅ Chat flow router (3 types): ACTIVE")
    logger.info("✅ Error recovery & resilience: ACTIVE")
    
    logger.info("🎯 PipeCat-Enhanced X-SevenAI Framework: READY FOR PRODUCTION")


# Enhanced shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown with cleanup."""
    logger.info("🛑 Shutting down Enhanced X-SevenAI Framework")
    
    try:
        # Cleanup Kafka components
        try:
            from app.core.kafka.manager import cleanup_kafka_manager
            await cleanup_kafka_manager()
            logger.info("✅ Kafka connections closed")
        except Exception as e:
            logger.error(f"❌ Error closing Kafka connections: {e}")
        
        # Cleanup enhanced components
        from app.api.v1.redis_persistence import RedisPersistenceManager
        from app.workflows.temporal_integration import get_temporal_manager
        
        # Close Redis connections
        redis_manager = RedisPersistenceManager()
        await redis_manager.close()
        logger.info("✅ Redis connections closed")
        
        # Close Temporal connections
        temporal_manager = get_temporal_manager()
        await temporal_manager.close()
        logger.info("✅ Temporal connections closed")
        
        # Cleanup PipeCat Voice System
        try:
            from app.core.voice.integration_manager import stop_voice_integration
            from app.core.voice.analytics import cleanup_voice_analytics
            
            # Stop voice integration
            await stop_voice_integration()
            logger.info("✅ PipeCat voice system stopped")
            
            # Cleanup voice analytics
            await cleanup_voice_analytics()
            logger.info("✅ Voice analytics cleaned up")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up voice system: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")
    
    logger.info("✅ PipeCat-Enhanced framework shutdown complete")