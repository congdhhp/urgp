# Architecture Decision Records (ADRs)
## Universal Release Governance Platform (URGP)

**Document Type:** Architecture Decision Records  
**Status:** APPROVED  
**Last Updated:** 2026-04-10

---

## ADR-001: Graph Storage Engine

### Status: ACCEPTED

### Context
The Traceability Hydrator constructs multi-dimensional graphs linking `Build_Manifest ↔ Artifacts ↔ Repositories ↔ Pull_Requests ↔ Issues`. We need to decide between a dedicated graph database (Neo4j) and a relational database with graph query capabilities (PostgreSQL with recursive CTEs and JSONB).

### Decision Drivers
- Operational complexity of running an additional database in production
- Team expertise and learning curve
- Query performance at expected scale (50-100 commits, 20-30 PRs, 15-20 issues per build)
- Infrastructure cost
- Backup and recovery integration

### Decision
**Use PostgreSQL with recursive CTEs and JSONB** for graph storage.

### Rationale
1. **Scale doesn't justify Neo4j**: Typical build traceability graphs have < 200 nodes and < 500 edges. PostgreSQL handles this trivially with recursive CTEs.
2. **Operational simplicity**: One database to manage, backup, monitor, and scale. Adding Neo4j doubles database operations overhead.
3. **JSONB flexibility**: PostgreSQL's JSONB columns provide schema-flexible metadata storage with indexing support via GIN indexes.
4. **Unified transactions**: Build manifest creation + artifact registration + graph construction can occur in a single database transaction.
5. **Team familiarity**: PostgreSQL is universally understood; Neo4j requires Cypher query language expertise.

### Consequences
- **Positive**: Simpler operations, lower cost, single backup strategy, transactional consistency.
- **Negative**: Complex graph traversals (> 5 hops) may require careful CTE optimization. If graph complexity grows significantly (> 10,000 nodes per build), we would revisit this decision.
- **Migration path**: Graph data is stored in normalized tables (`commits`, `pull_requests`, `issues`, `traceability_edges`). If Neo4j is needed later, data can be exported via ETL.

---

## ADR-002: Message Broker

### Status: ACCEPTED

### Context
The Event Gateway requires a message broker to decouple the Execution Edge (CLI) from the Control Plane. Options considered: Apache Kafka and RabbitMQ.

### Decision Drivers
- Expected event volume (realistically < 1000 events/day at full enterprise scale)
- Operational complexity
- Message ordering requirements
- Dead letter queue support
- Replay capability
- Team expertise

### Decision
**Use RabbitMQ** as the primary message broker.

### Rationale
1. **Right-sized for the workload**: URGP processes build events (not real-time streaming data). RabbitMQ handles 10,000+ msg/sec, far exceeding realistic needs.
2. **Superior DLQ support**: RabbitMQ has native Dead Letter Exchange (DLX) with automatic routing. Kafka DLQ requires custom implementation.
3. **Simpler operations**: RabbitMQ is a single process with built-in management UI. Kafka requires ZooKeeper/KRaft, topic partitioning strategy, consumer group management.
4. **Message acknowledgment**: RabbitMQ provides per-message acknowledgment, ensuring no message is lost even if the Control Plane crashes mid-processing.
5. **Lower resource footprint**: RabbitMQ requires ~256MB RAM minimum vs Kafka's multi-GB requirement.

