"""Main API router - Clean and Simple Version."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    business,
    global_endpoints,
    dedicated_endpoints,
    dashboard_endpoints,
    supabase_auth,
    analytics_endpoints  # Add analytics endpoints
)
from app.api.v1.endpoints.dashboard import business_dashboard as dashboard
from app.api.v1.endpoints.food import menu as food_menu, order as food_order, table as food_table, inventory as food_inventory, qr as food_qr
from app.api.v1.endpoints.food.websocket.dashboard_websocket import router as dashboard_ws_router
from app.api.v1.endpoints.food.websocket.kitchen_websocket import router as kitchen_ws_router
# from app.api.v1.endpoints.AREndpoints.analytics import router as analytics_router
# from app.api.v1.endpoints.AREndpoints.reports import router as reports_router
# from app.api.v1.endpoints.AREndpoints.business_intelligence import router as business_intelligence_router

# Create main router
api_router = APIRouter()

# Include only Supabase authentication endpoints
api_router.include_router(
    supabase_auth.router,
    prefix="/auth/supabase",
    tags=["Authentication"]
)

api_router.include_router(
    auth.router,  # This has your Google login endpoint
    prefix="/auth",
    tags=["Authentication"]
)
api_router.include_router(
    business.router,
    prefix="/business",
    tags=["Business Management"]
)

api_router.include_router(
    global_endpoints.router,
    prefix="/global",
    tags=["Global AI"]
)

api_router.include_router(
    dedicated_endpoints.router,
    prefix="/dedicated",
    tags=["Dedicated AI"]
)

api_router.include_router(
    dashboard_endpoints.router,
    prefix="/dashboard",
    tags=["Dashboard AI"]
)

# Include our new analytics endpoints
api_router.include_router(
    analytics_endpoints.router,
    prefix="/analytics",
    tags=["Analytics"]
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

# Note: dashboard_endpoints.router already handles dashboard routes

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

# # Include Analytics and Reporting endpoints
# api_router.include_router(
#     analytics_router,
#     prefix="/are",
#     tags=["Analytics and Reporting"]
# )

# api_router.include_router(
#     reports_router,
#     prefix="/are",
#     tags=["Analytics and Reporting"]
# )

# api_router.include_router(
#     business_intelligence_router,
#     prefix="/are",
#     tags=["Analytics and Reporting"]
# )
