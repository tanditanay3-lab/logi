# Lanework

**Lanework** is a multi-tenant agentic operating system for logistics companies. It provides a coordinated team of nine AI agents that run continuously in the background, making low-risk decisions autonomously and escalating everything else to a human.

## Features

- **9 Specialized Agents**: Shipment Tracking, Inventory Management, Route Optimization, Warehouse Operations, Fleet & Driver Management, Customer Communication, Demand Forecasting, Freight Procurement, and Voice
- **Multi-Channel Access**: Dashboard, Chat Copilot, Voice Agent (phone-based), and Public API
- **Human-in-the-Loop**: Configurable trust levels with approval workflows
- **Full Observability**: Every decision logged with reasoning traces for audit
- **Multi-Tenant**: Strict per-tenant data isolation with row-level security

## Architecture

```
                              ┌───────────────────────────────────────┐
                              │              Client Layer               │
                              │  Dashboard | Chat Copilot | Voice (SIP) │
                              │        Public/Partner API               │
                              └──────────────────┬───────────────────────┘
                                                 │
                              ┌──────────────────▼───────────────────┐
                              │            API Gateway                 │
                              │  Auth · Rate limiting · Tenant routing │
                              └──────────────────┬───────────────────┘
                                                 │
                    ┌─────────────────────────────▼───────────────────────────────┐
                    │                 Agent Orchestration Layer (LangGraph)          │
                    │  ┌────────────────┐  ┌───────────────┐  ┌──────────────────┐ │
                    │  │ Conversation    │  │ Voice I/O      │  │ Task/Event        │ │
                    │  │ Router          │  │ (LiveKit STT/  │  │ Orchestrator       │ │
                    │  │ (chat + voice)  │  │  TTS bridge)   │  │ (autonomous)       │ │
                    │  └────────────────┘  └───────────────┘  └──────────────────┘ │
                    │  Agent Registry · Planner · Guardrails/Policy Engine            │
                    └───┬───────┬───────┬───────┬───────┬───────┬───────┬───────────┘
                        │       │       │       │       │       │       │
                   ┌─────▼┐ ┌───▼───┐ ┌─▼────┐ ┌▼──────┐ ┌▼─────┐ ┌▼──────┐ ┌▼────────┐
                   │Inven-│ │Shipmnt│ │Route │ │Wareh. │ │Fleet │ │Custmr │ │Forecast/│
                   │tory  │ │Track  │ │Optim.│ │Ops    │ │Mgmt  │ │Comms  │ │Procure. │
                   └───┬──┘ └───┬───┘ └──┬───┘ └───┬───┘ └──┬───┘ └───┬───┘ └────┬────┘
                       │        │        │         │        │         │          │
                    ┌───▼────────▼────────▼─────────▼────────▼─────────▼──────────▼───┐
                    │        Tool / Integration Bus (MCP-standardized)                  │
                    │  Carrier APIs · TMS/WMS/ERP · Maps/Traffic · Telematics ·         │
                    │  Payment/Procurement APIs · Telephony (SIP trunk)                 │
                    └────────────────────────────┬───────────────────────────────────────┘
                                                  │
                    ┌──────────────────────────────▼──────────────────────────────────┐
                    │                          Data Layer                                │
                    │  Tenant-partitioned Postgres · Event stream (Kafka) · Vector       │
                    │  store (memory) · Time-series (metrics) · Object storage (POD,     │
                    │  call recordings/transcripts)                                       │
                    └────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | LangGraph + LangSmith |
| Voice | LiveKit Agents (STT/TTS/SIP) |
| Tool Bus | MCP (Model Context Protocol) |
| API Gateway | FastAPI |
| Database | PostgreSQL (row-level security) |
| Event Streaming | Kafka |
| Frontend | React + Tailwind |
| Observability | OpenTelemetry + Grafana + LangSmith |
| Containerization | Docker + Kubernetes |

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (for Python dependency management)
- Docker and Docker Compose
- PostgreSQL 15+
- Node.js 18+ (for dashboard)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd lanework
   ```

