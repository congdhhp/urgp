import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Select, Space, Table, Tabs, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ArrowRight, Download, FileJson, GitCommit, Play } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { compareBuilds } from "../lib/api";
import { comparisonToCsv, diffArtifacts } from "../lib/compareUtils";
import { artifactChecksum, formatDate, shortHash, titleize } from "../lib/format";
import { useArtifacts, useBuild, useBuilds, useProducts } from "../hooks/usePlatformQueries";
import type { Artifact, Issue, PullRequest } from "../types";

export function ComparisonPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [product, setProduct] = useState(searchParams.get("product") ?? "");
  const [start, setStart] = useState(searchParams.get("start") ?? "");
  const [end, setEnd] = useState(searchParams.get("end") ?? "");

  const productsQuery = useProducts();
  const buildsQuery = useBuilds({ product_id: product || undefined, limit: 200 }, Boolean(product));
  const startArtifactsQuery = useArtifacts(start, product);
  const endArtifactsQuery = useArtifacts(end, product);
  const startBuildQuery = useBuild(start, product);
  const endBuildQuery = useBuild(end, product);

  const comparisonQuery = useQuery({
    queryKey: ["comparison", product, start, end],
    queryFn: () => compareBuilds(start, end, product),
    enabled: Boolean(product && start && end)
  });

  const artifactDiff = useMemo(
    () => diffArtifacts(startArtifactsQuery.data?.artifacts ?? [], endArtifactsQuery.data?.artifacts ?? []),
    [endArtifactsQuery.data?.artifacts, startArtifactsQuery.data?.artifacts]
  );

  useEffect(() => {
    if (!product || !start || !end) return;
    setSearchParams({ product, start, end });
  }, [end, product, setSearchParams, start]);

  const buildOptions = (buildsQuery.data?.items ?? []).map((build) => ({
    value: build.build_id,
    label: `${build.build_id} / ${build.release ?? "no release"} / ${titleize(build.status)}`
  }));

  function exportJson() {
    if (!comparisonQuery.data) return;
    downloadText(
      `urgp-comparison-${start}-${end}.json`,
      JSON.stringify({ comparison: comparisonQuery.data, packages: artifactDiff }, null, 2),
      "application/json"
    );
  }

  function exportCsv() {
    if (!comparisonQuery.data) return;
    downloadText(`urgp-comparison-${start}-${end}.csv`, comparisonToCsv(comparisonQuery.data, artifactDiff), "text/csv");
  }

  return (
    <>
      <PageHeader
        title="Build Comparison"
        subtitle="Compare two build manifests across issues, pull requests, commits, and package checksums."
        breadcrumbs={[{ label: "Comparisons" }]}
        actions={
          <Space wrap>
            <Button icon={<FileJson size={16} />} disabled={!comparisonQuery.data} onClick={exportJson}>
              Export JSON
            </Button>
            <Button icon={<Download size={16} />} disabled={!comparisonQuery.data} onClick={exportCsv}>
              Export CSV
            </Button>
          </Space>
        }
      />

      {/* Build Picker */}
      <section className="workspace-section compare-picker">
        <Select
          placeholder="Select product"
          value={product || undefined}
          onChange={(value) => {
            setProduct(value);
            setStart("");
            setEnd("");
          }}
          options={(productsQuery.data?.items ?? []).map((item) => ({ value: item.external_id, label: item.name }))}
        />
        <Select
          showSearch
          placeholder="Start build"
          value={start || undefined}
          onChange={setStart}
          options={buildOptions}
          optionFilterProp="label"
          disabled={!product}
        />
        <Select
          showSearch
          placeholder="End build"
          value={end || undefined}
          onChange={setEnd}
          options={buildOptions}
          optionFilterProp="label"
          disabled={!product}
        />
        <Button
          type="primary"
          icon={<Play size={16} />}
          loading={comparisonQuery.isFetching}
          disabled={!product || !start || !end}
          onClick={() => {
            void comparisonQuery.refetch();
            message.info("Comparison refreshed.");
          }}
        >
          Compare
        </Button>
      </section>

      {/* Side-by-side build info cards */}
      {comparisonQuery.data && start && end ? (
        <>
          <div className="compare-builds-layout">
            <BuildInfoCard label="Start Build" buildId={start} data={startBuildQuery.data} />
            <div className="compare-arrow"><ArrowRight size={24} /></div>
            <BuildInfoCard label="End Build" buildId={end} data={endBuildQuery.data} />
          </div>

          <Tabs
            className="workspace-tabs"
            items={[
              {
                key: "issues",
                label: `Issues (${comparisonQuery.data.unique_issues.length})`,
                children: <IssueDiffGrouped issues={comparisonQuery.data.unique_issues} />
              },
              {
                key: "pull-requests",
                label: `Pull Requests (${comparisonQuery.data.unique_pull_requests.length})`,
                children: <PullRequestDiffTable pullRequests={comparisonQuery.data.unique_pull_requests} />
              },
              {
                key: "packages",
                label: `Packages (${artifactDiff.added.length + artifactDiff.removed.length + artifactDiff.changed.length})`,
                children: <PackageDiffTable diff={artifactDiff} />
              },
              {
                key: "commits",
                label: `Commits (${comparisonQuery.data.unique_commits.length})`,
                children: <CommitDiffTable commits={comparisonQuery.data.unique_commits} />
              }
            ]}
          />
        </>
      ) : (
        <EmptyState title="Select a product and two builds to compare." />
      )}
    </>
  );
}

