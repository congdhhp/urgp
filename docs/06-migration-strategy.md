# Migration & Coexistence Strategy
## From Legacy Build System to URGP

**Document Type:** Migration Strategy & Rollout Plan  
**Domain:** Release Governance, Change Management  
**Target Audience:** Technical Leaders, DevOps Engineers, Product Owners  
**Status:** PROPOSED

---

## 1. Executive Summary

Migrating from the current Jenkins + SharePoint + Email system to URGP requires a careful, phased approach to avoid disrupting the existing Nightly/Weekly release cadence. This document defines a 4-phase migration strategy that enables coexistence of both systems, progressive confidence building, and safe cutover.

**Core Principle**: At no point during migration should the R&D team lose access to their current delivery mechanism. URGP must **prove itself** before the old system is decommissioned.

---

## 2. Migration Phases Overview

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Phase 0    │    │   Phase 1    │    │   Phase 2    │    │   Phase 3    │
│  Shadow     │───▶│  Dual-Run    │───▶│  Primary     │───▶│  Cutover     │
│  Mode       │    │  Mode        │    │  Switchover  │    │  & Decom     │
│  (4 weeks)  │    │  (4 weeks)   │    │  (4 weeks)   │    │  (2 weeks)   │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

**Total Migration Duration**: ~14 weeks (parallel with URGP development)

---

## 3. Phase 0: Shadow Mode (Weeks 1-4)

### Objective
URGP silently collects build data alongside the existing system. No user-facing changes. Build confidence in data accuracy.

### What Changes
- **Jenkins pipelines**: Add `urgp-cli push` as the **last step** of existing Nightly/Weekly pipelines. This step is non-blocking — invoked with error suppression (`urgp-cli push ... --timeout 30 || true`) so that CLI failures are logged but never fail the build.
- **Email/SharePoint**: Continue unchanged. Users see no difference.
- **URGP Portal**: Available internally for the Platform Team only (not announced to R&D).

### What Gets Validated
| Validation Item | Method |
|----------------|--------|
| CLI successfully collects metadata from all package types | Review URGP build manifests vs Jenkins build logs |
| SHA-256 checksums match between SharePoint files and URGP records | Automated comparison script |
| Traceability Graph (commits → PRs → Jira) matches current Email's "What's New" table | Manual spot-check of 5 builds |
| No performance impact on Jenkins pipelines | Compare pipeline duration before/after CLI addition |

### Exit Criteria for Phase 0
- [ ] URGP has successfully captured ≥ 20 consecutive Nightly builds
- [ ] URGP has successfully captured ≥ 3 consecutive Weekly builds
- [ ] SHA-256 checksum validation passes for 100% of artifacts
- [ ] Traceability data matches Email "What's New" content for ≥ 90% of Jira issues
- [ ] Jenkins pipeline duration increase < 60 seconds

### Rollback
Remove the `urgp-cli push` step from Jenkins pipelines. Zero impact on existing workflow.

---

## 4. Phase 1: Dual-Run Mode (Weeks 5-8)

### Objective
URGP becomes visible to a pilot group of early adopters. Both systems deliver the same information. Users can choose which to use. Collect user feedback.

### What Changes
- **URGP Portal**: Announced to S32 pilot team (3-5 volunteers from Dev + QA).
- **Email announcement**: Adds a single line at the bottom: *"[BETA] View this build interactively: {URGP Portal Link}"*
- **Notifications**: URGP sends parallel notification (email/Slack) when build is processed. Users receive both old Email and new URGP notification.
- **SharePoint**: Continues unchanged. URGP Portal download links point to the same artifacts.

### What Gets Validated
| Validation Item | Method |
|----------------|--------|
| Portal usability and completeness | User feedback sessions (weekly 15-min standup with pilot group) |
| Build comparison feature works correctly | Pilot users compare "Email What's New" vs "Portal What's New" |
| Notification delivery reliability | Verify 100% notification delivery over 4 weeks |
| Dynamic historical queries work | Pilot users perform cross-build queries they couldn't do before |
| Portal performance meets SLA | Monitor page load times < 1 second |

