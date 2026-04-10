# Enterprise Platform Blueprint
## Universal Release Governance Platform (URGP)
*Multi-Tenant, Technology-Agnostic Control Plane*

**Document Type:** Enterprise Platform Architecture Blueprint  
**Domain:** Platform Engineering, Multi-Tenant Architecture, Software Supply Chain (SLSA)  
**Target Audience:** Enterprise Architects, CTOs, VPs of Engineering, Technical Leaders  
**Status:** APPROVED  
**Last Updated:** 2026-04-10

---

## 1. Platform Vision & Design Principles

The system is designed not as a point solution for "S32 Design Studio," but as the **Universal Release Governance Platform (URGP)** — a shared release governance control plane serving the entire R&D organization. The platform is built upon three core design principles:

1. **Agnostic Core:** The platform is free from vendor lock-in to any CI/CD tool (Jenkins, GitLab CI), programming language (C, Python, Node.js), or packaging format. All technology specifics are abstracted into `Logical Entities` at the data layer.

2. **Multi-Tenancy & Isolation:** Supports an unlimited number of development teams and products. Each product operates within an isolated workspace with its own release cadence, external integrations (Git/Jira servers), and access control (RBAC), while sharing the same physical governance infrastructure.

3. **Federated Execution & Standardized Contracts:** Differences in build toolchains and data collection across package types are handled by Agent/Adapter components at the execution edge. The central Control Plane rejects all technology-specific complexity — it accepts only a single, standardized Data Contract (JSON schema).

---

## 2. Domain-Driven Entity Abstraction Model

Rather than designing the data model around S32-specific concerns, the entity structure follows a **multi-domain hierarchy** that supports any product type:

1. **Workspace / Organization:** The top-level organizational boundary (e.g., *Automotive R&D Division*, *Cloud Services*).
2. **Product:** Represents an independent software project (e.g., *S32 Design Studio*, *AutoCore OS*).
   - **Attributes:** Contains API connection configuration for the Product's Git Provider and Issue Tracker.
3. **Release Train:** A delivery channel within a Product (e.g., *Nightly*, *Weekly*, *LTS*, *Hotfix*).
4. **Build Manifest:** The core entity representing a specific build version (e.g., Build `260330`). Anchors the Traceability Graph and test metrics.
5. **Universal Artifacts:** Regardless of physical format, the Control Plane's database stores only five fields per artifact:
   - `Name` — Human-readable artifact identifier
   - `Type` — Enumeration: `eclipse_p2`, `oci_image`, `binary`, `npm_tarball`, `maven_jar`, `python_wheel`, `generic`
   - `Storage_URI` — Location reference (e.g., `s3://...`, `nexus://...`, `sharepoint://...`)
   - `SHA-256 Checksum` — Cryptographic hash ensuring immutable identity
   - `Metadata (JSONB)` — Extensible key-value store for type-specific configuration without schema modifications

---

## 3. Decoupled 5-Layer Architecture

### Layer 1: Pluggable Execution Edge & Universal Agent

This layer addresses the question: *"How do we support fundamentally different package types?"*

- **Bring-Your-Own-Pipeline (BYOP):** Product teams are free to use Jenkins, GitLab CI, GitHub Actions, or any other CI/CD orchestrator. URGP does not interfere with existing build processes.
- **URGP CLI Agent (Adapter Pattern):** The Platform Team provides a CLI tool embedded as the final step of every pipeline.
- **Mechanism:** Based on the product type, DevOps engineers pass the appropriate adapter parameter to the CLI:
  - *Team S32 (P2 Repo)*: `urgp-cli push --product "S32_IDE" --adapter "eclipse_p2" --artifact "./s32.zip"`
  - *Team Cloud (Docker)*: `urgp-cli push --product "CloudBackend" --adapter "oci_image" --artifact "registry/app:v1"`
  - **Adapter Responsibility:** Automatically scans technology-specific logs, parses dependencies, computes SHA-256 checksums, and translates the result into a single standardized JSON payload.

### Layer 2: Universal Event Gateway

- **Message Broker:** Ingests `Build_Finished` events from all teams at scale.
- **Data Contract Validator:** The system's gatekeeper. Validates the incoming JSON payload against the Data Contract schema. Regardless of which CI system sends the event, if required fields are missing (`Product_ID`, `Commit_Hashes`, `Checksums`), the Gateway automatically rejects the message at the edge to protect Control Plane data integrity.

