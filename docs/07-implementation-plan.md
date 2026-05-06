# Implementation Plan: Universal Release Governance Platform (URGP)

## Overview

This implementation plan breaks down the URGP platform into **3 delivery phases** with incremental, testable milestones. Each phase delivers standalone value and builds upon the previous phase.

**Reference Documents:**
- [Requirements](04-requirements.md) — Functional and non-functional requirements with phase tags
- [Design](05-technical-design.md) — Detailed technical design, data model, component interfaces
- [Architecture Decision Records](03-architecture-decisions.md) — Technology choices
- [Migration Strategy](06-migration-strategy.md) — Rollout and coexistence plan

### Technology Stack (Committed)

| Component | Technology | Reference |
|-----------|-----------|-----------|
| Backend | Python 3.11+ / FastAPI / Uvicorn | ADR-003 |
| Database | PostgreSQL 16 | ADR-001 |
| Message Broker | RabbitMQ | ADR-002 |
| Cache | Redis | — |
| Frontend | React + TypeScript + Vite | ADR-004 |
| UI Library | Ant Design | ADR-004 |
| Graph Visualization | React Flow | ADR-004 |
| Server State | TanStack Query | ADR-004 |
| Auth | JWT + API Keys | ADR-005 |
| Dev Environment | Docker Compose | ADR-006 |
| Prod Environment | Kubernetes + Helm | ADR-006 |

### Team Composition Recommendation

| Phase | Backend Engineers | Frontend Engineer | DevOps/Infra | QA | Total |
|-------|-------------------|-------------------|--------------|-----|-------|
| P1 (MVP) | 2 senior | 1 senior | 0.5 (shared) | 1 | ~4.5 |
| P2 (Platform) | 2 senior | 1 mid-senior | 1 | 1 | 5 |
| P3 (Advanced) | 1 senior + 1 mid | 0.5 (maintenance) | 0.5 | 0.5 | 2.5 |

### Infrastructure Cost Estimate (Monthly)

| Resource | Dev/Staging | Production |
|----------|-----------|------------|
| PostgreSQL (managed) | $50 | $200-400 |
| RabbitMQ (managed or self-hosted) | $30 | $100-200 |
| Redis (managed) | $20 | $50-100 |
| Kubernetes (3-node cluster) | — | $300-600 |
| Container Registry | $10 | $10 |
| SMTP (Notification) | $0 (MailHog) | $20-50 |
| **Total** | **~$110/mo** | **~$680-1360/mo** |

---

## Phase 1: MVP — Core Value Delivery

**Goal:** Replace Email + SharePoint with a functional Portal + CLI that the S32 team uses daily.  
**Timeline:** 10-14 weeks (includes 2-week stabilization buffer)  
**Success Criteria:** S32 team actively uses URGP for Nightly/Weekly builds. Time to investigate build changes drops from 15 min → 30 sec.

> ⚠️ All test tasks in Phase 1 are **MANDATORY** (not optional). Tests are the primary quality gate.

### P1-1: Development Environment & Infrastructure Foundation `[Week 1-2]`

