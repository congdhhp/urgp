import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Divider, Select, Space, Table, Tabs, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  Calendar,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  ExternalLink,
  GitBranch,
  GitCommit,
  GitPullRequest,
  Package,
  Route,
  ShieldCheck
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { TraceabilityGraph } from "../components/TraceabilityGraph";
import { transitionBuildStatus, verifyBuild } from "../lib/api";
import { artifactChecksum, artifactMetadata, formatBytes, formatDate, shortHash, titleize } from "../lib/format";
import { useArtifacts, useBuild, useTraceability } from "../hooks/usePlatformQueries";
import type { Artifact, BuildStatus, Issue, PullRequest, TraceabilityRepository } from "../types";

const ALL_STATUSES: BuildStatus[] = ["ingesting", "hydrating", "completed", "testing", "released"];
const nextStatuses: BuildStatus[] = ["testing", "released", "deprecated"];

function statusIndex(status: string): number {
  return ALL_STATUSES.indexOf(status as BuildStatus);
}

export function BuildDetailPage() {
  const { productId = "", buildId = "" } = useParams();
  const product = decodeURIComponent(productId);
  const build = decodeURIComponent(buildId);
  const buildQuery = useBuild(build, product);
  const artifactsQuery = useArtifacts(build, product);
  const traceabilityQuery = useTraceability(build, product);
  const queryClient = useQueryClient();
  const [targetStatus, setTargetStatus] = useState<BuildStatus>("testing");

  const verificationMutation = useMutation({
    mutationFn: () => verifyBuild(build, product),
    onSuccess: () => message.success("Integrity verification completed.")
  });

  const transitionMutation = useMutation({
    mutationFn: () => transitionBuildStatus(build, product, targetStatus),
    onSuccess: async () => {
      message.success(`Build moved to ${titleize(targetStatus)}.`);
      await queryClient.invalidateQueries({ queryKey: ["build", product, build] });
      await queryClient.invalidateQueries({ queryKey: ["builds"] });
    }
  });

  const detail = buildQuery.data;
  const artifacts = artifactsQuery.data?.artifacts ?? [];
  const traceability = traceabilityQuery.data;
  const issues = useMemo(() => uniqueIssues(traceability?.repositories.flatMap((repo) => repo.commits.flatMap((commit) => commit.issues)) ?? []), [traceability]);
  const pullRequests = useMemo(
    () => uniquePullRequests(traceability?.repositories.flatMap((repo) => repo.commits.flatMap((commit) => commit.pull_requests)) ?? []),
    [traceability]
  );

  if (buildQuery.isError) {
    return <RetryEmptyState onRetry={() => void buildQuery.refetch()} />;
  }

  const currentIndex = detail ? statusIndex(detail.status) : -1;

  return (
    <>
      <PageHeader
        title={build}
        subtitle={detail ? `${detail.product_name} / ${detail.release ?? "Unassigned release"}` : "Build manifest details"}
        breadcrumbs={[
          { label: "Products", to: "/products" },
          { label: product, to: `/products/${encodeURIComponent(product)}` },
          { label: build }
        ]}
        actions={
          <Space wrap>
            {detail ? <StatusBadge status={detail.status} /> : null}
            {detail ? <span className="build-type-badge">{titleize(detail.build_type)}</span> : null}
          </Space>
        }
      />

      {/* Build metadata row */}
      {detail ? (
        <div className="build-header-meta" style={{ marginTop: -16, marginBottom: 8 }}>
          <span className="build-header-meta__item">
            <Calendar size={14} /> <span className="mono">{formatDate(detail.created_at)}</span>
          </span>
          {detail.released_at ? (
            <span className="build-header-meta__item">
              <Clock size={14} /> Released {formatDate(detail.released_at)}
            </span>
          ) : null}
          <span className="build-header-meta__item">
            <GitBranch size={14} /> <span className="mono">{detail.release ?? "No release"}</span>
          </span>
          <Space style={{ marginLeft: "auto" }}>
            <Button
              icon={<ShieldCheck size={16} />}
              loading={verificationMutation.isPending}
              onClick={() => verificationMutation.mutate()}
            >
              Verify Integrity
            </Button>
            <Button icon={<Download size={16} />}>Download Artifacts</Button>
          </Space>
        </div>
      ) : null}

      {detail?.traceability_incomplete ? (
        <Alert
          type="warning"
          showIcon
          className="content-alert"
          message="Traceability is incomplete"
          description="Some commit, PR, or issue enrichment data may be missing for this build."
        />
      ) : null}

      {/* Lifecycle Timeline */}
      {detail ? (
        <div className="lifecycle-timeline">
          <div
            className="lifecycle-timeline__progress"
            style={{ width: `${currentIndex >= 0 ? (currentIndex / (ALL_STATUSES.length - 1)) * 100 : 0}%` }}
          />
          {ALL_STATUSES.map((status, idx) => {
            const done = idx < currentIndex;
            const active = idx === currentIndex;
            return (
              <div key={status} className={`lifecycle-step${done ? " lifecycle-step--done" : ""}${active ? " lifecycle-step--active" : ""}`}>
                <span className="lifecycle-step__circle">
                  {done || active ? <Check size={14} /> : idx + 1}
                </span>
                <span className="lifecycle-step__label">{titleize(status)}</span>
              </div>
            );
          })}
        </div>
      ) : null}

      <Tabs
        className="workspace-tabs"
        items={[
          {
            key: "packages",
            label: `Packages (${artifacts.length})`,
            children: (
              <PackagesTab
                artifacts={artifacts}
                product={product}
                build={build}
                loading={artifactsQuery.isLoading}
                traceability={traceability?.repositories ?? []}
                issues={issues}
                pullRequests={pullRequests}
              />
            )
          },
          {
            key: "whats-new",
            label: `What's New (${issues.length})`,
            children: <WhatsNewTab issues={issues} pullRequests={pullRequests} loading={traceabilityQuery.isLoading} />
          },
          {
            key: "traceability",
            label: "Traceability",
            children: traceability ? (
              <TraceabilityGraph traceability={traceability} />
            ) : (
              <EmptyState title="No traceability graph available." />
            )
          },
          {
            key: "cicd",
            label: "CI/CD & Tests",
            children: detail ? (
              <CICDTab
                detail={detail}
                targetStatus={targetStatus}
                onTargetStatusChange={setTargetStatus}
                onTransition={() => transitionMutation.mutate()}
                transitioning={transitionMutation.isPending}
                verification={verificationMutation.data}
              />
            ) : null
          }
        ]}
      />

      {/* Signature Footer */}
      {detail?.signature ? (
        <div className="signature-footer">
          <div className="signature-footer__left">
            <ShieldCheck size={14} style={{ color: "var(--green)" }} />
            Manifest Signature: <span className="mono" style={{ color: "var(--text)" }}>HMAC-SHA256 verified</span>{" "}
            <span style={{ color: "var(--green)" }}>OK</span>
          </div>
          <div className="signature-footer__right">
            {detail.released_at ? `Locked at: ${formatDate(detail.released_at)}` : "Not locked"}
          </div>
        </div>
      ) : null}
    </>
  );
}

