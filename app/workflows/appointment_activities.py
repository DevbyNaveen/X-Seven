import logging
from datetime import datetime

from temporalio import activity

from app.config.database import get_supabase_client
from app.models.appointment import Appointment, AppointmentStatus
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)

@activity.defn
async def create_appointment(appointment_data: dict) -> int:
    """Creates an appointment in the database."""
    try:
        with get_supabase_client() as db:
            appointment = Appointment(**appointment_data)
            appointment.status = AppointmentStatus.CONFIRMED
            db.add(appointment)
            db.commit()
            db.refresh(appointment)
            logger.info(f"Successfully created appointment {appointment.id}")
            return appointment.id
    except Exception as e:
        logger.error(f"Error creating appointment: {e}")
        raise

@activity.defn
async def send_appointment_confirmation(appointment_id: int):
    """Sends an appointment confirmation notification."""
    try:
        with get_supabase_client() as db:
            notification_service = NotificationService(db)
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                logger.error(f"Appointment {appointment_id} not found for confirmation.")
                return

            if appointment.customer_phone:
                await notification_service.send_appointment_confirmation(
                    customer_phone=appointment.customer_phone,
                    appointment_id=appointment.id,
                    start_time=appointment.start_time,
                    business_name="Your Business"
                )
    except Exception as e:
        logger.error(f"Error sending appointment confirmation for {appointment_id}: {e}")
        raise

@activity.defn
async def send_appointment_reminder(appointment_id: int):
    """Sends an appointment reminder notification."""
    try:
        with get_supabase_client() as db:
            notification_service = NotificationService(db)
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                logger.error(f"Appointment {appointment_id} not found for reminder.")
                return

            if appointment.customer_phone:
                await notification_service.send_appointment_reminder(
                    customer_phone=appointment.customer_phone,
                    appointment_id=appointment.id,
                    start_time=appointment.start_time,
                    business_name="Your Business"
                )
    except Exception as e:
        logger.error(f"Error sending appointment reminder for {appointment_id}: {e}")
        raise
