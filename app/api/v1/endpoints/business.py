"""Updated business endpoints with phone configuration."""
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from app.config.database import get_supabase_client
from app.config.settings import settings
from app.core.dependencies import get_current_business
from app.models import Business, PhoneNumberType, User
from app.schemas.business import BusinessPhoneConfig, PhoneProvisioningResponse
# Correctly import the single manager class
from app.services.phone.providers.multi_provider_manager import MultiProviderPhoneManager
from app.services.phone.providers.twilio_provider import TwilioProvider

router = APIRouter()


@router.post("/{business_id}/phone-setup", response_model=PhoneProvisioningResponse)
async def configure_phone_setup(
    business_id: int,
    config: BusinessPhoneConfig,
    current_business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Configure phone setup for a business.
    """
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to configure this business"
        )
    
    # Use the corrected PhoneManager
    phone_manager = MultiProviderPhoneManager(supabase)
    
    result = phone_manager.onboard_business(
        business_id=business_id,
        phone_config=config.phone_config,
        wants_whatsapp=config.enable_whatsapp
    )
    
    if result is None:
        raise HTTPException(status_code=404, detail="Business not found")

    return PhoneProvisioningResponse(
        business_id=result["business_id"],
        universal_access=result["universal_access"],
        custom_number=result.get("custom_number"),
        whatsapp_enabled=result["whatsapp_enabled"],
        monthly_cost=result["monthly_cost"],
        message="Phone configuration successful"
    )


# ===== New: Dedicated number onboarding (search, provision, direct setup) =====

class DirectNumberSetup(BaseModel):
    custom_number: str = Field(..., description="Existing business number to use; system will provision a Twilio number in same country and map forwarding")
    enable_whatsapp: bool = Field(False, description="Enable WhatsApp for this number (Twilio number will be used for WA)")


class ProvisionRequest(BaseModel):
    number: str = Field(..., description="Number to provision (E.164)")
    provider: str = Field("twilio", description="Provider name")
    enable_whatsapp: bool = Field(False, description="Enable WhatsApp on provisioned number (if supported)")


@router.get("/{business_id}/numbers/search")
async def search_available_numbers(
    business_id: int,
    country_code: str = Query("+1", description="E.164 country code e.g. +1, +372, +371"),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Search available virtual numbers from providers (Twilio first)."""
    if current_business.id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    provider = TwilioProvider()
    numbers = await provider.search_available_numbers(country_code=country_code)

    return {
        "provider": "twilio",
        "country_code": country_code,
        "results": [
            {
                "number": n.number,
                "capabilities": n.capabilities,
                "monthly_cost": n.monthly_cost,
                "setup_cost": n.setup_cost,
                "region": n.region,
            }
            for n in numbers
        ],
    }


@router.post("/{business_id}/numbers/provision")
async def provision_business_number(
    business_id: int,
    body: ProvisionRequest,
    current_business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client),
) -> Any:
    """Provision a dedicated virtual number for this business and configure webhooks."""
    if current_business.id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if not current_business.can_use_feature("custom_phone_number"):
        raise HTTPException(status_code=400, detail="Plan does not allow custom numbers")

    # For now support Twilio provider
    if body.provider != "twilio":
        raise HTTPException(status_code=400, detail="Only 'twilio' provider is supported currently")

    webhook_base = f"{settings.API_URL}{settings.API_V1_STR}/communications"

    provider = TwilioProvider()
    result = await provider.provision_number(phone_number=body.number, webhook_url=webhook_base)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"Provisioning failed: {result.get('error', 'unknown error')}")

    # Persist phone number
    phone_row = {
        "business_id": business_id,
        "phone_number": result.get("number", body.number),
        "provider": "twilio",
        "provider_id": result.get("sid"),
        "status": "active",
        "is_primary": True,
        "type": "custom",
        "webhook_url": webhook_base,
        "capabilities": ["voice", "sms"] + (["whatsapp"] if body.enable_whatsapp else []),
        "is_forwarding_target": True,
    }
    try:
        supabase.table("phone_numbers").insert(phone_row).execute()
    except Exception:
        # Best-effort: continue even if insert fails; business update still done
        pass

    # Update business record
    try:
        supabase.table("businesses").update({
            "custom_phone_number": result.get("number", body.number),
            "custom_phone_sid": result.get("sid"),
            "phone_config": PhoneNumberType.BOTH.value if current_business.phone_config != PhoneNumberType.CUSTOM_ONLY.value else current_business.phone_config,
        }).eq("id", business_id).execute()
    except Exception:
        pass

    return {
        "success": True,
        "number": result.get("number", body.number),
        "provider": "twilio",
        "sid": result.get("sid"),
        "webhooks": {
            "voice": f"{webhook_base}/voice/incoming",
            "sms": f"{webhook_base}/sms/incoming",
            "whatsapp": f"{webhook_base}/whatsapp/incoming",
        },
        "capabilities": phone_row.get("capabilities", []),
    }


