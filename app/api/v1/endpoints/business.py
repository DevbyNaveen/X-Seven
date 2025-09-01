"""Updated business endpoints with phone configuration."""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, PhoneNumberType, User
from app.schemas.business import BusinessPhoneConfig, PhoneProvisioningResponse
# Correctly import the single manager class
from app.services.phone.providers.multi_provider_manager import MultiProviderPhoneManager

router = APIRouter()


@router.post("/{business_id}/phone-setup", response_model=PhoneProvisioningResponse)
async def setup_phone_configuration(
    business_id: int,
    config: BusinessPhoneConfig,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
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
    phone_manager = MultiProviderPhoneManager(db)
    
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


@router.get("/{business_id}/phone-status")
async def get_phone_status(
    business_id: int,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """Get current phone configuration and usage for a business."""
    if current_business.id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    phone_manager = MultiProviderPhoneManager(db)
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
async def initiate_human_transfer(
    business_id: int,
    body: dict,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
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