# Team Structure & Work Plan
## Universal Release Governance Platform (URGP)

**Document Type:** Team Organization, Role Assignments & Work Breakdown  
**Target Audience:** All Team Members, Engineering Managers  
**Status:** PROPOSED  
**Last Updated:** 2026-04-19

---

## 1. Project Status & What We're Building

URGP replaces the fragmented Jenkins + SharePoint + Email system with a unified, data-driven Release Governance Platform.

### Current Status

| Phase | Status | Details |
|-------|--------|---------|
| Documentation & Design | ✅ **Complete** | 9 docs ([01](01-problem-assessment.md)–[09](09-git-workflow.md)), 10 frontend mockups |
| Source Code | ⏳ **Not Started** | Ready to begin implementation |
| Infrastructure | ⏳ **Not Started** | Docker Compose, CI/CD, Database |
| Testing | ⏳ **Not Started** | 40 mandatory tests defined |

### Delivery Roadmap

```
  P1 — MVP (10-14 weeks)          P2 — Platform (6-8 weeks)       P3 — Advanced (8-12 weeks)
  ━━━━━━━━━━━━━━━━━━━━━━━         ━━━━━━━━━━━━━━━━━━━━━━━━━       ━━━━━━━━━━━━━━━━━━━━━━━━━
  • URGP CLI                      • Multi-Tenancy + RBAC           • MCP/AI Gateway
  • Event Gateway + RabbitMQ      • SBOM (CycloneDX)               • DORA Metrics
  • Control Plane (FastAPI)       • Adapter Plugin System          • Python SDK
  • Self-Service Portal (React)   • Audit Logging                  • Integration Guides
  • Notification Engine           • Prometheus + Grafana
  • Build Lifecycle Management    • Kubernetes + Helm
                                  • Webhook Event System
```

### Reference Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  Layer 5: Self-Service Portal — React + TypeScript + Ant Design   │
└───────────────────────────────────┬───────────────────────────────┘
                                    │ HTTPS / REST
┌───────────────────────────────────▼───────────────────────────────┐
│  Layer 3: Control Plane — FastAPI + PostgreSQL 16 + Redis          │
│  ┌──────────┬────────────┬─────────────┬──────────────────┐       │
│  │ Manifest │ Traceabil. │ Immutability│ Notification     │       │
│  │ Service  │ Hydrator   │ Controller  │ Engine           │       │
│  └──────────┴────────────┴─────────────┴──────────────────┘       │
└───────────────────────────────────┬───────────────────────────────┘
                                    │ RabbitMQ (AMQP)
┌───────────────────────────────────▼───────────────────────────────┐
│  Layer 2: Event Gateway — Schema Validation + DLQ + Idempotency   │
└───────────────────────────────────┬───────────────────────────────┘
                                    │ HTTPS
┌───────────────────────────────────▼───────────────────────────────┐
│  Layer 1: Execution Edge — URGP CLI (single binary)               │
│  Adapters: generic, eclipse_p2 (P1) → oci, maven, npm (P2)       │
└───────────────────────────────────────────────────────────────────┘
```

---

## 2. Team Structure

### Organization Chart

```
                        ┌──────────────────────┐
                        │   PROJECT MANAGER     │
                        │   (PM)                │
                        └──────────┬───────────┘
                                   │
            ┌──────────────────────┼───────────────────────┐
            │                      │                       │
  ┌─────────▼──────────┐  ┌───────▼────────┐   ┌──────────▼──────────┐
  │  TECH LEAD (BE)    │  │  FRONTEND LEAD │   │  DevOps ENGINEER    │
  │  Architecture +    │  │  Portal UI +   │   │  Infra + CI/CD +    │
  │  Code Quality      │  │  React/TS      │   │  Deployment         │
  │                    │  │                │   │  (shared, 50% P1)   │
  │  ┌──────────────┐  │  │  ┌───────────┐ │   └─────────────────────┘
  │  │ BE Dev #1    │  │  │  │ FE Dev    │ │
  │  │ Gateway +    │  │  │  │ (P2 only) │ │   ┌─────────────────────┐
  │  │ Manifest APIs│  │  │  └───────────┘ │   │  QA ENGINEER        │
  │  ├──────────────┤  │  └────────────────┘   │  Testing + Quality  │
  │  │ BE Dev #2    │  │                       │  Assurance           │
  │  │ CLI + Integ. │  │                       └─────────────────────┘
  │  │ + Notif.     │  │
  │  └──────────────┘  │
  └────────────────────┘
