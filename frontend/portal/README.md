# URGP Portal

**React-based self-service portal for release governance, traceability visualization, and notification management.**

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool and dev server |
| Ant Design | Component library |
| React Router | Client-side routing |
| ReactFlow | Traceability graph visualization |
| Recharts | Charts and reports |
| Zustand | State management |

## Quick Start

```bash
cd frontend/portal
npm ci
npm run dev    # http://localhost:5173
```

## Pages

| Page | Path | Description |
|------|------|-------------|
| Products | `/` | Product catalog with search and creation |
| Product Releases | `/products/:id` | Release timeline for a product |
| Release Builds | `/releases/:id` | Builds for a specific release |
| Build Detail | `/builds/:id` | Full build info, artifacts, traceability |
| Package Detail | `/packages/:id` | Artifact metadata and checksums |
| Activity | `/activity` | Real-time build activity feed |
| Comparison | `/compare` | Side-by-side build comparison with diff export |
| Reports | `/reports` | Platform metrics and charts |
| Search | `/search` | Full-text search across builds and products |
| Settings | `/settings` | Notification subscriptions and preferences |

## Development

```bash
# Type check
npx tsc --noEmit

# Build production bundle
npm run build

# Run tests
npm run test
```

## API Client

The portal communicates with the backend via `src/lib/api.ts`, which provides typed wrappers for all URGP API endpoints. In development, Vite proxies `/api/` requests to `http://localhost:8000`.

## Project Structure

```text
frontend/portal/
├── src/
│   ├── components/      # Reusable UI components
│   ├── contexts/        # React context providers (theme)
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # API client, formatting, storage utilities
│   ├── pages/           # Route page components
│   ├── App.tsx          # Root component with routing
│   └── main.tsx         # Entry point
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```
