"""Main API router - Clean and Simple Version."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    business,
    central_chat_endpoints as central_chat,
    global_chat_endpoints as global_chat,
    supabase_auth
)
from app.api.v1.endpoints.dashboard import business_dashboard as dashboard
from app.api.v1.endpoints.food import menu as food_menu, order as food_order, table as food_table, inventory as food_inventory, qr as food_qr
from app.api.v1.endpoints.food.websocket.dashboard_websocket import router as dashboard_ws_router
from app.api.v1.endpoints.food.websocket.kitchen_websocket import router as kitchen_ws_router
from app.api.v1.endpoints.AREndpoints.analytics import router as analytics_router
from app.api.v1.endpoints.AREndpoints.reports import router as reports_router
from app.api.v1.endpoints.AREndpoints.business_intelligence import router as business_intelligence_router

# Create main router
api_router = APIRouter()

# Include only Supabase authentication endpoints
api_router.include_router(
    supabase_auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    business.router,
    prefix="/business",
    tags=["Business Management"]
)

api_router.include_router(
    central_chat.router,
    prefix="/chat",
    tags=["Central Chat"]
)

api_router.include_router(
    global_chat.router,
    prefix="/global",
    tags=["Global Chat"]
)

api_router.include_router(
    food_menu.router,
    prefix="/food/menu",
    tags=["Food Menu Management"]
)

api_router.include_router(
    food_order.router,
    prefix="/food/orders",
    tags=["Food Order Management"]
)

api_router.include_router(
    food_table.router,
    prefix="/food/tables",
    tags=["Food Table Management"]
)

api_router.include_router(
    food_inventory.router,
    prefix="/food/inventory",
    tags=["Food Inventory Management"]
)

api_router.include_router(
    food_qr.router,
    prefix="/food/qr-codes",
    tags=["Food QR Code Management"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Business Dashboard"]
)

# WebSocket endpoints for real-time updates
api_router.include_router(
    dashboard_ws_router,
    prefix="/food",
    tags=["Food Dashboard WebSocket"]
)

api_router.include_router(
    kitchen_ws_router,
    prefix="/food/kitchen/ws",
    tags=["Food Service - Kitchen WebSocket"]
)

# Include Analytics and Reporting endpoints
api_router.include_router(
    analytics_router,
    prefix="/are",
    tags=["Analytics and Reporting"]
)

api_router.include_router(
    reports_router,
    prefix="/are",
    tags=["Analytics and Reporting"]
)

api_router.include_router(
    business_intelligence_router,
    prefix="/are",
    tags=["Analytics and Reporting"]
)