### Exit Criteria for Phase 1
- [ ] Pilot users confirm Portal data matches Email content
- [ ] Pilot users report positive experience with at least 3/5 rating
- [ ] All Portal features (What's New, Download, Compare, Traceability) are functional
- [ ] Zero data discrepancies reported over 4 weeks
- [ ] URGP notification delivery rate ≥ 99%

### Rollback
Remove the Portal link from Email. Disable URGP notifications. Pilot users return to Email-only workflow.

---

## 5. Phase 2: Primary Switchover (Weeks 9-12)

### Objective
URGP becomes the **primary** interface. The old Email becomes a summary with redirect to Portal. SharePoint becomes read-only.

### What Changes
- **Email announcement**: Simplified to a brief summary with link to Portal: *"Nightly Build 260415 is ready. 12 changes detected. [View Full Details on URGP Portal →]"*
- **SharePoint**: Set to **read-only** (no more manual uploads). All downloads redirect through URGP Portal (checksum-verified).
- **URGP Portal**: Announced to ALL R&D teams. Becomes the official source of truth.
- **Manual rebuilds**: Developers can no longer drop files onto SharePoint. Rebuilt packages must go through `urgp-cli push` to be tracked.

### What Gets Validated
| Validation Item | Method |
|----------------|--------|
| All R&D team members can access Portal | Track login statistics |
| No one is blocked by the reduced Email | Monitor support requests |
| SharePoint read-only enforcement works | Test that write access is revoked |
| Build immutability is maintained | Verify no artifact modifications after build completion |

### Exit Criteria for Phase 2
- [ ] ≥ 80% of R&D team has logged into Portal at least once
- [ ] Support request volume related to migration < 5 total
- [ ] Zero incidents caused by read-only SharePoint
- [ ] No manual file uploads to SharePoint for 4 consecutive weeks
- [ ] All teams confirm they can find build information via Portal

### Rollback
Re-enable full Email content. Restore SharePoint write access. URGP remains available but not mandatory.

---

## 6. Phase 3: Cutover & Decommission (Weeks 13-14)

### Objective
Fully decommission the old Email announcement system and SharePoint delivery. URGP is the sole system.

### What Changes
- **Email**: Completely replaced by URGP notification system (email + optional Slack/Teams webhook).
- **SharePoint**: Archived (read-only historical access for 6 months, then decommissioned).
- **Jenkins pipeline**: Remove legacy post-build scripts (Nexus metadata upload, Email generation, SharePoint upload). Only `urgp-cli push` remains.
- **Nexus metadata**: Historical metadata kept for reference. No new metadata uploaded to Nexus.

### Decommission Checklist
- [ ] Legacy Email generation scripts archived
- [ ] Legacy SharePoint upload scripts archived
- [ ] Legacy Nexus metadata upload scripts archived
- [ ] Legacy Delta computation scripts archived
- [ ] SharePoint folder set to archive mode (read-only, no new content)
- [ ] Documentation updated to reference URGP exclusively
- [ ] Jenkins pipeline cleanup completed

---

## 7. Data Migration Strategy

### 7.1. What Gets Migrated

| Data Source | Target in URGP | Priority | Method |
|------------|---------------|----------|--------|
| Jenkins Build History (last 6 months) | Build Manifests | HIGH | One-time migration script |
| SharePoint artifacts (checksums) | Artifact registry (metadata only) | HIGH | Scan + compute SHA-256 |
| Nexus metadata files | Traceability data (partial) | MEDIUM | Parse JSON/text → import |
| Email archives (What's New tables) | Not migrated | LOW | Historical reference only |

### 7.2. Migration Script Approach

```python
# Pseudocode for one-time data migration
for build in jenkins.get_builds(last_6_months):
    manifest = BuildManifest(
        build_id=build.id,
        product_id="s32_design_studio",
        release_train=build.get_param("RELEASE_TRAIN"),
        timestamp=build.timestamp,
        status="completed"  # All historical builds are already completed
    )
    
    # Import artifact metadata (not binary files)
    for artifact in sharepoint.list_files(build.id):
        manifest.add_artifact(
            name=artifact.name,
            type=detect_type(artifact),
            storage_uri=f"sharepoint://{artifact.path}",
            sha256=compute_sha256(artifact)
        )
    
    # Import partial traceability from Nexus metadata
    nexus_meta = nexus.get_metadata(build.id)
    if nexus_meta:
        manifest.set_commit_hashes(nexus_meta.commits)
    
    urgp_api.create_manifest(manifest)
```

### 7.3. What Does NOT Get Migrated
- **Binary artifacts**: Files remain on SharePoint/Nexus. URGP stores `storage_uri` references to their current locations.
- **Jenkins job configurations**: Not relevant to URGP.
- **Email content**: Not structured enough to parse reliably. Serves as historical reference only.

---

## 8. Rollback Plan (Emergency)

If URGP experiences a critical failure at any phase:

1. **Immediate**: Re-enable full legacy Email announcement.
2. **Within 1 hour**: Restore SharePoint write access.
3. **Within 4 hours**: Remove `urgp-cli` step from Jenkins pipelines if CLI is causing build failures.
4. **Communication**: Send "System Notice" email to R&D explaining temporary revert.
5. **Root cause**: Investigate URGP failure, fix, and re-enter the current migration phase.

**Key Guarantee**: The legacy system's scripts are **archived, not deleted**, for the entire migration duration. They can be restored within minutes.

---

## 9. Communication Plan

| When | Audience | Channel | Message |
|------|----------|---------|---------|
| Phase 0 start | Platform Team only | Team meeting | "We're adding silent data collection to Jenkins" |
| Phase 1 start | Pilot group (5 people) | Direct invitation | "Try the new Build Portal (beta)" |
| Phase 1 mid | Pilot group | Feedback session | "What's working? What's missing?" |
| Phase 2 start | All R&D | All-hands + Email | "Introducing URGP Portal - your new build dashboard" |
| Phase 2 mid | All R&D | FAQ document | "Common questions about the new system" |
| Phase 3 start | All R&D | Email | "Old Email system retiring on [date]" |
| Phase 3 complete | All R&D | Celebration | "Migration complete! 🎉" |

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| URGP Portal downtime during Phase 2 | Medium | High | Email fallback remains active; HA deployment |
| Users resist change ("I want my Email back") | High | Medium | Gradual rollout; URGP notifications replicate Email content initially |
| Data discrepancy between URGP and legacy | Low | High | Phase 0 validates data accuracy for 4 weeks before any user exposure |
| CLI adds latency to Jenkins pipelines | Low | Medium | CLI runs as last non-blocking step; timeout after 30s |
| SharePoint read-only breaks some team workflows | Medium | Medium | Phase 2 grace period; announce 2 weeks in advance |
