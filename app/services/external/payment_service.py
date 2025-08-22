"""Payment processing service."""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import stripe
from decimal import Decimal
from app.models import Order, PaymentStatus, OrderStatus
from app.config.settings import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentService:
    """Handle payment processing."""

    def __init__(self, db: Session):
        self.db = db

    async def create_payment_intent(
        self,
        order_id: int,
        amount: Decimal,
        currency: str = "EUR"
    ) -> Dict[str, Any]:
        """Create Stripe payment intent."""
        try:
            # Convert to cents for Stripe
            amount_cents = int(amount * 100)

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata={'order_id': str(order_id)}
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": amount,
                "currency": currency
            }
        except stripe.error.StripeError as e:
            return {
                "error": str(e),
                "status": "failed"
            }

    async def confirm_payment(
        self,
        order_id: int,
        payment_intent_id: str
    ) -> bool:
        """Confirm payment completion."""
        try:
            # Retrieve payment intent from Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status == 'succeeded':
                # Update order
                order = self.db.query(Order).filter(
                    Order.id == order_id
                ).first()

                if order:
                    order.payment_status = PaymentStatus.PAID
                    order.status = OrderStatus.CONFIRMED
                    self.db.commit()
                return True

            return False
        except stripe.error.StripeError:
            return False

    async def process_refund(
        self,
        order_id: int,
        amount: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Process refund for an order."""
        order = self.db.query(Order).filter(
            Order.id == order_id
        ).first()

        if not order:
            return {"error": "Order not found"}

        if order.payment_status != PaymentStatus.PAID:
            return {"error": "Order not paid"}

        try:
            # In production, retrieve payment intent from order metadata
            refund = stripe.Refund.create(
                payment_intent=order.payment_intent_id,
                amount=int((amount or order.total_amount) * 100)
            )

            if refund.status == 'succeeded':
                order.payment_status = PaymentStatus.REFUNDED
                self.db.commit()

                return {
                    "status": "refunded",
                    "refund_id": refund.id,
                    "amount": amount or order.total_amount
                }
        except stripe.error.StripeError as e:
            return {"error": str(e)}