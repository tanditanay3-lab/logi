# Lanework — Master Product Requirements Document

The Agentic Operating System for Logistics

Version: 1.0 (Master, consolidates prior drafts)
Status: Ready for engineering handoff
Supersedes: logistics-agentic-os-prd.md, agent-api-specifications.md (kept as detailed appendices — this document is the single source of truth for scope and architecture)


1. Executive Summary

Lanework is a multi-tenant agentic operating system for logistics companies. A coordinated team of nine AI agents — covering shipment tracking, inventory, route optimization, warehouse operations, fleet & driver management, customer communication, demand forecasting, freight procurement, and voice — runs continuously in the background of a logistics operation, making low-risk decisions autonomously and escalating everything else to a human.

It's accessed through a dashboard, an in-app chat copilot, a voice agent (phone-based, for drivers and customers who can't or won't use an app), and a public API so it plugs into whatever TMS/WMS/ERP a tenant already runs.

North star: a dispatcher should be able to call a phone number and say "where's truck 12" and get a spoken answer, exactly as fast as if they'd typed it into chat — and most of the time, nobody has to ask at all because the relevant agent already flagged it.


2. Product Principles

- Agents are modular services, not one giant prompt — independently deployable, versionable, testable.
- Shared runtime, isolated tenants — one control plane, strict per-tenant data isolation.
- Tool-use over hardcoding — agents act through a standardized Tool/Integration layer, not bespoke connectors.
- Human-in-the-loop by default, autonomous by configuration — every action is either auto-executed (trusted, low-risk) or proposed-then-approved, configurable per tenant.
- Everything is observable — every decision logged with a reasoning trace for audit.
- Voice is a first-class interface, not a bolt-on — drivers in a cab and dispatchers on a warehouse floor often can't type; the voice agent must reach full feature parity with chat over time.


3. Target Users