/* ─── Build Info Card ──────────────────────────────────────────────────── */
function BuildInfoCard({
  label,
  buildId,
  data
}: {
  label: string;
  buildId: string;
  data?: ReturnType<typeof useBuild>["data"];
}) {
  return (
    <div className="compare-build-card">
      <div className="compare-build-card__label">{label}</div>
      <div className="compare-build-card__id">{buildId}</div>
      {data ? (
        <div className="compare-build-card__stats">
          <span className="compare-build-card__stat">
            <StatusBadge status={data.status} />
          </span>
          <span className="compare-build-card__stat">{data.artifact_count} pkgs</span>
          <span className="compare-build-card__stat">{data.commit_count} commits</span>
          <span className="compare-build-card__stat">{formatDate(data.created_at)}</span>
        </div>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: "0.8rem" }}>Loading…</Typography.Text>
      )}
    </div>
  );
}

/* ─── Issues grouped by priority ───────────────────────────────────────── */
function IssueDiffGrouped({ issues }: { issues: Issue[] }) {
  const grouped = useMemo(() => {
    const groups: Record<string, Issue[]> = {};
    for (const issue of issues) {
      const priority = issue.priority ?? "Normal";
      if (!groups[priority]) groups[priority] = [];
      groups[priority].push(issue);
    }
    return groups;
  }, [issues]);

  const priorityOrder = ["Critical", "Major", "Normal", "Minor"];
  const priorityIcons: Record<string, string> = {
    Critical: "priority-group__icon--critical",
    Major: "priority-group__icon--major",
    Normal: "priority-group__icon--normal",
    Minor: "priority-group__icon--minor"
  };

  const columns: ColumnsType<Issue> = [
    { title: "Issue", dataIndex: "external_id", render: (v: string) => <span className="mono" style={{ fontWeight: 600 }}>{v}</span> },
    { title: "Title", dataIndex: "title", render: (value: string | null | undefined) => value ?? "Untitled" },
    { title: "Priority", dataIndex: "priority", render: (value: string | null | undefined) => value ?? "N/A" },
    { title: "Status", dataIndex: "status", render: (value: string | null | undefined) => value ?? "N/A" },
    { title: "Assignee", dataIndex: "assignee", render: (value: string | null | undefined) => value ?? "Unassigned" }
  ];

  const sortedKeys = Object.keys(grouped).sort((a, b) => {
    const ai = priorityOrder.indexOf(a);
    const bi = priorityOrder.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  if (issues.length === 0) {
    return <EmptyState title="No issues differ between these builds." />;
  }

  return (
    <section className="workspace-section">
      {sortedKeys.map((priority) => (
        <div key={priority} className="priority-group">
          <div className="priority-group__header">
            <span className={`priority-group__icon ${priorityIcons[priority] ?? "priority-group__icon--normal"}`}>
              {priority === "Critical" ? "!!" : priority === "Major" ? "!" : "·"}
            </span>
            <span className="priority-group__label">{priority}</span>
            <span className="priority-group__count">{grouped[priority].length} issues</span>
          </div>
          <Table
            rowKey={(issue) => `${issue.tracker_type}-${issue.external_id}`}
            columns={columns}
            dataSource={grouped[priority]}
            pagination={false}
            size="small"
          />
        </div>
      ))}
    </section>
  );
}

/* ─── Pull Requests Table ──────────────────────────────────────────────── */
function PullRequestDiffTable({ pullRequests }: { pullRequests: PullRequest[] }) {
  const columns: ColumnsType<PullRequest> = [
    { title: "PR", dataIndex: "external_id", render: (v: string) => <span className="mono" style={{ fontWeight: 600 }}>{v}</span> },
    { title: "Title", dataIndex: "title", render: (value: string | null | undefined) => value ?? "Untitled" },
    { title: "Author", dataIndex: "author", render: (value: string | null | undefined) => value ?? "N/A" },
    { title: "Branch", render: (_: unknown, pr: PullRequest) => <span className="mono" style={{ fontSize: "0.78rem" }}>{pr.source_branch ?? "?"} → {pr.target_branch ?? "?"}</span> },
    {
      title: "Status",
      render: () => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)" }} />
          Merged
        </span>
      )
    }
  ];
  return (
    <section className="workspace-section">
      <Table rowKey="external_id" columns={columns} dataSource={pullRequests} />
    </section>
  );
}

