# Detailed Design: Universal Release Governance Platform (URGP)

## Overview

The Universal Release Governance Platform (URGP) is an enterprise-grade, multi-tenant platform that provides centralized release governance, traceability, and immutability guarantees for software delivery across unlimited teams and products. The platform transforms fragmented, file-driven build systems into a unified, data-driven control plane that is technology-agnostic.

This design document translates the [requirements](04-requirements.md) into concrete technical specifications, data models, and component interfaces. All technology decisions reference the [Architecture Decision Records](03-architecture-decisions.md).

### Design Goals

1. **Technology Agnosticism**: Support any artifact type (Eclipse P2, OCI images, Maven JARs, npm packages) without platform code changes
2. **Multi-Tenant Isolation** (Phase 2): Enable unlimited products with complete data and configuration isolation
3. **Federated Execution**: Integrate with existing CI/CD pipelines without requiring orchestrator replacement
4. **Immutability Guarantees**: Enforce write-once semantics for released artifacts with cryptographic verification
5. **Complete Traceability**: Construct multi-dimensional graphs linking builds to source code changes, pull requests, and work items
6. **Self-Service Experience**: Enable developers to query build history and download artifacts without manual intervention
7. **Push Notifications**: Proactively notify stakeholders when builds complete, replacing legacy email announcements

### Committed Technology Stack

