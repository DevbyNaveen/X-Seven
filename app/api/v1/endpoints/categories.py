"""Business category endpoints for category-specific operations."""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, BusinessCategory
from app.models.service_provider import ServiceProvider
from app.models.appointment import Appointment
from app.schemas.business_category import (
    BusinessCategoryConfig,
    ServiceProviderCreate,
    ServiceProviderResponse,
    AppointmentCreate,
    AppointmentResponse,
    CategoryTemplateResponse,
    BusinessCategoryStats
)
from app.services.ai.business_category_service import BusinessCategoryService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/categories", response_model=List[CategoryTemplateResponse])
async def get_business_categories() -> Any:
    """Get all available business categories with their templates."""
    categories = []
    
    for category in BusinessCategory:
        # Create a mock business to get template
        template = Business().get_category_template()
        
        categories.append(CategoryTemplateResponse(
            category=category,
            template=template,
            default_services=template.get("default_services", []),
            pricing_tier=template.get("pricing_tier", "basic"),
            features=list(template.keys())
        ))
    
    return categories


@router.post("/{business_id}/category", response_model=CategoryTemplateResponse)
async def set_business_category(
    business_id: int,
    category_config: BusinessCategoryConfig,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Set the business category and apply template configuration."""
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to configure this business"
        )
    
    # Update business category
    current_business.category = category_config.category
    current_business.category_config = category_config.config
    
    # Apply template configuration
    template = current_business.get_category_template()
    current_business.category_config.update(template)
    
    db.commit()
    db.refresh(current_business)
    
    return CategoryTemplateResponse(
        category=current_business.category,
        template=current_business.category_config,
        default_services=template.get("default_services", []),
        pricing_tier=template.get("pricing_tier", "basic"),
        features=list(template.keys())
    )


@router.get("/{business_id}/category", response_model=CategoryTemplateResponse)
async def get_business_category(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Get the current business category configuration."""
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this business"
        )
    
    if not current_business.category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business category not set"
        )
    
    template = current_business.get_category_template()
    
    return CategoryTemplateResponse(
        category=current_business.category,
        template=current_business.category_config or {},
        default_services=template.get("default_services", []),
        pricing_tier=template.get("pricing_tier", "basic"),
        features=list(template.keys())
    )


@router.post("/{business_id}/providers", response_model=ServiceProviderResponse)
async def create_service_provider(
    business_id: int,
    provider_data: ServiceProviderCreate,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Create a new service provider for the business."""
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this business"
        )
    
    # Check if business supports service providers
    if not current_business.category or current_business.category == BusinessCategory.FOOD_HOSPITALITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This business category does not support service providers"
        )
    
    provider = ServiceProvider(
        business_id=business_id,
        name=provider_data.name,
        provider_type=provider_data.provider_type,
        email=provider_data.email,
        phone=provider_data.phone,
        specializations=provider_data.specializations,
        service_durations=provider_data.service_durations,
        service_pricing=provider_data.service_pricing,
        working_hours=provider_data.working_hours,
        bio=provider_data.bio,
        experience_years=provider_data.experience_years
    )
    
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    return ServiceProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        email=provider.email,
        phone=provider.phone,
        specializations=provider.specializations,
        service_durations=provider.service_durations,
        service_pricing=provider.service_pricing,
        working_hours=provider.working_hours,
        bio=provider.bio,
        experience_years=provider.experience_years,
        is_active=provider.is_active,
        image_url=provider.image_url,
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


@router.get("/{business_id}/providers", response_model=List[ServiceProviderResponse])
async def get_service_providers(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Get all service providers for the business."""
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this business"
        )
    
    providers = db.query(ServiceProvider).filter(
        ServiceProvider.business_id == business_id,
        ServiceProvider.is_active == True
    ).all()
    
    return [
        ServiceProviderResponse(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            email=provider.email,
            phone=provider.phone,
            specializations=provider.specializations,
            service_durations=provider.service_durations,
            service_pricing=provider.service_pricing,
            working_hours=provider.working_hours,
            bio=provider.bio,
            experience_years=provider.experience_years,
            is_active=provider.is_active,
            image_url=provider.image_url,
            created_at=provider.created_at,
            updated_at=provider.updated_at
        )
        for provider in providers
    ]