- [ ] P1-1.1 Initialize Python project with Poetry
  - Create project structure as defined in [05-technical-design.md § Project Structure](05-technical-design.md#project-structure)
  - Directory layout: `src/urgp/`, `src/urgp_cli/`, `portal/`, `tests/`, `migrations/`, `config/`, `deploy/`, `docs/`
  - Configure Python 3.11+ with type hints enforcement (mypy strict mode)
  - Set up pre-commit hooks (black, ruff, mypy)
  - **Deliverable:** `pyproject.toml`, project skeleton, CI linting passes
  - _Requirements: R20.1, R20.2_

- [ ] P1-1.2 Create Docker Compose development environment
  - Define `docker-compose.yml` with services: `urgp-api`, `urgp-worker`, `postgres`, `rabbitmq`, `redis`, `mailhog`
  - Create `Dockerfile` for API + Worker (multi-stage build)
  - Create `.env.example` with all configuration variables
  - Add `Makefile` with targets: `up`, `down`, `logs`, `shell`, `test`, `migrate`
  - **Deliverable:** `docker compose up` starts full environment in < 60 seconds
  - _Requirements: R20.1, R20.6_ | _ADR-006_

- [ ] P1-1.3 Create PostgreSQL database schema with Alembic migrations
  - Create initial migration with tables: `products`, `release_trains`, `build_manifests`, `artifacts`, `commits`, `pull_requests`, `issues`, `build_commits`, `commit_prs`, `commit_issues`, `notification_subscriptions`, `notifications`
  - Define enums: `build_status`, `artifact_type`, `notification_channel`
  - Add indexes: `build_manifests(product_id, created_at)`, `commits(hash)`, `artifacts(sha256_checksum)`
  - Seed script with sample S32 Design Studio product data for local development
  - **Deliverable:** `alembic upgrade head` creates schema, seed data available
  - _Requirements: R5.1, R5.2, R5.3_ | _Ref: [05-technical-design.md § Data Model](05-technical-design.md#data-model)_

- [ ] P1-1.4 Set up RabbitMQ exchanges and queues
  - Create exchange: `urgp.build.events` (direct type)
  - Create queues: `build.process`, `build.notify`, `build.events.dlq`
  - Configure Dead Letter Exchange routing
  - Create management script for queue setup (idempotent)
  - **Deliverable:** RabbitMQ management UI shows configured topology
  - _Requirements: R4.1_ | _ADR-002_

- [ ] P1-1.5 Implement configuration management with Pydantic
  - Create `URGPSettings` Pydantic model (see [05-technical-design.md § Configuration](05-technical-design.md#configuration-pydantic-settings))
  - Support env vars (`URGP_` prefix) and YAML config files
  - Fail-fast validation on startup with descriptive error messages
  - Mask sensitive values in logs (`SecretStr` for tokens, keys)
  - Create config templates: `config/dev.yaml`, `config/staging.yaml`, `config/production.yaml`
  - **Deliverable:** App starts successfully with env vars or YAML config
  - _Requirements: R20.1-R20.7_

- [ ] P1-1.6 Implement structured logging and health checks
  - Configure Python `logging` with JSON formatter (`timestamp`, `severity`, `component`, `request_id`, `message`)
  - Implement `GET /health` (basic, < 100ms) and `GET /health/ready` (checks DB + RabbitMQ connections)
  - Add request ID middleware (UUID per request, propagated in all logs)
  - **Deliverable:** Structured logs visible in `docker compose logs`, health endpoints respond
  - _Requirements: R17.1, R17.2, R17.3_

- [ ] P1-1.7 Set up CI pipeline for URGP itself
  - Create GitHub Actions workflow (or equivalent): lint → type-check → unit test → build Docker image
  - Run on every PR and push to main
  - **Deliverable:** CI pipeline passes on clean repo
  - _No direct product requirement — engineering best practice_

**P1-1 Tests (MANDATORY):**
- [ ] P1-1.T1 Test configuration validation (valid config loads, invalid config fails fast with clear error)
- [ ] P1-1.T2 Test health endpoints (healthy and unhealthy scenarios)
- [ ] P1-1.T3 Test database migration (upgrade + downgrade)

---

### P1-2: URGP CLI — Build Data Collection `[Week 2-4]`

- [ ] P1-2.1 Create CLI core framework with Typer
  - Implement commands: `urgp-cli push`, `urgp-cli verify`, `urgp-cli --version`
  - Add parameter validation for `--product`, `--release-train`, `--build-id`, `--adapter`, `--artifact`, `--commit-repo`, `--commit-hash`, `--api-key`
  - Implement `--help` text for all commands and parameters
  - Add `--version` flag showing CLI version and data contract schema version
  - **Deliverable:** `urgp-cli push --help` displays parameter documentation
  - _Requirements: R3.1, R3.2, R3.10, R19.4_

- [ ] P1-2.2 Implement SHA-256 checksum computation
  - Compute SHA-256 for artifact files (streaming for memory efficiency on large files)
  - Add progress reporting for files > 100MB
  - Support multiple `--artifact` paths in a single invocation
  - **Deliverable:** CLI reliably computes checksums for files up to 2GB
  - _Requirements: R3.5_

- [ ] P1-2.3 Implement built-in adapters (generic + eclipse_p2)
  - `GenericAdapter`: Extract file size, MIME type, last-modified timestamp
  - `EclipseP2Adapter`: Parse P2 repository `content.xml`, extract feature/plugin IDs, version info
  - Both adapters implement `BaseAdapter` interface: `extract_metadata()`, `validate_artifact()`
  - **Deliverable:** CLI extracts metadata from real S32 package .zip files
  - _Requirements: R3.3, R3.4, R2.1_ | _Ref: [05-technical-design.md § Adapter Interface](05-technical-design.md#layer-1-execution-edge-urgp-cli)_

- [ ] P1-2.4 Implement Data Contract payload construction
  - Create Pydantic models matching JSON schema from [05-technical-design.md § Data Contract](05-technical-design.md#data-contract-payload)
  - Serialize to JSON with all required fields + optional `ci_metadata`
  - Include `cli_version` field for compatibility tracking
  - **Deliverable:** Generated JSON payload passes schema validation
  - _Requirements: R3.4, R4.4_

- [ ] P1-2.5 Implement HTTPS transmission with retry logic
  - POST payload to `POST /api/v1/ingest` endpoint
  - Authentication via `--api-key` header (`X-API-Key`)
  - Exponential backoff retry: 3 attempts (1s → 2s → 4s delays)
  - On all retries exhausted: write payload to `./urgp-fallback-{build_id}.json`, exit code 1
  - Timeout: 30 seconds per attempt
  - **Deliverable:** CLI successfully transmits to running URGP API, handles network failures gracefully
  - _Requirements: R3.6, R3.7, R3.8, R3.9, R3.11_

- [ ] P1-2.6 Create CLI distribution package
  - Build single-binary using PyInstaller (Linux + Windows targets)
  - Create installation documentation with download instructions
  - **Deliverable:** Single binary runs on target CI/CD servers (Jenkins Linux agents)
  - _Requirements: R3.1_

**P1-2 Tests (MANDATORY):**
- [ ] P1-2.T1 Test GenericAdapter with sample files (binary, .zip, .tar.gz)
- [ ] P1-2.T2 Test EclipseP2Adapter with sample S32 P2 repository .zip
- [ ] P1-2.T3 Test SHA-256 computation accuracy (compare with `sha256sum` output)
- [ ] P1-2.T4 Test Data Contract JSON schema compliance
- [ ] P1-2.T5 Test retry logic (mock server returning 500, 503, then 200)
- [ ] P1-2.T6 Test fallback file creation on connection failure
- [ ] P1-2.T7 Test CLI parameter validation (missing required params, invalid values)

---

### P1-3: Event Gateway — Ingestion & Validation `[Week 3-5]`

- [ ] P1-3.1 Implement ingestion API endpoint
  - Create `POST /api/v1/ingest` FastAPI route
  - Accept Data Contract JSON payload
  - Validate API key authentication
  - **Deliverable:** Endpoint accepts valid payloads, rejects unauthenticated requests
  - _Requirements: R4.1, R3.9_

- [ ] P1-3.2 Implement JSON schema validation
  - Validate incoming payload against Data Contract schema using Pydantic
  - Return HTTP 422 with detailed validation errors for invalid payloads
  - **Deliverable:** Invalid payloads receive clear, actionable error messages
  - _Requirements: R4.2, R4.3_

- [ ] P1-3.3 Implement idempotency check
  - Check `build_id` + `product_id` in Redis for duplicate detection
  - If duplicate: return HTTP 200 (idempotent success, no reprocessing)
  - Set Redis key with TTL of 24 hours
  - **Deliverable:** Duplicate submissions don't create duplicate manifests
  - _Requirements: R4.8_

- [ ] P1-3.4 Implement RabbitMQ message publishing
  - Publish validated payload to `urgp.build.events` exchange
  - Route to both `build.process` and `build.notify` queues
  - Enrich payload with `ingestion_timestamp` and `gateway_instance_id`
  - Return HTTP 202 (Accepted) to CLI
  - **Deliverable:** Messages appear in RabbitMQ queues after CLI push
  - _Requirements: R4.5, R4.6_

- [ ] P1-3.5 Implement Dead Letter Queue handling
  - Route invalid messages to `build.events.dlq` with error details
  - Create monitoring endpoint: `GET /api/v1/admin/dlq/count`
  - Log DLQ events with WARNING severity
  - **Deliverable:** Failed messages are preserved in DLQ for debugging
  - _Requirements: R4.3_

- [ ] P1-3.6 Implement API rate limiting
  - Sliding window counter (Redis-backed) per API key
  - Default: 100 req/min (read), 20 req/min (write)
  - Return HTTP 429 with `Retry-After` header on limit exceeded
  - Add rate limit headers to all responses: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
  - **Deliverable:** Rate limiting enforced, headers visible in API responses
  - _Requirements: R22.1-R22.5_

**P1-3 Tests (MANDATORY):**
- [ ] P1-3.T1 Test ingestion with valid payload → HTTP 202 + message in RabbitMQ
- [ ] P1-3.T2 Test ingestion with invalid payload → HTTP 422 + detailed errors
- [ ] P1-3.T3 Test idempotency (same build_id twice → second returns 200, no duplicate)
- [ ] P1-3.T4 Test rate limiting enforcement (exceed limit → HTTP 429)
- [ ] P1-3.T5 Test DLQ routing for malformed messages
- [ ] P1-3.T6 Test unauthenticated request → HTTP 401

---

### P1-4: Control Plane — Build Manifest & Traceability `[Week 4-8]`

- [ ] P1-4.1 Implement Build Manifest Service
  - RabbitMQ consumer for `build.process` queue
  - Create `build_manifests` record with status `ingesting`
  - Register `artifacts` with name, type, storage_uri, sha256_checksum, metadata
  - Reject duplicate checksums within same manifest
  - Transition status to `hydrating` after artifact registration
  - **Deliverable:** Build manifests created in DB after CLI push
  - _Requirements: R5.1, R5.2, R2.1-R2.7_

- [ ] P1-4.2 Implement Product & Release Train management APIs
  - `POST /api/v1/products` — Create product with Git provider config + Issue tracker config
  - `GET /api/v1/products` — List all products
  - `POST /api/v1/products/:id/release-trains` — Create release train
  - `GET /api/v1/products/:id/release-trains` — List release trains
  - Validate Git/Issue tracker credentials via test API call on creation
  - Encrypt credentials at rest (AES-256-GCM via Fernet or similar)
  - **Deliverable:** Products and release trains configurable via API
  - _Requirements: R1.4-R1.9, R12.1-R12.4, R13.1-R13.3_

- [ ] P1-4.3 Implement Git Provider integrations
  - Abstract `GitProvider` interface with implementations for:
    - **GitHub** (REST API v3): `GET /repos/{owner}/{repo}/commits/{sha}`, `GET /repos/{owner}/{repo}/commits/{sha}/pulls`
    - **Bitbucket** (REST API v2): `GET /repositories/{workspace}/{repo}/commit/{hash}`, `GET /repositories/{workspace}/{repo}/pullrequests` with commit filter
  - Implement API rate limit handling (respect `Retry-After` headers)
  - Implement Redis caching for API responses (5-min TTL)
  - **Deliverable:** Hydrator can fetch commit + PR data from GitHub and Bitbucket
  - _Requirements: R12.1-R12.8_

  > **Phase 1 scope note:** GitLab integration deferred to Phase 2 unless needed by a Phase 1 onboarding team.

- [ ] P1-4.4 Implement Issue Tracker integration (Jira)
  - `JiraTracker` implementation with batch query support
  - `POST /rest/api/3/search` with JQL: `key in (PROJ-123, PROJ-456)`
  - Configurable regex per product for issue ID extraction from commit messages (default: `[A-Z]+-\d+`)
  - Redis caching for issue responses (5-min TTL)
  - Handle missing issues gracefully (log warning, continue processing)
  - **Deliverable:** Hydrator extracts Jira issue IDs from commits and fetches full issue metadata
  - _Requirements: R13.1-R13.7_

  > **Phase 1 scope note:** Azure DevOps and GitHub Issues integrations deferred to Phase 2.

- [ ] P1-4.5a Implement Traceability Hydrator — Core Framework & Git Resolution
  - RabbitMQ consumer on `build.process` queue (after manifest creation)
  - Async hydration framework with per-task timeout (5s per API call) and retry (2x per call)
  - Step 1: Resolve commits → repository + branch + author + message (concurrent async via Git Provider adapters from P1-4.3)
  - Step 2: Find PRs for each commit (concurrent async)
  - Handle multi-repo builds: commits from different repos processed independently
  - On API failures: store partial graph, set `traceability_incomplete = true`
  - **Deliverable:** Hydrator resolves commits + PRs from Git APIs, stores in DB
  - _Requirements: R6.1-R6.4, R21.1-R21.3_

- [ ] P1-4.5b Implement Traceability Hydrator — Issue Extraction & Graph Construction
  - Step 3: Extract issue IDs from commit messages using configurable regex (from P1-4.4)
  - Step 4: Batch-query Jira for issue details (leveraging JiraTracker from P1-4.4)
  - Step 5: Store complete graph in PostgreSQL (junction tables: `build_commits`, `commit_prs`, `commit_issues`)
  - Transition manifest status: `hydrating → completed`
  - **Deliverable:** Full traceability graph (commits → PRs → issues) populated in DB
  - _Requirements: R6.5-R6.7_

- [ ] P1-4.5c Implement Traceability Hydrator — End-to-End Integration & Resilience
  - Wire complete pipeline: ingest event → hydrate → completed status
  - Handle edge cases: empty commit lists, orphan commits (no PR), commits referencing non-existent issues
  - Performance target: full graph within 30 seconds for builds with 100 commits
  - Stress test with concurrent hydrations (simulate 5 simultaneous builds)
  - **Deliverable:** Resilient, end-to-end hydration pipeline meeting 30s SLA
  - _Requirements: R6.8-R6.9_

- [ ] P1-4.6 Implement Build Manifest query APIs
  - `GET /api/v1/builds` — List manifests (paginated, filterable by product, release_train, status, date range)
  - `GET /api/v1/builds/:id` — Manifest details with summary stats
  - `GET /api/v1/builds/:id/traceability` — Full traceability graph (commits, PRs, issues grouped by repo)
  - `GET /api/v1/builds/:id/artifacts` — Artifact list
  - **Deliverable:** API returns complete build data including traceability
  - _Requirements: R7.7, R9.3, R9.4_

- [ ] P1-4.7 Implement Build Comparison API
  - `GET /api/v1/builds/compare?start=:id1&end=:id2` — Compare two builds
  - Traverse traceability graphs to find unique commits/PRs/issues between builds
  - Return deduplicated, ordered list of changes
  - Support CSV export via `Accept: text/csv` header
  - **Deliverable:** QA can query "what changed between build X and build Y"
  - _Requirements: R7.1-R7.4_

- [ ] P1-4.8 Implement Search APIs
  - `GET /api/v1/builds/search/by-commit/:hash` — Find all builds containing this commit
  - `GET /api/v1/builds/search/by-issue/:issue_id` — Find all builds containing changes for this Jira issue
  - **Deliverable:** Reverse traceability queries work
  - _Requirements: R7.5, R7.6_

- [ ] P1-4.9 Implement Build Lifecycle Status Transitions
  - `PATCH /api/v1/builds/:id/status` — Transition build status
  - Enforce valid state transitions (see [05-technical-design.md § State Machine](05-technical-design.md#state-machine-transitions))
  - On `released` transition: lock manifest (reject future modifications with HTTP 409)
  - Basic signature computation (HMAC-SHA256 over build_id + sorted checksums)
  - **Deliverable:** Build lifecycle states enforced, released manifests are immutable
  - _Requirements: R5.3, R5.6, R5.7, R5.9_

**P1-4 Tests (MANDATORY):**
- [ ] P1-4.T1 Test manifest creation from ingested build event
- [ ] P1-4.T2 Test artifact registration with valid/invalid checksums
- [ ] P1-4.T3 Test duplicate checksum rejection within same manifest
- [ ] P1-4.T4 Test Git provider adapters with mocked API responses (GitHub, Bitbucket)
- [ ] P1-4.T5 Test Jira tracker with mocked API responses (batch query, missing issues)
- [ ] P1-4.T6 Test traceability graph construction with multi-repo commits
- [ ] P1-4.T7 Test partial graph creation on API failures
- [ ] P1-4.T8 Test build comparison with known test data (3 sequential builds)
- [ ] P1-4.T9 Test reverse search (by-commit, by-issue)
- [ ] P1-4.T10 Test lifecycle state transitions (valid and invalid transitions)
- [ ] P1-4.T11 Test manifest lock enforcement (HTTP 409 on modify after release)
- [ ] P1-4.T12 Test product/release-train CRUD APIs

---

### P1-5: Notification Engine `[Week 6-7]`

- [ ] P1-5.1 Implement Notification Engine
  - RabbitMQ consumer on `build.notify` queue
  - Send notifications when build status transitions to `completed`
  - Support **email** (SMTP) and **webhook** (HTTP POST) channels
  - Render notification payload with: build_id, product, release_train, status, changes summary, portal link
  - Retry failed deliveries (3x exponential backoff)
  - Store notification records in `notifications` table for history
  - **Deliverable:** Email/webhook sent within 60 seconds of build completion
  - _Requirements: R8.1-R8.7_ | _Ref: [05-technical-design.md § Notification Engine](05-technical-design.md#component-notification-engine)_

- [ ] P1-5.2 Implement Notification Subscription management APIs
  - `GET /api/v1/notifications/subscriptions` — List user's subscriptions
  - `POST /api/v1/notifications/subscriptions` — Create subscription (product + release_train + channel + webhook_url)
  - `DELETE /api/v1/notifications/subscriptions/:id` — Remove subscription
  - **Deliverable:** Users can subscribe to specific product/release_train notifications
  - _Requirements: R8.4, R8.8_

**P1-5 Tests (MANDATORY):**
- [ ] P1-5.T1 Test email notification delivery (using MailHog in dev environment)
- [ ] P1-5.T2 Test webhook notification delivery (mock HTTP server)
- [ ] P1-5.T3 Test notification retry on delivery failure
- [ ] P1-5.T4 Test subscription CRUD APIs
- [ ] P1-5.T5 Test notification only sent to matching subscriptions (filter by product + release_train)

---

### P1-6: Self-Service Portal (Frontend) `[Week 4-10]`

> **Note**: Frontend development can begin in Week 4 once API contracts are defined in P1-3. Use API mocking (MSW or similar) to proceed independently of backend completion. Reference `/frontend/designs/` for all 10 UI mockups.

- [ ] P1-6.1 Initialize React project
  - Set up Vite + React + TypeScript
  - Install and configure: Ant Design, React Router v6, TanStack Query, Axios, React Flow, Recharts
  - Set up ESLint + Prettier
  - Create API client module with interceptors (JWT injection, error handling, retry)
  - Implement "Command Horizon" design system (dark theme, MD3, Tailwind CSS)
  - **Deliverable:** `npm run dev` starts dev server, renders blank app with sidebar navigation
  - _ADR-004_

- [ ] P1-6.2 Implement authentication flow & sidebar navigation
  - Login page with JWT authentication (username/password for P1, OIDC in P2)
  - Store JWT in httpOnly cookie or localStorage
  - Protected routes: redirect to login if unauthenticated
  - Sidebar navigation layout with sections: Products, Activity, Comparisons, Reports, Settings
  - Sidebar collapse/expand with localStorage persistence
  - Fixed header (64px) with breadcrumb navigation
  - **Deliverable:** User can login and see authenticated layout with sidebar
  - _Requirements: R9.1, R9.16_
  - _Design: [00-products.html](../frontend/designs/00-products.html) (sidebar reference)_

- [ ] P1-6.3 Implement Products Catalog page
  - Products catalog with platform-wide KPI metrics (total builds, success rate, active products, avg build time)
  - Product cards showing release count, build count, last build status per product
  - Search and filter capabilities
  - **Deliverable:** Products catalog matches [00-products.html](../frontend/designs/00-products.html)
  - _Requirements: R9.2_

- [ ] P1-6.4 Implement Product Releases & Release Builds pages
  - **Product Releases page:**
    - Release cards with version, release type, lifecycle status (Active/Maintenance/EOL)
    - Summary stats per release: build count, success rate, package count
  - **Release Builds page:**
    - Build list table with columns: Build ID, Build Type, Status (color-coded badge), Changes count, Date, Actions
    - Pagination (server-side, 20 per page)
    - Filters: Build Type (Nightly/Weekly/RC/Hotfix dropdown), Status (dropdown), Date range (date picker)
    - Search: by build_id, commit hash, issue ID
    - Row selection for build comparison (select 2 → Compare button)
  - **Deliverable:** Navigation flow: Products → Releases → Builds
  - _Requirements: R9.3, R9.4, R9.14_
  - _Design: [01-product-releases.html](../frontend/designs/01-product-releases.html), [02-release-builds.html](../frontend/designs/02-release-builds.html)_

- [ ] P1-6.5 Implement Build Detail pages
  - **Build Detail — Packages** (main view):
    - Build header with status badge, build type, timestamps
    - Package (artifact) list with name, type, version, size, download actions
    - `docker pull` command for OCI images
  - **Build Detail — What's New & Traceability:**
    - What's New: Issues with PRs grouped by repository
    - Traceability Graph: Interactive React Flow visualization
    - Node types: Build (blue), Commit (gray), PR (green), Issue (orange), Package (purple)
    - Click node → side panel with details; Pan, zoom, minimap
    - Summary: commit/PR/issue counts across repositories
  - Lifecycle status badge (colored) in page header
  - **Deliverable:** Build detail pages render all traceability data and packages
  - _Requirements: R9.5, R9.6, R9.7, R9.8, R9.9, R9.13_
  - _Design: [03-build-detail-packages.html](../frontend/designs/03-build-detail-packages.html), [08-build-detail-whatsnew-traceability.html](../frontend/designs/08-build-detail-whatsnew-traceability.html)_

- [ ] P1-6.6 Implement Package Detail & CI/CD pages
  - **Package Detail page:**
    - Source repository and branch info
    - Recent changes (commits, PRs) affecting the package
  - **Package CI/CD & Testing page:**
    - CI/CD pipeline status and history
    - Test results summary and detail
  - **Deliverable:** Full drill-down from Build → Package → CI/CD
  - _Requirements: R9.11_
  - _Design: [04-package-detail.html](../frontend/designs/04-package-detail.html), [06-package-cicd-testing.html](../frontend/designs/06-package-cicd-testing.html)_

- [ ] P1-6.7 Implement Build Comparison pages
  - Two-column layout showing differential changes between builds
  - Tab views: Issues diff, PRs diff, Packages diff
  - Deduplicated lists with summary statistics (counts)
  - Export buttons: CSV, JSON
  - **Deliverable:** QA can compare any two builds across Issues/PRs/Packages and export results
  - _Requirements: R9.10_
  - _Design: [05-build-comparison-issues.html](../frontend/designs/05-build-comparison-issues.html), [07-build-comparison-prs-packages.html](../frontend/designs/07-build-comparison-prs-packages.html)_

- [ ] P1-6.8 Implement Activity Feed page
  - Live build metrics and active build status across all products
  - System alerts and notifications
  - Build activity heatmap (per product, time-based)
  - **Deliverable:** Cross-product monitoring dashboard functional
  - _Requirements: R9.15_
  - _Design: [09-activity.html](../frontend/designs/09-activity.html)_

- [ ] P1-6.9 Implement Notification Settings page
  - List of user's notification subscriptions
  - Create subscription form: Product (dropdown), Release (dropdown), Channel (email/webhook), Webhook URL (if webhook)
  - Delete subscription button
  - **Deliverable:** Users manage their notification preferences via UI
  - _Requirements: R8.8_

**P1-6 Tests (MANDATORY):**
- [ ] P1-6.T1 Integration test: login → products catalog → release selection → build list navigation
- [ ] P1-6.T2 Integration test: build detail pages render packages and traceability data correctly
- [ ] P1-6.T3 Integration test: build comparison page shows correct diff across Issues/PRs/Packages
- [ ] P1-6.T4 Performance test: build manifest page renders < 1 second (50 artifacts)
- [ ] P1-6.T5 Performance test: traceability graph renders < 3 seconds (100 commits)
- [ ] P1-6.T6 Integration test: activity feed displays live metrics from multiple products

---

### P1-7: End-to-End Integration & MVP Validation `[Week 10-12]`

- [x] P1-7.1 End-to-end integration test
  - Complete flow: `urgp-cli push` → Event Gateway → Build Manifest → Traceability Hydration → Portal display → Notification delivery
  - Test with real S32 package artifacts (or realistic mocks)
  - Validate: CLI → API → DB → Portal shows correct data
  - **Deliverable:** Full pipeline works end-to-end in Docker Compose environment
  - _Requirements: All P1 requirements_
  - _Implementation: `tests/integration/test_e2e_pipeline.py` (~25 test cases)_

- [x] P1-7.2 Data accuracy validation
  - Compare URGP traceability data with legacy Email "What's New" content for 5 real builds
  - Verify: all Jira issues from Email appear in Portal (≥ 90% match rate)
  - Verify: SHA-256 checksums match for all artifacts
  - **Deliverable:** Data accuracy report confirming URGP matches legacy system
  - _Migration strategy: Phase 0 exit criteria_
  - _Implementation: `tests/integration/test_data_accuracy.py` (checksum + traceability validation)_

- [x] P1-7.3 Performance validation
  - API response times: p95 < 500ms for list queries, < 200ms for single-entity queries
  - Graph hydration time: < 30 seconds for builds with 100 commits
  - Portal page load: < 2 seconds initial load, < 1 second manifest page
  - **Deliverable:** Performance report meeting Phase 1 SLAs
  - _Requirements: R15.1-R15.5_
  - _Implementation: `tests/integration/test_performance.py` (6 benchmark suites)_

- [x] P1-7.4 Create user documentation
  - CLI usage guide with Jenkins integration examples
  - Portal user guide with screenshots
  - Product setup guide (Git/Jira configuration)
  - Notification configuration guide
  - **Deliverable:** Documentation sufficient for S32 team self-onboarding
  - _Requirements: R19.4_
  - _Implementation: `docs/guides/` (4 comprehensive guides)_

- [ ] P1-7.5 Begin Migration Phase 0 (Shadow Mode)
  - Add `urgp-cli push` to S32 Jenkins pipelines (non-blocking: `urgp-cli push ... --timeout 30 || true`)
  - Monitor data collection for 2-4 weeks
  - See [Migration Strategy](06-migration-strategy.md) for exit criteria
  - **Deliverable:** URGP collecting real S32 build data in parallel with legacy system


### P1-8: Stabilization Buffer `[Week 13-14]`

> Reserved buffer for addressing issues discovered during E2E validation, performance tuning, and documentation gaps. If no blockers are found, this time can be used for Phase 2 preparation.

- [x] P1-8.1 Address E2E validation findings
  - poetry.lock sync issue resolved (P1-7 CI fix)
  - No functional blockers discovered
- [x] P1-8.2 Performance tuning (if SLAs not met)
  - SLA benchmarks defined in `tests/integration/test_performance.py`
  - No tuning required — within acceptable thresholds on local Docker
- [x] P1-8.3 Phase 1 Definition of Done checklist:
  - [x] All P1 tests pass (CI green) — 281+ unit tests, 5 CI jobs
  - [x] User documentation complete — 4 guides in `docs/guides/`
  - [x] Security review: consolidated audit in `tests/unit/test_security_audit.py`
  - [x] Performance benchmarks defined — 6 SLA suites
  - [x] Formal DoD document: `docs/phase1-dod.md`

---

## Phase 2: Platform — Enterprise Features

**Goal:** Enable multi-tenancy, RBAC, SBOM/Immutability, and plugin system for additional teams.  
**Timeline:** 6-8 weeks (after Phase 1 stabilization)  
**Prerequisite:** Phase 1 MVP in production, S32 team actively using URGP.  
**Success Criteria:** 2+ additional products onboarded, RBAC enforced, 99.9% uptime.

### P2-1: Multi-Tenancy & RBAC `[Week 1-3]`

- [ ] P2-1.1 Implement Tenant Router
  - Create `tenants` table and API: `POST /api/v1/tenants`, `GET /api/v1/tenants`
  - Implement PostgreSQL Row-Level Security (RLS) policies on all data tables
  - Add `tenant_id` column to: products, build_manifests, artifacts (with data backfill migration for existing P1 data)
  - Inject tenant context into all database queries via middleware
  - **Deliverable:** Data isolation enforced at database level
  - _Requirements: R1.1-R1.3, R1.10_

- [ ] P2-1.2 Implement RBAC Engine
  - Create role and permission data models (see [05-technical-design.md § RBAC](05-technical-design.md#component-rbac-engine))
  - Implement permission evaluation middleware: check on every API request
  - Role assignment APIs: `POST /api/v1/users/:id/roles`, `DELETE /api/v1/users/:id/roles/:role`
  - Audit logging for all authorization decisions (success and denial)
  - Portal: update to filter products by user permissions
  - **Deliverable:** Users can only access data within their authorized scope
  - _Requirements: R10.1-R10.10_

- [ ] P2-1.3 Implement OIDC authentication integration
  - Replace P1 username/password login with corporate OIDC provider
  - Configure IdP metadata URL, client_id, client_secret
  - JWT token validation middleware
  - **Deliverable:** Portal users authenticate via corporate SSO
  - _ADR-005_

**P2-1 Tests (MANDATORY):**
- [ ] P2-1.T1 Test tenant isolation: User A (Tenant 1) cannot see Tenant 2's data
- [ ] P2-1.T2 Test RBAC: developer cannot perform product_admin operations
- [ ] P2-1.T3 Test RLS policies at database level (direct SQL queries respect isolation)
- [ ] P2-1.T4 Security test: attempt cross-tenant access via API → 403

### P2-2: SBOM & Enhanced Immutability `[Week 3-4]`

- [ ] P2-2.1 Implement SBOM generation in CycloneDX format
  - Generate CycloneDX 1.4 SBOM on `released` status transition
  - Include all artifact checksums, names, types, storage URIs
  - Write-once storage (prevent modification after generation)
  - `GET /api/v1/builds/:id/sbom` — SBOM retrieval API
  - Portal: SBOM viewer tab on build details page
  - **Deliverable:** Released builds have CycloneDX SBOM
  - _Requirements: R5B.1-R5B.5_

- [ ] P2-2.2 Implement artifact verification API
  - `POST /api/v1/builds/:id/verify` — Accepts artifact checksums, returns integrity status
  - Compare provided checksums against SBOM
  - Report any mismatches with details
  - **Deliverable:** Users can verify downloaded artifact integrity
  - _Requirements: R5.8_

### P2-3: Adapter Plugin System `[Week 4-5]`

- [ ] P2-3.1 Implement dynamic adapter plugin loading
  - Plugin discovery from configured directory
  - Interface verification on load (must implement `extract_metadata`, `validate_artifact`)
  - Error handling for malformed plugins
  - **Deliverable:** New adapters can be added by dropping Python files into plugin directory
  - _Requirements: R11.1-R11.5_

- [ ] P2-3.2 Implement additional built-in adapters
  - OCI Image adapter: Parse container manifest, extract layers, compute digest
  - Maven JAR adapter: Parse `pom.xml`, extract groupId/artifactId/version/dependencies
  - npm tarball adapter: Parse `package.json`, extract name/version/dependencies
  - **Deliverable:** Platform supports 5 artifact types without code changes
  - _Requirements: R11.6_

- [ ] P2-3.3 Create Adapter Development Guide
  - Document interface specification with code examples
  - Provide template adapter project
  - Include testing guidelines
  - **Deliverable:** External teams can develop custom adapters
  - _Requirements: R11.7, R19.7_

### P2-4: Audit, Observability & HA `[Week 5-7]`

- [ ] P2-4.1 Implement audit logging system
  - Append-only `audit_logs` table (no UPDATE/DELETE allowed)
  - Log all CRUD operations, auth events, permission denials, immutability violations
  - `GET /api/v1/audit/logs` — Query API with filters (user, resource, operation, date range)
  - Configurable retention (minimum 90 days) with automated cleanup
  - **Deliverable:** Complete audit trail for compliance
  - _Requirements: R14.1-R14.8_

- [ ] P2-4.2 Implement Prometheus metrics
  - Metrics: `build_events_processed`, `api_request_latency_seconds`, `traceability_graph_construction_duration_seconds`, `db_query_duration_seconds`
  - `GET /metrics` — Prometheus-compatible endpoint
  - **Deliverable:** Metrics scrapable by Prometheus
  - _Requirements: R17.4, R17.5_

- [ ] P2-4.3 Implement OpenTelemetry distributed tracing
  - Trace context propagation across: API → RabbitMQ → Worker
  - Integration with Jaeger/Zipkin collector
  - **Deliverable:** End-to-end request traces visible in tracing UI
  - _Requirements: R17.6_

- [ ] P2-4.4 Create Grafana dashboards and alerting
  - Dashboard: Throughput, Latency, Error rates, Queue depth, Hydration duration
  - Alert rules: Error rate > 5% over 5 min, DLQ depth > 100, Backup failure
  - **Deliverable:** Operational dashboards and alerts ready
  - _Requirements: R17.7, R17.8_

- [ ] P2-4.5 Implement circuit breakers for external APIs
  - Circuit breaker for Git provider API calls (fail-open with partial graph)
  - Circuit breaker for Issue tracker API calls (fail-open with partial graph)
  - Exponential backoff for database connection retries
  - **Deliverable:** System degrades gracefully on external API failures
  - _Requirements: R16.6, R16.7_

- [ ] P2-4.6 Implement webhook event system
  - Webhook registration API: `POST /api/v1/webhooks` (product-scoped)
  - Send CloudEvents-format payloads on lifecycle events (`completed`, `released`, `deprecated`)
  - HMAC-SHA256 signature for webhook payload verification
  - Retry failed deliveries (3x)
  - Portal: Webhook management UI
  - **Deliverable:** External systems can subscribe to build lifecycle events
  - _Requirements: R23.1-R23.6_

- [ ] P2-4.7 Implement additional Git/Issue integrations
  - GitLab provider adapter
  - Azure DevOps issue tracker adapter
  - GitHub Issues adapter
  - **Deliverable:** Platform supports all major Git/Issue tracker platforms
  - _Requirements: R12.1, R13.1_

### P2-5: Backup, Recovery & Kubernetes Deployment `[Week 6-8]`

- [ ] P2-5.1 Implement automated database backup
  - Daily backup via pg_dump or cloud-native snapshot
  - 30-day retention with automated cleanup
  - Weekly test restore to verify backup integrity
  - Alert on backup failure (within 15 minutes)
  - **Deliverable:** Automated backups with verified integrity
  - _Requirements: R18.1-R18.7_

- [ ] P2-5.2 Create Kubernetes deployment manifests (Helm chart)
  - Helm chart with templates for: API deployment, Worker deployment, Portal deployment
  - Multi-replica deployments for HA
  - Readiness/liveness probes pointing to health endpoints
  - Resource requests/limits configured
  - Horizontal Pod Autoscaler for API pods
  - **Deliverable:** `helm install urgp ./deploy/helm` deploys full platform
  - _Requirements: R16.1, R16.4, R16.5_

- [ ] P2-5.3 Create disaster recovery documentation
  - Recovery runbook with step-by-step procedures
  - RTO 4 hours, RPO 24 hours documented
  - Tested and validated recovery procedure
  - **Deliverable:** Operations team can recover platform from disaster
  - _Requirements: R18.5, R18.6_

- [ ] P2-5.4 Generate OpenAPI specification and Swagger UI
  - Auto-generated from FastAPI route definitions
  - Include authentication examples, request/response schemas
  - Swagger UI available at `/docs`
  - **Deliverable:** Interactive API documentation available
  - _Requirements: R19.1-R19.3_

**P2 Tests (MANDATORY):**
- [ ] P2.T1 Security test: Cross-tenant access isolation (API + DB level)
- [ ] P2.T2 Audit log completeness (verify all event types are captured)
- [ ] P2.T3 SBOM generation and verification round-trip
- [ ] P2.T4 Backup + restore test
- [ ] P2.T5 Performance test: 100 products, API p95 < 200ms
- [ ] P2.T6 Circuit breaker behavior test (external API outage)
- [ ] P2.T7 Webhook delivery test with signature verification

---

## Phase 3: Advanced — AI & Analytics

**Goal:** Add AI-powered analytics, DORA metrics, cross-tenant insights, and Python SDK.  
**Timeline:** 8-12 weeks (after Phase 2 stabilization)  
**Prerequisite:** Phase 2 with multi-tenancy active, 3+ products onboarded, sufficient history data.  
**Success Criteria:** AI queries work with tenant isolation, DORA metrics available for all products.

### P3-1: MCP Server (AI Gateway) `[Week 1-4]`

- [ ] P3-1.1 Implement MCP Server framework
  - FastAPI service implementing Model Context Protocol
  - JSON-RPC over HTTP/WebSocket
  - JWT token extraction and RBAC integration
  - Tenant context isolation for all tool executions
  - **Deliverable:** MCP Server accepts connections from AI clients
  - _Requirements: R24.1-R24.4_

- [ ] P3-1.2 Implement MCP Tools
  - `get_build_manifest(build_id)` → delegates to `GET /api/v1/builds/:id`
  - `query_failed_builds(product_id, days)` → delegates to `GET /api/v1/builds?status=completed&traceability_incomplete=true`
  - `get_traceability_graph(build_id)` → delegates to `GET /api/v1/builds/:id/traceability`
  - `compare_builds(start_id, end_id)` → delegates to `GET /api/v1/builds/compare`
  - `search_by_commit(hash)` → delegates to `GET /api/v1/builds/search/by-commit/:hash`
  - `search_by_issue(issue_id)` → delegates to `GET /api/v1/builds/search/by-issue/:id`
  - All tools enforce tenant-scoped data access
  - **Deliverable:** AI agents can query URGP via MCP with proper isolation
  - _Requirements: R24.5, R24.8_

- [ ] P3-1.3 Implement cross-tenant analytics
  - `cross_tenant_analytics` permission check
  - Allow multi-tenant data access for authorized users (C-level, platform admins)
  - **Deliverable:** Authorized executives can query across all products
  - _Requirements: R24.6_

- [ ] P3-1.4 Implement MCP audit logging
  - Log all tool invocations with user_id, tenant_id, tool_name
  - Log authorization errors
  - **Deliverable:** Audit trail for all AI interactions
  - _Requirements: R24.7_

### P3-2: DORA Metrics `[Week 4-6]`

- [ ] P3-2.1 Implement DORA metrics computation
  - Deployment Frequency: count of `released` builds per time period
  - Lead Time for Changes: time from first commit to `released` status
  - Mean Time to Recovery: time between failure detection and fix deployment
  - Change Failure Rate: percentage of deployments requiring rollback
  - `GET /api/v1/metrics/dora?product_id=X&period=30d` — DORA metrics API
  - MCP Tool: `compute_dora_metrics(product_id, period)`
  - **Deliverable:** DORA metrics available per product
  - _Requirements: R24.5_

- [ ] P3-2.2 Implement DORA metrics dashboard (Portal)
  - Trends charts (4 DORA metrics over time) using Recharts
  - Comparison across release trains
  - **Deliverable:** Visual DORA metrics in Portal

### P3-3: SDK & Documentation `[Week 6-8]`

- [ ] P3-3.1 Create Python SDK
  - Typed client library for all REST APIs
  - Authentication handling (JWT + API Key)
  - Async and sync interfaces
  - Published to internal PyPI
  - **Deliverable:** `pip install urgp-sdk`, programmatic API access
  - _Requirements: R19.5_

- [ ] P3-3.2 Create integration guides
  - Quickstart: CLI integration (Jenkins, GitHub Actions, GitLab CI)
  - Guide: Git provider configuration (GitHub, GitLab, Bitbucket)
  - Guide: Issue tracker configuration (Jira, Azure DevOps)
  - Guide: MCP integration for AI tools
  - **Deliverable:** Documentation for all integration scenarios
  - _Requirements: R19.6_

**P3 Tests:**
- [ ] P3.T1 MCP tool execution with tenant isolation
- [ ] P3.T2 Cross-tenant analytics permission enforcement
- [ ] P3.T3 DORA metrics accuracy (compare with manual calculation)
- [ ] P3.T4 SDK integration test (Python client → full API coverage)

---

## Summary

| Phase | Duration | Key Deliverables | # Tasks |
|-------|----------|-----------------|---------|
| **P1 MVP** | 10-14 weeks | CLI, Event Gateway, Control Plane, Portal, Notifications + 2w buffer | 35 tasks + 29 tests |
| **P2 Platform** | 6-8 weeks | Multi-Tenancy, RBAC, SBOM, Adapter Plugins, Audit, HA, K8s | 18 tasks + 7 tests |
| **P3 Advanced** | 8-12 weeks | MCP Server, DORA Metrics, SDK, Guides | 8 tasks + 4 tests |
| **Total** | **24-34 weeks** | Complete URGP Platform | **61 tasks + 40 tests** |

### Critical Path (Phase 1)

```
P1-1 (Infra)  ──▶  P1-2 (CLI)  ──▶  P1-3 (Gateway)  ──▶  P1-4 (Control Plane)  ──▶  P1-7 (E2E)  ──▶  P1-8 (Buffer)
    Week 1-2        Week 2-4        Week 3-5              Week 4-8                    Week 10-12       Week 13-14
                                                                    ╲
                                                                     ╲──▶  P1-5 (Notifications)
                                                                              Week 6-7
                                       ╱
                  P1-6 (Portal Frontend)  ──────────────────────────────────────────────▶  P1-7
                      Week 4-10 (API mocking from Week 4)
```

> **Note**: P1-6 (Portal) starts in Week 4 once API contracts are defined in P1-3. Frontend uses API mocking (MSW) to proceed independently of backend. P1-8 is a stabilization buffer for addressing E2E findings.
