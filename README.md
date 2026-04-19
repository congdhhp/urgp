# Universal Release Governance Platform (URGP)

**A data-driven, multi-tenant platform for centralized release governance, traceability, and immutability across the software delivery lifecycle.**

URGP replaces fragmented, file-driven build systems (Jenkins scripts + SharePoint + Email) with a unified control plane that provides:

- 🔍 **Full Traceability** — Build → Commits → Pull Requests → Jira Issues, all linked automatically
- 🔒 **Release Immutability** — Cryptographic checksums and locked manifests prevent artifact tampering
- 📊 **Self-Service Portal** — Web dashboard replaces email archaeology for build investigation
- 🔔 **Push Notifications** — Email and webhook alerts when builds complete
- 🔌 **Pluggable Architecture** — Supports any CI/CD tool, any artifact type, any Git/Issue tracker
- 🏢 **Multi-Tenant** — Isolated workspaces for unlimited teams sharing one platform

## Documentation

Read in order for full context:

| # | Document | Description |
|---|----------|-------------|
| 1 | [Problem Assessment](docs/01-problem-assessment.md) | Analysis of current system pain points and architectural anti-patterns |
| 2 | [Solution Architecture](docs/02-solution-architecture.md) | High-level platform vision and 5-layer architecture blueprint |
| 3 | [Architecture Decisions](docs/03-architecture-decisions.md) | 7 ADRs: PostgreSQL, RabbitMQ, FastAPI, React, JWT, Docker/K8s, AI strategy |
| 4 | [Requirements](docs/04-requirements.md) | 24 requirements with acceptance criteria, phased P1/P2/P3 |
| 5 | [Technical Design](docs/05-technical-design.md) | Database schema, component interfaces, API design, project structure |
| 6 | [Migration Strategy](docs/06-migration-strategy.md) | 4-phase rollout plan from legacy system to URGP |
| 7 | [Implementation Plan](docs/07-implementation-plan.md) | 61 tasks + 40 tests across 3 phases with timeline and cost estimates |
| 8 | [Team & Work Plan](docs/08-team-workplan.md) | Team structure, role assignments, work breakdown with task ownership |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+ / FastAPI / Uvicorn |
| Database | PostgreSQL 16 (JSONB, recursive CTEs) |
| Message Broker | RabbitMQ |
| Cache | Redis |
| Frontend | React + TypeScript + Vite + Ant Design |
| Auth | JWT + API Keys |
| Dev Environment | Docker Compose |
| Prod Environment | Kubernetes + Helm |

## Delivery Phases

| Phase | Scope | Timeline |
|-------|-------|----------|
| **P1 — MVP** | CLI, Event Gateway, Control Plane, Portal, Notifications | 8-12 weeks |
| **P2 — Platform** | Multi-Tenancy, RBAC, SBOM, Adapter Plugins, Audit, HA | 6-8 weeks |
| **P3 — Advanced** | MCP/AI Gateway, DORA Metrics, SDK | 8-12 weeks |

## Quick Start (Development)

```bash
# Prerequisites: Docker, Docker Compose
git clone <repo-url>
cd urgp
cp .env.example .env
docker compose up -d
```

> **Note:** Source code implementation has not started yet. See [Implementation Plan](docs/07-implementation-plan.md) for the development roadmap.

## License

See [LICENSE](LICENSE) for details.