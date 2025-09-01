"""Billing and subscription management endpoints."""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import logging

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, Order, Message
from app.models.business import SubscriptionPlan
from app.services.external.stripe_service import StripeService
from app.schemas.billing import (
    BillingOverview,
    InvoiceResponse,
    PaymentMethodResponse,
    UsageMetrics,
    BillingHistory,
    SubscriptionDetails,
    PaymentIntentResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview", response_model=BillingOverview)
async def get_billing_overview(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get comprehensive billing overview for the business.
    """
    stripe_service = StripeService(db)
    
    # Get current subscription details
    subscription_details = None
    if business.stripe_subscription_id:
        try:
            subscription = await stripe_service.get_subscription(business.stripe_subscription_id)
            subscription_details = SubscriptionDetails(
                id=subscription.id,
                status=subscription.status,
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                cancel_at_period_end=subscription.cancel_at_period_end,
                plan_id=business.subscription_plan
            )
        except Exception as e:
            logger.error(f"Error fetching subscription: {e}")
    
    # Calculate usage metrics
    usage_metrics = await get_usage_metrics(business.id, db)
    
    # Get upcoming invoice
    upcoming_invoice = None
    if business.stripe_customer_id:
        try:
            invoice = await stripe_service.get_upcoming_invoice(business.stripe_customer_id)
            upcoming_invoice = InvoiceResponse(
                id=invoice.id,
                amount_due=invoice.amount_due / 100,  # Convert from cents
                currency=invoice.currency,
                due_date=datetime.fromtimestamp(invoice.due_date) if invoice.due_date else None,
                status=invoice.status
            )
        except Exception as e:
            logger.error(f"Error fetching upcoming invoice: {e}")
    
    return BillingOverview(
        business_id=business.id,
        subscription_plan=business.subscription_plan,
        subscription_status=business.subscription_status,
        subscription_details=subscription_details,
        usage_metrics=usage_metrics,
        upcoming_invoice=upcoming_invoice,
        trial_ends_at=business.trial_ends_at,
        is_trial_active=business.trial_ends_at and business.trial_ends_at > datetime.utcnow()
    )


@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_billing_history(
    limit: int = Query(50, ge=1, le=100),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get billing history and past invoices.
    """
    if not business.stripe_customer_id:
        return []
    
    stripe_service = StripeService(db)
    
    try:
        invoices = await stripe_service.get_customer_invoices(
            business.stripe_customer_id,
            limit=limit
        )
        
        return [
            InvoiceResponse(
                id=invoice.id,
                amount_due=invoice.amount_due / 100,
                currency=invoice.currency,
                due_date=datetime.fromtimestamp(invoice.due_date) if invoice.due_date else None,
                status=invoice.status,
                invoice_pdf=invoice.invoice_pdf,
                hosted_invoice_url=invoice.hosted_invoice_url
            )
            for invoice in invoices
        ]
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching billing history"
        )


@router.get("/usage", response_model=UsageMetrics)
async def get_usage_metrics(
    time_range: str = Query("current_month", regex="^(current_month|last_month|last_3_months|last_year)$"),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get detailed usage metrics for the business.
    """
    # Calculate date range
    now = datetime.utcnow()
    if time_range == "current_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif time_range == "last_month":
        start_date = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        end_date = now.replace(day=1) - timedelta(seconds=1)
    elif time_range == "last_3_months":
        start_date = now - timedelta(days=90)
    else:  # last_year
        start_date = now - timedelta(days=365)
    
    if time_range == "last_month":
        orders = db.query(Order).filter(
            Order.business_id == business.id,
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).all()
    else:
        orders = db.query(Order).filter(
            Order.business_id == business.id,
            Order.created_at >= start_date
        ).all()
    
    # Calculate metrics
    total_orders = len(orders)
    total_revenue = sum(order.total_amount for order in orders)
    
    # Get business for phone usage
    phone_usage = business.phone_usage if business else {}
    
    return UsageMetrics(
        time_range=time_range,
        orders_count=total_orders,
        revenue=total_revenue,
        voice_minutes_used=phone_usage.get("voice_minutes_used", 0),
        sms_messages_sent=phone_usage.get("sms_sent", 0),
        whatsapp_messages=phone_usage.get("whatsapp_messages", 0),
        active_conversations=len(set(order.session_id for order in orders if order.session_id))
    )


@router.post("/payment-methods", response_model=PaymentMethodResponse)
async def add_payment_method(
    payment_method_id: str,
    set_as_default: bool = True,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Add a new payment method to the business.
    """
    if not business.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer associated with this business"
        )
    
    stripe_service = StripeService(db)
    
    try:
        payment_method = await stripe_service.add_payment_method(
            customer_id=business.stripe_customer_id,
            payment_method_id=payment_method_id,
            set_as_default=set_as_default
        )
        
        return PaymentMethodResponse(
            id=payment_method.id,
            type=payment_method.type,
            last4=payment_method.card.last4 if payment_method.card else None,
            brand=payment_method.card.brand if payment_method.card else None,
            exp_month=payment_method.card.exp_month if payment_method.card else None,
            exp_year=payment_method.card.exp_year if payment_method.card else None,
            is_default=set_as_default
        )
    except Exception as e:
        logger.error(f"Error adding payment method: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error adding payment method: {str(e)}"
        )


@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
async def get_payment_methods(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get all payment methods for the business.
    """
    if not business.stripe_customer_id:
        return []
    
    stripe_service = StripeService(db)
    
    try:
        payment_methods = await stripe_service.get_customer_payment_methods(
            business.stripe_customer_id
        )
        
        return [
            PaymentMethodResponse(
                id=pm.id,
                type=pm.type,
                last4=pm.card.last4 if pm.card else None,
                brand=pm.card.brand if pm.card else None,
                exp_month=pm.card.exp_month if pm.card else None,
                exp_year=pm.card.exp_year if pm.card else None,
                is_default=pm.id == business.default_payment_method_id if hasattr(business, 'default_payment_method_id') else False
            )
            for pm in payment_methods
        ]
    except Exception as e:
        logger.error(f"Error fetching payment methods: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching payment methods"
        )


@router.delete("/payment-methods/{payment_method_id}")
async def remove_payment_method(
    payment_method_id: str,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Remove a payment method.
    """
    stripe_service = StripeService(db)
    
    try:
        await stripe_service.remove_payment_method(payment_method_id)
        return {"message": "Payment method removed successfully"}
    except Exception as e:
        logger.error(f"Error removing payment method: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error removing payment method: {str(e)}"
        )


@router.post("/upgrade-plan")
async def upgrade_subscription_plan(
    new_plan: SubscriptionPlan,
    payment_method_id: Optional[str] = None,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upgrade or change subscription plan.
    """
    stripe_service = StripeService(db)
    
    try:
        if business.stripe_subscription_id:
            # Update existing subscription
            subscription = await stripe_service.update_subscription(
                business.stripe_subscription_id,
                new_plan.value
            )
        else:
            # Create new subscription
            if not business.stripe_customer_id:
                # Create customer first
                customer = await stripe_service.create_customer(
                    email=business.contact_info.get("email", "admin@business.com"),
                    name=business.name,
                    metadata={"business_id": str(business.id)}
                )
                business.stripe_customer_id = customer.id
            
            subscription = await stripe_service.create_subscription(
                customer_id=business.stripe_customer_id,
                plan_id=new_plan.value,
                payment_method_id=payment_method_id
            )
            business.stripe_subscription_id = subscription.id
        
        # Update business record
        business.subscription_plan = new_plan
        business.subscription_status = subscription.status
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully upgraded to {new_plan.value} plan",
            "subscription_id": subscription.id
        }
        
    except Exception as e:
        logger.error(f"Error upgrading plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error upgrading plan: {str(e)}"
        )


@router.post("/cancel-subscription")
async def cancel_subscription(
    cancel_at_period_end: bool = True,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Cancel subscription.
    """
    if not business.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to cancel"
        )
    
    stripe_service = StripeService(db)
    
    try:
        if cancel_at_period_end:
            subscription = await stripe_service.cancel_subscription(business.stripe_subscription_id)
            business.subscription_status = "cancelling"
        else:
            subscription = await stripe_service.cancel_subscription_immediately(business.stripe_subscription_id)
            business.subscription_status = "cancelled"
            business.subscription_plan = SubscriptionPlan.BASIC
        
        db.commit()
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully",
            "cancelled_at_period_end": cancel_at_period_end
        }
        
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error cancelling subscription: {str(e)}"
        )


