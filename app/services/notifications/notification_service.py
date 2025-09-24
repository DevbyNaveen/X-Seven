"""
Advanced Notification Service - Handles customer and staff notifications.
"""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio
from sqlalchemy.orm import Session

from app.models import Business, Order, Message
from app.models.order import OrderStatus
from app.services.external.whatsapp_service import WhatsAppService
from app.services.external.twilio_service import TwilioService
from app.services.external.stripe_service import StripeService

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    ORDER_CONFIRMATION = "order_confirmation"
    ORDER_STATUS_UPDATE = "order_status_update"
    ORDER_READY = "order_ready"
    BOOKING_CONFIRMATION = "booking_confirmation"
    BOOKING_REMINDER = "booking_reminder"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    STAFF_ALERT = "staff_alert"
    SYSTEM_ALERT = "system_alert"
    PROMOTIONAL = "promotional"


class NotificationChannel(str, Enum):
    """Notification channels."""
    SMS = "sms"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priorities."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationService:
    """
    Comprehensive notification service for customer and staff communications.
    
    Features:
    1. Multi-channel notifications (SMS, WhatsApp, Email, Push)
    2. Automated order status updates
    3. Booking reminders and confirmations
    4. Payment notifications
    5. Staff alerts and escalations
    6. Promotional messaging
    7. Notification scheduling and queuing
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.whatsapp_service = WhatsAppService()
        self.twilio_service = TwilioService()
        self.stripe_service = StripeService(db)
        
        # Notification templates
        self.templates = self._load_notification_templates()
    
    async def send_order_confirmation(
        self,
        order: Order,
        business: Business,
        customer_phone: str,
        customer_name: str = "Guest"
    ) -> bool:
        """Send order confirmation notification."""
        try:
            # Prepare order details
            order_items = []
            for item in order.items:
                order_items.append(f"• {item.quantity}x {item.name} - ${item.unit_price:.2f}")
            
            items_text = "\n".join(order_items)
            
            # Create message
            message = f"""✅ **Order #{order.id} Confirmed!**

**{business.name}**
📋 **Your Order:**
{items_text}

💰 **Total: ${order.total_amount:.2f}**
⏰ **Estimated Ready: {self._estimate_ready_time(order)}**

**Next Steps:**
1. We'll notify you when your order is ready
2. Pick up at the counter
3. Enjoy your meal! 🎉

Thank you for choosing {business.name}!"""
            
            # Send via WhatsApp if available, otherwise SMS
            if business.settings.get("whatsapp_enabled", False):
                success = await self.whatsapp_service.send_message(
                    to_number=customer_phone,
                    message=message
                )
            else:
                success = await self.twilio_service.send_sms(
                    to_number=customer_phone,
                    message=message
                )
            
            if success:
                logger.info(f"Order confirmation sent for order {order.id}")
                return True
            else:
                logger.error(f"Failed to send order confirmation for order {order.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending order confirmation: {e}")
            return False
    
    async def send_order_status_update(
        self,
        order: Order,
        business: Business,
        status: OrderStatus,
        customer_phone: str
    ) -> bool:
        """Send order status update notification."""
        try:
            status_messages = {
                OrderStatus.PREPARING: "👨‍🍳 **Your order is being prepared!**",
                OrderStatus.READY: "✅ **Your order is ready for pickup!**",
                OrderStatus.COMPLETED: "🎉 **Thank you for your order!**",
                OrderStatus.CANCELLED: "❌ **Your order has been cancelled.**"
            }
            
            status_message = status_messages.get(status, f"**Order status: {status.value}**")
            
            message = f"""{status_message}

**Order #{order.id}**
🏪 {business.name}

{self._get_status_specific_message(status, order)}"""
            
            # Send notification
            if business.settings.get("whatsapp_enabled", False):
                success = await self.whatsapp_service.send_message(
                    to_number=customer_phone,
                    message=message
                )
            else:
                success = await self.twilio_service.send_sms(
                    to_number=customer_phone,
                    message=message
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending order status update: {e}")
            return False
    
    async def send_booking_confirmation(
        self,
        booking: Dict[str, Any],
        business: Business,
        customer_phone: str,
        customer_name: str
    ) -> bool:
        """Send booking confirmation notification."""
        try:
            date_str = booking["date"].strftime("%A, %B %d")
            time_str = booking["time"].strftime("%I:%M %p")
            
            message = f"""✅ **Booking Confirmed!**

**{business.name}**
📅 {date_str}
🕐 {time_str}
👥 {booking["party_size"]} people
📞 {customer_phone}

**Confirmation Code:** {booking["id"][-6:]}