```

### Team Size by Phase

| Phase | PM | TL-BE | BE-1 | BE-2 | FE-Lead | FE-Dev | DevOps | QA | **Total** |
|-------|:--:|:-----:|:----:|:----:|:-------:|:------:|:------:|:--:|:---------:|
| **P1 (MVP)** | 1 | 1 | 1 | 1 | 1 | — | 0.5 | 1 | **6.5** |
| **P2 (Platform)** | 0.5 | 1 | 1 | 1 | 0.5 | 1 | 1 | 1 | **7** |
| **P3 (Advanced)** | 0.3 | 1 | 0.5 | 0.5 | — | 0.5 | 0.5 | 0.5 | **3.8** |

> **Minimum viable team for P1**: TL-BE, BE-1, BE-2, FE-Lead, QA (**5 people**). PM and DevOps can be shared.

---

## 3. Role Definitions

### 3.1. Project Manager (PM)

| | |
|---|---|
| **Commitment** | Full-time P1, Part-time P2-P3 |
| **Experience** | 5+ years PM, enterprise platform experience |
| **Skills** | Agile/Scrum, Jira, stakeholder management, risk assessment |

**Responsibilities:**
- Sprint planning & backlog management
- Coordinate migration strategy (4-phase) with S32 team
- Weekly status reports to management
- Manage cross-team dependencies (BE ↔ FE ↔ DevOps)
- Scope control — all new feature requests go to P2

---

### 3.2. Technical Lead — Backend (TL-BE)

| | |
|---|---|
| **Commitment** | Full-time, entire project |
| **Experience** | 7+ years Python, system architecture |
| **Required** | Python 3.11+, FastAPI, PostgreSQL, async/await, system design |
| **Nice-to-have** | RabbitMQ, Redis, Docker, Kubernetes |

**Responsibilities:**
- **Architecture ownership** — owns backend design decisions
- Define API contracts (OpenAPI YAML) before team codes
- Code review all backend PRs
- Build core components: **Traceability Hydrator**, **Immutability Controller**
- Ensure performance SLAs: API p95 < 500ms, hydration < 30s

**Phase 1 Timeline:**

| Week | Focus |
|------|-------|
| 1-2 | Project setup, Docker Compose, DB schema, config |
| 4-5 | Traceability Hydrator framework + Git resolution |
| 5-7 | Traceability Hydrator issue extraction + resilience |
| 7-8 | Build Lifecycle state machine + Immutability Controller |
| 10-14 | E2E integration, performance tuning, stabilization |

---

### 3.3. Backend Developer #1 (BE-1) — Gateway & APIs

| | |
|---|---|
| **Commitment** | Full-time P1-P2, Part-time P3 |
| **Experience** | 4+ years Python |
| **Required** | Python, FastAPI, SQLAlchemy/asyncpg, PostgreSQL, Pydantic |
| **Nice-to-have** | RabbitMQ, Redis, pytest |

**Responsibilities:**
- **Event Gateway**: ingestion API, schema validation, idempotency, DLQ
- **Build Manifest Service**: CRUD, lifecycle state machine
- **Query APIs**: list builds, comparison, search by commit/issue
- **Rate Limiting** middleware (Redis sliding window)
- Unit tests for all owned components

**Phase 1 Timeline:**

| Week | Focus |
|------|-------|
| 1-2 | Infrastructure setup (RabbitMQ, config) |
| 3-5 | Event Gateway — all 6 sub-tasks (P1-3.1 → P1-3.6) |
| 5-8 | Build Manifest Service + Query APIs (P1-4.1, P1-4.6–P1-4.9) |
| 8-9 | Product & Release Train management APIs (P1-4.2) |
| 10-12 | E2E testing support |

---

### 3.4. Backend Developer #2 (BE-2) — CLI & Integrations

| | |
|---|---|
| **Commitment** | Full-time P1-P2, Part-time P3 |
| **Experience** | 4+ years Python, strong with external API integrations |
| **Required** | Python, REST API consumption, async I/O (aiohttp/httpx) |
| **Nice-to-have** | Git APIs (GitHub/Bitbucket), Jira REST API, Typer/Click |

**Responsibilities:**
- **URGP CLI**: push command, verify, adapters (generic + eclipse_p2), retry logic
- **Git Provider** adapters: GitHub REST v3, Bitbucket REST v2
- **Jira Issue Tracker** integration: batch queries, regex extraction, caching
- **Notification Engine**: email (SMTP) + webhook delivery + retry
- Unit tests with mocked external APIs

**Phase 1 Timeline:**

| Week | Focus |
|------|-------|
| 1-2 | Infrastructure setup (logging, health checks) |
| 2-4 | URGP CLI — all 6 sub-tasks (P1-2.1 → P1-2.6) |
| 4-6 | Git provider + Jira integrations (P1-4.3, P1-4.4) |
| 5-7 | Traceability Hydrator — with TL-BE (P1-4.5a, P1-4.5b) |
| 6-7 | Notification Engine (P1-5.1, P1-5.2) |
| 10-12 | E2E testing support |

---

### 3.5. Frontend Lead (FE-Lead)

| | |
|---|---|
| **Commitment** | Full-time P1 (from Week 4), Part-time P2 |
| **Experience** | 5+ years React/TypeScript |
| **Required** | React, TypeScript, Ant Design, React Router v6, TanStack Query |
| **Nice-to-have** | React Flow, Recharts, Vite, responsive design |

**Responsibilities:**
- **Own entire frontend** architecture & code quality
- Setup React project with Vite + design system
- Implement all Portal pages (6 screens)
- Interactive Traceability Graph (React Flow)
- API client layer (Axios + JWT interceptors)
- Frontend integration tests

> **Note:** Frontend starts Week 4 using **MSW (Mock Service Worker)** to mock backend APIs. This ensures FE is never blocked by BE.

**Phase 1 Timeline:**

| Week | Focus |
|------|-------|
| 4 | Project setup, design system, API client, sidebar navigation (P1-6.1) |
| 4-5 | Auth flow + Products Catalog (P1-6.2, P1-6.3) |
| 5-6 | Product Releases + Release Builds pages (P1-6.4) |
| 6-8 | Build Detail pages — Packages + What's New + Traceability Graph (P1-6.5) |
| 7-8 | Package Detail + Package CI/CD pages (P1-6.6) |
| 8-9 | Build Comparison + Activity Feed + Notification Settings (P1-6.7, P1-6.8, P1-6.9) |
| 10-12 | Integration testing, visual polish |

---

### 3.6. DevOps Engineer (shared)

| | |
|---|---|
| **Commitment** | 50% P1, 100% P2, 50% P3 |
| **Experience** | 4+ years DevOps/SRE |
| **Required** | Docker, Docker Compose, GitHub Actions, Linux |
| **Nice-to-have** | Kubernetes, Helm, Prometheus, Grafana |

**Responsibilities:**
- Docker Compose development environment
- CI/CD pipeline for URGP itself (GitHub Actions)
- CLI binary build pipeline (PyInstaller)
- Kubernetes Helm charts (P2)
- Monitoring stack: Prometheus + Grafana (P2)
- Backup automation + DR (P2)

---

### 3.7. QA Engineer

| | |
|---|---|
| **Commitment** | Full-time P1-P2, Part-time P3 |
| **Experience** | 3+ years API + UI testing |
| **Required** | API testing (Postman/pytest), integration testing |
| **Nice-to-have** | Playwright/Cypress, performance testing (k6/Locust) |

**Responsibilities:**
- Write test plans per sprint
- Execute **40 mandatory tests** across 3 phases (see Section 5)
- API integration testing (pytest + httpx)
- E2E testing: CLI → API → DB → Portal → Notification
- Performance testing: API latency, hydration SLA, portal load time
- Data accuracy validation: URGP vs legacy Email

---

## 4. Phase 1 — Detailed Work Breakdown

### P1-1: Infrastructure Foundation `[Week 1-2]`

| ID | Task | Owner | Est. | Deps | Req |
|----|------|-------|------|------|-----|
| P1-1.1 | Initialize Python project with Poetry + mypy + pre-commit hooks | TL-BE | 2d | — | R20 |
| P1-1.2 | Create Docker Compose (urgp-api, urgp-worker, postgres, rabbitmq, redis, mailhog) | TL-BE + DevOps | 3d | — | R20, ADR-006 |
| P1-1.3 | PostgreSQL schema + Alembic migrations (12 tables, 3 enums, indexes) | TL-BE | 3d | P1-1.1 | R5 |
| P1-1.4 | RabbitMQ topology (exchanges, queues, DLX) | BE-1 | 1d | P1-1.2 | R4, ADR-002 |
| P1-1.5 | Pydantic config management (URGPSettings, env vars, YAML) | BE-1 | 2d | P1-1.1 | R20 |
| P1-1.6 | Structured JSON logging + health endpoints (/health, /health/ready) | BE-2 | 2d | P1-1.1 | R17 |
| P1-1.7 | CI pipeline (GitHub Actions: lint → type-check → test → build) | DevOps | 2d | P1-1.1 | — |

**Tests:**

| ID | Test | Owner | Est. |
|----|------|-------|------|
| P1-1.T1 | Config validation: valid loads, invalid fails fast with clear error | QA | 0.5d |
| P1-1.T2 | Health endpoints: healthy and unhealthy scenarios | QA | 0.5d |
| P1-1.T3 | DB migration: upgrade + downgrade round-trip | QA | 0.5d |

**Sprint 1-2 Definition of Done:**
- [ ] `docker compose up` starts full environment in < 60 seconds
- [ ] `alembic upgrade head` creates schema without errors
- [ ] Health endpoints respond < 100ms
- [ ] CI pipeline passes on clean repo
- [ ] All 3 tests pass

---

### P1-2: URGP CLI `[Week 2-4]`

| ID | Task | Owner | Est. | Deps | Req |
|----|------|-------|------|------|-----|
| P1-2.1 | CLI core framework (Typer): push, verify, --version, --help | BE-2 | 2d | P1-1.1 | R3 |
| P1-2.2 | SHA-256 checksum computation (streaming, files up to 2GB) | BE-2 | 1d | P1-2.1 | R3.5 |
| P1-2.3 | Built-in adapters: GenericAdapter + EclipseP2Adapter | BE-2 | 3d | P1-2.1 | R3.3 |
| P1-2.4 | Data Contract payload construction (Pydantic models → JSON) | BE-2 | 1d | P1-2.1 | R3.4, R4.4 |
| P1-2.5 | HTTPS transmission + retry (3x exponential backoff) + fallback file | BE-2 | 2d | P1-2.4 | R3.6-R3.9 |
| P1-2.6 | CLI binary distribution (PyInstaller: Linux + Windows) | DevOps + BE-2 | 2d | P1-2.5 | R3.1 |

**Tests:**

| ID | Test | Owner | Est. |
|----|------|-------|------|
| P1-2.T1 | GenericAdapter with sample files (binary, .zip, .tar.gz) | QA | 0.5d |
| P1-2.T2 | EclipseP2Adapter with sample S32 P2 repository .zip | QA | 0.5d |
| P1-2.T3 | SHA-256 accuracy (compare with `sha256sum` output) | QA | 0.5d |
| P1-2.T4 | Data Contract JSON schema compliance | QA | 0.5d |
| P1-2.T5 | Retry logic: mock server 500 → 503 → 200 | QA | 0.5d |
| P1-2.T6 | Fallback file creation on connection failure | QA | 0.5d |
| P1-2.T7 | CLI parameter validation (missing required params, invalid values) | QA | 0.5d |

**CLI Definition of Done:**
- [ ] `urgp-cli push --help` displays all parameters
- [ ] Checksums computed correctly for files up to 2GB
- [ ] Adapters extract metadata from real S32 package files
- [ ] Retry logic handles transient failures gracefully
- [ ] Single binary runs on Linux and Windows
- [ ] All 7 tests pass

---

### P1-3: Event Gateway `[Week 3-5]`

| ID | Task | Owner | Est. | Deps | Req |
|----|------|-------|------|------|-----|
| P1-3.1 | Ingestion API: `POST /api/v1/ingest` with API key auth | BE-1 | 2d | P1-1.3, P1-1.4 | R4.1 |
| P1-3.2 | JSON schema validation (Pydantic) → HTTP 422 on failure | BE-1 | 1d | P1-3.1 | R4.2, R4.3 |
| P1-3.3 | Idempotency check (Redis, build_id + product_id, 24h TTL) | BE-1 | 1d | P1-3.1 | R4.8 |
| P1-3.4 | RabbitMQ publish → build.process + build.notify queues | BE-1 | 2d | P1-3.1 | R4.5, R4.6 |
| P1-3.5 | Dead Letter Queue handling + monitoring endpoint | BE-1 | 1d | P1-3.4 | R4.3 |
| P1-3.6 | API rate limiting (Redis sliding window, 100r/m read, 20r/m write) | BE-1 | 2d | P1-3.1 | R22 |

**Tests:**

| ID | Test | Owner | Est. |
|----|------|-------|------|
| P1-3.T1 | Valid payload → HTTP 202 + message in RabbitMQ | QA | 0.5d |
| P1-3.T2 | Invalid payload → HTTP 422 + detailed validation errors | QA | 0.5d |
| P1-3.T3 | Idempotency: same build_id twice → second returns 200, no duplicate | QA | 0.5d |
| P1-3.T4 | Rate limiting: exceed limit → HTTP 429 + Retry-After header | QA | 0.5d |
| P1-3.T5 | DLQ routing for malformed messages | QA | 0.5d |
| P1-3.T6 | Unauthenticated request → HTTP 401 | QA | 0.5d |

**Gateway Definition of Done:**
- [ ] CLI payloads flow through Gateway → RabbitMQ → queues
- [ ] Invalid payloads rejected with actionable error messages
- [ ] Duplicate submissions handled idempotently
- [ ] Rate limiting enforced with proper HTTP headers
- [ ] All 6 tests pass

---

### P1-4: Control Plane `[Week 4-8]`

| ID | Task | Owner | Est. | Deps | Req |
|----|------|-------|------|------|-----|
| P1-4.1 | Build Manifest Service (RabbitMQ consumer, create manifest + artifacts) | BE-1 | 3d | P1-3.4 | R5, R2 |
| P1-4.2 | Product & Release Train CRUD APIs with Git/Jira config | BE-1 | 2d | P1-1.3 | R1, R12, R13 |
| P1-4.3 | Git Provider adapters: GitHub REST v3, Bitbucket REST v2 | BE-2 | 5d | P1-1.3 | R12 |
| P1-4.4 | Jira Issue Tracker: batch query, regex extraction, Redis caching | BE-2 | 3d | P1-1.3 | R13 |
| P1-4.5a | Traceability Hydrator: async framework + Git resolution + PR lookup | TL-BE + BE-2 | 4d | P1-4.3 | R6.1-R6.4, R21 |
| P1-4.5b | Traceability Hydrator: issue extraction + graph construction + DB storage | TL-BE + BE-2 | 3d | P1-4.5a, P1-4.4 | R6.5-R6.7 |
| P1-4.5c | Traceability Hydrator: E2E resilience + 30s SLA + concurrent builds | TL-BE | 3d | P1-4.5b | R6.8-R6.9 |
| P1-4.6 | Build query APIs: list (paginated), detail, traceability graph | BE-1 | 3d | P1-4.1 | R7, R9 |
| P1-4.7 | Build Comparison API: diff two builds, deduplicated changes | BE-1 | 2d | P1-4.6 | R7.1-R7.4 |
| P1-4.8 | Search APIs: by-commit and by-issue reverse lookup | BE-1 | 2d | P1-4.6 | R7.5-R7.6 |
| P1-4.9 | Build Lifecycle: state transitions + manifest locking + HMAC signature | TL-BE | 3d | P1-4.1 | R5.3-R5.9 |

**Tests:**

| ID | Test | Owner | Est. |
|----|------|-------|------|
| P1-4.T1 | Manifest creation from ingested build event | QA | 0.5d |
| P1-4.T2 | Artifact registration: valid and invalid checksums | QA | 0.5d |
| P1-4.T3 | Duplicate checksum rejection within same manifest | QA | 0.5d |
| P1-4.T4 | Git provider adapters with mocked responses (GitHub, Bitbucket) | QA | 0.5d |
| P1-4.T5 | Jira tracker with mocked responses (batch, missing issues) | QA | 0.5d |
| P1-4.T6 | Traceability graph: multi-repo commits correctly linked | QA | 0.5d |
| P1-4.T7 | Partial graph on API failures + traceability_incomplete flag | QA | 0.5d |
| P1-4.T8 | Build comparison with 3 sequential test builds | QA | 0.5d |
| P1-4.T9 | Reverse search: by-commit, by-issue | QA | 0.5d |
| P1-4.T10 | Lifecycle: valid and invalid state transitions | QA | 0.5d |
| P1-4.T11 | Manifest lock: HTTP 409 on modify after release | QA | 0.5d |
| P1-4.T12 | Product and Release Train CRUD APIs | QA | 0.5d |

**Control Plane Definition of Done:**
- [ ] End-to-end: ingested event → manifest → hydrated graph → queryable data
- [ ] Full traceability: build ↔ commits ↔ PRs ↔ Jira issues
- [ ] Build comparison returns accurate diffs between any two builds
- [ ] Released manifests are locked and immutable
- [ ] Graph hydration completes within 30 seconds (100 commits)
- [ ] All 12 tests pass

---

### P1-5: Notification Engine `[Week 6-7]`

| ID | Task | Owner | Est. | Deps | Req |
|----|------|-------|------|------|-----|
| P1-5.1 | Notification Engine: email (SMTP) + webhook (HTTP POST) + retry | BE-2 | 4d | P1-3.4 | R8 |
| P1-5.2 | Subscription management APIs: list, create, delete | BE-2 | 2d | P1-5.1 | R8.4, R8.8 |

**Tests:**

| ID | Test | Owner | Est. |
|----|------|-------|------|
| P1-5.T1 | Email notification delivery (MailHog in dev) | QA | 0.5d |
| P1-5.T2 | Webhook notification delivery (mock HTTP server) | QA | 0.5d |
| P1-5.T3 | Notification retry on delivery failure | QA | 0.5d |
| P1-5.T4 | Subscription CRUD APIs | QA | 0.5d |
| P1-5.T5 | Notification filtering: only matching product + release_train | QA | 0.5d |

**Notification Definition of Done:**
- [ ] Notifications sent within 60 seconds of build completion
- [ ] Both email and webhook channels functional
- [ ] Failed deliveries retried with exponential backoff
- [ ] Users can self-manage subscriptions
- [ ] All 5 tests pass

---

### P1-6: Self-Service Portal `[Week 4-10]`

| ID | Task | Owner | Est. | Deps | Req |
|----|------|-------|------|------|-----|
| P1-6.1 | React project setup (Vite + Ant Design + Router + TanStack Query + Axios + Recharts) | FE-Lead | 2d | — | ADR-004 |
| P1-6.2 | Authentication flow + sidebar navigation (Products/Activity/Comparisons/Reports/Settings) | FE-Lead | 3d | P1-6.1 | R9.1, R9.16 |
| P1-6.3 | Products Catalog page (KPI metrics, product cards, search) | FE-Lead | 3d | P1-6.2 | R9.2 |
| P1-6.4 | Product Releases + Release Builds pages (hierarchy navigation, build type filters) | FE-Lead | 4d | P1-6.3 | R9.3-R9.4, R9.14 |
| P1-6.5 | Build Detail: Packages + What's New + Traceability (React Flow) | FE-Lead | 6d | P1-6.4 | R9.5-R9.9, R9.13 |
| P1-6.6 | Package Detail + Package CI/CD & Testing pages | FE-Lead | 4d | P1-6.5 | R9.11 |
| P1-6.7 | Build Comparison pages (Issues + PRs + Packages tabs, CSV/JSON export) | FE-Lead | 3d | P1-6.4 | R9.10 |
| P1-6.8 | Activity Feed page (live metrics, active builds, alerts, heatmap) | FE-Lead | 3d | P1-6.2 | R9.15 |
| P1-6.9 | Notification Settings page (subscription management UI) | FE-Lead | 2d | P1-6.2 | R8.8 |

**Tests:**

| ID | Test | Owner | Est. |
|----|------|-------|------|
| P1-6.T1 | Integration: login → products catalog → release selection → build list navigation | QA + FE | 0.5d |
| P1-6.T2 | Integration: build detail pages render packages and traceability data correctly | QA + FE | 0.5d |
| P1-6.T3 | Integration: build comparison page shows correct diff across Issues/PRs/Packages | QA + FE | 0.5d |
| P1-6.T4 | Performance: manifest page renders < 1 second (50 artifacts) | QA + FE | 0.5d |
| P1-6.T5 | Performance: traceability graph renders < 3 seconds (100 commits) | QA + FE | 0.5d |
| P1-6.T6 | Integration: activity feed displays live metrics from multiple products | QA + FE | 0.5d |

**Portal Definition of Done:**
- [ ] All 10 pages functional and connected to APIs
- [ ] Products catalog: KPI metrics, product cards with release/build stats
- [ ] Product → Release → Build navigation hierarchy works end-to-end
- [ ] Build detail: packages list with downloads, What's New with issues/PRs, Traceability Graph
- [ ] Package detail and CI/CD pages with drill-down from build
- [ ] Build Comparison: accurate diff across Issues/PRs/Packages with export functionality
- [ ] Activity Feed: live metrics, active builds, alerts, heatmap
- [ ] Sidebar navigation: Products, Activity, Comparisons, Reports, Settings
- [ ] Consistent "Command Horizon" design system (see `/frontend/designs/`)
- [ ] All 6 tests pass

---

### P1-7: E2E Validation `[Week 10-12]`

| ID | Task | Owner | Est. | Deps |
|----|------|-------|------|------|
| P1-7.1 | Full pipeline E2E test: CLI push → Gateway → Manifest → Hydration → Portal → Notification | QA + ALL | 5d | All P1 |
| P1-7.2 | Data accuracy: compare 5 URGP builds vs legacy Email "What's New" (≥ 90% match) | QA | 3d | P1-7.1 |
| P1-7.3 | Performance: API p95 < 500ms, hydration < 30s, portal < 1s | QA + TL-BE | 2d | P1-7.1 |
| P1-7.4 | User documentation: CLI guide, Portal guide, setup guide, notifications guide | TL-BE + FE-Lead | 3d | P1-7.1 |
| P1-7.5 | Begin Migration Phase 0 — shadow mode on S32 Jenkins pipelines | DevOps + BE-2 | 2d | P1-7.1 |

### P1-8: Stabilization Buffer `[Week 13-14]`

| ID | Task | Owner | Est. |
|----|------|-------|------|
| P1-8.1 | Address E2E validation findings | ALL | buffer |
| P1-8.2 | Performance tuning (if SLAs not met) | TL-BE | buffer |
| P1-8.3 | Phase 1 Definition of Done — final sign-off | PM + TL-BE | 1d |

---

## 5. Phase 2 & Phase 3 — Summary

### Phase 2: Platform (6-8 weeks)

| ID | Task | Owner | Est. |
|----|------|-------|------|
| P2-1.1 | Tenant Router + PostgreSQL Row-Level Security | TL-BE | 5d |
| P2-1.2 | RBAC Engine + role assignment APIs | BE-1 | 5d |
| P2-1.3 | OIDC authentication (corporate SSO) | BE-1 | 3d |
| P2-2.1 | SBOM generation (CycloneDX 1.4+) | TL-BE | 3d |
| P2-2.2 | Artifact verification API | TL-BE | 2d |
| P2-3.1 | Dynamic adapter plugin loading system | BE-2 | 3d |
| P2-3.2 | New adapters: OCI image, Maven JAR, npm tarball | BE-2 | 5d |
| P2-3.3 | Adapter development guide | BE-2 | 2d |
| P2-4.1 | Audit logging (append-only, query API, 90-day retention) | BE-1 | 3d |
| P2-4.2 | Prometheus metrics endpoint (/metrics) | TL-BE | 2d |
| P2-4.3 | OpenTelemetry distributed tracing | TL-BE | 3d |
| P2-4.4 | Grafana dashboards + alert rules | DevOps | 3d |
| P2-4.5 | Circuit breakers for Git/Jira API calls | TL-BE | 2d |
| P2-4.6 | Webhook event system (CloudEvents format) | BE-1 | 3d |
| P2-4.7 | GitLab, Azure DevOps, GitHub Issues adapters | BE-2 | 5d |
| P2-5.1 | Automated daily DB backups (30-day retention) | DevOps | 3d |
| P2-5.2 | Kubernetes Helm charts (API, Worker, Portal, HPA) | DevOps | 5d |
| P2-5.3 | Disaster recovery documentation (RTO 4h, RPO 24h) | DevOps | 2d |
| P2-5.4 | OpenAPI spec polish + Swagger UI | BE-1 | 1d |
| — | Frontend: Tenant/RBAC UI, SBOM viewer, webhooks, admin pages | FE-Lead + FE-Dev | 15d |

**Phase 2 Tests (7 mandatory):** cross-tenant isolation, RBAC enforcement, RLS at DB level, SBOM round-trip, backup+restore, performance at scale, circuit breaker behavior, webhook delivery.

---

### Phase 3: Advanced (8-12 weeks)

| ID | Task | Owner | Est. |
|----|------|-------|------|
| P3-1.1 | MCP Server framework (FastAPI, JWT, tenant isolation) | TL-BE | 5d |
| P3-1.2 | MCP Tools: 6 tools mapping to REST APIs | TL-BE + BE-1 | 5d |
| P3-1.3 | Cross-tenant analytics (permission-gated) | BE-1 | 3d |
| P3-1.4 | MCP audit logging | BE-1 | 1d |
| P3-2.1 | DORA metrics computation (4 metrics, API) | TL-BE | 5d |
| P3-2.2 | DORA metrics dashboard (Recharts) | FE-Dev | 5d |
| P3-3.1 | Python SDK (typed, async+sync, published to PyPI) | BE-2 | 8d |
| P3-3.2 | Integration guides (CI/CD, Git, Jira, MCP) | ALL | 5d |

**Phase 3 Tests (4 mandatory):** MCP tenant isolation, cross-tenant permissions, DORA accuracy, SDK coverage.

---

## 6. Sprint Calendar — Visual Overview (Phase 1)

```
Week        1    2    3    4    5    6    7    8    9   10   11   12   13   14
            ├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
 TL-BE      ████████ ·    ····████████████████████ ·    ····████████████████
            Infra        Hydrator + Immutability       E2E + Perf Tuning
                                                       
 BE-1       ████████ ████████████████████████████ ·    ····████████████
            Infra    Gateway     Manifest + APIs       E2E Support
                                                       
 BE-2       ████████ ████████████████████████████████ ·    ████████████
            Infra    CLI       Git/Jira+Hydrator Notif E2E Support
                                                       
 FE-Lead    ·    ·   ·    ████████████████████████████████████████
                          Setup → History → Details → Compare Pol.
                                                       
 QA         ····████ ████████████████████████████████████████████████████
            Plans    CLI+GW   → Control Plane → Notif → E2E + Performance
                                                       
 DevOps     ████████ ····                              ····████████
            Docker+CI CLI Build                        Migration Setup

 ████ = Active coding    ···· = Support/Review    · = Available for other tasks
