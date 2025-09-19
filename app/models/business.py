"""Business model for Supabase operations."""
import enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.models.base import SupabaseModel


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


class Business(SupabaseModel):
    """
    Business model with phone configuration and category support.
    """
    table_name = "businesses"
    
    # Basic Information
    name: str
    slug: str
    description: Optional[str] = None
    
    # Business owner email (for authentication)
    email: str
    
    # Business Category
    category: Optional[str] = None
    
    # Category-specific configuration
    category_config: Dict[str, Any] = {}
    
    # Subscription
    subscription_plan: str = "basic"
    subscription_status: str = "active"
    is_active: bool = True
    trial_ends_at: Optional[datetime] = None
    
    # Stripe Integration
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    
    # Phone Number Configuration
    phone_config: str = "universal_only"
    
    # Custom phone numbers
    custom_phone_number: Optional[str] = None
    custom_whatsapp_number: Optional[str] = None
    custom_phone_sid: Optional[str] = None
    
    # Phone features
    phone_features: Dict[str, Any] = {}
    
    # Phone usage tracking
    phone_usage: Dict[str, Any] = {}
    
    # Custom number pricing
    custom_number_monthly_cost: float = 0.0
    
    # Configuration fields
    settings: Dict[str, Any] = {}
    branding_config: Dict[str, Any] = {}
    contact_info: Dict[str, Any] = {}
    
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