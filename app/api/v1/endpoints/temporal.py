import os
from fastapi import APIRouter, HTTPException
from temporalio.client import Client

from app.schemas.appointment import AppointmentCreate
from app.schemas.order import OrderCreate
from app.workflows.appointment_workflow import AppointmentWorkflow
from app.workflows.order_workflow import OrderWorkflow

router = APIRouter()

async def get_temporal_client():
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    return await Client.connect(temporal_host)

@router.post("/orders", status_code=202)
async def create_order_workflow(order: OrderCreate, business_id: int):
    """Triggers the order processing workflow."""
    try:
        client = await get_temporal_client()
        is_delivery = True if order.delivery_address else False
        # In a real application, you would first create the order in the database
        # and then pass the order_id to the workflow.
        # For simplicity, we'll pass the order data directly.
        await client.start_workflow(
            OrderWorkflow.run,
            args=[1, business_id, is_delivery], # placeholder order_id
            id=f"order-{business_id}-{order.customer_email}-{order.scheduled_time or ''}",
            task_queue="order-processing-task-queue",
        )
        return {"message": "Order processing workflow started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/appointments", status_code=202)
async def create_appointment_workflow(appointment: AppointmentCreate):
    """Triggers the appointment booking workflow."""
    try:
        client = await get_temporal_client()
        await client.start_workflow(
            AppointmentWorkflow.run,
            appointment.dict(),
            id=f"appointment-{appointment.customer_email}-{appointment.start_time}",
            task_queue="appointment-processing-task-queue",
        )
        return {"message": "Appointment booking workflow started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