@router.post("/{business_id}/numbers/direct")
async def setup_direct_custom_number(
    business_id: int,
    body: DirectNumberSetup,
    current_business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client),
) -> Any:
    """Hybrid routing for custom numbers:
    - Provision a Twilio number in the same country as the custom number
    - Configure webhooks on the Twilio number
    - Store mapping: custom_number.forwarding_number = twilio_number and mark Twilio number as forwarding target
    - Business/provider must configure forwarding: custom → Twilio
    """
    if current_business.id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if not current_business.can_use_feature("custom_phone_number"):
        raise HTTPException(status_code=400, detail="Plan does not allow custom numbers")

    custom_number = body.custom_number.strip()
    if not custom_number.startswith("+"):
        raise HTTPException(status_code=400, detail="Number must be in E.164 format (e.g., +15551234567)")

    # Helper: extract E.164 country code prefix (naive: first 2-4 chars after '+')
    def extract_country_code(num: str) -> str:
        # Simple heuristics for common codes
        for code in ["+371", "+372", "+370", "+44", "+1", "+91", "+61", "+81", "+49", "+33"]:
            if num.startswith(code):
                return code
        # Fallback to first 2 chars after '+' if unknown
        return num[:3]

    country_code = extract_country_code(custom_number)

    # 1) Provision Twilio number in same country
    provider = TwilioProvider()
    search = await provider.search_available_numbers(country_code=country_code)
    if not search:
        raise HTTPException(status_code=502, detail="No available provider numbers found for the given country")
    chosen = search[0]
    webhook_base = f"{settings.API_URL}{settings.API_V1_STR}/communications"
    provision = await provider.provision_number(phone_number=chosen.number, webhook_url=webhook_base)
    if not provision.get("success"):
        raise HTTPException(status_code=502, detail=f"Failed to provision provider number: {provision.get('error')}")

    twilio_number = provision.get("number", chosen.number)
    twilio_sid = provision.get("sid")

    # 2) Persist Twilio number (forwarding target)
    twilio_row = {
        "business_id": business_id,
        "phone_number": twilio_number,
        "provider": "twilio",
        "provider_id": twilio_sid,
        "status": "active",
        "is_primary": True,
        "type": "custom",
        "webhook_url": webhook_base,
        "capabilities": ["voice", "sms"] + (["whatsapp"] if body.enable_whatsapp else []),
        "is_forwarding_target": True,
    }
    try:
        supabase.table("phone_numbers").insert(twilio_row).execute()
    except Exception:
        pass

    # 3) Persist Custom number mapping to Twilio number
    custom_row = {
        "business_id": business_id,
        "phone_number": custom_number,
        "provider": "custom",
        "status": "active",
        "is_primary": False,
        "type": "custom",
        "forwarding_number": twilio_number,
        "capabilities": ["voice", "sms"] + (["whatsapp"] if body.enable_whatsapp else []),
    }
    try:
        supabase.table("phone_numbers").insert(custom_row).execute()
    except Exception:
        pass

    # 4) Update business model
    update_payload: Dict[str, Any] = {
        "custom_phone_number": custom_number,
        "custom_phone_sid": twilio_sid,
        "phone_config": PhoneNumberType.BOTH.value if current_business.phone_config != PhoneNumberType.CUSTOM_ONLY.value else current_business.phone_config,
    }
    if body.enable_whatsapp:
        update_payload["custom_whatsapp_number"] = custom_number
        update_payload["phone_features"] = {"whatsapp_enabled": True}
    try:
        supabase.table("businesses").update(update_payload).eq("id", business_id).execute()
    except Exception:
        pass

    return {
        "success": True,
        "custom_number": custom_number,
        "twilio_number": twilio_number,
        "sid": twilio_sid,
        "webhooks": {
            "voice": f"{webhook_base}/voice/incoming",
            "sms": f"{webhook_base}/sms/incoming",
            "whatsapp": f"{webhook_base}/whatsapp/incoming",
        },
        "note": "Please configure your provider to forward calls/messages from your custom number to the Twilio number above.",
        "whatsapp_enabled": body.enable_whatsapp,
    }


@router.get("/{business_id}/phone-status")
async def get_phone_status(
    business_id: int,
    current_business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """Get current phone configuration and usage for a business."""
    if current_business.id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    phone_manager = MultiProviderPhoneManager(supabase)
    usage = phone_manager.check_usage_limits(business_id)
    
    return {
        "phone_config": current_business.phone_config,
        "custom_number": current_business.custom_phone_number,
        "whatsapp_number": current_business.custom_whatsapp_number,
        "universal_access": current_business.phone_config in [
            PhoneNumberType.UNIVERSAL_ONLY,
            PhoneNumberType.BOTH
        ],
        "usage": usage,
        "monthly_cost": current_business.custom_number_monthly_cost
    }


@router.post("/{business_id}/transfer-to-human")
async def transfer_to_human(
    business_id: int,
    body: dict,
    current_business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """Initiate transfer to human staff (custom numbers only)."""
    call_sid = body.get("call_sid")
    if not call_sid:
        raise HTTPException(status_code=400, detail="call_sid is required in the request body")

    if current_business.id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    if current_business.phone_config == PhoneNumberType.UNIVERSAL_ONLY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Human transfer not available for universal-only configuration"
        )
    
    phone_manager = MultiProviderPhoneManager(db)
    success = phone_manager.transfer_to_human(business_id, call_sid)
    
    if success:
        return {"status": "success", "message": "Transfer initiated", "call_sid": call_sid}
    else:
        raise HTTPException(status_code=500, detail="Transfer failed")