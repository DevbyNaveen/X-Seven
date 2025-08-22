"""
Schemas package for X-SevenAI backend.

This package contains all Pydantic models for request/response validation:
- auth: Authentication schemas
- base: Base schemas and common types
- billing: Billing and subscription schemas
- bookings: Booking system schemas
- business: Business management schemas
- customer: Customer management schemas
- language: Language and localization schemas
- menu: Menu management schemas
- message: Message and chat schemas
- notifications: Notification schemas
- order: Order management schemas
- phone: Phone number management schemas
- plans: Subscription plan schemas
- qr_codes: QR code generation schemas
- table: Table management schemas
- voice_calls: Voice call system schemas
- whatsapp: WhatsApp integration schemas
"""

# Base schemas
from app.schemas.base import BaseSchema, BaseResponse

# Authentication schemas
from app.schemas.auth import Token, RegisterBusinessRequest, LoginRequest

# Business schemas
from app.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
    BusinessResponse,
    BusinessSettings,
)

# Menu schemas
from app.schemas.menu import (
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuCategoryResponse,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemResponse,
)

# Table schemas
from app.schemas.table import (
    TableCreate,
    TableUpdate,
    TableResponse,
    TableStatus,
)

# Order schemas
from app.schemas.order import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderItemCreate,
    OrderItemResponse,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
)

# Message schemas
from app.schemas.message import (
    ChatRequest,
    ChatResponse,
    MessageCreate,
    MessageResponse,
)

# Customer schemas
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerPreferences,
)

# Phone schemas
from app.schemas.phone import (
    PhoneNumberCreate,
    PhoneNumberUpdate,
    PhoneNumberResponse,
    NumberStatus,
    NumberProvider,
)

# Billing schemas
from app.schemas.billing import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    PaymentIntentCreate,
    PaymentIntentResponse,
    InvoiceResponse,
)

# Plans schemas
from app.schemas.plans import (
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    PlanFeature,
)

# QR Codes schemas
from app.schemas.qr_codes import (
    QRCodeCreate,
    QRCodeResponse,
    QRCodeType,
)

# Bookings schemas
from app.schemas.bookings import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingStatus,
    BookingTimeSlot,
)

# Voice Calls schemas
from app.schemas.voice_calls import (
    VoiceCallCreate,
    VoiceCallResponse,
    VoiceCallStatus,
    VoiceCallDirection,
)

# Notifications schemas
from app.schemas.notifications import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    NotificationType,
    NotificationChannel,
)

# Language schemas
from app.schemas.language import (
    LanguageResponse,
    TranslationRequest,
    TranslationResponse,
)

# WhatsApp schemas
from app.schemas.whatsapp import (
    WhatsAppWebhook,
    WhatsAppMessage,
    WhatsAppResponse,
)

__all__ = [
    # Base
    "BaseSchema",
    "BaseResponse",
    
    # Auth
    "Token",
    "RegisterBusinessRequest",
    "LoginRequest",
    
    # Business
    "BusinessCreate",
    "BusinessUpdate", 
    "BusinessResponse",
    "BusinessSettings",
    
    # Menu
    "MenuCategoryCreate",
    "MenuCategoryUpdate",
    "MenuCategoryResponse",
    "MenuItemCreate",
    "MenuItemUpdate",
    "MenuItemResponse",
    
    # Table
    "TableCreate",
    "TableUpdate",
    "TableResponse",
    "TableStatus",
    
    # Order
    "OrderCreate",
    "OrderUpdate",
    "OrderResponse",
    "OrderItemCreate",
    "OrderItemResponse",
    "OrderStatus",
    "PaymentStatus",
    "PaymentMethod",
    
    # Message
    "ChatRequest",
    "ChatResponse",
    "MessageCreate",
    "MessageResponse",
    
    # Customer
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerPreferences",
    
    # Phone
    "PhoneNumberCreate",
    "PhoneNumberUpdate",
    "PhoneNumberResponse",
    "NumberStatus",
    "NumberProvider",
    
    # Billing
    "SubscriptionCreate",
    "SubscriptionUpdate",
    "SubscriptionResponse",
    "PaymentIntentCreate",
    "PaymentIntentResponse",
    "InvoiceResponse",
    
    # Plans
    "PlanCreate",
    "PlanUpdate",
    "PlanResponse",
    "PlanFeature",
    
    # QR Codes
    "QRCodeCreate",
    "QRCodeResponse",
    "QRCodeType",
    
    # Bookings
    "BookingCreate",
    "BookingUpdate",
    "BookingResponse",
    "BookingStatus",
    "BookingTimeSlot",
    
    # Voice Calls
    "VoiceCallCreate",
    "VoiceCallResponse",
    "VoiceCallStatus",
    "VoiceCallDirection",
    
    # Notifications
    "NotificationCreate",
    "NotificationUpdate",
    "NotificationResponse",
    "NotificationType",
    "NotificationChannel",
    
    # Language
    "LanguageResponse",
    "TranslationRequest",
    "TranslationResponse",
    
    # WhatsApp
    "WhatsAppWebhook",
    "WhatsAppMessage",
    "WhatsAppResponse",
]
