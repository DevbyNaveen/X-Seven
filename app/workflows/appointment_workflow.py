from datetime import datetime, timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.workflows.appointment_activities import (
        create_appointment,
        send_appointment_confirmation,
        send_appointment_reminder,
    )

@workflow.defn
class AppointmentWorkflow:
    @workflow.run
    async def run(self, appointment_data: dict) -> str:
        workflow.logger.info("Starting appointment workflow.")

        # 1. Create the appointment
        appointment_id = await workflow.execute_activity(
            create_appointment,
            args=[appointment_data],
            start_to_close_timeout=timedelta(seconds=60),
        )
        workflow.logger.info(f"Appointment {appointment_id} created.")

        # 2. Send confirmation immediately
        await workflow.execute_activity(
            send_appointment_confirmation,
            args=[appointment_id],
            start_to_close_timeout=timedelta(seconds=30),
        )
        workflow.logger.info(f"Sent appointment confirmation for {appointment_id}.")

        # 3. Schedule and send a reminder
        start_time_str = appointment_data.get("start_time")
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            reminder_time = start_time - timedelta(hours=1)
            now = workflow.now()

            if reminder_time > now:
                sleep_duration = reminder_time - now
                workflow.logger.info(f"Scheduling reminder for appointment {appointment_id} in {sleep_duration}.")
                await workflow.sleep(sleep_duration)

                await workflow.execute_activity(
                    send_appointment_reminder,
                    args=[appointment_id],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                workflow.logger.info(f"Sent appointment reminder for {appointment_id}.")

        return f"Appointment {appointment_id} processed successfully."