| Persona | Primary interface | What they need from Lanework |
|---------|------------------|------------------------------|
| Dispatcher | Dashboard + Chat + Voice | Real-time visibility, quick re-routing, exception handling |
| Warehouse Manager | Dashboard | Task queues, dock schedules, labor forecasts |
| Driver | Voice (hands-free, in-cab) | Route updates, HOS status, reporting delays/issues by talking |
| Ops/Fleet Manager | Dashboard | Compliance alerts, maintenance scheduling, approvals queue |
| Customer | Voice + Chat widget (embedded on tenant's site) | "Where's my order" without waiting on hold |
| Procurement Lead | Dashboard | Carrier quotes, performance history |
| Developer (tenant's IT team) | API | Wiring Lanework into existing TMS/WMS/ERP |


4. Problem Statements & Agent Modules

4.1 Shipment / Order Tracking Agent
Aggregates multi-carrier tracking into one timeline, detects delays proactively, answers status questions conversationally.

4.2 Inventory Management Agent
Monitors stock across warehouses, predicts depletion, generates replenishment recommendations, reconciles discrepancies.

4.3 Route Optimization Agent
Generates and dynamically re-optimizes multi-stop routes against vehicle capacity, time windows, and driver hours.

4.4 Warehouse Operations Agent
Optimizes pick/pack sequencing, assigns tasks, manages dock scheduling, forecasts labor needs.

4.5 Fleet & Driver Management Agent
Tracks vehicle maintenance windows and driver HOS compliance, matches drivers to routes, flags compliance risk.

4.6 Customer Communication Agent
Handles tier-1 status/ETA/POD requests over chat and email, escalates sentiment-negative cases, drafts proactive delay notices.

4.7 Demand Forecasting Agent
Forecasts demand by SKU/region/season, feeds signal to Inventory and Fleet agents.

4.8 Freight / Carrier Procurement Agent
Solicits and compares carrier quotes, recommends carrier selection, tracks carrier performance.

4.9 Voice Agent (new)
Pain it solves: Drivers can't safely type while driving. Many customers still call rather than use an app or portal. Dispatchers on a noisy warehouse floor want to talk, not tap. A pure text/dashboard product excludes all three.

What it does:
- Answers inbound phone calls (customers asking "where's my order," drivers checking in, dispatchers requesting status) and routes the request to the right underlying agent (Shipment Tracking, Route Optimization, Fleet, etc.) exactly like the Chat Copilot does — the Voice Agent is a speech interface on top of the same orchestration layer, not a separate brain.
- Makes outbound calls when configured to (e.g., a driver hasn't confirmed pickup, a customer needs a proactive delay call instead of just a text).
- Lets drivers report issues hands-free ("I'm stuck, this road is closed") which gets transcribed, structured, and routed to the Route Optimization Agent as a re-optimization trigger.
- Falls back to human transfer immediately on request, on repeated failure to understand, or on any interaction requiring judgment beyond its trust level (same escalation rules as every other agent — see §6).

Explicitly not in scope for v1: fully autonomous outbound sales/collections calls, or any voice interaction involving payment collection (handled by a human or a dedicated, separately-audited flow).


5. Agentic Framework Selection

5.1 Orchestration framework: LangGraph
Recommendation: build the Task/Event Orchestrator and Planner (PRD §3.3 components) on LangGraph.

Why: LangGraph pairs with LangChain for stateful multi-agent orchestration, and the LangChain ecosystem adds Deep Agents for long-running workflows and LangSmith for enterprise-grade observability and evaluation across the full application lifecycle. That combination maps directly onto Lanework's needs: our agents are long-running (a route stays "live" for hours), our workflows branch conditionally (approval required vs. auto-execute), and we need full observability per §8 of the original PRD (audit trail on every decision). LangGraph's orchestration model is a directed graph with conditional edges, which is a natural fit for the trust-level branching (propose_only / auto_execute / fully_autonomous) already specified for every agent.

5.2 Voice framework: LiveKit Agents
Recommendation: build the Voice Agent (§4.9) on LiveKit Agents.

Why: logistics voice use cases are inherently telephony-heavy (driver phone check-ins, customer calls) and sometimes multi-party (a dispatcher bridging a driver and a customer). LiveKit Agent Workflows is best for WebRTC-first architectures, teams that want voice-native performance without building a separate media stack, deployments that may also need SIP integration, and latency-sensitive production deployments — SIP support matters directly here since it's how the Voice Agent answers and places real phone calls, not just in-browser audio.

5.3 How voice plugs into the architecture
The Voice Agent does not get its own reasoning/orchestration logic. It is a transport + speech layer:

Phone call (SIP) → LiveKit Agent (STT → structured request) 
                 → Conversation Router (same one Chat Copilot uses, §3.3)
                 → routes to relevant domain agent(s) (Shipment Tracking, Route Opt, etc.)
                 → response → LiveKit Agent (TTS) → spoken back to caller

This keeps the "9 agents" framing honest to the underlying architecture: Voice is the 9th interface-plus-transcription agent, but it delegates all actual logistics reasoning to agents 4.1–4.8, exactly as the Chat Copilot does. This also means every voice interaction produces the same AgentTask audit record as any other channel (§0 of the API spec doc) — there is no separate, less-observable voice code path.


6. System Architecture

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

Everything from the original PRD's §3.3 (component responsibilities), §5 (data model), §8 (non-functional requirements), and §9 (tech stack) still applies — this section only adds the voice transport layer and names LangGraph/LiveKit/MCP explicitly where the original left the framework choice open.

6.1 Voice-specific data additions

```json
// VoiceCall
{
  "id": "call_...",
  "tenant_id": "tenant_...",
  "direction": "inbound | outbound",
  "caller_type": "driver | customer | dispatcher | unknown",
  "phone_number": "+1...",
  "transcript": "string, full transcript",
  "structured_intent": { "agent_routed_to": "shipment-tracking", "extracted_request": "..." },
  "duration_seconds": 142,
  "escalated_to_human": false,
  "recording_url": "s3://...",
  "related_agent_task_ids": ["task_..."],
  "timestamp": "iso8601"
}
```

6.2 Voice-specific approval/trust rules

- Answering factual questions (status, ETA, HOS remaining): auto-execute at all trust levels, same as chat.
- Logging a driver-reported issue and triggering a re-optimization: auto-execute, but always creates a pending_approval task if the re-optimization affects a route already in progress with other stops (matches §3.6 of the API spec doc).
- Any call involving a customer complaint, compensation, or contract terms: immediate transfer to a human — the Voice Agent never attempts to resolve these itself, regardless of trust level.
- Outbound calls: only placed for pre-approved reasons (§4.9) and tenant must explicitly opt in per use case (e.g., "allow outbound delay-notification calls" is a separate toggle from "allow outbound pickup-confirmation calls").


7. Core Data Model

Unchanged from the original PRD §5 (Tenant, User, Order, Shipment, InventoryItem, Warehouse, Vehicle, Driver, Route, Carrier, ForecastRecord, AgentTask, Conversation, ApprovalRequest), plus the new VoiceCall entity in §6.1 above. Conversation should be extended with a channel field (chat | voice) so both interfaces share the same conversation history model.


8. Representative Cross-Agent Workflows

Workflows 6.1–6.3 from the original PRD (order→delivery, delay detected, stock+demand spike) are unchanged. New voice-specific workflow:

8.1 "Driver reports a road closure by phone"
- Driver calls in → Voice Agent (LiveKit) transcribes: "Route 12 is closed, I need a new way to my next stop."
- Conversation Router extracts structured intent, routes to Route Optimization Agent.
- Route Agent checks Fleet Agent for HOS remaining, re-optimizes remaining stops.
- If the route is already in progress with other pending stops, a pending_approval AgentTask is created (per §6.2); otherwise auto-executes.
- Voice Agent reads the new route back to the driver over the phone; dashboard shows the same update in real time to the dispatcher.
- Customer Communication Agent is notified if any customer-facing ETA changed, and sends proactive updates per its own approval rules.


9. Interfaces

- Dashboard — full visibility, approval queue, config per PRD §7.
- Chat Copilot — text-based, same Conversation Router as Voice.
- Voice Agent — phone-based (SIP), same Conversation Router as Chat, built on LiveKit Agents (§5.2–5.3).
- Public/Partner API — unchanged from original PRD §7.


10. Non-Functional Requirements

All of original PRD §8 applies. Voice-specific additions:

- Latency: voice responses must stay under ~800ms turn-taking latency to feel conversational (industry-standard target for real-time voice, consistent with the sub-500ms-to-first-audio-chunk goal typical of production voice agents).
- Call recording & consent: recordings/transcripts stored in tenant-isolated object storage; tenant must configure consent/disclosure messaging per applicable regional call-recording laws (this varies by jurisdiction — flag as a legal review item, not an engineering default).
- Graceful degradation: if STT confidence is low or the caller's intent can't be matched to an agent, the Voice Agent says so explicitly and offers a human transfer rather than guessing.


11. Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Agent orchestration | LangGraph (+ LangSmith for observability) | §5.1 |
| Tool/integration standard | MCP | Used by all agents incl. voice, for uniform tool access |
| Voice | LiveKit Agents (STT/TTS/SIP) | §5.2 |
| API Gateway | Kong / AWS API Gateway | unchanged |
| Backend services | Python (FastAPI) | updated from "Node or Python" to Python for consistency with orchestration + voice stack |
| Relational DB | PostgreSQL (row-level security) | unchanged |
| Event streaming | Kafka | unchanged |
| Vector store | pgvector | unchanged |
| Time-series | TimescaleDB | unchanged |
| Frontend | React + Tailwind | unchanged |
| Observability | OpenTelemetry + Grafana + LangSmith | LangSmith added for orchestration-specific tracing |
| Infra | Kubernetes on AWS/GCP | unchanged |


12. Phased Roadmap

Phase 1 — Core Loop (MVP): Shipment Tracking + Inventory + Route Optimization agents, dashboard + chat copilot, LangGraph orchestration foundation, single reference TMS/WMS integration, manual-approval-by-default.

Phase 2 — Expand Coverage: Warehouse Ops + Fleet & Driver + Customer Communication agents; auto-execute trust tiers introduced; public API opened to early partners.

Phase 3 — Voice: Voice Agent built on LiveKit, wired into the existing Conversation Router — starts with inbound status queries only (lowest-risk), then adds driver issue-reporting, then outbound notification calls.

Phase 4 — Predictive & Procurement: Demand Forecasting + Freight/Carrier Procurement agents; full cross-agent workflows; multi-tenant self-serve onboarding.

Phase 5 — Scale & Autonomy: expanded connector library, higher autonomy levels based on accumulated trust data, enterprise features (SSO, schema-per-tenant, custom SLAs).


13. Success Metrics

Original PRD §11 metrics apply, plus voice-specific:

- % of inbound calls resolved without human transfer
- Average call handle time vs. prior human-staffed baseline
- Driver adoption rate of voice check-ins vs. app/text


14. Open Questions

- Which reference TMS/WMS/ERP for Phase 1 (pick based on design-partner customers)?
- Approval/override UX — Slack-style, in-dashboard, or both?
- Pricing model — per-agent, per-shipment, or flat tiers? (Voice may warrant its own usage-based add-on given telephony costs.)
- Regional call-recording consent requirements for target markets (legal review needed before Phase 3).
- Data residency requirements if operating outside one region.


This master document is the single source of truth for scope and architecture.
