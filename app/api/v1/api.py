"""Main API router that includes all endpoints."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    business,
    menu,
    tables,
    orders,
    chat,
    universal,    # NEW
    dedicated_chat,  # NEW - Dedicated cafe chat
    dashboard,    # NEW
    kitchen,      # NEW
    onboarding,
    voice,    # NEW
    analytics,    # NEW
    plans,    # NEW
    customers,    # NEW - Customer management
    billing,      # NEW - Subscription billing
    notifications, # NEW - Real-time notifications
    qr_codes,     # NEW - QR code generation
    voice_calls,  # NEW - Voice call system
    bookings,     # NEW - Booking system
    waitlist,     # NEW - Waitlist management
    inventory,    # NEW - Inventory management
    categories,   # NEW - Business categories
)

# Create main router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    business.router,
    prefix="/business",
    tags=["Business Management"]
)

api_router.include_router(
    menu.router,
    prefix="/menu",
    tags=["Menu Management"]
)

api_router.include_router(
    tables.router,
    prefix="/tables",
    tags=["Table Management"]
)

api_router.include_router(
    orders.router,
    prefix="/orders",
    tags=["Order Management"]
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat System"]
)

api_router.include_router(
    dedicated_chat.router,
    prefix="/dedicated-chat",
    tags=["Dedicated Cafe Chat"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Admin Dashboard"]
)

api_router.include_router(
    kitchen.router,
    prefix="/kitchen",
    tags=["Kitchen Management"]
)

api_router.include_router(
    onboarding.router,
    prefix="/onboarding",
    tags=["Onboarding"]
)

api_router.include_router(
    voice.router,
    prefix="/voice",
    tags=["Voice System"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics & Business Intelligence"]
)

api_router.include_router(
    plans.router,
    prefix="/plans",
    tags=["Subscription Plans"]
)

api_router.include_router(
    customers.router,
    prefix="/customers",
    tags=["Customer Management"]
)

api_router.include_router(
    billing.router,
    prefix="/billing",
    tags=["Billing & Subscriptions"]
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)

api_router.include_router(
    qr_codes.router,
    prefix="/qr-codes",
    tags=["QR Codes"]
)

api_router.include_router(
    voice_calls.router,
    prefix="/voice-calls",
    tags=["Voice Calls"]
)

api_router.include_router(
    bookings.router,
    prefix="/bookings",
    tags=["Bookings"]
)

api_router.include_router(
    waitlist.router,
    prefix="/waitlist",
    tags=["Waitlist Management"]
)

api_router.include_router(
    inventory.router,
    prefix="/inventory",
    tags=["Inventory Management"]
)

api_router.include_router(
    categories.router,
    prefix="/categories",
    tags=["Business Categories"]
)