| Component | Technology | ADR Reference |
|-----------|-----------|---------------|
| Backend Framework | **FastAPI** (Python 3.11+, async) | [ADR-003](03-architecture-decisions.md#adr-003-backend-framework) |
| Database | **PostgreSQL 16** (JSONB, recursive CTEs, RLS) | [ADR-001](03-architecture-decisions.md#adr-001-graph-storage-engine) |
| Message Broker | **RabbitMQ** (with Dead Letter Exchange) | [ADR-002](03-architecture-decisions.md#adr-002-message-broker) |
| Caching | **Redis** (API response cache, 5-min TTL) | — |
| Frontend | **React + TypeScript** (Vite, TanStack Query, Ant Design, React Flow) | [ADR-004](03-architecture-decisions.md#adr-004-frontend-framework--libraries) |
| Auth | **JWT + API Keys** (OIDC integration) | [ADR-005](03-architecture-decisions.md#adr-005-authentication--authorization-strategy) |
| Dev Environment | **Docker Compose** | [ADR-006](03-architecture-decisions.md#adr-006-deployment-model) |
| Prod Environment | **Kubernetes** (Helm, ArgoCD) | [ADR-006](03-architecture-decisions.md#adr-006-deployment-model) |
| AI Integration | **REST APIs** (Phase 1-2), **MCP Server** (Phase 3) | [ADR-007](03-architecture-decisions.md#adr-007-ai-integration-strategy) |

### Design Principles

- **Separation of Concerns**: Clear boundaries between execution (CI/CD), ingestion (Event Gateway), governance (Control Plane), and presentation (Portal)
- **Contract-Driven Integration**: Standardized JSON schemas for all inter-component communication
- **Plugin Architecture** (Phase 2): Extensible adapter system for supporting new artifact types
- **API-First Design**: All functionality exposed through REST APIs with auto-generated OpenAPI documentation
- **Defense in Depth**: Multiple layers of validation, authentication, and authorization
- **Async by Default**: External API calls (Git, Jira) execute asynchronously using Python's asyncio

---

## Architecture

### 5-Layer Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 5: Self-Service Portal (React + TypeScript)                   │
│ ┌──────────┬──────────┬──────────┬───────────┬──────────────────┐  │
│ │ Products │ Releases │ Builds   │ Build     │ Build            │  │
│ │ Catalog  │ List     │ List     │ Details   │ Comparison       │  │
│ ├──────────┼──────────┼──────────┼───────────┼──────────────────┤  │
│ │ Activity │ Package  │ Package  │ What's New│ Traceability     │  │
│ │ Feed     │ Detail   │ CI/CD    │ Table     │ Graph (React Flow│  │
│ └──────────┴──────────┴──────────┴───────────┴──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS/REST (TanStack Query)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 4: AI Gateway — Phase 3 only (MCP Server)                     │
│ - Thin wrapper over REST APIs                                       │
│ - Tenant-aware context isolation                                    │
│ - DORA metrics computation                                          │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ REST APIs (Phases 1-2) / MCP (Phase 3)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 3: Control Plane (FastAPI + PostgreSQL + Redis)                │
│ ┌─────────┬──────────┬─────────────┬──────────┬──────────────────┐ │
│ │ Tenant  │ RBAC     │ Traceability│ Immutabi-│ Notification     │ │
│ │ Router  │ Engine   │ Hydrator    │ lity Ctrl│ Engine           │ │
│ │ (P2)    │ (P2)     │ (async)     │ (P1/P2)  │ (P1)             │ │
│ └─────────┴──────────┴─────────────┴──────────┴──────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────┐│
│ │ PostgreSQL: tenants, products, manifests, artifacts,            ││
│ │             commits, pull_requests, issues, traceability_edges  ││
│ └──────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Internal async consumption
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 2: Event Gateway (RabbitMQ + Schema Validator)                 │
│ - Exchange: urgp.build.events                                       │
│ - Dead Letter Exchange: urgp.build.events.dlx                       │
│ - JSON Schema validation → reject invalid → DLQ                    │
│ - Idempotency check (build_id + product_id)                        │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS (AMQP publish via HTTPS API)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 1: Execution Edge (URGP CLI)                                  │
│ - Single binary (PyInstaller / Nuitka)                              │
│ - Built-in adapters: generic, eclipse_p2 (P1)                      │
│ - Plugin adapters: oci_image, maven_jar, npm_tarball (P2)           │
│ - SHA-256 checksum computation                                      │
│ - Retry with exponential backoff + local fallback                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Entity Relationship Diagram

```
┌──────────────┐     1:N     ┌──────────────┐     1:N     ┌───────────────┐
│   tenants    │────────────▶│   products   │────────────▶│   releases    │
│              │             │              │             │               │
│ id (PK)      │             │ id (PK)      │             │ id (PK)       │
│ name         │             │ tenant_id(FK)│             │ product_id(FK)│
│ namespace    │             │ name         │             │ version       │
│ created_at   │             │ git_config   │             │ release_type  │
│ updated_at   │             │ issue_config │             │ status        │
│              │             │ created_at   │             │ created_at    │
└──────────────┘             └──────────────┘             └───────────────┘
                                                                 │
                                                                 │ 1:N
                                                                 ▼
                                                    ┌──────────────────────┐
                                                    │   build_manifests    │
                                                    │                      │
                                                    │ id (PK)              │
                                                    │ build_id (unique)    │
                                                    │ product_id (FK)      │
                                                    │ release_id (FK)      │
                                                    │ build_type (enum)    │
                                                    │ status (enum)        │
                                                    │ traceability_incomplete│
                                                    │ sbom_reference       │
                                                    │ signature            │
                                                    │ created_at           │
                                                    │ released_at          │
                                                    └──────────┬───────────┘
                                                               │
                             ┌─────────────────────────────────┼───────────────────────┐
                             │ 1:N                             │ 1:N                   │ 1:N
                             ▼                                 ▼                       ▼
                ┌────────────────────┐            ┌──────────────────┐    ┌───────────────────┐
                │   artifacts        │            │  build_commits   │    │  notifications    │
                │                    │            │  (junction)      │    │                   │
                │ id (PK)            │            │ build_id (FK)    │    │ id (PK)           │
                │ manifest_id (FK)   │            │ commit_id (FK)   │    │ manifest_id (FK)  │
                │ name               │            └────────┬─────────┘    │ channel           │
                │ type (enum)        │                     │              │ status            │
                │ storage_uri        │                     │ N:1          │ sent_at           │
                │ sha256_checksum    │                     ▼              └───────────────────┘
                │ metadata (JSONB)   │            ┌──────────────────┐
                │ created_at         │            │    commits       │
                └────────────────────┘            │                  │
                                                  │ id (PK)          │
                                                  │ hash (unique)    │
                                                  │ repository       │
                                                  │ branch           │
                                                  │ author           │
                                                  │ message          │
                                                  │ timestamp        │
                                                  └────────┬─────────┘
                                                           │
                                          ┌────────────────┼─────────────────┐
                                          │ N:M            │                 │ N:M
                                          ▼                │                 ▼
                             ┌──────────────────┐          │    ┌──────────────────┐
                             │ commit_prs       │          │    │ commit_issues    │
                             │ (junction)       │          │    │ (junction)       │
                             │ commit_id (FK)   │          │    │ commit_id (FK)   │
                             │ pr_id (FK)       │          │    │ issue_id (FK)    │
                             └────────┬─────────┘          │    └────────┬─────────┘
                                      │ N:1                │             │ N:1
                                      ▼                    │             ▼
                             ┌──────────────────┐          │    ┌──────────────────┐
                             │ pull_requests    │          │    │    issues        │
                             │                  │          │    │                  │
                             │ id (PK)          │          │    │ id (PK)          │
                             │ external_id      │          │    │ external_id      │
                             │ repository       │          │    │ tracker_type     │
                             │ title            │          │    │ title            │
                             │ author           │          │    │ status           │
                             │ source_branch    │          │    │ priority         │
                             │ target_branch    │          │    │ assignee         │
                             │ merge_timestamp  │          │    │ labels (JSONB)   │
                             │ url              │          │    │ url              │
                             └──────────────────┘          │    └──────────────────┘
                                                           │
                                                  ┌────────┘
                                                  │ Additional tables
                                                  ▼
                             ┌──────────────────┐          ┌──────────────────────┐
                             │  audit_logs (P2) │          │ notification_subs    │
                             │                  │          │                      │
                             │ id (PK)          │          │ id (PK)              │
                             │ timestamp        │          │ user_id              │
                             │ user_id          │          │ product_id (FK)      │
                             │ operation_type   │          │ release_id (FK)      │
                             │ resource_type    │          │ channel (enum)       │
                             │ resource_id      │          │ webhook_url          │
                             │ change_details   │          │ active               │
                             └──────────────────┘          └──────────────────────┘
```

### Database Schema (PostgreSQL)

#### Core Enums

```sql
CREATE TYPE build_status AS ENUM (
    'ingesting',    -- Build event received, artifacts being registered
    'hydrating',    -- Traceability Hydrator is constructing the graph
    'completed',    -- Graph construction done, ready for testing
    'testing',      -- QA has marked this build as under test
    'released',     -- Officially released, manifest is locked/immutable
    'deprecated'    -- Superseded by a newer release
);

CREATE TYPE artifact_type AS ENUM (
    'eclipse_p2',
    'oci_image',
    'binary',
    'npm_tarball',
    'maven_jar',
    'python_wheel',
    'generic'
);

CREATE TYPE notification_channel AS ENUM (
    'email',
    'webhook'
);

CREATE TYPE build_type AS ENUM (
    'nightly',
    'weekly',
    'rc',
    'hotfix'
);

CREATE TYPE user_role AS ENUM (
    'platform_admin',
    'product_admin',
    'developer',
    'tester',
    'viewer'
);
```

#### State Machine Transitions

```
                  ┌──────────┐
                  │ingesting │
                  └────┬─────┘
                       │ (auto: event processed)
                       ▼
                  ┌──────────┐
                  │hydrating │
                  └────┬─────┘
                       │ (auto: hydration complete or timeout)
                       ▼
                  ┌──────────┐
             ┌───▶│completed │◀──── (traceability_incomplete flag if APIs fail)
             │    └────┬─────┘
             │         │ (manual: QA starts testing)
             │         ▼
             │    ┌──────────┐
             │    │ testing  │
             │    └────┬─────┘
             │         │ (manual: authorized user approves release)
             │         ▼
             │    ┌──────────┐
             │    │ released │──────▶ MANIFEST LOCKED (immutable)
             │    └────┬─────┘
             │         │ (manual: superseded by newer release)
             │         ▼
             │    ┌────────────┐
             └───▶│deprecated │
                  └────────────┘
                  (also reachable from completed)
```

**Transition Rules:**
- `ingesting → hydrating`: Automatic when all artifacts are registered
- `hydrating → completed`: Automatic when Traceability Hydrator finishes
- `completed → testing`: Manual (QA user action via Portal/API)
- `completed → deprecated`: Manual (skip testing, mark as obsolete)
- `testing → released`: Manual (authorized user approves)
- `released → deprecated`: Manual (newer version released)
- **LOCKED on `released`**: No field modifications allowed. Any attempt returns HTTP 409 Conflict with audit log entry.

---

## Layer 1: Execution Edge (URGP CLI)

### Component Design

The CLI is a single-binary tool (compiled via PyInstaller or Nuitka) that CI/CD pipelines invoke as their final step.

**Commands:**
```bash
# Primary command: push build data to URGP
urgp-cli push \
  --product "S32_IDE" \
  --release "3.6.8-RFP" \
  --build-type "nightly" \
  --build-id "260330" \
  --adapter "eclipse_p2" \
  --artifact "./target/s32-ide.zip" \
  --artifact "./target/s32-ide-docs.zip" \
  --commit-repo "bitbucket.org/nxp/s32k3_dev" \
  --commit-hash "abc123def456..." \
  --commit-repo "bitbucket.org/nxp/s32k3_drivers" \
  --commit-hash "789xyz..." \
  --api-key $URGP_API_KEY

# Verify an existing build manifest
urgp-cli verify --build-id "260330" --api-key $URGP_API_KEY

# Version info
urgp-cli --version
# Output: urgp-cli v1.2.0 (data-contract: v1)
```

**Data Flow:**
```
CI/CD Pipeline
    │
    ▼
urgp-cli push
    ├── 1. Load adapter (eclipse_p2 / generic)
    ├── 2. Adapter.extract_metadata(artifact_path)
    ├── 3. Compute SHA-256 for each artifact
    ├── 4. Construct Data Contract JSON payload
    ├── 5. POST to URGP API (HTTPS)
    │       ├── Success → exit 0
    │       ├── Retry (3x exponential backoff)
    │       └── All retries fail → write payload to ./urgp-fallback.json → exit 1
    └── 6. Report summary to stdout
```

**Adapter Interface (Python):**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AdapterResult:
    metadata: dict          # Technology-specific metadata (stored as JSONB)
    dependencies: list[str] # Detected dependencies
    errors: list[str]       # Non-fatal extraction warnings

class BaseAdapter(ABC):
    @abstractmethod
    def extract_metadata(self, artifact_path: str) -> AdapterResult:
        """Extract technology-specific metadata from build output."""
        ...

    @abstractmethod
    def validate_artifact(self, artifact_path: str) -> bool:
        """Validate artifact integrity (e.g., ZIP not corrupted)."""
        ...

# Phase 1 adapters:
class GenericAdapter(BaseAdapter):
    """Default adapter: file size, MIME type, basic metadata."""

class EclipseP2Adapter(BaseAdapter):
    """Parse P2 repository content.xml, extract feature/plugin IDs."""
```

### Data Contract Payload

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["product_id", "release", "build_type", "build_id", "commit_hashes", "artifacts", "timestamp", "cli_version"],
  "properties": {
    "product_id": {"type": "string"},
    "release": {"type": "string"},
    "build_type": {"type": "string", "enum": ["nightly", "weekly", "rc", "hotfix"]},
    "build_id": {"type": "string"},
    "cli_version": {"type": "string", "description": "CLI and data contract version for compatibility tracking"},
    "commit_hashes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["repository", "hash"],
        "properties": {
          "repository": {"type": "string", "description": "Full repository identifier (e.g., bitbucket.org/org/repo)"},
          "hash": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
          "branch": {"type": "string"}
        }
      }
    },
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type", "storage_uri", "sha256"],
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["eclipse_p2", "oci_image", "maven_jar", "npm_tarball", "binary", "python_wheel", "generic"]},
          "storage_uri": {"type": "string", "format": "uri"},
          "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
          "size_bytes": {"type": "integer"},
          "metadata": {"type": "object"}
        }
      }
    },
    "timestamp": {"type": "string", "format": "date-time"},
    "ci_metadata": {
      "type": "object",
      "description": "Optional CI/CD pipeline metadata",
      "properties": {
        "ci_system": {"type": "string"},
        "pipeline_url": {"type": "string", "format": "uri"},
        "triggered_by": {"type": "string"}
      }
    }
  }
}
```

---

## Layer 2: Event Gateway

### RabbitMQ Topology

```
                      ┌──────────────────────────┐
  URGP CLI ──HTTPS──▶ │  FastAPI Ingestion API   │
                      │  POST /api/v1/ingest     │
                      └──────────┬───────────────┘
                                 │ publish
                                 ▼
                      ┌──────────────────────────┐
                      │  Exchange:               │
                      │  urgp.build.events       │
                      │  (type: direct)          │
                      └──────────┬───────────────┘
                                 │
                    ┌────────────┼────────────────┐
                    │            │                │
                    ▼            ▼                ▼
           ┌──────────┐  ┌──────────┐    ┌──────────────┐
           │ Queue:    │  │ Queue:   │    │ Queue:       │
           │ build.    │  │ build.   │    │ build.events │
           │ process   │  │ notify   │    │ .dlq         │
           └────┬──────┘  └────┬─────┘    └──────────────┘
                │              │           (Dead Letter Queue)
                ▼              ▼
           Control Plane  Notification
           Consumer       Engine Consumer
```

**Processing pipeline:**
1. CLI sends HTTPS POST to `/api/v1/ingest` with Data Contract payload
2. Ingestion API validates JSON schema
3. If invalid → publish to DLQ with error details → return HTTP 422
4. If valid → check idempotency (build_id + product_id lookup in Redis)
5. If duplicate → return HTTP 200 (accepted, no reprocessing)
6. If new → publish to `urgp.build.events` exchange → return HTTP 202 (accepted)
7. Two consumers process the message:
   - **build.process queue** → Control Plane creates manifest + triggers hydration
   - **build.notify queue** → Notification Engine sends notifications

---

## Layer 3: Control Plane (Governance Engine)

### Component: Build Manifest Service

**API Endpoints:**

```
POST   /api/v1/products                          # Create product with Git/Jira config
GET    /api/v1/products                           # List products (RBAC-filtered in P2)
POST   /api/v1/products/:id/release-trains        # Create release train
GET    /api/v1/products/:id/release-trains        # List release trains

POST   /api/v1/ingest                             # Ingest build event (from CLI)

GET    /api/v1/builds                             # List build manifests (paginated)
GET    /api/v1/builds/:id                         # Retrieve manifest details
GET    /api/v1/builds/:id/traceability            # Retrieve traceability graph
GET    /api/v1/builds/:id/artifacts               # List artifacts
GET    /api/v1/builds/:id/sbom                    # Retrieve SBOM (P2)
PATCH  /api/v1/builds/:id/status                  # Transition lifecycle status
POST   /api/v1/builds/:id/verify                  # Verify artifact integrity

GET    /api/v1/builds/compare                     # Compare two builds (?start=X&end=Y)
GET    /api/v1/builds/search/by-commit/:hash      # Find builds containing commit
GET    /api/v1/builds/search/by-issue/:issue_id   # Find builds containing issue

GET    /api/v1/notifications/subscriptions        # List user's subscriptions
POST   /api/v1/notifications/subscriptions        # Create subscription
DELETE /api/v1/notifications/subscriptions/:id    # Delete subscription

GET    /health                                     # Health check
GET    /health/ready                               # Readiness check
GET    /docs                                       # Swagger UI (auto-generated)
```

**Status Transition API:**
```http
PATCH /api/v1/builds/260330/status
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "status": "released",
  "comment": "Approved by QA lead after regression testing"
}
```

**Response on locked manifest:**
```http
HTTP/1.1 409 Conflict
{
  "error": "immutability_violation",
  "message": "Build manifest 260330 is locked (status: released). No modifications allowed.",
  "audit_event_id": "evt_abc123"
}
```

### Component: Traceability Hydrator

**Architecture:**
```
                    ┌──────────────────────────────────────┐
                    │         Traceability Hydrator        │
                    │         (async worker process)       │
                    │                                      │
   RabbitMQ ──────▶ │  1. Receive build manifest ID       │
  (build.process)   │  2. Load product Git/Jira config     │
                    │  3. For each commit (concurrent):    │
                    │     ├── Git API: resolve commit      │
                    │     ├── Git API: find PRs             │
                    │     └── Regex: extract Jira IDs       │
                    │  4. Batch query Jira API for issues   │
                    │  5. Store graph in PostgreSQL         │
                    │  6. Update manifest status            │
                    └──────────────────────────────────────┘
                            │             │
                            ▼             ▼
                       ┌──────┐     ┌──────────┐
                       │Redis │     │PostgreSQL│
                       │Cache │     │ (graph)  │
                       └──────┘     └──────────┘
```

**Async Hydration Worker (Python):**
```python
import asyncio
import aiohttp
from typing import List

class TraceabilityHydrator:
    def __init__(self, git_provider: GitProvider, issue_tracker: IssueTracker, cache: Redis):
        self.git = git_provider
        self.issues = issue_tracker
        self.cache = cache

    async def hydrate(self, manifest: BuildManifest) -> TraceabilityGraph:
        # Update status to hydrating
        await manifest.set_status("hydrating")
        
        try:
            # Step 1: Resolve all commits concurrently
            commit_tasks = [
                self.resolve_commit(c.repository, c.hash)
                for c in manifest.commit_hashes
            ]
            commits = await asyncio.gather(*commit_tasks, return_exceptions=True)
            
            # Step 2: Find PRs for each commit concurrently
            pr_tasks = [
                self.git.find_pull_requests(c.repository, c.hash)
                for c in commits if not isinstance(c, Exception)
            ]
            pull_requests = await asyncio.gather(*pr_tasks, return_exceptions=True)
            
            # Step 3: Extract issue IDs from commit messages
            issue_ids = self.extract_issue_ids(commits, manifest.product.issue_regex)
            
            # Step 4: Batch query issue tracker (with cache)
            issues = await self.issues.batch_get(issue_ids)
            
            # Step 5: Build and store graph
            graph = TraceabilityGraph(
                manifest=manifest,
                commits=[c for c in commits if not isinstance(c, Exception)],
                pull_requests=flatten(pr for pr in pull_requests if not isinstance(pr, Exception)),
                issues=issues
            )
            await self.store_graph(graph)
            
            # Step 6: Update status
            has_failures = any(isinstance(c, Exception) for c in commits)
            await manifest.set_status("completed", traceability_incomplete=has_failures)
            
            return graph
            
        except Exception as e:
            await manifest.set_status("completed", traceability_incomplete=True)
            logger.error(f"Hydration failed for {manifest.build_id}: {e}")
            raise
```

**Git Provider Adapter Interface:**
```python
class GitProvider(ABC):
    @abstractmethod
    async def get_commit(self, repo: str, hash: str) -> Commit: ...
    
    @abstractmethod
    async def find_pull_requests(self, repo: str, commit_hash: str) -> list[PullRequest]: ...

class GitHubProvider(GitProvider):
    """GitHub REST API v3 implementation."""
    
    async def get_commit(self, repo: str, hash: str) -> Commit:
        # GET /repos/{owner}/{repo}/commits/{sha}
        # Respects rate limits via retry_after header
        ...

class GitLabProvider(GitProvider):
    """GitLab REST API v4 implementation."""
    ...

class BitbucketProvider(GitProvider):
    """Bitbucket Cloud REST API v2 implementation."""
    ...
```

**Issue Tracker Adapter Interface:**
```python
class IssueTracker(ABC):
    @abstractmethod
    async def get_issue(self, issue_id: str) -> Issue: ...
    
    @abstractmethod
    async def batch_get(self, issue_ids: list[str]) -> list[Issue]: ...

class JiraTracker(IssueTracker):
    """Jira REST API v3 implementation with JQL batch queries."""
    
    async def batch_get(self, issue_ids: list[str]) -> list[Issue]:
        # POST /rest/api/3/search
        # { "jql": "key in (PROJ-123, PROJ-456)", "fields": [...] }
        ...
```

**Caching Strategy (Redis):**
- **What is cached**: Git commit details, PR details, Jira issue details
- **TTL**: 5 minutes (issues change status; cache must be reasonably fresh)
- **Key format**: `cache:{provider}:{resource_type}:{id}` (e.g., `cache:github:commit:abc123`)
- **Invalidation**: TTL-based only (no explicit invalidation needed — build data is append-only)

### Component: Immutability Controller

```python
class ImmutabilityController:
    async def lock_manifest(self, build_id: str, user_id: str) -> None:
        manifest = await self.get_manifest(build_id)
        if manifest.status == "released":
            raise ImmutabilityViolation(f"Manifest {build_id} is already locked")
        
        # Generate SBOM (Phase 2)
        if self.sbom_enabled:
            sbom = self.generate_sbom(manifest)
            await self.store_sbom(build_id, sbom)
        
        # Compute signature
        signature = self.compute_signature(manifest)
        
        # Lock: database UPDATE with status check
        # UPDATE build_manifests SET status='released', signature=$sig
        # WHERE id=$id AND status IN ('completed','testing')
        affected = await self.db.lock_manifest(build_id, signature)
        if affected == 0:
            raise InvalidStateTransition(f"Cannot release manifest in status {manifest.status}")
        
        # Audit log
        await self.audit.log("manifest_locked", build_id, user_id)

    def compute_signature(self, manifest: BuildManifest) -> str:
        """HMAC-SHA256 over (build_id + artifact checksums sorted)."""
        content = manifest.build_id + "".join(sorted(a.sha256 for a in manifest.artifacts))
        return hmac.new(self.signing_key, content.encode(), hashlib.sha256).hexdigest()
```

### Component: Notification Engine

```python
class NotificationEngine:
    """Sends push notifications when build status changes."""
    
    async def on_build_completed(self, manifest: BuildManifest):
        subscriptions = await self.get_subscriptions(
            product_id=manifest.product_id,
            release_id=manifest.release_id
        )
        
        for sub in subscriptions:
            payload = self.render_notification(manifest, sub)
            
            if sub.channel == "email":
                await self.send_email(sub.user_email, payload)
            elif sub.channel == "webhook":
                await self.send_webhook(sub.webhook_url, payload)
    
    def render_notification(self, manifest, subscription) -> dict:
        return {
            "build_id": manifest.build_id,
            "product": manifest.product.name,
            "release": manifest.release.version,
            "build_type": manifest.build_type,
            "status": manifest.status,
            "changes_summary": {
                "commits": len(manifest.commits),
                "pull_requests": len(manifest.pull_requests),
                "issues": len(manifest.issues)
            },
            "portal_url": f"{self.base_url}/builds/{manifest.build_id}",
            "timestamp": manifest.created_at.isoformat()
        }
```

**Email Template Example:**
```
Subject: [URGP] S32 Design Studio — Nightly Build 260330 Ready

Build 260330 (nightly) is now available.

📊 Changes: 15 commits, 8 Pull Requests, 5 Jira Issues
🔗 View details: https://urgp.internal/builds/260330

Top Issues:
  • PROJ-1234: Fix GPIO driver initialization [Critical]
  • PROJ-1235: Update CAN bus timing parameters [Major]
  • PROJ-1236: Add SPI slave mode support [Normal]

—
Manage notifications: https://urgp.internal/settings/notifications
```

---

## Layer 4: AI Gateway (Phase 3)

> Per [ADR-007](03-architecture-decisions.md#adr-007-ai-integration-strategy), this layer is deferred to Phase 3. During Phases 1-2, AI tools access URGP via standard REST APIs.

**Phase 3 Design:**
- MCP Server implemented as a thin FastAPI service
- Delegates all business logic to existing Control Plane REST APIs
- Adds tenant-aware context filtering based on user JWT
- MCP Tools map 1:1 to REST API endpoints

```python
# Phase 3: MCP Tool → REST API mapping
MCP_TOOL_MAPPING = {
    "get_build_manifest": "GET /api/v1/builds/{build_id}",
    "query_failed_builds": "GET /api/v1/builds?status=completed&traceability_incomplete=true",
    "get_traceability_graph": "GET /api/v1/builds/{build_id}/traceability",
    "compare_builds": "GET /api/v1/builds/compare?start={start_id}&end={end_id}",
    "search_by_commit": "GET /api/v1/builds/search/by-commit/{hash}",
    "search_by_issue": "GET /api/v1/builds/search/by-issue/{issue_id}",
    "compute_dora_metrics": "GET /api/v1/metrics/dora?product_id={id}&period={period}",
}
```

---

## Layer 5: Self-Service Portal (React)

### Page Structure

```
/login                                        → Login page (OIDC redirect)
/products                                     → Products catalog with platform KPIs (home)
/products/:id/releases                        → Product releases list
/products/:id/releases/:releaseId/builds      → Release builds list (filterable by build type)
/products/:id/releases/:releaseId/builds/:buildId
                                              → Build detail (packages, what's new, traceability)
/products/:id/releases/:releaseId/builds/:buildId/packages/:packageId
                                              → Package detail (source & changes)
/products/:id/releases/:releaseId/builds/:buildId/packages/:packageId/cicd
                                              → Package CI/CD & testing
/builds/compare                               → Build comparison — Issues view
/builds/compare/prs                           → Build comparison — PRs & Packages view
/activity                                     → Cross-product activity feed & monitoring
/settings/notifications                       → Notification subscription management
/settings/profile                             → User profile
/admin/products (P2)                          → Product administration
/admin/tenants (P2)                           → Tenant administration
```

**Sidebar Navigation:**
```
┌──────────────────────────┐
│  COMMAND HORIZON         │
├──────────────────────────┤
│  🏢 Products      (home) │
│  📊 Activity             │
│  🔀 Comparisons          │
│  📈 Reports              │
│  ⚙️  Settings             │
└──────────────────────────┘
```

### Key UI Components

**Products Catalog** (see [00-products.html](../frontend/designs/00-products.html)):
- Platform-wide KPI metrics (total builds, success rate, active products, avg build time)
- Product cards showing release count, build count, last build status per product
- Search and filter capabilities

**Product Releases List** (see [01-product-releases.html](../frontend/designs/01-product-releases.html)):
- Release cards with version, release type, lifecycle status (Active/Maintenance/EOL)
- Summary stats per release: build count, success rate, package count

**Release Builds List** (see [02-release-builds.html](../frontend/designs/02-release-builds.html)):
```
┌────────────┬───────────┬──────────┬────────┬─────────┬──────────┐
│ Build ID   │ Type      │ Status   │Changes │ Date    │ Actions  │
├────────────┼───────────┼──────────┼────────┼─────────┼──────────┤
│ 260330     │ Nightly   │ 🟢 Released│ 15    │ 03/30   │ View     │
│ 260329     │ Nightly   │ 🟡 Testing │ 8     │ 03/29   │ View     │
│ 260328     │ Nightly   │ ⚪ Completed│ 22    │ 03/28   │ View     │
│ 260325     │ Weekly    │ 🟢 Released│ 45    │ 03/25   │ View     │
└────────────┴───────────┴──────────┴────────┴─────────┴──────────┘
  [Filter: Build Type ▼] [Filter: Status ▼] [Date range: __|__]  [Search: ____]
  [Compare builds: select 2 rows → Compare button]
```

**Build Detail — Packages** (see [03-build-detail-packages.html](../frontend/designs/03-build-detail-packages.html)):
- Build header with status badge, build type, timestamps
- Package (artifact) list with name, type, version, size, download actions
- `docker pull` command for OCI images

**Build Detail — What's New & Traceability** (see [08-build-detail-whatsnew-traceability.html](../frontend/designs/08-build-detail-whatsnew-traceability.html)):
- What's New: Issues with PRs grouped by repository
- Traceability Graph: Interactive React Flow visualization
- Summary: commit/PR/issue counts across repositories

**Package Detail** (see [04-package-detail.html](../frontend/designs/04-package-detail.html)):
- Source repository and branch info
- Recent changes (commits, PRs) affecting the package

**Package CI/CD & Testing** (see [06-package-cicd-testing.html](../frontend/designs/06-package-cicd-testing.html)):
- CI/CD pipeline status and history
- Test results summary and detail

**Build Comparison** (see [05-build-comparison-issues.html](../frontend/designs/05-build-comparison-issues.html), [07-build-comparison-prs-packages.html](../frontend/designs/07-build-comparison-prs-packages.html)):
- Two-column diff layout with Issues, PRs, and Packages tabs
- Export: CSV, JSON

**Activity Feed** (see [09-activity.html](../frontend/designs/09-activity.html)):
- Live build metrics and active build status across all products
- System alerts and notifications
- Build activity heatmap

**Traceability Graph (React Flow):**
```
 ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
 │ Build    │────▶│ Commit   │────▶│ PR #456  │────▶│PROJ-1234 │
 │ 260330   │     │ abc123   │     │ Fix GPIO │     │ Critical │
 └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │               │
       │          ┌──────────┐     ┌──────────┐
       │          │ Commit   │────▶│ PR #789  │────▶│PROJ-1235│
       │          │ def456   │     │ CAN bus  │     │ Major   │
       │          └──────────┘     └──────────┘     └─────────┘
       │
  ┌──────────┐
  │ Package  │
  │ s32k3.zip│
  │ SHA:abc..│
  └──────────┘
```

### Frontend Data Flow

```
React Components
    │
    ▼ (useQuery hooks)
TanStack Query (caching + background refetch)
    │
    ▼ (Axios with JWT interceptor)
URGP REST API
    │
    ▼ (server response)
TanStack Query cache (5 min for immutable data, 30s for mutable)
    │
    ▼ (re-render)
React Components
```

---

## Cross-Cutting Concerns

### Authentication Flow

```
┌────────────┐     ┌──────────────┐     ┌──────────────┐
│  Browser   │────▶│  OIDC IdP    │────▶│  URGP API    │
│  (Portal)  │     │  (Corporate) │     │  (FastAPI)   │
│            │◀────│  JWT issued  │     │              │
│            │─────────────────────────▶│  Validate JWT│
└────────────┘                          └──────────────┘

┌────────────┐                          ┌──────────────┐
│  CI/CD     │─────API Key header──────▶│  URGP API    │
│  (CLI)     │                          │  Validate Key│
└────────────┘                          └──────────────┘
```

### Rate Limiting

- **Algorithm**: Sliding window counter (Redis-backed)
- **Defaults**: 100 req/min (read), 20 req/min (write)
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Override**: Per API-key configuration in database

### Error Response Format

All API errors follow a consistent format:
```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": { "field": "specific detail" },
  "request_id": "req_abc123",
  "timestamp": "2026-03-30T10:30:00Z"
}
```

### Configuration (Pydantic Settings)

```python
class URGPSettings(BaseSettings):
    # Database
    database_url: PostgresDsn
    database_pool_size: int = 10
    
    # RabbitMQ
    rabbitmq_url: AmqpDsn
    
    # Redis
    redis_url: RedisDsn
    
    # External integrations
    default_git_provider: str = "github"
    default_issue_tracker: str = "jira"
    
    # Security
    jwt_secret_key: SecretStr
    api_key_hash_rounds: int = 12
    signing_key: SecretStr  # For HMAC-SHA256 manifest signatures
    
    # Notifications
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_from: str = "urgp@company.com"
    
    # Rate limiting
    rate_limit_read: int = 100   # per minute
    rate_limit_write: int = 20   # per minute
    
    # Operational
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
    
    class Config:
        env_prefix = "URGP_"
        env_file = ".env"
```

---

## Project Structure

```text
urgp/
+-- frontend/
|   +-- portal/                         # React + Vite self-service portal
|   |   +-- package.json
|   |   +-- vite.config.ts
|   |   +-- src/
|   +-- designs/                        # UI mockups and visual references
|
+-- backend/
|   +-- pyproject.toml                  # Backend dependencies and tooling
|   +-- alembic.ini                     # Database migration config
|   +-- .env.example                    # Backend configuration template
|   +-- src/
|   |   +-- urgp/                       # FastAPI API, worker, domain services
|   |       +-- main.py                 # FastAPI app entry point
|   |       +-- config.py               # Pydantic settings
|   |       +-- api/                    # FastAPI routers
|   |       +-- db/                     # SQLAlchemy session and seed data
|   |       +-- integrations/           # Git and issue tracker adapters
|   |       +-- messaging/              # RabbitMQ connection and topology
|   |       +-- middleware/             # Auth, rate limiting, request IDs
|   |       +-- models/                 # SQLAlchemy models
|   |       +-- schemas/                # API/data contract schemas
|   |       +-- services/               # Business logic
|   |       +-- worker/                 # Background consumers
|   +-- migrations/                     # Alembic database migrations
|   +-- config/                         # Environment config templates
|   +-- tests/                          # Backend unit/integration tests
|
+-- cli/
|   +-- pyproject.toml                  # CLI dependencies and tooling
|   +-- urgp-cli.spec                   # PyInstaller spec
|   +-- scripts/
|   |   +-- build_cli.py                # CLI binary build helper
|   +-- src/
|   |   +-- urgp_cli/                   # Typer CLI package
|   |       +-- main.py                 # CLI entry point
|   |       +-- adapters/               # Artifact adapters
|   |       +-- commands/               # push/verify commands
|   |       +-- contracts/              # Data contract models
|   |       +-- transport/              # API client
|   +-- tests/                          # CLI tests
|
+-- deploy/
|   +-- docker-compose.yml              # Full local dev environment
|   +-- Dockerfile.backend              # API + worker image
|   +-- Dockerfile.portal               # Portal image
|   +-- nginx.portal.conf               # Portal reverse proxy config
|
+-- docs/                               # Architecture and usage docs
+-- Makefile                            # Root workflow shortcuts
+-- README.md
```