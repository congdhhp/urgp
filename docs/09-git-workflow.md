# Git Workflow & Worktree Guide
## Universal Release Governance Platform (URGP) — Phase 1

**Document Type:** Developer Workflow Guide  
**Target Audience:** All Developers  
**Status:** ACTIVE  
**Last Updated:** 2026-04-19

---

## 1. Branch Strategy

### Branch Layout

```
master                              ← Production-ready releases
  │
  └── devel                         ← Integration branch (all features merge here)
        │
        ├── feature/p1-1-infrastructure    ← Week 1-2: TL-BE, BE-1, BE-2, DevOps
        ├── feature/p1-2-cli               ← Week 2-4: BE-2
        ├── feature/p1-3-event-gateway     ← Week 3-5: BE-1
        ├── feature/p1-4-control-plane     ← Week 4-8: TL-BE, BE-1, BE-2
        ├── feature/p1-5-notifications     ← Week 6-7: BE-2
        └── feature/p1-6-portal            ← Week 4-10: FE-Lead
```

### Rules

| Rule | Description |
|------|-------------|
| **Base branch** | All `feature/*` branches are created from `devel` |
| **Merge target** | All `feature/*` branches merge back into `devel` via **Pull Request** |
| **PR reviews** | Backend PRs → reviewed by TL-BE. Frontend PRs → reviewed by FE-Lead |
| **CI must pass** | No merge without green CI pipeline (lint + type-check + tests) |
| **No direct commits to `devel`** | All changes go through feature branches + PRs |
| **Release** | `devel` → `master` when Phase milestone is stable |

---

## 2. Worktree Layout

Git worktrees allow each team member to work on their feature branch in a **separate directory** while sharing the same `.git` repository. No need to switch branches — each worktree is its own checkout.

### Directory Structure

```
C:\Users\congd\Desktop\works\
├── urgp/                           ← Main repo (devel branch)
│   ├── docs/                       ← Documentation (shared)
│   ├── frontend/designs/           ← UI mockups (shared)
│   └── .git/                       ← Single shared git database
│
└── urgp-worktrees/                 ← All worktrees live here
    ├── p1-1-infrastructure/        ← feature/p1-1-infrastructure
    ├── p1-2-cli/                   ← feature/p1-2-cli
    ├── p1-3-event-gateway/         ← feature/p1-3-event-gateway
    ├── p1-4-control-plane/         ← feature/p1-4-control-plane
    ├── p1-5-notifications/         ← feature/p1-5-notifications
    └── p1-6-portal/                ← feature/p1-6-portal
```

### Worktree → Branch → Owner Mapping

| Worktree Directory | Branch | Owner(s) | Work Stream |
|--------------------|--------|----------|-------------|
| `urgp/` | `devel` | PM, TL-BE | Integration, docs, reviews |
| `p1-1-infrastructure/` | `feature/p1-1-infrastructure` | TL-BE, BE-1, BE-2, DevOps | Docker, DB, RabbitMQ, Config, CI |
| `p1-2-cli/` | `feature/p1-2-cli` | BE-2, DevOps | CLI framework, adapters, checksums |
| `p1-3-event-gateway/` | `feature/p1-3-event-gateway` | BE-1 | Ingestion API, validation, DLQ, rate limiting |
| `p1-4-control-plane/` | `feature/p1-4-control-plane` | TL-BE, BE-1, BE-2 | Manifest, Hydrator, APIs, Lifecycle |
| `p1-5-notifications/` | `feature/p1-5-notifications` | BE-2 | Email + webhook notifications |
| `p1-6-portal/` | `feature/p1-6-portal` | FE-Lead | React Portal — all 10 pages |

---

## 3. How to Use Worktrees

### For Team Members (First Time Setup)

If you clone the repo fresh and want to use worktrees:

```bash
# 1. Clone the repo
git clone https://github.com/congdhhp/urgp.git
cd urgp

# 2. Fetch all remote branches
git fetch --all

# 3. Create your worktree (example for BE-1 working on Event Gateway)
mkdir ../urgp-worktrees
git worktree add ../urgp-worktrees/p1-3-event-gateway feature/p1-3-event-gateway

# 4. Work in your worktree
cd ../urgp-worktrees/p1-3-event-gateway
# You are now on feature/p1-3-event-gateway — ready to code!
```

### Daily Workflow

```bash
# 1. Go to your worktree
cd C:\Users\congd\Desktop\works\urgp-worktrees\p1-3-event-gateway

# 2. Pull latest changes
git pull origin feature/p1-3-event-gateway

# 3. Also sync with devel to stay up-to-date
git fetch origin devel
git rebase origin/devel    # or: git merge origin/devel

# 4. Do your work...
#    code, test, etc.

# 5. Commit & push
git add .
git commit -m "feat(gateway): implement ingestion API endpoint"
git push origin feature/p1-3-event-gateway

# 6. When ready → Create Pull Request on GitHub: feature/p1-3-event-gateway → devel
```

### Syncing with `devel`

