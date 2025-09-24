import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

# Import activities and workflows
from app.workflows.activities import (
    confirm_order,
    send_order_confirmation,
    update_inventory,
    process_delivery,
)
from app.workflows.appointment_activities import (
    create_appointment,
    send_appointment_confirmation,
    send_appointment_reminder,
)
from app.workflows.order_workflow import OrderWorkflow
from app.workflows.appointment_workflow import AppointmentWorkflow
from app.workflows.cleanup_workflow import CleanupWorkflow
from app.workflows.cleanup_activities import cleanup_expired_orders_activity


async def main():
    # Get Temporal server host from environment variable
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")

    # Create a client to connect to the Temporal server
    client = await Client.connect(temporal_host)

    # Create a worker for order processing
    order_worker = Worker(
        client,
        task_queue="order-processing-task-queue",
        workflows=[OrderWorkflow],
        activities=[
            confirm_order,
            send_order_confirmation,
            update_inventory,
            process_delivery,
        ],
    )

    # Create a worker for appointment processing
    appointment_worker = Worker(
        client,
        task_queue="appointment-processing-task-queue",
        workflows=[AppointmentWorkflow],
        activities=[
            create_appointment,
            send_appointment_confirmation,
            send_appointment_reminder,
        ],
    )

    # Create a worker for cleanup tasks
    cleanup_worker = Worker(
        client,
        task_queue="cleanup-task-queue",
        workflows=[CleanupWorkflow],
        activities=[cleanup_expired_orders_activity],
    )

    # Start the cleanup workflow on a cron schedule
    await client.start_workflow(
        CleanupWorkflow.run,
        id="cleanup-workflow",
        task_queue="cleanup-task-queue",
        cron_schedule="*/30 * * * *",  # Every 30 minutes
    )

    # Run all workers concurrently
    print("Starting Temporal workers...")
    await asyncio.gather(order_worker.run(), appointment_worker.run(), cleanup_worker.run())
    print("Temporal workers stopped.")


if __name__ == "__main__":
    asyncio.run(main())
