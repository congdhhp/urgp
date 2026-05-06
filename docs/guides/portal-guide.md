# URGP Portal User Guide

## Overview

The URGP Portal is a self-service web interface for investigating build traceability, managing products, and monitoring the platform. It provides real-time visibility into the complete lifecycle of every build event.

## Accessing the Portal

Navigate to your URGP instance in a web browser:

```
https://urgp.example.com/portal/
```

### Authentication

The portal uses API key authentication. On first visit, you'll be prompted to enter:

| Field | Description |
|-------|-------------|
| **API Key** | Your URGP API key (provided by your administrator) |
| **User ID** | Your email address (used for notification subscriptions) |

Credentials are stored in browser `localStorage` for convenience. Click the user icon to update or clear credentials.

## Dashboard (Activity Feed)

The landing page displays the **Activity Dashboard** with:

- **Platform Totals**: Products, releases, total builds, released builds, incomplete builds
- **Recent Builds**: The latest build events across all products
- **Products Catalog**: Quick navigation to all registered products

### Key Metrics

| Metric | Description |
|--------|-------------|
| Products | Total registered product lines |
| Releases | Total release trains across all products |
| Builds | Total build manifests ingested |
| Released | Builds that have reached `released` status |
| Incomplete | Builds with incomplete traceability data |

## Products Page

Navigate to **Products** to see all registered product lines.

### Creating a Product

1. Click **"+ New Product"**
2. Fill in:
   - **External ID**: Unique identifier (e.g., `S32_IDE`)
   - **Name**: Human-readable name (e.g., "S32 Design Studio")
   - **Description**: Optional product description
3. Click **Create**

### Managing Releases

From a product page:

1. Click **"+ New Release"**
2. Enter the release version (e.g., `3.6.8-RFP`)
3. Set status to `active`
4. Click **Create**

## Build Detail Page

The build detail page is the primary investigation tool. Access it by clicking any build in the dashboard or build list.

### Build Information

The header shows:
- **Build ID** and **Product**
- **Status badge**: `ingesting` → `hydrating` → `completed` → `testing` → `released`
- **Build type**: nightly, weekly, release, manual
- **Traceability status**: Complete ✅ or Incomplete ⚠️
- **Timestamps**: Created, last updated

### Artifacts Tab

Lists all artifacts associated with the build:

| Column | Description |
|--------|-------------|
| Name | Artifact filename |
| Type | `generic`, `eclipse_p2` |
| SHA-256 | Integrity checksum |
| Size | File size in bytes |
| Storage URI | Link to artifact location |

### Traceability Tab

Displays the complete traceability graph:

- **Commits**: All git commits linked to this build
- **Pull Requests**: PRs discovered during hydration
- **Issues**: Jira/issue tracker references

Each commit shows:
- Repository and commit hash
- Branch name
- Author and message (if hydrated)
- Linked PRs and issues

### Integrity Verification

Click **"Verify Integrity"** to validate:
- Manifest signature (HMAC-SHA256)
- Artifact checksums
- Traceability completeness

Results show per-artifact integrity status: `valid` ✅ or `invalid` ❌

### Lifecycle Transitions

Build managers can advance builds through the lifecycle:

```
completed → testing → released
```

Click the **status dropdown** to transition. Released builds are **immutable** — they cannot be modified further.

## Build Comparison

Compare two builds to see what changed:

1. Navigate to **Builds** → **Compare**
2. Select **Start Build** and **End Build**
3. View the diff:
   - New commits in End Build
   - New PRs and issues
   - Artifact changes

## Search

### By Commit Hash

Search for builds containing a specific commit:

1. Go to **Search** → **By Commit**
2. Enter the full or partial commit SHA
3. Results show all builds containing that commit

### By Issue ID

Search for builds linked to a specific Jira issue:

1. Go to **Search** → **By Issue**
2. Enter the issue key (e.g., `PROJ-1234`)
3. Results show all builds with commits referencing that issue

## Notification Management

### Creating Subscriptions

1. Navigate to **Notifications** → **Subscriptions**
2. Click **"+ New Subscription"**
3. Configure:
   - **Product**: Select the product to monitor
   - **Release** (optional): Filter to a specific release train
   - **Channel**: `email` or `webhook`
   - **Webhook URL** (if webhook): The endpoint to receive notifications
4. Click **Subscribe**

### Managing Subscriptions

- View all active subscriptions in the **Subscriptions** tab
- Click the trash icon to deactivate a subscription
- Deactivated subscriptions can be reactivated by creating the same subscription again

### Notification History

View delivery history in the **History** tab:

| Column | Description |
|--------|-------------|
| Event | `build_completed` or `build_released` |
| Build | Build ID that triggered the notification |
| Channel | `email` or `webhook` |
| Status | `pending`, `sent`, or `failed` |
| Attempts | Number of delivery attempts |
| Sent At | Timestamp of successful delivery |

## Dark Mode

Toggle dark mode using the 🌙/☀️ icon in the top navigation bar. The preference is saved in `localStorage`.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus search bar |
| `Esc` | Close modal/dialog |

## Troubleshooting

### "Unauthorized" error

Your API key may be invalid or expired. Click the user icon and re-enter your credentials.

### Build shows "Traceability Incomplete"

This means the hydration process could not fully resolve all commit metadata. Common causes:
- Git provider credentials not configured for the product
- External API rate limits exceeded during hydration
- Commits belong to a repository not accessible by the configured provider

Contact your administrator to verify the product's Git/Jira configuration.

### Empty build list

If no builds appear:
1. Verify your API key has read permissions
2. Check that builds have been ingested (ask your CI/CD team)
3. Try clearing filters (product, release, status)
