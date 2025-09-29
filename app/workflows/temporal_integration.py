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
    
    async def start_workflow(self, workflow_type: str, workflow_data: Dict[str, Any] = None, conversation_id: str = None) -> Optional[str]:
        """Start a workflow based on its type"""
        if self._disabled or not await self.is_ready():
            logger.warning("Cannot start workflow - Temporal is disabled or not ready")
            return None
            
        try:
            # Generate workflow ID if not provided
            workflow_id = f"{workflow_type}-{conversation_id or str(uuid.uuid4())[:8]}-{int(datetime.now().timestamp())}"
            
            # Get workflow class
            workflow_class = self.workflow_mapping.get(workflow_type)
            if not workflow_class:
                raise ValueError(f"Unknown workflow type: {workflow_type}")
            
            # Start workflow
            handle = await self.client.start_workflow(
                workflow_class.run,
                workflow_data or {},
                id=workflow_id,
                task_queue="conversation-tasks"
            )
            
            # Track active workflow
            self.active_workflows[workflow_id] = handle
            
            logger.info(f"✅ Started {workflow_type} workflow with ID: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"❌ Failed to start {workflow_type} workflow: {e}")
            return None
    
    async def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get list of active workflows with status"""
        if self._disabled:
            return []
            
        result = []
        try:
            for workflow_id, handle in self.active_workflows.items():
                try:
                    description = await handle.describe()
                    result.append({
                        "workflow_id": workflow_id,
                        "status": description.status.name,
                        "started_at": description.start_time.isoformat() if description.start_time else None,
                        "type": description.workflow_type.name
                    })
                except Exception as e:
                    logger.debug(f"Error fetching workflow {workflow_id}: {e}")
            
            return result
        except Exception as e:
            logger.error(f"Failed to get active workflows: {e}")
            return []
    
    async def cancel_workflow(self, workflow_id: str, reason: str = None) -> bool:
        """Cancel a running workflow"""
        if self._disabled or workflow_id not in self.active_workflows:
            return False
            
        try:
            handle = self.active_workflows[workflow_id]
            await handle.cancel(reason)
            
            # Remove from active workflows
            self.active_workflows.pop(workflow_id, None)
            
            logger.info(f"✅ Cancelled workflow {workflow_id}: {reason or 'No reason provided'}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel workflow {workflow_id}: {e}")
            return False
    
    async def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get metrics for Temporal workflows"""
        if self._disabled:
            return {
                "status": "disabled",
                "active_workflows": 0,
                "completed_workflows": 0
            }
            
        try:
            active_count = len(self.active_workflows)
            workflow_types = {}
            
            # Count workflows by type
            for workflow_id in self.active_workflows:
                workflow_type = workflow_id.split('-')[0]
                workflow_types[workflow_type] = workflow_types.get(workflow_type, 0) + 1
            
            return {
                "status": "active",
                "active_workflows": active_count,
                "workflow_types": workflow_types,
                "task_queue": "conversation-tasks",
                "temporal_host": self.temporal_host,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get workflow metrics: {e}")
            return {
                "status": "error",
                "error": str(e),
                "active_workflows": len(self.active_workflows)
            }
    
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
