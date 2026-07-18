"""
Service layer for the Fleet & Driver Management Agent.

This service handles all business logic for fleet and driver management including:
- Driver management (CRUD, HOS tracking)
- Vehicle management (CRUD, maintenance tracking)
- HOS compliance checking
- Driver-vehicle assignment
- Compliance alert generation
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.db.models import (
    AgentTask as AgentTaskModel,
    Driver as DriverModel,
    DriverHOSRecord as DriverHOSRecordModel,
    DriverViolation as DriverViolationModel,
    Tenant,
    Vehicle as VehicleModel,
    VehicleMaintenance as VehicleMaintenanceModel,
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
    WebhookEvent,
    WebhookEventType,
)
from packages.shared_types.utils import generate_id, get_current_timestamp
from packages.tool_bus.mcp_client import MCPClient
from packages.tool_bus.tool_definitions import ToolCall, ToolResult

from .config import FleetManagementConfig
from .schemas import (
    ComplianceAlert,
    ComplianceAlertListResponse,
    Driver,
    DriverCreate,
    DriverListResponse,
    DriverStatus,
    DriverUpdate,
    DriverVehicleAssignment,
    DriverVehicleAssignmentResponse,
    FleetStats,
    HOSComplianceCheckRequest,
    HOSComplianceCheckResponse,
    HOSEventCreate,
    HOSStatus,
    HOSEventType,
    MaintenanceRecord,
    MaintenanceRecordCreate,
    MaintenanceStatus,
    MaintenanceType,
    TelematicsData,
    Vehicle,
    VehicleCreate,
    VehicleListResponse,
    VehicleStatus,
    VehicleType,
    VehicleUpdate,
)

logger = logging.getLogger(__name__)


class FleetManagementService:
    """
    Service for managing fleet and driver operations.
    
    This service handles:
    - Creating and managing drivers
    - Tracking HOS (Hours of Service) compliance
    - Creating and managing vehicles
    - Tracking vehicle maintenance
    - Checking HOS compliance for route assignments
    - Generating compliance alerts
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: FleetManagementConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        logger.info("Fleet Management Service initialized")
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
        logger.info("Fleet Management Service closed")
    
    # ========================================================================
    # Driver Operations
    # ========================================================================
    
    async def create_driver(
        self,
        driver_data: DriverCreate,
        tenant_id: str
    ) -> Tuple[Driver, Optional[AgentTask]]:
        """
        Create a new driver.
        
        Args:
            driver_data: Driver data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created driver, agent task if approval required)
        """
        # Drivers are typically auto-executed as they're just data entry
        agent_task: Optional[AgentTask] = None
        
        # Create the driver
        driver_model = DriverModel(
            id=generate_id("driver"),
            tenant_id=tenant_id,
            name=driver_data.name,
            license_number=driver_data.license_number,
            license_state=driver_data.license_state,
            license_expiry=driver_data.license_expiry,
            status=driver_data.status,
            home_warehouse_id=driver_data.home_warehouse_id,
            skills=driver_data.skills,
            phone=driver_data.phone,
            email=driver_data.email,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(driver_model)
        await self.db_session.commit()
        await self.db_session.refresh(driver_model)
        
        # Convert to schema
        driver = await self._driver_model_to_schema(driver_model)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.FLEET_DRIVER_ASSIGNED,
            data={"driver_id": driver.id, "name": driver.name},
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return driver, agent_task
    
    async def get_driver(self, driver_id: str, tenant_id: str) -> Optional[Driver]:
        """Get a driver by ID."""
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.id == driver_id,
                    DriverModel.tenant_id == tenant_id
                )
            )
            .options(joinedload(DriverModel.home_warehouse))
        )
        
        driver_model = result.scalar_one_or_none()
        if not driver_model:
            return None
        
        return await self._driver_model_to_schema(driver_model)
    
    async def list_drivers(
        self,
        tenant_id: str,
        status: Optional[DriverStatus] = None,
        warehouse_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Driver], int]:
        """List drivers with optional filters."""
        query = select(DriverModel).where(DriverModel.tenant_id == tenant_id)
        
        if status:
            query = query.where(DriverModel.status == status)
        if warehouse_id:
            query = query.where(DriverModel.home_warehouse_id == warehouse_id)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db_session.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(desc(DriverModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        driver_models = result.scalars().all()
        
        drivers = [await self._driver_model_to_schema(model) for model in driver_models]
        
        return drivers, total
    
    async def update_driver(
        self,
        driver_id: str,
        driver_data: DriverUpdate,
        tenant_id: str
    ) -> Tuple[Optional[Driver], Optional[AgentTask]]:
        """
        Update a driver.
        
        Returns:
            Tuple of (updated driver, agent task if approval required)
        """
        # Get existing driver
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.id == driver_id,
                    DriverModel.tenant_id == tenant_id
                )
            )
        )
        
        driver_model = result.scalar_one_or_none()
        if not driver_model:
            return None, None
        
        # Update fields
        if driver_data.name:
            driver_model.name = driver_data.name
        if driver_data.license_number:
            driver_model.license_number = driver_data.license_number
        if driver_data.license_state:
            driver_model.license_state = driver_data.license_state
        if driver_data.license_expiry:
            driver_model.license_expiry = driver_data.license_expiry
        if driver_data.status:
            driver_model.status = driver_data.status
        if driver_data.home_warehouse_id:
            driver_model.home_warehouse_id = driver_data.home_warehouse_id
        if driver_data.skills:
            driver_model.skills = driver_data.skills
        if driver_data.phone:
            driver_model.phone = driver_data.phone
        if driver_data.email:
            driver_model.email = driver_data.email
        if driver_data.assigned_route_id:
            driver_model.assigned_route_id = driver_data.assigned_route_id
        if driver_data.current_vehicle_id:
            driver_model.current_vehicle_id = driver_data.current_vehicle_id
        
        driver_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(driver_model)
        
        driver = await self._driver_model_to_schema(driver_model)
        return driver, None
    
    async def delete_driver(self, driver_id: str, tenant_id: str) -> bool:
        """Delete a driver."""
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.id == driver_id,
                    DriverModel.tenant_id == tenant_id
                )
            )
        )
        
        driver_model = result.scalar_one_or_none()
        if not driver_model:
            return False
        
        await self.db_session.delete(driver_model)
        await self.db_session.commit()
        
        return True
    
    # ========================================================================
    # HOS Operations
    # ========================================================================
    
    async def update_hos_status(
        self,
        driver_id: str,
        event_data: HOSEventCreate,
        tenant_id: str
    ) -> Tuple[HOSStatus, Optional[AgentTask]]:
        """
        Update HOS status for a driver.
        
        Args:
            driver_id: Driver ID
            event_data: HOS event data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (updated HOS status, agent task if created)
        """
        # HOS updates are always auto-executed per trust level rules
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="update_hos_status",
            input_data={"driver_id": driver_id, **event_data.model_dump()},
            status=AgentTaskStatus.AUTO_EXECUTED,
            related_entity_id=driver_id,
            related_entity_type="driver"
        )
        
        # Get driver
        driver = await self.get_driver(driver_id, tenant_id)
        if not driver:
            raise ValueError(f"Driver {driver_id} not found")
        
        # Create HOS record
        hos_record = DriverHOSRecordModel(
            id=generate_id("hos"),
            driver_id=driver_id,
            tenant_id=tenant_id,
            event_type=event_data.event_type.value,
            duration_minutes=event_data.duration_minutes,
            location=event_data.location.model_dump() if event_data.location else None,
            notes=event_data.notes,
            created_at=event_data.timestamp or get_current_timestamp()
        )
        
        self.db_session.add(hos_record)
        await self.db_session.commit()
        
        # Recalculate HOS status
        hos_status = await self._calculate_hos_status(driver_id, tenant_id)
        
        # Update driver's HOS status
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.id == driver_id,
                    DriverModel.tenant_id == tenant_id
                )
            )
        )
        driver_model = result.scalar_one_or_none()
        if driver_model:
            # Update HOS status fields
            driver_model.hos_status = hos_status.model_dump()
            driver_model.updated_at = get_current_timestamp()
            await self.db_session.commit()
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.FLEET_DRIVER_HOS_UPDATED,
            data={
                "driver_id": driver_id,
                "event_type": event_data.event_type.value,
                "hos_status": hos_status.model_dump()
            },
            agent_task_id=agent_task.id
        )
        
        return hos_status, agent_task
    
    async def _calculate_hos_status(self, driver_id: str, tenant_id: str) -> HOSStatus:
        """
        Calculate current HOS status for a driver.
        
        This is a simplified calculation. In production, this would implement
        full FMCSA HOS regulations including 11-hour, 14-hour, and 60/70-hour rules.
        """
        # Get recent HOS records
        cutoff = get_current_timestamp() - timedelta(days=8)  # Look back 8 days
        
        result = await self.db_session.execute(
            select(DriverHOSRecordModel)
            .where(
                and_(
                    DriverHOSRecordModel.driver_id == driver_id,
                    DriverHOSRecordModel.tenant_id == tenant_id,
                    DriverHOSRecordModel.created_at >= cutoff
                )
            )
            .order_by(desc(DriverHOSRecordModel.created_at))
        )
        
        records = result.scalars().all()
        
        # Calculate duty and drive hours
        current_duty_hours = 0.0
        current_drive_hours = 0.0
        
        for record in records:
            if record.event_type in [HOSEventType.DUTY_ON.value, HOSEventType.DRIVE_START.value]:
                if record.duration_minutes:
                    if record.event_type == HOSEventType.DRIVE_START.value:
                        current_drive_hours += record.duration_minutes / 60
                    current_duty_hours += record.duration_minutes / 60
            elif record.event_type in [HOSEventType.DUTY_OFF.value, HOSEventType.DRIVE_END.value]:
                if record.duration_minutes:
                    if record.event_type == HOSEventType.DRIVE_END.value:
                        current_drive_hours -= record.duration_minutes / 60
                    current_duty_hours -= record.duration_minutes / 60
        
        # Calculate remaining hours
        remaining_duty_hours = max(0, self.config.max_duty_hours - current_duty_hours)
        remaining_drive_hours = max(0, self.config.max_drive_hours - current_drive_hours)
        
        # Determine status
        if current_duty_hours >= self.config.max_duty_hours or current_drive_hours >= self.config.max_drive_hours:
            status = HOSStatus.VIOLATION
        elif remaining_duty_hours < 2 or remaining_drive_hours < 2:
            status = HOSStatus.WARNING
        else:
            status = HOSStatus.OK
        
        return HOSStatus(
            current_duty_hours=round(current_duty_hours, 2),
            current_drive_hours=round(current_drive_hours, 2),
            remaining_duty_hours=round(remaining_duty_hours, 2),
            remaining_drive_hours=round(remaining_drive_hours, 2),
            last_reset=get_current_timestamp(),
            status=status
        )
    
    # ========================================================================
    # Vehicle Operations
    # ========================================================================
    
    async def create_vehicle(
        self,
        vehicle_data: VehicleCreate,
        tenant_id: str
    ) -> Tuple[Vehicle, Optional[AgentTask]]:
        """
        Create a new vehicle.
        
        Args:
            vehicle_data: Vehicle data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created vehicle, agent task if approval required)
        """
        # Vehicles are typically auto-executed as they're just data entry
        agent_task: Optional[AgentTask] = None
        
        # Create the vehicle
        vehicle_model = VehicleModel(
            id=generate_id("vehicle"),
            tenant_id=tenant_id,
            name=vehicle_data.name,
            vin=vehicle_data.vin,
            license_plate=vehicle_data.license_plate,
            vehicle_type=vehicle_data.vehicle_type,
            status=vehicle_data.status,
            home_warehouse_id=vehicle_data.home_warehouse_id,
            capacity_cubic_feet=vehicle_data.capacity_cubic_feet,
            capacity_weight_lbs=vehicle_data.capacity_weight_lbs,
            fuel_type=vehicle_data.fuel_type,
            fuel_efficiency_mpg=vehicle_data.fuel_efficiency_mpg,
            odometer=vehicle_data.odometer,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(vehicle_model)
        await self.db_session.commit()
        await self.db_session.refresh(vehicle_model)
        
        # Convert to schema
        vehicle = await self._vehicle_model_to_schema(vehicle_model)
        
        return vehicle, agent_task
    
    async def get_vehicle(self, vehicle_id: str, tenant_id: str) -> Optional[Vehicle]:
        """Get a vehicle by ID."""
        result = await self.db_session.execute(
            select(VehicleModel)
            .where(
                and_(
                    VehicleModel.id == vehicle_id,
                    VehicleModel.tenant_id == tenant_id
                )
            )
        )
        
        vehicle_model = result.scalar_one_or_none()
        if not vehicle_model:
            return None
        
        return await self._vehicle_model_to_schema(vehicle_model)
    
    async def list_vehicles(
        self,
        tenant_id: str,
        status: Optional[VehicleStatus] = None,
        warehouse_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Vehicle], int]:
        """List vehicles with optional filters."""
        query = select(VehicleModel).where(VehicleModel.tenant_id == tenant_id)
        
        if status:
            query = query.where(VehicleModel.status == status)
        if warehouse_id:
            query = query.where(VehicleModel.home_warehouse_id == warehouse_id)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db_session.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(desc(VehicleModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        vehicle_models = result.scalars().all()
        
        vehicles = [await self._vehicle_model_to_schema(model) for model in vehicle_models]
        
        return vehicles, total
    
    async def update_vehicle(
        self,
        vehicle_id: str,
        vehicle_data: VehicleUpdate,
        tenant_id: str
    ) -> Tuple[Optional[Vehicle], Optional[AgentTask]]:
        """
        Update a vehicle.
        
        Returns:
            Tuple of (updated vehicle, agent task if approval required)
        """
        # Get existing vehicle
        result = await self.db_session.execute(
            select(VehicleModel)
            .where(
                and_(
                    VehicleModel.id == vehicle_id,
                    VehicleModel.tenant_id == tenant_id
                )
            )
        )
        
        vehicle_model = result.scalar_one_or_none()
        if not vehicle_model:
            return None, None
        
        # Update fields
        if vehicle_data.name:
            vehicle_model.name = vehicle_data.name
        if vehicle_data.vin:
            vehicle_model.vin = vehicle_data.vin
        if vehicle_data.license_plate:
            vehicle_model.license_plate = vehicle_data.license_plate
        if vehicle_data.vehicle_type:
            vehicle_model.vehicle_type = vehicle_data.vehicle_type
        if vehicle_data.status:
            vehicle_model.status = vehicle_data.status
        if vehicle_data.home_warehouse_id:
            vehicle_model.home_warehouse_id = vehicle_data.home_warehouse_id
        if vehicle_data.capacity_cubic_feet:
            vehicle_model.capacity_cubic_feet = vehicle_data.capacity_cubic_feet
        if vehicle_data.capacity_weight_lbs:
            vehicle_model.capacity_weight_lbs = vehicle_data.capacity_weight_lbs
        if vehicle_data.fuel_type:
            vehicle_model.fuel_type = vehicle_data.fuel_type
        if vehicle_data.fuel_efficiency_mpg:
            vehicle_model.fuel_efficiency_mpg = vehicle_data.fuel_efficiency_mpg
        if vehicle_data.odometer:
            vehicle_model.odometer = vehicle_data.odometer
        
        vehicle_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(vehicle_model)
        
        vehicle = await self._vehicle_model_to_schema(vehicle_model)
        return vehicle, None
    
    async def delete_vehicle(self, vehicle_id: str, tenant_id: str) -> bool:
        """Delete a vehicle."""
        result = await self.db_session.execute(
            select(VehicleModel)
            .where(
                and_(
                    VehicleModel.id == vehicle_id,
                    VehicleModel.tenant_id == tenant_id
                )
            )
        )
        
        vehicle_model = result.scalar_one_or_none()
        if not vehicle_model:
            return False
        
        await self.db_session.delete(vehicle_model)
        await self.db_session.commit()
        
        return True
    
    # ========================================================================
    # Maintenance Operations
    # ========================================================================
    
    async def log_maintenance(
        self,
        vehicle_id: str,
        maintenance_data: MaintenanceRecordCreate,
        tenant_id: str
    ) -> Tuple[MaintenanceRecord, Optional[AgentTask]]:
        """
        Log a maintenance event for a vehicle.
        
        Args:
            vehicle_id: Vehicle ID
            maintenance_data: Maintenance data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created maintenance record, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="log_maintenance",
                input_data={"vehicle_id": vehicle_id, **maintenance_data.model_dump()},
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_id=vehicle_id,
                related_entity_type="vehicle"
            )
        
        # Create maintenance record
        maintenance_model = VehicleMaintenanceModel(
            id=generate_id("maint"),
            vehicle_id=vehicle_id,
            tenant_id=tenant_id,
            maintenance_type=maintenance_data.maintenance_type.value,
            description=maintenance_data.description,
            odometer=maintenance_data.odometer,
            cost=maintenance_data.cost,
            next_service_due_miles=maintenance_data.next_service_due_miles,
            next_service_due_date=maintenance_data.next_service_due_date,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(maintenance_model)
        await self.db_session.commit()
        await self.db_session.refresh(maintenance_model)
        
        # If auto-execute
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Convert to schema
        maintenance = await self._maintenance_model_to_schema(maintenance_model)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.FLEET_VEHICLE_MAINTENANCE_LOGGED,
            data={
                "vehicle_id": vehicle_id,
                "maintenance_id": maintenance.id,
                "maintenance_type": maintenance_data.maintenance_type.value
            },
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return maintenance, agent_task
    
    # ========================================================================
    # HOS Compliance Check
    # ========================================================================
    
    async def check_hos_compliance(
        self,
        driver_id: str,
        request: HOSComplianceCheckRequest,
        tenant_id: str
    ) -> Tuple[HOSComplianceCheckResponse, Optional[AgentTask]]:
        """
        Check HOS compliance for a driver for a potential route assignment.
        
        Args:
            driver_id: Driver ID
            request: Compliance check request
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (compliance check response, agent task if created)
        """
        # HOS compliance checks are always auto-executed per trust level rules
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="check_hos_compliance",
            input_data={"driver_id": driver_id, **request.model_dump()},
            status=AgentTaskStatus.AUTO_EXECUTED,
            related_entity_id=driver_id,
            related_entity_type="driver"
        )
        
        # Get current HOS status
        hos_status = await self._calculate_hos_status(driver_id, tenant_id)
        
        # Check if the route duration would cause a violation
        estimated_hours = request.estimated_duration_minutes / 60
        remaining_after = hos_status.remaining_drive_hours - estimated_hours
        
        compliant = remaining_after >= 0
        
        # Generate warnings
        warnings = []
        if remaining_after < 2:
            warnings.append(f"Only {remaining_after:.1f} hours remaining after route")
        if hos_status.status == HOSStatus.WARNING:
            warnings.append("Driver currently has HOS warning")
        
        response = HOSComplianceCheckResponse(
            driver_id=driver_id,
            route_id=request.route_id,
            compliant=compliant,
            remaining_hours_after=round(remaining_after, 2),
            warnings=warnings,
            agent_task_id=agent_task.id
        )
        
        # Emit webhook event if not compliant
        if not compliant:
            await self._emit_webhook_event(
                tenant_id=tenant_id,
                event_type=WebhookEventType.FLEET_HOS_VIOLATION,
                data={
                    "driver_id": driver_id,
                    "route_id": request.route_id,
                    "remaining_hours": remaining_after
                },
                agent_task_id=agent_task.id
            )
        
        return response, agent_task
    
    # ========================================================================
    # Driver-Vehicle Assignment
    # ========================================================================
    
    async def assign_driver_to_vehicle(
        self,
        driver_id: str,
        assignment: DriverVehicleAssignment,
        tenant_id: str
    ) -> Tuple[DriverVehicleAssignmentResponse, Optional[AgentTask]]:
        """
        Assign a driver to a vehicle.
        
        Args:
            driver_id: Driver ID
            assignment: Assignment data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (assignment response, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="assign_driver_to_vehicle",
                input_data={"driver_id": driver_id, **assignment.model_dump()},
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_id=driver_id,
                related_entity_type="driver"
            )
        
        # Update driver
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.id == driver_id,
                    DriverModel.tenant_id == tenant_id
                )
            )
        )
        
        driver_model = result.scalar_one_or_none()
        if not driver_model:
            return DriverVehicleAssignmentResponse(
                driver_id=driver_id,
                vehicle_id=assignment.vehicle_id,
                route_id=assignment.route_id,
                assigned=False
            ), agent_task
        
        driver_model.current_vehicle_id = assignment.vehicle_id
        if assignment.route_id:
            driver_model.assigned_route_id = assignment.route_id
        driver_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        
        # If auto-execute
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.FLEET_DRIVER_ASSIGNED,
            data={
                "driver_id": driver_id,
                "vehicle_id": assignment.vehicle_id,
                "route_id": assignment.route_id
            },
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return DriverVehicleAssignmentResponse(
            driver_id=driver_id,
            vehicle_id=assignment.vehicle_id,
            route_id=assignment.route_id,
            assigned=True,
            agent_task_id=agent_task.id if agent_task else None
        ), agent_task
    
    # ========================================================================
    # Compliance Alerts
    # ========================================================================
    
    async def get_compliance_alerts(self, tenant_id: str) -> ComplianceAlertListResponse:
        """Get all compliance alerts for a tenant."""
        # In a real implementation, this would query the alerts table
        # For now, we'll generate alerts based on current state
        
        alerts = []
        
        # Check for HOS violations
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.tenant_id == tenant_id,
                    DriverModel.hos_status["status"] == HOSStatus.VIOLATION.value
                )
            )
        )
        
        for driver_model in result.scalars().all():
            alerts.append(ComplianceAlert(
                id=generate_id("alert"),
                type=AlertType.HOS_VIOLATION,
                severity=AlertSeverity.HIGH,
                entity_type="driver",
                entity_id=driver_model.id,
                description=f"Driver {driver_model.name} has HOS violation",
                timestamp=get_current_timestamp(),
                acknowledged=False
            ))
        
        # Check for maintenance overdue
        result = await self.db_session.execute(
            select(VehicleMaintenanceModel)
            .where(
                and_(
                    VehicleMaintenanceModel.tenant_id == tenant_id,
                    VehicleMaintenanceModel.next_service_due_date < date.today()
                )
            )
        )
        
        for maint_model in result.scalars().all():
            alerts.append(ComplianceAlert(
                id=generate_id("alert"),
                type=AlertType.MAINTENANCE_OVERDUE,
                severity=AlertSeverity.MEDIUM,
                entity_type="vehicle",
                entity_id=maint_model.vehicle_id,
                description=f"Vehicle maintenance overdue",
                timestamp=get_current_timestamp(),
                acknowledged=False
            ))
        
        # Check for license expiry
        result = await self.db_session.execute(
            select(DriverModel)
            .where(
                and_(
                    DriverModel.tenant_id == tenant_id,
                    DriverModel.license_expiry < date.today() + timedelta(days=self.config.license_warning_days),
                    DriverModel.license_expiry >= date.today()
                )
            )
        )
        
        for driver_model in result.scalars().all():
            alerts.append(ComplianceAlert(
                id=generate_id("alert"),
                type=AlertType.LICENSE_EXPIRY,
                severity=AlertSeverity.MEDIUM,
                entity_type="driver",
                entity_id=driver_model.id,
                description=f"Driver {driver_model.name} license expiring soon",
                timestamp=get_current_timestamp(),
                acknowledged=False
            ))
        
        return ComplianceAlertListResponse(alerts=alerts)
    
    # ========================================================================
    # Configuration
    # ========================================================================
    
    async def get_config(self, tenant_id: str) -> FleetManagementConfig:
        """Get the current configuration."""
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> FleetManagementConfig:
        """Update the configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.config
    
    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get fleet management statistics."""
        # Count drivers by status
        result = await self.db_session.execute(
            select(
                DriverModel.status,
                func.count(DriverModel.id)
            )
            .where(DriverModel.tenant_id == tenant_id)
            .group_by(DriverModel.status)
        )
        
        driver_status_counts = {row[0]: row[1] for row in result.all()}
        
        # Count vehicles by status
        result = await self.db_session.execute(
            select(
                VehicleModel.status,
                func.count(VehicleModel.id)
            )
            .where(VehicleModel.tenant_id == tenant_id)
            .group_by(VehicleModel.status)
        )
        
        vehicle_status_counts = {row[0]: row[1] for row in result.all()}
        
        # Count HOS violations
        result = await self.db_session.execute(
            select(func.count(DriverModel.id))
            .where(
                and_(
                    DriverModel.tenant_id == tenant_id,
                    DriverModel.hos_status["status"] == HOSStatus.VIOLATION.value
                )
            )
        )
        hos_violations = result.scalar() or 0
        
        # Count maintenance overdue
        result = await self.db_session.execute(
            select(func.count(VehicleMaintenanceModel.id))
            .where(
                and_(
                    VehicleMaintenanceModel.tenant_id == tenant_id,
                    VehicleMaintenanceModel.next_service_due_date < date.today()
                )
            )
        )
        maintenance_overdue = result.scalar() or 0
        
        # Count license expiring soon
        result = await self.db_session.execute(
            select(func.count(DriverModel.id))
            .where(
                and_(
                    DriverModel.tenant_id == tenant_id,
                    DriverModel.license_expiry < date.today() + timedelta(days=self.config.license_warning_days),
                    DriverModel.license_expiry >= date.today()
                )
            )
        )
        license_expiring_soon = result.scalar() or 0
        
        return {
            "total_drivers": driver_status_counts.get(DriverStatus.ACTIVE, 0) +
                          driver_status_counts.get(DriverStatus.INACTIVE, 0) +
                          driver_status_counts.get(DriverStatus.ON_LEAVE, 0),
            "active_drivers": driver_status_counts.get(DriverStatus.ACTIVE, 0),
            "total_vehicles": vehicle_status_counts.get(VehicleStatus.ACTIVE, 0) +
                           vehicle_status_counts.get(VehicleStatus.INACTIVE, 0) +
                           vehicle_status_counts.get(VehicleStatus.MAINTENANCE, 0),
            "active_vehicles": vehicle_status_counts.get(VehicleStatus.ACTIVE, 0),
            "vehicles_in_maintenance": vehicle_status_counts.get(VehicleStatus.MAINTENANCE, 0),
            "hos_violations": int(hos_violations),
            "maintenance_overdue": int(maintenance_overdue),
            "license_expiring_soon": int(license_expiring_soon)
        }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _driver_model_to_schema(self, model: DriverModel) -> Driver:
        """Convert DriverModel to Driver schema."""
        # Parse HOS status
        hos_status_data = model.hos_status if isinstance(model.hos_status, dict) else {}
        hos_status = HOSStatus(
            current_duty_hours=hos_status_data.get("current_duty_hours", 0.0),
            current_drive_hours=hos_status_data.get("current_drive_hours", 0.0),
            remaining_duty_hours=hos_status_data.get("remaining_duty_hours", 0.0),
            remaining_drive_hours=hos_status_data.get("remaining_drive_hours", 0.0),
            last_reset=hos_status_data.get("last_reset"),
            status=hos_status_data.get("status", HOSStatus.OK)
        )
        
        return Driver(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            license_number=model.license_number,
            license_state=model.license_state,
            license_expiry=model.license_expiry,
            status=model.status,
            home_warehouse_id=model.home_warehouse_id,
            skills=model.skills or [],
            phone=model.phone,
            email=model.email,
            hos_status=hos_status,
            assigned_route_id=model.assigned_route_id,
            current_vehicle_id=model.current_vehicle_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    async def _vehicle_model_to_schema(self, model: VehicleModel) -> Vehicle:
        """Convert VehicleModel to Vehicle schema."""
        # Parse maintenance status
        maint_status_data = model.maintenance_status if isinstance(model.maintenance_status, dict) else {}
        maintenance_status = MaintenanceStatus(
            last_service=maint_status_data.get("last_service"),
            next_service_due=maint_status_data.get("next_service_due"),
            next_service_miles=maint_status_data.get("next_service_miles"),
            status=maint_status_data.get("status", MaintenanceStatus.OK)
        )
        
        # Parse telematics
        telematics_data = model.telematics if isinstance(model.telematics, dict) else {}
        telematics = TelematicsData(
            device_id=telematics_data.get("device_id"),
            last_location=Location(
                lat=telematics_data.get("last_location", {}).get("lat", 0.0),
                lng=telematics_data.get("last_location", {}).get("lng", 0.0)
            ) if telematics_data.get("last_location") else None,
            last_update=telematics_data.get("last_update"),
            speed_mph=telematics_data.get("speed_mph"),
            engine_hours=telematics_data.get("engine_hours")
        )
        
        return Vehicle(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            vin=model.vin,
            license_plate=model.license_plate,
            vehicle_type=model.vehicle_type,
            status=model.status,
            home_warehouse_id=model.home_warehouse_id,
            capacity_cubic_feet=model.capacity_cubic_feet,
            capacity_weight_lbs=model.capacity_weight_lbs,
            fuel_type=model.fuel_type,
            fuel_efficiency_mpg=model.fuel_efficiency_mpg,
            odometer=model.odometer,
            maintenance_status=maintenance_status,
            telematics=telematics,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    async def _maintenance_model_to_schema(self, model: VehicleMaintenanceModel) -> MaintenanceRecord:
        """Convert VehicleMaintenanceModel to MaintenanceRecord schema."""
        return MaintenanceRecord(
            id=model.id,
            vehicle_id=model.vehicle_id,
            tenant_id=model.tenant_id,
            maintenance_type=MaintenanceType(model.maintenance_type),
            description=model.description,
            odometer=model.odometer,
            cost=model.cost,
            next_service_due_miles=model.next_service_due_miles,
            next_service_due_date=model.next_service_due_date,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    async def _create_agent_task(
        self,
        tenant_id: str,
        action_type: str,
        input_data: Dict[str, Any],
        status: AgentTaskStatus = AgentTaskStatus.PENDING_APPROVAL,
        reasoning_trace: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        related_entity_type: Optional[str] = None
    ) -> AgentTask:
        """Create an AgentTask record."""
        reasoning_trace = reasoning_trace or f"Fleet Management Agent: {action_type}"
        
        task_model = AgentTaskModel(
            id=generate_id("task"),
            tenant_id=tenant_id,
            agent_type=AgentType.FLEET_MANAGEMENT,
            action_type=action_type,
            status=status,
            trust_level=self.config.trust_level,
            reasoning_trace=reasoning_trace,
            input_data=input_data,
            related_entity_id=related_entity_id,
            related_entity_type=related_entity_type,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(task_model)
        await self.db_session.commit()
        await self.db_session.refresh(task_model)
        
        return AgentTask(
            id=task_model.id,
            tenant_id=task_model.tenant_id,
            agent_type=task_model.agent_type,
            action_type=task_model.action_type,
            status=task_model.status,
            trust_level=task_model.trust_level,
            reasoning_trace=task_model.reasoning_trace,
            input_data=task_model.input_data,
            related_entity_id=task_model.related_entity_id,
            related_entity_type=task_model.related_entity_type,
            created_at=task_model.created_at,
            updated_at=task_model.updated_at
        )
    
    async def _update_agent_task(self, task: AgentTask) -> None:
        """Update an AgentTask record."""
        result = await self.db_session.execute(
            select(AgentTaskModel)
            .where(AgentTaskModel.id == task.id)
        )
        
        task_model = result.scalar_one_or_none()
        if task_model:
            task_model.status = task.status
            task_model.completed_at = task.completed_at
            task_model.output_data = task.output_data
            task_model.error_message = task.error_message
            task_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
    
    async def _emit_webhook_event(
        self,
        tenant_id: str,
        event_type: WebhookEventType,
        data: Dict[str, Any],
        agent_task_id: Optional[str] = None
    ) -> None:
        """Emit a webhook event."""
        logger.info(f"Webhook event: {event_type.value} for tenant {tenant_id}")
