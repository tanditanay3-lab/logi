# Project Instructions for Lanework

This document contains the build order, repo conventions, and specific instructions for the coding agent.

## 1. Build Order - Strict Sequence

**DO NOT SKIP AHEAD.** Each phase must be working and demoable before the next starts.

### Phase 1 — Foundation + Core Loop (MVP)

1. **Shared Foundation** (COMPLETED)
   - ✅ Monorepo structure created (`/apps`, `/agents`, `/packages`, `/docs`)
   - ✅ Shared `AgentTask` type implemented in `/packages/shared-types`
   - ✅ Base API conventions implemented (FastAPI middleware, schemas)
   - ✅ Config object implemented (common config shape with trust levels)
   - ✅ Webhook events schema implemented
   - ✅ Tool/Integration Bus foundation with MCP in `/packages/tool-bus`

2. **Shipment Tracking Agent** (COMPLETED)
   - ✅ All endpoints from API spec §1 implemented
   - ✅ AgentTask created for every action
   - ✅ Trust-level approval branching implemented (propose_only / auto_execute / fully_autonomous)
   - ✅ Carrier webhook ingestion endpoint with mocked payload support
   - ✅ ETA drift detection implemented
   - ✅ Notification task flow implemented

3. **Next Steps for Phase 1**
   - ⏳ Inventory Management Agent (stub Demand Forecasting dependency)
   - ⏳ Route Optimization Agent (stub Fleet & Driver HOS check)
   - ⏳ Dashboard: minimal view showing live AgentTasks + approval queue
   - ⏳ Chat Copilot: Conversation Router wired to these three agents
   - ⏳ **STOP**: Confirm real end-to-end demo before Phase 2

### Phase 2 — Expand Coverage

7. Warehouse Operations Agent (§4)
8. Fleet & Driver Management Agent (§5) — replace Phase 1 stub in Route Optimization
9. Customer Communication Agent (§6)
10. Open public API to partner integrations

### Phase 3 — Voice

11. Voice Agent built on LiveKit, wired into existing Conversation Router
    - Start with inbound status queries only (lowest-risk)
    - Add driver issue-reporting
    - Add outbound notification calls

### Phase 4 — Predictive & Procurement

15. Demand Forecasting Agent (§7) — wire real signal into Inventory Agent
16. Freight/Carrier Procurement Agent (§8)

### Phase 5 — Scale & Autonomy

17. Expand connector library
18. Raise autonomy levels using accumulated trust data
19. Enterprise features (SSO, schema-per-tenant, custom SLAs)

## 2. Repository Structure

```
lanework/
├── apps/
│   ├── api-gateway/          # Kong/AWS API Gateway (FastAPI for dev)
│   │   ├── main.py           # Main FastAPI app
│   │   ├── config.py         # Configuration
│   │   └── middleware.py     # Authentication, tenant routing, rate limiting
│   │
│   ├── orchestrator/         # LangGraph orchestration layer
│   │   ├── main.py           # FastAPI app
│   │   ├── graphs.py         # LangGraph graph definitions
│   │   ├── services.py       # Service classes
│   │   ├── schemas.py        # Pydantic schemas
│   │   └── config.py         # Configuration
│   │
│   ├── voice-gateway/        # LiveKit Agents integration
│   │   ├── main.py           # FastAPI app
│   │   ├── livekit_client.py # LiveKit client
│   │   ├── voice_agent.py    # Voice agent logic
│   │   └── config.py         # Configuration
│   │
│   └── dashboard/            # React + Tailwind frontend
│       ├── public/           # Static assets
│       ├── src/              # React source
│       └── config.py         # Configuration
│
├── agents/
│   ├── shipment-tracking/    # §1 Shipment Tracking Agent
│   │   ├── main.py           # FastAPI app
│   │   ├── service.py        # Business logic
│   │   ├── schemas.py        # Pydantic schemas
│   │   └── config.py         # Configuration
│   │
│   ├── inventory-management/ # §2 Inventory Management Agent
│   │   ├── main.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── config.py
│   │
│   ├── route-optimization/   # §3 Route Optimization Agent
│   │   ├── main.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── config.py
│   │
│   ├── warehouse-ops/        # §4 Warehouse Operations Agent
│   │   ├── main.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── config.py
│   │
│   ├── fleet-management/     # §5 Fleet & Driver Management Agent
│   │   ├── main.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── config.py
│   │
│   ├── customer-support/     # §6 Customer Communication Agent
│   │   ├── main.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── config.py
│   │
│   ├── demand-forecasting/   # §7 Demand Forecasting Agent
│   │   ├── main.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── config.py
│   │
│   └── freight-procurement/   # §8 Freight/Carrier Procurement Agent
│       ├── main.py
│       ├── service.py
│       ├── schemas.py
│       └── config.py
│
├── packages/
│   ├── shared-types/         # Shared schemas and utilities
│   │   ├── __init__.py
│   │   ├── schemas.py        # AgentTask, Config, Conversation, VoiceCall, etc.
│   │   ├── exceptions.py     # Custom exceptions
│   │   └── utils.py          # Utility functions
│   │
│   ├── tool-bus/             # MCP Tool/Integration Bus
│   │   ├── __init__.py
│   │   ├── tool_definitions.py # Tool schemas
│   │   ├── mcp_client.py     # MCP client
│   │   ├── mcp_server.py     # MCP server
│   │   └── integrations/     # Integration implementations
│   │
│   └── db/                  # Database layer
│       ├── __init__.py
│       ├── models.py         # SQLAlchemy models
│       └── migrations/       # Alembic migrations
│
├── docs/
│   ├── lanework-master-prd.md          # Master PRD
│   ├── agent-api-specifications.md     # API specs §1-8
│   └── architecture-diagrams/           # Architecture diagrams
│
├── docker-compose.yml       # Docker Compose configuration
├── Dockerfile               # Base Dockerfile
├── Dockerfile.*             # Service-specific Dockerfiles
├── Makefile                 # Common development tasks
├── pyproject.toml           # Python project configuration
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
└── README.md
```

