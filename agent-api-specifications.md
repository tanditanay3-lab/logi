# Agent API Specifications

Lanework — Detailed API specifications for all agents (§1–8 map to PRD §4.1–4.8)

## §0. Shared Types and Conventions

### AgentTask
The core audit and orchestration object. Every agent action produces exactly one AgentTask record.

```json
{
  "id": "task_<uuid>",
  "tenant_id": "tenant_<uuid>",
  "agent_type": "shipment-tracking|inventory|route-optimization|warehouse-ops|fleet-management|customer-communication|demand-forecasting|freight-procurement|voice",
  "action_type": "string, e.g., 'update_eta', 'create_replenishment_order', 'reoptimize_route'",
  "status": "pending_approval|approved|rejected|auto_executed|failed|completed",
  "trust_level": "propose_only|auto_execute_low_risk|fully_autonomous",
  "reasoning_trace": "string, full LLM reasoning trace for audit",
  "input_data": "object, the structured input that triggered this task",
  "output_data": "object, the result of the action (if executed)",
  "approval_request_id": "string | null, reference to ApprovalRequest if status is pending_approval",
  "related_entity_id": "string | null, e.g., shipment_id, route_id, inventory_item_id",
  "related_entity_type": "string | null, e.g., 'shipment', 'route', 'inventory_item'",
  "created_at": "iso8601",
  "updated_at": "iso8601",
  "completed_at": "iso8601 | null",
  "error_message": "string | null"
}
```

### ApprovalRequest
Tracks human approval workflows.

```json
{
  "id": "approval_<uuid>",
  "tenant_id": "tenant_<uuid>",
  "agent_task_id": "task_<uuid>",
  "agent_type": "string",
  "action_description": "string, human-readable summary of what needs approval",
  "status": "pending|approved|rejected|expired",
  "requested_by": "user_<uuid> | system",
  "approved_by": "user_<uuid> | null",
  "rejected_by": "user_<uuid> | null",
  "rejection_reason": "string | null",
  "created_at": "iso8601",
  "updated_at": "iso8601",
  "expires_at": "iso8601 | null"
}
```

### Conversation
Shared model for both chat and voice interactions.

