"""Subscription plans and pricing endpoints."""
from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, SubscriptionPlan, MenuItem
from app.schemas.plans import PlanResponse, SubscriptionRequest, PlanFeature
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[PlanResponse])
async def get_available_plans(
    db: Session = Depends(get_db)
) -> Any:
    """
    Get available subscription plans with features and pricing.
    """
    plans = [
        {
            "id": "basic",
            "name": "Basic",
            "description": "Perfect for small cafes getting started",
            "price": 29,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": [
                PlanFeature(
                    name="Universal Phone Number",
                    description="Shared AI phone number (+1-800-X-SEVENAI)",
                    included=True
                ),
                PlanFeature(
                    name="Basic AI Assistant",
                    description="AI-powered ordering and customer service",
                    included=True
                ),
                PlanFeature(
                    name="Menu Management",
                    description="Up to 50 menu items",
                    included=True
                ),
                PlanFeature(
                    name="Order Management",
                    description="Up to 100 orders per month",
                    included=True
                ),
                PlanFeature(
                    name="WhatsApp Integration",
                    description="Universal WhatsApp number",
                    included=True
                ),
                PlanFeature(
                    name="Custom Phone Number",
                    description="Dedicated business phone number",
                    included=False
                ),
                PlanFeature(
                    name="Advanced Analytics",
                    description="Detailed business insights",
                    included=False
                ),
                PlanFeature(
                    name="Priority Support",
                    description="24/7 priority customer support",
                    included=False
                )
            ],
            "limits": {
                "menu_items": 50,
                "monthly_orders": 100,
                "voice_minutes": 500,
                "sms_messages": 1000,
                "whatsapp_messages": 2000
            }
        },
        {
            "id": "pro",
            "name": "Pro",
            "description": "For growing businesses with custom needs",
            "price": 79,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": [
                PlanFeature(
                    name="Universal Phone Number",
                    description="Shared AI phone number (+1-800-X-SEVENAI)",
                    included=True
                ),
                PlanFeature(
                    name="Custom Phone Number",
                    description="Dedicated business phone number",
                    included=True
                ),
                PlanFeature(
                    name="Advanced AI Assistant",
                    description="Enhanced AI with custom personality",
                    included=True
                ),
                PlanFeature(
                    name="Unlimited Menu Items",
                    description="No limit on menu items",
                    included=True
                ),
                PlanFeature(
                    name="Unlimited Orders",
                    description="No limit on monthly orders",
                    included=True
                ),
                PlanFeature(
                    name="WhatsApp Business",
                    description="Dedicated WhatsApp Business number",
                    included=True
                ),
                PlanFeature(
                    name="Advanced Analytics",
                    description="Detailed business insights and reports",
                    included=True
                ),
                PlanFeature(
                    name="Priority Support",
                    description="24/7 priority customer support",
                    included=False
                )
            ],
            "limits": {
                "menu_items": -1,  # Unlimited
                "monthly_orders": -1,  # Unlimited
                "voice_minutes": 2000,
                "sms_messages": 5000,
                "whatsapp_messages": 10000
            }
        },
        {
            "id": "enterprise",
            "name": "Enterprise",
            "description": "Complete solution for large operations",
            "price": 199,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": [
                PlanFeature(
                    name="Everything in Pro",
                    description="All Pro features included",
                    included=True
                ),
                PlanFeature(
                    name="Multiple Phone Numbers",
                    description="Up to 5 dedicated phone numbers",
                    included=True
                ),
                PlanFeature(
                    name="Custom AI Training",
                    description="AI trained on your specific menu and style",
                    included=True
                ),
                PlanFeature(
                    name="Priority Support",
                    description="24/7 priority customer support",
                    included=True
                ),
                PlanFeature(
                    name="Custom Integrations",
                    description="Integration with your existing systems",
                    included=True
                ),
                PlanFeature(
                    name="White-label Options",
                    description="Custom branding and domain",
                    included=True
                ),
                PlanFeature(
                    name="Dedicated Account Manager",
                    description="Personal account manager",
                    included=True
                )
            ],
            "limits": {
                "menu_items": -1,  # Unlimited
                "monthly_orders": -1,  # Unlimited
                "voice_minutes": 10000,
                "sms_messages": 25000,
                "whatsapp_messages": 50000
            }
        }
    ]
    
    return [PlanResponse(**plan) for plan in plans]


