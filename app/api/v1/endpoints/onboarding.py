"""Onboarding endpoints for phone setup."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import random
import string
from datetime import datetime, timedelta
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, MenuItem, SubscriptionPlan, PhoneNumberType
from app.schemas.phone import (
    PhoneConfigRequest,
    PhoneStatusResponse,
    WhatsAppSetupRequest,
    OTPVerificationRequest,
    UniversalAccessRequest,
    PhoneSetupOption
)
from app.services.external.phone_manager import PhoneManagerService

router = APIRouter()


@router.post("/phone-setup")
async def setup_phone_system(
    config: PhoneConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> PhoneStatusResponse:
    """
    Setup phone system based on selected option.
    
    Validates subscription plan restrictions:
    - Basic plan: Universal number only
    - Pro/Enterprise: Custom numbers allowed
    """
    # Validate subscription plan restrictions
    if config.setup_option in [PhoneSetupOption.CUSTOM_NUMBER, PhoneSetupOption.BOTH]:
        if business.subscription_plan == SubscriptionPlan.BASIC:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "plan_restriction",
                    "message": "Custom phone numbers require Pro or Enterprise plan",
                    "required_plan": "pro",
                    "current_plan": business.subscription_plan,
                    "upgrade_url": "/api/v1/plans"
                }
            )
    
    phone_manager = PhoneManagerService(db)

    # Handle different setup options
    if config.setup_option == PhoneSetupOption.UNIVERSAL_ONLY:
        # Just register for universal access
        result = await phone_manager.register_universal_access(business.id)

    elif config.setup_option == PhoneSetupOption.CUSTOM_NUMBER:
        # Auto-provision new number
        result = await phone_manager.provision_new_number(
            business_id=business.id,
            country_code=config.country_code,
            area_code=config.area_code,
            provider=config.provider
        )

    elif config.setup_option == PhoneSetupOption.OWN_NUMBER:
        # Use existing number - need OTP verification
        if not config.existing_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Existing number required for this option"
            )

        # Send OTP for verification
        otp = await phone_manager.send_otp(config.existing_number)

        # Store OTP temporarily (in production, use Redis)
        # For now, return status indicating OTP sent
        result = {
            "status": "otp_sent",
            "phone_number": config.existing_number,
            "message": "Please verify ownership with OTP"
        }

    else:  # BOTH option
        # Register universal AND provision custom
        universal_result = await phone_manager.register_universal_access(business.id)
        custom_result = await phone_manager.provision_new_number(
            business_id=business.id,
            country_code=config.country_code,
            area_code=config.area_code,
            provider=config.provider
        )

        result = {
            "universal": universal_result,
            "custom": custom_result
        }

    # Update business settings
    business.settings = business.settings or {}
    business.settings['phone_setup'] = {
        'option': config.setup_option,
        'provider': config.provider,
        'setup_date': datetime.utcnow().isoformat()
    }
    db.commit()

    # Schedule WhatsApp setup in background
    if config.setup_option != PhoneSetupOption.UNIVERSAL_ONLY:
        background_tasks.add_task(
            phone_manager.setup_whatsapp_business,
            business.id
        )

    return PhoneStatusResponse(
        business_id=business.id,
        setup_option=config.setup_option,
        universal_number="+1-800-X-SEVENAI" if config.setup_option in [PhoneSetupOption.UNIVERSAL_ONLY, PhoneSetupOption.BOTH] else None,
        dedicated_number=result.get('phone_number') if config.setup_option != PhoneSetupOption.UNIVERSAL_ONLY else None,
        provider=config.provider,
        is_verified=False,
        is_active=False,
        whatsapp_connected=False,
        created_at=datetime.utcnow()
    )


@router.post("/whatsapp-verify")
async def verify_whatsapp_setup(
    otp_request: OTPVerificationRequest,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Verify WhatsApp setup with OTP.
    
    Validates subscription plan restrictions:
    - Basic plan: Universal WhatsApp only
    - Pro/Enterprise: Dedicated WhatsApp Business allowed
    """
    # Check if business is trying to use dedicated WhatsApp on basic plan
    if business.phone_config in [PhoneNumberType.CUSTOM_ONLY, PhoneNumberType.BOTH]:
        if business.subscription_plan == SubscriptionPlan.BASIC:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "plan_restriction",
                    "message": "Dedicated WhatsApp Business requires Pro or Enterprise plan",
                    "required_plan": "pro",
                    "current_plan": business.subscription_plan
                }
            )
    
    phone_manager = PhoneManagerService(db)

    # Verify OTP
    is_valid = await phone_manager.verify_otp(
        otp_request.phone_number,
        otp_request.otp_code
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code"
        )

    # Complete WhatsApp setup
    result = await phone_manager.complete_whatsapp_setup(
        business.id,
        otp_request.phone_number
    )

    return {
        "status": "verified",
        "whatsapp_connected": True,
        "message": "WhatsApp Business API successfully connected"
    }


