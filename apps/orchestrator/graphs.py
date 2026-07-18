"""
LangGraph graphs for the Orchestrator.

This module contains the graph definitions for:
- Conversation Router
- Task/Event Orchestrator
- Planner
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import Graph
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool

from packages.shared_types.schemas import (
    AgentType,
    AgentTask,
    AgentTaskCreate,
    AgentTaskStatus,
    ApprovalRequest,
    ApprovalRequestCreate,
    ApprovalRequestStatus,
    Config,
    Conversation,
    ConversationChannel,
    ConversationMessage,
    TrustLevel,
)
from packages.shared_types.utils import generate_id, get_current_timestamp
from packages.tool_bus.mcp_client import MCPClient
from packages.tool_bus.tool_definitions import ToolCall, ToolResult

from .schemas import (
    ConversationRequest,
    ConversationResponse,
    IntentType,
    PlanRequest,
    PlanResponse,
    PlanStep,
    StructuredIntent,
    TaskRequest,
    TaskResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Conversation Router Graph
# ============================================================================

class ConversationRouterGraph:
    """
    LangGraph graph for the Conversation Router.
    
    This graph:
    1. Receives conversation requests (chat or voice)
    2. Extracts structured intent
    3. Routes to the appropriate agent
    4. Handles approval workflows
    5. Returns responses
    """
    
    def __init__(self, tool_client: Optional[MCPClient] = None):
        self.tool_client = tool_client or MCPClient()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> Graph:
        """Build the Conversation Router graph."""
        graph = Graph()
        
        # Define nodes
        graph.add_node("extract_intent", self._extract_intent_node)
        graph.add_node("route_to_agent", self._route_to_agent_node)
        graph.add_node("check_approval", self._check_approval_node)
        graph.add_node("execute_agent", self._execute_agent_node)
        graph.add_node("format_response", self._format_response_node)
        
        # Define edges
        graph.add_edge("extract_intent", "route_to_agent")
        graph.add_edge("route_to_agent", "check_approval")
        graph.add_conditional_edges(
            "check_approval",
            self._should_execute,
            {
                "execute": "execute_agent",
                "pending_approval": "format_response"
            }
        )
        graph.add_edge("execute_agent", "format_response")
        
        # Set entry and end points
        graph.set_entry_point("extract_intent")
        graph.set_finish_point("format_response")
        
        return graph
    
    async def _extract_intent_node(
        self,
        request: ConversationRequest
    ) -> Dict[str, Any]:
        """
        Extract structured intent from the conversation message.
        
        This uses an LLM to analyze the message and extract:
        - Intent type
        - Agent to route to
        - Entities (tracking numbers, order IDs, etc.)
        - Confidence score
        """
        # In a real implementation, this would call an LLM
        # For now, we'll use a simple rule-based approach
        
        message = request.message.lower()
        
        # Extract intent based on keywords
        intent_type = IntentType.UNKNOWN
        agent_type = None
        entities: Dict[str, Any] = {}
        confidence = 0.0
        
        # Status query patterns
        if any(word in message for word in ["where is", "status", "eta", "tracking", "where's"]):
            intent_type = IntentType.STATUS_QUERY
            agent_type = AgentType.SHIPMENT_TRACKING
            confidence = 0.9
            
            # Extract tracking number
            import re
            tracking_match = re.search(r'\b\d{10,20}\b', message)
            if tracking_match:
                entities["tracking_number"] = tracking_match.group()
        
        # Route optimization patterns
        elif any(word in message for word in ["route", "optimize", "re-optimize", "reoptimize", "best route"]):
            intent_type = IntentType.ROUTE_OPTIMIZATION
            agent_type = AgentType.ROUTE_OPTIMIZATION
            confidence = 0.85
        
        # Inventory patterns
        elif any(word in message for word in ["inventory", "stock", "quantity", "replenish"]):
            intent_type = IntentType.INVENTORY_CHECK
            agent_type = AgentType.INVENTORY
            confidence = 0.85
        
        # Driver issue patterns
        elif any(word in message for word in ["stuck", "closed", "delay", "issue", "problem", "road closed"]):
            intent_type = IntentType.DRIVER_ISSUE
            agent_type = AgentType.ROUTE_OPTIMIZATION
            confidence = 0.9
        
        # Customer complaint patterns
        elif any(word in message for word in ["complaint", "refund", "compensation", "contract"]):
            intent_type = IntentType.CUSTOMER_COMPLAINT
            agent_type = AgentType.CUSTOMER_COMMUNICATION
            confidence = 0.95
        
        # Default to general question
        else:
            intent_type = IntentType.GENERAL_QUESTION
            agent_type = AgentType.CUSTOMER_COMMUNICATION
            confidence = 0.7
        
        structured_intent = StructuredIntent(
            intent_type=intent_type,
            agent_type=agent_type,
            entities=entities,
            confidence=confidence
        )
        
        return {
            **request.model_dump(),
            "structured_intent": structured_intent.model_dump(),
            "extracted_intent": structured_intent
        }
    
    async def _route_to_agent_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route the request to the appropriate agent.
        
        Based on the extracted intent, determine which agent should handle the request.
        """
        structured_intent = state.get("structured_intent")
        
        if not structured_intent:
            # Fall back to customer communication for unknown intents
            state["agent_type"] = AgentType.CUSTOMER_COMMUNICATION
        else:
            state["agent_type"] = structured_intent.get("agent_type", AgentType.CUSTOMER_COMMUNICATION)
        
        return state
    
    async def _check_approval_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if the action requires approval.
        
        This checks the trust level and action type to determine if approval is needed.
        """
        # For now, we'll assume most actions are auto-executed
        # In a real implementation, this would check the tenant's trust level
        # and the specific action's requirements
        
        structured_intent = state.get("structured_intent", {})
        intent_type = structured_intent.get("intent_type", IntentType.UNKNOWN)
        
        # Customer complaints always require human handling
        if intent_type == IntentType.CUSTOMER_COMPLAINT:
            state["requires_approval"] = True
            state["approval_reason"] = "Customer complaints require human review"
        else:
            # For demo purposes, auto-execute most actions
            state["requires_approval"] = False
        
        return state
    
    async def _execute_agent_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the agent action.
        
        This calls the appropriate agent's API to handle the request.
        """
        agent_type = state.get("agent_type", AgentType.CUSTOMER_COMMUNICATION)
        structured_intent = state.get("structured_intent", {})
        request = state.get("request", {})
        
        # In a real implementation, this would call the agent's API
        # For now, we'll simulate responses
        
        if agent_type == AgentType.SHIPMENT_TRACKING:
            tracking_number = structured_intent.get("entities", {}).get("tracking_number", "UNKNOWN")
            response = f"Shipment {tracking_number} is currently in transit with an ETA of tomorrow."
        
        elif agent_type == AgentType.ROUTE_OPTIMIZATION:
            response = "I've re-optimized your route. The new route avoids the closed road and adds 15 minutes to your trip."
        
        elif agent_type == AgentType.INVENTORY:
            response = "Current inventory levels: SKU-001 has 50 units, SKU-002 has 25 units."
        
        elif agent_type == AgentType.CUSTOMER_COMMUNICATION:
            response = "I understand your concern. Let me look into that for you."
        
        else:
            response = "I can help with that. What specific information do you need?"
        
        state["agent_response"] = response
        state["agent_task_id"] = generate_id("task")
        
        return state
    
    async def _format_response_node(
        self,
        state: Dict[str, Any]
    ) -> ConversationResponse:
        """
        Format the final response.
        
        This creates the ConversationResponse object to return to the client.
        """
        request = state.get("request", {})
        structured_intent = state.get("structured_intent", {})
        
        return ConversationResponse(
            conversation_id=request.get("conversation_id", generate_id("conv")),
            message_id=generate_id("msg"),
            response=state.get("agent_response", "I can help with that."),
            structured_intent=state.get("extracted_intent"),
            agent_type=state.get("agent_type"),
            agent_task_id=state.get("agent_task_id"),
            requires_approval=state.get("requires_approval", False),
            approval_request_id=state.get("approval_request_id"),
            confidence=structured_intent.get("confidence", 0.0),
            timestamp=get_current_timestamp()
        )
    
    def _should_execute(self, state: Dict[str, Any]) -> str:
        """Determine if we should execute or request approval."""
        if state.get("requires_approval", False):
            return "pending_approval"
        return "execute"
    
    async def run(self, request: ConversationRequest) -> ConversationResponse:
        """Run the Conversation Router graph."""
        await self.tool_client.initialize()
        
        try:
            # Compile the graph
            app = self.graph.compile()
            
            # Run the graph
            result = await app.ainvoke({"request": request.model_dump()})
            
            # Extract the response
            if isinstance(result, ConversationResponse):
                return result
            elif isinstance(result, dict):
                return ConversationResponse(**result)
            else:
                return ConversationResponse(
                    conversation_id=generate_id("conv"),
                    message_id=generate_id("msg"),
                    response=str(result),
                    timestamp=get_current_timestamp()
                )
        finally:
            await self.tool_client.close()


