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
        """Initialize Temporal client and worker"""
        try:
            # Connect to Temporal server
            self.client = await Client.connect(self.temporal_host)
            logger.info(f"✅ Connected to Temporal server at {self.temporal_host}")
            
            # Initialize worker for workflow execution
            self.worker = Worker(
                self.client,
                task_queue="x-seven-ai-workflows",
                workflows=[AppointmentWorkflow, OrderWorkflow, CleanupWorkflow],
                activities=self._get_all_activities()
            )
            
            logger.info("✅ Temporal worker initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Temporal: {e}")
            raise
    
    def _get_all_activities(self):
        """Get all workflow activities"""
        from app.workflows.appointment_activities import (
            create_appointment,
            send_appointment_confirmation,
            send_appointment_reminder
        )
        from app.workflows.activities import (
            send_notification,
            update_business_state,
            log_interaction
        )
        from app.workflows.cleanup_activities import (
            cleanup_expired_conversations,
            cleanup_old_workflows
        )
        
        return [
            create_appointment,
            send_appointment_confirmation,
            send_appointment_reminder,
            send_notification,
            update_business_state,
            log_interaction,
            cleanup_expired_conversations,
            cleanup_old_workflows
        ]
    
    async def start_workflow(self, workflow_type: str, workflow_data: Dict[str, Any],
                           conversation_id: str = None) -> str:
        """Start a Temporal workflow"""
        try:
            if not self.client:
                await self.initialize()
            
            # Get workflow class
            workflow_class = self.workflow_mapping.get(workflow_type)
            if not workflow_class:
                raise ValueError(f"Unknown workflow type: {workflow_type}")
            
            # Generate workflow ID
            workflow_id = f"{workflow_type}_{uuid.uuid4()}"
            
            # Enhance workflow data with conversation context
            enhanced_data = {
                **workflow_data,
                "workflow_id": workflow_id,
                "conversation_id": conversation_id,
                "started_at": datetime.now().isoformat(),
                "workflow_type": workflow_type
            }
            
            # Start workflow
            handle = await self.client.start_workflow(
                workflow_class.run,
                enhanced_data,
                id=workflow_id,
                task_queue="x-seven-ai-workflows"
            )
            
            # Track active workflow
            self.active_workflows[workflow_id] = handle
            
            logger.info(f"✅ Started {workflow_type} workflow {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"❌ Failed to start workflow {workflow_type}: {e}")
            raise
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get status of a running workflow"""
        try:
            if workflow_id not in self.active_workflows:
                # Try to get handle from Temporal
                handle = self.client.get_workflow_handle(workflow_id)
                self.active_workflows[workflow_id] = handle
            else:
                handle = self.active_workflows[workflow_id]
            
            # Get workflow description
            description = await handle.describe()
            
            return {
                "workflow_id": workflow_id,
                "status": description.status.name,
                "run_id": description.run_id,
                "start_time": description.start_time.isoformat() if description.start_time else None,
                "close_time": description.close_time.isoformat() if description.close_time else None,
                "execution_time": description.execution_time,
                "workflow_type": description.workflow_type.name if description.workflow_type else None
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get workflow status {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "unknown",
                "error": str(e)
            }
    
    async def wait_for_workflow_completion(self, workflow_id: str, timeout_seconds: int = 300) -> Dict[str, Any]:
        """Wait for workflow completion with timeout"""
        try:
            if workflow_id not in self.active_workflows:
                handle = self.client.get_workflow_handle(workflow_id)
                self.active_workflows[workflow_id] = handle
            else:
                handle = self.active_workflows[workflow_id]
            
            # Wait for completion with timeout
            result = await asyncio.wait_for(
                handle.result(),
                timeout=timeout_seconds
            )
            
            # Remove from active workflows
            if workflow_id in self.active_workflows:
                del self.active_workflows[workflow_id]
            
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat()
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Workflow {workflow_id} timed out after {timeout_seconds} seconds")
            return {
                "workflow_id": workflow_id,
                "status": "timeout",
                "timeout_seconds": timeout_seconds
            }
        except Exception as e:
            logger.error(f"❌ Error waiting for workflow {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": str(e)
            }
    
    async def cancel_workflow(self, workflow_id: str, reason: str = "User requested") -> bool:
        """Cancel a running workflow"""
        try:
            if workflow_id not in self.active_workflows:
                handle = self.client.get_workflow_handle(workflow_id)
                self.active_workflows[workflow_id] = handle
            else:
                handle = self.active_workflows[workflow_id]
            
            # Cancel workflow
            await handle.cancel()
            
            # Remove from active workflows
            if workflow_id in self.active_workflows:
                del self.active_workflows[workflow_id]
            
            logger.info(f"✅ Cancelled workflow {workflow_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel workflow {workflow_id}: {e}")
            return False
    
    async def signal_workflow(self, workflow_id: str, signal_name: str, signal_data: Any) -> bool:
        """Send signal to a running workflow"""
        try:
            if workflow_id not in self.active_workflows:
                handle = self.client.get_workflow_handle(workflow_id)
                self.active_workflows[workflow_id] = handle
            else:
                handle = self.active_workflows[workflow_id]
            
            # Send signal
            await handle.signal(signal_name, signal_data)
            
            logger.info(f"✅ Sent signal {signal_name} to workflow {workflow_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to signal workflow {workflow_id}: {e}")
            return False
    
    async def query_workflow(self, workflow_id: str, query_name: str) -> Any:
        """Query a running workflow"""
        try:
            if workflow_id not in self.active_workflows:
                handle = self.client.get_workflow_handle(workflow_id)
                self.active_workflows[workflow_id] = handle
            else:
                handle = self.active_workflows[workflow_id]
            
            # Execute query
            result = await handle.query(query_name)
            
            logger.info(f"✅ Queried workflow {workflow_id} with {query_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to query workflow {workflow_id}: {e}")
            return None
    
    # Conversation-specific workflow methods
    
    async def start_appointment_workflow(self, appointment_data: Dict[str, Any], 
                                       conversation_id: str = None) -> str:
        """Start appointment booking workflow"""
        return await self.start_workflow(
            "appointment_workflow",
            appointment_data,
            conversation_id
        )
    
    async def start_order_workflow(self, order_data: Dict[str, Any],
                                 conversation_id: str = None) -> str:
        """Start order processing workflow"""
        return await self.start_workflow(
            "order_workflow", 
            order_data,
            conversation_id
        )
    
    async def start_cleanup_workflow(self, cleanup_data: Dict[str, Any] = None) -> str:
        """Start system cleanup workflow"""
        return await self.start_workflow(
            "cleanup_workflow",
            cleanup_data or {"cleanup_type": "routine"},
            None
        )
    
    # Workflow data preparation helpers
    
    def prepare_appointment_data(self, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare appointment data from conversation context"""
        return {
            "business_id": conversation_context.get("business_id"),
            "user_id": conversation_context.get("user_id"),
            "service_type": conversation_context.get("detected_intent", "general"),
            "appointment_date": conversation_context.get("date"),
            "appointment_time": conversation_context.get("time"),
            "party_size": conversation_context.get("party_size", 1),
            "special_requests": conversation_context.get("special_requests", ""),
            "contact_info": {
                "phone": conversation_context.get("phone"),
                "email": conversation_context.get("email")
            },
            "created_from": "conversation",
            "conversation_id": conversation_context.get("conversation_id")
        }
    
    def prepare_order_data(self, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare order data from conversation context"""
        return {
            "business_id": conversation_context.get("business_id"),
            "user_id": conversation_context.get("user_id"),
            "items": conversation_context.get("items", []),
            "total_amount": conversation_context.get("total_amount", 0),
            "delivery_address": conversation_context.get("delivery_address"),
            "delivery_time": conversation_context.get("delivery_time"),
            "payment_method": conversation_context.get("payment_method"),
            "special_instructions": conversation_context.get("special_instructions", ""),
            "created_from": "conversation",
            "conversation_id": conversation_context.get("conversation_id")
        }
    
    # System management
    
    async def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get list of active workflows"""
        workflows = []
        
        for workflow_id, handle in self.active_workflows.items():
            try:
                status = await self.get_workflow_status(workflow_id)
                workflows.append(status)
            except Exception as e:
                logger.error(f"Error getting status for workflow {workflow_id}: {e}")
                workflows.append({
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": str(e)
                })
        
        return workflows
    
    async def cleanup_completed_workflows(self) -> int:
        """Clean up completed workflows from tracking"""
        cleaned = 0
        completed_workflows = []
        
        for workflow_id, handle in self.active_workflows.items():
            try:
                description = await handle.describe()
                if description.status.name in ["COMPLETED", "FAILED", "CANCELLED", "TERMINATED"]:
                    completed_workflows.append(workflow_id)
            except Exception as e:
                logger.error(f"Error checking workflow {workflow_id}: {e}")
                completed_workflows.append(workflow_id)
        
        # Remove completed workflows
        for workflow_id in completed_workflows:
            if workflow_id in self.active_workflows:
                del self.active_workflows[workflow_id]
                cleaned += 1
        
        logger.info(f"✅ Cleaned up {cleaned} completed workflows")
        return cleaned
    
    async def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get workflow system metrics"""
        active_count = len(self.active_workflows)
        
        # Get status breakdown
        status_counts = {}
        for workflow_id in self.active_workflows:
            try:
                status = await self.get_workflow_status(workflow_id)
                status_name = status.get("status", "unknown")
                status_counts[status_name] = status_counts.get(status_name, 0) + 1
            except Exception:
                status_counts["error"] = status_counts.get("error", 0) + 1
        
        return {
            "active_workflows": active_count,
            "status_breakdown": status_counts,
            "workflow_types": list(self.workflow_mapping.keys()),
            "temporal_host": self.temporal_host,
            "timestamp": datetime.now().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform Temporal health check"""
        try:
            if not self.client:
                return {
                    "status": "unhealthy",
                    "error": "Client not initialized",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Try to list workflows (basic connectivity test)
            # This is a simple way to test if Temporal is responsive
            workflows = await self.get_active_workflows()
            
            return {
                "status": "healthy",
                "client_connected": True,
                "active_workflows": len(workflows),
                "temporal_host": self.temporal_host,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "temporal_host": self.temporal_host,
                "timestamp": datetime.now().isoformat()
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
