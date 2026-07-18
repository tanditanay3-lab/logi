"""
Service layer for the Warehouse Operations Agent.

This service handles all business logic for warehouse operations including:
- Task management (create, update, list)
- Task optimization and sequencing
- Dock scheduling
- Labor forecasting
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.db.models import (
    AgentTask as AgentTaskModel,
    DockSchedule as DockScheduleModel,
    DockSlot as DockSlotModel,
    Tenant,
    User,
    Warehouse as WarehouseModel,
    WarehouseTask as WarehouseTaskModel,
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

from .config import WarehouseOpsConfig
from .schemas import (
    DockSchedule,
    DockScheduleCreate,
    DockScheduleListResponse,
    DockSlot,
    DockSlotStatus,
    LaborForecastEntry,
    LaborForecastRequest,
    LaborForecastResponse,
    OptimizedTaskAssignment,
    TaskOptimizationRequest,
    TaskOptimizationResponse,
    WarehouseTask,
    WarehouseTaskCreate,
    WarehouseTaskListResponse,
    WarehouseTaskPriority,
    WarehouseTaskStatus,
    WarehouseTaskType,
    WarehouseTaskUpdate,
    WorkerInfo,
)

logger = logging.getLogger(__name__)


class WarehouseOpsService:
    """
    Service for managing warehouse operations.
    
    This service handles:
    - Creating and managing warehouse tasks
    - Optimizing task sequencing and assignment
    - Managing dock schedules
    - Generating labor forecasts
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: WarehouseOpsConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        logger.info("Warehouse Operations Service initialized")
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
        logger.info("Warehouse Operations Service closed")
    
    # ========================================================================
    # Warehouse Task Operations
    # ========================================================================
    
    async def create_task(
        self,
        task_data: WarehouseTaskCreate,
        tenant_id: str
    ) -> Tuple[WarehouseTask, Optional[AgentTask]]:
        """
        Create a new warehouse task.
        
        Args:
            task_data: Task data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created task, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level for approval
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="create_warehouse_task",
                input_data=task_data.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_type="warehouse_task"
            )
        
        # Create the task
        task_model = WarehouseTaskModel(
            id=generate_id("task"),
            tenant_id=tenant_id,
            warehouse_id=task_data.warehouse_id,
            task_type=task_data.task_type,
            priority=task_data.priority,
            description=task_data.description,
            location=task_data.location,
            order_id=task_data.order_id,
            shipment_id=task_data.shipment_id,
            inventory_item_id=task_data.inventory_item_id,
            quantity=task_data.quantity,
            estimated_duration_minutes=task_data.estimated_duration_minutes,
            due_at=task_data.due_at,
            status=WarehouseTaskStatus.PENDING,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(task_model)
        await self.db_session.commit()
        await self.db_session.refresh(task_model)
        
        # If auto-execute, mark task as auto-executed
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Convert to schema
        task = await self._model_to_schema(task_model)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.WAREHOUSE_TASK_CREATED,
            data={"task_id": task.id, "task_type": task.task_type},
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return task, agent_task
    
    async def get_task(self, task_id: str, tenant_id: str) -> Optional[WarehouseTask]:
        """Get a warehouse task by ID."""
        result = await self.db_session.execute(
            select(WarehouseTaskModel)
            .where(
                and_(
                    WarehouseTaskModel.id == task_id,
                    WarehouseTaskModel.tenant_id == tenant_id
                )
            )
        )
        
        task_model = result.scalar_one_or_none()
        if not task_model:
            return None
        
        return await self._model_to_schema(task_model)
    
    async def list_tasks(
        self,
        tenant_id: str,
        warehouse_id: Optional[str] = None,
        status: Optional[WarehouseTaskStatus] = None,
        task_type: Optional[WarehouseTaskType] = None,
        priority: Optional[WarehouseTaskPriority] = None,
        assigned_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[WarehouseTask], int]:
        """List warehouse tasks with optional filters."""
        query = select(WarehouseTaskModel).where(WarehouseTaskModel.tenant_id == tenant_id)
        
        if warehouse_id:
            query = query.where(WarehouseTaskModel.warehouse_id == warehouse_id)
        if status:
            query = query.where(WarehouseTaskModel.status == status)
        if task_type:
            query = query.where(WarehouseTaskModel.task_type == task_type)
        if priority:
            query = query.where(WarehouseTaskModel.priority == priority)
        if assigned_to:
            query = query.where(WarehouseTaskModel.assigned_to == assigned_to)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db_session.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(desc(WarehouseTaskModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        task_models = result.scalars().all()
        
        tasks = [await self._model_to_schema(model) for model in task_models]
        
        return tasks, total
    
    async def update_task(
        self,
        task_id: str,
        task_data: WarehouseTaskUpdate,
        tenant_id: str
    ) -> Tuple[Optional[WarehouseTask], Optional[AgentTask]]:
        """
        Update a warehouse task.
        
        Returns:
            Tuple of (updated task, agent task if approval required)
        """
        # Get existing task
        result = await self.db_session.execute(
            select(WarehouseTaskModel)
            .where(
                and_(
                    WarehouseTaskModel.id == task_id,
                    WarehouseTaskModel.tenant_id == tenant_id
                )
            )
        )
        
        task_model = result.scalar_one_or_none()
        if not task_model:
            return None, None
        
        agent_task: Optional[AgentTask] = None
        
        # Check if assignment requires approval
        if task_data.assigned_to and self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="assign_warehouse_task",
                input_data={
                    "task_id": task_id,
                    "assigned_to": task_data.assigned_to
                },
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_id=task_id,
                related_entity_type="warehouse_task"
            )
        
        # Update fields
        if task_data.status:
            task_model.status = task_data.status
        if task_data.assigned_to:
            task_model.assigned_to = task_data.assigned_to
        if task_data.priority:
            task_model.priority = task_data.priority
        if task_data.description:
            task_model.description = task_data.description
        if task_data.location:
            task_model.location = task_data.location
        if task_data.due_at:
            task_model.due_at = task_data.due_at
        if task_data.actual_duration_minutes:
            task_model.actual_duration_minutes = task_data.actual_duration_minutes
        
        task_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(task_model)
        
        # If auto-execute for assignment
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Emit webhook event
        if task_data.assigned_to:
            await self._emit_webhook_event(
                tenant_id=tenant_id,
                event_type=WebhookEventType.WAREHOUSE_TASK_ASSIGNED,
                data={"task_id": task_id, "assigned_to": task_data.assigned_to},
                agent_task_id=agent_task.id if agent_task else None
            )
        
        if task_data.status == WarehouseTaskStatus.COMPLETED:
            await self._emit_webhook_event(
                tenant_id=tenant_id,
                event_type=WebhookEventType.WAREHOUSE_TASK_COMPLETED,
                data={"task_id": task_id},
                agent_task_id=agent_task.id if agent_task else None
            )
        
        task = await self._model_to_schema(task_model)
        return task, agent_task
    
    async def delete_task(self, task_id: str, tenant_id: str) -> bool:
        """Delete a warehouse task."""
        result = await self.db_session.execute(
            select(WarehouseTaskModel)
            .where(
                and_(
                    WarehouseTaskModel.id == task_id,
                    WarehouseTaskModel.tenant_id == tenant_id
                )
            )
        )
        
        task_model = result.scalar_one_or_none()
        if not task_model:
            return False
        
        await self.db_session.delete(task_model)
        await self.db_session.commit()
        
        return True
    
    # ========================================================================
    # Task Optimization
    # ========================================================================
    
    async def optimize_tasks(
        self,
        request: TaskOptimizationRequest,
        tenant_id: str
    ) -> Tuple[TaskOptimizationResponse, Optional[AgentTask]]:
        """
        Optimize task sequencing for a warehouse.
        
        Args:
            request: Optimization request
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (optimization response, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="optimize_warehouse_tasks",
                input_data=request.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_type="warehouse_optimization"
            )
        
        # Get tasks from database
        result = await self.db_session.execute(
            select(WarehouseTaskModel)
            .where(
                and_(
                    WarehouseTaskModel.tenant_id == tenant_id,
                    WarehouseTaskModel.warehouse_id == request.warehouse_id,
                    WarehouseTaskModel.id.in_(request.task_ids)
                )
            )
        )
        
        task_models = result.scalars().all()
        
        # Simple optimization algorithm
        optimized_sequence = await self._optimize_task_sequence(
            tasks=task_models,
            workers=request.workers,
            constraints=request.constraints
        )
        
        # If auto-execute
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        response = TaskOptimizationResponse(
            optimized_sequence=optimized_sequence,
            unassigned_tasks=[],
            agent_task_id=agent_task.id if agent_task else None
        )
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.WAREHOUSE_TASKS_OPTIMIZED,
            data={
                "warehouse_id": request.warehouse_id,
                "task_count": len(request.task_ids),
                "optimized_count": len(optimized_sequence)
            },
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return response, agent_task
    
    async def _optimize_task_sequence(
        self,
        tasks: List[WarehouseTaskModel],
        workers: List[WorkerInfo],
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[OptimizedTaskAssignment]:
        """
        Optimize task sequence using a simple algorithm.
        
        This is a placeholder for a more sophisticated optimization algorithm.
        In production, this would use a proper optimization library.
        """
        constraints = constraints or {}
        max_tasks_per_worker = constraints.get("max_tasks_per_worker", self.config.max_tasks_per_worker)
        balance_workload = constraints.get("balance_workload", self.config.balance_workload)
        prioritize_by_due = constraints.get("prioritize_by_due", self.config.prioritize_by_due)
        
        # Sort tasks by priority and due date
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                self._priority_to_int(t.priority),
                t.due_at or datetime.max
            )
        )
        
        # Simple round-robin assignment
        optimized_sequence = []
        worker_index = 0
        task_count = 0
        
        for task in sorted_tasks:
            # Check if we've reached max tasks per worker
            if balance_workload and worker_index < len(workers):
                assigned_worker = workers[worker_index % len(workers)]
                worker_index += 1
            else:
                assigned_worker = None
            
            optimized_sequence.append(OptimizedTaskAssignment(
                task_id=task.id,
                sequence=task_count,
                assigned_to=assigned_worker.user_id if assigned_worker else None,
                start_time=None
            ))
            task_count += 1
            
            # Reset worker index if we've assigned to all workers
            if worker_index >= len(workers):
                worker_index = 0
        
        return optimized_sequence
    
    def _priority_to_int(self, priority: WarehouseTaskPriority) -> int:
        """Convert priority to integer for sorting."""
        priority_map = {
            WarehouseTaskPriority.CRITICAL: 0,
            WarehouseTaskPriority.HIGH: 1,
            WarehouseTaskPriority.MEDIUM: 2,
            WarehouseTaskPriority.LOW: 3
        }
        return priority_map.get(priority, 2)
    
    # ========================================================================
    # Dock Schedule Operations
    # ========================================================================
    
    async def get_dock_schedule(
        self,
        warehouse_id: Optional[str] = None,
        date: Optional[date] = None,
        tenant_id: str
    ) -> DockScheduleListResponse:
        """Get dock schedules with optional filters."""
        query = select(DockScheduleModel).where(DockScheduleModel.tenant_id == tenant_id)
        
        if warehouse_id:
            query = query.where(DockScheduleModel.warehouse_id == warehouse_id)
        if date:
            query = query.where(DockScheduleModel.date == date)
        
        result = await self.db_session.execute(
            query
            .order_by(DockScheduleModel.date, DockScheduleModel.dock_number)
        )
        
        schedule_models = result.scalars().all()
        schedules = [await self._dock_schedule_model_to_schema(model) for model in schedule_models]
        
        return DockScheduleListResponse(
            schedules=schedules,
            total=len(schedules),
            limit=100,
            offset=0
        )
    
    async def create_dock_schedule(
        self,
        schedule_data: DockScheduleCreate,
        tenant_id: str
    ) -> Tuple[DockSchedule, Optional[AgentTask]]:
        """
        Create a new dock schedule.
        
        Returns:
            Tuple of (created schedule, agent task if approval required)
        """
        agent_task: Optional[AgentTask] = None
        
        # Check trust level
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="create_dock_schedule",
                input_data=schedule_data.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL,
                related_entity_type="dock_schedule"
            )
        
        # Create the schedule
        schedule_model = DockScheduleModel(
            id=generate_id("dock_schedule"),
            tenant_id=tenant_id,
            warehouse_id=schedule_data.warehouse_id,
            dock_number=schedule_data.dock_number,
            date=schedule_data.date,
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(schedule_model)
        await self.db_session.commit()
        await self.db_session.refresh(schedule_model)
        
        # Create slots
        for slot_data in schedule_data.slots:
            slot_model = DockSlotModel(
                id=generate_id("dock_slot"),
                dock_schedule_id=schedule_model.id,
                start_time=slot_data.start_time,
                end_time=slot_data.end_time,
                status=slot_data.status,
                shipment_id=slot_data.shipment_id,
                carrier=slot_data.carrier,
                vehicle_type=slot_data.vehicle_type,
                notes=slot_data.notes,
                created_at=get_current_timestamp(),
                updated_at=get_current_timestamp()
            )
            self.db_session.add(slot_model)
        
        await self.db_session.commit()
        
        # If auto-execute
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        schedule = await self._dock_schedule_model_to_schema(schedule_model)
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.WAREHOUSE_DOCK_SCHEDULE_UPDATED,
            data={"schedule_id": schedule.id, "warehouse_id": schedule.warehouse_id},
            agent_task_id=agent_task.id if agent_task else None
        )
        
        return schedule, agent_task
    
    async def _dock_schedule_model_to_schema(self, model: DockScheduleModel) -> DockSchedule:
        """Convert DockScheduleModel to DockSchedule schema."""
        # Get slots
        result = await self.db_session.execute(
            select(DockSlotModel)
            .where(DockSlotModel.dock_schedule_id == model.id)
            .order_by(DockSlotModel.start_time)
        )
        slot_models = result.scalars().all()
        
        slots = [
            DockSlot(
                id=slot.id,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status=slot.status,
                shipment_id=slot.shipment_id,
                carrier=slot.carrier,
                vehicle_type=slot.vehicle_type,
                notes=slot.notes
            )
            for slot in slot_models
        ]
        
        return DockSchedule(
            id=model.id,
            warehouse_id=model.warehouse_id,
            dock_number=model.dock_number,
            date=model.date,
            slots=slots
        )
    
    # ========================================================================
    # Labor Forecasting
    # ========================================================================
    
    async def generate_labor_forecast(
        self,
        request: LaborForecastRequest,
        tenant_id: str
    ) -> Tuple[LaborForecastResponse, Optional[AgentTask]]:
        """
        Generate labor forecast for a warehouse.
        
        Args:
            request: Forecast request
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (forecast response, agent task if created)
        """
        # Labor forecast is always auto-executed per trust level rules
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="generate_labor_forecast",
            input_data=request.model_dump(),
            status=AgentTaskStatus.AUTO_EXECUTED,
            related_entity_type="labor_forecast"
        )
        
        # Generate forecast entries for each day
        forecast_entries = []
        current_date = request.start_date
        
        while current_date <= request.end_date:
            entry = await self._generate_forecast_entry(
                warehouse_id=request.warehouse_id,
                date=current_date,
                historical_data_days=request.historical_data_days
            )
            forecast_entries.append(entry)
            current_date += timedelta(days=1)
        
        response = LaborForecastResponse(
            forecast=forecast_entries,
            agent_task_id=agent_task.id
        )
        
        # Emit webhook event
        await self._emit_webhook_event(
            tenant_id=tenant_id,
            event_type=WebhookEventType.WAREHOUSE_LABOR_FORECAST_GENERATED,
            data={
                "warehouse_id": request.warehouse_id,
                "start_date": str(request.start_date),
                "end_date": str(request.end_date),
                "forecast_days": len(forecast_entries)
            },
            agent_task_id=agent_task.id
        )
        
        return response, agent_task
    
    async def _generate_forecast_entry(
        self,
        warehouse_id: str,
        date: date,
        historical_data_days: int
    ) -> LaborForecastEntry:
        """
        Generate a single forecast entry.
        
        This is a placeholder for a real forecasting algorithm.
        In production, this would use historical data and ML models.
        """
        # Get historical task data
        end_date = date
        start_date = date - timedelta(days=historical_data_days)
        
        result = await self.db_session.execute(
            select(WarehouseTaskModel)
            .where(
                and_(
                    WarehouseTaskModel.warehouse_id == warehouse_id,
                    WarehouseTaskModel.created_at >= datetime(start_date.year, start_date.month, start_date.day),
                    WarehouseTaskModel.created_at < datetime(end_date.year, end_date.month, end_date.day + 1)
                )
            )
        )
        
        historical_tasks = result.scalars().all()
        
        # Simple average-based forecast
        avg_daily_tasks = len(historical_tasks) / max(historical_data_days, 1)
        estimated_tasks = int(avg_daily_tasks)
        
        # Estimate hours (assuming 30 minutes per task on average)
        estimated_hours = estimated_tasks * 0.5
        
        # Estimate workers (assuming 8 hours per worker per day)
        recommended_workers = max(1, int(estimated_hours / 8))
        
        # Breakdown by task type
        task_type_counts = {}
        for task in historical_tasks:
            task_type = task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type)
            task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
        
        # Calculate average by type
        by_task_type = {}
        for task_type, count in task_type_counts.items():
            by_task_type[task_type] = int(count / max(historical_data_days, 1))
        
        return LaborForecastEntry(
            date=date,
            estimated_tasks=estimated_tasks,
            estimated_hours=estimated_hours,
            recommended_workers=recommended_workers,
            by_task_type=by_task_type
        )
    
    # ========================================================================
    # Configuration
    # ========================================================================
    
    async def get_config(self, tenant_id: str) -> WarehouseOpsConfig:
        """Get the current configuration."""
        # In a real implementation, this would fetch from database
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> WarehouseOpsConfig:
        """Update the configuration."""
        # Update config fields
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        # In a real implementation, this would save to database
        return self.config
    
    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get warehouse operations statistics."""
        # Count tasks by status
        result = await self.db_session.execute(
            select(
                WarehouseTaskModel.status,
                func.count(WarehouseTaskModel.id)
            )
            .where(WarehouseTaskModel.tenant_id == tenant_id)
            .group_by(WarehouseTaskModel.status)
        )
        
        status_counts = {row[0]: row[1] for row in result.all()}
        
        # Count overdue tasks
        result = await self.db_session.execute(
            select(func.count(WarehouseTaskModel.id))
            .where(
                and_(
                    WarehouseTaskModel.tenant_id == tenant_id,
                    WarehouseTaskModel.due_at < get_current_timestamp(),
                    WarehouseTaskModel.status != WarehouseTaskStatus.COMPLETED
                )
            )
        )
        overdue_count = result.scalar() or 0
        
        # Calculate average completion time
        result = await self.db_session.execute(
            select(func.avg(WarehouseTaskModel.actual_duration_minutes))
            .where(
                and_(
                    WarehouseTaskModel.tenant_id == tenant_id,
                    WarehouseTaskModel.actual_duration_minutes.isnot(None)
                )
            )
        )
        avg_completion_time = result.scalar() or 0.0
        
        return {
            "total_tasks": status_counts.get(WarehouseTaskStatus.PENDING, 0) +
                          status_counts.get(WarehouseTaskStatus.ASSIGNED, 0) +
                          status_counts.get(WarehouseTaskStatus.IN_PROGRESS, 0) +
                          status_counts.get(WarehouseTaskStatus.COMPLETED, 0),
            "pending_tasks": status_counts.get(WarehouseTaskStatus.PENDING, 0),
            "in_progress_tasks": status_counts.get(WarehouseTaskStatus.IN_PROGRESS, 0),
            "completed_tasks": status_counts.get(WarehouseTaskStatus.COMPLETED, 0),
            "overdue_tasks": overdue_count,
            "avg_completion_time_minutes": float(avg_completion_time),
            "task_completion_rate": 0.0  # Would be calculated from historical data
        }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _model_to_schema(self, model: WarehouseTaskModel) -> WarehouseTask:
        """Convert WarehouseTaskModel to WarehouseTask schema."""
        return WarehouseTask(
            id=model.id,
            tenant_id=model.tenant_id,
            warehouse_id=model.warehouse_id,
            task_type=model.task_type,
            priority=model.priority,
            description=model.description,
            location=model.location,
            order_id=model.order_id,
            shipment_id=model.shipment_id,
            inventory_item_id=model.inventory_item_id,
            quantity=model.quantity,
            estimated_duration_minutes=model.estimated_duration_minutes,
            due_at=model.due_at,
            status=model.status,
            assigned_to=model.assigned_to,
            actual_duration_minutes=model.actual_duration_minutes,
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
        reasoning_trace = reasoning_trace or f"Warehouse Ops Agent: {action_type}"
        
        task_model = AgentTaskModel(
            id=generate_id("task"),
            tenant_id=tenant_id,
            agent_type=AgentType.WAREHOUSE_OPS,
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
        # In a real implementation, this would publish to Kafka or similar
        # For now, we'll just log it
        logger.info(f"Webhook event: {event_type.value} for tenant {tenant_id}")
        
        # Store in database or send to message queue
        # This is a placeholder for actual webhook implementation
