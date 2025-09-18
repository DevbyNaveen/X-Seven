"""
Execution Agent - Modern Database Operations Agent with Self-Healing
Executes structured actions in Supabase with validation and automatic recovery
"""
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .self_healing import with_self_healing, self_healing_manager

@dataclass
class ExecutionResult:
    """Result of execution operation"""
    success: bool
    action_type: str
    data: Dict[str, Any]
    confirmation_message: str
    error_message: Optional[str] = None

class ExecutionAgent:
    """
    AI-powered execution agent with self-healing capabilities
    Validates and executes structured actions in Supabase with automatic recovery
    """

    def __init__(self, supabase_client, webhook_url: Optional[str] = None):
        self.supabase = supabase_client
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)
        
        # Register with self-healing system
        self_healing_manager.register_agent("execution_agent", self)
        
        # Define fallback strategies
        self._fallback_strategies = self._create_fallback_strategies()
    
    def _create_fallback_strategies(self):
        """Create fallback strategies for self-healing"""
        async def error_fallback():
            return ExecutionResult(
                success=False,
                action_type="unknown",
                data={},
                confirmation_message="",
                error_message="Service temporarily unavailable, please try again"
            )
        
        return error_fallback
    
    @with_self_healing("execution_agent")
    async def execute_action(self, structured_data: Dict[str, Any]) -> ExecutionResult:
        """
        Execute the structured action in database with self-healing protection
        
        Args:
            structured_data: Structured data from slot-filling agent
            
        Returns:
            ExecutionResult with success status and confirmation
        """
        try:
            action_type = structured_data.get("action", "")

            if action_type == "create_booking":
                return await self._create_booking(structured_data)
            elif action_type == "create_order":
                return await self._create_order(structured_data)
            elif action_type == "get_information":
                return await self._get_information(structured_data)
            elif action_type == "cancel_booking":
                return await self._cancel_booking(structured_data)
            elif action_type == "update_booking":
                return await self._update_booking(structured_data)
            else:
                return ExecutionResult(
                    success=False,
                    action_type=action_type,
                    data={},
                    confirmation_message="",
                    error_message=f"Unknown action type: {action_type}"
                )

        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                action_type=structured_data.get("action", "unknown"),
                data={},
                confirmation_message="",
                error_message=str(e)
            )

    async def _create_booking(self, data: Dict[str, Any]) -> ExecutionResult:
        """Create a new booking/appointment - category-agnostic"""
        try:
            # Validate required fields
            required_fields = ["business_id", "customer_name", "booking_datetime", "phone"]
            missing_fields = [field for field in required_fields if not data.get(field)]

            if missing_fields:
                return ExecutionResult(
                    success=False,
                    action_type="create_booking",
                    data={},
                    confirmation_message="",
                    error_message=f"Missing required fields: {', '.join(missing_fields)}"
                )

            # Handle case where business_id is None
            business_id = data.get("business_id")
            if business_id is None:
                return ExecutionResult(
                    success=False,
                    action_type="create_booking",
                    data={},
                    confirmation_message="",
                    error_message="Unable to determine which business to book with. Please specify a business name."
                )

            # Validate business exists
            business_resp = self.supabase.table("businesses").select("*").eq("id", business_id).execute()
            if not business_resp.data:
                return ExecutionResult(
                    success=False,
                    action_type="create_booking",
                    data={},
                    confirmation_message="",
                    error_message="Business not found"
                )

            business = business_resp.data[0]
            business_category = business.get("category", "General")

            # Create booking record (use existing reservations table for now, but make it generic)
            booking_data = {
                "business_id": business_id,
                "customer_name": data["customer_name"].strip(),
                "phone": data["phone"].strip(),
                "reservation_datetime": data["booking_datetime"],
                "party_size": data.get("party_size", 1),
                "special_requests": data.get("special_requests", "").strip(),
                "status": "confirmed",
                "created_at": datetime.utcnow().isoformat(),
                "user_id": data.get("user_id"),
                "booking_type": business_category.lower()  # Track the business category
            }

            result = self.supabase.table("reservations").insert(booking_data).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="create_booking",
                    data={},
                    confirmation_message="",
                    error_message="Failed to create booking in database"
                )

            booking = result.data[0]
            booking_id = booking["id"]
            confirmation_code = f"BK{booking_id:06d}"

            # Update with confirmation code
            self.supabase.table("reservations").update({
                "confirmation_code": confirmation_code
            }).eq("id", booking_id).execute()

            # Add to live dining board (reuse existing table for now)
            await self._add_to_live_dining_board(booking, confirmation_code)

            # Trigger webhook if configured
            await self._trigger_webhook("booking_created", {
                "booking_id": booking_id,
                "confirmation_code": confirmation_code,
                "business_name": business["name"],
                "business_category": business_category,
                "customer_name": data["customer_name"],
                "party_size": data.get("party_size", 1),
                "booking_datetime": data["booking_datetime"]
            })

            # Generate category-specific confirmation message
            confirmation_msg = self._generate_booking_confirmation_message(
                business, business_category, confirmation_code, data
            )

            return ExecutionResult(
                success=True,
                action_type="create_booking",
                data={
                    "booking_id": booking_id,
                    "confirmation_code": confirmation_code,
                    "business_name": business["name"],
                    "business_category": business_category
                },
                confirmation_message=confirmation_msg
            )

        except Exception as e:
            self.logger.error(f"Booking creation failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="create_booking",
                data={},
                confirmation_message="",
                error_message=f"Failed to create booking: {str(e)}"
            )

    def _generate_booking_confirmation_message(self, business: Dict, category: str, confirmation_code: str, data: Dict) -> str:
        """Generate category-specific booking confirmation message"""
        base_msg = f"Thank you! Your booking at {business['name']} is confirmed. Confirmation code: {confirmation_code}"

        category_lower = category.lower()

        if "restaurant" in category_lower or "food" in category_lower:
            party_size = data.get("party_size", 2)
            return f"{base_msg}\n\nTable for {party_size} confirmed. We'll see you then!"
        elif "service" in category_lower or "repair" in category_lower:
            return f"{base_msg}\n\nYour service appointment has been scheduled. We'll contact you if needed."
        elif "retail" in category_lower or "shop" in category_lower:
            return f"{base_msg}\n\nYour appointment is confirmed. Looking forward to serving you!"
        else:
            return f"{base_msg}\n\nYour appointment has been confirmed successfully."

    async def _create_reservation(self, data: Dict[str, Any]) -> ExecutionResult:
        """Create a new reservation"""
        try:
            # Validate required fields
            required_fields = ["business_id", "customer_name", "party_size", "reservation_datetime", "phone"]
            missing_fields = [field for field in required_fields if not data.get(field)]

            if missing_fields:
                return ExecutionResult(
                    success=False,
                    action_type="create_reservation",
                    data={},
                    confirmation_message="",
                    error_message=f"Missing required fields: {', '.join(missing_fields)}"
                )

            # Validate business exists
            business_resp = self.supabase.table("businesses").select("*").eq("id", data["business_id"]).execute()
            if not business_resp.data:
                return ExecutionResult(
                    success=False,
                    action_type="create_reservation",
                    data={},
                    confirmation_message="",
                    error_message="Business not found"
                )

            business = business_resp.data[0]

            # Create reservation record
            reservation_data = {
                "business_id": data["business_id"],
                "customer_name": data["customer_name"].strip(),
                "phone": data["phone"].strip(),
                "reservation_datetime": data["reservation_datetime"],
                "party_size": int(data["party_size"]),
                "special_requests": data.get("special_requests", "").strip(),
                "status": "confirmed",
                "created_at": datetime.utcnow().isoformat(),
                "user_id": data.get("user_id")
            }

            result = self.supabase.table("reservations").insert(reservation_data).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="create_reservation",
                    data={},
                    confirmation_message="",
                    error_message="Failed to create reservation in database"
                )

            reservation = result.data[0]
            reservation_id = reservation["id"]
            confirmation_code = f"RES{reservation_id:06d}"

            # Update with confirmation code
            self.supabase.table("reservations").update({
                "confirmation_code": confirmation_code
            }).eq("id", reservation_id).execute()

            # Add to live dining board
            await self._add_to_live_dining_board(reservation, confirmation_code)

            # Trigger webhook if configured
            await self._trigger_webhook("reservation_created", {
                "reservation_id": reservation_id,
                "confirmation_code": confirmation_code,
                "business_name": business["name"],
                "customer_name": data["customer_name"],
                "party_size": data["party_size"],
                "reservation_datetime": data["reservation_datetime"]
            })

            return ExecutionResult(
                success=True,
                action_type="create_reservation",
                data={
                    "reservation_id": reservation_id,
                    "confirmation_code": confirmation_code,
                    "business_name": business["name"]
                },
                confirmation_message=f"Perfect! Your reservation at {business['name']} is confirmed. Reservation code: {confirmation_code}"
            )

        except Exception as e:
            self.logger.error(f"Reservation creation failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="create_reservation",
                data={},
                confirmation_message="",
                error_message=f"Failed to create reservation: {str(e)}"
            )

    async def _create_order(self, data: Dict[str, Any]) -> ExecutionResult:
        """Create a new order - category-agnostic"""
        try:
            # Validate required fields
            required_fields = ["business_id", "customer_name", "phone", "items"]
            missing_fields = [field for field in required_fields if not data.get(field)]

            if missing_fields:
                return ExecutionResult(
                    success=False,
                    action_type="create_order",
                    data={},
                    confirmation_message="",
                    error_message=f"Missing required fields: {', '.join(missing_fields)}"
                )

            # Handle case where business_id is None
            business_id = data.get("business_id")
            if business_id is None:
                return ExecutionResult(
                    success=False,
                    action_type="create_order",
                    data={},
                    confirmation_message="",
                    error_message="Unable to determine which business to order from. Please specify a business name."
                )

            # Validate business exists
            business_resp = self.supabase.table("businesses").select("*").eq("id", business_id).execute()
            if not business_resp.data:
                return ExecutionResult(
                    success=False,
                    action_type="create_order",
                    data={},
                    confirmation_message="",
                    error_message="Business not found"
                )

            business = business_resp.data[0]
            business_category = business.get("category", "General")

            # Calculate total price (simplified - you may want to implement proper menu pricing)
            total_amount = 0.0
            items_description = data.get("items", "")

            # For now, use a simple estimation - in production you'd calculate based on menu
            # This is a placeholder for proper order calculation
            order_data = {
                "business_id": business_id,
                "customer_name": data["customer_name"].strip(),
                "phone": data["phone"].strip(),
                "items": items_description,
                "total_amount": total_amount,  # This should be calculated properly
                "delivery_method": data.get("delivery_method", "pickup"),
                "delivery_address": data.get("delivery_address", "").strip(),
                "special_instructions": data.get("special_instructions", "").strip(),
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "user_id": data.get("user_id"),
                "order_type": business_category.lower()  # Track the business category
            }

            result = self.supabase.table("orders").insert(order_data).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="create_order",
                    data={},
                    confirmation_message="",
                    error_message="Failed to create order in database"
                )

            order = result.data[0]
            order_id = order["id"]
            order_number = f"ORD{order_id:06d}"

            # Update with order number
            self.supabase.table("orders").update({
                "order_number": order_number
            }).eq("id", order_id).execute()

            # Trigger webhook if configured
            await self._trigger_webhook("order_created", {
                "order_id": order_id,
                "order_number": order_number,
                "business_name": business["name"],
                "business_category": business_category,
                "customer_name": data["customer_name"],
                "items": items_description,
                "delivery_method": data.get("delivery_method", "pickup")
            })

            # Generate category-specific confirmation message
            confirmation_msg = f"Thank you! I've placed your order from {business['name']}. Order number: {order_number}. We'll confirm the total shortly."

            return ExecutionResult(
                success=True,
                action_type="create_order",
                data={
                    "order_id": order_id,
                    "order_number": order_number,
                    "business_name": business["name"],
                    "business_category": business_category
                },
                confirmation_message=confirmation_msg
            )

        except Exception as e:
            self.logger.error(f"Order creation failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="create_order",
                data={},
                confirmation_message="",
                error_message=f"Failed to create order: {str(e)}"
            )

    async def _cancel_reservation(self, data: Dict[str, Any]) -> ExecutionResult:
        """Cancel an existing reservation"""
        try:
            reservation_id = data.get("reservation_id")
            if not reservation_id:
                return ExecutionResult(
                    success=False,
                    action_type="cancel_reservation",
                    data={},
                    confirmation_message="",
                    error_message="Reservation ID is required for cancellation"
                )

            # Update reservation status to cancelled
            result = self.supabase.table("reservations").update({
                "status": "cancelled",
                "cancelled_at": datetime.utcnow().isoformat()
            }).eq("id", reservation_id).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="cancel_reservation",
                    data={},
                    confirmation_message="",
                    error_message="Reservation not found or already cancelled"
                )

            reservation = result.data[0]

            # Trigger webhook
            await self._trigger_webhook("reservation_cancelled", {
                "reservation_id": reservation_id,
                "customer_name": reservation["customer_name"],
                "business_id": reservation["business_id"]
            })

            return ExecutionResult(
                success=True,
                action_type="cancel_reservation",
                data={"reservation_id": reservation_id},
                confirmation_message="Your reservation has been cancelled successfully."
            )

        except Exception as e:
            self.logger.error(f"Reservation cancellation failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="cancel_reservation",
                data={},
                confirmation_message="",
                error_message=f"Failed to cancel reservation: {str(e)}"
            )

    async def _update_reservation(self, data: Dict[str, Any]) -> ExecutionResult:
        """Update an existing reservation"""
        try:
            reservation_id = data.get("reservation_id")
            if not reservation_id:
                return ExecutionResult(
                    success=False,
                    action_type="update_reservation",
                    data={},
                    confirmation_message="",
                    error_message="Reservation ID is required for updates"
                )

            # Build update data from provided fields
            update_data = {}
            updatable_fields = ["party_size", "reservation_datetime", "special_requests"]

            for field in updatable_fields:
                if field in data:
                    if field == "party_size":
                        update_data[field] = int(data[field])
                    else:
                        update_data[field] = data[field]

            if not update_data:
                return ExecutionResult(
                    success=False,
                    action_type="update_reservation",
                    data={},
                    confirmation_message="",
                    error_message="No valid fields provided for update"
                )

            update_data["updated_at"] = datetime.utcnow().isoformat()

            # Update reservation
            result = self.supabase.table("reservations").update(update_data).eq("id", reservation_id).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="update_reservation",
                    data={},
                    confirmation_message="",
                    error_message="Reservation not found"
                )

            reservation = result.data[0]

            # Trigger webhook
            await self._trigger_webhook("reservation_updated", {
                "reservation_id": reservation_id,
                "updates": update_data,
                "customer_name": reservation["customer_name"]
            })

            return ExecutionResult(
                success=True,
                action_type="update_reservation",
                data={"reservation_id": reservation_id, "updates": update_data},
                confirmation_message="Your reservation has been updated successfully."
            )

        except Exception as e:
            self.logger.error(f"Reservation update failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="update_reservation",
                data={},
                confirmation_message="",
                error_message=f"Failed to update reservation: {str(e)}"
            )

    async def _get_information(self, data: Dict[str, Any]) -> ExecutionResult:
        """Handle information requests"""
        try:
            business_name = data.get("business_name")
            topic = data.get("topic", "general")

            # This is a simple placeholder - in a real system, you'd implement
            # more sophisticated information retrieval
            if business_name:
                return ExecutionResult(
                    success=True,
                    action_type="get_information",
                    data={"business_name": business_name, "topic": topic},
                    confirmation_message=f"I'll help you find information about {business_name} regarding {topic}."
                )
            else:
                return ExecutionResult(
                    success=True,
                    action_type="get_information",
                    data={"topic": topic},
                    confirmation_message=f"I'll help you find information about {topic}."
                )

        except Exception as e:
            self.logger.error(f"Information retrieval failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="get_information",
                data={},
                confirmation_message="",
                error_message=f"Failed to retrieve information: {str(e)}"
            )

    async def _cancel_booking(self, data: Dict[str, Any]) -> ExecutionResult:
        """Cancel an existing booking"""
        try:
            booking_id = data.get("booking_id")
            if not booking_id:
                return ExecutionResult(
                    success=False,
                    action_type="cancel_booking",
                    data={},
                    confirmation_message="",
                    error_message="Booking ID is required for cancellation"
                )

            # Update booking status to cancelled
            result = self.supabase.table("reservations").update({
                "status": "cancelled",
                "cancelled_at": datetime.utcnow().isoformat()
            }).eq("id", booking_id).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="cancel_booking",
                    data={},
                    confirmation_message="",
                    error_message="Booking not found or already cancelled"
                )

            booking = result.data[0]

            # Trigger webhook
            await self._trigger_webhook("booking_cancelled", {
                "booking_id": booking_id,
                "customer_name": booking["customer_name"],
                "business_id": booking["business_id"]
            })

            return ExecutionResult(
                success=True,
                action_type="cancel_booking",
                data={"booking_id": booking_id},
                confirmation_message="Your booking has been cancelled successfully."
            )

        except Exception as e:
            self.logger.error(f"Booking cancellation failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="cancel_booking",
                data={},
                confirmation_message="",
                error_message=f"Failed to cancel booking: {str(e)}"
            )

    async def _update_booking(self, data: Dict[str, Any]) -> ExecutionResult:
        """Update an existing booking"""
        try:
            booking_id = data.get("booking_id")
            if not booking_id:
                return ExecutionResult(
                    success=False,
                    action_type="update_booking",
                    data={},
                    confirmation_message="",
                    error_message="Booking ID is required for updates"
                )

            # Build update data from provided fields
            update_data = {}
            updatable_fields = ["party_size", "reservation_datetime", "special_requests"]

            for field in updatable_fields:
                if field in data:
                    if field == "party_size":
                        update_data[field] = int(data[field])
                    else:
                        update_data[field] = data[field]

            if not update_data:
                return ExecutionResult(
                    success=False,
                    action_type="update_booking",
                    data={},
                    confirmation_message="",
                    error_message="No valid fields provided for update"
                )

            update_data["updated_at"] = datetime.utcnow().isoformat()

            # Update booking
            result = self.supabase.table("reservations").update(update_data).eq("id", booking_id).execute()

            if not result.data:
                return ExecutionResult(
                    success=False,
                    action_type="update_booking",
                    data={},
                    confirmation_message="",
                    error_message="Booking not found"
                )

            booking = result.data[0]

            # Trigger webhook
            await self._trigger_webhook("booking_updated", {
                "booking_id": booking_id,
                "updates": update_data,
                "customer_name": booking["customer_name"]
            })

            return ExecutionResult(
                success=True,
                action_type="update_booking",
                data={"booking_id": booking_id, "updates": update_data},
                confirmation_message="Your booking has been updated successfully."
            )

        except Exception as e:
            self.logger.error(f"Booking update failed: {e}")
            return ExecutionResult(
                success=False,
                action_type="update_booking",
                data={},
                confirmation_message="",
                error_message=f"Failed to update booking: {str(e)}"
            )

    async def _add_to_live_dining_board(self, reservation_data: Dict[str, Any], confirmation_code: str):
        """Add reservation to live dining board"""
        try:
            live_entry = {
                "reservation_id": reservation_data["id"],
                "business_id": reservation_data["business_id"],
                "customer_name": reservation_data["customer_name"],
                "party_size": reservation_data["party_size"],
                "reservation_time": reservation_data["reservation_datetime"],
                "status": "confirmed",
                "confirmation_code": confirmation_code,
                "created_at": datetime.utcnow().isoformat(),
            }
            self.supabase.table("live_dining_board").insert(live_entry).execute()
            self.logger.info(f"✅ Added reservation {confirmation_code} to Live Dining Board")

        except Exception as e:
            self.logger.error(f"❌ Failed to add to Live Dining Board: {e}")

    async def _trigger_webhook(self, event_type: str, data: Dict[str, Any]):
        """Trigger webhook for real-time integrations"""
        if not self.webhook_url:
            return

        try:
            import httpx

            payload = {
                "event": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }

            async with httpx.AsyncClient() as client:
                await client.post(self.webhook_url, json=payload, timeout=10.0)

            self.logger.info(f"📤 Webhook sent: {event_type}")

        except Exception as e:
            self.logger.error(f"❌ Webhook failed: {e}")
