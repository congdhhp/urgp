import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Divider, Select, Space, Statistic, Table, Tabs, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { CheckCircle2, Download, ExternalLink, GitCommit, GitPullRequest, Package, Route, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { TraceabilityGraph } from "../components/TraceabilityGraph";
import { transitionBuildStatus, verifyBuild } from "../lib/api";
import { artifactChecksum, artifactMetadata, formatBytes, formatDate, shortHash, titleize } from "../lib/format";
import { useArtifacts, useBuild, useTraceability } from "../hooks/usePlatformQueries";
import type { Artifact, BuildStatus, Issue, PullRequest } from "../types";

const nextStatuses: BuildStatus[] = ["testing", "released", "deprecated"];

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
            <Button
              icon={<ShieldCheck size={16} />}
              loading={verificationMutation.isPending}
              onClick={() => verificationMutation.mutate()}
            >
              Verify Integrity
            </Button>
          </Space>
        }
      />

      {detail?.traceability_incomplete ? (
        <Alert
          type="warning"
          showIcon
          className="content-alert"
          message="Traceability is incomplete"
          description="Some commit, PR, or issue enrichment data may be missing for this build."
        />
      ) : null}

      <Tabs
        className="workspace-tabs"
        items={[
          {
            key: "summary",
            label: "Summary",
            children: detail ? (
              <SummaryTab
                detail={detail}
                targetStatus={targetStatus}
                onTargetStatusChange={setTargetStatus}
                onTransition={() => transitionMutation.mutate()}
                transitioning={transitionMutation.isPending}
                verification={verificationMutation.data}
              />
            ) : null
          },
          {
            key: "packages",
            label: `Packages (${artifacts.length})`,
            children: <PackagesTab artifacts={artifacts} product={product} build={build} loading={artifactsQuery.isLoading} />
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
          }
        ]}
      />
    </>
  );
}

function SummaryTab({
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
      <div className="build-summary-grid">
        <Statistic title="Artifacts" value={detail.artifact_count} prefix={<Package size={18} />} />
        <Statistic title="Commits" value={detail.commit_count} prefix={<GitCommit size={18} />} />
        <Statistic title="Pull Requests" value={detail.pull_request_count} prefix={<GitPullRequest size={18} />} />
        <Statistic title="Issues" value={detail.issue_count} prefix={<Route size={18} />} />
      </div>

      <Descriptions bordered size="small" column={{ xs: 1, md: 2, xl: 3 }} className="description-table">
        <Descriptions.Item label="Product">{detail.product_name}</Descriptions.Item>
        <Descriptions.Item label="Product ID">{detail.product_id}</Descriptions.Item>
        <Descriptions.Item label="Release">{detail.release ?? "Unassigned"}</Descriptions.Item>
        <Descriptions.Item label="Build Type">{titleize(detail.build_type)}</Descriptions.Item>
        <Descriptions.Item label="Status">
          <StatusBadge status={detail.status} />
        </Descriptions.Item>
        <Descriptions.Item label="CLI Version">{detail.cli_version ?? "N/A"}</Descriptions.Item>
        <Descriptions.Item label="Created">{formatDate(detail.created_at)}</Descriptions.Item>
        <Descriptions.Item label="Updated">{formatDate(detail.updated_at)}</Descriptions.Item>
        <Descriptions.Item label="Released">{formatDate(detail.released_at)}</Descriptions.Item>
        <Descriptions.Item label="Signature" span={3}>
          <Typography.Text code copyable>
            {detail.signature ?? "N/A"}
          </Typography.Text>
        </Descriptions.Item>
      </Descriptions>

      <Divider />

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
          type={verification.integrity_status === "valid" ? "success" : "error"}
          showIcon
          message={`Integrity status: ${titleize(verification.integrity_status)}`}
          description={`${verification.artifacts.length} artifacts checked at ${formatDate(verification.verification_timestamp)}.`}
        />
      ) : null}
    </section>
  );
}

function PackagesTab({
  artifacts,
  product,
  build,
  loading
}: {
  artifacts: Artifact[];
  product: string;
  build: string;
  loading: boolean;
}) {
  const columns: ColumnsType<Artifact> = [
    {
      title: "Package",
      dataIndex: "name",
      render: (_, artifact) => (
        <Link to={`/packages/${encodeURIComponent(product)}/${encodeURIComponent(build)}/${encodeURIComponent(artifact.id)}`}>
          {artifact.name}
        </Link>
      )
    },
    { title: "Type", dataIndex: "type", render: titleize },
    { title: "Size", dataIndex: "size_bytes", render: formatBytes },
    {
      title: "Checksum",
      render: (_, artifact) => (
        <Typography.Text code copyable={{ text: artifactChecksum(artifact) }}>
          {shortHash(artifactChecksum(artifact), 16)}
        </Typography.Text>
      )
    },
    {
      title: "Access",
      render: (_, artifact) =>
        artifact.type === "oci_image" ? (
          <Typography.Text code copyable>
            docker pull {artifact.storage_uri}
          </Typography.Text>
        ) : (
          <Button href={artifact.storage_uri} target="_blank" icon={<Download size={16} />}>
            Download
          </Button>
        )
    }
  ];

  return (
    <section className="workspace-section">
      <Table rowKey="id" columns={columns} dataSource={artifacts} loading={loading} scroll={{ x: 900 }} />
    </section>
  );
}

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

function uniqueIssues(issues: Issue[]): Issue[] {
  const seen = new Set<string>();
  return issues.filter((issue) => {
    const key = `${issue.tracker_type}:${issue.external_id}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function uniquePullRequests(pullRequests: PullRequest[]): PullRequest[] {
  const seen = new Set<string>();
  return pullRequests.filter((pullRequest) => {
    if (seen.has(pullRequest.external_id)) {
      return false;
    }
    seen.add(pullRequest.external_id);
    return true;
  });
}