@router.post("/reactivate-subscription")
async def reactivate_subscription(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Reactivate a cancelled subscription.
    """
    if not business.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription to reactivate"
        )
    
    stripe_service = StripeService(db)
    
    try:
        subscription = await stripe_service.reactivate_subscription(business.stripe_subscription_id)
        business.subscription_status = subscription.status
        db.commit()
        
        return {
            "success": True,
            "message": "Subscription reactivated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error reactivating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reactivating subscription: {str(e)}"
        )


@router.post("/create-payment-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    amount: float,
    currency: str = "usd",
    payment_method_id: Optional[str] = None,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a payment intent for one-time payments.
    """
    stripe_service = StripeService(db)
    
    try:
        payment_intent = await stripe_service.create_payment_intent(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            customer_id=business.stripe_customer_id,
            metadata={"business_id": str(business.id)}
        )
        
        return PaymentIntentResponse(
            id=payment_intent.id,
            client_secret=payment_intent.client_secret,
            amount=amount,
            currency=currency,
            status=payment_intent.status
        )
        
    except Exception as e:
        logger.error(f"Error creating payment intent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating payment intent: {str(e)}"
        )


@router.get("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    """
    Handle Stripe webhook events.
    """
    stripe_service = StripeService(db)
    
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        result = await stripe_service.handle_webhook(payload, sig_header)
        return result
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook error"
        )


@router.get("/usage-alerts")
async def get_usage_alerts(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get usage alerts and warnings.
    """
    # Get current usage
    usage_metrics = await get_usage_metrics(business.id, db)
    
    # Get plan limits
    plan_limits = {
        SubscriptionPlan.BASIC: {
            "voice_minutes": 500,
            "sms_messages": 1000,
            "whatsapp_messages": 2000,
            "orders": 100
        },
        SubscriptionPlan.PRO: {
            "voice_minutes": 2000,
            "sms_messages": 5000,
            "whatsapp_messages": 10000,
            "orders": -1  # Unlimited
        },
        SubscriptionPlan.ENTERPRISE: {
            "voice_minutes": 10000,
            "sms_messages": 25000,
            "whatsapp_messages": 50000,
            "orders": -1  # Unlimited
        }
    }
    
    current_limits = plan_limits.get(business.subscription_plan, plan_limits[SubscriptionPlan.BASIC])
    
    alerts = []
    
    # Check usage against limits
    if current_limits["voice_minutes"] > 0:
        usage_percentage = (usage_metrics.voice_minutes_used / current_limits["voice_minutes"]) * 100
        if usage_percentage >= 90:
            alerts.append({
                "type": "warning",
                "message": f"Voice minutes usage at {usage_percentage:.1f}% of limit",
                "current": usage_metrics.voice_minutes_used,
                "limit": current_limits["voice_minutes"]
            })
        elif usage_percentage >= 100:
            alerts.append({
                "type": "critical",
                "message": "Voice minutes limit exceeded",
                "current": usage_metrics.voice_minutes_used,
                "limit": current_limits["voice_minutes"]
            })
    
    if current_limits["sms_messages"] > 0:
        usage_percentage = (usage_metrics.sms_messages_sent / current_limits["sms_messages"]) * 100
        if usage_percentage >= 90:
            alerts.append({
                "type": "warning",
                "message": f"SMS messages usage at {usage_percentage:.1f}% of limit",
                "current": usage_metrics.sms_messages_sent,
                "limit": current_limits["sms_messages"]
            })
    
    if current_limits["orders"] > 0:
        usage_percentage = (usage_metrics.orders_count / current_limits["orders"]) * 100
        if usage_percentage >= 90:
            alerts.append({
                "type": "warning",
                "message": f"Orders usage at {usage_percentage:.1f}% of limit",
                "current": usage_metrics.orders_count,
                "limit": current_limits["orders"]
            })
    
    return {
        "alerts": alerts,
        "usage_metrics": usage_metrics,
        "plan_limits": current_limits
    }