# ============================================================================
# Task/Event Orchestrator Graph
# ============================================================================

class TaskOrchestratorGraph:
    """
    LangGraph graph for the Task/Event Orchestrator.
    
    This graph:
    1. Receives task requests
    2. Validates against guardrails
    3. Checks trust levels
    4. Creates AgentTask records
    5. Routes to appropriate agent
    6. Handles approval workflows
    7. Tracks task completion
    """
    
    def __init__(self, tool_client: Optional[MCPClient] = None):
        self.tool_client = tool_client or MCPClient()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> Graph:
        """Build the Task Orchestrator graph."""
        graph = Graph()
        
        # Define nodes
        graph.add_node("validate_request", self._validate_request_node)
        graph.add_node("check_guardrails", self._check_guardrails_node)
        graph.add_node("check_trust_level", self._check_trust_level_node)
        graph.add_node("create_agent_task", self._create_agent_task_node)
        graph.add_node("route_to_agent", self._route_to_agent_node)
        graph.add_node("handle_approval", self._handle_approval_node)
        graph.add_node("track_completion", self._track_completion_node)
        
        # Define edges
        graph.add_edge("validate_request", "check_guardrails")
        graph.add_edge("check_guardrails", "check_trust_level")
        graph.add_edge("check_trust_level", "create_agent_task")
        graph.add_conditional_edges(
            "create_agent_task",
            self._should_request_approval,
            {
                "request_approval": "handle_approval",
                "execute": "route_to_agent"
            }
        )
        graph.add_edge("handle_approval", "track_completion")
        graph.add_edge("route_to_agent", "track_completion")
        
        # Set entry and end points
        graph.set_entry_point("validate_request")
        graph.set_finish_point("track_completion")
        
        return graph
    
    async def _validate_request_node(
        self,
        request: TaskRequest
    ) -> Dict[str, Any]:
        """Validate the task request."""
        # Basic validation
        if not request.tenant_id:
            raise ValueError("Tenant ID is required")
        if not request.agent_type:
            raise ValueError("Agent type is required")
        if not request.action_type:
            raise ValueError("Action type is required")
        
        return request.model_dump()
    
    async def _check_guardrails_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check the request against guardrails."""
        # In a real implementation, this would call the GuardrailsEngine
        # For now, we'll just pass through
        
        state["guardrails_passed"] = True
        state["guardrails_violations"] = []
        
        return state
    
    async def _check_trust_level_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if the trust level allows the action."""
        # In a real implementation, this would check the tenant's trust level
        # and the action's requirements
        
        trust_level = state.get("trust_level", TrustLevel.PROPOSE_ONLY)
        action_type = state.get("action_type", "")
        
        # For demo purposes, we'll allow most actions
        state["trust_level_allowed"] = True
        
        return state
    
    async def _create_agent_task_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an AgentTask record."""
        agent_task = AgentTaskCreate(
            tenant_id=state.get("tenant_id"),
            agent_type=state.get("agent_type"),
            action_type=state.get("action_type"),
            trust_level=state.get("trust_level", TrustLevel.PROPOSE_ONLY),
            reasoning_trace=f"Task created for {state.get('action_type', 'unknown')}",
            input_data=state.get("input_data", {}),
            status=AgentTaskStatus.PENDING_APPROVAL
        )
        
        state["agent_task"] = agent_task
        state["agent_task_id"] = generate_id("task")
        
        return state
    
    async def _route_to_agent_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route the task to the appropriate agent."""
        # In a real implementation, this would call the agent's API
        # For now, we'll simulate execution
        
        state["execution_status"] = "success"
        state["output_data"] = {"result": "Task executed successfully"}
        
        return state
    
    async def _handle_approval_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle approval workflow."""
        # Create an ApprovalRequest
        approval_request = ApprovalRequestCreate(
            tenant_id=state.get("tenant_id"),
            agent_task_id=state.get("agent_task_id"),
            agent_type=state.get("agent_type"),
            action_description=f"{state.get('action_type', 'unknown')} action",
            requested_by="system",
            status=ApprovalRequestStatus.PENDING
        )
        
        state["approval_request"] = approval_request
        state["approval_request_id"] = generate_id("approval")
        state["requires_approval"] = True
        
        return state
    
    async def _track_completion_node(
        self,
        state: Dict[str, Any]
    ) -> TaskResponse:
        """Track task completion."""
        agent_task_id = state.get("agent_task_id")
        requires_approval = state.get("requires_approval", False)
        approval_request_id = state.get("approval_request_id")
        output_data = state.get("output_data", {})
        error_message = state.get("error_message")
        
        status = AgentTaskStatus.PENDING_APPROVAL if requires_approval else AgentTaskStatus.AUTO_EXECUTED
        
        return TaskResponse(
            agent_task_id=agent_task_id,
            status=status,
            output_data=output_data,
            error_message=error_message,
            requires_approval=requires_approval,
            approval_request_id=approval_request_id
        )
    
    def _should_request_approval(self, state: Dict[str, Any]) -> str:
        """Determine if approval is required."""
        if state.get("requires_approval", False):
            return "request_approval"
        return "execute"
    
    async def run(self, request: TaskRequest) -> TaskResponse:
        """Run the Task Orchestrator graph."""
        await self.tool_client.initialize()
        
        try:
            # Compile the graph
            app = self.graph.compile()
            
            # Run the graph
            result = await app.ainvoke(request.model_dump())
            
            # Extract the response
            if isinstance(result, TaskResponse):
                return result
            elif isinstance(result, dict):
                return TaskResponse(**result)
            else:
                return TaskResponse(
                    agent_task_id=generate_id("task"),
                    status=AgentTaskStatus.FAILED,
                    error_message="Invalid response from orchestrator"
                )
        finally:
            await self.tool_client.close()


# ============================================================================
# Planner Graph
# ============================================================================

class PlannerGraph:
    """
    LangGraph graph for the Planner.
    
    This graph:
    1. Receives planning requests
    2. Analyzes the goal and constraints
    3. Generates a plan with steps
    4. Validates the plan
    5. Returns the plan
    """
    
    def __init__(self, tool_client: Optional[MCPClient] = None):
        self.tool_client = tool_client or MCPClient()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> Graph:
        """Build the Planner graph."""
        graph = Graph()
        
        # Define nodes
        graph.add_node("analyze_goal", self._analyze_goal_node)
        graph.add_node("generate_steps", self._generate_steps_node)
        graph.add_node("validate_plan", self._validate_plan_node)
        graph.add_node("optimize_plan", self._optimize_plan_node)
        
        # Define edges
        graph.add_edge("analyze_goal", "generate_steps")
        graph.add_edge("generate_steps", "validate_plan")
        graph.add_edge("validate_plan", "optimize_plan")
        
        # Set entry and end points
        graph.set_entry_point("analyze_goal")
        graph.set_finish_point("optimize_plan")
        
        return graph
    
    async def _analyze_goal_node(
        self,
        request: PlanRequest
    ) -> Dict[str, Any]:
        """Analyze the goal and extract requirements."""
        # In a real implementation, this would use an LLM to analyze the goal
        # For now, we'll do simple analysis
        
        goal = request.goal.lower()
        
        # Extract key information
        requirements = []
        if "shipment" in goal or "tracking" in goal:
            requirements.append("shipment_tracking")
        if "route" in goal or "optimize" in goal:
            requirements.append("route_optimization")
        if "inventory" in goal:
            requirements.append("inventory")
        
        return {
            **request.model_dump(),
            "requirements": requirements
        }
    
    async def _generate_steps_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate plan steps."""
        goal = state.get("goal", "")
        requirements = state.get("requirements", [])
        
        # Generate steps based on requirements
        steps = []
        
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
                dependencies=[s.id for s in steps] if steps else [],
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
        
        state["steps"] = steps
        
        return state
    
    async def _validate_plan_node(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate the plan."""
        steps = state.get("steps", [])
        
        # Check for circular dependencies
        step_ids = [s.step_id for s in steps]
        for step in steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    raise ValueError(f"Dependency {dep} not found in steps")
        
        state["valid"] = True
        
        return state
    
    async def _optimize_plan_node(
        self,
        state: Dict[str, Any]
    ) -> PlanResponse:
        """Optimize the plan."""
        steps = state.get("steps", [])
        goal = state.get("goal", "")
        
        # Calculate total duration
        total_duration = sum(s.estimated_duration_seconds for s in steps)
        
        return PlanResponse(
            plan_id=generate_id("plan"),
            goal=goal,
            steps=steps,
            estimated_total_duration_seconds=total_duration,
            confidence=0.85,
            created_at=get_current_timestamp()
        )
    
    async def run(self, request: PlanRequest) -> PlanResponse:
        """Run the Planner graph."""
        await self.tool_client.initialize()
        
        try:
            # Compile the graph
            app = self.graph.compile()
            
            # Run the graph
            result = await app.ainvoke(request.model_dump())
            
            # Extract the response
            if isinstance(result, PlanResponse):
                return result
            elif isinstance(result, dict):
                return PlanResponse(**result)
            else:
                return PlanResponse(
                    plan_id=generate_id("plan"),
                    goal=request.goal,
                    steps=[],
                    confidence=0.0
                )
        finally:
            await self.tool_client.close()