@router.get("/current", response_model=PlanResponse)
async def get_current_plan(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get current subscription plan for the business.
    """
    # Get plan details based on current subscription
    all_plans = await get_available_plans(db)
    
    for plan in all_plans:
        if plan.id == business.subscription_plan:
            return plan
    
    # Fallback to basic if plan not found
    return all_plans[0]


@router.post("/subscribe", response_model=Dict[str, Any])
async def subscribe_to_plan(
    request: SubscriptionRequest,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Subscribe to a new plan with payment processing.
    """
    from app.services.external.stripe_service import StripeService
    
    # Validate plan exists
    available_plans = await get_available_plans(db)
    selected_plan = None
    
    for plan in available_plans:
        if plan.id == request.plan_id:
            selected_plan = plan
            break
    
    if not selected_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{request.plan_id}' not found"
        )
    
    # Process payment with Stripe
    stripe_service = StripeService(db)
    
    try:
        # Create Stripe customer if not exists
        if not business.stripe_customer_id:
            customer = await stripe_service.create_customer(
                email=business.contact_info.get("email"),
                name=business.name,
                metadata={"business_id": str(business.id)}
            )
            business.stripe_customer_id = customer.id
            db.commit()
        
        # Create subscription
        subscription = await stripe_service.create_subscription(
            customer_id=business.stripe_customer_id,
            plan_id=request.plan_id,
            payment_method_id=request.payment_method_id
        )
        
        # Update business subscription
        business.subscription_plan = request.plan_id
        business.stripe_subscription_id = subscription.id
        business.subscription_status = "active"
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully subscribed to {selected_plan.name} plan",
            "plan": selected_plan,
            "subscription_id": subscription.id
        }
        
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment processing failed: {str(e)}"
        )


@router.post("/cancel")
async def cancel_subscription(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Cancel current subscription.
    """
    from app.services.external.stripe_service import StripeService
    
    if not business.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to cancel"
        )
    
    stripe_service = StripeService(db)
    
    try:
        # Cancel Stripe subscription
        await stripe_service.cancel_subscription(business.stripe_subscription_id)
        
        # Update business status
        business.subscription_status = "cancelled"
        business.subscription_plan = "basic"  # Downgrade to basic
        db.commit()
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully"
        }
        
    except Exception as e:
        logger.error(f"Subscription cancellation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cancellation failed: {str(e)}"
        )


@router.get("/usage")
async def get_usage_limits(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get current usage and limits for the business.
    """
    # Get current plan limits
    current_plan = await get_current_plan(db, business)
    
    # Get actual usage from business data
    menu_items_count = db.query(MenuItem).filter(
        MenuItem.business_id == business.id
    ).count()
    
    # This would be calculated from orders table in a real implementation
    monthly_orders_count = 0  # Placeholder
    
    usage = {
        "menu_items": {
            "used": menu_items_count,
            "limit": current_plan.limits["menu_items"],
            "remaining": current_plan.limits["menu_items"] - menu_items_count if current_plan.limits["menu_items"] > 0 else -1
        },
        "monthly_orders": {
            "used": monthly_orders_count,
            "limit": current_plan.limits["monthly_orders"],
            "remaining": current_plan.limits["monthly_orders"] - monthly_orders_count if current_plan.limits["monthly_orders"] > 0 else -1
        },
        "voice_minutes": {
            "used": business.phone_usage.get("voice_minutes_used", 0),
            "limit": current_plan.limits["voice_minutes"],
            "remaining": current_plan.limits["voice_minutes"] - business.phone_usage.get("voice_minutes_used", 0)
        },
        "sms_messages": {
            "used": business.phone_usage.get("sms_sent", 0),
            "limit": current_plan.limits["sms_messages"],
            "remaining": current_plan.limits["sms_messages"] - business.phone_usage.get("sms_sent", 0)
        },
        "whatsapp_messages": {
            "used": business.phone_usage.get("whatsapp_messages", 0),
            "limit": current_plan.limits["whatsapp_messages"],
            "remaining": current_plan.limits["whatsapp_messages"] - business.phone_usage.get("whatsapp_messages", 0)
        }
    }
    
    return {
        "plan": current_plan,
        "usage": usage
    }
