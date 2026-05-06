# Product Setup Guide

## Overview

This guide covers how to register and configure products in URGP, including Git provider and issue tracker integration for full traceability hydration.

## Creating a Product

### Via API

```bash
curl -X POST https://urgp.example.com/api/v1/products \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "S32_IDE",
    "name": "S32 Design Studio",
    "description": "Eclipse-based IDE for S32 microcontrollers"
  }'
```

**Response:**
```json
{
  "external_id": "S32_IDE",
  "name": "S32 Design Studio"
}
```

### Via Portal

1. Navigate to **Products** page
2. Click **"+ New Product"**
3. Fill in External ID, Name, and optional Description
4. Click **Create**

### Auto-creation via Ingestion

Products are automatically created when the CLI pushes a build with a new `product_id`. The product name is derived from the ID (e.g., `S32_IDE` → "S32 IDE").

## Managing Release Trains

Release trains organize builds under versioned release cycles.

### Creating a Release Train

```bash
curl -X POST https://urgp.example.com/api/v1/products/S32_IDE/release-trains \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "3.6.8-RFP",
    "release_type": "RFP",
    "status": "active"
  }'
```

### Release Types

| Type | Description |
|------|-------------|
| `RFP` | Release for Production |
| `RC` | Release Candidate |
| `GA` | General Availability |
| `BETA` | Beta release |

Release types are automatically inferred from the version string suffix when created via ingestion.

## Git Provider Configuration

Configure a Git provider to enable full traceability hydration (commit messages, authors, pull requests).

### Supported Providers

| Provider | Config Type | Description |
|----------|------------|-------------|
| GitHub | `github` | GitHub.com or GitHub Enterprise |
| Bitbucket | `bitbucket` | Bitbucket Cloud or Server |
| Generic | `generic` | Fallback — no API enrichment |

### GitHub Configuration

```bash
curl -X PUT https://urgp.example.com/api/v1/admin/products/S32_IDE/git-config \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "github",
    "base_url": "https://api.github.com",
    "token": "ghp_xxxxxxxxxxxxxxxxxxxx",
    "org": "my-organization"
  }'
```

### Bitbucket Configuration

```bash
curl -X PUT https://urgp.example.com/api/v1/admin/products/S32_IDE/git-config \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "bitbucket",
    "base_url": "https://bitbucket.org",
    "username": "bot-user",
    "app_password": "xxxxxxxxxxxxxxxxxxxx",
    "workspace": "my-workspace"
  }'
```

### What Hydration Enriches

When a Git provider is configured, hydration resolves:

| Data | Source |
|------|--------|
| Commit message | Git API |
| Author name/email | Git API |
| Pull request title | Git API |
| Pull request URL | Git API |
| PR review status | Git API |

Without a Git provider, only the commit hash and repository are stored.

## Issue Tracker Configuration

Configure an issue tracker to link builds to project management issues.

### Supported Trackers

| Tracker | Config Type | Description |
|---------|------------|-------------|
| Jira | `jira` | Jira Cloud or Server |

### Jira Configuration

```bash
curl -X PUT https://urgp.example.com/api/v1/admin/products/S32_IDE/issue-config \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tracker": "jira",
    "base_url": "https://jira.example.com",
    "username": "urgp-bot@example.com",
    "api_token": "xxxxxxxxxxxxxxxxxxxx",
    "project_keys": ["S32", "IDE"]
  }'
```

### Issue Detection

URGP uses a configurable regex pattern to detect issue references in commit messages. The default pattern is:

```
\b[A-Z][A-Z0-9]+-\d+\b
```

This matches patterns like `S32-1234`, `IDE-567`, `PROJ-89`.

## Credential Encryption

All provider credentials (tokens, passwords, API keys) are encrypted at rest using AES-256-GCM. The encryption key is derived from the `URGP_SIGNING_KEY` environment variable.

### How it works

1. Admin submits Git/Jira config via API
2. URGP encrypts sensitive fields before storing in PostgreSQL
3. During hydration, the worker decrypts credentials on-the-fly
4. Decrypted credentials never touch disk or logs

### Rotating Credentials

To rotate a provider credential:

1. Update the config via the admin API (same endpoint, new token)
2. URGP re-encrypts with the current signing key
3. No service restart required

## Environment Variables Reference

Core product-related settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `URGP_DATABASE_URL` | (required) | PostgreSQL connection string |
| `URGP_RABBITMQ_URL` | (required) | RabbitMQ AMQP connection string |
| `URGP_REDIS_URL` | (required) | Redis connection string |
| `URGP_SIGNING_KEY` | (required) | 32+ char key for HMAC signatures and credential encryption |
| `URGP_API_KEY` | (required) | Comma-separated list of valid API keys |
| `URGP_DEFAULT_GIT_PROVIDER` | `generic` | Default Git provider when product has no config |
| `URGP_DEFAULT_ISSUE_TRACKER` | `jira` | Default issue tracker |
| `URGP_DEFAULT_ISSUE_REGEX` | `\b[A-Z][A-Z0-9]+-\d+\b` | Regex for issue detection |

## Verification

After configuring a product, verify the setup by:

1. **Push a test build:**
   ```bash
   urgp-cli push --product-id S32_IDE --build-id test-001 ...
   ```

2. **Check traceability:**
   ```bash
   curl https://urgp.example.com/api/v1/builds/test-001/traceability \
     -H "X-API-Key: $URGP_API_KEY"
   ```

3. **Verify hydration completed:**
   - `traceability_incomplete: false` — all commits enriched
   - `traceability_incomplete: true` — provider may need reconfiguration