### Consequences
- **Positive**: Simpler deployment, native DLQ, lower resource usage, built-in management UI.
- **Negative**: No native log replay (unlike Kafka's offset-based replay). Mitigated by storing processed events in PostgreSQL for audit replay.
- **Migration path**: The Event Gateway abstracts the broker behind an interface. Switching to Kafka later requires only a new adapter implementation.

---

## ADR-003: Backend Framework

### Status: ACCEPTED

### Context
The Control Plane, Event Gateway, and AI Gateway all require a Python web framework. Options considered: FastAPI and Flask.

### Decision Drivers
- Async support for external API calls (Git/Jira with high latency)
- Automatic OpenAPI specification generation
- Performance under concurrent load
- Type safety and validation
- Community and ecosystem maturity

### Decision
**Use FastAPI** as the backend framework.

### Rationale
1. **Native async/await**: The Traceability Hydrator makes many concurrent API calls to Git providers and issue trackers. FastAPI's native async support enables parallel execution without threading complexity.
2. **Automatic OpenAPI**: FastAPI generates OpenAPI 3.0 specs from Pydantic models — directly satisfying Requirement 19.1 with zero additional effort.
3. **Pydantic integration**: Request/response validation using Pydantic models provides strong type safety at runtime, critical for Data Contract validation.
4. **Performance**: FastAPI on Uvicorn delivers 2-5x higher throughput than Flask for async workloads (benchmarked by TechEmpower).
5. **Dependency injection**: Built-in DI system simplifies testing and tenant context propagation.

### Consequences
- **Positive**: Async performance, auto-generated API docs, Pydantic validation, WebSocket support for MCP.
- **Negative**: Smaller ecosystem than Flask for some niche plugins. Mitigated by FastAPI's compatibility with most ASGI middleware.

---

## ADR-004: Frontend Framework & Libraries

### Status: ACCEPTED

### Context
The Self-Service Portal requires a modern SPA framework. The high-level solution mentioned both React and Vue.

### Decision
**Use React with TypeScript** as the frontend framework.

### Supporting Libraries
| Concern | Library | Rationale |
|---------|---------|-----------|
| State Management | **TanStack Query (React Query)** | Server state caching and synchronization; avoids Redux boilerplate for a read-heavy portal |
| UI Components | **Ant Design** | Enterprise-grade component library with table, form, and layout components suited for data-heavy UIs |
| Graph Visualization | **React Flow** | Purpose-built for node-edge graphs; easier than D3.js for interactive traceability visualization |
| HTTP Client | **Axios** | Interceptors for JWT injection, retry logic, error handling |
| Routing | **React Router v6** | Standard routing solution with nested routes and loaders |
| Charts | **Recharts** | Lightweight charts for build metrics and trends |
| Build Tool | **Vite** | Fast HMR, TypeScript-first, smaller bundle than Create React App |

### Rationale
1. **React over Vue**: Larger ecosystem, more enterprise adoption, easier to find experienced developers.
2. **TanStack Query over Redux**: Portal is primarily read-heavy with server-driven data. TanStack Query provides caching, background refetching, and optimistic updates without Redux's boilerplate.
3. **React Flow over D3.js**: D3 is low-level and has a steep learning curve. React Flow provides declarative graph rendering with built-in pan/zoom, minimap, and node/edge interactivity — directly suited for traceability graph visualization.
4. **Ant Design over Material-UI**: Ant Design has stronger Table components (sorting, filtering, pagination) which are critical for build history views.

---

## ADR-005: Authentication & Authorization Strategy

### Status: ACCEPTED

### Context
The platform needs authentication for three consumer types:
1. Human users (Portal)
2. CI/CD pipelines (CLI)
3. AI agents (MCP Gateway)

### Decision
**Use JWT tokens for human users and API Keys for machine clients (CLI/CI/CD).**

### Design
```
┌──────────────┬──────────────────────┬─────────────────────┐
│ Consumer     │ Auth Method          │ Token Lifetime      │
├──────────────┼──────────────────────┼─────────────────────┤
│ Portal Users │ OIDC → JWT           │ 1 hour (+ refresh)  │
│ CLI / CI/CD  │ API Key (revocable)  │ 90 days (rotatable) │
│ MCP / AI     │ JWT (delegated)      │ 1 hour              │
└──────────────┴──────────────────────┴─────────────────────┘
```

### Details
1. **Portal Authentication**: Integrate with corporate identity provider (OIDC/OAuth2). FastAPI middleware validates JWT and extracts `user_id` + `tenant_ids`.
2. **CLI / CI/CD Authentication**: Product admins generate API Keys via Portal. Keys are hashed (bcrypt) at rest. Each key is scoped to a specific `product_id`.
3. **API Key Rotation**: Keys support rotation with a grace period (old key valid for 24h after new key generation).
4. **MCP Authentication**: AI agents authenticate via user's JWT token, inheriting the user's RBAC permissions.

### Secret Management
- **Production**: HashiCorp Vault or cloud-native secret manager (AWS Secrets Manager / Azure Key Vault) for Git/Jira integration tokens.
- **Development**: Environment variables loaded from `.env` files (never committed to VCS).
- **Encryption at rest**: AES-256-GCM for integration tokens stored in PostgreSQL, with key managed by Vault/KMS.

---

## ADR-006: Deployment Model

### Status: ACCEPTED

### Context
The platform needs deployment strategies for development, staging, and production environments.

### Decision
**Docker Compose for development. Kubernetes for staging and production.**

### Development Environment
```yaml
# deploy/docker-compose.yml provides:
services:
  - urgp-api        (FastAPI Control Plane)
  - urgp-worker     (Traceability Hydrator async worker)
  - urgp-portal     (React dev server)
  - postgres        (PostgreSQL 16)
  - rabbitmq        (RabbitMQ with management UI)
  - redis           (Redis for caching)
  - mailhog         (SMTP mock for notification testing)
```

### Production Environment
- **Platform**: Kubernetes (EKS/GKE/AKS or self-hosted)
- **Deployment strategy**: Rolling updates with readiness probes
- **Helm charts**: For parameterized deployments across environments
- **GitOps**: ArgoCD or Flux for declarative deployments from Git
- **PostgreSQL**: Managed service (RDS/CloudSQL) or Patroni for self-hosted HA
- **RabbitMQ**: Managed service or Kubernetes Operator (rabbitmq-cluster-operator)

### Rationale
1. Docker Compose provides a single `docker compose up` command for developers to get a fully functional environment.
2. Kubernetes provides production-grade orchestration with auto-scaling, self-healing, and multi-AZ deployment.
3. Helm charts parameterize differences between environments (replica count, resource limits, external endpoints).

---

## ADR-007: AI Integration Strategy

### Status: ACCEPTED

### Context
The high-level architecture proposes an AI Gateway implementing Model Context Protocol (MCP). However, MCP is still evolving and building against it prematurely adds risk.

### Decision
**Phase 1-2: REST API only. Phase 3: Add MCP Server as a thin wrapper over REST APIs.**

### Rationale
1. **MCP is a moving target**: The protocol specification is still evolving. Building a full MCP Server before the core platform is stable risks rework.
2. **REST APIs are universally consumable**: Any AI tool (Claude, ChatGPT, Cursor) can call REST APIs via function calling without MCP.
3. **Thin wrapper pattern**: When MCP stabilizes, the MCP Server simply delegates to REST API endpoints. All business logic remains in the Control Plane.
4. **DORA metrics require data**: Meaningful DORA metrics need weeks/months of historical build data. Computing them at launch adds complexity with no value.

### Phase 3 Architecture
```
AI Agent (Claude/Cursor)
    ↓ MCP Protocol
MCP Server (thin wrapper)
    ↓ REST API calls
Control Plane (existing APIs)
    ↓ RBAC-filtered response
AI Agent
```

### Consequences
- **Risk reduction**: Core platform ships faster without MCP dependency.
- **No capability loss**: AI tools can still query URGP via REST APIs in Phases 1-2.
- **Deferred effort**: MCP Server implementation moves to Phase 3 when protocol is stable and historical data is available.