@router.get("/progress")
async def get_onboarding_progress(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get onboarding progress with plan-based feature recommendations.
    """
    steps_completed = []
    steps_pending = []
    plan_recommendations = []

    # Check business profile
    if business.name and business.slug:
        steps_completed.append("business_profile")
    else:
        steps_pending.append("business_profile")

    # Check phone setup
    phone_setup = business.settings.get('phone_setup') if business.settings else None
    if phone_setup:
        steps_completed.append("phone_setup")
    else:
        steps_pending.append("phone_setup")

    # Check menu
    menu_items = db.query(MenuItem).filter(
        MenuItem.business_id == business.id
    ).count()
    if menu_items > 0:
        steps_completed.append("menu_setup")
    else:
        steps_pending.append("menu_setup")

    # Check WhatsApp
    whatsapp_connected = phone_setup.get('whatsapp_connected', False) if phone_setup else False
    if whatsapp_connected:
        steps_completed.append("whatsapp_setup")
    else:
        steps_pending.append("whatsapp_setup")

    # Check subscription plan
    if business.subscription_status == "trial":
        steps_pending.append("plan_selection")
        plan_recommendations.append({
            "type": "trial_expiry",
            "message": "Your trial is active. Select a plan to continue using all features.",
            "action": "select_plan"
        })
    elif business.subscription_status == "active":
        steps_completed.append("plan_selection")
    else:
        steps_pending.append("plan_selection")
        plan_recommendations.append({
            "type": "subscription_required",
            "message": "Active subscription required to continue.",
            "action": "subscribe"
        })

    # Plan-specific recommendations
    if business.subscription_plan == SubscriptionPlan.BASIC:
        if menu_items >= 40:  # Approaching limit
            plan_recommendations.append({
                "type": "limit_warning",
                "message": f"You have {menu_items}/50 menu items. Consider upgrading to Pro for unlimited items.",
                "action": "upgrade_plan",
                "feature": "unlimited_menu_items"
            })
        
        if business.phone_config in [PhoneNumberType.CUSTOM_ONLY, PhoneNumberType.BOTH]:
            plan_recommendations.append({
                "type": "feature_restriction",
                "message": "Custom phone numbers require Pro or Enterprise plan.",
                "action": "upgrade_plan",
                "feature": "custom_phone_number"
            })

    progress_percentage = (len(steps_completed) / (len(steps_completed) + len(steps_pending))) * 100

    return {
        "progress_percentage": progress_percentage,
        "steps_completed": steps_completed,
        "steps_pending": steps_pending,
        "is_complete": len(steps_pending) == 0,
        "current_plan": business.subscription_plan,
        "subscription_status": business.subscription_status,
        "plan_recommendations": plan_recommendations,
        "usage": {
            "menu_items": {
                "current": menu_items,
                "limit": business.get_usage_limit("menu_items"),
                "unlimited": business.get_usage_limit("menu_items") == -1
            }
        }
    }


@router.post("/plan-selection")
async def select_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Select a subscription plan during onboarding.
    
    This endpoint is called when user chooses a plan during onboarding.
    Payment processing happens separately via /api/v1/plans/subscribe
    """
    # Validate plan exists
    valid_plans = ["basic", "pro", "enterprise"]
    if plan_id not in valid_plans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {plan_id}. Valid plans: {valid_plans}"
        )
    
    # Update business plan (payment will be processed separately)
    business.subscription_plan = plan_id
    business.subscription_status = "pending_payment"  # Will be updated after payment
    db.commit()
    
    return {
        "success": True,
        "message": f"Plan {plan_id} selected. Complete payment to activate.",
        "next_step": "payment",
        "payment_url": f"/api/v1/plans/subscribe"
    }