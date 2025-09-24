"""Stripe payment and subscription service."""
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import stripe
from datetime import datetime
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Handle Stripe payment processing and subscriptions."""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Plan price IDs (these should be created in Stripe dashboard)
        self.plan_prices = {
            "basic": "price_basic_monthly",  # Replace with actual Stripe price ID
            "pro": "price_pro_monthly",      # Replace with actual Stripe price ID
            "enterprise": "price_enterprise_monthly"  # Replace with actual Stripe price ID
        }
    
    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> stripe.Customer:
        """Create a new Stripe customer."""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            logger.info(f"Created Stripe customer: {customer.id}")
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        payment_method_id: str
    ) -> stripe.Subscription:
        """Create a subscription for a customer."""
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": self.plan_prices[plan_id]}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent"]
            )
            
            logger.info(f"Created subscription: {subscription.id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            raise
    
    async def cancel_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Cancel a subscription."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"Cancelled subscription: {subscription_id}")
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_plan_id: str
    ) -> stripe.Subscription:
        """Update subscription to a different plan."""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update the subscription item
            stripe.SubscriptionItem.modify(
                subscription.items.data[0].id,
                price=self.plan_prices[new_plan_id]
            )
            
            logger.info(f"Updated subscription {subscription_id} to plan {new_plan_id}")
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription: {e}")
            raise
    
    async def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> stripe.PaymentIntent:
        """Create a payment intent for one-time payments."""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {}
            )
            logger.info(f"Created payment intent: {payment_intent.id}")
            return payment_intent
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create payment intent: {e}")
            raise
    
    async def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Retrieve a subscription."""
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription: {e}")
            raise
    
    async def get_customer(self, customer_id: str) -> stripe.Customer:
        """Retrieve a customer."""
        try:
            return stripe.Customer.retrieve(customer_id)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve customer: {e}")
            raise
    
    async def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,
        reason: str = "requested_by_customer"
    ) -> stripe.Refund:
        """Create a refund for a payment."""
        try:
            refund_data = {
                "payment_intent": payment_intent_id,
                "reason": reason
            }
            if amount:
                refund_data["amount"] = amount
                
            refund = stripe.Refund.create(**refund_data)
            logger.info(f"Created refund: {refund.id}")
            return refund
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create refund: {e}")
            raise
    
    async def handle_webhook(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            
            # Handle different event types
            if event.type == "customer.subscription.created":
                await self._handle_subscription_created(event.data.object)
            elif event.type == "customer.subscription.updated":
                await self._handle_subscription_updated(event.data.object)
            elif event.type == "customer.subscription.deleted":
                await self._handle_subscription_deleted(event.data.object)
            elif event.type == "invoice.payment_succeeded":
                await self._handle_payment_succeeded(event.data.object)
            elif event.type == "invoice.payment_failed":
                await self._handle_payment_failed(event.data.object)
            
            return {"status": "success", "event": event.type}
            
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise
    
    async def _handle_subscription_created(self, subscription: stripe.Subscription):
        """Handle subscription created event."""
        logger.info(f"Subscription created: {subscription.id}")
        # Update business subscription status in database
        # This would be implemented based on your business logic
    
    async def _handle_subscription_updated(self, subscription: stripe.Subscription):
        """Handle subscription updated event."""
        logger.info(f"Subscription updated: {subscription.id}")
        # Update business subscription in database
    
    async def _handle_subscription_deleted(self, subscription: stripe.Subscription):
        """Handle subscription deleted event."""
        logger.info(f"Subscription deleted: {subscription.id}")
        # Update business subscription status in database
    
    async def _handle_payment_succeeded(self, invoice: stripe.Invoice):
        """Handle successful payment event."""
        logger.info(f"Payment succeeded for invoice: {invoice.id}")
        # Update business payment status in database
    
    async def _handle_payment_failed(self, invoice: stripe.Invoice):
        """Handle failed payment event."""
        logger.info(f"Payment failed for invoice: {invoice.id}")
        # Update business payment status and handle failed payment

    async def add_payment_method(
        self,
        customer_id: str,
        payment_method_id: str,
        set_as_default: bool = True
    ) -> stripe.PaymentMethod:
        """Add a payment method to a customer."""
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            if set_as_default:
                # Set as default payment method
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={
                        "default_payment_method": payment_method_id
                    }
                )
            
            return stripe.PaymentMethod.retrieve(payment_method_id)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to add payment method: {e}")
            raise

    async def get_customer_payment_methods(self, customer_id: str) -> List[stripe.PaymentMethod]:
        """Get all payment methods for a customer."""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            return payment_methods.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods: {e}")
            raise

    async def remove_payment_method(self, payment_method_id: str) -> bool:
        """Remove a payment method."""
        try:
            stripe.PaymentMethod.detach(payment_method_id)
            return True
        except stripe.error.StripeError as e:
            logger.error(f"Failed to remove payment method: {e}")
            raise

    async def get_upcoming_invoice(self, customer_id: str) -> stripe.Invoice:
        """Get upcoming invoice for a customer."""
        try:
            return stripe.Invoice.upcoming(customer=customer_id)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get upcoming invoice: {e}")
            raise

    async def get_customer_invoices(
        self,
        customer_id: str,
        limit: int = 50
    ) -> List[stripe.Invoice]:
        """Get invoice history for a customer."""
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit
            )
            return invoices.data
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get customer invoices: {e}")
            raise

    async def cancel_subscription_immediately(self, subscription_id: str) -> stripe.Subscription:
        """Cancel subscription immediately."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            subscription.cancel()
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription immediately: {e}")
            raise

    async def reactivate_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Reactivate a cancelled subscription."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to reactivate subscription: {e}")
            raise

    async def create_customer_portal_session(self, customer_id: str, return_url: str) -> str:
        """Create a customer portal session URL."""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return session.url
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer portal session: {e}")
            raise

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str
    ) -> stripe.checkout.Session:
        """Create a checkout session for subscription."""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url
            )
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise

    async def get_subscription_usage(self, subscription_id: str) -> Dict[str, Any]:
        """Get usage records for a subscription."""
        try:
            usage_records = stripe.SubscriptionItem.list_usage_record_summaries(
                subscription_id
            )
            return {
                "usage_records": usage_records.data,
                "total_count": len(usage_records.data)
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get subscription usage: {e}")
            raise
