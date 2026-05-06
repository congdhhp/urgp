# Notification Configuration Guide

## Overview

URGP's notification engine delivers real-time alerts when builds reach key lifecycle milestones. Users can subscribe to email or webhook notifications, filtered by product and release train.

## Notification Events

URGP supports two notification event types:

| Event | Trigger | Description |
|-------|---------|-------------|
| `build_completed` | Build hydration finishes | Fired automatically when a build's traceability processing completes |
| `build_released` | Build status → `released` | Fired when an operator transitions a build to released status |

## Creating Subscriptions

### Email Subscription

Subscribe to receive email notifications for all builds of a product:

```bash
curl -X POST https://urgp.example.com/api/v1/notifications/subscriptions \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "X-User-Id: qa-lead@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "S32_IDE",
    "channel": "email"
  }'
```

> **Note:** For email subscriptions, the `X-User-Id` header must be a valid email address. This is where notifications will be delivered.

### Email Subscription (Filtered by Release)

Subscribe only to builds for a specific release train:

```bash
curl -X POST https://urgp.example.com/api/v1/notifications/subscriptions \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "X-User-Id: qa-lead@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "S32_IDE",
    "release": "3.6.8-RFP",
    "channel": "email"
  }'
```

### Webhook Subscription

Subscribe to receive webhook (HTTP POST) notifications:

```bash
curl -X POST https://urgp.example.com/api/v1/notifications/subscriptions \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "X-User-Id: ci-bot" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "S32_IDE",
    "channel": "webhook",
    "webhook_url": "https://hooks.slack.com/services/T00/B00/xxx"
  }'
```

### Via Portal

1. Navigate to **Notifications** → **Subscriptions**
2. Click **"+ New Subscription"**
3. Select product, optionally filter by release
4. Choose channel: **Email** or **Webhook**
5. If webhook, enter the destination URL
6. Click **Subscribe**

## Notification Payload

### Email Content

Email notifications include:

```
Subject: [URGP] S32 Design Studio - Completed build 260330

S32 Design Studio build 260330 is now completed.

Release train: 3.6.8-RFP
Build type: nightly
Changes: 15 commits, 8 pull requests, 5 issues
Traceability incomplete: no
Portal: https://urgp.example.com/portal/?build=260330&product=S32_IDE
```

### Webhook Payload

Webhook notifications deliver a structured JSON payload via HTTP POST:

```json
{
  "schema_version": "v1",
  "event_type": "build_completed",
  "triggered_at": "2026-05-06T12:00:00Z",
  "build": {
    "id": "260330",
    "status": "completed",
    "type": "nightly",
    "product_id": "S32_IDE",
    "product_name": "S32 Design Studio",
    "release_train": "3.6.8-RFP"
  },
  "changes_summary": {
    "commits": 15,
    "pull_requests": 8,
    "issues": 5
  },
  "traceability": {
    "incomplete": false
  },
  "links": {
    "portal": "https://urgp.example.com/portal/?build=260330&product=S32_IDE"
  }
}
```

## Managing Subscriptions

### Listing Active Subscriptions

```bash
curl https://urgp.example.com/api/v1/notifications/subscriptions \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "X-User-Id: qa-lead@example.com"
```

**Response:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "qa-lead@example.com",
      "product_id": "S32_IDE",
      "product_name": "S32 Design Studio",
      "release": "3.6.8-RFP",
      "channel": "email",
      "webhook_url": null,
      "active": true,
      "created_at": "2026-05-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

### Deleting a Subscription

```bash
curl -X DELETE https://urgp.example.com/api/v1/notifications/subscriptions/{subscription_id} \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "X-User-Id: qa-lead@example.com"
```

Subscriptions are soft-deleted (deactivated). Re-creating the same subscription reactivates it.

## Delivery History

### Viewing Notification History

```bash
curl "https://urgp.example.com/api/v1/notifications/history?limit=20" \
  -H "X-API-Key: $URGP_API_KEY" \
  -H "X-User-Id: qa-lead@example.com"
```

### Filtering History

| Parameter | Description |
|-----------|-------------|
| `build_id` | Filter by specific build |
| `product_id` | Filter by product |
| `channel` | Filter by channel: `email`, `webhook` |
| `status` | Filter by delivery status: `pending`, `sent`, `failed` |
| `limit` | Max results (default: 50, max: 100) |
| `offset` | Pagination offset |

### Delivery Statuses

| Status | Description |
|--------|-------------|
| `pending` | Notification created, delivery in progress |
| `sent` | Successfully delivered to recipient |
| `failed` | All delivery attempts exhausted |

## Retry Behavior

Failed deliveries are retried with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1st | Immediate |
| 2nd | 1 second |
| 3rd | 2 seconds |
| 4th | 4 seconds |

After all retry attempts are exhausted (default: 3 retries), the notification is marked as `failed`.

Configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| `URGP_NOTIFICATION_MAX_RETRIES` | `3` | Maximum retry attempts |
| `URGP_NOTIFICATION_RETRY_BACKOFF_SECONDS` | `1.0` | Base backoff delay |

## Development: Testing with MailHog

In the development environment, URGP uses [MailHog](https://github.com/mailhog/MailHog) as a local SMTP server. All email notifications are captured by MailHog instead of being sent to real recipients.

### Accessing MailHog

After starting Docker Compose:

```bash
docker compose up -d
```

Open MailHog in your browser:

```
http://localhost:8025
```

### SMTP Configuration (Development)

The Docker Compose environment configures SMTP to use MailHog automatically:

```env
URGP_SMTP_HOST=mailhog
URGP_SMTP_PORT=1025
URGP_SMTP_FROM=urgp@localhost
```

### Verifying Notifications

1. Create a subscription (email channel)
2. Ingest a build via CLI or API
3. Open MailHog at `http://localhost:8025`
4. Verify the notification email appears with correct build details

## Architecture Notes

### Event Flow

```
Build Completed/Released
        │
        ▼
  [Event Publisher]  ──→  RabbitMQ (build.notify queue)
                                │
                                ▼
                     [Notification Worker]
                          │        │
                    ┌─────┘        └─────┐
                    ▼                    ▼
              [Email Transport]    [Webhook Transport]
                    │                    │
                    ▼                    ▼
               SMTP Server          HTTP POST
              (MailHog/SMTP)       (Webhook URL)
```

### Queue Architecture

- **`build.notify`** — Main notification delivery queue
- **`build.notify.dlq`** — Dead letter queue for permanently failed messages
- Separate channel from hydration queue to prevent slow processing from starving notifications

### Idempotency

Duplicate notifications for the same `(manifest_id, subscription_id, event_type)` tuple are automatically deduplicated. If a previously failed notification is retriggered, URGP resets and reattempts delivery.