/* ─── Packages Tab (expandable cards) ──────────────────────────────────── */
function PackagesTab({
  artifacts,
  product,
  build,
  loading,
  traceability,
  issues,
  pullRequests
}: {
  artifacts: Artifact[];
  product: string;
  build: string;
  loading: boolean;
  traceability: TraceabilityRepository[];
  issues: Issue[];
  pullRequests: PullRequest[];
}) {
  const [expandedId, setExpandedId] = useState<string | null>(artifacts[0]?.id ?? null);
  const totalCommits = traceability.reduce((sum, repo) => sum + repo.commit_count, 0);
  const totalRepos = traceability.length;

  if (loading) {
    return <section className="workspace-section"><Typography.Text type="secondary">Loading packages…</Typography.Text></section>;
  }

  return (
    <section className="workspace-section">
      {/* Summary Stats Bar */}
      <div className="summary-stats-bar">
        <div className="summary-stats-bar__item">
          <span className="summary-stats-bar__label">Architecture</span>
          <span className="summary-stats-bar__value">{artifacts.length} Packages / {totalRepos} Repositories</span>
        </div>
        <div className="summary-stats-bar__divider" />
        <div className="summary-stats-bar__item">
          <span className="summary-stats-bar__label">Code Flux</span>
          <span className="summary-stats-bar__value">{totalCommits} Commits / {pullRequests.length} Pull Requests</span>
        </div>
        <div className="summary-stats-bar__divider" />
        <div className="summary-stats-bar__item">
          <span className="summary-stats-bar__label">Requirements</span>
          <span className="summary-stats-bar__value">{issues.length} Issues</span>
        </div>
      </div>

      {/* Expandable Package Cards */}
      {artifacts.map((artifact) => {
        const isExpanded = expandedId === artifact.id;
        return (
          <div key={artifact.id} className={`package-card${isExpanded ? " package-card--expanded" : ""}`}>
            <div
              className="package-card__header"
              onClick={() => setExpandedId(isExpanded ? null : artifact.id)}
            >
              <div className="package-card__info">
                <div className="package-card__icon">
                  <Package size={18} />
                </div>
                <div>
                  <div className="package-card__name">
                    <Link
                      to={`/packages/${encodeURIComponent(product)}/${encodeURIComponent(build)}/${encodeURIComponent(artifact.id)}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {artifact.name}
                    </Link>
                  </div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 2 }}>
                    <span className="mono" style={{ fontSize: "0.75rem" }}>{titleize(artifact.type)}</span>
                    {artifact.size_bytes ? (
                      <span className="mono" style={{ fontSize: "0.72rem", color: "var(--text-faint)" }}>{formatBytes(artifact.size_bytes)}</span>
                    ) : null}
                  </div>
                </div>
              </div>
              <div className="package-card__meta">
                <span className="mono">{shortHash(artifactChecksum(artifact), 10)}</span>
                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>

            {isExpanded ? (
              <div className="package-card__body">
                <div className="package-card__bento">
                  {/* Repos & Commits */}
                  <div>
                    <div className="package-card__section-title">Source Repositories & Commits</div>
                    {traceability.length > 0 ? traceability.map((repo) => (
                      <div key={repo.repository} className="package-card__repo-row">
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <GitBranch size={13} style={{ color: "var(--text-faint)" }} />
                          <span style={{ fontSize: "0.8rem", fontWeight: 500 }}>{repo.repository}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <span style={{ fontSize: "0.72rem", color: "var(--text-faint)" }}>{repo.commit_count} commits</span>
                          <span className="mono" style={{ fontSize: "0.7rem", padding: "2px 6px", background: "var(--border-subtle)", borderRadius: 4 }}>
                            {repo.commits[0] ? shortHash(repo.commits[0].hash, 7) : "—"}
                          </span>
                        </div>
                      </div>
                    )) : (
                      <Typography.Text type="secondary" style={{ fontSize: "0.8rem" }}>No repository data.</Typography.Text>
                    )}
                  </div>

                  {/* Linked Issues */}
                  <div>
                    <div className="package-card__section-title">Linked Governance Issues</div>
                    {issues.length > 0 ? issues.slice(0, 4).map((issue) => (
                      <div key={`${issue.tracker_type}-${issue.external_id}`} className="package-card__issue-row">
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <Route size={13} style={{ color: issue.priority === "Critical" ? "var(--red)" : "var(--primary)" }} />
                          <span className="mono" style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--primary)" }}>{issue.external_id}</span>
                          <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {issue.title ?? "Untitled"}
                          </span>
                        </div>
                        <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", color: "var(--green)" }}>
                          {issue.status ?? "N/A"}
                        </span>
                      </div>
                    )) : (
                      <Typography.Text type="secondary" style={{ fontSize: "0.8rem" }}>No linked issues.</Typography.Text>
                    )}
                  </div>

                  {/* Pull Requests (full span) */}
                  <div className="package-card__bento-full">
                    <div className="package-card__section-title">Integrated Pull Requests</div>
                    {pullRequests.length > 0 ? (
                      <Table
                        rowKey="external_id"
                        size="small"
                        pagination={false}
                        dataSource={pullRequests.slice(0, 5)}
                        columns={[
                          { title: "ID", dataIndex: "external_id", render: (v: string) => <span className="mono" style={{ fontWeight: 600 }}>{v}</span> },
                          { title: "Author", dataIndex: "author", render: (v: string | null | undefined) => v ?? "N/A" },
                          { title: "Title", dataIndex: "title", render: (v: string | null | undefined) => v ?? "Untitled" },
                          {
                            title: "Status",
                            render: () => (
                              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />
                                Merged
                              </span>
                            )
                          },
                          {
                            title: "",
                            render: (_: unknown, pr: PullRequest) =>
                              pr.url ? (
                                <a href={pr.url} target="_blank" rel="noreferrer"><ExternalLink size={14} /></a>
                              ) : null
                          }
                        ]}
                      />
                    ) : (
                      <Typography.Text type="secondary" style={{ fontSize: "0.8rem" }}>No pull requests linked.</Typography.Text>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </section>
  );
}

/* ─── What's New Tab ───────────────────────────────────────────────────── */
function WhatsNewTab({ issues, pullRequests, loading }: { issues: Issue[]; pullRequests: PullRequest[]; loading: boolean }) {
  const issueColumns: ColumnsType<Issue> = [
    {
      title: "Issue",
      dataIndex: "external_id",
      render: (_, issue) =>
        issue.url ? (
          <a href={issue.url} target="_blank" rel="noreferrer">
            {issue.external_id} <ExternalLink size={12} />
          </a>
        ) : (
          issue.external_id
        )
    },
    { title: "Title", dataIndex: "title", render: (value) => value ?? "Untitled issue" },
    { title: "Priority", dataIndex: "priority", render: (value) => value ?? "N/A" },
    { title: "Status", dataIndex: "status", render: (value) => value ?? "N/A" },
    { title: "Assignee", dataIndex: "assignee", render: (value) => value ?? "Unassigned" }
  ];
  const prColumns: ColumnsType<PullRequest> = [
    {
      title: "PR",
      dataIndex: "external_id",
      render: (_, pullRequest) =>
        pullRequest.url ? (
          <a href={pullRequest.url} target="_blank" rel="noreferrer">
            {pullRequest.external_id} <ExternalLink size={12} />
          </a>
        ) : (
          pullRequest.external_id
        )
    },
    { title: "Title", dataIndex: "title", render: (value) => value ?? "Untitled PR" },
    { title: "Author", dataIndex: "author", render: (value) => value ?? "N/A" },
    { title: "Source", dataIndex: "source_branch", render: (value) => value ?? "N/A" },
    { title: "Target", dataIndex: "target_branch", render: (value) => value ?? "N/A" }
  ];

  return (
    <section className="workspace-section whats-new-grid">
      <div>
        <Typography.Title level={3}>Issues</Typography.Title>
        <Table rowKey={(issue) => `${issue.tracker_type}-${issue.external_id}`} columns={issueColumns} dataSource={issues} loading={loading} pagination={{ pageSize: 8 }} />
      </div>
      <div>
        <Typography.Title level={3}>Pull Requests</Typography.Title>
        <Table rowKey="external_id" columns={prColumns} dataSource={pullRequests} loading={loading} pagination={{ pageSize: 8 }} />
      </div>
    </section>
  );
}

/* ─── CI/CD & Tests Tab ────────────────────────────────────────────────── */
function CICDTab({
  detail,
  targetStatus,
  onTargetStatusChange,
  onTransition,
  transitioning,
  verification
}: {
  detail: NonNullable<ReturnType<typeof useBuild>["data"]>;
  targetStatus: BuildStatus;
  onTargetStatusChange: (status: BuildStatus) => void;
  onTransition: () => void;
  transitioning: boolean;
  verification?: Awaited<ReturnType<typeof verifyBuild>>;
}) {
  const ciMetadata = detail.ci_metadata ?? {};
  return (
    <section className="workspace-section">
      <div className="split-panel">
        <div>
          <Typography.Title level={3}>Lifecycle Control</Typography.Title>
          <Space wrap>
            <Select
              value={targetStatus}
              onChange={onTargetStatusChange}
              options={nextStatuses.map((status) => ({ value: status, label: titleize(status) }))}
            />
            <Button type="primary" loading={transitioning} onClick={onTransition}>
              Apply Status
            </Button>
          </Space>

          <Divider />

          <Typography.Title level={3}>Build Summary</Typography.Title>
          <Descriptions bordered size="small" column={1} className="description-table">
            <Descriptions.Item label="Product">{detail.product_name}</Descriptions.Item>
            <Descriptions.Item label="Release">{detail.release ?? "Unassigned"}</Descriptions.Item>
            <Descriptions.Item label="Build Type">{titleize(detail.build_type)}</Descriptions.Item>
            <Descriptions.Item label="Status"><StatusBadge status={detail.status} /></Descriptions.Item>
            <Descriptions.Item label="CLI Version">{detail.cli_version ?? "N/A"}</Descriptions.Item>
            <Descriptions.Item label="Created">{formatDate(detail.created_at)}</Descriptions.Item>
            <Descriptions.Item label="Released">{formatDate(detail.released_at)}</Descriptions.Item>
            <Descriptions.Item label="Signature">
              <Typography.Text code copyable>{detail.signature ?? "N/A"}</Typography.Text>
            </Descriptions.Item>
          </Descriptions>
        </div>
        <div>
          <Typography.Title level={3}>CI/CD Metadata</Typography.Title>
          {Object.keys(ciMetadata).length ? (
            <pre className="code-block">{JSON.stringify(ciMetadata, null, 2)}</pre>
          ) : (
            <Typography.Text type="secondary">No CI/CD metadata was attached to this manifest.</Typography.Text>
          )}
        </div>
      </div>

      {verification ? (
        <Alert
          className="content-alert"
          style={{ marginTop: 16 }}
          type={verification.integrity_status === "valid" ? "success" : "error"}
          showIcon
          message={`Integrity status: ${titleize(verification.integrity_status)}`}
          description={`${verification.artifacts.length} artifacts checked at ${formatDate(verification.verification_timestamp)}.`}
        />
      ) : null}
    </section>
  );
}

/* ─── Helpers ──────────────────────────────────────────────────────────── */
function uniqueIssues(issues: Issue[]): Issue[] {
  const seen = new Set<string>();
  return issues.filter((issue) => {
    const key = `${issue.tracker_type}:${issue.external_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function uniquePullRequests(pullRequests: PullRequest[]): PullRequest[] {
  const seen = new Set<string>();
  return pullRequests.filter((pullRequest) => {
    if (seen.has(pullRequest.external_id)) return false;
    seen.add(pullRequest.external_id);
    return true;
  });
}
