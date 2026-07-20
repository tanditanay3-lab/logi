# Lanework SaaS Layer

This document describes the SaaS shell built in front of the existing Lanework agent platform.

## Overview

The SaaS layer provides:
- **Authentication**: Neon Auth-based auth system
- **Multi-tenancy**: Organization-based isolation with RLS
- **Subscription Management**: Plan and subscription handling (Stripe integration ready)
- **Usage Metering**: Track usage for billing (future)
- **Feature Gating**: Plan-based access control (future)
- **Dashboard**: Customer-facing UI for managing organizations and users
- **Admin Console**: Internal operations tool (future)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                                │
├─────────────────────────────────────────────────────────────────┤
│  saas-dashboard (React + Tailwind)    admin-console (React)        │
│  - Onboarding flow                     - Account management         │
│  - Organization management            - Plan overrides              │
│  - Usage dashboard (future)           - Support tools               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SaaS API Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  saas-api (FastAPI)                                                  │
│  - Auth (Neon Auth)                                                  │
│  - Organization CRUD                                                 │
│  - Plan CRUD                                                         │
│  - User management                                                   │
│  - Subscription management (future)                                │
│  - Usage metering (future)                                           │
│  - Feature gating middleware (future)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                     │
├─────────────────────────────────────────────────────────────────┤
│  Neon Postgres (with RLS)                                            │
│  - organizations                                                     │
│  - plans                                                             │
│  - subscriptions (future)                                           │
│  - usage_records (future)                                           │
│  - saas_users                                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Platform (External)                        │
├─────────────────────────────────────────────────────────────────┤
│  - API Gateway                                                       │
│  - All 9 agents (Shipment, Inventory, Route, etc.)                   │
│  - Tool/Integration Bus                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
lanework/
├── apps/
│   ├── saas-api/              # FastAPI service for SaaS layer
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── config.py          # Configuration
│   │   ├── auth/              # Authentication (Neon Auth)
│   │   │   └── neon_auth.py   # Neon Auth integration
│   │   ├── routers/           # API routers
│   │   │   ├── organizations.py
│   │   │   ├── plans.py
│   │   │   ├── users.py
│   │   │   └── health.py
│   │   └── schemas.py         # Pydantic schemas
│   │
│   ├── saas-dashboard/        # React frontend
│   │   ├── src/              # React source
│   │   │   ├── pages/        # Page components
│   │   │   ├── layouts/      # Layout components
│   │   │   ├── components/   # UI components
│   │   │   └── lib/          # Utilities
│   │   └── package.json
│   │
│   └── admin-console/         # Admin console (future)
│
├── packages/
│   ├── saas-db/              # Database layer
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── database.py       # Database utilities
│   │   └── migrations/       # Alembic migrations
│   │
│   ├── agent-platform-client/  # Client for agent platform
│   │   ├── client.py         # HTTP client
│   │   └── schemas.py        # Pydantic schemas
│   │
│   └── billing-client/      # Stripe integration (stub)
│
└── docker-compose.saas.yml   # Docker Compose for SaaS services
```

## Tenant ID Format

The SaaS layer uses `org_<uuid>` format for organization IDs.

When calling the agent platform, these are converted to `tenant_<uuid>` format:

```python
# In agent-platform-client/client.py
def _format_tenant_id(self, org_id: str) -> str:
    if org_id.startswith("org_"):
        uuid_part = org_id[4:]
        return f"tenant_{uuid_part}"
    return f"tenant_{org_id}"
```

This ensures compatibility with the existing agent platform which expects `tenant_<uuid>`.

## Row-Level Security (RLS)

All SaaS tables have RLS policies enforced at the database level:

```sql
-- For organization-specific tables
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY sub_org_policy ON subscriptions 
FOR ALL USING (org_id = current_setting('app.current_org_id'));