When infrastructure changes are merged into `devel`, all feature branches should sync:

```bash
# From your worktree directory
git fetch origin devel
git rebase origin/devel

# If there are conflicts:
# 1. Resolve conflicts in your editor
# 2. git add <resolved-files>
# 3. git rebase --continue
```

### Useful Commands

```bash
# List all worktrees
git worktree list

# Remove a worktree (when done with that feature)
git worktree remove ../urgp-worktrees/p1-1-infrastructure

# Prune stale worktree references
git worktree prune
```

---

## 4. Merge Order & Dependencies

P1 features have dependencies and should be merged in this order:

```
Step 1: feature/p1-1-infrastructure → devel     (Week 2 — foundation for everything)
        ※ All other branches rebase on updated devel

Step 2: feature/p1-2-cli → devel                (Week 4 — CLI sends data to Gateway)
        feature/p1-3-event-gateway → devel       (Week 5 — Gateway receives CLI data)
        ※ These can merge in any order, but both needed before Control Plane

Step 3: feature/p1-4-control-plane → devel       (Week 8 — depends on Gateway)
        feature/p1-6-portal → devel              (Week 10 — depends on Control Plane APIs)

Step 4: feature/p1-5-notifications → devel       (Week 7 — depends on RabbitMQ from Gateway)

Step 5: E2E validation on devel                  (Week 10-12 — all features integrated)
```

### Dependency Graph

```
p1-1-infrastructure ──┬──→ p1-2-cli ──────────────────────────┐
                      │                                        │
                      ├──→ p1-3-event-gateway ──→ p1-4-control-plane ──→ p1-6-portal
                      │                      │                             │
                      │                      └──→ p1-5-notifications       │
                      │                                                    │
                      └────────────────────────────────────────────────────┘
                                                                    devel (E2E)
```

---

## 5. Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

Examples:
feat(cli): implement SHA-256 checksum computation
feat(gateway): add ingestion API endpoint with schema validation
feat(hydrator): implement async Git provider resolution
feat(portal): add Build History page with Ant Design table
fix(gateway): handle duplicate build_id gracefully
test(cli): add adapter unit tests for EclipseP2
docs(api): update OpenAPI spec for build comparison endpoint
chore(docker): add Redis health check to docker-compose
refactor(manifest): extract lifecycle state machine into service
```

### Types

| Type | Use When |
|------|----------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `test` | Adding or updating tests |
| `docs` | Documentation changes |
| `chore` | Build, CI, dependency updates |
| `refactor` | Code restructuring (no behavior change) |
| `perf` | Performance improvement |

### Scopes

| Scope | Component |
|-------|-----------|
| `cli` | URGP CLI (cli/src/urgp_cli/) |
| `gateway` | Event Gateway (ingestion, validation) |
| `manifest` | Build Manifest Service |
| `hydrator` | Traceability Hydrator |
| `immutability` | Immutability Controller |
| `notifications` | Notification Engine |
| `portal` | React Portal (frontend/portal/) |
| `docker` | Docker Compose, deploy Dockerfiles |
| `db` | Database schema, migrations |
| `api` | API endpoints, OpenAPI |
| `config` | Configuration management |
| `auth` | Authentication, API keys |

---

## 6. Quick Reference

### Where Do I Work?

| I am... | My worktree | My branch |
|---------|-------------|-----------|
| **TL-BE** (Week 1-2) | `p1-1-infrastructure/` | `feature/p1-1-infrastructure` |
| **TL-BE** (Week 4-8) | `p1-4-control-plane/` | `feature/p1-4-control-plane` |
| **BE-1** (Week 1-2) | `p1-1-infrastructure/` | `feature/p1-1-infrastructure` |
| **BE-1** (Week 3-5) | `p1-3-event-gateway/` | `feature/p1-3-event-gateway` |
| **BE-1** (Week 5-8) | `p1-4-control-plane/` | `feature/p1-4-control-plane` |
| **BE-2** (Week 1-2) | `p1-1-infrastructure/` | `feature/p1-1-infrastructure` |
| **BE-2** (Week 2-4) | `p1-2-cli/` | `feature/p1-2-cli` |
| **BE-2** (Week 4-7) | `p1-4-control-plane/` | `feature/p1-4-control-plane` |
| **BE-2** (Week 6-7) | `p1-5-notifications/` | `feature/p1-5-notifications` |
| **FE-Lead** (Week 4-10) | `p1-6-portal/` | `feature/p1-6-portal` |
| **DevOps** (Week 1-2) | `p1-1-infrastructure/` | `feature/p1-1-infrastructure` |

> **Tip:** When working on multiple streams in the same week, you can simply `cd` between worktree directories. No `git checkout` needed — that's the whole point of worktrees!

### Key Paths

| Path | Purpose |
|------|---------|
| `C:\Users\congd\Desktop\works\urgp\` | Main repo — `devel` branch, docs, reviews |
| `C:\Users\congd\Desktop\works\urgp-worktrees\` | All worktrees (6 directories) |
