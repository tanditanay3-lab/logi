"""
Service layer for the Shipment Tracking Agent.

This service handles all business logic for shipment tracking.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.db.models import (
    AgentTask as AgentTaskModel,
    Shipment as ShipmentModel,
    ShipmentEvent as ShipmentEventModel,
    Tenant,
)
from packages.shared_types.schemas import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskStatus,
    AgentType,
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalRequestStatus,
    Config,
    TrustLevel,
)
from packages.shared_types.utils import generate_id, get_current_timestamp
from packages.tool_bus.mcp_client import MCPClient
from packages.tool_bus.tool_definitions import ToolCall, ToolResult

from .config import ShipmentTrackingConfig
from .schemas import (
    EtaDriftDetection,
    Location,
    Shipment,
    ShipmentCreate,
    ShipmentEvent,
    ShipmentEventCreate,
    ShipmentStatus,
    ShipmentUpdate,
    TrackingWebhookPayload,
    TrackingWebhookResponse,
)

logger = logging.getLogger(__name__)


class ShipmentTrackingService:
    """
    Service for managing shipment tracking operations.
    
    This service handles:
    - Creating and updating shipments
    - Processing carrier webhooks
    - Detecting ETA drift
    - Managing tracking events
    - Generating notifications
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: ShipmentTrackingConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        self._eta_drift_check_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        
        # Start background tasks
        if self.config.eta_drift_check_interval_minutes > 0:
            self._eta_drift_check_task = asyncio.create_task(
                self._check_eta_drift_periodically()
            )
        
    async def close(self):
        """Close the service."""
        if self._eta_drift_check_task:
            self._eta_drift_check_task.cancel()
            try:
                await self._eta_drift_check_task
            except asyncio.CancelledError:
                pass
        
        await self.tool_client.close()
    
    # ========================================================================
    # Shipment CRUD Operations
    # ========================================================================
    
    async def create_shipment(
        self,
        shipment_data: ShipmentCreate,
        tenant_id: str
    ) -> Tuple[Shipment, Optional[AgentTask]]:
        """
        Create a new shipment.
        
        Args:
            shipment_data: Shipment data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created shipment, agent task if approval required)
        """
        # Check if we need approval based on trust level
        agent_task: Optional[AgentTask] = None
        
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            # Create approval request
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="create_shipment",
                input_data=shipment_data.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        
        # Create the shipment
        shipment_model = ShipmentModel(
            id=generate_id("shipment"),
            tenant_id=tenant_id,
            tracking_number=shipment_data.tracking_number,
            carrier=shipment_data.carrier,
            carrier_service=shipment_data.carrier_service,
            status=shipment_data.status,
            origin=shipment_data.origin.model_dump() if shipment_data.origin else {},
            destination=shipment_data.destination.model_dump() if shipment_data.destination else {},
            estimated_delivery=shipment_data.estimated_delivery,
            metadata=shipment_data.metadata.model_dump() if shipment_data.metadata else {},
            notes=shipment_data.notes,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(shipment_model)
        await self.db_session.commit()
        await self.db_session.refresh(shipment_model)
        
        # If auto-execute, mark task as completed
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            # Update in database
            await self._update_agent_task(agent_task)
        
        # Convert to schema
        shipment = await self._model_to_schema(shipment_model)
        
        return shipment, agent_task
    
    async def get_shipment(self, shipment_id: str, tenant_id: str) -> Optional[Shipment]:
        """Get a shipment by ID."""
        result = await self.db_session.execute(
            select(ShipmentModel)
            .where(
                and_(
                    ShipmentModel.id == shipment_id,
                    ShipmentModel.tenant_id == tenant_id
                )
            )
            .options(joinedload(ShipmentModel.events))
        )
        
        shipment_model = result.scalar_one_or_none()
        if not shipment_model:
            return None
        
        return await self._model_to_schema(shipment_model)
    
    async def list_shipments(
        self,
        tenant_id: str,
        status: Optional[ShipmentStatus] = None,
        carrier: Optional[str] = None,
        tracking_number: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Shipment], int]:
        """List shipments with optional filters."""
        query = select(ShipmentModel).where(ShipmentModel.tenant_id == tenant_id)
        
        if status:
            query = query.where(ShipmentModel.status == status)
        if carrier:
            query = query.where(ShipmentModel.carrier.ilike(f"%{carrier}%"))
        if tracking_number:
            query = query.where(ShipmentModel.tracking_number.ilike(f"%{tracking_number}%"))
        
        # Count total
        count_result = await self.db_session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Get results
        query = query.order_by(desc(ShipmentModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        shipment_models = result.scalars().all()
        
        shipments = [await self._model_to_schema(m) for m in shipment_models]
        
        return shipments, total
    
    async def update_shipment(
        self,
        shipment_id: str,
        shipment_data: ShipmentUpdate,
        tenant_id: str
    ) -> Tuple[Optional[Shipment], Optional[AgentTask]]:
        """Update a shipment."""
        result = await self.db_session.execute(
            select(ShipmentModel).where(
                and_(
                    ShipmentModel.id == shipment_id,
                    ShipmentModel.tenant_id == tenant_id
                )
            )
        )
        
        shipment_model = result.scalar_one_or_none()
        if not shipment_model:
            return None, None
        
        # Check if we need approval
        agent_task: Optional[AgentTask] = None
        
        # Update fields
        if shipment_data.tracking_number is not None:
            shipment_model.tracking_number = shipment_data.tracking_number
        if shipment_data.carrier is not None:
            shipment_model.carrier = shipment_data.carrier
        if shipment_data.carrier_service is not None:
            shipment_model.carrier_service = shipment_data.carrier_service
        if shipment_data.status is not None:
            shipment_model.status = shipment_data.status
        if shipment_data.estimated_delivery is not None:
            shipment_model.estimated_delivery = shipment_data.estimated_delivery
        if shipment_data.actual_delivery is not None:
            shipment_model.actual_delivery = shipment_data.actual_delivery
        if shipment_data.current_location is not None:
            shipment_model.current_location = (
                shipment_data.current_location.model_dump()
                if shipment_data.current_location else None
            )
        if shipment_data.metadata is not None:
            shipment_model.metadata = shipment_data.metadata.model_dump()
        if shipment_data.notes is not None:
            shipment_model.notes = shipment_data.notes
        
        shipment_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(shipment_model)
        
        shipment = await self._model_to_schema(shipment_model)
        
        return shipment, agent_task
    
    async def delete_shipment(self, shipment_id: str, tenant_id: str) -> bool:
        """Delete a shipment."""
        result = await self.db_session.execute(
            select(ShipmentModel).where(
                and_(
                    ShipmentModel.id == shipment_id,
                    ShipmentModel.tenant_id == tenant_id
                )
            )
        )
        
        shipment_model = result.scalar_one_or_none()
        if not shipment_model:
            return False
        
        await self.db_session.delete(shipment_model)
        await self.db_session.commit()
        
        return True
    
    # ========================================================================
    # Shipment Event Operations
    # ========================================================================
    
    async def add_shipment_event(
        self,
        shipment_id: str,
        event_data: ShipmentEventCreate,
        tenant_id: str
    ) -> Tuple[Optional[Shipment], Optional[AgentTask]]:
        """Add an event to a shipment."""
        # Get shipment
        shipment = await self.get_shipment(shipment_id, tenant_id)
        if not shipment:
            return None, None
        
        # Create event model
        event_model = ShipmentEventModel(
            id=generate_id("evt"),
            shipment_id=shipment_id,
            timestamp=event_data.timestamp,
            event_type=event_data.event_type,
            description=event_data.description,
            location=event_data.location.model_dump() if event_data.location else None,
            carrier_timestamp=event_data.carrier_timestamp,
            created_at=get_current_timestamp()
        )
        
        self.db_session.add(event_model)
        await self.db_session.commit()
        await self.db_session.refresh(event_model)
        
        # Update shipment status if needed
        if event_data.event_type in ["DELIVERED", "DELIVERY_CONFIRMED"]:
            shipment_model = await self.db_session.get(ShipmentModel, shipment_id)
            if shipment_model:
                shipment_model.status = ShipmentStatus.DELIVERED
                shipment_model.actual_delivery = event_data.timestamp
                shipment_model.updated_at = get_current_timestamp()
                await self.db_session.commit()
        
        # Check for ETA drift
        await self._check_eta_drift(shipment_id, tenant_id)
        
        # Return updated shipment
        updated_shipment = await self.get_shipment(shipment_id, tenant_id)
        
        return updated_shipment, None
    
    # ========================================================================
    # Carrier Webhook Processing
    # ========================================================================
    
    async def process_carrier_webhook(
        self,
        payload: TrackingWebhookPayload,
        tenant_id: str
    ) -> TrackingWebhookResponse:
        """
        Process a carrier webhook payload.
        
        This method:
        1. Finds or creates the shipment
        2. Adds the event to the shipment
        3. Updates shipment status
        4. Checks for ETA drift
        5. Creates AgentTask for the webhook processing
        """
        events_created = 0
        shipment_id: Optional[str] = None
        
        # Find existing shipment by tracking number
        result = await self.db_session.execute(
            select(ShipmentModel).where(
                and_(
                    ShipmentModel.tracking_number == payload.tracking_number,
                    ShipmentModel.tenant_id == tenant_id
                )
            )
        )
        
        shipment_model = result.scalar_one_or_none()
        
        if not shipment_model:
            # Create new shipment from webhook
            shipment_model = ShipmentModel(
                id=generate_id("shipment"),
                tenant_id=tenant_id,
                tracking_number=payload.tracking_number,
                carrier=payload.carrier,
                status=payload.status or ShipmentStatus.IN_TRANSIT,
                estimated_delivery=payload.estimated_delivery,
                created_at=get_current_timestamp(),
                updated_at=get_current_timestamp()
            )
            self.db_session.add(shipment_model)
            await self.db_session.commit()
            await self.db_session.refresh(shipment_model)
            shipment_id = shipment_model.id
        else:
            shipment_id = shipment_model.id
            
            # Update shipment from webhook
            if payload.status:
                shipment_model.status = payload.status
            if payload.estimated_delivery:
                shipment_model.estimated_delivery = payload.estimated_delivery
            if payload.location:
                shipment_model.current_location = payload.location.model_dump()
            
            shipment_model.updated_at = get_current_timestamp()
            await self.db_session.commit()
        
        # Add event
        event_model = ShipmentEventModel(
            id=generate_id("evt"),
            shipment_id=shipment_id,
            timestamp=payload.event_timestamp,
            event_type=payload.event_type,
            description=payload.event_description,
            location=payload.location.model_dump() if payload.location else None,
            carrier_timestamp=payload.event_timestamp,
            created_at=get_current_timestamp()
        )
        
        self.db_session.add(event_model)
        await self.db_session.commit()
        events_created = 1
        
        # Check for ETA drift
        await self._check_eta_drift(shipment_id, tenant_id)
        
        # Create AgentTask for webhook processing
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="process_carrier_webhook",
            input_data={
                "tracking_number": payload.tracking_number,
                "carrier": payload.carrier,
                "event_type": payload.event_type,
                "shipment_id": shipment_id
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Processed carrier webhook for {payload.carrier} tracking {payload.tracking_number}"
        )
        
        return TrackingWebhookResponse(
            status="processed",
            shipment_id=shipment_id,
            tracking_number=payload.tracking_number,
            events_created=events_created,
            agent_task_id=agent_task.id if agent_task else None
        )
    
    # ========================================================================
    # Tracking Refresh
    # ========================================================================
    
    async def refresh_tracking(
        self,
        shipment_id: str,
        tenant_id: str
    ) -> Tuple[str, Optional[str]]:
        """
        Refresh tracking data from carrier.
        
        Returns:
            Tuple of (status, agent_task_id)
        """
        shipment = await self.get_shipment(shipment_id, tenant_id)
        if not shipment:
            return "failed", None
        
        # Call carrier API to refresh tracking
        tool_result = await self._call_carrier_tracking_api(
            tracking_number=shipment.tracking_number,
            carrier=shipment.carrier,
            tenant_id=tenant_id
        )
        
        if tool_result.status == "success":
            tracking_data = tool_result.result
            
            # Update shipment with new data
            shipment_model = await self.db_session.get(ShipmentModel, shipment_id)
            if shipment_model:
                if tracking_data.get("status"):
                    shipment_model.status = tracking_data["status"]
                if tracking_data.get("current_location"):
                    shipment_model.current_location = tracking_data["current_location"]
                if tracking_data.get("estimated_delivery"):
                    shipment_model.estimated_delivery = datetime.fromisoformat(
                        tracking_data["estimated_delivery"]
                    )
                if tracking_data.get("events"):
                    # Add new events
                    for event in tracking_data["events"]:
                        event_model = ShipmentEventModel(
                            id=generate_id("evt"),
                            shipment_id=shipment_id,
                            timestamp=datetime.fromisoformat(event["timestamp"]),
                            event_type=event["type"],
                            description=event["description"],
                            location=event.get("location"),
                            carrier_timestamp=datetime.fromisoformat(event["timestamp"]),
                            created_at=get_current_timestamp()
                        )
                        self.db_session.add(event_model)
                
                shipment_model.updated_at = get_current_timestamp()
                await self.db_session.commit()
            
            # Check for ETA drift
            await self._check_eta_drift(shipment_id, tenant_id)
            
            # Create AgentTask
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="refresh_tracking",
                input_data={"shipment_id": shipment_id},
                status=AgentTaskStatus.AUTO_EXECUTED,
                reasoning_trace=f"Refreshed tracking data for shipment {shipment_id}"
            )
            
            return "completed", agent_task.id
        else:
            # Create failed AgentTask
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="refresh_tracking",
                input_data={"shipment_id": shipment_id},
                status=AgentTaskStatus.FAILED,
                error_message=tool_result.error or "Unknown error",
                reasoning_trace=f"Failed to refresh tracking for shipment {shipment_id}"
            )
            
            return "failed", agent_task.id
    
    # ========================================================================
    # ETA Drift Detection
    # ========================================================================
    
    async def _check_eta_drift(
        self,
        shipment_id: str,
        tenant_id: str
    ) -> Optional[EtaDriftDetection]:
        """Check if a shipment has ETA drift."""
        shipment = await self.get_shipment(shipment_id, tenant_id)
        if not shipment:
            return None
        
        if not shipment.estimated_delivery:
            return None
        
        # Get current ETA from carrier
        tool_result = await self._call_carrier_tracking_api(
            tracking_number=shipment.tracking_number,
            carrier=shipment.carrier,
            tenant_id=tenant_id
        )
        
        if tool_result.status != "success":
            return None
        
        tracking_data = tool_result.result
        current_eta_str = tracking_data.get("estimated_delivery")
        
        if not current_eta_str:
            return None
        
        try:
            current_eta = datetime.fromisoformat(current_eta_str)
            original_eta = shipment.estimated_delivery
            
            if original_eta and current_eta:
                drift_minutes = (current_eta - original_eta).total_seconds() / 60
                
                if abs(drift_minutes) > self.config.eta_drift_threshold_minutes:
                    # ETA drift detected
                    drift_detection = EtaDriftDetection(
                        shipment_id=shipment_id,
                        tracking_number=shipment.tracking_number,
                        original_eta=original_eta,
                        current_eta=current_eta,
                        drift_minutes=drift_minutes,
                        drift_detected=True,
                        threshold_minutes=self.config.eta_drift_threshold_minutes
                    )
                    
                    # Update shipment
                    shipment_model = await self.db_session.get(ShipmentModel, shipment_id)
                    if shipment_model:
                        shipment_model.eta_drift_minutes = drift_minutes
                        shipment_model.eta_drift_detected_at = get_current_timestamp()
                        shipment_model.updated_at = get_current_timestamp()
                        await self.db_session.commit()
                    
                    # Create AgentTask for drift detection
                    await self._create_agent_task(
                        tenant_id=tenant_id,
                        action_type="eta_drift_detected",
                        input_data={
                            "shipment_id": shipment_id,
                            "drift_minutes": drift_minutes,
                            "original_eta": original_eta.isoformat(),
                            "current_eta": current_eta.isoformat()
                        },
                        status=AgentTaskStatus.AUTO_EXECUTED,
                        reasoning_trace=f"Detected ETA drift of {drift_minutes} minutes for shipment {shipment_id}"
                    )
                    
                    # Send notification if configured
                    if self.config.notify_on_delay and abs(drift_minutes) >= self.config.delay_notification_threshold_minutes:
                        await self._send_delay_notification(shipment, drift_minutes, tenant_id)
                    
                    return drift_detection
        except (ValueError, TypeError) as e:
            logger.error(f"Error checking ETA drift for {shipment_id}: {e}")
        
        return None
    
    async def _check_eta_drift_periodically(self):
        """Periodically check all shipments for ETA drift."""
        while True:
            try:
                # Get all in-transit shipments
                result = await self.db_session.execute(
                    select(ShipmentModel).where(
                        and_(
                            ShipmentModel.status == ShipmentStatus.IN_TRANSIT,
                            ShipmentModel.estimated_delivery.isnot(None)
                        )
                    )
                )
                
                shipments = result.scalars().all()
                
                for shipment in shipments:
                    await self._check_eta_drift(shipment.id, shipment.tenant_id)
                
            except Exception as e:
                logger.error(f"Error in periodic ETA drift check: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.config.eta_drift_check_interval_minutes * 60)
    
    # ========================================================================
    # Notifications
    # ========================================================================
    
    async def _send_delay_notification(
        self,
        shipment: Shipment,
        drift_minutes: float,
        tenant_id: str
    ):
        """Send a delay notification."""
        # This would call the notification tool
        tool_result = await self.tool_client.call_tool(
            tool_name="notification.send_email",
            arguments={
                "to": "dispatcher@company.com",  # Would be configured per-tenant
                "subject": f"Delay Alert: Shipment {shipment.tracking_number}",
                "body": f"Shipment {shipment.tracking_number} has a delay of {abs(drift_minutes)} minutes.",
                "template_id": "shipment_delay"
            },
            tenant_id=tenant_id,
            agent_type="shipment-tracking",
            timeout=10
        )
        
        if tool_result.status != "success":
            logger.error(f"Failed to send delay notification: {tool_result.error}")
    
    # ========================================================================
    # Agent Task Management
    # ========================================================================
    
    async def _create_agent_task(
        self,
        tenant_id: str,
        action_type: str,
        input_data: Dict[str, Any],
        status: AgentTaskStatus = AgentTaskStatus.PENDING_APPROVAL,
        reasoning_trace: str = "",
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> AgentTask:
        """Create an AgentTask record."""
        task_data = AgentTaskCreate(
            tenant_id=tenant_id,
            agent_type=AgentType.SHIPMENT_TRACKING,
            action_type=action_type,
            trust_level=self.config.trust_level,
            reasoning_trace=reasoning_trace or f"{action_type} action",
            input_data=input_data,
            output_data=output_data,
            status=status,
            error_message=error_message
        )
        
        # Create task model
        task_model = AgentTaskModel(
            id=generate_id("task"),
            tenant_id=tenant_id,
            agent_type=AgentType.SHIPMENT_TRACKING,
            action_type=action_type,
            status=status,
            trust_level=self.config.trust_level,
            reasoning_trace=task_data.reasoning_trace,
            input_data=task_data.input_data,
            output_data=task_data.output_data,
            error_message=task_data.error_message,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(task_model)
        await self.db_session.commit()
        await self.db_session.refresh(task_model)
        
        # Convert to schema
        return AgentTask(
            id=task_model.id,
            tenant_id=task_model.tenant_id,
            agent_type=task_model.agent_type,
            action_type=task_model.action_type,
            status=task_model.status,
            trust_level=task_model.trust_level,
            reasoning_trace=task_model.reasoning_trace,
            input_data=task_model.input_data,
            output_data=task_model.output_data,
            error_message=task_model.error_message,
            created_at=task_model.created_at,
            updated_at=task_model.updated_at,
            completed_at=task_model.completed_at
        )
    
    async def _update_agent_task(self, task: AgentTask):
        """Update an AgentTask."""
        result = await self.db_session.execute(
            select(AgentTaskModel).where(AgentTaskModel.id == task.id)
        )
        
        task_model = result.scalar_one_or_none()
        if task_model:
            task_model.status = task.status
            task_model.output_data = task.output_data
            task_model.error_message = task.error_message
            task_model.completed_at = task.completed_at or get_current_timestamp()
            task_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
    
    # ========================================================================
    # Carrier API Integration
    # ========================================================================
    
    async def _call_carrier_tracking_api(
        self,
        tracking_number: str,
        carrier: str,
        tenant_id: str
    ) -> ToolResult:
        """Call the carrier tracking API through the Tool Bus."""
        return await self.tool_client.call_tool(
            tool_name="carrier.get_tracking_info",
            arguments={
                "tracking_number": tracking_number,
                "carrier": carrier
            },
            tenant_id=tenant_id,
            agent_type="shipment-tracking",
            timeout=10
        )
    
    # ========================================================================
    # Configuration Management
    # ========================================================================
    
    async def get_config(self, tenant_id: str) -> ShipmentTrackingConfig:
        """Get the current configuration."""
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> ShipmentTrackingConfig:
        """Update the configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.config
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def _model_to_schema(self, model: ShipmentModel) -> Shipment:
        """Convert a ShipmentModel to Shipment schema."""
        return Shipment(
            id=model.id,
            tenant_id=model.tenant_id,
            tracking_number=model.tracking_number,
            carrier=model.carrier,
            carrier_service=model.carrier_service,
            status=model.status,
            origin=Location(**model.origin) if model.origin else None,
            destination=Location(**model.destination) if model.destination else None,
            estimated_delivery=model.estimated_delivery,
            actual_delivery=model.actual_delivery,
            current_location=Location(**model.current_location) if model.current_location else None,
            eta_drift_minutes=model.eta_drift_minutes,
            eta_drift_detected_at=model.eta_drift_detected_at,
            metadata=model.metadata,
            carrier_account=model.carrier_account,
            billing_reference=model.billing_reference,
            notes=model.notes,
            events=[
                ShipmentEvent(
                    id=e.id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    description=e.description,
                    location=Location(**e.location) if e.location else None,
                    carrier_timestamp=e.carrier_timestamp
                )
                for e in (model.events or [])
            ],
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get shipment statistics."""
        result = await self.db_session.execute(
            select(
                func.count(ShipmentModel.id),
                func.count().filter(ShipmentModel.status == ShipmentStatus.IN_TRANSIT).label("in_transit"),
                func.count().filter(ShipmentModel.status == ShipmentStatus.DELIVERED).label("delivered"),
                func.count().filter(ShipmentModel.status == ShipmentStatus.DELAYED).label("delayed"),
                func.count().filter(ShipmentModel.status == ShipmentStatus.CANCELLED).label("cancelled"),
                func.count().filter(ShipmentModel.status == ShipmentStatus.PENDING).label("pending"),
            )
            .where(ShipmentModel.tenant_id == tenant_id)
        )
        
        row = result.fetchone()
        
        return {
            "total_shipments": row[0],
            "in_transit": row[1],
            "delivered": row[2],
            "delayed": row[3],
            "cancelled": row[4],
            "pending": row[5]
        }
