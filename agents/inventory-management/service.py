"""
Service layer for the Inventory Management Agent.

This service handles all business logic for inventory management.
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
    InventoryItem as InventoryItemModel,
    InventoryMovement as InventoryMovementModel,
    Tenant,
    Warehouse as WarehouseModel,
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

from .config import InventoryManagementConfig
from .schemas import (
    AdjustmentType,
    DiscrepancyReport,
    DiscrepancyResponse,
    InventoryAdjustment,
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryListResponse,
    InventoryMovement,
    InventoryPriority,
    InventoryRelease,
    InventoryReservation,
    InventoryStatus,
    InventoryStats,
    LowStockAlert,
    Location,
    MovementHistoryResponse,
    ReplenishmentRecommendation,
    ReplenishmentRequest,
)

logger = logging.getLogger(__name__)


class InventoryManagementService:
    """
    Service for managing inventory operations.
    
    This service handles:
    - Creating and updating inventory items
    - Adjusting inventory quantities
    - Reserving and releasing inventory
    - Generating replenishment recommendations
    - Detecting and reporting discrepancies
    - Monitoring low stock levels
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: InventoryManagementConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        self._low_stock_check_task: Optional[asyncio.Task] = None
        self._replenishment_check_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        
        # Start background tasks
        if self.config.low_stock_check_interval_hours > 0:
            self._low_stock_check_task = asyncio.create_task(
                self._check_low_stock_periodically()
            )
        
        if self.config.replenishment_check_interval_hours > 0:
            self._replenishment_check_task = asyncio.create_task(
                self._check_replenishment_periodically()
            )
        
    async def close(self):
        """Close the service."""
        if self._low_stock_check_task:
            self._low_stock_check_task.cancel()
            try:
                await self._low_stock_check_task
            except asyncio.CancelledError:
                pass
        
        if self._replenishment_check_task:
            self._replenishment_check_task.cancel()
            try:
                await self._replenishment_check_task
            except asyncio.CancelledError:
                pass
        
        await self.tool_client.close()
    
    # ========================================================================
    # Inventory Item CRUD Operations
    # ========================================================================
    
    async def create_inventory_item(
        self,
        item_data: InventoryItemCreate,
        tenant_id: str
    ) -> Tuple[InventoryItem, Optional[AgentTask]]:
        """
        Create a new inventory item.
        
        Args:
            item_data: Inventory item data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created item, agent task if approval required)
        """
        # Check if we need approval based on trust level
        agent_task: Optional[AgentTask] = None
        
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            # Create approval request
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="create_inventory_item",
                input_data=item_data.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        
        # Create the inventory item
        item_model = InventoryItemModel(
            id=generate_id("inventory"),
            tenant_id=tenant_id,
            sku=item_data.sku,
            name=item_data.name,
            description=item_data.description,
            category=item_data.category,
            warehouse_id=item_data.warehouse_id,
            location=item_data.location.model_dump() if item_data.location else {},
            quantity_on_hand=item_data.quantity_on_hand,
            quantity_reserved=item_data.quantity_reserved,
            reorder_point=item_data.reorder_point,
            reorder_quantity=item_data.reorder_quantity,
            unit_cost=item_data.unit_cost,
            unit_of_measure=item_data.unit_of_measure,
            low_stock_alert=False,
            expiry_date=item_data.expiry_date,
            batch_number=item_data.batch_number,
            status=item_data.status,
            metadata=item_data.metadata.model_dump() if item_data.metadata else {},
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(item_model)
        await self.db_session.commit()
        await self.db_session.refresh(item_model)
        
        # If auto-execute, mark task as completed
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Convert to schema
        item = await self._model_to_schema(item_model)
        
        return item, agent_task
    
    async def get_inventory_item(self, item_id: str, tenant_id: str) -> Optional[InventoryItem]:
        """Get an inventory item by ID."""
        result = await self.db_session.execute(
            select(InventoryItemModel)
            .where(
                and_(
                    InventoryItemModel.id == item_id,
                    InventoryItemModel.tenant_id == tenant_id
                )
            )
            .options(joinedload(InventoryItemModel.warehouse))
        )
        
        item_model = result.scalar_one_or_none()
        if not item_model:
            return None
        
        return await self._model_to_schema(item_model)
    
    async def list_inventory_items(
        self,
        tenant_id: str,
        warehouse_id: Optional[str] = None,
        sku: Optional[str] = None,
        category: Optional[str] = None,
        low_stock: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[InventoryItem], int]:
        """List inventory items with optional filters."""
        query = select(InventoryItemModel).where(InventoryItemModel.tenant_id == tenant_id)
        
        if warehouse_id:
            query = query.where(InventoryItemModel.warehouse_id == warehouse_id)
        if sku:
            query = query.where(InventoryItemModel.sku.ilike(f"%{sku}%"))
        if category:
            query = query.where(InventoryItemModel.category.ilike(f"%{category}%"))
        if low_stock is not None:
            query = query.where(InventoryItemModel.low_stock_alert == low_stock)
        
        # Count total
        count_result = await self.db_session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Get results
        query = query.order_by(desc(InventoryItemModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        item_models = result.scalars().all()
        
        items = [await self._model_to_schema(m) for m in item_models]
        
        return items, total
    
    async def update_inventory_item(
        self,
        item_id: str,
        item_data: InventoryItemUpdate,
        tenant_id: str
    ) -> Tuple[Optional[InventoryItem], Optional[AgentTask]]:
        """Update an inventory item."""
        result = await self.db_session.execute(
            select(InventoryItemModel).where(
                and_(
                    InventoryItemModel.id == item_id,
                    InventoryItemModel.tenant_id == tenant_id
                )
            )
        )
        
        item_model = result.scalar_one_or_none()
        if not item_model:
            return None, None
        
        # Check if we need approval for significant changes
        agent_task: Optional[AgentTask] = None
        
        # Update fields
        if item_data.sku is not None:
            item_model.sku = item_data.sku
        if item_data.name is not None:
            item_model.name = item_data.name
        if item_data.description is not None:
            item_model.description = item_data.description
        if item_data.category is not None:
            item_model.category = item_data.category
        if item_data.warehouse_id is not None:
            item_model.warehouse_id = item_data.warehouse_id
        if item_data.location is not None:
            item_model.location = item_data.location.model_dump()
        if item_data.reorder_point is not None:
            item_model.reorder_point = item_data.reorder_point
        if item_data.reorder_quantity is not None:
            item_model.reorder_quantity = item_data.reorder_quantity
        if item_data.unit_cost is not None:
            item_model.unit_cost = item_data.unit_cost
        if item_data.unit_of_measure is not None:
            item_model.unit_of_measure = item_data.unit_of_measure
        if item_data.low_stock_alert is not None:
            item_model.low_stock_alert = item_data.low_stock_alert
        if item_data.expiry_date is not None:
            item_model.expiry_date = item_data.expiry_date
        if item_data.batch_number is not None:
            item_model.batch_number = item_data.batch_number
        if item_data.status is not None:
            item_model.status = item_data.status
        if item_data.metadata is not None:
            item_model.metadata = item_data.metadata.model_dump()
        
        item_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(item_model)
        
        item = await self._model_to_schema(item_model)
        
        return item, agent_task
    
    async def delete_inventory_item(self, item_id: str, tenant_id: str) -> bool:
        """Delete an inventory item."""
        result = await self.db_session.execute(
            select(InventoryItemModel).where(
                and_(
                    InventoryItemModel.id == item_id,
                    InventoryItemModel.tenant_id == tenant_id
                )
            )
        )
        
        item_model = result.scalar_one_or_none()
        if not item_model:
            return False
        
        await self.db_session.delete(item_model)
        await self.db_session.commit()
        
        return True
    
    # ========================================================================
    # Inventory Adjustment Operations
    # ========================================================================
    
    async def adjust_inventory(
        self,
        item_id: str,
        adjustment_data: InventoryAdjustment,
        tenant_id: str
    ) -> Tuple[Optional[InventoryItem], Optional[AgentTask]]:
        """
        Adjust inventory quantity.
        
        Args:
            item_id: Inventory item ID
            adjustment_data: Adjustment data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (updated item, agent task if approval required)
        """
        # Get the item
        item = await self.get_inventory_item(item_id, tenant_id)
        if not item:
            return None, None
        
        # Check if approval is needed based on adjustment size
        agent_task: Optional[AgentTask] = None
        
        # Calculate percentage change
        current_quantity = item.quantity_on_hand
        adjustment_pct = abs(adjustment_data.quantity / current_quantity * 100) if current_quantity > 0 else 100
        adjustment_value = adjustment_data.quantity * item.unit_cost
        
        # Check thresholds
        needs_approval = False
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            needs_approval = True
        elif self.config.trust_level == TrustLevel.AUTO_EXECUTE_LOW_RISK:
            if adjustment_pct > self.config.max_adjustment_pct:
                needs_approval = True
            if adjustment_value > self.config.max_adjustment_value:
                needs_approval = True
        
        if needs_approval:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="adjust_inventory",
                input_data={
                    "item_id": item_id,
                    "adjustment": adjustment_data.model_dump()
                },
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        
        # Update the item
        item_model = await self.db_session.get(InventoryItemModel, item_id)
        if item_model:
            if adjustment_data.adjustment_type == AdjustmentType.RECEIPT:
                item_model.quantity_on_hand += adjustment_data.quantity
            elif adjustment_data.adjustment_type == AdjustmentType.ISSUE:
                item_model.quantity_on_hand -= adjustment_data.quantity
            elif adjustment_data.adjustment_type == AdjustmentType.ADJUSTMENT:
                item_model.quantity_on_hand += adjustment_data.quantity
            elif adjustment_data.adjustment_type == AdjustmentType.TRANSFER:
                # For transfers, we'd need to update both source and target
                item_model.quantity_on_hand -= adjustment_data.quantity
            elif adjustment_data.adjustment_type == AdjustmentType.SHRINKAGE:
                item_model.quantity_on_hand -= abs(adjustment_data.quantity)
            elif adjustment_data.adjustment_type == AdjustmentType.DAMAGE:
                item_model.quantity_on_hand -= abs(adjustment_data.quantity)
            
            # Update timestamp
            item_model.updated_at = get_current_timestamp()
            item_model.last_updated = get_current_timestamp()
            
            # Check low stock
            if item_model.quantity_on_hand <= item_model.reorder_point:
                item_model.low_stock_alert = True
            
            await self.db_session.commit()
            await self.db_session.refresh(item_model)
            
            # Create movement record
            movement_model = InventoryMovementModel(
                id=generate_id("movement"),
                inventory_item_id=item_id,
                tenant_id=tenant_id,
                adjustment_type=adjustment_data.adjustment_type.value,
                quantity=adjustment_data.quantity,
                reference=adjustment_data.reference or "",
                user_id=adjustment_data.user_id,
                notes=adjustment_data.notes,
                created_at=get_current_timestamp()
            )
            self.db_session.add(movement_model)
            await self.db_session.commit()
        
        # If auto-execute, mark task as completed
        if agent_task and not needs_approval:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Return updated item
        updated_item = await self.get_inventory_item(item_id, tenant_id)
        
        return updated_item, agent_task
    
    # ========================================================================
    # Inventory Reservation Operations
    # ========================================================================
    
    async def reserve_inventory(
        self,
        item_id: str,
        reservation_data: InventoryReservation,
        tenant_id: str
    ) -> Tuple[Optional[InventoryItem], Optional[AgentTask]]:
        """
        Reserve inventory for an order.
        
        Args:
            item_id: Inventory item ID
            reservation_data: Reservation data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (updated item, agent task if approval required)
        """
        # Get the item
        item = await self.get_inventory_item(item_id, tenant_id)
        if not item:
            return None, None
        
        # Check if we have enough quantity
        if item.quantity_available < reservation_data.quantity:
            # Not enough inventory
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="reserve_inventory",
                input_data={
                    "item_id": item_id,
                    "reservation": reservation_data.model_dump()
                },
                status=AgentTaskStatus.FAILED,
                error_message=f"Insufficient inventory. Available: {item.quantity_available}, Requested: {reservation_data.quantity}"
            )
            return item, agent_task
        
        # Check if approval is needed
        agent_task: Optional[AgentTask] = None
        
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="reserve_inventory",
                input_data={
                    "item_id": item_id,
                    "reservation": reservation_data.model_dump()
                },
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        
        # Update the item
        item_model = await self.db_session.get(InventoryItemModel, item_id)
        if item_model:
            item_model.quantity_reserved += reservation_data.quantity
            item_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
            await self.db_session.refresh(item_model)
        
        # If auto-execute, mark task as completed
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Return updated item
        updated_item = await self.get_inventory_item(item_id, tenant_id)
        
        return updated_item, agent_task
    
    async def release_inventory(
        self,
        item_id: str,
        release_data: InventoryRelease,
        tenant_id: str
    ) -> Tuple[Optional[InventoryItem], Optional[AgentTask]]:
        """
        Release reserved inventory.
        
        Args:
            item_id: Inventory item ID
            release_data: Release data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (updated item, agent task if approval required)
        """
        # Get the item
        item = await self.get_inventory_item(item_id, tenant_id)
        if not item:
            return None, None
        
        # Check if we need approval
        agent_task: Optional[AgentTask] = None
        
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="release_inventory",
                input_data={
                    "item_id": item_id,
                    "release": release_data.model_dump()
                },
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        
        # Get the reservation quantity
        reservation_quantity = release_data.quantity
        if reservation_quantity is None:
            # Release all reserved quantity
            reservation_quantity = item.quantity_reserved
        
        # Update the item
        item_model = await self.db_session.get(InventoryItemModel, item_id)
        if item_model:
            # Don't release more than reserved
            release_quantity = min(reservation_quantity, item_model.quantity_reserved)
            item_model.quantity_reserved -= release_quantity
            item_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
            await self.db_session.refresh(item_model)
        
        # If auto-execute, mark task as completed
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Return updated item
        updated_item = await self.get_inventory_item(item_id, tenant_id)
        
        return updated_item, agent_task
    
    # ========================================================================
    # Replenishment Operations
    # ========================================================================
    
    async def get_replenishment_recommendations(
        self,
        request: ReplenishmentRequest,
        tenant_id: str
    ) -> List[ReplenishmentRecommendation]:
        """
        Generate replenishment recommendations.
        
        Args:
            request: Replenishment request
            tenant_id: Tenant ID
            
        Returns:
            List of replenishment recommendations
        """
        # Get all inventory items
        items, _ = await self.list_inventory_items(
            tenant_id=tenant_id,
            warehouse_id=request.warehouse_id,
            category=request.category,
            limit=1000
        )
        
        recommendations = []
        
        for item in items:
            # Calculate if replenishment is needed
            if item.quantity_on_hand <= item.reorder_point:
                # Calculate recommended order quantity
                recommended_qty = item.reorder_quantity
                
                # If demand forecasting is enabled, use it (stubbed for Phase 1)
                if self.config.demand_forecasting_enabled:
                    # In Phase 1, this is stubbed
                    # In Phase 4, this will call the Demand Forecasting Agent
                    pass
                
                # Calculate urgency
                usage_rate = 0  # Would come from demand forecasting
                days_until_stockout = 0
                if usage_rate > 0:
                    days_until_stockout = item.quantity_on_hand / usage_rate
                
                if days_until_stockout <= 7:
                    urgency = InventoryPriority.CRITICAL
                elif days_until_stockout <= 14:
                    urgency = InventoryPriority.HIGH
                elif days_until_stockout <= 30:
                    urgency = InventoryPriority.MEDIUM
                else:
                    urgency = InventoryPriority.LOW
                
                # Create recommendation
                recommendation = ReplenishmentRecommendation(
                    item_id=item.id,
                    sku=item.sku,
                    current_quantity=item.quantity_on_hand,
                    recommended_order_quantity=recommended_qty,
                    urgency=urgency,
                    lead_time_days=item.metadata.lead_time_days or 7,
                    estimated_cost=recommended_qty * item.unit_cost,
                    reason=f"Quantity ({item.quantity_on_hand}) below reorder point ({item.reorder_point})"
                )
                recommendations.append(recommendation)
        
        # Sort by urgency
        urgency_order = {
            InventoryPriority.CRITICAL: 0,
            InventoryPriority.HIGH: 1,
            InventoryPriority.MEDIUM: 2,
            InventoryPriority.LOW: 3
        }
        recommendations.sort(key=lambda r: urgency_order.get(r.urgency, 4))
        
        # Create AgentTask for replenishment check
        await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="generate_replenishment_recommendations",
            input_data={
                "request": request.model_dump(),
                "recommendations_count": len(recommendations)
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Generated {len(recommendations)} replenishment recommendations"
        )
        
        return recommendations
    
    # ========================================================================
    # Discrepancy Operations
    # ========================================================================
    
    async def report_discrepancy(
        self,
        discrepancy_data: DiscrepancyReport,
        tenant_id: str
    ) -> DiscrepancyResponse:
        """
        Report a stock discrepancy.
        
        Args:
            discrepancy_data: Discrepancy report
            tenant_id: Tenant ID
            
        Returns:
            Discrepancy response
        """
        # Get the item
        item = await self.get_inventory_item(discrepancy_data.item_id, tenant_id)
        if not item:
            raise ValueError(f"Inventory item {discrepancy_data.item_id} not found")
        
        # Calculate discrepancy
        discrepancy = discrepancy_data.actual_quantity - discrepancy_data.expected_quantity
        discrepancy_pct = abs(discrepancy / discrepancy_data.expected_quantity * 100) if discrepancy_data.expected_quantity > 0 else 0
        
        # Create AgentTask
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="report_discrepancy",
            input_data={
                "item_id": discrepancy_data.item_id,
                "expected_quantity": discrepancy_data.expected_quantity,
                "actual_quantity": discrepancy_data.actual_quantity,
                "discrepancy": discrepancy,
                "discrepancy_pct": discrepancy_pct,
                "type": discrepancy_data.discrepancy_type
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Reported discrepancy of {discrepancy} ({discrepancy_pct:.1f}%) for item {discrepancy_data.item_id}"
        )
        
        # Update the item if auto-correct is enabled
        if self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            # Adjust the inventory to match actual quantity
            adjustment = InventoryAdjustment(
                adjustment_type=AdjustmentType.ADJUSTMENT,
                quantity=discrepancy,
                reference=f"discrepancy_{agent_task.id}",
                notes=f"Correction for discrepancy: {discrepancy_data.notes or 'No notes'}"
            )
            await self.adjust_inventory(
                item_id=discrepancy_data.item_id,
                adjustment_data=adjustment,
                tenant_id=tenant_id
            )
        
        # Generate discrepancy ID
        discrepancy_id = generate_id("discrepancy")
        
        return DiscrepancyResponse(
            discrepancy_id=discrepancy_id,
            item_id=discrepancy_data.item_id,
            status="reported",
            agent_task_id=agent_task.id
        )
    
    # ========================================================================
    # Low Stock Monitoring
    # ========================================================================
    
    async def _check_low_stock_periodically(self):
        """Periodically check all items for low stock."""
        while True:
            try:
                # Get all items
                result = await self.db_session.execute(
                    select(InventoryItemModel).where(
                        InventoryItemModel.tenant_id == self.config.tenant_id or True  # All tenants
                    )
                )
                
                items = result.scalars().all()
                
                for item in items:
                    await self._check_low_stock(item)
                
            except Exception as e:
                logger.error(f"Error in periodic low stock check: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.config.low_stock_check_interval_hours * 3600)
    
    async def _check_low_stock(self, item_model: InventoryItemModel) -> Optional[LowStockAlert]:
        """Check if an item is low on stock."""
        if not item_model.reorder_point:
            return None
        
        threshold = item_model.reorder_point * (self.config.low_stock_threshold_pct / 100)
        
        if item_model.quantity_on_hand <= threshold and not item_model.low_stock_alert:
            # Low stock detected
            item_model.low_stock_alert = True
            item_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
            
            # Create AgentTask
            await self._create_agent_task(
                tenant_id=item_model.tenant_id,
                action_type="low_stock_detected",
                input_data={
                    "item_id": item_model.id,
                    "sku": item_model.sku,
                    "current_quantity": item_model.quantity_on_hand,
                    "reorder_point": item_model.reorder_point
                },
                status=AgentTaskStatus.AUTO_EXECUTED,
                reasoning_trace=f"Low stock detected for {item_model.sku}: {item_model.quantity_on_hand} <= {threshold}"
            )
            
            # Send notification if configured
            if self.config.notify_on_low_stock:
                await self._send_low_stock_notification(item_model)
            
            return LowStockAlert(
                item_id=item_model.id,
                sku=item_model.sku,
                name=item_model.name,
                current_quantity=item_model.quantity_on_hand,
                reorder_point=item_model.reorder_point,
                quantity_below=item_model.reorder_point - item_model.quantity_on_hand,
                warehouse_id=item_model.warehouse_id,
                location=item_model.location.get("address", "") if item_model.location else None
            )
        
        elif item_model.quantity_on_hand > item_model.reorder_point and item_model.low_stock_alert:
            # Stock is back to normal
            item_model.low_stock_alert = False
            item_model.updated_at = get_current_timestamp()
            await self.db_session.commit()
        
        return None
    
    async def _check_replenishment_periodically(self):
        """Periodically check for replenishment needs."""
        while True:
            try:
                # Get all tenants
                result = await self.db_session.execute(
                    select(Tenant)
                )
                tenants = result.scalars().all()
                
                for tenant in tenants:
                    request = ReplenishmentRequest(
                        warehouse_id=None,
                        category=None,
                        horizon_days=self.config.replenishment_horizon_days
                    )
                    await self.get_replenishment_recommendations(request, tenant.id)
                
            except Exception as e:
                logger.error(f"Error in periodic replenishment check: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.config.replenishment_check_interval_hours * 3600)
    
    # ========================================================================
    # Statistics
    # ========================================================================
    
    async def get_stats(self, tenant_id: str) -> InventoryStats:
        """Get inventory statistics."""
        # Count total items
        total_result = await self.db_session.execute(
            select(func.count(InventoryItemModel.id))
            .where(InventoryItemModel.tenant_id == tenant_id)
        )
        total_items = total_result.scalar()
        
        # Sum total quantity
        quantity_result = await self.db_session.execute(
            select(func.sum(InventoryItemModel.quantity_on_hand))
            .where(InventoryItemModel.tenant_id == tenant_id)
        )
        total_quantity = quantity_result.scalar() or 0
        
        # Sum total value
        value_result = await self.db_session.execute(
            select(func.sum(InventoryItemModel.quantity_on_hand * InventoryItemModel.unit_cost))
            .where(InventoryItemModel.tenant_id == tenant_id)
        )
        total_value = value_result.scalar() or 0.0
        
        # Count low stock items
        low_stock_result = await self.db_session.execute(
            select(func.count(InventoryItemModel.id))
            .where(
                and_(
                    InventoryItemModel.tenant_id == tenant_id,
                    InventoryItemModel.low_stock_alert == True
                )
            )
        )
        low_stock_items = low_stock_result.scalar()
        
        # Count out of stock items
        out_of_stock_result = await self.db_session.execute(
            select(func.count(InventoryItemModel.id))
            .where(
                and_(
                    InventoryItemModel.tenant_id == tenant_id,
                    InventoryItemModel.quantity_on_hand == 0
                )
            )
        )
        out_of_stock_items = out_of_stock_result.scalar()
        
        # Group by category
        category_result = await self.db_session.execute(
            select(
                InventoryItemModel.category,
                func.count(InventoryItemModel.id),
                func.sum(InventoryItemModel.quantity_on_hand)
            )
            .where(InventoryItemModel.tenant_id == tenant_id)
            .group_by(InventoryItemModel.category)
        )
        by_category = {row[0]: row[1] for row in category_result if row[0]}
        
        # Group by warehouse
        warehouse_result = await self.db_session.execute(
            select(
                InventoryItemModel.warehouse_id,
                func.count(InventoryItemModel.id),
                func.sum(InventoryItemModel.quantity_on_hand)
            )
            .where(InventoryItemModel.tenant_id == tenant_id)
            .group_by(InventoryItemModel.warehouse_id)
        )
        by_warehouse = {row[0]: row[1] for row in warehouse_result if row[0]}
        
        return InventoryStats(
            total_items=total_items,
            total_quantity=total_quantity,
            total_value=total_value,
            low_stock_items=low_stock_items,
            out_of_stock_items=out_of_stock_items,
            by_category=by_category,
            by_warehouse=by_warehouse
        )
    
    # ========================================================================
    # Movement History
    # ========================================================================
    
    async def get_movement_history(
        self,
        item_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> MovementHistoryResponse:
        """Get movement history for an inventory item."""
        result = await self.db_session.execute(
            select(InventoryMovementModel)
            .where(
                and_(
                    InventoryMovementModel.inventory_item_id == item_id,
                    InventoryMovementModel.tenant_id == tenant_id
                )
            )
            .order_by(desc(InventoryMovementModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        
        movements = result.scalars().all()
        
        # Count total
        count_result = await self.db_session.execute(
            select(func.count(InventoryMovementModel.id))
            .where(
                and_(
                    InventoryMovementModel.inventory_item_id == item_id,
                    InventoryMovementModel.tenant_id == tenant_id
                )
            )
        )
        total = count_result.scalar()
        
        # Convert to schemas
        movement_schemas = [
            InventoryMovement(
                id=m.id,
                inventory_item_id=m.inventory_item_id,
                adjustment_type=m.adjustment_type,
                quantity=m.quantity,
                reference=m.reference or "",
                user_id=m.user_id,
                notes=m.notes,
                timestamp=m.created_at
            )
            for m in movements
        ]
        
        return MovementHistoryResponse(
            item_id=item_id,
            movements=movement_schemas,
            total=total
        )
    
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
            agent_type=AgentType.INVENTORY,
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
            agent_type=AgentType.INVENTORY,
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
    # Notification
    # ========================================================================
    
    async def _send_low_stock_notification(self, item_model: InventoryItemModel):
        """Send a low stock notification."""
        # This would call the notification tool
        tool_result = await self.tool_client.call_tool(
            tool_name="notification.send_email",
            arguments={
                "to": "warehouse-manager@company.com",  # Would be configured per-tenant
                "subject": f"Low Stock Alert: {item_model.sku}",
                "body": f"Item {item_model.sku} ({item_model.name}) is low on stock. Current quantity: {item_model.quantity_on_hand}, Reorder point: {item_model.reorder_point}",
                "template_id": "low_stock_alert"
            },
            tenant_id=item_model.tenant_id,
            agent_type="inventory",
            timeout=10
        )
        
        if tool_result.status != "success":
            logger.error(f"Failed to send low stock notification: {tool_result.error}")
    
    # ========================================================================
    # Configuration Management
    # ========================================================================
    
    async def get_config(self, tenant_id: str) -> InventoryManagementConfig:
        """Get the current configuration."""
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> InventoryManagementConfig:
        """Update the configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.config
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def _model_to_schema(self, model: InventoryItemModel) -> InventoryItem:
        """Convert an InventoryItemModel to InventoryItem schema."""
        return InventoryItem(
            id=model.id,
            tenant_id=model.tenant_id,
            sku=model.sku,
            name=model.name,
            description=model.description,
            category=model.category,
            warehouse_id=model.warehouse_id,
            location=Location(**model.location) if model.location else None,
            quantity_on_hand=model.quantity_on_hand,
            quantity_reserved=model.quantity_reserved,
            quantity_available=model.quantity_on_hand - model.quantity_reserved,
            reorder_point=model.reorder_point,
            reorder_quantity=model.reorder_quantity,
            unit_cost=model.unit_cost,
            unit_of_measure=model.unit_of_measure,
            low_stock_alert=model.low_stock_alert,
            expiry_date=model.expiry_date,
            batch_number=model.batch_number,
            status=model.status,
            metadata=model.metadata,
            supplier_id=model.supplier_id,
            last_updated=model.last_updated,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