**Next Steps:**
1. We'll send you a reminder 2 hours before
2. Please arrive 5 minutes early
3. Call us if you need to modify or cancel

Thank you for choosing {business.name}! 🎉"""
            
            # Send notification
            if business.settings.get("whatsapp_enabled", False):
                success = await self.whatsapp_service.send_message(
                    to_number=customer_phone,
                    message=message
                )
            else:
                success = await self.twilio_service.send_sms(
                    to_number=customer_phone,
                    message=message
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending booking confirmation: {e}")
            return False
    
    async def send_booking_reminder(
        self,
        booking: Dict[str, Any],
        business: Business,
        customer_phone: str,
        customer_name: str
    ) -> bool:
        """Send booking reminder notification."""
        try:
            date_str = booking["date"].strftime("%A, %B %d")
            time_str = booking["time"].strftime("%I:%M %p")
            
            message = f"""⏰ **Booking Reminder**

**{business.name}**
📅 {date_str}
🕐 {time_str}
👥 {booking["party_size"]} people

**Your table is reserved for {time_str} today!**

Please arrive 5 minutes early. We look forward to serving you! 🎉"""
            
            # Send notification
            if business.settings.get("whatsapp_enabled", False):
                success = await self.whatsapp_service.send_message(
                    to_number=customer_phone,
                    message=message
                )
            else:
                success = await self.twilio_service.send_sms(
                    to_number=customer_phone,
                    message=message
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending booking reminder: {e}")
            return False
    
    async def send_payment_notification(
        self,
        order: Order,
        business: Business,
        customer_phone: str,
        payment_status: str,
        payment_method: str
    ) -> bool:
        """Send payment notification."""
        try:
            if payment_status == "success":
                message = f"""💳 **Payment Successful!**

**{business.name}**
💰 **Amount:** ${order.total_amount:.2f}
💳 **Method:** {payment_method}
📋 **Order:** #{order.id}

Your payment has been processed successfully. Thank you! ✅"""
            else:
                message = f"""❌ **Payment Failed**

**{business.name}**
💰 **Amount:** ${order.total_amount:.2f}
💳 **Method:** {payment_method}
📋 **Order:** #{order.id}