-- For global tables (visible to all)
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_all_policy ON organizations 
FOR ALL USING (true);
```

The `app.current_org_id` setting is set at the start of each request based on the authenticated user's organization.

## Authentication Flow

1. User logs in via `/auth/login` with email/password
2. JWT token is generated and returned
3. Token is stored in localStorage (browser) or cookies
4. Subsequent requests include `Authorization: Bearer <token>` header
5. Auth middleware validates token and extracts user info
6. `org_id` is set for RLS context

## Onboarding Flow

1. User visits `/onboarding`
2. Enters organization name
3. Enters admin user details (email, name, password)
4. System creates:
   - Organization record
   - SaaS user record (with owner role)
   - JWT token
5. User is redirected to dashboard

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get token
- `GET /auth/me` - Get current user profile
- `POST /auth/logout` - Logout
- `POST /auth/refresh` - Refresh token

### Organizations
- `GET /organizations` - List organizations
- `POST /organizations` - Create organization
- `GET /organizations/{id}` - Get organization
- `PATCH /organizations/{id}` - Update organization
- `DELETE /organizations/{id}` - Delete organization

### Plans
- `GET /plans` - List plans
- `POST /plans` - Create plan
- `GET /plans/{id}` - Get plan
- `PATCH /plans/{id}` - Update plan
- `DELETE /plans/{id}` - Delete plan

### Users
- `GET /users` - List users in current org
- `POST /users` - Create user
- `GET /users/{id}` - Get user
- `PATCH /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

### Health
- `GET /health` - Health check
- `GET /health/db` - Database health check
- `GET /health/auth` - Auth health check

## Environment Variables

### SaaS API
```bash
# Database
SAAS_DATABASE_URL=postgresql+asyncpg://user:pass@host/db?sslmode=require

# Auth
NEON_AUTH_URL=https://auth.neon.tech
NEON_AUTH_PROJECT_ID=your-project-id
NEON_AUTH_API_KEY=your-api-key
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Agent Platform
AGENT_PLATFORM_URL=http://localhost:8001
AGENT_PLATFORM_API_KEY=your-api-key

# Server
HOST=0.0.0.0
PORT=8000
```

### SaaS Dashboard
```bash
VITE_API_URL=http://localhost:8000
```

## Running the SaaS Layer

### Development

```bash
# Start saas-api
make -f Makefile.saas dev-saas-api

# Start saas-dashboard (in another terminal)
cd apps/saas-dashboard
npm install
npm run dev

# Start admin-console (in another terminal)
cd apps/admin-console
npm install
npm run dev
```

### Docker

```bash
# Build and start all services
docker-compose -f docker-compose.saas.yml up -d --build

# Stop services
docker-compose -f docker-compose.saas.yml down
```

## Database Setup

### Initialize Database

```bash
# Run migrations
cd packages/saas-db
alembic upgrade head

# Or use the make command
make -f Makefile.saas db-migrate
```

### Create Migration

```bash
cd packages/saas-db
alembic revision --autogenerate -m "add_new_table"
```

## Testing

### Run Tests

```bash
# Run all saas-api tests
make -f Makefile.saas test-saas-api

# Or directly
cd apps/saas-api
python -m pytest tests/
```

## Future Work

The following features are planned but not yet implemented:

1. **Stripe Integration**
   - Checkout for plan selection
   - Webhook handlers for subscription events
   - Subscription status sync

2. **Usage Metering**
   - Consume agent platform events
   - Idempotent usage recording
   - Usage dashboard

3. **Feature Gating**
   - Middleware to check plan features
   - Grace period for past_due status
   - Fail-closed on unverifiable status

4. **Admin Console**
   - Full CRUD for accounts
   - Manual plan overrides
   - Support tools

5. **Self-serve Cancellation**
   - User-initiated cancellation
   - Stripe dunning settings

## Non-Negotiables (Implemented)

✅ Every new table has `org_id` with RLS enforced in Neon
✅ All agent-platform calls go through `/packages/agent-platform-client`
✅ Tenant ID format confirmed and mapped correctly
✅ Secrets in environment variables, never committed
✅ Follows existing repository style and architecture

## Non-Negotiables (Future)

⏳ Usage metering must be idempotent (dedupe by event ID)
⏳ Gating middleware fails closed on unverifiable plan/billing status
⏳ Stripe webhooks handled idempotently
⏳ RLS verified - one org can't see another's data
