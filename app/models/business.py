"""Updated Business model with phone number configuration."""
from sqlalchemy import Column, String, JSON, Boolean, Enum as SQLEnum, DateTime, Float
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class SubscriptionPlan(str, enum.Enum):
    """Subscription tiers for SaaS model."""
    BASIC = "basic"  # $29/month - Universal number only
    PRO = "pro"  # $79/month - Universal + Custom number
    ENTERPRISE = "enterprise"  # $199/month - Everything


class PhoneNumberType(str, enum.Enum):
    """Phone number configuration types."""
    UNIVERSAL_ONLY = "universal_only"  # Free - only on universal bot
    CUSTOM_ONLY = "custom_only"  # Paid - only custom number
    BOTH = "both"  # Paid - universal + custom


class BusinessCategory(str, enum.Enum):
    """Top 5 business categories for automation."""
    FOOD_HOSPITALITY = "food_hospitality"  # Restaurants, cafes, bars, bakeries
    BEAUTY_PERSONAL_CARE = "beauty_personal_care"  # Salons, spas, barbers
    AUTOMOTIVE_SERVICES = "automotive_services"  # Repair shops, car washes
    HEALTH_MEDICAL = "health_medical"  # Clinics, dental, veterinary
    LOCAL_SERVICES = "local_services"  # Cleaning, pet care, tutoring