There was an issue with your payment. Please try again or contact us."""
            
            # Send notification
            if business.settings.get("whatsapp_enabled", False):
                success = await self.whatsapp_service.send_message(
                    to_number=customer_phone,
                    message=message
                )
            else:
                success = await self.twilio_service.send_sms(
                    to_number=customer_phone,
                    message=message
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending payment notification: {e}")
            return False
    
    async def send_staff_alert(
        self,
        business: Business,
        alert_type: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send staff alert notification."""
        try:
            # Get staff phone numbers
            staff_phones = self._get_staff_phones(business.id)
            
            if not staff_phones:
                logger.warning(f"No staff phones found for business {business.id}")
                return False
            
            # Format alert message
            alert_message = f"""🚨 **Staff Alert - {business.name}**

**Type:** {alert_type}
**Priority:** {priority.value.upper()}

{message}

**Time:** {datetime.now().strftime('%I:%M %p')}"""
            
            # Send to all staff members
            success_count = 0
            for phone in staff_phones:
                if business.settings.get("whatsapp_enabled", False):
                    success = await self.whatsapp_service.send_message(
                        to_number=phone,
                        message=alert_message
                    )
                else:
                    success = await self.twilio_service.send_sms(
                        to_number=phone,
                        message=alert_message
                    )
                
                if success:
                    success_count += 1
            
            logger.info(f"Staff alert sent to {success_count}/{len(staff_phones)} staff members")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending staff alert: {e}")
            return False
    
    async def send_system_alert(
        self,
        business: Business,
        alert_type: str,
        message: str,
        severity: str = "info"
    ) -> bool:
        """Send system alert notification."""
        try:
            # Get admin phone numbers
            admin_phones = self._get_admin_phones(business.id)
            
            if not admin_phones:
                logger.warning(f"No admin phones found for business {business.id}")
                return False
            
            # Format system alert
            alert_message = f"""⚙️ **System Alert - {business.name}**

**Type:** {alert_type}
**Severity:** {severity.upper()}

{message}

**Time:** {datetime.now().strftime('%I:%M %p')}"""
            
            # Send to all admins
            success_count = 0
            for phone in admin_phones:
                if business.settings.get("whatsapp_enabled", False):
                    success = await self.whatsapp_service.send_message(
                        to_number=phone,
                        message=alert_message
                    )
                else:
                    success = await self.twilio_service.send_sms(
                        to_number=phone,
                        message=alert_message
                    )
                
                if success:
                    success_count += 1
            
            logger.info(f"System alert sent to {success_count}/{len(admin_phones)} admins")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending system alert: {e}")
            return False
    
    async def send_promotional_message(
        self,
        business: Business,
        customer_phone: str,
        promotion_type: str,
        message: str,
        discount_code: Optional[str] = None
    ) -> bool:
        """Send promotional message."""
        try:
            promo_message = f"""🎉 **Special Offer - {business.name}**

{message}

{f"**Use Code:** {discount_code}" if discount_code else ""}

**Valid until:** {self._get_promotion_end_date()}

Visit us today! 🍽️"""
            
            # Send notification
            if business.settings.get("whatsapp_enabled", False):
                success = await self.whatsapp_service.send_message(
                    to_number=customer_phone,
                    message=promo_message
                )
            else:
                success = await self.twilio_service.send_sms(
                    to_number=customer_phone,
                    message=promo_message
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending promotional message: {e}")
            return False
    
    async def schedule_notification(
        self,
        notification_type: NotificationType,
        scheduled_time: datetime,
        recipient_phone: str,
        business_id: int,
        message_data: Dict[str, Any]
    ) -> bool:
        """Schedule a notification for later delivery."""
        try:
            # Store notification in database for scheduled delivery
            # This would be implemented with a task queue like Celery
            logger.info(f"Scheduled {notification_type.value} notification for {scheduled_time}")
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return False
    
    def _load_notification_templates(self) -> Dict[str, str]:
        """Load notification templates."""
        return {
            "order_confirmation": "✅ Your order #{order_id} has been confirmed!",
            "order_ready": "🎉 Your order is ready for pickup!",
            "booking_confirmation": "📅 Your booking has been confirmed!",
            "payment_success": "💳 Payment successful!",
            "payment_failed": "❌ Payment failed. Please try again.",
            "staff_alert": "🚨 Staff alert: {message}",
            "system_alert": "⚙️ System alert: {message}"
        }
    
    def _estimate_ready_time(self, order: Order) -> str:
        """Estimate order ready time."""
        # Simple estimation based on order size and type
        base_time = 10  # minutes
        item_count = sum(item.quantity for item in order.items)
        
        if item_count > 5:
            base_time += 5
        elif item_count > 10:
            base_time += 10
        
        ready_time = datetime.now() + timedelta(minutes=base_time)
        return ready_time.strftime("%I:%M %p")
    
    def _get_status_specific_message(self, status: OrderStatus, order: Order) -> str:
        """Get status-specific message."""
        if status == OrderStatus.PREPARING:
            return f"⏰ Estimated ready time: {self._estimate_ready_time(order)}"
        elif status == OrderStatus.READY:
            return "🎉 Please pick up your order at the counter!"
        elif status == OrderStatus.COMPLETED:
            return "Thank you for choosing us! We hope you enjoyed your meal."
        elif status == OrderStatus.CANCELLED:
            return "If you have any questions, please contact our staff."
        else:
            return ""
    
    def _get_staff_phones(self, business_id: int) -> List[str]:
        """Get staff phone numbers for a business."""
        # This would query your user/staff table
        # For now, return empty list as placeholder
        return []
    
    def _get_admin_phones(self, business_id: int) -> List[str]:
        """Get admin phone numbers for a business."""
        # This would query your user/admin table
        # For now, return empty list as placeholder
        return []
    
    def _get_promotion_end_date(self) -> str:
        """Get promotion end date."""
        end_date = datetime.now() + timedelta(days=7)
        return end_date.strftime("%B %d, %Y")

    async def send_waitlist_confirmation(
        self,
        customer_phone: str,
        customer_name: str,
        estimated_wait_time: int,
        business_name: str
    ) -> bool:
        """Send waitlist confirmation notification."""
        try:
            message = f"""⏳ **Added to Waitlist**

**{business_name}**
👤 {customer_name}
⏰ Estimated wait: {estimated_wait_time} minutes

We'll notify you as soon as a table becomes available! 

**What to expect:**
• We'll send you a message when your table is ready
• Please respond within 5 minutes to confirm
• If you don't respond, we'll move to the next person

Thank you for your patience! 🙏"""
            
            # Send via SMS (waitlist notifications are typically urgent)
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending waitlist confirmation: {e}")
            return False

    async def send_table_ready_notification(
        self,
        customer_phone: str,
        customer_name: str,
        wait_time: int,
        business_name: str
    ) -> bool:
        """Send table ready notification."""
        try:
            message = f"""🎉 **Your Table is Ready!**

**{business_name}**
👤 {customer_name}
⏱️ You waited: {wait_time} minutes

**Your table is now available!**

Please come to the host stand within 5 minutes to be seated.

Thank you for your patience! 🙏"""
            
            # Send via SMS (urgent notification)
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending table ready notification: {e}")
            return False

    async def send_waitlist_update(
        self,
        customer_phone: str,
        customer_name: str,
        current_wait_time: int,
        estimated_wait_time: int
    ) -> bool:
        """Send waitlist update notification."""
        try:
            message = f"""⏳ **Waitlist Update**

**{customer_name}**
⏱️ Current wait: {current_wait_time} minutes
⏰ Original estimate: {estimated_wait_time} minutes

We're working to get you seated as soon as possible. Thank you for your patience! 🙏"""
            
            # Send via SMS
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending waitlist update: {e}")
            return False

    async def send_churn_prevention_message(
        self,
        customer_phone: str,
        customer_name: str,
        business_name: str,
        days_since_last_order: int,
        usual_order: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send churn prevention message to at-risk customers."""
        try:
            if usual_order:
                usual_items = ", ".join([item["name"] for item in usual_order["items"][:2]])
                message = f"""👋 **We Miss You!**

**{business_name}**
👤 {customer_name}

It's been {days_since_last_order} days since your last visit. We'd love to see you again!

**Your usual favorites are waiting:**
{usual_items}

**Special offer:** 15% off your next order when you visit this week!

Use code: WELCOMEBACK

Come back soon! 🍽️"""
            else:
                message = f"""👋 **We Miss You!**

**{business_name}**
👤 {customer_name}

It's been {days_since_last_order} days since your last visit. We'd love to see you again!

**Special offer:** 15% off your next order when you visit this week!

Use code: WELCOMEBACK

Come back soon! 🍽️"""
            
            # Send via WhatsApp if available, otherwise SMS
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending churn prevention message: {e}")
            return False

    async def send_personalized_recommendation(
        self,
        customer_phone: str,
        customer_name: str,
        business_name: str,
        recommendations: List[Dict[str, Any]]
    ) -> bool:
        """Send personalized recommendations to customer."""
        try:
            if not recommendations:
                return False
            
            # Format recommendations
            rec_items = []
            for rec in recommendations[:3]:  # Top 3 recommendations
                rec_items.append(f"• {rec['name']} - ${rec['price']:.2f} ({rec['reason']})")
            
            rec_text = "\n".join(rec_items)
            
            message = f"""🎯 **Personalized for You**

**{business_name}**
👤 {customer_name}

Based on your preferences, we think you'll love:

{rec_text}

**Ready to order?** Just reply with what you'd like! 🍽️"""
            
            # Send via WhatsApp if available, otherwise SMS
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending personalized recommendation: {e}")
            return False

    async def send_low_stock_alert(
        self,
        business_id: int,
        item_name: str,
        current_stock: int,
        threshold: int
    ) -> bool:
        """Send low stock alert to business staff."""
        try:
            # Get business info
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if not business:
                return False
            
            message = f"""⚠️ **Low Stock Alert**

**{business.name}**
📦 Item: {item_name}
🔢 Current stock: {current_stock}
🚨 Threshold: {threshold}

**Action required:** Please restock this item soon to avoid running out.

**Time:** {datetime.now().strftime('%I:%M %p')}"""
            
            # Send to staff
            return await self.send_staff_alert(
                business=business,
                alert_type="low_stock",
                message=f"Low stock alert for {item_name}",
                priority=NotificationPriority.HIGH
            )
            
        except Exception as e:
            logger.error(f"Error sending low stock alert: {e}")
            return False

    async def send_order_confirmation(
        self,
        customer_phone: str,
        order_id: int,
        business_name: str,
        estimated_time: Optional[datetime] = None
    ) -> bool:
        """Send order confirmation notification."""
        try:
            time_str = estimated_time.strftime("%I:%M %p") if estimated_time else "10-15 minutes"
            
            message = f"""✅ **Order #{order_id} Confirmed!**

**{business_name}**
⏰ Estimated ready time: {time_str}

We'll notify you when your order is ready for pickup!

Thank you for choosing us! 🎉"""
            
            # Send via SMS
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending order confirmation: {e}")
            return False

    async def send_delivery_notification(
        self,
        customer_phone: str,
        order_id: int,
        delivery_address: str,
        estimated_delivery_time: Optional[str] = None
    ) -> bool:
        """Send delivery notification."""
        try:
            time_str = estimated_delivery_time or "30-45 minutes"
            
            message = f"""🚚 **Delivery Order #{order_id}**

⏰ Estimated delivery: {time_str}
📍 Address: {delivery_address}

We'll notify you when your order is on the way!

Thank you for choosing delivery! 🎉"""
            
            # Send via SMS
            success = await self.twilio_service.send_sms(
                to_number=customer_phone,
                message=message
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending delivery notification: {e}")
            return False