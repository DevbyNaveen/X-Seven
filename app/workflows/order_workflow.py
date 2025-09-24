from datetime import datetime, timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        send_notification,
        update_business_state,
        log_interaction,
    )
    from app.workflows.order_activities import (
        validate_order,
        process_payment,
        prepare_order,
        schedule_delivery,
        send_order_updates
    )

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order_data: dict) -> str:
        workflow.logger.info(f"Starting enhanced order workflow for order {order_data.get('order_id', 'unknown')}")

        try:
            # 1. Validate order data
            validation_result = await workflow.execute_activity(
                validate_order,
                args=[order_data],
                start_to_close_timeout=timedelta(seconds=60),
            )
            
            if not validation_result.get("valid", False):
                workflow.logger.error(f"Order validation failed: {validation_result.get('error')}")
                return f"Order validation failed: {validation_result.get('error')}"
            
            workflow.logger.info("Order validated successfully")

            # 2. Process payment if required
            if order_data.get("payment_required", True):
                payment_result = await workflow.execute_activity(
                    process_payment,
                    args=[order_data],
                    start_to_close_timeout=timedelta(seconds=120),
                )
                
                if not payment_result.get("success", False):
                    workflow.logger.error(f"Payment processing failed: {payment_result.get('error')}")
                    return f"Payment failed: {payment_result.get('error')}"
                
                workflow.logger.info("Payment processed successfully")

            # 3. Log the order creation
            await workflow.execute_activity(
                log_interaction,
                args=[{
                    "type": "order_created",
                    "business_id": order_data.get("business_id"),
                    "user_id": order_data.get("user_id"),
                    "order_data": order_data,
                    "conversation_id": order_data.get("conversation_id"),
                    "timestamp": datetime.now().isoformat()
                }],
                start_to_close_timeout=timedelta(seconds=30),
            )
            workflow.logger.info("Order interaction logged")

            # 4. Send order confirmation
            await workflow.execute_activity(
                send_notification,
                args=[{
                    "type": "order_confirmation",
                    "recipient": order_data.get("user_id"),
                    "message": f"Your order has been confirmed! Order ID: {order_data.get('order_id', 'N/A')}",
                    "channel": "email",
                    "order_details": order_data
                }],
                start_to_close_timeout=timedelta(seconds=60),
            )
            workflow.logger.info("Order confirmation sent")

            # 5. Prepare order for fulfillment
            preparation_result = await workflow.execute_activity(
                prepare_order,
                args=[order_data],
                start_to_close_timeout=timedelta(seconds=300),  # 5 minutes for preparation
            )
            workflow.logger.info(f"Order preparation: {preparation_result.get('status')}")

            # 6. Schedule delivery if needed
            if order_data.get("delivery_required", False):
                delivery_result = await workflow.execute_activity(
                    schedule_delivery,
                    args=[order_data],
                    start_to_close_timeout=timedelta(seconds=120),
                )
                workflow.logger.info(f"Delivery scheduled: {delivery_result.get('status')}")
                
                # Send delivery notification
                await workflow.execute_activity(
                    send_notification,
                    args=[{
                        "type": "delivery_scheduled",
                        "recipient": order_data.get("user_id"),
                        "message": f"Your order will be delivered at {delivery_result.get('estimated_time')}",
                        "channel": "sms"
                    }],
                    start_to_close_timeout=timedelta(seconds=60),
                )

            # 7. Update business state
            await workflow.execute_activity(
                update_business_state,
                args=[{
                    "business_id": order_data.get("business_id"),
                    "update_type": "new_order",
                    "data": {
                        **order_data,
                        "status": "confirmed",
                        "processed_at": datetime.now().isoformat()
                    }
                }],
                start_to_close_timeout=timedelta(seconds=30),
            )
            workflow.logger.info("Business state updated")

            # 8. Schedule order status updates
            await workflow.execute_activity(
                send_order_updates,
                args=[order_data],
                start_to_close_timeout=timedelta(seconds=60),
            )

            order_id = order_data.get('order_id', 'unknown')
            workflow.logger.info(f"Order workflow completed successfully for {order_id}")
            return f"Order {order_id} processed and confirmed successfully"
            
        except Exception as e:
            workflow.logger.error(f"Order workflow failed: {str(e)}")
            
            # Send failure notification
            await workflow.execute_activity(
                send_notification,
                args=[{
                    "type": "order_failed",
                    "recipient": order_data.get("user_id"),
                    "message": f"We're sorry, but your order could not be processed. Please contact support.",
                    "channel": "email",
                    "error_details": str(e)
                }],
                start_to_close_timeout=timedelta(seconds=60),
            )
            
            return f"Order processing failed: {str(e)}"
