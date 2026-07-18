"""
Service layer for the Route Optimization Agent.

This service handles all business logic for route optimization.
"""

import asyncio
import logging
import random
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.db.models import (
    AgentTask as AgentTaskModel,
    Driver as DriverModel,
    Route as RouteModel,
    RouteStop as RouteStopModel,
    Tenant,
    Vehicle as VehicleModel,
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

from .config import RouteOptimizationConfig
from .schemas import (
    DriverInfo,
    Location,
    OptimizedRoute,
    ReoptimizationTrigger,
    Route,
    RouteAssignment,
    RouteAssignmentResponse,
    RouteConstraints,
    RouteCreate,
    RouteMetrics,
    RouteOptimizationRequest,
    RouteOptimizationResponse,
    RouteReoptimizationRequest,
    RouteReoptimizationResponse,
    RouteStats,
    RouteStatus,
    RouteStop,
    RouteStopCreate,
    RouteStopStatus,
    RouteStopType,
    RouteStopUpdate,
    RouteUpdate,
    StopActionRequest,
    StopActionResponse,
    VehicleInfo,
)

logger = logging.getLogger(__name__)


class RouteOptimizationService:
    """
    Service for managing route optimization operations.
    
    This service handles:
    - Creating and updating routes
    - Optimizing routes with multiple stops
    - Re-optimizing existing routes
    - Assigning routes to drivers and vehicles
    - Managing route stops
    - Checking HOS compliance (stubbed for Phase 1)
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config: RouteOptimizationConfig,
        tool_client: Optional[MCPClient] = None
    ):
        self.db_session = db_session
        self.config = config
        self.tool_client = tool_client or MCPClient()
        self._reoptimization_cooldown: Dict[str, datetime] = {}
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        logger.info("Route Optimization Service initialized")
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
        logger.info("Route Optimization Service closed")
    
    # ========================================================================
    # Route CRUD Operations
    # ========================================================================
    
    async def create_route(
        self,
        route_data: RouteCreate,
        tenant_id: str
    ) -> Tuple[Route, Optional[AgentTask]]:
        """
        Create a new route.
        
        Args:
            route_data: Route data
            tenant_id: Tenant ID
            
        Returns:
            Tuple of (created route, agent task if approval required)
        """
        # Check if we need approval based on trust level
        agent_task: Optional[AgentTask] = None
        
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            # Create approval request
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="create_route",
                input_data=route_data.model_dump(),
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        
        # Create the route
        route_model = RouteModel(
            id=generate_id("route"),
            tenant_id=tenant_id,
            name=route_data.name,
            warehouse_id=route_data.warehouse_id,
            date=route_data.date,
            status=RouteStatus.PENDING,
            total_distance_miles=0.0,
            total_duration_minutes=0,
            total_stops=len(route_data.stops),
            optimization_score=0.0,
            constraints=route_data.constraints.model_dump() if route_data.constraints else {},
            metrics={},
            created_at=get_current_timestamp(),
            updated_at=get_current_timestamp()
        )
        
        self.db_session.add(route_model)
        await self.db_session.commit()
        await self.db_session.refresh(route_model)
        
        # Create stops
        for i, stop_data in enumerate(route_data.stops):
            stop_model = RouteStopModel(
                id=generate_id("stop"),
                route_id=route_model.id,
                sequence=i + 1,
                location=stop_data.location.model_dump(),
                stop_type=stop_data.stop_type,
                time_window_start=stop_data.time_window_start,
                time_window_end=stop_data.time_window_end,
                shipment_ids=stop_data.shipment_ids or [],
                required_skills=stop_data.required_skills or [],
                weight_lbs=stop_data.weight_lbs,
                cubic_feet=stop_data.cubic_feet,
                status=RouteStopStatus.PENDING,
                notes=stop_data.notes,
                created_at=get_current_timestamp()
            )
            self.db_session.add(stop_model)
        
        await self.db_session.commit()
        
        # If auto-execute, mark task as completed
        if agent_task and self.config.trust_level != TrustLevel.PROPOSE_ONLY:
            agent_task.status = AgentTaskStatus.AUTO_EXECUTED
            agent_task.completed_at = get_current_timestamp()
            await self._update_agent_task(agent_task)
        
        # Return the created route
        route = await self.get_route(route_model.id, tenant_id)
        
        return route, agent_task
    
    async def get_route(self, route_id: str, tenant_id: str) -> Optional[Route]:
        """Get a route by ID."""
        result = await self.db_session.execute(
            select(RouteModel)
            .where(
                and_(
                    RouteModel.id == route_id,
                    RouteModel.tenant_id == tenant_id
                )
            )
            .options(joinedload(RouteModel.stops))
        )
        
        route_model = result.scalar_one_or_none()
        if not route_model:
            return None
        
        return await self._model_to_schema(route_model)
    
    async def list_routes(
        self,
        tenant_id: str,
        status: Optional[RouteStatus] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        date: Optional[date] = None,
        warehouse_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Route], int]:
        """List routes with optional filters."""
        query = select(RouteModel).where(RouteModel.tenant_id == tenant_id)
        
        if status:
            query = query.where(RouteModel.status == status)
        if driver_id:
            query = query.where(RouteModel.driver_id == driver_id)
        if vehicle_id:
            query = query.where(RouteModel.vehicle_id == vehicle_id)
        if date:
            query = query.where(RouteModel.date == date)
        if warehouse_id:
            query = query.where(RouteModel.warehouse_id == warehouse_id)
        
        # Count total
        count_result = await self.db_session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Get results
        query = query.order_by(desc(RouteModel.created_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db_session.execute(query)
        route_models = result.scalars().all()
        
        routes = []
        for model in route_models:
            route = await self._model_to_schema(model)
            routes.append(route)
        
        return routes, total
    
    async def update_route(
        self,
        route_id: str,
        route_data: RouteUpdate,
        tenant_id: str
    ) -> Tuple[Optional[Route], Optional[AgentTask]]:
        """Update a route."""
        result = await self.db_session.execute(
            select(RouteModel).where(
                and_(
                    RouteModel.id == route_id,
                    RouteModel.tenant_id == tenant_id
                )
            )
        )
        
        route_model = result.scalar_one_or_none()
        if not route_model:
            return None, None
        
        # Check if we need approval
        agent_task: Optional[AgentTask] = None
        
        # Update fields
        if route_data.name is not None:
            route_model.name = route_data.name
        if route_data.warehouse_id is not None:
            route_model.warehouse_id = route_data.warehouse_id
        if route_data.date is not None:
            route_model.date = route_data.date
        if route_data.driver_id is not None:
            route_model.driver_id = route_data.driver_id
        if route_data.vehicle_id is not None:
            route_model.vehicle_id = route_data.vehicle_id
        if route_data.status is not None:
            route_model.status = route_data.status
        if route_data.constraints is not None:
            route_model.constraints = route_data.constraints.model_dump()
        
        route_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(route_model)
        
        route = await self._model_to_schema(route_model)
        
        return route, agent_task
    
    async def delete_route(self, route_id: str, tenant_id: str) -> bool:
        """Delete a route."""
        result = await self.db_session.execute(
            select(RouteModel).where(
                and_(
                    RouteModel.id == route_id,
                    RouteModel.tenant_id == tenant_id
                )
            )
        )
        
        route_model = result.scalar_one_or_none()
        if not route_model:
            return False
        
        # Delete stops first
        await self.db_session.execute(
            select(RouteStopModel).where(RouteStopModel.route_id == route_id)
        )
        
        await self.db_session.delete(route_model)
        await self.db_session.commit()
        
        return True
    
    # ========================================================================
    # Route Optimization
    # ========================================================================
    
    async def optimize_routes(
        self,
        request: RouteOptimizationRequest,
        tenant_id: str
    ) -> RouteOptimizationResponse:
        """
        Optimize routes from a set of stops.
        
        Args:
            request: Optimization request
            tenant_id: Tenant ID
            
        Returns:
            RouteOptimizationResponse with optimized routes
        """
        # Create AgentTask for optimization
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="optimize_routes",
            input_data={
                "warehouse_id": request.warehouse_id,
                "date": request.date.isoformat(),
                "stop_count": len(request.stops),
                "driver_count": len(request.drivers),
                "vehicle_count": len(request.vehicles)
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Optimizing {len(request.stops)} stops for {request.date}"
        )
        
        # Perform optimization
        optimized_routes = await self._perform_optimization(request, tenant_id)
        
        # Create route models for the optimized routes
        created_routes = []
        for opt_route in optimized_routes:
            # Create the route
            route_data = RouteCreate(
                name=f"Optimized Route {len(created_routes) + 1}",
                warehouse_id=request.warehouse_id,
                date=request.date,
                stops=opt_route.stops,
                constraints=request.constraints
            )
            route, _ = await self.create_route(route_data, tenant_id)
            created_routes.append(route)
        
        # Return response
        return RouteOptimizationResponse(
            routes=optimized_routes,
            unassigned_stops=optimized_routes[0].unassigned_stops if optimized_routes else [],
            agent_task_id=agent_task.id
        )
    
    async def _perform_optimization(
        self,
        request: RouteOptimizationRequest,
        tenant_id: str
    ) -> List[OptimizedRoute]:
        """
        Perform the actual route optimization.
        
        This uses a simplified optimization algorithm for demonstration.
        In production, this would use a more sophisticated algorithm.
        """
        import math
        from itertools import permutations
        
        # For demo purposes, use a simple greedy algorithm
        # Group stops by proximity to warehouse
        
        # Get warehouse location (simplified)
        warehouse_lat = 37.7749  # Default San Francisco
        warehouse_lng = -122.4194
        
        # Calculate distances from warehouse
        stops_with_distance = []
        for stop in request.stops:
            distance = self._haversine_distance(
                warehouse_lat, warehouse_lng,
                stop.location.lat, stop.location.lng
            )
            stops_with_distance.append((stop, distance))
        
        # Sort by distance from warehouse
        stops_with_distance.sort(key=lambda x: x[1])
        
        # Create routes
        optimized_routes = []
        current_route_stops = []
        current_distance = 0.0
        current_duration = 0
        current_weight = 0.0
        current_volume = 0.0
        
        max_distance = request.constraints.max_distance_miles or self.config.max_route_distance_miles
        max_duration = request.constraints.max_duration_minutes or (self.config.max_route_duration_hours * 60)
        max_weight = request.constraints.vehicle_capacity_weight_lbs or self.config.default_vehicle_capacity_weight_lbs
        max_volume = request.constraints.vehicle_capacity_cubic_feet or self.config.default_vehicle_capacity_cubic_feet
        
        for stop, distance in stops_with_distance:
            # Check if adding this stop would exceed constraints
            if (current_distance + distance > max_distance or
                current_duration + 30 > max_duration or  # Assume 30 min per stop
                current_weight + stop.weight_lbs > max_weight or
                current_volume + stop.cubic_feet > max_volume):
                
                # Create a new route with current stops
                if current_route_stops:
                    optimized_route = await self._create_optimized_route(
                        current_route_stops,
                        request,
                        tenant_id
                    )
                    optimized_routes.append(optimized_route)
                
                # Start new route
                current_route_stops = [stop]
                current_distance = distance
                current_duration = 30
                current_weight = stop.weight_lbs
                current_volume = stop.cubic_feet
            else:
                current_route_stops.append(stop)
                current_distance += distance
                current_duration += 30
                current_weight += stop.weight_lbs
                current_volume += stop.cubic_feet
        
        # Add the last route
        if current_route_stops:
            optimized_route = await self._create_optimized_route(
                current_route_stops,
                request,
                tenant_id
            )
            optimized_routes.append(optimized_route)
        
        return optimized_routes
    
    async def _create_optimized_route(
        self,
        stops: List[RouteStopCreate],
        request: RouteOptimizationRequest,
        tenant_id: str
    ) -> OptimizedRoute:
        """Create an optimized route from a list of stops."""
        # Calculate route metrics
        total_distance = 0.0
        total_duration = 0
        total_weight = 0.0
        total_volume = 0.0
        
        # Simple distance calculation (sum of distances between consecutive stops)
        for i in range(len(stops)):
            if i > 0:
                distance = self._haversine_distance(
                    stops[i-1].location.lat, stops[i-1].location.lng,
                    stops[i].location.lat, stops[i].location.lng
                )
                total_distance += distance
            total_duration += 30  # 30 minutes per stop
            total_weight += stops[i].weight_lbs
            total_volume += stops[i].cubic_feet
        
        # Calculate optimization score (0-1)
        # For demo, use a random score based on how well we did
        utilization = min(
            total_weight / (request.constraints.vehicle_capacity_weight_lbs or self.config.default_vehicle_capacity_weight_lbs),
            total_volume / (request.constraints.vehicle_capacity_cubic_feet or self.config.default_vehicle_capacity_cubic_feet)
        )
        optimization_score = min(0.8 + (utilization * 0.2), 1.0)  # 0.8-1.0
        
        # Calculate costs
        fuel_cost = total_distance * (self.config.vehicle_cost_per_mile / self.config.default_vehicle_capacity_cubic_feet)
        driver_cost = (total_duration / 60) * self.config.driver_cost_per_hour
        total_cost = fuel_cost + driver_cost
        
        # Create route stops with sequences
        route_stops = []
        for i, stop in enumerate(stops):
            route_stop = RouteStop(
                id=generate_id("stop"),
                sequence=i + 1,
                location=stop.location,
                stop_type=stop.stop_type,
                time_window_start=stop.time_window_start,
                time_window_end=stop.time_window_end,
                shipment_ids=stop.shipment_ids or [],
                required_skills=stop.required_skills or [],
                weight_lbs=stop.weight_lbs,
                cubic_feet=stop.cubic_feet,
                status=RouteStopStatus.PENDING,
                notes=stop.notes,
                estimated_arrival=None,
                actual_arrival=None,
                estimated_departure=None,
                actual_departure=None
            )
            route_stops.append(route_stop)
        
        # Create optimized route
        optimized_route = OptimizedRoute(
            id=generate_id("route"),
            stops=route_stops,
            metrics=RouteMetrics(
                fuel_cost=fuel_cost,
                toll_cost=0.0,
                driver_pay=driver_cost,
                total_cost=total_cost
            ),
            optimization_score=optimization_score,
            unassigned_stops=[]
        )
        
        return optimized_route
    
    # ============================================================================
    # Route Re-optimization
    # ============================================================================
    
    async def reoptimize_route(
        self,
        route_id: str,
        request: RouteReoptimizationRequest,
        tenant_id: str
    ) -> RouteReoptimizationResponse:
        """
        Re-optimize an existing route.
        
        Args:
            route_id: Route ID to re-optimize
            request: Re-optimization request
            tenant_id: Tenant ID
            
        Returns:
            RouteReoptimizationResponse with the re-optimized route
        """
        # Get the existing route
        route = await self.get_route(route_id, tenant_id)
        if not route:
            raise ValueError(f"Route {route_id} not found")
        
        # Check cooldown
        if route_id in self._reoptimization_cooldown:
            last_reopt = self._reoptimization_cooldown[route_id]
            cooldown_minutes = self.config.reoptimization_cooldown_minutes
            if (datetime.utcnow() - last_reopt).total_seconds() < cooldown_minutes * 60:
                raise ValueError(f"Route {route_id} was recently re-optimized. Please wait {cooldown_minutes} minutes.")
        
        # Check if we need approval for re-optimization
        # If route is in progress with other stops, require approval
        in_progress_stops = [s for s in route.stops if s.status == RouteStopStatus.IN_PROGRESS]
        
        if in_progress_stops and self.config.trust_level != TrustLevel.FULLY_AUTONOMOUS:
            # Create approval request
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="reoptimize_route",
                input_data={
                    "route_id": route_id,
                    "trigger": request.trigger.value,
                    "in_progress_stops": len(in_progress_stops)
                },
                status=AgentTaskStatus.PENDING_APPROVAL,
                reasoning_trace=f"Re-optimization requested for route {route_id} with {len(in_progress_stops)} stops in progress"
            )
            
            return RouteReoptimizationResponse(
                route_id=route_id,
                optimized_route=OptimizedRoute(
                    id=route_id,
                    stops=route.stops,
                    metrics=route.metrics,
                    optimization_score=route.optimization_score
                ),
                changes="Pending approval due to in-progress stops",
                agent_task_id=agent_task.id
            )
        
        # Perform re-optimization
        optimized_route = await self._perform_reoptimization(route, request, tenant_id)
        
        # Update the route
        route_model = await self.db_session.get(RouteModel, route_id)
        if route_model:
            route_model.total_distance_miles = optimized_route.metrics.fuel_cost / self.config.vehicle_cost_per_mile
            route_model.total_duration_minutes = int(optimized_route.metrics.driver_pay / self.config.driver_cost_per_hour * 60)
            route_model.optimization_score = optimized_route.optimization_score
            route_model.updated_at = get_current_timestamp()
            
            # Add to reoptimization history
            if not route_model.reoptimization_history:
                route_model.reoptimization_history = []
            route_model.reoptimization_history.append({
                "timestamp": get_current_timestamp().isoformat(),
                "trigger": request.trigger.value,
                "changes": "Route re-optimized",
                "agent_task_id": None
            })
            
            await self.db_session.commit()
        
        # Update cooldown
        self._reoptimization_cooldown[route_id] = datetime.utcnow()
        
        # Create AgentTask
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="reoptimize_route",
            input_data={
                "route_id": route_id,
                "trigger": request.trigger.value,
                "changes": "Route re-optimized"
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Re-optimized route {route_id} due to {request.trigger.value}"
        )
        
        return RouteReoptimizationResponse(
            route_id=route_id,
            optimized_route=optimized_route,
            changes="Route re-optimized",
            agent_task_id=agent_task.id
        )
    
    async def _perform_reoptimization(
        self,
        route: Route,
        request: RouteReoptimizationRequest,
        tenant_id: str
    ) -> OptimizedRoute:
        """
        Perform the actual route re-optimization.
        
        This handles:
        - Adding new stops
        - Removing stops
        - Re-ordering stops
        - Re-calculating metrics
        """
        # Get all stops (excluding removed ones)
        all_stops = [s for s in route.stops if s.id not in request.removed_stop_ids]
        
        # Add new stop if provided
        if request.new_stop:
            all_stops.append(request.new_stop)
        
        # Create optimization request
        opt_request = RouteOptimizationRequest(
            warehouse_id=route.warehouse_id,
            date=route.date,
            stops=all_stops,
            drivers=[],
            vehicles=[],
            constraints=route.constraints or RouteConstraints()
        )
        
        # Perform optimization
        optimized_routes = await self._perform_optimization(opt_request, tenant_id)
        
        # Return the first (and only) optimized route
        if optimized_routes:
            return optimized_routes[0]
        
        # Fallback to original route
        return OptimizedRoute(
            id=route.id,
            stops=route.stops,
            metrics=route.metrics,
            optimization_score=route.optimization_score
        )
    
    # ============================================================================
    # Route Assignment
    # ============================================================================
    
    async def assign_route(
        self,
        route_id: str,
        assignment_data: RouteAssignment,
        tenant_id: str
    ) -> RouteAssignmentResponse:
        """
        Assign a route to a driver and vehicle.
        
        Args:
            route_id: Route ID
            assignment_data: Assignment data
            tenant_id: Tenant ID
            
        Returns:
            RouteAssignmentResponse
        """
        # Get the route
        route = await self.get_route(route_id, tenant_id)
        if not route:
            raise ValueError(f"Route {route_id} not found")
        
        # Check if we need to verify HOS compliance (stubbed for Phase 1)
        if self.config.check_hos_compliance:
            # In Phase 1, this is stubbed
            # In Phase 2, this will call the Fleet Management Agent
            hos_compliant = await self._check_hos_compliance(
                driver_id=assignment_data.driver_id,
                route=route,
                tenant_id=tenant_id
            )
            
            if not hos_compliant:
                # Create AgentTask for HOS violation
                agent_task = await self._create_agent_task(
                    tenant_id=tenant_id,
                    action_type="assign_route",
                    input_data={
                        "route_id": route_id,
                        "driver_id": assignment_data.driver_id,
                        "vehicle_id": assignment_data.vehicle_id
                    },
                    status=AgentTaskStatus.FAILED,
                    error_message="Driver HOS compliance check failed"
                )
                
                raise ValueError("Driver HOS compliance check failed. Cannot assign route.")
        
        # Check if approval is needed
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="assign_route",
                input_data={
                    "route_id": route_id,
                    "driver_id": assignment_data.driver_id,
                    "vehicle_id": assignment_data.vehicle_id
                },
                status=AgentTaskStatus.PENDING_APPROVAL
            )
            
            return RouteAssignmentResponse(
                route_id=route_id,
                driver_id=assignment_data.driver_id,
                vehicle_id=assignment_data.vehicle_id,
                assigned_at=datetime.utcnow(),
                agent_task_id=agent_task.id
            )
        
        # Update the route
        route_model = await self.db_session.get(RouteModel, route_id)
        if route_model:
            route_model.driver_id = assignment_data.driver_id
            route_model.vehicle_id = assignment_data.vehicle_id
            route_model.status = RouteStatus.ASSIGNED
            route_model.assigned_at = get_current_timestamp()
            route_model.updated_at = get_current_timestamp()
            
            await self.db_session.commit()
            await self.db_session.refresh(route_model)
        
        # Create AgentTask
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="assign_route",
            input_data={
                "route_id": route_id,
                "driver_id": assignment_data.driver_id,
                "vehicle_id": assignment_data.vehicle_id
            },
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Assigned route {route_id} to driver {assignment_data.driver_id} and vehicle {assignment_data.vehicle_id}"
        )
        
        return RouteAssignmentResponse(
            route_id=route_id,
            driver_id=assignment_data.driver_id,
            vehicle_id=assignment_data.vehicle_id,
            assigned_at=datetime.utcnow(),
            agent_task_id=agent_task.id
        )
    
    async def _check_hos_compliance(
        self,
        driver_id: str,
        route: Route,
        tenant_id: str
    ) -> bool:
        """
        Check if a driver has sufficient HOS for a route.
        
        This is stubbed for Phase 1. In Phase 2, this will call the Fleet Management Agent.
        """
        # In Phase 1, always return True (compliant)
        # In Phase 2, this would call the Fleet Management Agent
        
        logger.info(f"Checking HOS compliance for driver {driver_id} on route {route.id} (stubbed)")
        
        # Simulate HOS check
        return True
    
    # ============================================================================
    # Route Status Updates
    # ============================================================================
    
    async def start_route(self, route_id: str, tenant_id: str) -> Route:
        """Mark a route as started."""
        route_model = await self.db_session.get(RouteModel, route_id)
        if not route_model or route_model.tenant_id != tenant_id:
            raise ValueError(f"Route {route_id} not found")
        
        route_model.status = RouteStatus.IN_PROGRESS
        route_model.started_at = get_current_timestamp()
        route_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(route_model)
        
        # Create AgentTask
        await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="start_route",
            input_data={"route_id": route_id},
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Route {route_id} started"
        )
        
        return await self._model_to_schema(route_model)
    
    async def complete_route(self, route_id: str, tenant_id: str) -> Route:
        """Mark a route as completed."""
        route_model = await self.db_session.get(RouteModel, route_id)
        if not route_model or route_model.tenant_id != tenant_id:
            raise ValueError(f"Route {route_id} not found")
        
        route_model.status = RouteStatus.COMPLETED
        route_model.completed_at = get_current_timestamp()
        route_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(route_model)
        
        # Create AgentTask
        await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="complete_route",
            input_data={"route_id": route_id},
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Route {route_id} completed"
        )
        
        return await self._model_to_schema(route_model)
    
    # ============================================================================
    # Stop Operations
    # ============================================================================
    
    async def update_stop(
        self,
        route_id: str,
        stop_id: str,
        stop_data: RouteStopUpdate,
        tenant_id: str
    ) -> Route:
        """Update a route stop."""
        stop_model = await self.db_session.get(RouteStopModel, stop_id)
        if not stop_model or stop_model.route_id != route_id:
            raise ValueError(f"Stop {stop_id} not found in route {route_id}")
        
        # Update fields
        if stop_data.location is not None:
            stop_model.location = stop_data.location.model_dump()
        if stop_data.stop_type is not None:
            stop_model.stop_type = stop_data.stop_type
        if stop_data.time_window_start is not None:
            stop_model.time_window_start = stop_data.time_window_start
        if stop_data.time_window_end is not None:
            stop_model.time_window_end = stop_data.time_window_end
        if stop_data.shipment_ids is not None:
            stop_model.shipment_ids = stop_data.shipment_ids
        if stop_data.required_skills is not None:
            stop_model.required_skills = stop_data.required_skills
        if stop_data.weight_lbs is not None:
            stop_model.weight_lbs = stop_data.weight_lbs
        if stop_data.cubic_feet is not None:
            stop_model.cubic_feet = stop_data.cubic_feet
        if stop_data.notes is not None:
            stop_model.notes = stop_data.notes
        if stop_data.status is not None:
            stop_model.status = stop_data.status
        
        stop_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        await self.db_session.refresh(stop_model)
        
        # Return updated route
        return await self.get_route(route_id, tenant_id)
    
    async def start_stop(
        self,
        route_id: str,
        stop_id: str,
        tenant_id: str
    ) -> StopActionResponse:
        """Mark a stop as started."""
        stop_model = await self.db_session.get(RouteStopModel, stop_id)
        if not stop_model or stop_model.route_id != route_id:
            raise ValueError(f"Stop {stop_id} not found in route {route_id}")
        
        stop_model.status = RouteStopStatus.IN_PROGRESS
        stop_model.estimated_arrival = get_current_timestamp().time()
        stop_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        
        # Create AgentTask
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="start_stop",
            input_data={"route_id": route_id, "stop_id": stop_id},
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Stop {stop_id} in route {route_id} started"
        )
        
        return StopActionResponse(
            stop_id=stop_id,
            route_id=route_id,
            action="start",
            timestamp=get_current_timestamp(),
            agent_task_id=agent_task.id
        )
    
    async def complete_stop(
        self,
        route_id: str,
        stop_id: str,
        tenant_id: str
    ) -> StopActionResponse:
        """Mark a stop as completed."""
        stop_model = await self.db_session.get(RouteStopModel, stop_id)
        if not stop_model or stop_model.route_id != route_id:
            raise ValueError(f"Stop {stop_id} not found in route {route_id}")
        
        stop_model.status = RouteStopStatus.COMPLETED
        stop_model.actual_arrival = get_current_timestamp().time()
        stop_model.actual_departure = get_current_timestamp().time()
        stop_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        
        # Create AgentTask
        agent_task = await self._create_agent_task(
            tenant_id=tenant_id,
            action_type="complete_stop",
            input_data={"route_id": route_id, "stop_id": stop_id},
            status=AgentTaskStatus.AUTO_EXECUTED,
            reasoning_trace=f"Stop {stop_id} in route {route_id} completed"
        )
        
        return StopActionResponse(
            stop_id=stop_id,
            route_id=route_id,
            action="complete",
            timestamp=get_current_timestamp(),
            agent_task_id=agent_task.id
        )
    
    async def skip_stop(
        self,
        route_id: str,
        stop_id: str,
        request: StopActionRequest,
        tenant_id: str
    ) -> StopActionResponse:
        """Skip a stop."""
        stop_model = await self.db_session.get(RouteStopModel, stop_id)
        if not stop_model or stop_model.route_id != route_id:
            raise ValueError(f"Stop {stop_id} not found in route {route_id}")
        
        stop_model.status = RouteStopStatus.SKIPPED
        stop_model.updated_at = get_current_timestamp()
        
        await self.db_session.commit()
        
        # Check if approval is needed for skipping
        if self.config.trust_level == TrustLevel.PROPOSE_ONLY:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="skip_stop",
                input_data={
                    "route_id": route_id,
                    "stop_id": stop_id,
                    "reason": request.reason or ""
                },
                status=AgentTaskStatus.PENDING_APPROVAL
            )
        else:
            agent_task = await self._create_agent_task(
                tenant_id=tenant_id,
                action_type="skip_stop",
                input_data={
                    "route_id": route_id,
                    "stop_id": stop_id,
                    "reason": request.reason or ""
                },
                status=AgentTaskStatus.AUTO_EXECUTED,
                reasoning_trace=f"Stop {stop_id} in route {route_id} skipped: {request.reason or 'No reason'}"
            )
        
        return StopActionResponse(
            stop_id=stop_id,
            route_id=route_id,
            action="skip",
            timestamp=get_current_timestamp(),
            agent_task_id=agent_task.id
        )
    
    # ============================================================================
    # Statistics
    # ============================================================================
    
    async def get_stats(self, tenant_id: str) -> RouteStats:
        """Get route statistics."""
        # Count by status
        status_counts = {}
        for status in [RouteStatus.PENDING, RouteStatus.ASSIGNED, RouteStatus.IN_PROGRESS, RouteStatus.COMPLETED, RouteStatus.CANCELLED]:
            result = await self.db_session.execute(
                select(func.count(RouteModel.id))
                .where(
                    and_(
                        RouteModel.tenant_id == tenant_id,
                        RouteModel.status == status
                    )
                )
            )
            status_counts[status.value] = result.scalar()
        
        # Calculate averages
        avg_score_result = await self.db_session.execute(
            select(func.avg(RouteModel.optimization_score))
            .where(RouteModel.tenant_id == tenant_id)
        )
        avg_optimization_score = avg_score_result.scalar() or 0.0
        
        avg_distance_result = await self.db_session.execute(
            select(func.avg(RouteModel.total_distance_miles))
            .where(RouteModel.tenant_id == tenant_id)
        )
        avg_distance_miles = avg_distance_result.scalar() or 0.0
        
        avg_duration_result = await self.db_session.execute(
            select(func.avg(RouteModel.total_duration_minutes))
            .where(RouteModel.tenant_id == tenant_id)
        )
        avg_duration_minutes = avg_duration_result.scalar() or 0
        
        # Count total stops
        stop_count_result = await self.db_session.execute(
            select(func.count(RouteStopModel.id))
            .join(RouteModel)
            .where(RouteModel.tenant_id == tenant_id)
        )
        total_stops = stop_count_result.scalar() or 0
        
        return RouteStats(
            total_routes=status_counts.get("pending", 0) + status_counts.get("assigned", 0) + 
                         status_counts.get("in_progress", 0) + status_counts.get("completed", 0) + 
                         status_counts.get("cancelled", 0),
            pending_routes=status_counts.get("pending", 0),
            assigned_routes=status_counts.get("assigned", 0),
            in_progress_routes=status_counts.get("in_progress", 0),
            completed_routes=status_counts.get("completed", 0),
            avg_optimization_score=avg_optimization_score,
            avg_distance_miles=avg_distance_miles,
            avg_duration_minutes=avg_duration_minutes,
            total_stops=total_stops
        )
    
    # ============================================================================
    # Agent Task Management
    # ============================================================================
    
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
            agent_type=AgentType.ROUTE_OPTIMIZATION,
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
            agent_type=AgentType.ROUTE_OPTIMIZATION,
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
    
    # ============================================================================
    # Configuration Management
    # ============================================================================
    
    async def get_config(self, tenant_id: str) -> RouteOptimizationConfig:
        """Get the current configuration."""
        return self.config
    
    async def update_config(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any]
    ) -> RouteOptimizationConfig:
        """Update the configuration."""
        for key, value in config_updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        return self.config
    
    # ============================================================================
    # Utility Methods
    # ============================================================================
    
    async def _model_to_schema(self, model: RouteModel) -> Route:
        """Convert a RouteModel to Route schema."""
        # Get stops
        stops_result = await self.db_session.execute(
            select(RouteStopModel)
            .where(RouteStopModel.route_id == model.id)
            .order_by(RouteStopModel.sequence)
        )
        stop_models = stops_result.scalars().all()
        
        stops = []
        for stop_model in stop_models:
            stop = RouteStop(
                id=stop_model.id,
                sequence=stop_model.sequence,
                location=Location(**stop_model.location) if stop_model.location else None,
                stop_type=stop_model.stop_type,
                time_window_start=stop_model.time_window_start,
                time_window_end=stop_model.time_window_end,
                shipment_ids=stop_model.shipment_ids or [],
                required_skills=stop_model.required_skills or [],
                weight_lbs=stop_model.weight_lbs,
                cubic_feet=stop_model.cubic_feet,
                status=stop_model.status,
                notes=stop_model.notes,
                estimated_arrival=stop_model.estimated_arrival,
                actual_arrival=stop_model.actual_arrival,
                estimated_departure=stop_model.estimated_departure,
                actual_departure=stop_model.actual_departure
            )
            stops.append(stop)
        
        return Route(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            warehouse_id=model.warehouse_id,
            date=model.date,
            status=model.status,
            driver_id=model.driver_id,
            vehicle_id=model.vehicle_id,
            total_distance_miles=model.total_distance_miles,
            total_duration_minutes=model.total_duration_minutes,
            total_stops=model.total_stops,
            optimization_score=model.optimization_score,
            constraints=RouteConstraints(**model.constraints) if model.constraints else RouteConstraints(),
            metrics=RouteMetrics(**model.metrics) if model.metrics else RouteMetrics(),
            assigned_at=model.assigned_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            stops=stops,
            reoptimization_history=model.reoptimization_history or []
        )
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two points on Earth.
        
        Args:
            lat1, lon1: Latitude and longitude of point 1
            lat2, lon2: Latitude and longitude of point 2
            
        Returns:
            Distance in miles
        """
        import math
        
        # Radius of Earth in miles
        R = 3958.8
        
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
