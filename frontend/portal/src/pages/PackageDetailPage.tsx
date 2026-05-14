import { useMemo, useState } from "react";
import { Alert, Button, Descriptions, Progress, Space, Steps, Table, Tabs, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  GitBranch,
  GitCommit,
  GitPullRequest,
  PackageCheck,
  Route,
  ShieldCheck,
  TestTube2
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { artifactChecksum, artifactMetadata, formatBytes, formatDate, shortHash, titleize } from "../lib/format";
import { useArtifacts, useBuild, useTraceability } from "../hooks/usePlatformQueries";
import type { CommitTraceability, Issue, PullRequest, TraceabilityRepository } from "../types";

export function PackageDetailPage() {
  const { productId = "", buildId = "", artifactId = "" } = useParams();
  const product = decodeURIComponent(productId);
  const build = decodeURIComponent(buildId);
  const artifactRef = decodeURIComponent(artifactId);
  const buildQuery = useBuild(build, product);
  const artifactsQuery = useArtifacts(build, product);
  const traceabilityQuery = useTraceability(build, product);

  const detail = buildQuery.data;
  const artifact = artifactsQuery.data?.artifacts.find((item) => item.id === artifactRef || item.name === artifactRef);
  const metadata = artifact ? artifactMetadata(artifact) : {};
  const repositories = traceabilityQuery.data?.repositories ?? [];
  const ciMetadata = detail?.ci_metadata ?? {};
  const testPassRate = inferPassRate(ciMetadata);

  const allIssues = useMemo(
    () => uniqueItems(repositories.flatMap((r) => r.commits.flatMap((c) => c.issues)), (i) => `${i.tracker_type}:${i.external_id}`),
    [repositories]
  );
  const allPRs = useMemo(
    () => uniqueItems(repositories.flatMap((r) => r.commits.flatMap((c) => c.pull_requests)), (pr) => pr.external_id),
    [repositories]
  );
  const totalCommits = repositories.reduce((sum, r) => sum + r.commit_count, 0);

  if (artifactsQuery.isError || buildQuery.isError) {
    return <RetryEmptyState onRetry={() => void Promise.all([artifactsQuery.refetch(), buildQuery.refetch()])} />;
  }

  if (!artifact && !artifactsQuery.isLoading) {
    return <EmptyState title="Package not found." description="The artifact may have been removed or the URL is stale." />;
  }

  return (
    <>
      <PageHeader
        title={artifact?.name ?? "Package"}
        subtitle={detail ? `${detail.product_name} / build ${detail.build_id}` : "Package readiness and provenance"}
        breadcrumbs={[
          { label: "Products", to: "/products" },
          { label: product, to: `/products/${encodeURIComponent(product)}` },
          { label: build, to: `/builds/${encodeURIComponent(product)}/${encodeURIComponent(build)}` },
          { label: artifact?.name ?? "Package" }
        ]}
      />

      {artifact ? (
        <>
          {/* Package Header Section (design-aligned) */}
          <div className="package-header-section">
            <div className="package-header-section__top">
              <div className="package-header-section__left">
                <div className="package-header-section__icon">PKG</div>
                <div>
                  <Typography.Title level={2} style={{ margin: 0 }}>{artifact.name}</Typography.Title>
                  <div className="package-header-section__meta">
                    <span className="package-type-badge">{titleize(artifact.type)}</span>
                    <span className="mono" style={{ fontSize: "0.82rem" }}>
                      {String(metadata.version ?? shortHash(artifactChecksum(artifact), 12))}
                    </span>
                    {artifact.size_bytes ? (
                      <>
                        <span style={{ color: "var(--text-faint)" }}>·</span>
                        <span className="mono" style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{formatBytes(artifact.size_bytes)}</span>
                      </>
                    ) : null}
                    <span style={{ color: "var(--text-faint)" }}>·</span>
                    <Link to={`/builds/${encodeURIComponent(product)}/${encodeURIComponent(build)}`} style={{ fontSize: "0.82rem", color: "var(--primary)" }}>
                      Build {build}
                    </Link>
                  </div>
                  {/* SHA-256 Strip */}
                  <div className="sha-strip">
                    <span className="sha-strip__label">SHA-256</span>
                    <Typography.Text copyable={{ text: artifactChecksum(artifact) }}>
                      <span className="sha-strip__value">{artifactChecksum(artifact) || "N/A"}</span>
                    </Typography.Text>
                  </div>
                </div>
              </div>
              <div className="package-header-section__actions">
                {artifact.type === "oci_image" ? (
                  <Typography.Text code copyable>docker pull {artifact.storage_uri}</Typography.Text>
                ) : (
                  <>
                    <Button type="primary" icon={<Download size={16} />} href={artifact.storage_uri} target="_blank">
                      Download Package
                    </Button>
                    <Button icon={<ExternalLink size={16} />} href={artifact.storage_uri} target="_blank">
                      View in Nexus
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* 4-Card Stats Grid */}
          <div className="stats-card-grid">
            <div className="stats-glass-card">
              <div className="stats-glass-card__header">
                <span className="stats-glass-card__icon stats-glass-card__icon--blue"><GitBranch size={18} /></span>
                <span className="stats-glass-card__tag">Git Metrics</span>
              </div>
              <div className="stats-glass-card__label">Repositories</div>
              <div style={{ display: "flex", alignItems: "baseline" }}>
                <span className="stats-glass-card__value">{repositories.length}</span>
                <span className="stats-glass-card__sub">{totalCommits} commits total</span>
              </div>
            </div>
            <div className="stats-glass-card">
              <div className="stats-glass-card__header">
                <span className="stats-glass-card__icon stats-glass-card__icon--green"><GitPullRequest size={18} /></span>
                <span className="stats-glass-card__tag">Code Review</span>
              </div>
              <div className="stats-glass-card__label">Pull Requests</div>
              <div style={{ display: "flex", alignItems: "baseline" }}>
                <span className="stats-glass-card__value">{allPRs.length}</span>
                <span className="stats-glass-card__sub">All merged</span>
              </div>
            </div>
            <div className="stats-glass-card">
              <div className="stats-glass-card__header">
                <span className="stats-glass-card__icon stats-glass-card__icon--red"><Route size={18} /></span>
                <span className="stats-glass-card__tag">Issue Tracking</span>
              </div>
              <div className="stats-glass-card__label">Issues</div>
              <div style={{ display: "flex", alignItems: "baseline" }}>
                <span className="stats-glass-card__value">{allIssues.length}</span>
              </div>
            </div>
            <div className="stats-glass-card">
              <div className="stats-glass-card__header">
                <span className="stats-glass-card__icon stats-glass-card__icon--amber"><TestTube2 size={18} /></span>
                <span className="stats-glass-card__tag">Automation</span>
              </div>
              <div className="stats-glass-card__label">Test Pass Rate</div>
              <div style={{ display: "flex", alignItems: "baseline" }}>
                <span className="stats-glass-card__value">{testPassRate}%</span>
                <span className="stats-glass-card__sub">{testPassRate >= 90 ? "All tests passed" : "Some failures"}</span>
              </div>
            </div>
          </div>

          {/* Tabbed Content */}
          <Tabs
            className="workspace-tabs"
            items={[
              {
                key: "source",
                label: "Source & Changes",
                children: (
                  <SourceChangesTab
                    repositories={repositories}
                    pullRequests={allPRs}
                    issues={allIssues}
                  />
                )
              },
              {
                key: "cicd",
                label: "CI/CD & Testing",
                children: (
                  <CICDTestingTab
                    detail={detail}
                    ciMetadata={ciMetadata}
                    testPassRate={testPassRate}
                  />
                )
              }
            ]}
          />
        </>
      ) : null}
    </>
  );
}

/* ─── Source & Changes Tab ─────────────────────────────────────────────── */
function SourceChangesTab({
  repositories,
  pullRequests,
  issues
}: {
  repositories: TraceabilityRepository[];
  pullRequests: PullRequest[];
  issues: Issue[];
}) {
  return (
    <section className="workspace-section" style={{ display: "flex", flexDirection: "column", gap: 32 }}>
      {/* Repositories & Commits */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <Typography.Title level={3} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <GitCommit size={20} style={{ color: "var(--primary)" }} /> Repositories & Commits
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Auto-linked from build metadata
          </Typography.Text>
        </div>
        {repositories.map((repo) => (
          <RepoSection key={repo.repository} repo={repo} />
        ))}
        {repositories.length === 0 ? (
          <Typography.Text type="secondary">No repository data available.</Typography.Text>
        ) : null}
      </div>

      {/* Pull Requests Table */}
      <div>
        <Typography.Title level={3} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <GitPullRequest size={20} style={{ color: "var(--green)" }} /> Linked Pull Requests
        </Typography.Title>
        <Table
          rowKey="external_id"
          dataSource={pullRequests}
          pagination={false}
          columns={[
            { title: "PR#", dataIndex: "external_id", render: (v: string) => <span className="mono" style={{ fontWeight: 600, color: "var(--primary)" }}>{v}</span> },
            { title: "Title", dataIndex: "title", render: (v: string | null | undefined) => <span style={{ fontWeight: 500 }}>{v ?? "Untitled"}</span> },
            { title: "Author", dataIndex: "author", render: (v: string | null | undefined) => v ?? "N/A" },
            { title: "Branch", render: (_: unknown, pr: PullRequest) => <span className="mono" style={{ fontSize: "0.78rem" }}>{pr.source_branch ?? "?"} → {pr.target_branch ?? "?"}</span> },
            {
              title: "Status",
              render: () => (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.78rem" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />
                  Merged
                </span>
              )
            },
            {
              title: "",
              render: (_: unknown, pr: PullRequest) =>
                pr.url ? <a href={pr.url} target="_blank" rel="noreferrer"><ExternalLink size={14} /></a> : null
            }
          ]}
        />
      </div>

      {/* Jira Issues Table */}
      <div>
        <Typography.Title level={3} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Route size={20} style={{ color: "var(--red)" }} /> Linked Issues
        </Typography.Title>
        <Table
          rowKey={(i) => `${i.tracker_type}-${i.external_id}`}
          dataSource={issues}
          pagination={false}
          columns={[
            { title: "Key", dataIndex: "external_id", render: (v: string) => <span className="mono" style={{ fontWeight: 600, color: "var(--primary)" }}>{v}</span> },
            { title: "Summary", dataIndex: "title", render: (v: string | null | undefined) => v ?? "Untitled" },
            { title: "Priority", dataIndex: "priority", render: (v: string | null | undefined) => v ?? "N/A" },
            {
              title: "Status",
              dataIndex: "status",
              render: (v: string | null | undefined) => (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.78rem" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />
                  {v ?? "N/A"}
                </span>
              )
            },
            { title: "Assignee", dataIndex: "assignee", render: (v: string | null | undefined) => v ?? "Unassigned" }
          ]}
        />
      </div>
    </section>
  );
}

/* ─── Expandable Repo Section ──────────────────────────────────────────── */
function RepoSection({ repo }: { repo: TraceabilityRepository }) {
  const [expanded, setExpanded] = useState(true);

  const commitColumns: ColumnsType<CommitTraceability> = [
    {
      title: "Hash",
      dataIndex: "hash",
      width: "15%",
      render: (v: string) => <span className="mono" style={{ color: "var(--primary)", fontSize: "0.78rem" }}>{shortHash(v, 7)}</span>
    },
    { title: "Message", dataIndex: "message", render: (v: string | null | undefined) => <span style={{ fontWeight: 500 }}>{v ?? "No message"}</span> },
    { title: "Author", dataIndex: "author", render: (v: string | null | undefined) => v ?? "N/A", width: "18%" },
    { title: "Date", dataIndex: "committed_at", render: (v: string | null | undefined) => v ? formatDate(v) : "—", width: "18%" },
    {
      title: "PR",
      width: "10%",
      render: (_: unknown, commit: CommitTraceability) =>
        commit.pull_requests.length > 0 ? (
          <span className="mono" style={{ fontSize: "0.78rem", color: "var(--text-faint)" }}>
            {commit.pull_requests.map((pr) => pr.external_id).join(", ")}
          </span>
        ) : "—"
    }
  ];

  return (
    <div className="repo-section">
      <div className="repo-section__header" onClick={() => setExpanded(!expanded)}>
        <div className="repo-section__info">
          {expanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          <span className="repo-section__name">{repo.repository}</span>
          {repo.commits[0]?.branch ? (
            <span className="repo-section__branch-badge">BRANCH: {repo.commits[0].branch}</span>
          ) : null}
        </div>
        <span className="repo-section__count">{repo.commit_count} Commits</span>
      </div>
      {expanded ? (
        <Table
          rowKey="hash"
          dataSource={repo.commits}
          columns={commitColumns}
          size="small"
          pagination={false}
          style={{ borderRadius: 0 }}
        />
      ) : null}
    </div>
  );
}

/* ─── CI/CD & Testing Tab ──────────────────────────────────────────────── */
function CICDTestingTab({
  detail,
  ciMetadata,
  testPassRate
}: {
  detail: ReturnType<typeof useBuild>["data"];
  ciMetadata: Record<string, unknown>;
  testPassRate: number;
}) {
  return (
    <section className="workspace-section">
      <div className="split-panel">
        <div>
          <Typography.Title level={3}>Build Pipeline</Typography.Title>
          <Steps
            direction="vertical"
            current={detail?.status === "released" ? 3 : detail?.status === "testing" ? 2 : 1}
            items={[
              { title: "Manifest stored", description: formatDate(detail?.created_at), icon: <PackageCheck size={18} /> },
              { title: "Traceability hydrated", description: detail?.traceability_incomplete ? "Pending enrichment" : "Complete" },
              { title: "QA validation", description: titleize(detail?.status), icon: <TestTube2 size={18} /> },
              { title: "Immutable release", description: detail?.released_at ? formatDate(detail.released_at) : "Not released", icon: <ShieldCheck size={18} /> }
            ]}
          />
        </div>
        <div>
          <Typography.Title level={3}>Test Results</Typography.Title>
          <div className="quality-strip">
            <div>
              <Typography.Text type="secondary">Pipeline Status</Typography.Text>
              <div>{detail ? <StatusBadge status={detail.status} /> : "N/A"}</div>
            </div>
            <div>
              <Typography.Text type="secondary">Test Pass Rate</Typography.Text>
              <Progress percent={testPassRate} size="small" status={testPassRate >= 90 ? "success" : "active"} />
            </div>
          </div>

          <Typography.Title level={4} style={{ marginTop: 16 }}>CI/CD Metadata</Typography.Title>
          {Object.keys(ciMetadata).length ? (
            <pre className="code-block">{JSON.stringify(ciMetadata, null, 2)}</pre>
          ) : (
            <Alert type="info" showIcon message="No CI/CD metadata was attached for this package." />
          )}
        </div>
      </div>
    </section>
  );
}

/* ─── Helpers ──────────────────────────────────────────────────────────── */
function inferPassRate(ciMetadata: Record<string, unknown>): number {
  const tests = ciMetadata.test_results;
  if (tests && typeof tests === "object") {
    const record = tests as Record<string, unknown>;
    const passed = Number(record.passed ?? 0);
    const failed = Number(record.failed ?? 0);
    const skipped = Number(record.skipped ?? 0);
    const total = passed + failed + skipped;
    return total ? Math.round((passed / total) * 100) : 0;
  }
  return 0;
}

function uniqueItems<T>(items: T[], keyFn: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = keyFn(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
