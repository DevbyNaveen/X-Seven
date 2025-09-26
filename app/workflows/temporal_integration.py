"""
Temporal Workflow Integration Manager
Handles integration between LangGraph conversations and Temporal workflows
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import logging

from temporalio import workflow
from temporalio.client import Client, WorkflowHandle
from temporalio.worker import Worker

from app.workflows.appointment_workflow import AppointmentWorkflow
from app.workflows.order_workflow import OrderWorkflow
from app.workflows.cleanup_workflow import CleanupWorkflow

logger = logging.getLogger(__name__)


class TemporalWorkflowManager:
    """Manages Temporal workflow integration with LangGraph conversations"""
    
    def __init__(self, temporal_host: str = "localhost:7233"):
        self.temporal_host = temporal_host
        self.client: Optional[Client] = None
        self.worker: Optional[Worker] = None
        self._disabled = False
        
        # Workflow mapping
        self.workflow_mapping = {
            "appointment_workflow": AppointmentWorkflow,
            "order_workflow": OrderWorkflow,
            "cleanup_workflow": CleanupWorkflow
        }
        
        # Active workflows tracking
        self.active_workflows: Dict[str, WorkflowHandle] = {}
        
        logger.info("✅ Temporal Workflow Manager initialized")
    
    async def initialize(self):
        try:
            # Connect to Temporal server
            self.client = await Client.connect(self.temporal_host)
            logger.info(f"✅ Connected to Temporal server at {self.temporal_host}")
            
            # Initialize worker
            self.worker = Worker(
                self.client,
                task_queue="conversation-tasks",
                workflows=list(self.workflow_mapping.values())
            )
            
            logger.info("✅ Temporal worker initialized")
            
        except Exception as e:
            logger.warning(f"⚠️ Temporal server unavailable, workflows will be disabled: {e}")
            self._disabled = True
            self.client = None
            self.worker = None
    
    def _get_all_activities(self):
        """Get all workflow activities"""
        from app.workflows.appointment_activities import (
            create_appointment,
            update_appointment,
            cancel_appointment,
            get_appointment_details
        )
        from app.workflows.order_activities import (
            create_order,
            update_order_status,
            process_payment,
            send_order_confirmation
        )
        from app.workflows.cleanup_activities import (
            cleanup_old_conversations,
            archive_completed_workflows,
            optimize_database
        )
        
        return {
            "appointment": {
                "create_appointment": create_appointment,
                "update_appointment": update_appointment,
                "cancel_appointment": cancel_appointment,
                "get_appointment_details": get_appointment_details
            },
            "order": {
                "create_order": create_order,
                "update_order_status": update_order_status,
                "process_payment": process_payment,
                "send_order_confirmation": send_order_confirmation
            },
            "cleanup": {
                "cleanup_old_conversations": cleanup_old_conversations,
                "archive_completed_workflows": archive_completed_workflows,
                "optimize_database": optimize_database
            }
        }
    
    async def is_ready(self) -> bool:
        """Check if Temporal is ready for workflow execution"""
        return not self._disabled and self.client is not None and self.worker is not None
    
    async def cleanup_completed_workflows(self):
        """Clean up completed workflows - no-op when Temporal is disabled"""
        if self._disabled:
            logger.debug("Temporal disabled, skipping workflow cleanup")
            return
            
        try:
            # Clean up completed workflows
            completed_workflows = []
            for workflow_id, handle in list(self.active_workflows.items()):
                try:
                    status = await handle.describe()
                    if status.status.name == "COMPLETED":
                        completed_workflows.append(workflow_id)
                        await handle.cancel()
                except Exception as e:
                    logger.debug(f"Error checking workflow {workflow_id}: {e}")
                    completed_workflows.append(workflow_id)
            
            # Remove completed workflows from tracking
            for workflow_id in completed_workflows:
                self.active_workflows.pop(workflow_id, None)
                
            if completed_workflows:
                logger.info(f"Cleaned up {len(completed_workflows)} completed workflows")
                
        except Exception as e:
            logger.warning(f"Error during workflow cleanup: {e}")
    
    async def close(self):
        """Close Temporal connections"""
        try:
            if self.worker:
                await self.worker.shutdown()
            
            if self.client:
                await self.client.close()
            
            logger.info("✅ Temporal connections closed")
            
        except Exception as e:
            logger.error(f"❌ Error closing Temporal connections: {e}")


# Global instance
_temporal_manager = None

def get_temporal_manager() -> TemporalWorkflowManager:
    """Get global Temporal manager instance"""
    global _temporal_manager
    if _temporal_manager is None:
        _temporal_manager = TemporalWorkflowManager()
    return _temporal_manager