```json
{
  "id": "conv_<uuid>",
  "tenant_id": "tenant_<uuid>",
  "channel": "chat|voice",
  "participant_type": "user|driver|customer|system",
  "participant_id": "string | null",
  "messages": [
    {
      "id": "msg_<uuid>",
      "role": "user|assistant|system",
      "content": "string",
      "timestamp": "iso8601",
      "metadata": "object | null"
    }
  ],
  "related_agent_task_ids": ["task_<uuid>"],
  "voice_call_id": "call_<uuid> | null",
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

### Config Object (Per-Agent)
All agents expose a common config shape at GET/PATCH `/config`.

```json
{
  "trust_level": "propose_only|auto_execute_low_risk|fully_autonomous",
  "auto_approval_thresholds": {
    "max_monetary_value": 1000.00,
    "max_route_deviation_minutes": 30,
    "max_inventory_adjustment_pct": 5
  },
  "notification_settings": {
    "email_enabled": true,
    "sms_enabled": true,
    "voice_enabled": false,
    "webhook_url": "string | null"
  },
  "integration_settings": {
    "carrier_webhook_enabled": true,
    "tms_sync_enabled": false,
    "telematics_enabled": false
  },
  "agent_specific": "object | null"
}
```

### Base API Conventions

- All endpoints return JSON
- All endpoints require `Authorization: Bearer <tenant_api_key>` header
- All endpoints include `X-Tenant-ID` header for explicit tenant context
- All POST/PUT/PATCH endpoints return the created/updated resource
- All list endpoints support `?tenant_id=<uuid>` filter (admin-only for cross-tenant queries)
- All endpoints support `?limit=100&offset=0` pagination
- Error format: `{ "error": { "code": "string", "message": "string", "details": {} } }`

### Webhook Events
All agents emit webhook events for significant state changes.

```json
{
  "event_id": "evt_<uuid>",
  "event_type": "string, e.g., 'shipment.status_updated', 'route.reoptimized'",
  "tenant_id": "tenant_<uuid>",
  "timestamp": "iso8601",
  "data": "object, event-specific payload",
  "agent_task_id": "task_<uuid> | null"
}
```

---

## §1. Shipment Tracking Agent

### Overview
Aggregates multi-carrier tracking into one timeline, detects delays proactively, answers status questions conversationally.

### Endpoints

#### GET /shipments
List all shipments for a tenant.

**Query Parameters:**
- `status`: filter by status (`pending|in_transit|delivered|cancelled|delayed`)
- `carrier`: filter by carrier
- `tracking_number`: filter by tracking number
- `created_after`: ISO8601 timestamp
- `created_before`: ISO8601 timestamp

**Response:**
```json
{
  "shipments": [
    {
      "id": "shipment_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "tracking_number": "string",
      "carrier": "string",
      "carrier_service": "string",
      "status": "pending|in_transit|delivered|cancelled|delayed",
      "origin": {"address": "string", "city": "string", "state": "string", "zip": "string", "country": "string"},
      "destination": {"address": "string", "city": "string", "state": "string", "zip": "string", "country": "string"},
      "estimated_delivery": "iso8601 | null",
      "actual_delivery": "iso8601 | null",
      "current_location": {"lat": 0.0, "lng": 0.0} | null,
      "events": [
        {
          "timestamp": "iso8601",
          "type": "string",
          "description": "string",
          "location": {"lat": 0.0, "lng": 0.0} | null,
          "carrier_timestamp": "iso8601 | null"
        }
      ],
      "eta_drift_minutes": 0 | null,
      "eta_drift_detected_at": "iso8601 | null",
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### GET /shipments/{shipment_id}
Get a single shipment with full details.

**Response:** Same as shipment object in list, plus:
```json
{
  "...": "...",
  "metadata": {
    "weight_lbs": 0.0,
    "dimensions": {"length": 0.0, "width": 0.0, "height": 0.0},
    "commodity": "string",
    "reference_numbers": ["string"]
  },
  "carrier_account": "string",
  "billing_reference": "string",
  "notes": "string"
}
```

#### POST /shipments
Create a new shipment for tracking.

**Request:**
```json
{
  "tracking_number": "string",
  "carrier": "string",
  "carrier_service": "string",
  "origin": {"address": "string", "city": "string", "state": "string", "zip": "string", "country": "string"},
  "destination": {"address": "string", "city": "string", "state": "string", "zip": "string", "country": "string"},
  "estimated_delivery": "iso8601 | null",
  "metadata": {
    "weight_lbs": 0.0,
    "dimensions": {"length": 0.0, "width": 0.0, "height": 0.0},
    "commodity": "string",
    "reference_numbers": ["string"]
  },
  "notes": "string"
}
```

**Response:** Created shipment object

#### PATCH /shipments/{shipment_id}
Update shipment fields.

**Request:** Partial shipment object

#### POST /shipments/{shipment_id}/events
Add a tracking event (from carrier webhook or manual entry).

**Request:**
```json
{
  "timestamp": "iso8601",
  "type": "string",
  "description": "string",
  "location": {"lat": 0.0, "lng": 0.0} | null,
  "carrier_timestamp": "iso8601 | null"
}
```

**Response:** Updated shipment with new event

#### POST /shipments/{shipment_id}/refresh
Trigger a refresh of tracking data from carrier.

**Response:**
```json
{
  "status": "queued|in_progress|completed|failed",
  "shipment_id": "shipment_<uuid>",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /shipments/{shipment_id}/notify
Send a status notification to customer.

**Request:**
```json
{
  "message_template": "string | null",
  "channels": ["email", "sms", "voice"],
  "recipient": {
    "email": "string | null",
    "phone": "string | null"
  }
}
```

**Response:**
```json
{
  "status": "queued|sent|failed",
  "notification_id": "string",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /carrier-webhook
Ingest carrier webhook payload.

**Headers:**
- `X-Carrier-Signature`: Carrier-specific signature for verification
- `X-Carrier`: Carrier name

**Request:** Carrier-specific payload (will be normalized internally)

**Response:**
```json
{
  "status": "received|processed|error",
  "shipment_id": "shipment_<uuid> | null",
  "tracking_number": "string | null",
  "events_created": 0,
  "agent_task_id": "task_<uuid> | null"
}
```

### Trust Level Rules (§1.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Create shipment | Propose | Auto-execute | Auto-execute |
| Update shipment status from carrier | Auto-execute | Auto-execute | Auto-execute |
| Add tracking event | Auto-execute | Auto-execute | Auto-execute |
| Refresh tracking data | Propose | Auto-execute | Auto-execute |
| Send customer notification | Propose | Auto-execute | Auto-execute |
| Detect and flag ETA drift | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `shipment.created`
- `shipment.updated`
- `shipment.status_changed`
- `shipment.eta_drift_detected`
- `shipment.delivered`
- `shipment.delayed`

---

## §2. Inventory Management Agent

### Overview
Monitors stock across warehouses, predicts depletion, generates replenishment recommendations, reconciles discrepancies.

### Endpoints

#### GET /inventory/items
List inventory items.

**Query Parameters:**
- `warehouse_id`: filter by warehouse
- `sku`: filter by SKU
- `low_stock`: boolean, filter by low stock items
- `category`: filter by category

**Response:**
```json
{
  "items": [
    {
      "id": "inventory_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "sku": "string",
      "name": "string",
      "description": "string",
      "category": "string",
      "warehouse_id": "warehouse_<uuid>",
      "location": "string",
      "quantity_on_hand": 0,
      "quantity_reserved": 0,
      "quantity_available": 0,
      "reorder_point": 0,
      "reorder_quantity": 0,
      "unit_cost": 0.00,
      "unit_of_measure": "string",
      "last_updated": "iso8601",
      "low_stock_alert": true,
      "expiry_date": "iso8601 | null",
      "batch_number": "string | null",
      "status": "active|inactive|quarantined"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### GET /inventory/items/{item_id}
Get a single inventory item.

**Response:** Same as item object in list, plus:
```json
{
  "...": "...",
  "supplier": {
    "id": "supplier_<uuid>",
    "name": "string",
    "lead_time_days": 0
  },
  "demand_forecast": {
    "daily_average": 0.0,
    "weekly_trend": 0.0,
    "seasonal_factor": 0.0
  },
  "movement_history": [
    {
      "timestamp": "iso8601",
      "type": "receipt|issue|adjustment|transfer",
      "quantity": 0,
      "reference": "string",
      "user_id": "user_<uuid> | null"
    }
  ]
}
```

#### POST /inventory/items
Create a new inventory item.

**Request:**
```json
{
  "sku": "string",
  "name": "string",
  "description": "string",
  "category": "string",
  "warehouse_id": "warehouse_<uuid>",
  "location": "string",
  "quantity_on_hand": 0,
  "reorder_point": 0,
  "reorder_quantity": 0,
  "unit_cost": 0.00,
  "unit_of_measure": "string",
  "expiry_date": "iso8601 | null",
  "batch_number": "string | null",
  "supplier_id": "supplier_<uuid> | null"
}
```

#### PATCH /inventory/items/{item_id}
Update inventory item.

#### POST /inventory/items/{item_id}/adjust
Adjust inventory quantity.

**Request:**
```json
{
  "adjustment_type": "receipt|issue|adjustment|transfer|shrinkage|damage",
  "quantity": 0,
  "reason": "string",
  "reference": "string | null",
  "target_warehouse_id": "warehouse_<uuid> | null"
}
```

**Response:**
```json
{
  "item_id": "inventory_<uuid>",
  "new_quantity_on_hand": 0,
  "movement_id": "movement_<uuid>",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /inventory/items/{item_id}/reserve
Reserve inventory for an order.

**Request:**
```json
{
  "quantity": 0,
  "order_id": "order_<uuid>",
  "reservation_id": "string | null"
}
```

**Response:**
```json
{
  "item_id": "inventory_<uuid>",
  "reserved_quantity": 0,
  "reservation_id": "string",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /inventory/items/{item_id}/release
Release reserved inventory.

**Request:**
```json
{
  "quantity": 0,
  "reservation_id": "string"
}
```

#### POST /inventory/replenishment-recommendations
Generate replenishment recommendations.

**Request:**
```json
{
  "warehouse_id": "warehouse_<uuid> | null",
  "category": "string | null",
  "horizon_days": 30
}
```

**Response:**
```json
{
  "recommendations": [
    {
      "item_id": "inventory_<uuid>",
      "sku": "string",
      "current_quantity": 0,
      "recommended_order_quantity": 0,
      "urgency": "low|medium|high|critical",
      "lead_time_days": 0,
      "estimated_cost": 0.00,
      "reason": "string"
    }
  ],
  "generated_at": "iso8601",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /inventory/discrepancies
Report a stock discrepancy.

**Request:**
```json
{
  "item_id": "inventory_<uuid>",
  "expected_quantity": 0,
  "actual_quantity": 0,
  "discrepancy_type": "overage|shortage|damage|expired",
  "location": "string",
  "notes": "string"
}
```

**Response:**
```json
{
  "discrepancy_id": "discrepancy_<uuid>",
  "item_id": "inventory_<uuid>",
  "status": "reported|investigating|resolved",
  "agent_task_id": "task_<uuid>"
}
```

### Trust Level Rules (§2.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Create inventory item | Propose | Auto-execute | Auto-execute |
| Adjust inventory quantity | Propose | Auto-execute (within threshold) | Auto-execute |
| Reserve inventory | Propose | Auto-execute | Auto-execute |
| Release inventory | Propose | Auto-execute | Auto-execute |
| Generate replenishment recommendations | Auto-execute | Auto-execute | Auto-execute |
| Report discrepancy | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `inventory.item.created`
- `inventory.item.updated`
- `inventory.quantity_adjusted`
- `inventory.reserved`
- `inventory.released`
- `inventory.low_stock`
- `inventory.discrepancy_reported`
- `inventory.replenishment_recommended`

---

## §3. Route Optimization Agent

### Overview
Generates and dynamically re-optimizes multi-stop routes against vehicle capacity, time windows, and driver hours.

### Endpoints

#### GET /routes
List routes.

**Query Parameters:**
- `status`: `pending|assigned|in_progress|completed|cancelled`
- `driver_id`: filter by driver
- `vehicle_id`: filter by vehicle
- `date`: filter by route date
- `warehouse_id`: filter by origin warehouse

**Response:**
```json
{
  "routes": [
    {
      "id": "route_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "name": "string",
      "status": "pending|assigned|in_progress|completed|cancelled",
      "driver_id": "driver_<uuid> | null",
      "vehicle_id": "vehicle_<uuid> | null",
      "warehouse_id": "warehouse_<uuid>",
      "date": "date",
      "stops": [
        {
          "id": "stop_<uuid>",
          "sequence": 0,
          "location": {"address": "string", "lat": 0.0, "lng": 0.0},
          "type": "pickup|delivery|both",
          "time_window_start": "time | null",
          "time_window_end": "time | null",
          "estimated_arrival": "time | null",
          "actual_arrival": "time | null",
          "estimated_departure": "time | null",
          "actual_departure": "time | null",
          "shipment_ids": ["shipment_<uuid>"],
          "status": "pending|in_progress|completed|skipped",
          "notes": "string"
        }
      ],
      "total_distance_miles": 0.0,
      "total_duration_minutes": 0,
      "total_stops": 0,
      "optimization_score": 0.0,
      "created_at": "iso8601",
      "updated_at": "iso8601",
      "assigned_at": "iso8601 | null",
      "started_at": "iso8601 | null",
      "completed_at": "iso8601 | null"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### GET /routes/{route_id}
Get a single route with full details.

**Response:** Same as route object in list, plus:
```json
{
  "...": "...",
  "constraints": {
    "max_duration_minutes": 0,
    "max_distance_miles": 0.0,
    "vehicle_capacity_cubic_feet": 0.0,
    "vehicle_capacity_weight_lbs": 0.0,
    "driver_hours_available": 0.0
  },
  "metrics": {
    "fuel_cost": 0.00,
    "toll_cost": 0.00,
    "driver_pay": 0.00,
    "total_cost": 0.00
  },
  "reoptimization_history": [
    {
      "timestamp": "iso8601",
      "trigger": "manual|delay|driver_issue|traffic|weather",
      "changes": "string",
      "agent_task_id": "task_<uuid>"
    }
  ]
}
```

#### POST /routes
Create a new route (manually or from optimization).

**Request:**
```json
{
  "name": "string",
  "warehouse_id": "warehouse_<uuid>",
  "date": "date",
  "stops": [
    {
      "location": {"address": "string", "lat": 0.0, "lng": 0.0},
      "type": "pickup|delivery|both",
      "time_window_start": "time | null",
      "time_window_end": "time | null",
      "shipment_ids": ["shipment_<uuid>"],
      "notes": "string"
    }
  ],
  "constraints": {
    "max_duration_minutes": 0 | null,
    "max_distance_miles": 0.0 | null,
    "vehicle_capacity_cubic_feet": 0.0 | null,
    "vehicle_capacity_weight_lbs": 0.0 | null
  }
}
```

#### POST /routes/optimize
Generate optimized routes from a set of stops.

**Request:**
```json
{
  "warehouse_id": "warehouse_<uuid>",
  "date": "date",
  "stops": [
    {
      "location": {"address": "string", "lat": 0.0, "lng": 0.0},
      "type": "pickup|delivery|both",
      "time_window_start": "time | null",
      "time_window_end": "time | null",
      "shipment_ids": ["shipment_<uuid>"],
      "required_skills": ["string"],
      "weight_lbs": 0.0,
      "cubic_feet": 0.0
    }
  ],
  "drivers": [
    {
      "driver_id": "driver_<uuid>",
      "available_start": "time",
      "available_end": "time",
      "hos_remaining_minutes": 0,
      "skills": ["string"]
    }
  ],
  "vehicles": [
    {
      "vehicle_id": "vehicle_<uuid>",
      "capacity_cubic_feet": 0.0,
      "capacity_weight_lbs": 0.0,
      "fuel_type": "string",
      "fuel_efficiency_mpg": 0.0
    }
  ],
  "constraints": {
    "max_routes": 0 | null,
    "max_stops_per_route": 0 | null,
    "balance_load": true
  }
}
```

**Response:**
```json
{
  "routes": [
    {
      "id": "route_<uuid>",
      "stops": [...],
      "metrics": {...},
      "optimization_score": 0.0
    }
  ],
  "unassigned_stops": [...],
  "agent_task_id": "task_<uuid>"
}
```

#### POST /routes/{route_id}/reoptimize
Re-optimize an existing route.

**Request:**
```json
{
  "trigger": "manual|delay|driver_issue|traffic|weather|new_stop",
  "new_stop": {
    "location": {"address": "string", "lat": 0.0, "lng": 0.0},
    "type": "pickup|delivery|both",
    "time_window_start": "time | null",
    "time_window_end": "time | null"
  } | null,
  "removed_stop_ids": ["stop_<uuid>"] | null
}
```

**Response:** Same as optimize response

#### POST /routes/{route_id}/assign
Assign a route to a driver and vehicle.

**Request:**
```json
{
  "driver_id": "driver_<uuid>",
  "vehicle_id": "vehicle_<uuid>",
  "start_time": "time"
}
```

**Response:**
```json
{
  "route_id": "route_<uuid>",
  "driver_id": "driver_<uuid>",
  "vehicle_id": "vehicle_<uuid>",
  "assigned_at": "iso8601",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /routes/{route_id}/start
Mark a route as started.

#### POST /routes/{route_id}/complete
Mark a route as completed.

#### POST /routes/{route_id}/stops/{stop_id}/start
Mark a stop as started.

#### POST /routes/{route_id}/stops/{stop_id}/complete
Mark a stop as completed.

#### POST /routes/{route_id}/stops/{stop_id}/skip
Skip a stop.

**Request:**
```json
{
  "reason": "string"
}
```

### Trust Level Rules (§3.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Create route manually | Propose | Auto-execute | Auto-execute |
| Optimize routes | Propose | Auto-execute | Auto-execute |
| Re-optimize route (no stops in progress) | Propose | Auto-execute | Auto-execute |
| Re-optimize route (stops in progress) | Propose | Propose | Auto-execute |
| Assign route to driver | Propose | Propose | Auto-execute |
| Start/Complete route | Auto-execute | Auto-execute | Auto-execute |
| Skip stop | Propose | Propose | Auto-execute |

### Webhook Events

- `route.created`
- `route.optimized`
- `route.reoptimized`
- `route.assigned`
- `route.started`
- `route.completed`
- `route.stop.started`
- `route.stop.completed`
- `route.stop.skipped`

---

## §4. Warehouse Operations Agent

### Overview
Optimizes pick/pack sequencing, assigns tasks, manages dock scheduling, forecasts labor needs.

### Endpoints

#### GET /warehouse/tasks
List warehouse tasks.

**Query Parameters:**
- `warehouse_id`: filter by warehouse
- `status`: `pending|assigned|in_progress|completed|cancelled`
- `type`: `pick|pack|receive|putaway|count|move`
- `priority`: `low|medium|high|critical`
- `assigned_to`: filter by user/driver

**Response:**
```json
{
  "tasks": [
    {
      "id": "task_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "warehouse_id": "warehouse_<uuid>",
      "type": "pick|pack|receive|putaway|count|move",
      "status": "pending|assigned|in_progress|completed|cancelled",
      "priority": "low|medium|high|critical",
      "description": "string",
      "location": "string",
      "assigned_to": "user_<uuid> | null",
      "order_id": "order_<uuid> | null",
      "shipment_id": "shipment_<uuid> | null",
      "inventory_item_id": "inventory_<uuid> | null",
      "quantity": 0 | null,
      "estimated_duration_minutes": 0,
      "actual_duration_minutes": 0 | null,
      "due_at": "iso8601 | null",
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### POST /warehouse/tasks
Create a warehouse task.

**Request:**
```json
{
  "warehouse_id": "warehouse_<uuid>",
  "type": "pick|pack|receive|putaway|count|move",
  "priority": "low|medium|high|critical",
  "description": "string",
  "location": "string",
  "order_id": "order_<uuid> | null",
  "shipment_id": "shipment_<uuid> | null",
  "inventory_item_id": "inventory_<uuid> | null",
  "quantity": 0 | null,
  "estimated_duration_minutes": 0,
  "due_at": "iso8601 | null"
}
```

#### POST /warehouse/tasks/optimize
Optimize task sequencing for a warehouse.

**Request:**
```json
{
  "warehouse_id": "warehouse_<uuid>",
  "tasks": ["task_<uuid>"],
  "workers": [
    {
      "user_id": "user_<uuid>",
      "skills": ["string"],
      "available_start": "time",
      "available_end": "time"
    }
  ],
  "constraints": {
    "max_tasks_per_worker": 0 | null,
    "balance_workload": true,
    "prioritize_by_due": true
  }
}
```

**Response:**
```json
{
  "optimized_sequence": [
    {
      "task_id": "task_<uuid>",
      "sequence": 0,
      "assigned_to": "user_<uuid> | null",
      "start_time": "time | null"
    }
  ],
  "unassigned_tasks": ["task_<uuid>"],
  "agent_task_id": "task_<uuid>"
}
```

#### GET /warehouse/dock-schedule
Get dock scheduling.

**Query Parameters:**
- `warehouse_id`: filter by warehouse
- `date`: filter by date

**Response:**
```json
{
  "schedule": [
    {
      "id": "schedule_<uuid>",
      "warehouse_id": "warehouse_<uuid>",
      "dock_number": "string",
      "date": "date",
      "slots": [
        {
          "id": "slot_<uuid>",
          "start_time": "time",
          "end_time": "time",
          "status": "available|reserved|in_use|completed",
          "shipment_id": "shipment_<uuid> | null",
          "carrier": "string | null",
          "vehicle_type": "string | null",
          "notes": "string"
        }
      ]
    }
  ]
}
```

#### POST /warehouse/dock-schedule
Create/update dock schedule.

#### POST /warehouse/labor-forecast
Generate labor forecast.

**Request:**
```json
{
  "warehouse_id": "warehouse_<uuid>",
  "start_date": "date",
  "end_date": "date",
  "historical_data_days": 30
}
```

**Response:**
```json
{
  "forecast": [
    {
      "date": "date",
      "estimated_tasks": 0,
      "estimated_hours": 0.0,
      "recommended_workers": 0,
      "by_task_type": {
        "pick": 0,
        "pack": 0,
        "receive": 0,
        "putaway": 0
      }
    }
  ],
  "agent_task_id": "task_<uuid>"
}
```

### Trust Level Rules (§4.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Create warehouse task | Propose | Auto-execute | Auto-execute |
| Optimize task sequencing | Propose | Auto-execute | Auto-execute |
| Assign task to worker | Propose | Propose | Auto-execute |
| Update dock schedule | Propose | Propose | Auto-execute |
| Generate labor forecast | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `warehouse.task.created`
- `warehouse.task.assigned`
- `warehouse.task.completed`
- `warehouse.tasks.optimized`
- `warehouse.dock_schedule.updated`
- `warehouse.labor_forecast.generated`

---

## §5. Fleet & Driver Management Agent

### Overview
Tracks vehicle maintenance windows and driver HOS compliance, matches drivers to routes, flags compliance risk.

### Endpoints

#### GET /fleet/drivers
List drivers.

**Query Parameters:**
- `status`: `active|inactive|on_leave`
- `warehouse_id`: filter by home warehouse

**Response:**
```json
{
  "drivers": [
    {
      "id": "driver_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "name": "string",
      "license_number": "string",
      "license_state": "string",
      "license_expiry": "date",
      "status": "active|inactive|on_leave",
      "home_warehouse_id": "warehouse_<uuid> | null",
      "skills": ["string"],
      "hos_status": {
        "current_duty_hours": 0.0,
        "current_drive_hours": 0.0,
        "remaining_duty_hours": 0.0,
        "remaining_drive_hours": 0.0,
        "last_reset": "iso8601",
        "status": "ok|warning|violation"
      },
      "phone": "string",
      "email": "string",
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### GET /fleet/drivers/{driver_id}
Get a single driver with full details.

**Response:** Same as driver object in list, plus:
```json
{
  "...": "...",
  "hos_history": [
    {
      "timestamp": "iso8601",
      "event_type": "duty_on|duty_off|drive_start|drive_end|break_start|break_end",
      "duration_minutes": 0,
      "location": {"lat": 0.0, "lng": 0.0} | null,
      "notes": "string"
    }
  ],
  "violations": [
    {
      "id": "violation_<uuid>",
      "type": "string",
      "severity": "warning|violation",
      "timestamp": "iso8601",
      "description": "string",
      "resolved": true
    }
  ],
  "assigned_route_id": "route_<uuid> | null",
  "current_vehicle_id": "vehicle_<uuid> | null"
}
```

#### POST /fleet/drivers/{driver_id}/hos-update
Update HOS status.

**Request:**
```json
{
  "event_type": "duty_on|duty_off|drive_start|drive_end|break_start|break_end",
  "timestamp": "iso8601",
  "duration_minutes": 0 | null,
  "location": {"lat": 0.0, "lng": 0.0} | null,
  "notes": "string"
}
```

**Response:**
```json
{
  "driver_id": "driver_<uuid>",
  "hos_status": {...},
  "agent_task_id": "task_<uuid>"
}
```

#### GET /fleet/vehicles
List vehicles.

**Query Parameters:**
- `status`: `active|inactive|maintenance`
- `warehouse_id`: filter by home warehouse

**Response:**
```json
{
  "vehicles": [
    {
      "id": "vehicle_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "name": "string",
      "vin": "string",
      "license_plate": "string",
      "type": "truck|van|cargo_van|box_truck|semi",
      "status": "active|inactive|maintenance",
      "home_warehouse_id": "warehouse_<uuid> | null",
      "capacity_cubic_feet": 0.0,
      "capacity_weight_lbs": 0.0,
      "fuel_type": "string",
      "fuel_efficiency_mpg": 0.0,
      "odometer": 0,
      "maintenance_status": {
        "last_service": "iso8601 | null",
        "next_service_due": "iso8601 | null",
        "next_service_miles": 0 | null,
        "status": "ok|warning|overdue"
      },
      "telematics": {
        "device_id": "string | null",
        "last_location": {"lat": 0.0, "lng": 0.0} | null,
        "last_update": "iso8601 | null",
        "speed_mph": 0.0 | null,
        "engine_hours": 0.0 | null
      },
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### POST /fleet/vehicles/{vehicle_id}/maintenance
Log maintenance event.

**Request:**
```json
{
  "type": "preventive|corrective|inspection",
  "description": "string",
  "odometer": 0,
  "cost": 0.00,
  "next_service_due_miles": 0 | null,
  "next_service_due_date": "date | null"
}
```

#### POST /fleet/drivers/{driver_id}/assign-vehicle
Assign driver to vehicle.

**Request:**
```json
{
  "vehicle_id": "vehicle_<uuid>",
  "route_id": "route_<uuid> | null"
}
```

#### POST /fleet/drivers/{driver_id}/check-hos
Check HOS compliance for a potential route assignment.

**Request:**
```json
{
  "route_id": "route_<uuid>",
  "estimated_duration_minutes": 0
}
```

**Response:**
```json
{
  "driver_id": "driver_<uuid>",
  "route_id": "route_<uuid>",
  "compliant": true,
  "remaining_hours_after": 0.0,
  "warnings": ["string"],
  "agent_task_id": "task_<uuid>"
}
```

#### POST /fleet/alerts
List compliance alerts.

**Response:**
```json
{
  "alerts": [
    {
      "id": "alert_<uuid>",
      "type": "hos_violation|maintenance_overdue|license_expiry",
      "severity": "low|medium|high|critical",
      "entity_type": "driver|vehicle",
      "entity_id": "string",
      "description": "string",
      "timestamp": "iso8601",
      "acknowledged": true,
      "acknowledged_by": "user_<uuid> | null",
      "acknowledged_at": "iso8601 | null"
    }
  ]
}
```

### Trust Level Rules (§5.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Update HOS status | Auto-execute | Auto-execute | Auto-execute |
| Log maintenance | Propose | Auto-execute | Auto-execute |
| Assign driver to vehicle | Propose | Propose | Auto-execute |
| Check HOS compliance | Auto-execute | Auto-execute | Auto-execute |
| Generate compliance alerts | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `fleet.driver.hos_updated`
- `fleet.driver.assigned`
- `fleet.vehicle.maintenance_logged`
- `fleet.vehicle.assigned`
- `fleet.compliance.alert`
- `fleet.hos.violation`

---

## §6. Customer Communication Agent

### Overview
Handles tier-1 status/ETA/POD requests over chat and email, escalates sentiment-negative cases, drafts proactive delay notices.

### Endpoints

#### GET /customer/conversations
List customer conversations.

**Query Parameters:**
- `customer_id`: filter by customer
- `status`: `open|closed|escalated`
- `channel`: `chat|email|voice`

**Response:**
```json
{
  "conversations": [
    {
      "id": "conv_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "customer_id": "customer_<uuid>",
      "channel": "chat|email|voice",
      "status": "open|closed|escalated",
      "subject": "string",
      "messages": [
        {
          "id": "msg_<uuid>",
          "role": "customer|assistant|system",
          "content": "string",
          "timestamp": "iso8601",
          "sentiment": "positive|neutral|negative | null",
          "intent": "string | null"
        }
      ],
      "assigned_to": "user_<uuid> | null",
      "priority": "low|medium|high|critical",
      "related_shipment_ids": ["shipment_<uuid>"],
      "created_at": "iso8601",
      "updated_at": "iso8601",
      "closed_at": "iso8601 | null"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### POST /customer/conversations/{conversation_id}/reply
Send a reply to a customer conversation.

**Request:**
```json
{
  "content": "string",
  "channel": "chat|email|voice",
  "template_id": "string | null"
}
```

**Response:**
```json
{
  "conversation_id": "conv_<uuid>",
  "message_id": "msg_<uuid>",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /customer/conversations/{conversation_id}/escalate
Escalate a conversation to human.

**Request:**
```json
{
  "reason": "string",
  "priority": "low|medium|high|critical",
  "assign_to": "user_<uuid> | null"
}
```

**Response:**
```json
{
  "conversation_id": "conv_<uuid>",
  "escalation_id": "escalation_<uuid>",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /customer/notifications
Send a proactive notification to a customer.

**Request:**
```json
{
  "customer_id": "customer_<uuid>",
  "shipment_id": "shipment_<uuid> | null",
  "type": "delay|delivery_confirmation|pickup_confirmation|exception",
  "message": "string",
  "channels": ["email", "sms", "voice"],
  "template_id": "string | null"
}
```

**Response:**
```json
{
  "notification_id": "notification_<uuid>",
  "status": "queued|sent|failed",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /customer/sentiment-analysis
Analyze sentiment of a message.

**Request:**
```json
{
  "message": "string",
  "conversation_id": "conv_<uuid> | null"
}
```

**Response:**
```json
{
  "sentiment": "positive|neutral|negative",
  "confidence": 0.0,
  "intent": "string | null",
  "agent_task_id": "task_<uuid>"
}
```

### Trust Level Rules (§6.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Send customer reply | Propose | Auto-execute | Auto-execute |
| Escalate conversation | Auto-execute | Auto-execute | Auto-execute |
| Send proactive notification | Propose | Auto-execute | Auto-execute |
| Analyze sentiment | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `customer.conversation.created`
- `customer.conversation.closed`
- `customer.conversation.escalated`
- `customer.notification.sent`
- `customer.sentiment.negative_detected`

---

## §7. Demand Forecasting Agent

### Overview
Forecasts demand by SKU/region/season, feeds signal to Inventory and Fleet agents.

### Endpoints

#### GET /forecasts
List demand forecasts.

**Query Parameters:**
- `sku`: filter by SKU
- `warehouse_id`: filter by warehouse
- `start_date`: filter by start date
- `end_date`: filter by end date

**Response:**
```json
{
  "forecasts": [
    {
      "id": "forecast_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "sku": "string",
      "warehouse_id": "warehouse_<uuid> | null",
      "start_date": "date",
      "end_date": "date",
      "granularity": "daily|weekly|monthly",
      "forecast_values": [
        {
          "date": "date",
          "forecasted_quantity": 0.0,
          "confidence_interval_lower": 0.0,
          "confidence_interval_upper": 0.0,
          "actual_quantity": 0.0 | null
        }
      ],
      "model_version": "string",
      "accuracy_score": 0.0 | null,
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### POST /forecasts
Generate a new forecast.

**Request:**
```json
{
  "sku": "string | null",
  "warehouse_id": "warehouse_<uuid> | null",
  "start_date": "date",
  "end_date": "date",
  "granularity": "daily|weekly|monthly",
  "historical_data_days": 365,
  "seasonality_adjustment": true
}
```

**Response:**
```json
{
  "forecast_id": "forecast_<uuid>",
  "status": "queued|generating|completed|failed",
  "agent_task_id": "task_<uuid>"
}
```

#### POST /forecasts/{forecast_id}/retrain
Retrain forecast model with new data.

**Request:**
```json
{
  "additional_data": [
    {
      "date": "date",
      "actual_quantity": 0.0
    }
  ]
}
```

#### GET /forecasts/insights
Get forecasting insights.

**Query Parameters:**
- `warehouse_id`: filter by warehouse
- `start_date`: filter by start date
- `end_date`: filter by end date

**Response:**
```json
{
  "insights": [
    {
      "type": "trend|seasonality|anomaly|outlier",
      "sku": "string",
      "warehouse_id": "warehouse_<uuid> | null",
      "description": "string",
      "severity": "low|medium|high",
      "start_date": "date",
      "end_date": "date",
      "recommended_action": "string"
    }
  ],
  "generated_at": "iso8601",
  "agent_task_id": "task_<uuid>"
}
```

### Trust Level Rules (§7.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Generate forecast | Auto-execute | Auto-execute | Auto-execute |
| Retrain model | Propose | Auto-execute | Auto-execute |
| Generate insights | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `forecast.generated`
- `forecast.retrained`
- `forecast.insights_generated`

---

## §8. Freight / Carrier Procurement Agent

### Overview
Solicits and compares carrier quotes, recommends carrier selection, tracks carrier performance.

### Endpoints

#### GET /freight/quotes
List freight quotes.

**Query Parameters:**
- `shipment_id`: filter by shipment
- `status`: `requested|received|expired|selected|rejected`
- `carrier_id`: filter by carrier

**Response:**
```json
{
  "quotes": [
    {
      "id": "quote_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "shipment_id": "shipment_<uuid> | null",
      "carrier_id": "carrier_<uuid>",
      "carrier_name": "string",
      "service_level": "string",
      "transit_time_hours": 0.0,
      "cost": 0.00,
      "currency": "string",
      "status": "requested|received|expired|selected|rejected",
      "expires_at": "iso8601 | null",
      "requested_at": "iso8601",
      "received_at": "iso8601 | null",
      "notes": "string"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### POST /freight/quotes
Request quotes from carriers.

**Request:**
```json
{
  "shipment_id": "shipment_<uuid> | null",
  "origin": {"address": "string", "city": "string", "state": "string", "zip": "string", "country": "string"},
  "destination": {"address": "string", "city": "string", "state": "string", "zip": "string", "country": "string"},
  "weight_lbs": 0.0,
  "dimensions": {"length": 0.0, "width": 0.0, "height": 0.0},
  "commodity": "string",
  "service_level": "standard|expedited|overnight",
  "carrier_ids": ["carrier_<uuid>"] | null,
  "pickup_date": "date | null",
  "delivery_date": "date | null"
}
```

**Response:**
```json
{
  "quote_request_id": "quote_request_<uuid>",
  "status": "queued|requesting|completed|failed",
  "quotes_requested": 0,
  "agent_task_id": "task_<uuid>"
}
```

#### POST /freight/quotes/{quote_id}/select
Select a carrier quote.

**Request:**
```json
{
  "notes": "string"
}
```

**Response:**
```json
{
  "quote_id": "quote_<uuid>",
  "status": "selected",
  "shipment_id": "shipment_<uuid> | null",
  "agent_task_id": "task_<uuid>"
}
```

#### GET /freight/carriers
List carriers.

**Response:**
```json
{
  "carriers": [
    {
      "id": "carrier_<uuid>",
      "tenant_id": "tenant_<uuid>",
      "name": "string",
      "carrier_type": "ltl|ftl|parcel|courier",
      "services": ["string"],
      "contact": {
        "phone": "string",
        "email": "string",
        "website": "string"
      },
      "performance": {
        "on_time_delivery_rate": 0.0,
        "average_transit_time_hours": 0.0,
        "claims_rate": 0.0,
        "average_cost_per_shipment": 0.00
      },
      "contract_terms": {
        "rates": "string | null",
        "min_charge": 0.00,
        "fuel_surcharge": 0.0
      },
      "status": "active|inactive",
      "created_at": "iso8601",
      "updated_at": "iso8601"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```

#### POST /freight/carriers
Create a new carrier.

**Request:**
```json
{
  "name": "string",
  "carrier_type": "ltl|ftl|parcel|courier",
  "services": ["string"],
  "contact": {
    "phone": "string",
    "email": "string",
    "website": "string"
  },
  "contract_terms": {
    "rates": "string | null",
    "min_charge": 0.00,
    "fuel_surcharge": 0.0
  }
}
```

#### GET /freight/carriers/{carrier_id}/performance
Get carrier performance metrics.

**Query Parameters:**
- `start_date`: filter by start date
- `end_date`: filter by end date

**Response:**
```json
{
  "carrier_id": "carrier_<uuid>",
  "performance": {
    "total_shipments": 0,
    "on_time_deliveries": 0,
    "on_time_delivery_rate": 0.0,
    "average_transit_time_hours": 0.0,
    "late_deliveries": 0,
    "average_lateness_hours": 0.0,
    "claims": 0,
    "claims_rate": 0.0,
    "average_cost_per_shipment": 0.00,
    "total_spend": 0.00
  },
  "period": {
    "start_date": "date",
    "end_date": "date"
  }
}
```

### Trust Level Rules (§8.6)

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Request quotes | Auto-execute | Auto-execute | Auto-execute |
| Select carrier quote | Propose | Propose | Auto-execute (within threshold) |
| Create carrier | Propose | Propose | Auto-execute |
| Update carrier performance | Auto-execute | Auto-execute | Auto-execute |

### Webhook Events

- `freight.quote.requested`
- `freight.quote.received`
- `freight.quote.selected`
- `freight.carrier.created`
- `freight.carrier.performance_updated`

---

## Voice Agent Specification

The Voice Agent (§4.9) uses the same Conversation Router as Chat Copilot. It exposes no additional domain-specific endpoints beyond those defined in §1–8 above. Voice-specific functionality is handled through:

1. **LiveKit Agent Integration**: STT/TTS/SIP handling
2. **VoiceCall entity**: Defined in PRD §6.1
3. **Conversation entity extension**: Added `channel` field to support voice

### Voice-Specific Endpoints

#### POST /voice/calls
Initiate an outbound call (requires tenant opt-in).

**Request:**
```json
{
  "phone_number": "string",
  "caller_type": "driver|customer|dispatcher",
  "intent": "string",
  "message": "string | null",
  "agent_type": "shipment-tracking|route-optimization|fleet-management|customer-communication"
}
```

**Response:**
```json
{
  "call_id": "call_<uuid>",
  "status": "queued|dialing|in_progress|completed|failed",
  "agent_task_id": "task_<uuid>"
}
```

#### GET /voice/calls/{call_id}
Get call details.

**Response:**
```json
{
  "id": "call_<uuid>",
  "tenant_id": "tenant_<uuid>",
  "direction": "inbound|outbound",
  "caller_type": "driver|customer|dispatcher|unknown",
  "phone_number": "string",
  "transcript": "string | null",
  "structured_intent": {
    "agent_routed_to": "string | null",
    "extracted_request": "string | null",
    "confidence": 0.0
  },
  "duration_seconds": 0 | null,
  "escalated_to_human": true,
  "recording_url": "string | null",
  "related_agent_task_ids": ["task_<uuid>"],
  "status": "queued|dialing|in_progress|completed|failed",
  "timestamp": "iso8601",
  "ended_at": "iso8601 | null"
}
```

### Voice Trust Level Rules

| Action | propose_only | auto_execute_low_risk | fully_autonomous |
|--------|--------------|----------------------|------------------|
| Answer inbound call (status query) | Auto-execute | Auto-execute | Auto-execute |
| Route to agent | Auto-execute | Auto-execute | Auto-execute |
| Log driver issue | Auto-execute | Auto-execute | Auto-execute |
| Trigger re-optimization | Propose | Auto-execute | Auto-execute |
| Make outbound call | Propose | Propose | Auto-execute |
| Handle complaint/contract | Never (human transfer) | Never (human transfer) | Never (human transfer) |