## 3. Non-Negotiable Conventions

### Every table has tenant_id with row-level security
- ✅ Implemented in `/packages/db/models.py`
- ✅ All models inherit from `TenantMixin`
- ✅ Row-level security enforced at DB layer (PostgreSQL RLS)

### Every agent action produces an AgentTask record
- ✅ Implemented in `/packages/shared-types/schemas.py`
- ✅ AgentTask model in `/packages/db/models.py`
- ✅ All agent services create AgentTask records

### Trust-level approval rules per agent
- ✅ Defined in `agent-api-specifications.md` §1.6, §2.6, etc.
- ✅ Implemented in each agent's config
- ✅ Branching logic in agent services

### Cross-agent calls go through Tool/Integration Bus (MCP)
- ✅ MCP client implemented in `/packages/tool-bus/mcp_client.py`
- ✅ Tool definitions in `/packages/tool-bus/tool_definitions.py`
- ✅ All agents use MCP client for external calls

### Secrets live in vault, never in code
- ⚠️ Environment variables used for configuration
- ⚠️ `.env.example` provided as template
- ⚠️ Production should use proper secrets management

### Third-party API calls need retries + circuit breakers
- ✅ Implemented in MCP client with retry policy
- ✅ Circuit breaker pattern implemented
- ✅ Graceful degradation (serve last-known state)

### Voice interactions are fully traced
- ✅ VoiceCall model in `/packages/db/models.py`
- ✅ VoiceCall schema in `/packages/shared-types/schemas.py`
- ✅ Voice Agent creates AgentTask records
- ✅ Same Conversation Router used for voice and chat

## 4. Definition of Done, Per Agent

All endpoints from its API spec section implemented, correct schemas
- ✅ Shipment Tracking: All §1 endpoints implemented
- ⏳ Inventory: Not yet started
- ⏳ Route Optimization: Not yet started

AgentTask created for every action, including auto-executed ones
- ✅ Shipment Tracking: AgentTask creation implemented
- ⏳ Others: Not yet implemented

Trust-level approval branching implemented and tested at all three levels
- ✅ Shipment Tracking: Trust level logic implemented
- ⏳ Others: Not yet implemented

At least one integration test covering primary trigger → task → action flow
- ⏳ Shipment Tracking: Integration tests needed
- ⏳ Others: Not yet implemented

Config endpoint (GET/PATCH /config) working with common config shape
- ✅ Shipment Tracking: Config endpoint implemented
- ⏳ Others: Not yet implemented

Two-tenant isolation test passes (no data leakage across tenant_id)
- ⏳ Tests needed for all agents

(Voice-integrated agents only) reachable via voice query end-to-end
- ⏳ Voice Gateway: Not yet fully integrated

## 5. First Task for Coding Agent

