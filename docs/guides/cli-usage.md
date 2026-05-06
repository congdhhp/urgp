# URGP CLI Usage Guide

## Overview

The URGP CLI (`urgp-cli`) is the primary interface for pushing build events from CI/CD pipelines into the URGP platform. It collects build artifacts, commit information, and metadata, then sends them to the Event Gateway for processing.

## Installation

### Via pip (recommended for development)

```bash
pip install urgp
# or with Poetry
poetry add urgp
```

### Via PyInstaller binary (recommended for CI)

Pre-built binaries are available in the project releases. Download the appropriate binary for your platform and add it to your CI agent's PATH.

## Commands

### `push` — Send a build event to URGP

The `push` command is the primary operation. It collects build artifacts and metadata, then submits them to the URGP Event Gateway.

```bash
urgp-cli push \
  --product-id S32_IDE \
  --release 3.6.8-RFP \
  --build-type nightly \
  --build-id 260330 \
  --api-url https://urgp.example.com \
  --api-key $URGP_API_KEY \
  --artifact "path/to/artifact.zip" \
  --commit-repo "github.com/org/repo" \
  --commit-hash "abc123def456"
```

**Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--product-id` | ✅ | Product identifier (e.g., `S32_IDE`) |
| `--release` | ✅ | Release train version (e.g., `3.6.8-RFP`) |
| `--build-type` | ✅ | Build type: `nightly`, `weekly`, `release`, `manual` |
| `--build-id` | ✅ | Unique build identifier |
| `--api-url` | ✅ | URGP API base URL |
| `--api-key` | ✅ | API authentication key |
| `--artifact` | ✅ | Path to artifact file (repeatable) |
| `--commit-repo` | ✅ | Git repository URL |
| `--commit-hash` | ✅ | Git commit SHA (repeatable) |
| `--commit-branch` | ❌ | Branch name (default: auto-detect) |
| `--adapter` | ❌ | Artifact adapter: `generic`, `eclipse_p2` |
| `--timeout` | ❌ | Request timeout in seconds (default: 30) |
| `--fallback-file` | ❌ | Save payload to file on failure |

### `verify` — Verify build integrity

```bash
urgp-cli verify \
  --build-id 260330 \
  --product-id S32_IDE \
  --api-url https://urgp.example.com \
  --api-key $URGP_API_KEY
```

**Response:**
```json
{
  "build_id": "260330",
  "integrity_status": "valid",
  "artifacts": [
    {
      "name": "s32-ide.zip",
      "integrity_status": "valid"
    }
  ]
}
```

## Jenkins Integration

### Freestyle Project

Add a **Post-build action → Execute shell**:

```bash
#!/bin/bash
urgp-cli push \
  --product-id "${PRODUCT_ID}" \
  --release "${RELEASE_VERSION}" \
  --build-type nightly \
  --build-id "${BUILD_NUMBER}" \
  --api-url "${URGP_API_URL}" \
  --api-key "${URGP_API_KEY}" \
  --artifact "target/*.zip" \
  --commit-repo "${GIT_URL}" \
  --commit-hash "${GIT_COMMIT}" \
  --timeout 30 || true  # Non-blocking
```

### Jenkins Pipeline (Declarative)

```groovy
pipeline {
    agent any
    
    environment {
        URGP_API_URL = credentials('urgp-api-url')
        URGP_API_KEY = credentials('urgp-api-key')
    }
    
    stages {
        stage('Build') {
            steps {
                sh 'make build'
            }
        }
        
        stage('Report to URGP') {
            steps {
                sh """
                    urgp-cli push \
                      --product-id S32_IDE \
                      --release ${RELEASE_VERSION} \
                      --build-type nightly \
                      --build-id ${BUILD_NUMBER} \
                      --api-url ${URGP_API_URL} \
                      --api-key ${URGP_API_KEY} \
                      --artifact 'target/*.zip' \
                      --commit-repo ${GIT_URL} \
                      --commit-hash ${GIT_COMMIT} \
                      --timeout 30 || true
                """
            }
        }
    }
}
```

### Shadow Mode (Non-blocking)

During the migration phase, use the `|| true` suffix to ensure build pipelines are not affected:

```bash
urgp-cli push ... --timeout 30 || true
```

This ensures:
- ✅ Build pipeline always succeeds
- ✅ URGP collects data in parallel
- ✅ Failures are logged but don't block the pipeline

## GitLab CI Integration

```yaml
report_to_urgp:
  stage: post-build
  script:
    - urgp-cli push
        --product-id ${CI_PROJECT_NAME}
        --release ${CI_COMMIT_TAG:-untagged}
        --build-type ${CI_PIPELINE_SOURCE}
        --build-id ${CI_PIPELINE_ID}
        --api-url ${URGP_API_URL}
        --api-key ${URGP_API_KEY}
        --artifact "dist/*.zip"
        --commit-repo ${CI_REPOSITORY_URL}
        --commit-hash ${CI_COMMIT_SHA}
        --timeout 30 || true
  allow_failure: true
```

## Artifact Adapter: Eclipse P2

For Eclipse-based products with P2 update sites, use the `eclipse_p2` adapter:

```bash
urgp-cli push \
  --adapter eclipse_p2 \
  --artifact "target/repository/" \
  ...
```

This adapter:
- Scans the P2 repository directory for IU (installable unit) metadata
- Extracts version, qualifier, and category information
- Generates SHA-256 checksums per feature/plugin

## Environment Variables

All CLI parameters can also be set via environment variables:

| Variable | CLI Parameter |
|----------|--------------|
| `URGP_API_URL` | `--api-url` |
| `URGP_API_KEY` | `--api-key` |
| `URGP_PRODUCT_ID` | `--product-id` |
| `URGP_RELEASE` | `--release` |
| `URGP_BUILD_TYPE` | `--build-type` |

## Troubleshooting

### Connection timeout

```
Error: Connection to URGP API timed out after 30s
```

**Solution:** Increase timeout or check network connectivity:
```bash
urgp-cli push --timeout 60 ...
```

### API key rejected

```
Error: 401 Unauthorized — Invalid API key
```

**Solution:** Verify your API key is correct and has write permissions. Check with your URGP administrator.

### Fallback file

If the URGP API is unreachable, use `--fallback-file` to save the payload locally for later resubmission:

```bash
urgp-cli push --fallback-file /tmp/urgp-fallback.json ... || true
# Later, resubmit:
urgp-cli push --from-file /tmp/urgp-fallback.json --api-url ...
```