2. **Install Python dependencies**:
   ```bash
   make install
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**:
   ```bash
   make migrate
   make seed
   ```

5. **Start services**:
   ```bash
   make docker-up
   ```
   or for local development:
   ```bash
   make dev
   ```

### Access the Services

- **API Gateway**: http://localhost:8080
- **Orchestrator**: http://localhost:8000
- **Shipment Tracking Agent**: http://localhost:8001
- **Dashboard**: http://localhost:3000

## Development

### Project Structure

```
lanework/
├── apps/
│   ├── api-gateway/          # Main API Gateway
│   ├── orchestrator/         # LangGraph orchestration layer
│   ├── voice-gateway/        # LiveKit voice integration
│   └── dashboard/            # React frontend
├── agents/
│   ├── shipment-tracking/    # Shipment Tracking Agent
│   ├── inventory-management/ # Inventory Management Agent
│   ├── route-optimization/   # Route Optimization Agent
│   ├── warehouse-ops/        # Warehouse Operations Agent
│   ├── fleet-management/     # Fleet & Driver Management Agent
│   ├── customer-support/     # Customer Communication Agent
│   ├── demand-forecasting/   # Demand Forecasting Agent
│   └── freight-procurement/   # Freight/Carrier Procurement Agent
├── packages/
│   ├── shared-types/         # Shared schemas and types
│   ├── tool-bus/             # MCP tool bus implementation
│   └── db/                  # Database models and utilities
├── docs/                    # Documentation
├── docker-compose.yml       # Docker Compose configuration
├── Makefile                 # Common development tasks
└── README.md
```

### Running Tests

```bash
# Run all tests
make test

# Run unit tests
make test-unit

# Run integration tests
make test-integration

# Run end-to-end tests
make test-e2e
```

### Code Quality

```bash
# Linting
make lint

# Formatting
make format
```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/lanework

# API Keys
API_KEY=your-api-key
JWT_SECRET=your-jwt-secret

# LiveKit (for voice)
LIVEKIT_HOST=localhost
LIVEKIT_PORT=7880
LIVEKIT_API_KEY=your-livekit-key
LIVEKIT_API_SECRET=your-livekit-secret

# Trust Level (propose_only, auto_execute_low_risk, fully_autonomous)
TRUST_LEVEL=propose_only

# Observability
OTEL_ENABLED=true
OTEL_ENDPOINT=http://localhost:4317
```

### Trust Levels

Each agent can be configured with one of three trust levels:

- **propose_only**: All actions require human approval
- **auto_execute_low_risk**: Low-risk actions are auto-executed, others require approval
- **fully_autonomous**: All actions are auto-executed (use with caution)

## API Documentation

All services expose OpenAPI documentation:

- API Gateway: http://localhost:8080/docs
- Orchestrator: http://localhost:8000/docs
- Shipment Tracking: http://localhost:8001/docs

## Phased Roadmap

### Phase 1 - Core Loop (MVP)
- Shipment Tracking Agent
- Inventory Management Agent
- Route Optimization Agent
- Dashboard + Chat Copilot
- LangGraph orchestration foundation

### Phase 2 - Expand Coverage
- Warehouse Operations Agent
- Fleet & Driver Management Agent
- Customer Communication Agent
- Public API for partners

### Phase 3 - Voice
- Voice Agent (LiveKit)
- Inbound status queries
- Driver issue reporting
- Outbound notification calls

### Phase 4 - Predictive & Procurement
- Demand Forecasting Agent
- Freight/Carrier Procurement Agent
- Full cross-agent workflows

### Phase 5 - Scale & Autonomy
- Expanded connector library
- Higher autonomy levels
- Enterprise features (SSO, custom SLAs)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue in the GitHub repository or contact the development team.

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) for orchestration
- Voice powered by [LiveKit](https://github.com/livekit/livekit) for real-time communication
- Tool integration using [MCP](https://github.com/modelcontextprotocol/python-sdk) for standardization
