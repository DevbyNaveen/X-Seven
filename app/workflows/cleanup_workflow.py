from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.workflows.cleanup_activities import cleanup_expired_orders_activity

@workflow.defn
class CleanupWorkflow:
    @workflow.run
    async def run(self) -> None:
        """Runs the cleanup workflow."""
        workflow.logger.info("Starting cleanup workflow...")
        await workflow.execute_activity(
            cleanup_expired_orders_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )
        workflow.logger.info("Cleanup workflow finished.")