@router.post("/{business_id}/appointments", response_model=AppointmentResponse)
async def create_appointment(
    business_id: int,
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Create a new appointment for the business."""
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this business"
        )
    
    # Check if business supports appointments
    if not current_business.category or current_business.category == BusinessCategory.FOOD_HOSPITALITY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This business category does not support appointments"
        )
    
    from datetime import datetime, timedelta
    
    # Parse datetime strings
    start_time = datetime.fromisoformat(appointment_data.start_time.replace('Z', '+00:00'))
    end_time = start_time + timedelta(minutes=appointment_data.duration_minutes)
    
    appointment = Appointment(
        business_id=business_id,
        customer_name=appointment_data.customer_name,
        customer_phone=appointment_data.customer_phone,
        customer_email=appointment_data.customer_email,
        provider_id=appointment_data.provider_id,
        service_name=appointment_data.service_name,
        service_category=appointment_data.service_category,
        scheduled_date=datetime.fromisoformat(appointment_data.scheduled_date),
        start_time=start_time,
        end_time=end_time,
        duration_minutes=appointment_data.duration_minutes,
        total_amount=appointment_data.total_amount,
        deposit_amount=appointment_data.deposit_amount,
        notes=appointment_data.notes,
        special_requirements=appointment_data.special_requirements
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    return AppointmentResponse(
        id=appointment.id,
        business_id=appointment.business_id,
        customer_name=appointment.customer_name,
        customer_phone=appointment.customer_phone,
        customer_email=appointment.customer_email,
        provider_id=appointment.provider_id,
        service_name=appointment.service_name,
        service_category=appointment.service_category,
        scheduled_date=appointment.scheduled_date.isoformat(),
        start_time=appointment.start_time.isoformat(),
        duration_minutes=appointment.duration_minutes,
        total_amount=appointment.total_amount,
        deposit_amount=appointment.deposit_amount,
        notes=appointment.notes,
        special_requirements=appointment.special_requirements,
        customer_id=appointment.customer_id,
        appointment_type=appointment.appointment_type,
        end_time=appointment.end_time.isoformat(),
        status=appointment.status,
        payment_status=appointment.payment_status,
        deposit_paid=appointment.deposit_paid,
        reminder_sent=appointment.reminder_sent,
        cancelled_at=appointment.cancelled_at.isoformat() if appointment.cancelled_at else None,
        cancelled_by=appointment.cancelled_by,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at
    )


@router.get("/{business_id}/appointments", response_model=List[AppointmentResponse])
async def get_appointments(
    business_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business)
) -> Any:
    """Get appointments for the business."""
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this business"
        )
    
    query = db.query(Appointment).filter(Appointment.business_id == business_id)
    
    if status:
        query = query.filter(Appointment.status == status)
    
    appointments = query.order_by(Appointment.start_time).all()
    
    return [
        AppointmentResponse(
            id=appointment.id,
            business_id=appointment.business_id,
            customer_name=appointment.customer_name,
            customer_phone=appointment.customer_phone,
            customer_email=appointment.customer_email,
            provider_id=appointment.provider_id,
            service_name=appointment.service_name,
            service_category=appointment.service_category,
            scheduled_date=appointment.scheduled_date.isoformat(),
            start_time=appointment.start_time.isoformat(),
            duration_minutes=appointment.duration_minutes,
            total_amount=appointment.total_amount,
            deposit_amount=appointment.deposit_amount,
            notes=appointment.notes,
            special_requirements=appointment.special_requirements,
            customer_id=appointment.customer_id,
            appointment_type=appointment.appointment_type,
            end_time=appointment.end_time.isoformat(),
            status=appointment.status,
            payment_status=appointment.payment_status,
            deposit_paid=appointment.deposit_paid,
            reminder_sent=appointment.reminder_sent,
            cancelled_at=appointment.cancelled_at.isoformat() if appointment.cancelled_at else None,
            cancelled_by=appointment.cancelled_by,
            cancellation_reason=appointment.cancellation_reason,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at
        )
        for appointment in appointments
    ]


@router.get("/categories/{category}/stats", response_model=BusinessCategoryStats)
async def get_category_stats(
    category: BusinessCategory,
    db: Session = Depends(get_db)
) -> Any:
    """Get statistics for a specific business category."""
    # This would typically query actual data from the database
    # For now, returning mock data
    return BusinessCategoryStats(
        total_businesses=150,
        active_businesses=142,
        total_orders=1250,
        total_appointments=890,
        total_revenue=45678.90,
        average_rating=4.5
    )