/* ─── Package Diff Table (color-coded badges) ──────────────────────────── */
function PackageDiffTable({ diff }: { diff: ReturnType<typeof diffArtifacts> }) {
  const rows = [
    ...diff.added.map((artifact) => ({ kind: "Added" as const, artifact })),
    ...diff.removed.map((artifact) => ({ kind: "Removed" as const, artifact })),
    ...diff.changed.map(({ after }) => ({ kind: "Changed" as const, artifact: after }))
  ];

  const columns: ColumnsType<{ kind: string; artifact: Artifact }> = [
    {
      title: "Diff",
      dataIndex: "kind",
      width: 100,
      render: (kind: string) => {
        const cls = kind === "Added" ? "diff-badge--added" : kind === "Removed" ? "diff-badge--removed" : "diff-badge--changed";
        return <span className={`diff-badge ${cls}`}>{kind}</span>;
      }
    },
    { title: "Package", render: (_, row) => row.artifact.name },
    { title: "Type", render: (_, row) => titleize(row.artifact.type) },
    {
      title: "Checksum",
      render: (_, row) => (
        <Typography.Text code copyable={{ text: artifactChecksum(row.artifact) }}>
          {shortHash(artifactChecksum(row.artifact), 16)}
        </Typography.Text>
      )
    }
  ];
  return (
    <section className="workspace-section">
      <Table rowKey={(row) => `${row.kind}-${row.artifact.id}`} columns={columns} dataSource={rows} />
    </section>
  );
}

/* ─── Commits Table ────────────────────────────────────────────────────── */
function CommitDiffTable({ commits }: { commits: string[] }) {
  const rows = commits.map((commit) => ({ commit }));
  return (
    <section className="workspace-section">
      <Table
        rowKey="commit"
        dataSource={rows}
        columns={[
          {
            title: "Commit Hash",
            dataIndex: "commit",
            render: (value: string) => (
              <Space>
                <GitCommit size={16} />
                <Typography.Text code copyable>{value}</Typography.Text>
              </Space>
            )
          }
        ]}
      />
    </section>
  );
}

/* ─── Utility ──────────────────────────────────────────────────────────── */
function downloadText(filename: string, text: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