class Business(BaseModel):
    """
    Updated Business model with phone configuration and category support.
    """
    __tablename__ = "businesses"
    
    # Basic Information (existing fields)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(String(500))
    
    # NEW: Business Category
    category = Column(
        SQLEnum(BusinessCategory),
        nullable=True,
        index=True
    )
    
    # Category-specific configuration
    category_config = Column(JSON, default=dict)
    # Example configurations for each category:
    # FOOD_HOSPITALITY: {
    #   "has_tables": true,
    #   "has_kitchen": true,
    #   "delivery_available": true,
    #   "qr_ordering": true,
    #   "reservation_system": true
    # }
    # BEAUTY_PERSONAL_CARE: {
    #   "has_stylists": true,
    #   "appointment_duration": 60,
    #   "deposit_required": true,
    #   "service_categories": ["hair", "nails", "massage"]
    # }
    # AUTOMOTIVE_SERVICES: {
    #   "has_service_bays": true,
    #   "parts_management": true,
    #   "vehicle_types": ["car", "motorcycle"],
    #   "emergency_service": true
    # }
    # HEALTH_MEDICAL: {
    #   "has_doctors": true,
    #   "insurance_accepted": true,
    #   "emergency_available": true,
    #   "specialties": ["general", "dental", "veterinary"]
    # }
    # LOCAL_SERVICES: {
    #   "mobile_service": true,
    #   "service_area": "10km",
    #   "recurring_available": true,
    #   "equipment_required": true
    # }
    
    # Subscription
    subscription_plan = Column(
        SQLEnum(SubscriptionPlan),
        default=SubscriptionPlan.BASIC,
        nullable=False
    )
    subscription_status = Column(String(50), default="active")  # active, cancelled, past_due, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    trial_ends_at = Column(DateTime(timezone=True))
    
    # Stripe Integration
    stripe_customer_id = Column(String(100), index=True)
    stripe_subscription_id = Column(String(100), index=True)
    
    # NEW: Phone Number Configuration
    phone_config = Column(
        SQLEnum(PhoneNumberType),
        default=PhoneNumberType.UNIVERSAL_ONLY,
        nullable=False
    )
    
    # NEW: Custom phone numbers (if applicable)
    custom_phone_number = Column(String(20))  # Their dedicated number
    custom_whatsapp_number = Column(String(20))  # WhatsApp Business number
    custom_phone_sid = Column(String(50))  # Twilio SID for the number
    
    # NEW: Phone features
    phone_features = Column(JSON, default=dict)
    # Example: {
    #   "voice_enabled": true,
    #   "whatsapp_enabled": false,
    #   "sms_enabled": true,
    #   "transfer_to_human": true,
    #   "business_hours_only": false,
    #   "voice_personality": "friendly",
    #   "monthly_minutes_limit": 1000
    # }
    
    # NEW: Phone usage tracking
    phone_usage = Column(JSON, default=dict)
    # Example: {
    #   "voice_minutes_used": 450,
    #   "sms_sent": 1200,
    #   "whatsapp_messages": 3400,
    #   "last_reset_date": "2024-01-01"
    # }
    
    # NEW: Custom number pricing
    custom_number_monthly_cost = Column(Float, default=0.0)
    
    # Existing fields...
    settings = Column(JSON, default=dict)
    branding_config = Column(JSON, default=dict)
    contact_info = Column(JSON, default=dict)
    
    # Relationships
    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    menu_categories = relationship("MenuCategory", back_populates="business", cascade="all, delete-orphan")
    menu_items = relationship("MenuItem", back_populates="business", cascade="all, delete-orphan")
    tables = relationship("Table", back_populates="business", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="business", cascade="all, delete-orphan")
    phone_numbers = relationship("PhoneNumber", back_populates="business", cascade="all, delete-orphan")
    waitlist_entries = relationship("WaitlistEntry", back_populates="business", cascade="all, delete-orphan")
    service_providers = relationship("ServiceProvider", back_populates="business", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="business", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Business {self.name} ({self.category}) - {self.subscription_plan}>"
    
    def get_category_template(self) -> dict:
        """Get the default configuration template for the business category."""
        templates = {
            BusinessCategory.FOOD_HOSPITALITY: {
                "has_tables": True,
                "has_kitchen": True,
                "delivery_available": True,
                "qr_ordering": True,
                "reservation_system": True,
                "menu_categories": ["Beverages", "Appetizers", "Main Dishes", "Desserts", "Specials"],
                "default_services": ["Dine-in", "Takeout", "Delivery"],
                "pricing_tier": "basic"
            },
            BusinessCategory.BEAUTY_PERSONAL_CARE: {
                "has_stylists": True,
                "appointment_duration": 60,
                "deposit_required": True,
                "service_categories": ["Hair", "Nails", "Massage", "Facial", "Makeup"],
                "default_services": ["Haircut", "Hair Color", "Manicure", "Pedicure", "Massage"],
                "pricing_tier": "pro"
            },
            BusinessCategory.AUTOMOTIVE_SERVICES: {
                "has_service_bays": True,
                "parts_management": True,
                "vehicle_types": ["Car", "Motorcycle", "Truck"],
                "emergency_service": True,
                "service_categories": ["Maintenance", "Repair", "Inspection", "Emergency"],
                "default_services": ["Oil Change", "Brake Service", "Tire Rotation", "Inspection"],
                "pricing_tier": "pro"
            },
            BusinessCategory.HEALTH_MEDICAL: {
                "has_doctors": True,
                "insurance_accepted": True,
                "emergency_available": True,
                "specialties": ["General", "Dental", "Veterinary", "Specialist"],
                "service_categories": ["Checkup", "Treatment", "Emergency", "Follow-up"],
                "default_services": ["General Checkup", "Cleaning", "Consultation", "Emergency Visit"],
                "pricing_tier": "enterprise"
            },
            BusinessCategory.LOCAL_SERVICES: {
                "mobile_service": True,
                "service_area": "10km",
                "recurring_available": True,
                "equipment_required": True,
                "service_categories": ["Cleaning", "Maintenance", "Care", "Repair"],
                "default_services": ["House Cleaning", "Pet Grooming", "Lawn Care", "Tutoring"],
                "pricing_tier": "basic"
            }
        }
        return templates.get(self.category, {})
    
    def can_use_feature(self, feature_name: str) -> bool:
        """Check if business can use a specific feature based on their plan."""
        plan_features = {
            "basic": {
                "custom_phone_number": False,
                "advanced_analytics": False,
                "priority_support": False,
                "unlimited_menu_items": False,
                "unlimited_orders": False,
                "whatsapp_business": False,
                "multi_language": False,
                "advanced_scheduling": False
            },
            "pro": {
                "custom_phone_number": True,
                "advanced_analytics": True,
                "priority_support": False,
                "unlimited_menu_items": True,
                "unlimited_orders": True,
                "whatsapp_business": True,
                "multi_language": True,
                "advanced_scheduling": True
            },
            "enterprise": {
                "custom_phone_number": True,
                "advanced_analytics": True,
                "priority_support": True,
                "unlimited_menu_items": True,
                "unlimited_orders": True,
                "whatsapp_business": True,
                "multi_language": True,
                "advanced_scheduling": True
            }
        }
        
        return plan_features.get(self.subscription_plan, {}).get(feature_name, False)
    
    def get_usage_limit(self, limit_type: str) -> int:
        """Get usage limit for a specific type based on plan."""
        plan_limits = {
            "basic": {
                "menu_items": 50,
                "monthly_orders": 100,
                "voice_minutes": 500,
                "sms_messages": 1000,
                "whatsapp_messages": 2000,
                "appointments": 50,
                "service_providers": 3
            },
            "pro": {
                "menu_items": -1,  # Unlimited
                "monthly_orders": -1,  # Unlimited
                "voice_minutes": 2000,
                "sms_messages": 5000,
                "whatsapp_messages": 10000,
                "appointments": 200,
                "service_providers": 10
            },
            "enterprise": {
                "menu_items": -1,  # Unlimited
                "monthly_orders": -1,  # Unlimited
                "voice_minutes": 10000,
                "sms_messages": 25000,
                "whatsapp_messages": 50000,
                "appointments": -1,  # Unlimited
                "service_providers": -1  # Unlimited
            }
        }
        
        return plan_limits.get(self.subscription_plan, {}).get(limit_type, 0)
    
    def is_within_limit(self, limit_type: str, current_usage: int) -> bool:
        """Check if current usage is within plan limits."""
        limit = self.get_usage_limit(limit_type)
        return limit == -1 or current_usage < limit  # -1 means unlimited