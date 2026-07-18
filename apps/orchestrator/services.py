"""
Services for the Orchestrator.

This module contains the service classes that power the orchestration layer.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from packages.shared_types.schemas import (
    AgentType,
    TrustLevel,
)
from packages.tool_bus.mcp_client import MCPClient

from .schemas import (
    AgentInfo,
    ConversationRequest,
    ConversationResponse,
    GuardrailsCheckRequest,
    GuardrailsCheckResponse,
    PlanRequest,
    PlanResponse,
    TaskRequest,
    TaskResponse,
)

logger = logging.getLogger(__name__)


class ConversationRouterService:
    """
    Service for routing conversations to agents.
    
    This service:
    - Extracts intent from messages
    - Routes to appropriate agents
    - Manages conversation state
    - Handles approval workflows
    """
    
    def __init__(self, tool_client: Optional[MCPClient] = None):
        self.tool_client = tool_client or MCPClient()
        self._conversations: Dict[str, ConversationRequest] = {}
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
    
    async def route_conversation(
        self,
        request: ConversationRequest
    ) -> ConversationResponse:
        """
        Route a conversation to the appropriate agent.
        
        Args:
            request: The conversation request
            
        Returns:
            ConversationResponse with the agent's response
        """
        # Store conversation for state management
        if request.conversation_id:
            self._conversations[request.conversation_id] = request
        
        # Extract intent
        structured_intent = await self._extract_intent(request)
        
        # Determine agent
        agent_type = self._determine_agent(structured_intent)
        
        # Check if approval is needed
        requires_approval = self._check_approval_needed(structured_intent, agent_type)
        
        # Route to agent
        if requires_approval:
            response = await self._handle_approval(request, structured_intent, agent_type)
        else:
            response = await self._execute_agent(request, structured_intent, agent_type)
        
        return response
    
    async def _extract_intent(
        self,
        request: ConversationRequest
    ) -> Dict[str, Any]:
        """Extract intent from the conversation message."""
        # In a real implementation, this would use an LLM
        # For now, use simple keyword matching
        
        message = request.message.lower()
        intent: Dict[str, Any] = {
            "intent_type": "unknown",
            "entities": {},
            "confidence": 0.0
        }
        
        # Status query
        if any(word in message for word in ["where is", "status", "eta", "tracking", "where's"]):
            intent["intent_type"] = "status_query"
            intent["confidence"] = 0.9
            
            # Extract tracking number
            import re
            tracking_match = re.search(r'\b\d{10,20}\b', message)
            if tracking_match:
                intent["entities"]["tracking_number"] = tracking_match.group()
        
        # Route optimization
        elif any(word in message for word in ["route", "optimize", "re-optimize", "best route"]):
            intent["intent_type"] = "route_optimization"
            intent["confidence"] = 0.85
        
        # Inventory
        elif any(word in message for word in ["inventory", "stock", "quantity"]):
            intent["intent_type"] = "inventory_check"
            intent["confidence"] = 0.85
        
        # Driver issue
        elif any(word in message for word in ["stuck", "closed", "delay", "issue", "problem"]):
            intent["intent_type"] = "driver_issue"
            intent["confidence"] = 0.9
        
        # Customer complaint
        elif any(word in message for word in ["complaint", "refund", "compensation"]):
            intent["intent_type"] = "customer_complaint"
            intent["confidence"] = 0.95
        
        return intent
    
    def _determine_agent(self, intent: Dict[str, Any]) -> AgentType:
        """Determine which agent should handle the request."""
        intent_type = intent.get("intent_type", "unknown")
        
        if intent_type == "status_query":
            return AgentType.SHIPMENT_TRACKING
        elif intent_type == "route_optimization":
            return AgentType.ROUTE_OPTIMIZATION
        elif intent_type == "inventory_check":
            return AgentType.INVENTORY
        elif intent_type == "driver_issue":
            return AgentType.ROUTE_OPTIMIZATION
        elif intent_type == "customer_complaint":
            return AgentType.CUSTOMER_COMMUNICATION
        else:
            return AgentType.CUSTOMER_COMMUNICATION
    
    def _check_approval_needed(
        self,
        intent: Dict[str, Any],
        agent_type: AgentType
    ) -> bool:
        """Check if approval is needed for this request."""
        intent_type = intent.get("intent_type", "unknown")
        
        # Customer complaints always need human review
        if intent_type == "customer_complaint":
            return True
        
        # For demo purposes, don't require approval for other types
        return False
    
    async def _handle_approval(
        self,
        request: ConversationRequest,
        intent: Dict[str, Any],
        agent_type: AgentType
    ) -> ConversationResponse:
        """Handle approval workflow."""
        # In a real implementation, this would create an ApprovalRequest
        # and return a response indicating approval is needed
        
        return ConversationResponse(
            conversation_id=request.conversation_id or "conv_unknown",
            message_id="msg_unknown",
            response="This request requires human approval. Please contact a dispatcher.",
            structured_intent=intent,
            agent_type=agent_type,
            requires_approval=True,
            confidence=intent.get("confidence", 0.0),
            timestamp=datetime.utcnow()
        )
    
    async def _execute_agent(
        self,
        request: ConversationRequest,
        intent: Dict[str, Any],
        agent_type: AgentType
    ) -> ConversationResponse:
        """Execute the agent action."""
        # In a real implementation, this would call the agent's API
        # For now, generate a simulated response
        
        response = self._generate_simulated_response(agent_type, intent, request)
        
        return ConversationResponse(
            conversation_id=request.conversation_id or "conv_unknown",
            message_id="msg_unknown",
            response=response,
            structured_intent=intent,
            agent_type=agent_type,
            requires_approval=False,
            confidence=intent.get("confidence", 0.0),
            timestamp=datetime.utcnow()
        )
    
    def _generate_simulated_response(
        self,
        agent_type: AgentType,
        intent: Dict[str, Any],
        request: ConversationRequest
    ) -> str:
        """Generate a simulated agent response."""
        if agent_type == AgentType.SHIPMENT_TRACKING:
            tracking_number = intent.get("entities", {}).get("tracking_number", "UNKNOWN")
            return f"Shipment {tracking_number} is currently in transit with an ETA of tomorrow."
        
        elif agent_type == AgentType.ROUTE_OPTIMIZATION:
            return "I've re-optimized your route. The new route avoids the closed road and adds 15 minutes to your trip."
        
        elif agent_type == AgentType.INVENTORY:
            return "Current inventory levels: SKU-001 has 50 units, SKU-002 has 25 units."
        
        elif agent_type == AgentType.CUSTOMER_COMMUNICATION:
            return "I understand your concern. Let me look into that for you."
        
        else:
            return "I can help with that. What specific information do you need?"


class TaskOrchestratorService:
    """
    Service for orchestrating tasks across agents.
    
    This service:
    - Validates task requests
    - Checks guardrails
    - Manages trust levels
    - Creates AgentTask records
    - Routes tasks to agents
    - Handles approval workflows
    """
    
    def __init__(self, tool_client: Optional[MCPClient] = None):
        self.tool_client = tool_client or MCPClient()
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
    
    async def execute_task(self, request: TaskRequest) -> TaskResponse:
        """
        Execute a task through the orchestrator.
        
        Args:
            request: The task request
            
        Returns:
            TaskResponse with the execution result
        """
        # Validate request
        if not request.tenant_id:
            return TaskResponse(
                agent_task_id="",
                status="failed",
                error_message="Tenant ID is required"
            )
        
        # Check guardrails
        guardrails_result = await self._check_guardrails(request)
        if not guardrails_result.allowed:
            return TaskResponse(
                agent_task_id="",
                status="failed",
                error_message=f"Guardrails violation: {', '.join(guardrails_result.violations)}"
            )
        
        # Check trust level
        trust_allowed = await self._check_trust_level(request)
        if not trust_allowed:
            return TaskResponse(
                agent_task_id="",
                status="failed",
                error_message="Trust level not sufficient for this action"
            )
        
        # Create AgentTask
        agent_task_id = self._create_agent_task(request)
        
        # Check if approval is needed
        requires_approval = self._check_approval_needed(request)
        
        if requires_approval:
            approval_request_id = self._create_approval_request(request, agent_task_id)
            return TaskResponse(
                agent_task_id=agent_task_id,
                status="pending_approval",
                requires_approval=True,
                approval_request_id=approval_request_id
            )
        else:
            # Execute the task
            output_data = await self._execute_agent_task(request)
            return TaskResponse(
                agent_task_id=agent_task_id,
                status="auto_executed",
                output_data=output_data,
                requires_approval=False
            )
    
    async def _check_guardrails(self, request: TaskRequest) -> GuardrailsCheckResponse:
        """Check the request against guardrails."""
        # In a real implementation, this would call the GuardrailsEngine
        # For now, just return allowed
        return GuardrailsCheckResponse(
            allowed=True,
            violations=[],
            warnings=[],
            required_trust_level=request.trust_level,
            recommended_action=None
        )
    
    async def _check_trust_level(self, request: TaskRequest) -> bool:
        """Check if the trust level allows the action."""
        # In a real implementation, this would check the tenant's trust level
        # and the action's requirements
        return True
    
    def _create_agent_task(self, request: TaskRequest) -> str:
        """Create an AgentTask record."""
        # In a real implementation, this would save to the database
        # For now, just generate an ID
        from packages.shared_types.utils import generate_id
        return generate_id("task")
    
    def _check_approval_needed(self, request: TaskRequest) -> bool:
        """Check if approval is needed for this task."""
        # In a real implementation, this would check the action type
        # and the tenant's trust level
        
        # For demo purposes, don't require approval
        return False
    
    def _create_approval_request(self, request: TaskRequest, agent_task_id: str) -> str:
        """Create an ApprovalRequest."""
        # In a real implementation, this would save to the database
        # For now, just generate an ID
        from packages.shared_types.utils import generate_id
        return generate_id("approval")
    
    async def _execute_agent_task(self, request: TaskRequest) -> Dict[str, Any]:
        """Execute the agent task."""
        # In a real implementation, this would call the agent's API
        # For now, return a simulated result
        return {"result": "Task executed successfully"}


class PlannerService:
    """
    Service for creating plans.
    
    This service:
    - Analyzes goals and constraints
    - Generates plans with steps
    - Validates plans
    - Optimizes plans
    """
    
    def __init__(self, tool_client: Optional[MCPClient] = None):
        self.tool_client = tool_client or MCPClient()
        
    async def initialize(self):
        """Initialize the service."""
        await self.tool_client.initialize()
        
    async def close(self):
        """Close the service."""
        await self.tool_client.close()
    
    async def create_plan(self, request: PlanRequest) -> PlanResponse:
        """
        Create a plan to achieve a goal.
        
        Args:
            request: The plan request
            
        Returns:
            PlanResponse with the generated plan
        """
        # Analyze the goal
        analysis = await self._analyze_goal(request)
        
        # Generate steps
        steps = await self._generate_steps(request, analysis)
        
        # Validate the plan
        validation = await self._validate_plan(steps)
        
        if not validation["valid"]:
            return PlanResponse(
                plan_id="",
                goal=request.goal,
                steps=[],
                confidence=0.0
            )
        
        # Optimize the plan
        optimized_steps = await self._optimize_plan(steps)
        
        # Calculate total duration
        total_duration = sum(s.estimated_duration_seconds for s in optimized_steps)
        
        return PlanResponse(
            plan_id=self._generate_plan_id(),
            goal=request.goal,
            steps=optimized_steps,
            estimated_total_duration_seconds=total_duration,
            confidence=0.85,
            created_at=datetime.utcnow()
        )
    
    async def _analyze_goal(self, request: PlanRequest) -> Dict[str, Any]:
        """Analyze the goal and extract requirements."""
        goal = request.goal.lower()
        
        requirements = []
        if "shipment" in goal or "tracking" in goal:
            requirements.append("shipment_tracking")
        if "route" in goal or "optimize" in goal:
            requirements.append("route_optimization")
        if "inventory" in goal:
            requirements.append("inventory")
        
        return {
            "requirements": requirements,
            "constraints": request.constraints
        }
    
    async def _generate_steps(
        self,
        request: PlanRequest,
        analysis: Dict[str, Any]
    ) -> List[Any]:
        """Generate plan steps."""
        from .schemas import PlanStep
        from packages.shared_types.utils import generate_id
        
        steps = []
        requirements = analysis.get("requirements", [])
        
        if "shipment_tracking" in requirements:
            steps.append(PlanStep(
                step_id=generate_id("step"),
                agent_type=AgentType.SHIPMENT_TRACKING,
                action="check_shipment_status",
                description="Check the status of the shipment",
                dependencies=[],
                estimated_duration_seconds=5.0,
                trust_level_required=TrustLevel.AUTO_EXECUTE_LOW_RISK
            ))
        
        if "route_optimization" in requirements:
            steps.append(PlanStep(
                step_id=generate_id("step"),
                agent_type=AgentType.ROUTE_OPTIMIZATION,
                action="optimize_route",
                description="Optimize the delivery route",
                dependencies=[s.step_id for s in steps] if steps else [],
                estimated_duration_seconds=10.0,
                trust_level_required=TrustLevel.PROPOSE_ONLY
            ))
        
        if "inventory" in requirements:
            steps.append(PlanStep(
                step_id=generate_id("step"),
                agent_type=AgentType.INVENTORY,
                action="check_inventory",
                description="Check inventory levels",
                dependencies=[],
                estimated_duration_seconds=3.0,
                trust_level_required=TrustLevel.AUTO_EXECUTE_LOW_RISK
            ))
        
        return steps
    
    async def _validate_plan(self, steps: List[Any]) -> Dict[str, Any]:
        """Validate the plan."""
        step_ids = [s.step_id for s in steps]
        
        for step in steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    return {"valid": False, "error": f"Dependency {dep} not found"}
        
        return {"valid": True}
    
    async def _optimize_plan(self, steps: List[Any]) -> List[Any]:
        """Optimize the plan."""
        # In a real implementation, this would optimize the step order
        # For now, just return the steps as-is
        return steps
    
    def _generate_plan_id(self) -> str:
        """Generate a plan ID."""
        from packages.shared_types.utils import generate_id
        return generate_id("plan")


class AgentRegistry:
    """
    Registry for managing agent information.
    
    This service:
    - Tracks registered agents
    - Provides agent information
    - Manages agent health checks
    """
    
    def __init__(self):
        self._agents: Dict[AgentType, AgentInfo] = {}
        
    async def initialize(self):
        """Initialize the registry."""
        # Register default agents
        await self._register_default_agents()
        
    async def _register_default_agents(self):
        """Register the default Lanework agents."""
        default_agents = [
            AgentInfo(
                agent_type=AgentType.SHIPMENT_TRACKING,
                name="Shipment Tracking Agent",
                description="Aggregates multi-carrier tracking into one timeline, detects delays proactively, answers status questions conversationally.",
                version="1.0.0",
                endpoint="/agents/shipment-tracking",
                capabilities=[
                    "track_shipments",
                    "detect_delays",
                    "answer_status_questions",
                    "process_carrier_webhooks"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.INVENTORY,
                name="Inventory Management Agent",
                description="Monitors stock across warehouses, predicts depletion, generates replenishment recommendations, reconciles discrepancies.",
                version="1.0.0",
                endpoint="/agents/inventory",
                capabilities=[
                    "monitor_inventory",
                    "predict_depletion",
                    "generate_replenishment",
                    "reconcile_discrepancies"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.ROUTE_OPTIMIZATION,
                name="Route Optimization Agent",
                description="Generates and dynamically re-optimizes multi-stop routes against vehicle capacity, time windows, and driver hours.",
                version="1.0.0",
                endpoint="/agents/route-optimization",
                capabilities=[
                    "generate_routes",
                    "reoptimize_routes",
                    "check_capacity",
                    "check_time_windows"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.WAREHOUSE_OPS,
                name="Warehouse Operations Agent",
                description="Optimizes pick/pack sequencing, assigns tasks, manages dock scheduling, forecasts labor needs.",
                version="1.0.0",
                endpoint="/agents/warehouse-ops",
                capabilities=[
                    "optimize_pick_pack",
                    "assign_tasks",
                    "manage_dock_schedule",
                    "forecast_labor"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.FLEET_MANAGEMENT,
                name="Fleet & Driver Management Agent",
                description="Tracks vehicle maintenance windows and driver HOS compliance, matches drivers to routes, flags compliance risk.",
                version="1.0.0",
                endpoint="/agents/fleet-management",
                capabilities=[
                    "track_maintenance",
                    "check_hos_compliance",
                    "match_drivers",
                    "flag_compliance_risk"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.CUSTOMER_COMMUNICATION,
                name="Customer Communication Agent",
                description="Handles tier-1 status/ETA/POD requests over chat and email, escalates sentiment-negative cases, drafts proactive delay notices.",
                version="1.0.0",
                endpoint="/agents/customer-communication",
                capabilities=[
                    "handle_status_requests",
                    "escalate_cases",
                    "draft_notices",
                    "analyze_sentiment"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.DEMAND_FORECASTING,
                name="Demand Forecasting Agent",
                description="Forecasts demand by SKU/region/season, feeds signal to Inventory and Fleet agents.",
                version="1.0.0",
                endpoint="/agents/demand-forecasting",
                capabilities=[
                    "forecast_demand",
                    "analyze_trends",
                    "generate_insights"
                ],
                trust_level=TrustLevel.AUTO_EXECUTE_LOW_RISK,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.FREIGHT_PROCUREMENT,
                name="Freight / Carrier Procurement Agent",
                description="Solicits and compares carrier quotes, recommends carrier selection, tracks carrier performance.",
                version="1.0.0",
                endpoint="/agents/freight-procurement",
                capabilities=[
                    "solicit_quotes",
                    "compare_quotes",
                    "recommend_carriers",
                    "track_performance"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            ),
            AgentInfo(
                agent_type=AgentType.VOICE,
                name="Voice Agent",
                description="Answers inbound phone calls and routes to appropriate agents. Built on LiveKit Agents.",
                version="1.0.0",
                endpoint="/agents/voice",
                capabilities=[
                    "answer_calls",
                    "route_voice_requests",
                    "transcribe_speech",
                    "synthesize_speech"
                ],
                trust_level=TrustLevel.PROPOSE_ONLY,
                is_active=True,
                last_heartbeat=datetime.utcnow()
            )
        ]
        
        for agent in default_agents:
            self._agents[agent.agent_type] = agent
        
    async def list_agents(self) -> List[AgentInfo]:
        """List all registered agents."""
        return list(self._agents.values())
    
    async def get_agent(self, agent_type: AgentType) -> Optional[AgentInfo]:
        """Get information about a specific agent."""
        return self._agents.get(agent_type)
    
    async def register_agent(self, agent_info: AgentInfo) -> AgentInfo:
        """Register a new agent."""
        self._agents[agent_info.agent_type] = agent_info
        return agent_info
    
    async def update_agent_heartbeat(self, agent_type: AgentType):
        """Update an agent's heartbeat."""
        if agent_type in self._agents:
            self._agents[agent_type].last_heartbeat = datetime.utcnow()