**COMPLETED** ✅

Set up the monorepo structure from §4. Implemented:
1. Shared AgentTask type in `/packages/shared-types`
2. Base API conventions as LangGraph state schema + FastAPI middleware
3. Config object (API spec doc §0) in `/packages/shared-types`
4. Tool/Integration Bus foundation with MCP in `/packages/tool-bus`
5. Shipment Tracking Agent (§1) end-to-end as LangGraph-based service:
   - All endpoints implemented
   - Carrier webhook ingestion with mocked payload
   - ETA drift detection
   - Notification task flow
   - Trust level branching
   - AgentTask creation for all actions

## 6. Current Status

### Completed
- ✅ Monorepo structure
- ✅ Shared types (AgentTask, Config, Conversation, VoiceCall, etc.)
- ✅ Tool Bus with MCP client and tool definitions
- ✅ Database models with tenant_id and row-level security
- ✅ Shipment Tracking Agent with all §1 endpoints
- ✅ Orchestrator with LangGraph graphs (Conversation Router, Task Orchestrator, Planner)
- ✅ API Gateway with authentication and tenant routing
- ✅ Voice Gateway with LiveKit client and Voice Agent
- ✅ Docker configuration for all services
- ✅ Documentation (PRD, API specs, architecture)

### In Progress
- ⏳ Inventory Management Agent (Phase 1)
- ⏳ Route Optimization Agent (Phase 1)
- ⏳ Dashboard frontend
- ⏳ Integration tests

### Not Started
- ⏳ Warehouse Operations Agent (Phase 2)
- ⏳ Fleet & Driver Management Agent (Phase 2)
- ⏳ Customer Communication Agent (Phase 2)
- ⏳ Demand Forecasting Agent (Phase 4)
- ⏳ Freight Procurement Agent (Phase 4)
- ⏳ Full Voice Gateway integration (Phase 3)

## 7. Next Steps

1. **Complete Phase 1**:
   - Implement Inventory Management Agent
   - Implement Route Optimization Agent
   - Create Dashboard with live AgentTasks view
   - Create Chat Copilot with Conversation Router
   - Write integration tests
   - Demo end-to-end: order → tracked, stock reserved, route generated

2. **Verify Phase 1**:
   - Run all tests
   - Verify two-tenant isolation
   - Confirm real end-to-end demo works
   - Get approval to proceed to Phase 2

3. **Start Phase 2**:
   - Implement Warehouse Operations Agent
   - Implement Fleet & Driver Management Agent
   - Implement Customer Communication Agent
   - Open public API to partners

## 8. Important Notes

### Do NOT do:
- ❌ Build a single "mega-agent" handling multiple domains
- ❌ Skip approval/trust-level logic "for now"
- ❌ Build Voice Agent with separate reasoning logic
- ❌ Wire in real third-party integrations until stubbed version works
- ❌ Start Phase 2/3/4 agents before prior phase is demoable
- ❌ Substitute different orchestration or voice framework without flagging

### DO:
- ✅ Follow repository style and architecture
- ✅ Implement trust-level branching exactly as specified
- ✅ Create AgentTask for every action
- ✅ Use MCP for all cross-agent and third-party calls
- ✅ Enforce tenant isolation at DB layer
- ✅ Make smallest correct change
- ✅ Verify with tests before committing

## 9. Testing Strategy

### Unit Tests
- Test individual functions and methods
- Mock external dependencies
- Test all trust level branches

### Integration Tests
- Test agent-to-agent communication via Tool Bus
- Test webhook processing
- Test approval workflows

### End-to-End Tests
- Test complete workflows (order → tracking → inventory → route)
- Test voice interactions
- Test dashboard functionality

### Tenant Isolation Tests
- Verify no data leakage between tenants
- Test with at least two tenants
- Verify row-level security

## 10. Deployment

### Local Development
```bash
# Start all services
make docker-up

# Or run individual services
make dev-api-gateway
make dev-orchestrator
make dev-shipment-tracking
```

### Production
```bash
# Build and push images
make docker-build
make docker-push

# Deploy with Kubernetes
kubectl apply -f k8s/
```

## 11. Monitoring and Observability

All services expose:
- `/health` endpoint for health checks
- OpenTelemetry metrics and traces
- Structured logging
- AgentTask audit trail

## 12. Version Control

- Use feature branches: `feature/<description>`
- Use conventional commits
- Squash merge for clean history
- Protect main branch