```

---

## 7. Critical Path & Risks

### Critical Path

```
P1-1 (Infra) → P1-3 (Gateway) → P1-4 (Control Plane) → P1-7 (E2E) → P1-8 (Buffer)
  Week 1-2       Week 3-5          Week 4-8            Week 10-12     Week 13-14

                                              ↗ P1-5 (Notifications, Week 6-7)
  P1-6 (Portal, Week 4-10) ─────────────────────────────────────────→ P1-7
```

> **Any delay on the critical path impacts the entire P1 timeline.**  
> Frontend runs in parallel using API mocking (MSW) — not on the critical path.

### Top Risks

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Frontend blocked waiting for APIs | High | Medium | Use MSW mock from Week 4; define OpenAPI contracts early |
| External APIs (Git/Jira) unstable during hydration | Medium | High | Circuit breakers, partial graph, `traceability_incomplete` flag |
| Performance SLA failure (hydration > 30s) | Medium | High | Async I/O, Redis cache, early load testing |
| S32 team resists migration | High | Medium | 4-phase migration, shadow mode first, pilot group |
| Scope creep in P1 | High | High | PM locks P1 scope; all new requests → P2 backlog |
| Data mismatch between URGP and legacy | Low | Critical | Phase 0 shadow mode validates data for 4 weeks |

---

## 8. How We Work

### Engineering Principles

1. **API-First** — Define OpenAPI contract → Mock → Implement → Integrate
2. **Test-Driven** — Write tests alongside implementation, not after
3. **Small PRs** — Each PR ≤ 400 lines, reviewed within 24 hours
4. **Trunk-Based Development** — Short-lived feature branches, merge to `main` frequently

### Ceremonies

| Ceremony | Frequency | Duration | Attendees |
|----------|-----------|----------|-----------|
| Daily Standup | Daily | 15 min | All dev team |
| Sprint Planning | Bi-weekly | 1 hour | All team + PM |
| Sprint Demo | Bi-weekly | 30 min | All team + stakeholders |
| Sprint Retro | Bi-weekly | 30 min | All dev team |
| Architecture Review | As needed | 1 hour | TL-BE + relevant devs |

### Definition of Done (Global)

A task is "Done" when:
- [ ] Code is implemented and self-reviewed
- [ ] Unit tests pass with ≥ 80% coverage
- [ ] PR is approved by at least 1 reviewer (TL-BE for backend, FE-Lead for frontend)
- [ ] CI pipeline passes (lint + type-check + test)
- [ ] No known regressions introduced
- [ ] Documentation updated if applicable

---

## 9. Summary — By The Numbers

| Metric | Value |
|--------|-------|
| **Total tasks** | 61 development + 40 tests = **101 items** |
| **Phase 1 items** | 35 tasks + 29 tests = **64 items** |
| **Phase 2 items** | 18 tasks + 7 tests = **25 items** |
| **Phase 3 items** | 8 tasks + 4 tests = **12 items** |
| **Total estimated effort** | **~423 person-days (≈ 21 person-months)** |
| **Team size (P1)** | **6.5 FTE** |
| **Total timeline** | **24-34 weeks** across 3 phases |

### Effort Distribution

| Role | P1 | P2 | P3 | Total |
|------|:--:|:--:|:--:|:-----:|
| TL-BE | 50d | 25d | 20d | **95d** |
| BE-1 | 45d | 25d | 10d | **80d** |
| BE-2 | 45d | 20d | 15d | **80d** |
| FE-Lead | 35d | 10d | — | **45d** |
| FE-Dev | — | 15d | 5d | **20d** |
| DevOps | 10d | 20d | 5d | **35d** |
| QA | 25d | 10d | 5d | **40d** |
| PM | 15d | 8d | 5d | **28d** |

---

## Quick Links to Project Documentation

| # | Document | Purpose |
|---|----------|---------|
| 01 | [Problem Assessment](01-problem-assessment.md) | Why we're building this — pain points & root causes |
| 02 | [Solution Architecture](02-solution-architecture.md) | 5-layer architecture vision |
| 03 | [Architecture Decisions](03-architecture-decisions.md) | Technology choices (PostgreSQL, RabbitMQ, FastAPI, React) |
| 04 | [Requirements](04-requirements.md) | 24 requirements with acceptance criteria |
| 05 | [Technical Design](05-technical-design.md) | Database schema, APIs, component interfaces |
| 06 | [Migration Strategy](06-migration-strategy.md) | 4-phase rollout from legacy |
| 07 | [Implementation Plan](07-implementation-plan.md) | Detailed 61 tasks + 40 tests |
| 08 | **This Document** | Team structure, role assignments, work breakdown |
| — | [Frontend Designs](../frontend/designs/index.html) | 7 UI mockups (Command Horizon design) |