class GuardrailsEngine:
    """
    Engine for enforcing guardrails and policies.
    
    This service:
    - Validates actions against tenant policies
    - Checks for compliance violations
    - Enforces trust level requirements
    - Provides audit logging
    """
    
    def __init__(self):
        self._policies: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Initialize the engine."""
        # Load default policies
        await self._load_default_policies()
        
    async def _load_default_policies(self):
        """Load default guardrail policies."""
        # Default policies would be loaded from configuration
        self._policies = {
            "default": {
                "max_monetary_value": 1000.00,
                "max_route_deviation_minutes": 30,
                "max_inventory_adjustment_pct": 5.0,
                "allowed_actions": ["read", "query", "notify"],
                "restricted_actions": ["delete", "modify_contract", "process_payment"]
            }
        }
    
    async def check(self, request: GuardrailsCheckRequest) -> GuardrailsCheckResponse:
        """
        Check if an action is allowed by guardrails.
        
        Args:
            request: The guardrails check request
            
        Returns:
            GuardrailsCheckResponse with the check result
        """
        violations = []
        warnings = []
        
        # Get tenant policy
        policy = self._policies.get(request.tenant_id, self._policies.get("default", {}))
        
        # Check action type
        restricted_actions = policy.get("restricted_actions", [])
        if request.action_type in restricted_actions:
            violations.append(f"Action '{request.action_type}' is restricted")
        
        # Check trust level
        required_trust = self._get_required_trust_level(request.action_type)
        if request.trust_level.value < required_trust.value:
            violations.append(
                f"Trust level {request.trust_level.value} is insufficient. "
                f"Required: {required_trust.value}"
            )
        
        # Check monetary value if applicable
        if "monetary_value" in request.input_data:
            max_value = policy.get("max_monetary_value", 1000.00)
            if request.input_data["monetary_value"] > max_value:
                violations.append(
                    f"Monetary value {request.input_data['monetary_value']} "
                    f"exceeds maximum of {max_value}"
                )
        
        # Check route deviation if applicable
        if "route_deviation_minutes" in request.input_data:
            max_deviation = policy.get("max_route_deviation_minutes", 30)
            if request.input_data["route_deviation_minutes"] > max_deviation:
                warnings.append(
                    f"Route deviation {request.input_data['route_deviation_minutes']} "
                    f"exceeds recommended maximum of {max_deviation}"
                )
        
        # Determine if allowed
        allowed = len(violations) == 0
        
        return GuardrailsCheckResponse(
            allowed=allowed,
            violations=violations,
            warnings=warnings,
            required_trust_level=required_trust,
            recommended_action=None if allowed else "Request human approval"
        )
    
    def _get_required_trust_level(self, action_type: str) -> TrustLevel:
        """Get the required trust level for an action."""
        # Define trust level requirements for different actions
        high_risk_actions = [
            "process_payment",
            "modify_contract",
            "delete_data",
            "override_safety"
        ]
        
        medium_risk_actions = [
            "create_order",
            "assign_route",
            "adjust_inventory",
            "select_carrier"
        ]
        
        if action_type in high_risk_actions:
            return TrustLevel.FULLY_AUTONOMOUS
        elif action_type in medium_risk_actions:
            return TrustLevel.AUTO_EXECUTE_LOW_RISK
        else:
            return TrustLevel.PROPOSE_ONLY