### Layer 3: Enterprise Governance Control Plane

The core engine manages all products through shared, zero-custom-code-per-product engines:

- **Tenant Router & RBAC:** Routes events to the correct namespace. Ensures that developers from `Team Cloud` cannot view, approve, or mutate builds belonging to `Team S32`.
- **Universal Traceability Hydrator:** Retrieves the product's Git/Jira API credentials from database configuration, then automatically queries external APIs to construct the multi-dimensional Traceability Graph.
- **Global Immutability Controller:** Manages release lifecycle locking and SBOM generation. For this engine, verifying the hash of a `.zip` file or a Docker layer follows the exact same logic.

### Layer 4: Tenant-Aware AI Gateway

The combination of multi-tenancy and Model Context Protocol (MCP) enables a security breakthrough:

- **Context Isolation:** When an AI agent (e.g., Claude, Cursor) calls the MCP Server (e.g., `get_failed_logs`), the server analyzes the *User Token*. If the user belongs to Team S32, the AI is granted read-only access exclusively to the S32 sub-graph (code, logs, Jira issues). This eliminates cross-tenant data leakage risks.
- **Cross-Product Analytics:** Reserved for C-level executives and platform administrators. The AI can query across product boundaries: *"Which product across the entire organization had the worst DORA metrics last week?"*

### Layer 5: Federated Self-Service Portal

- **Single Pane of Glass:** A unified Web Portal for the entire organization.
- **Dynamic UI Rendering:** Upon login, users select their Workspace/Product (similar to switching projects in Jira). Based on the product's `artifact_type`, the UI adapts dynamically:
  - For `eclipse_p2` artifacts: displays a **Download .zip** button with verified checksum.
  - For `oci_image` artifacts: displays a **Copy `docker pull` command** box.

---

## 4. Zero-Touch Onboarding Scenario

How does the system accommodate a **new product** built with entirely different technology — without any platform code changes?

**Scenario:** *The company creates Team `AutoGateway`, using Rust source code, packaging as `.tar.gz`, and running CI on GitHub Actions.*

**Workflow:**

1. **Setup (5 minutes):** Admin creates Product `AutoGateway` on the URGP Web Portal and generates an API Key.
2. **Edge Integration:** Team AutoGateway adds the `urgp-cli` tool as the final step in their `.github/workflows/build.yml` pipeline, pointing to the `.tar.gz` output.
3. **Control Plane Processing (Automatic):** The Event Gateway receives the event → the system recognizes a new Product ID → hydrates the Traceability Graph using the team's GitHub/Jira configuration → stores the graph in the database → generates SBOM protection.
4. **Immediate Result:** Team AutoGateway logs into the Portal, selects their project, and **inherits the complete platform capabilities** — AI dashboards, "What's New" traceability matrix, and immutability governance. **Not a single line of URGP backend code was modified.**

---

## 5. Enterprise Strategic Value

1. **Platform as a Product (PaaP):** The organization does not need to build one system for Team S32 and then spend additional R&D effort building a separate toolset for Team AutoGateway. URGP serves as the centralized governance hub with **converging maintenance costs**.

2. **Standardized Developer Experience:** Every product, regardless of its technology stack, adheres to the same rigorous SLSA/Immutability standards. A Tester transferring from the S32 project to the Cloud project spends zero time learning a new release process or searching for changelogs.

3. **Enterprise AI Knowledge Lake:** By normalizing lifecycle data from all systems into a single format, URGP functions as a **Data Warehouse**, transforming AI technology (via MCP standards) into a powerful lever for DORA Metrics analysis at the management level.

---

## Appendix: Document Roadmap

This blueprint is the high-level vision. For detailed specifications, refer to:

| Document | Purpose |
|----------|---------|
| [Architecture Decision Records](03-architecture-decisions.md) | Committed technology choices (PostgreSQL, RabbitMQ, FastAPI, React) |
| [Requirements Specification](04-requirements.md) | 24 requirements with acceptance criteria, phased delivery |
| [Technical Design](05-technical-design.md) | Database schema, component interfaces, API design, project structure |
| [Migration Strategy](06-migration-strategy.md) | Phased rollout plan from legacy to URGP |
| [Implementation Plan](07-implementation-plan.md) | 58 tasks + 40 tests across 3 delivery phases |